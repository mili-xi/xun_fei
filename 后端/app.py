import json
import logging
import os
import re
import tempfile
import time
import uuid
from io import BytesIO
from pathlib import Path

from flask import Flask, jsonify, request, send_file, send_from_directory

import bootstrap  # noqa: F401
import config


LOGGER = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", str(BASE_DIR / "前端"))).resolve()
# 确保前端目录存在（便携版分发）
if not FRONTEND_DIR.exists():
    raise RuntimeError(
        f"前端目录不存在: {FRONTEND_DIR}。请确认 '前端/' 目录与后端代码在同一父目录下。"
    )
SESSIONS = {}
ANALYSES = {}
ANALYSIS_VARIANT_COUNTER = 0
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(60 * 60 * 6)))
ANALYSIS_TTL_SECONDS = int(os.getenv("ANALYSIS_TTL_SECONDS", str(60 * 60 * 2)))


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    app.json.ensure_ascii = False
    app.config.update(test_config or {})

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "front.html")

    @app.get("/front.html")
    def front_html():
        return send_from_directory(FRONTEND_DIR, "front.html")

    @app.get("/unified.html")
    def unified_html():
        return send_from_directory(FRONTEND_DIR, "unified.html")

    @app.get("/api/health")
    def health():
        launch_token = os.getenv("XUNFEI_LAUNCH_TOKEN", "")
        if launch_token and request.headers.get("X-Xunfei-Launch-Token") != launch_token:
            return error_response("unauthorized health check", 401)
        return ok_response(
            data={
                "status": "ok",
                "frontend_dir_exists": FRONTEND_DIR.exists(),
                "ffmpeg_available": config.ffmpeg_is_available(),
                "spark_configured": bool(config.IFLYTEK_SPARK_API_PASSWORD),
                "ocr_configured": bool(config.IFLYTEK_APP_ID and config.IFLYTEK_API_KEY and config.IFLYTEK_API_SECRET),
                "voice_configured": has_voice_credentials(),
            }
        )

    @app.post("/api/analyze")
    def analyze_resume():
        prune_expired_state()
        uploaded = request.files.get("image")
        manual_resume_text = (request.form.get("resume_text") or "").strip()
        job_desc = (request.form.get("job_desc") or "").strip()
        if uploaded is None and not manual_resume_text:
            return error_response("missing image file or resume_text", 400)
        if not job_desc:
            return error_response("missing job_desc", 400)

        try:
            resume_text = manual_resume_text or extract_resume_text(uploaded)
            data = build_resume_analysis(resume_text, job_desc)
            analysis_id = uuid.uuid4().hex
            ANALYSES[analysis_id] = {
                "resume_text": resume_text,
                "job_desc": job_desc,
                "created_at": time.time(),
                "last_accessed": time.time(),
            }
            data["analysis_id"] = analysis_id
            LOGGER.info(
                "Created resume analysis analysis_id=%s source=%s resume_chars=%s job_desc_chars=%s",
                analysis_id,
                "manual" if manual_resume_text else "image",
                len(resume_text),
                len(job_desc),
            )
            return ok_response(data=data)
        except ValueError as exc:
            return error_response(str(exc), 422)
        except Exception as exc:
            return error_response(str(exc), 500)

    @app.post("/api/interview/start")
    def interview_start():
        prune_expired_state()
        payload = request.get_json(silent=True) or {}
        analysis_id = (payload.get("analysis_id") or "").strip()
        resume_text = (payload.get("resume_text") or "").strip()
        job_desc = (payload.get("job_desc") or "").strip()
        question_count = clamp_int(payload.get("question_count"), 1, 8, default=3)
        if analysis_id:
            analysis = ANALYSES.get(analysis_id)
            if analysis is None:
                return error_response("invalid analysis_id", 404)
            touch_state_entry(analysis)
            resume_text = analysis["resume_text"]
            job_desc = job_desc or analysis["job_desc"]
        if not resume_text:
            return error_response("missing resume_text", 400)

        session_id = uuid.uuid4().hex
        interview_plan = generate_interview_plan(resume_text, job_desc, question_count)
        questions = interview_plan_to_frontend_questions(interview_plan)
        SESSIONS[session_id] = {
            "resume_text": resume_text,
            "job_desc": job_desc,
            "questions": questions,
            "interview_plan": interview_plan,
            "answers": {},
            "conversation_memory": build_initial_interview_memory(resume_text, job_desc, interview_plan),
            "created_at": time.time(),
            "last_accessed": time.time(),
        }
        LOGGER.info(
            "Created interview session session_id=%s question_count=%s question_source=%s resume_source=%s",
            session_id,
            len(questions),
            interview_plan.get("question_source", "fallback"),
            "analysis" if analysis_id else "direct",
        )
        return ok_response(
            data={
                "session_id": session_id,
                "questions": questions,
                "question_source": interview_plan.get("question_source", "fallback"),
                "generation_error": interview_plan.get("generation_error", ""),
            }
        )

    @app.post("/api/interview/answer")
    def interview_answer():
        prune_expired_state()
        payload = request.get_json(silent=True) or {}
        session_id = payload.get("session_id") or ""
        question_id = payload.get("question_id") or ""
        answer = payload.get("answer") or ""
        session = SESSIONS.get(session_id)
        if session is None:
            return error_response("invalid session_id", 404)
        touch_state_entry(session)
        if not question_id:
            return error_response("missing question_id", 400)

        session["answers"][question_id] = answer
        update_interview_memory(session, question_id, answer)
        next_question = build_adaptive_next_question(session, question_id, answer)
        LOGGER.info(
            "Saved interview answer session_id=%s question_id=%s answer_chars=%s has_next_question=%s",
            session_id,
            question_id,
            len(answer.strip()),
            bool(next_question),
        )
        return ok_response(data={"saved": True, "followup": None, "next_question": next_question})

    @app.post("/api/interview/feedback")
    def interview_feedback():
        prune_expired_state()
        payload = request.get_json(silent=True) or {}
        session_id = payload.get("session_id") or ""
        session = SESSIONS.get(session_id)
        if session is None:
            return error_response("invalid session_id", 404)
        touch_state_entry(session)
        LOGGER.info(
            "Building interview feedback session_id=%s answered_questions=%s",
            session_id,
            len(session.get("answers", {})),
        )

        return ok_response(data=build_interview_feedback(session))

    @app.post("/api/interview/speak")
    def interview_speak():
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        if not text:
            return error_response("missing text", 400)

        if not has_voice_credentials():
            return error_response("语音合成服务未配置，前端将使用浏览器朗读。", 503)

        try:
            LOGGER.info("Interview TTS request text_chars=%s", len(text))
            audio = synthesize_interviewer_audio(text)
            if isinstance(audio, (bytes, bytearray)):
                audio_bytes = bytes(audio)
            else:
                audio_path = Path(audio)
                audio_bytes = audio_path.read_bytes()
                audio_path.unlink(missing_ok=True)
            LOGGER.info("Interview TTS completed bytes=%s", len(audio_bytes))
            return send_file(
                BytesIO(audio_bytes),
                mimetype="audio/mpeg",
                as_attachment=False,
                download_name="interviewer.mp3",
            )
        except Exception as exc:
            LOGGER.exception("Interview TTS failed")
            return error_response(str(exc), 500)

    @app.post("/api/chat")
    def chat():
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        if not text:
            return error_response("missing text", 400)
        LOGGER.info("Chat request text_chars=%s", len(text))
        return ok_response(answer=build_chat_answer(text))

    @app.post("/api/voice-chat")
    def voice_chat():
        uploaded = request.files.get("audio")
        if uploaded is None:
            return error_response("missing audio file", 400)
        mode = (request.form.get("mode") or "chat").strip().lower()
        LOGGER.info(
            "Voice chat request mode=%s filename=%s",
            mode,
            uploaded.filename or "<unknown>",
        )

        try:
            question = transcribe_audio(uploaded)
            if mode == "transcribe":
                LOGGER.info(
                    "Voice chat transcribe completed mode=%s transcript_chars=%s answer_chars=0",
                    mode,
                    len(question),
                )
                return ok_response(question=question, answer="")
            answer = build_chat_answer(question)
            LOGGER.info(
                "Voice chat completed mode=%s transcript_chars=%s answer_chars=%s",
                mode,
                len(question),
                len(answer),
            )
            return ok_response(question=question, answer=answer)
        except ValueError as exc:
            return error_response(str(exc), 422)
        except Exception as exc:
            LOGGER.exception("Voice chat failed mode=%s", mode)
            return error_response(str(exc), 500)

    return app


def ok_response(**payload):
    return jsonify({"code": 0, **payload})


def error_response(message, status=400):
    if status >= 500:
        LOGGER.error("API error response %s: %s", status, message)
    elif status >= 400:
        LOGGER.warning("API error response %s: %s", status, message)
    return jsonify({"code": 1, "message": message}), status


def clamp_int(value, minimum, maximum, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def touch_state_entry(entry):
    entry["last_accessed"] = time.time()


def _is_entry_expired(entry, ttl_seconds, now):
    last_accessed = entry.get("last_accessed") or entry.get("created_at") or now
    return (now - float(last_accessed)) > ttl_seconds


def prune_expired_state(now=None):
    now = time.time() if now is None else now
    expired_sessions = [
        session_id for session_id, session in SESSIONS.items()
        if _is_entry_expired(session, SESSION_TTL_SECONDS, now)
    ]
    for session_id in expired_sessions:
        SESSIONS.pop(session_id, None)

    expired_analyses = [
        analysis_id for analysis_id, analysis in ANALYSES.items()
        if _is_entry_expired(analysis, ANALYSIS_TTL_SECONDS, now)
    ]
    for analysis_id in expired_analyses:
        ANALYSES.pop(analysis_id, None)


def extract_resume_text(uploaded_file):
    suffix = Path(uploaded_file.filename or "resume.png").suffix or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        uploaded_file.save(tmp.name)
        tmp_path = Path(tmp.name)

    try:
        if config.IFLYTEK_APP_ID and config.IFLYTEK_API_KEY:
            try:
                ocr_client_class = globals().get("IFlyTekOCRClient")
                if ocr_client_class is None:
                    from ocr_client import IFlyTekOCRClient as ocr_client_class

                text = ocr_client_class().extract_text(tmp_path)
                if text.strip():
                    return text.strip()
            except Exception as exc:
                raise ValueError(
                    "OCR 服务暂时不可用，请检查讯飞 OCR 配置、图片清晰度或稍后重试。"
                    f"（错误：{exc}）"
                ) from exc

        raise ValueError("未能从图片中识别到简历内容，请检查讯飞 OCR 配置、图片清晰度或稍后重试。")
    finally:
        tmp_path.unlink(missing_ok=True)


def build_resume_analysis(resume_text, job_desc):
    global ANALYSIS_VARIANT_COUNTER
    ANALYSIS_VARIANT_COUNTER += 1
    variant = ANALYSIS_VARIANT_COUNTER
    llm_struct = {}
    if config.IFLYTEK_SPARK_API_PASSWORD:
        try:
            from llm_client import SparkLLMClient

            raw_llm_text = SparkLLMClient(timeout=config.WEB_AI_TIMEOUT).analyze_resume(resume_text, job_desc)
            llm_struct = parse_llm_json(raw_llm_text)
        except Exception as exc:
            llm_struct = {"_error": str(exc)}

    score = llm_struct.get("match_score") or score_resume_match(resume_text, job_desc)
    local_profile = extract_resume_profile(resume_text, job_desc)
    skills = ensure_string_list(llm_struct.get("core_info", {}).get("skills")) or local_profile["skills"]

    suggestions = normalize_resume_suggestions(
        llm_struct.get("improvement_suggestions"),
        resume_text,
        job_desc,
        local_profile,
        variant,
    )

    core_info = llm_struct.get("core_info") or {
        "name": local_profile["name"],
        "education": local_profile["education"],
        "years": local_profile["years"],
        "position": local_profile["position"],
        "skills": skills,
    }

    advantages = normalize_chinese_list(llm_struct.get("advantages")) or build_advantages(skills)
    disadvantages = normalize_chinese_list(llm_struct.get("gaps")) or build_resume_gaps(local_profile, job_desc)

    return {
        "match_score": score,
        "match_score_reason": llm_struct.get("match_score_reason", ""),
        "core_info": core_info,
        "advantages": advantages,
        "disadvantages": disadvantages,
        "suggestions": suggestions,
        "hard_requirements_check": llm_struct.get("hard_requirements_check", []),
        "experience_credibility": llm_struct.get("experience_credibility", {}),
        "risk_flags": llm_struct.get("risk_flags", []),
        "deep_dive_topics": llm_struct.get("deep_dive_topics", []),
        "interview_prep_advice": llm_struct.get("interview_prep_advice", []),
        "resume_text": resume_text,
    }


def parse_llm_json(raw):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {}
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        return {}
    return data


def score_resume_match(resume_text, job_desc):
    resume_words = keyword_set(resume_text)
    job_words = keyword_set(job_desc)
    if not job_words:
        return 60
    overlap = len(resume_words & job_words)
    ratio = overlap / max(1, len(job_words))
    return max(35, min(92, int(45 + ratio * 55)))


def keyword_set(text):
    words = re.findall(r"[A-Za-z0-9+#.]+|[\u4e00-\u9fff]{2,}", text.lower())
    stop = {"and", "with", "the", "for", "of", "in", "to", "a", "or"}
    return {word for word in words if len(word) > 1 and word not in stop}


def extract_skills(text):
    common = [
        "Python",
        "Flask",
        "JavaScript",
        "Vue",
        "React",
        "SQL",
        "OCR",
        "LLM",
        "REST API",
        "Java",
        "Spring",
        "Docker",
        "用户增长",
        "活动策划",
        "数据复盘",
        "社群运营",
        "跨部门沟通",
        "问卷调研",
        "用户分层",
        "内容运营",
        "转化率",
    ]
    found = [skill for skill in common if skill.lower() in text.lower()]
    return found[:8] or ["沟通协作", "学习能力", "项目经历"]


def extract_name(text):
    match = re.search(r"(?:Candidate|Name|姓名)[:：]\s*([^\n]+)", text, re.IGNORECASE)
    return match.group(1).strip()[:30] if match else "待识别"


def extract_education(text):
    for label in ["硕士", "本科", "博士", "Bachelor", "Master", "PhD"]:
        if label.lower() in text.lower():
            return label
    return "待识别"


def extract_years(text):
    match = re.search(r"(\d+)\s*(?:年|years?)", text, re.IGNORECASE)
    return f"{match.group(1)} 年" if match else "待识别"


def extract_position(job_desc):
    text = compact_text(job_desc, 120)
    match = re.search(r"(?:目标岗位|岗位|职位)[:：]\s*([^。\n；;，,]+)", text)
    if match:
        return match.group(1).strip()[:40]
    first_line = (job_desc.splitlines() or ["目标岗位"])[0].strip()
    return re.split(r"[。；;，,]", first_line)[0].strip()[:40] or "目标岗位"


def build_advantages(skills):
    return [
        f"已体现与岗位相关的能力：{skill}。" for skill in skills[:3]
    ] or ["简历中已有可与目标岗位关联的项目经历。"]


def normalize_chinese_list(value):
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        text = str(item).strip()
        if text and is_chinese_specific(text):
            items.append(text)
    return items


def build_resume_gaps(profile, job_desc):
    jd_focus = "、".join(profile["jd_keywords"][:4]) or extract_jd_evidence(job_desc)
    gaps = [
        f"“{profile['project']}”虽然能对应{jd_focus}，但还需要写清楚你个人负责的边界，避免看起来像团队整体成果。",
        f"“{profile['achievement']}”已经有数据基础，但建议补充统计周期、样本范围和复盘后的动作，让结果更可信。",
    ]
    if "跨部门沟通" in jd_focus and "跨部门" not in profile["responsibility"]:
        gaps.append("目标岗位强调跨部门沟通，但简历中还缺少和产品、设计、技术或业务方协作推进的具体例子。")
    return gaps


def extract_resume_profile(resume_text, job_desc):
    project = extract_labeled_value(resume_text, ["项目", "项目经历", "Projects"])
    responsibility = extract_labeled_value(resume_text, ["负责", "职责", "工作内容", "Experience"])
    achievement = extract_labeled_value(resume_text, ["成果", "结果", "业绩", "产出"])
    skills = extract_skills(resume_text + "\n" + job_desc)
    return {
        "name": extract_name(resume_text),
        "education": extract_education(resume_text),
        "years": extract_years(resume_text),
        "position": extract_position(job_desc),
        "skills": skills,
        "project": project or "核心项目",
        "responsibility": responsibility or "项目职责",
        "achievement": achievement or extract_metric_phrase(resume_text) or "成果数据未突出",
        "jd_keywords": extract_jd_focus_points(job_desc),
    }


def extract_labeled_value(text, labels):
    for label in labels:
        pattern = rf"(?:^|\n)\s*{re.escape(label)}[:：]\s*([^\n]+)"
        match = re.search(pattern, text or "", re.IGNORECASE)
        if match:
            return match.group(1).strip()[:160]
    return ""


def extract_metric_phrase(text):
    matches = re.findall(r"[^。\n；;]*(?:\d+(?:\.\d+)?%?)[^。\n；;]*", text or "")
    return "；".join(item.strip() for item in matches[:2] if item.strip())[:160]


def normalize_resume_suggestions(value, resume_text, job_desc, profile, variant):
    required_keys = ["structure", "content", "keywords", "quantification"]
    if isinstance(value, dict) and all(key in value and is_chinese_specific(value[key]) for key in required_keys):
        return {key: str(value[key]).strip() for key in required_keys}
    return build_local_resume_suggestions(resume_text, job_desc, profile, variant)


def is_chinese_specific(text):
    text = str(text or "")
    if not text.strip():
        return False
    if re.search(r"[A-Za-z]{4,}", text):
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def build_local_resume_suggestions(resume_text, job_desc, profile, variant):
    project = profile["project"]
    responsibility = profile["responsibility"]
    achievement = profile["achievement"]
    jd_keywords = [item for item in profile["jd_keywords"] if item]
    jd_focus = "、".join(jd_keywords[:4]) or extract_jd_evidence(job_desc)
    skill_focus = "、".join(profile["skills"][:4])
    metric = extract_metric_phrase(resume_text) or achievement
    mode = variant % 3

    if mode == 1:
        return {
            "structure": f"建议把简历改成“目标岗位匹配摘要-核心技能-项目经历-量化成果”顺序。开头先写你面向{profile['position']}的匹配点，例如围绕“{jd_focus}”，再把“{project}”放到第一段项目经历中，避免招聘者先看到不相关信息。",
            "content": f"“{project}”不要只写做过什么，要补成真实业务故事：背景是什么、你负责“{responsibility}”中的哪一块、用了什么方法解决用户或运营问题、结果如何影响{jd_focus}。",
            "keywords": f"建议把岗位关键词自然放进项目条目：{jd_focus}。比如在“{project}”下写清楚{skill_focus or jd_focus}，让系统筛选和招聘者快速看到岗位匹配。",
            "quantification": f"你已经有“{metric}”这类结果，建议继续补充口径：活动周期、覆盖人数、转化率计算方式、复盘后下一轮提升点。这样比只写“效果较好”更可信。",
        }
    if mode == 2:
        return {
            "structure": f"建议单独增加“岗位匹配亮点”小节，用 2-3 行概括：你做过“{project}”，承担“{responsibility}”，并能对应 JD 的“{jd_focus}”。随后项目经历再展开细节。",
            "content": f"内容层面要把“我参与”改成“我负责”。围绕“{responsibility}”写清楚你独立完成的动作，例如调研、策划、执行、复盘中的具体判断，不要让 HR 觉得贡献边界模糊。",
            "keywords": f"关键词不要堆在技能栏里，建议嵌入经历句子：围绕{jd_focus}，说明你在“{project}”中如何使用{skill_focus or '相关方法'}完成目标。",
            "quantification": f"对“{achievement}”继续拆数字：起点、终点、样本量、时间范围、你个人动作和指标变化之间的关系。数字越有口径，可信度越高。",
        }
    return {
            "structure": f"建议把“{project}”拆成 3-4 条经历要点：目标、动作、协作、结果。每条都尽量和{profile['position']}的“{jd_focus}”对应，减少泛泛的经历罗列。",
        "content": f"目前最值得强化的是“{responsibility}”背后的决策过程：为什么这么策划、为什么选这个社群/用户群、复盘后改了什么。真实面试里这些会比标题更有说服力。",
        "keywords": f"保留与岗位高度相关的词：{jd_focus}；弱化与岗位无关的工具堆叠。建议在项目标题或第一条经历要点中直接出现“{project}+{jd_keywords[0] if jd_keywords else profile['position']}”。",
        "quantification": f"量化成果建议写成“动作-指标-变化”格式，例如基于“{metric}”补出：你做了哪些动作、指标从多少到多少、这个结果对用户增长或运营目标意味着什么。",
    }


def generate_interview_plan(resume_text, job_desc, count):
    job_direction = infer_job_direction(resume_text, job_desc)
    if config.IFLYTEK_SPARK_API_PASSWORD:
        try:
            client_class = globals().get("SparkLLMClient")
            if client_class is None:
                from llm_client import SparkLLMClient as client_class

            client = create_spark_client(client_class)
            plan = client.generate_interview_questions(
                resume_text=resume_text,
                job_desc=job_desc,
                count=count,
                job_direction=job_direction,
            )
            return normalize_interview_plan(
                plan,
                count,
                job_direction,
                resume_text=resume_text,
                job_desc=job_desc,
                question_source="spark",
            )
        except Exception as exc:
            fallback = build_fallback_interview_plan(resume_text, job_desc, count, job_direction)
            fallback["generation_error"] = str(exc)
            return fallback

    return build_fallback_interview_plan(resume_text, job_desc, count, job_direction)


def create_spark_client(client_class):
    try:
        return client_class(timeout=config.WEB_AI_TIMEOUT)
    except TypeError:
        return client_class()


def generate_interview_questions(resume_text, job_desc, count):
    return interview_plan_to_frontend_questions(
        generate_interview_plan(resume_text, job_desc, count)
    )


def interview_plan_to_frontend_questions(plan):
    questions = []
    for index, question in enumerate(plan.get("questions", []), 1):
        questions.append(question_to_frontend(question, index))
    return questions


def question_to_frontend(question, index=1):
    return {
        "id": str(question.get("id") or f"q{index}"),
        "type": str(question.get("type") or "综合面试"),
        "content": str(question.get("question") or question.get("content") or ""),
    }


def normalize_interview_plan(plan, count, job_direction, resume_text="", job_desc="", question_source="spark"):
    if isinstance(plan, str):
        plan = parse_json_object(plan)
    if not isinstance(plan, dict):
        raise ValueError("interview plan must be a JSON object")

    raw_questions = plan.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ValueError("interview plan missing questions")

    normalized_questions = []
    for index, raw in enumerate(raw_questions[:count], 1):
        if not isinstance(raw, dict):
            continue
        question_text = str(raw.get("question") or raw.get("content") or "").strip()
        if not question_text:
            continue
        normalized = {
            "id": str(raw.get("id") or f"q{index}"),
            "stage": str(raw.get("stage") or "general"),
            "type": str(raw.get("type") or "综合面试"),
            "difficulty": str(raw.get("difficulty") or "medium"),
            "question": question_text,
            "intent": str(raw.get("intent") or "考察候选人与岗位的匹配度。"),
            "evidence_from_resume": str(raw.get("evidence_from_resume") or ""),
            "evidence_from_jd": str(raw.get("evidence_from_jd") or ""),
            "expected_points": ensure_string_list(raw.get("expected_points")),
            "bad_answer_signals": ensure_string_list(raw.get("bad_answer_signals")),
            "followup_rules": [],
            "scoring_rubric": ensure_scoring_rubric(raw.get("scoring_rubric")),
        }
        normalized_questions.append(ground_question(normalized, resume_text, job_desc, job_direction))

    if not normalized_questions:
        raise ValueError("interview plan has no valid questions")

    while len(normalized_questions) < count:
        fallback = {
            "id": f"q{len(normalized_questions) + 1}",
            "stage": "fallback",
            "type": "综合面试",
            "difficulty": "medium",
            "question": f"请用一两分钟介绍一下你自己，重点说说和你投递的{job_direction}最相关的一段经历。",
            "intent": "破冰+了解候选人",
            "evidence_from_resume": "",
            "evidence_from_jd": "",
            "expected_points": ["具体经历", "个人角色", "与岗位的关联"],
            "bad_answer_signals": ["泛泛而谈", "没有具体项目"],
            "followup_rules": [],
            "scoring_rubric": ensure_scoring_rubric(None),
        }
        normalized_questions.append(fallback)

    return {
        "job_direction": str(plan.get("job_direction") or job_direction),
        "interview_style": str(plan.get("interview_style") or "真实电话面试"),
        "question_source": question_source,
        "questions": normalized_questions[:count],
    }


def parse_json_object(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def ensure_string_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def ensure_scoring_rubric(value):
    default = {
        "relevance": 20,
        "structure": 20,
        "depth": 20,
        "job_fit": 20,
        "expression": 20,
    }
    if not isinstance(value, dict):
        return default
    rubric = {}
    for key, score in value.items():
        try:
            rubric[str(key)] = int(score)
        except (TypeError, ValueError):
            continue
    return rubric or default


def ground_question(question, resume_text, job_desc, job_direction):
    resume_evidence = question.get("evidence_from_resume") or extract_resume_evidence(resume_text)
    jd_evidence = question.get("evidence_from_jd") or extract_jd_evidence(job_desc)
    question_text = question.get("question", "")

    if is_generic_question(question_text, resume_evidence, jd_evidence):
        question_text = build_grounded_question(
            question,
            resume_evidence,
            jd_evidence,
            job_direction,
        )

    question["question"] = question_text
    question["evidence_from_resume"] = resume_evidence
    question["evidence_from_jd"] = jd_evidence
    return question


def is_generic_question(question_text, resume_evidence, jd_evidence):
    question_text = question_text or ""
    generic_patterns = [
        "介绍一下自己",
        "简单介绍",
        "项目经历",
        "为什么选择",
        "你的优势",
        "遇到困难",
        "职业规划",
    ]
    has_generic_pattern = any(pattern in question_text for pattern in generic_patterns)
    evidence_tokens = keyword_set(resume_evidence + "\n" + jd_evidence)
    has_evidence_token = any(token in question_text.lower() for token in evidence_tokens if len(token) >= 2)
    return has_generic_pattern or not has_evidence_token


def extract_resume_evidence(resume_text):
    source_text = (resume_text or "").strip()
    field_text = "\n".join(line.strip() for line in source_text.splitlines() if line.strip())
    patterns = [
        r"(?:^|\n)\s*(?:项目|Projects?)[:：]\s*([^\n；;]+)",
        r"(?:^|\n)\s*(?:技术|Skills?)[:：]\s*([^\n；;]+)",
        r"(?:^|\n)\s*(?:负责|职责|Experience)[:：]\s*([^\n；;]+)",
    ]
    hits = []
    for pattern in patterns:
        match = re.search(pattern, field_text, re.IGNORECASE)
        if match:
            hits.append(match.group(1).strip())
    if hits:
        return "；".join(hits[:3])[:140]
    return ""


def build_grounded_question(question, resume_evidence, jd_evidence, job_direction):
    question_type = question.get("type", "岗位匹配")
    experience_hint = f'可以结合“{resume_evidence}”这段经历，' if resume_evidence else ""
    if question_type in {"自我介绍", "综合面试"}:
        return (
            f'目标岗位是{job_direction}，核心要求包括“{jd_evidence}”。'
            f'{experience_hint}你会如何证明自己最匹配这些要求？请按背景、行动、结果来回答。'
        )
    if "技术" in question_type or job_direction in {"后端开发", "前端开发", "算法", "测试开发"}:
        return (
            f'目标岗位要求“{jd_evidence}”。你会如何证明自己的{job_direction}能力？'
            f'{experience_hint}请重点讲技术方案、你的职责和结果。'
        )
    return (
        f'围绕{job_direction}岗位要求“{jd_evidence}”，你最能证明岗位匹配度的一段经历是什么？'
        f'{experience_hint}请直接说明你的动作、判断依据和结果。'
    )


def extract_jd_evidence(job_desc):
    text = compact_text(job_desc, 240)
    patterns = [
        r"(?:要求|任职要求|岗位要求)[:：，,]?\s*([^\n。；;]+)",
        r"(?:负责|岗位职责|职责)[:：，,]?\s*([^\n。；;]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:100]
    return text[:100] or "岗位要求未明确"


def extract_jd_focus_points(job_desc):
    source = job_desc or ""
    text = re.sub(r"[。；;，,、/\n]+", " ", source.strip())
    candidates = []
    for token in text.split():
        token = token.strip("：: .")
        if len(token) >= 2 and token not in {"目标岗位", "岗位要求", "任职要求", "要求", "负责"}:
            candidates.append(token[:24])
    keywords = [
        "产品运营", "用户增长", "活动策划", "数据复盘", "社群运营", "跨部门沟通",
        "Spring Boot", "MySQL", "Redis", "接口设计", "性能优化",
        "需求分析", "原型设计", "用户洞察", "自动化测试", "模型训练",
    ]
    lower_source = source.lower()
    for keyword in keywords:
        if keyword.lower() in lower_source:
            candidates.append(keyword)
    unique = list(dict.fromkeys(candidates))
    return unique[:6] or [extract_jd_evidence(job_desc)]

def infer_job_direction(resume_text, job_desc):
    job_text = (job_desc or "").lower()
    resume_side_text = (resume_text or "").lower()
    rules = [
        ("算法", ["算法", "机器学习", "深度学习", "模型训练", "nlp", "cv", "pytorch", "tensorflow"]),
        ("后端开发", ["后端", "java", "spring", "python", "flask", "django", "go", "接口", "数据库", "sql"]),
        ("前端开发", ["前端", "vue", "react", "javascript", "typescript", "css", "html", "小程序"]),
        ("测试开发", ["测试", "自动化测试", "性能测试", "测试用例", "selenium", "pytest"]),
        ("产品运营", ["产品运营", "运营", "增长", "活动", "内容", "社群", "数据复盘", "转化"]),
        ("产品经理", ["产品经理", "需求", "原型", "用户洞察", "竞品", "prd", "axure", "figma"]),
        ("数据分析", ["数据分析", "bi", "tableau", "powerbi", "指标", "看板", "sql"]),
    ]
    for direction, keywords in rules:
        if any(keyword in job_text for keyword in keywords):
            return direction
    for direction, keywords in rules:
        if any(keyword in resume_side_text for keyword in keywords):
            return direction
    return "通用岗位"


def generate_adaptive_next_question(session, answered_question_id, answer, next_index, job_direction):
    if config.IFLYTEK_SPARK_API_PASSWORD:
        client_class = globals().get("SparkLLMClient")
        if client_class is None:
            from llm_client import SparkLLMClient as client_class

        client = create_spark_client(client_class)
        if hasattr(client, "generate_adaptive_interview_question"):
            raw = client.generate_adaptive_interview_question(
                resume_text=session.get("resume_text", ""),
                job_desc=session.get("job_desc", ""),
                job_direction=job_direction,
                current_question=find_question_content(session, answered_question_id),
                answer=answer,
                asked_questions=session.get("questions", [])[: next_index],
                conversation_memory=ensure_interview_memory(session),
                next_index=next_index + 1,
            )
            parsed = parse_json_object(raw) if isinstance(raw, str) else raw
            return normalize_adaptive_question(
                parsed,
                next_index + 1,
                job_direction,
                session.get("resume_text", ""),
                session.get("job_desc", ""),
                answer,
                ensure_interview_memory(session),
            )

    return build_fallback_adaptive_question(
        index=next_index + 1,
        job_direction=job_direction,
        resume_text=session.get("resume_text", ""),
        job_desc=session.get("job_desc", ""),
        answer=answer,
        memory=ensure_interview_memory(session),
    )


def normalize_adaptive_question(raw, index, job_direction, resume_text, job_desc, answer, memory=None):
    if not isinstance(raw, dict):
        raise ValueError("adaptive question must be a JSON object")
    question_text = str(raw.get("question") or raw.get("content") or "").strip()
    if not question_text:
        raise ValueError("adaptive question missing question")
    normalized = {
        "id": str(raw.get("id") or f"q{index}"),
        "stage": str(raw.get("stage") or "adaptive"),
        "type": str(raw.get("type") or "动态下一题"),
        "difficulty": str(raw.get("difficulty") or "medium"),
        "question": question_text,
        "intent": str(raw.get("intent") or "根据上一轮回答继续考察岗位匹配度。"),
        "evidence_from_resume": str(raw.get("evidence_from_resume") or extract_resume_evidence(resume_text)),
        "evidence_from_jd": str(raw.get("evidence_from_jd") or extract_jd_evidence(job_desc)),
        "expected_points": ensure_string_list(raw.get("expected_points")),
        "bad_answer_signals": ensure_string_list(raw.get("bad_answer_signals")),
        "followup_rules": [],
        "scoring_rubric": ensure_scoring_rubric(raw.get("scoring_rubric")),
    }
    normalized["question"] = rewrite_adaptive_question_text(normalized["question"], job_direction, job_desc, answer, memory)
    return normalized


def build_adaptive_next_question(session, answered_question_id, answer):
    questions = session.get("questions", [])
    current_index = next(
        (index for index, question in enumerate(questions) if str(question.get("id")) == str(answered_question_id)),
        -1,
    )
    next_index = current_index + 1
    if next_index <= 0 or next_index >= len(questions):
        return None

    interview_plan = session.get("interview_plan", {})
    job_direction = str(interview_plan.get("job_direction") or infer_job_direction(session.get("resume_text", ""), session.get("job_desc", "")))
    memory = ensure_interview_memory(session)
    try:
        adaptive_question = generate_adaptive_next_question(
            session=session,
            answered_question_id=answered_question_id,
            answer=answer,
            next_index=next_index,
            job_direction=job_direction,
        )
    except Exception:
        adaptive_question = build_fallback_adaptive_question(
            index=next_index + 1,
            job_direction=job_direction,
            resume_text=session.get("resume_text", ""),
            job_desc=session.get("job_desc", ""),
            answer=answer,
            memory=memory,
        )

    if next_index >= 2:
        uncovered = [point for point in memory.get("uncovered_points", []) if point]
        preferred = next((point for point in ["数据复盘", "跨部门沟通"] if point in uncovered), "")
        if preferred and preferred not in adaptive_question.get("question", ""):
            anchor = choose_memory_anchor(memory, answer) or "前面这段经历"
            adaptive_question = {
                "id": f"q{next_index + 1}",
                "stage": "adaptive",
                "type": "动态下一题",
                "difficulty": "medium",
                "question": f"你刚才提到{anchor}。如果继续往下追问，里面和{preferred}最相关的一次判断、协作或者复盘是什么？",
                "intent": f"继续核验{preferred}以及经历真实性。",
                "evidence_from_resume": extract_resume_evidence(session.get("resume_text", "")),
                "evidence_from_jd": extract_jd_evidence(session.get("job_desc", "")),
                "expected_points": ["承接前文事实", preferred, "个人动作", "结果或复盘"],
                "bad_answer_signals": ["没有回应上一轮内容", "泛泛而谈", f"没有说明{preferred}"],
                "followup_rules": [],
                "scoring_rubric": ensure_scoring_rubric(None),
            }

    questions[next_index] = question_to_frontend(adaptive_question, next_index + 1)
    plan_questions = interview_plan.setdefault("questions", [])
    while len(plan_questions) <= next_index:
        plan_questions.append({
            "id": f"q{len(plan_questions) + 1}",
            "stage": "fallback",
            "type": "综合面试",
            "difficulty": "medium",
            "question": f"结合{job_direction}岗位要求，请谈谈你最匹配的一段经历。",
            "intent": "兜底题目",
            "evidence_from_resume": session.get("resume_text", "")[:100],
            "evidence_from_jd": session.get("job_desc", "")[:100],
            "expected_points": ["具体经历", "个人角色"],
            "bad_answer_signals": ["泛泛而谈"],
            "followup_rules": [],
            "scoring_rubric": ensure_scoring_rubric(None),
        })
    plan_questions[next_index] = adaptive_question
    return questions[next_index]


def rewrite_adaptive_question_text(question_text, job_direction, job_desc, answer, memory=None):
    if "你" in question_text and not any(bad in question_text for bad in ["追问", "简历里提到", "姓名"]):
        return question_text
    memory = memory or {}
    focus = choose_memory_anchor(memory, answer)
    jd_evidence = extract_jd_evidence(job_desc)
    missing_focus = choose_next_gap(memory, job_desc, 1)
    return (
        f"刚才你提到“{focus}”。结合目标岗位{job_direction}对“{jd_evidence}”的要求，"
        f"你能接着讲讲这段经历里和“{missing_focus}”最相关的一次判断或取舍吗？"
    )


def build_initial_interview_memory(resume_text, job_desc, interview_plan):
    jd_points = extract_jd_focus_points(job_desc)
    return {
        "job_direction": str((interview_plan or {}).get("job_direction") or infer_job_direction(resume_text, job_desc)),
        "jd_points": jd_points,
        "covered_points": [],
        "uncovered_points": jd_points[:],
        "answer_facts": [],
        "answer_weaknesses": [],
        "turns": [],
    }


def ensure_interview_memory(session):
    memory = session.get("conversation_memory")
    if not isinstance(memory, dict):
        memory = build_initial_interview_memory(
            session.get("resume_text", ""),
            session.get("job_desc", ""),
            session.get("interview_plan", {}),
        )
        session["conversation_memory"] = memory
    return memory


def update_interview_memory(session, question_id, answer):
    memory = ensure_interview_memory(session)
    answer = (answer or "").strip()
    current_question = find_question_content(session, question_id)
    facts = extract_answer_facts(answer)
    covered = [point for point in memory.get("jd_points", []) if point and point.lower() in answer.lower()]
    weaknesses = detect_answer_weaknesses(answer)

    memory.setdefault("turns", []).append(
        {
            "question_id": question_id,
            "question": current_question,
            "answer": answer,
            "facts": facts,
            "covered_points": covered,
            "weaknesses": weaknesses,
        }
    )
    memory["answer_facts"] = merge_unique(memory.get("answer_facts", []), facts, limit=10)
    memory["covered_points"] = merge_unique(memory.get("covered_points", []), covered, limit=12)
    memory["answer_weaknesses"] = merge_unique(memory.get("answer_weaknesses", []), weaknesses, limit=8)
    memory["uncovered_points"] = [
        point for point in memory.get("jd_points", []) if point not in set(memory.get("covered_points", []))
    ]
    return memory


def extract_answer_facts(answer):
    answer = (answer or "").strip()
    if not answer:
        return []
    facts = []
    known_terms = [
        "问卷调研", "用户调研", "用户洞察", "社群运营", "活动策划", "数据复盘", "跨部门沟通",
        "用户增长", "报名链路", "转化率", "留存", "拉新", "复盘", "接口", "缓存", "数据库",
        "性能优化", "Vue", "React", "Flask", "Spring Boot", "MySQL", "Redis",
    ]
    lower_answer = answer.lower()
    for term in known_terms:
        if term.lower() in lower_answer:
            facts.append(term)
    for metric in re.findall(r"[^，。；;\n]*(?:\d+(?:\.\d+)?%?)[^，。；;\n]*", answer):
        metric = metric.strip()
        if metric:
            facts.append(metric[:40])
    if not facts:
        focus = extract_answer_focus(answer)
        if focus != "刚才的回答":
            facts.append(focus)
    return list(dict.fromkeys(facts))[:5]


def detect_answer_weaknesses(answer):
    answer = (answer or "").strip()
    if not answer:
        return ["未作答"]
    weaknesses = []
    if not re.search(r"\d", answer):
        weaknesses.append("缺少量化结果")
    if not any(word in answer for word in ["我负责", "我主导", "我设计", "我推进", "我把", "我先", "我通过"]):
        weaknesses.append("个人贡献边界不清")
    if not any(word in answer for word in ["复盘", "数据", "指标", "转化", "增长", "结果", "提升", "下降"]):
        weaknesses.append("缺少结果复盘")
    if len(answer) < 35:
        weaknesses.append("回答偏短")
    return weaknesses


def merge_unique(existing, incoming, limit=10):
    merged = []
    for item in list(existing or []) + list(incoming or []):
        text = str(item).strip()
        if text and text not in merged:
            merged.append(text)
    return merged[:limit]


def choose_memory_anchor(memory, answer):
    """选择上一轮回答中的有效锚点。如果全是无效内容，返回空字符串。"""
    facts = memory.get("answer_facts") or []
    if facts:
        # 过滤无效锚点
        bad_facts = {"不知道", "没做过", "不太了解", "不清楚", "未作答", "刚才的回答"}
        valid_facts = [f for f in facts if f not in bad_facts and len(f) >= 2]
        if valid_facts:
            preferred_order = ["问卷调研", "用户洞察", "社群运营", "活动策划", "数据复盘", "跨部门沟通", "用户增长"]
            for term in preferred_order:
                if term in valid_facts:
                    return term
            return valid_facts[0]
    # 从原始回答中提取
    focus = extract_answer_focus(answer)
    bad_focus = {"不知道", "没做过", "不太了解", "不清楚", "刚才的回答", "我不知道"}
    if focus in bad_focus:
        return ""  # 无效回答，返回空
    return focus


def choose_next_gap(memory, job_desc, index):
    uncovered = [point for point in memory.get("uncovered_points", []) if point]
    if uncovered:
        priority = ["数据复盘", "跨部门沟通", "用户洞察", "用户增长", "活动策划", "社群运营"]
        for term in priority:
            if term in uncovered:
                return term
        return uncovered[(index - 1) % len(uncovered)]
    focus_points = extract_jd_focus_points(job_desc)
    return focus_points[(index - 1) % len(focus_points)] if focus_points else extract_jd_evidence(job_desc)


def choose_answer_weakness(memory):
    weaknesses = memory.get("answer_weaknesses") or []
    if "缺少量化结果" in weaknesses:
        return "缺少量化结果"
    if "缺少结果复盘" in weaknesses:
        return "缺少结果复盘"
    if "个人贡献边界不清" in weaknesses:
        return "个人贡献边界不清"
    return weaknesses[0] if weaknesses else ""


def build_contextual_question_text(job_direction, jd_evidence, anchor, missing_focus, weakness):
    """根据候选人的回答生成自然的下一题（本地兜底）。
    
    关键改进：当anchor是无效内容（如"不知道"/"没做过"/"刚才的回答"）时，
    不强行围绕它出题，而是切换到JD中未覆盖的能力点。
    """
    # 无效anchor检测
    bad_anchors = ["不知道", "没做过", "不太了解", "不清楚", "没接触过", "不会",
                   "刚才的回答", "我不知道", "不知道啊", "没有", "没经验"]
    is_bad_anchor = any(bad in anchor for bad in bad_anchors) if anchor else True

    # 如果候选人说的都是无效内容，切换到通用模式
    if is_bad_anchor:
        if missing_focus and missing_focus != "数据复盘":
            return f"没关系，我们聊聊另一个方向。你对{missing_focus}有接触过吗？说说你知道的就行，不用很深入。"
        return f"换个话题——你现在投的是{job_direction}，你觉得这个岗位上最重要的能力是什么？能结合你自己的经历说说吗？"

    # 有效anchor：正常生成追问
    if weakness in {"缺少量化结果", "缺少结果复盘"} or missing_focus == "数据复盘":
        return f"你讲到{anchor}这一点挺有意思的。当时有没有什么具体的数据能衡量这个效果？比如从多少到多少，或者覆盖了多少用户？"
    if missing_focus == "跨部门沟通":
        return f"你做的{anchor}相关的事，如果涉及到和其他部门合作，你当时是怎么对齐各方目标和分工的？"
    if weakness == "个人贡献边界不清":
        return f"关于{anchor}这部分，我想更清楚一点——哪些是你自己独立做的，哪些是和别人配合的？"
    if anchor and missing_focus:
        return f"你做的{anchor}这件事，如果再让你做一遍，你觉得在{missing_focus}这个方面有什么可以改进的地方？"
    return f"你前面提到的经历有点意思，能再展开讲讲{missing_focus or '你觉得最值得说'}的部分吗？"

def extract_answer_focus(answer):
    tokens = keyword_set(answer)
    preferred = [
        "用户增长", "活动策划", "数据复盘", "社群运营", "跨部门沟通",
        "接口", "缓存", "性能", "项目", "数据", "用户", "活动", "复盘",
    ]
    for keyword in preferred:
        if keyword.lower() in (answer or "").lower():
            return keyword
    for token in tokens:
        if len(token) >= 2:
            return token[:24]
    return "刚才的回答"


def find_question_content(session, question_id):
    for question in session.get("questions", []):
        if str(question.get("id")) == str(question_id):
            return question.get("content", "")
    return ""

def compact_text(text, limit):
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text[:limit] or "该岗位的核心要求"


def find_plan_question(interview_plan, question_id):
    for question in interview_plan.get("questions", []):
        if str(question.get("id")) == str(question_id):
            return question
    return None


def build_interview_feedback(session):
    questions = session["questions"]
    interview_plan = session.get("interview_plan", {})
    job_direction = interview_plan.get("job_direction", "通用岗位")
    reviews = []

    has_ai_scorer = bool(config.IFLYTEK_SPARK_API_PASSWORD)

    for question in questions:
        qid = question["id"]
        answer = build_review_answer(session, qid)
        plan_question = find_plan_question(interview_plan, qid)

        if has_ai_scorer and answer:
            ai_review = ai_score_answer(question, answer, job_direction, plan_question)
        else:
            ai_review = fallback_review(question, answer)

        reviews.append(ai_review)

    total_score = int(sum(r.get("total", 0) for r in reviews) / len(reviews)) if reviews else 0
    return {
        "total_score": total_score,
        "summary": build_feedback_summary(reviews),
        "dimension_scores": aggregate_dimension_scores(reviews),
        "reviews": reviews,
    }


def ai_score_answer(question, answer, job_direction, plan_question):
    try:
        from llm_client import SparkLLMClient

        raw = SparkLLMClient(timeout=config.WEB_AI_TIMEOUT).score_answer_dimensions(
            question=question.get("content", question.get("question", "")),
            answer=answer,
            job_direction=job_direction,
            question_intent=plan_question.get("intent", "") if plan_question else "",
        )
        result = parse_llm_json(raw)
        return {
            "question": question.get("content", question.get("question", "")),
            "answer": answer,
            "scores": result.get("scores", {}),
            "total": result.get("total", 50),
            "comment": result.get("comment", ""),
            "risk_flags": result.get("risk_flags", []),
            "better_example": result.get("better_example", ""),
            "highlights": result.get("highlights", []),
            "improvements": result.get("improvements", []),
        }
    except Exception:
        return fallback_review(question, answer)


def fallback_review(question, answer):
    score = 55 if not answer else min(90, 60 + len(answer) // 12)
    return {
        "question": question.get("content", question.get("question", "")),
        "answer": answer,
        "scores": {
            "relevance": min(20, score // 5),
            "structure": min(20, score // 5),
            "concreteness": min(20, score // 5 + 2),
            "job_fit": min(20, score // 5),
            "expression": min(20, score // 5 - 1),
        },
        "total": score,
        "comment": build_answer_comment(answer),
        "risk_flags": [],
        "better_example": "",
        "highlights": build_answer_highlights(answer),
        "improvements": build_answer_improvements(answer),
    }


def build_feedback_summary(reviews):
    totals = [r.get("total", 0) for r in reviews]
    avg = int(sum(totals) / len(totals)) if totals else 0
    unanswered = sum(1 for r in reviews if not r.get("answer"))
    risk_count = sum(1 for r in reviews if r.get("risk_flags"))
    if avg >= 80:
        level = "优秀"
    elif avg >= 60:
        level = "良好"
    elif avg >= 40:
        level = "一般"
    else:
        level = "需要提升"
    parts = [
        f"整体面试评分为 {avg} 分，表现{level}。",
    ]
    if unanswered:
        parts.append(f"共有 {unanswered} 题未作答。")
    if risk_count:
        parts.append(f"检测到 {risk_count} 题存在值得关注的回答信号。")
    parts.append("建议继续强化 STAR 结构、量化成果和岗位关键词。")
    return "".join(parts)


def aggregate_dimension_scores(reviews):
    dims = ["relevance", "structure", "concreteness", "job_fit", "expression"]
    result = {}
    for dim in dims:
        values = [r.get("scores", {}).get(dim, 0) for r in reviews]
        result[dim] = int(sum(values) / len(values)) if values else 0
    return result


def build_review_answer(session, question_id):
    return (session.get("answers", {}).get(question_id) or "").strip()

def build_answer_comment(answer):
    if not answer:
        return "本题未作答，建议补充具体经历和结果。"
    return "回答具备基本信息，可以进一步补充背景、行动、结果和量化指标。"


def build_answer_highlights(answer):
    if not answer:
        return []
    return ["能够围绕问题给出个人经历。"]


def build_answer_improvements(answer):
    items = ["补充可量化结果。", "用 STAR 结构组织表达。"]
    if len(answer) < 80:
        items.append("回答略短，可展开技术细节和个人贡献。")
    return items


def build_chat_answer(text):
    if config.IFLYTEK_SPARK_API_PASSWORD:
        try:
            from llm_client import SparkLLMClient

            return SparkLLMClient(timeout=config.WEB_AI_TIMEOUT).chat(
                [{"role": "user", "content": text}],
                model=os.getenv("IFLYTEK_SPARK_MODEL", "lite"),
                temperature=0.5,
                max_tokens=1024,
            )
        except Exception as exc:
            return f"AI 服务调用失败，先给你一个本地建议：{fallback_chat_answer(text)}（错误：{exc}）"
    return fallback_chat_answer(text)


def fallback_chat_answer(text):
    return (
        "建议先明确岗位要求，再准备 2-3 个最匹配的项目故事。"
        "每个故事按背景、任务、行动、结果来讲，并尽量加入数据。"
    )


def transcribe_audio(uploaded_file):
    suffix = Path(uploaded_file.filename or "recording.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        uploaded_file.save(tmp.name)
        audio_path = Path(tmp.name)
    LOGGER.info(
        "Transcribing audio filename=%s suffix=%s temp_path=%s",
        uploaded_file.filename or "<unknown>",
        suffix,
        audio_path.name,
    )

    try:
        if config.XFYUN_APPID and config.XFYUN_API_KEY and config.XFYUN_API_SECRET:
            text = recognize_audio_with_xfyun(audio_path).strip()
            if not text:
                raise ValueError("未识别到有效语音，请确认麦克风权限已开启，并靠近麦克风说完整一句话。")
            return text
        return "请根据我的简历帮我模拟一个面试问题"
    finally:
        audio_path.unlink(missing_ok=True)


def recognize_audio_with_xfyun(audio_path):
    from voice_chat_flow import recognize_pcm

    if audio_path.suffix.lower() == ".pcm":
        return recognize_pcm(audio_path)

    pcm_path = audio_path.with_suffix(".pcm")
    convert_audio_to_pcm(audio_path, pcm_path)
    try:
        return recognize_pcm(pcm_path)
    finally:
        pcm_path.unlink(missing_ok=True)


def convert_audio_to_pcm(source, target):
    import subprocess

    ffmpeg = os.getenv("FFMPEG_PATH", "ffmpeg")
    command = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(target),
    ]
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg audio conversion failed: {stderr}")


def has_voice_credentials():
    return bool(config.XFYUN_APPID and config.XFYUN_API_KEY and config.XFYUN_API_SECRET)

def synthesize_interviewer_audio(text):
    from voice_chat_flow import synthesize_mp3

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        output_path = Path(tmp.name)

    try:
        synthesize_mp3(text, output_path)
        return output_path
    except Exception:
        output_path.unlink(missing_ok=True)
        raise


def build_fallback_interview_plan(resume_text, job_desc, count, job_direction):
    jd_evidence = extract_jd_evidence(job_desc)
    jd_focus_points = extract_jd_focus_points(job_desc)
    skills = extract_skills(resume_text + "\n" + job_desc)
    resume_evidence = extract_resume_evidence(resume_text)

    questions = []
    for index in range(1, count + 1):
        skill_idx = (index - 1) % len(skills) if skills else 0
        focus_idx = (index - 1) % len(jd_focus_points) if jd_focus_points else 0

        if index == 1:
            stage = "warm_up"
            qtype = "暖场破冰"
            difficulty = "easy"
            if resume_evidence:
                text = f"我看到你有{resume_evidence[:60]}的经历。针对{job_direction}这个方向，你能先简单跟我说说你在里面主要负责什么吗？"
            else:
                text = f"请用一两分钟介绍一下自己，重点说说和你投递的{job_direction}最相关的一段经历。"
            intent = "破冰，了解候选人的角色定位和表达能力"
        elif index % 5 == 2:
            stage = "project_deep_dive"
            qtype = "经历深挖"
            difficulty = "medium"
            skill1 = skills[skill_idx]
            skill2 = skills[(skill_idx + 1) % len(skills)] if len(skills) > 1 else "项目"
            text = f"你提到你在项目里用了{skill1}和{skill2}。当时这个方案是怎么定下来的？是你提的还是别人定的？做技术选型时你主要考虑了哪些因素？"
            intent = "考察候选人是否真正理解自己的技术或业务决策，而不只是执行"
        elif index % 5 == 3:
            stage = "scenario"
            qtype = "情境判断"
            difficulty = "medium"
            focus = jd_focus_points[focus_idx] if jd_focus_points else jd_evidence
            text = f"假设你现在入职了，第一项任务是在两周内解决一个和{focus}相关的紧急需求。站在{job_direction}岗位的角度，你会怎么开始？"
            intent = "考察候选人在信息不完备情况下的拆解能力和推进思路"
        elif index % 5 == 4:
            stage = "behavior"
            qtype = "行为面试"
            difficulty = "medium"
            text = "回顾你过去的经历，不管是学习还是工作，有没有哪次事情没做成或者结果不如预期？当时发生了什么，你从中学到了什么？"
            intent = "考察候选人的复盘能力、诚实度和成长心态"
        else:
            stage = "comprehensive"
            qtype = "综合判断"
            difficulty = "medium"
            text = f"站在{job_direction}这个岗位的角度，如果让你用三个关键词概括你自己的核心优势，你会选哪三个，分别用一段经历来证明？"
            intent = "考察候选人对岗位的理解和对自我的清晰认知"

        questions.append({
            "id": f"q{index}",
            "stage": stage,
            "type": qtype,
            "difficulty": difficulty,
            "question": text,
            "intent": intent,
            "evidence_from_resume": resume_evidence,
            "evidence_from_jd": jd_evidence,
            "expected_points": ["具体经历和动作", "个人决策和判断", "可量化的结果", "对岗位的理解"],
            "bad_answer_signals": ["回答泛泛而谈", "没有具体项目或场景", "缺少数据或结果支撑"],
            "followup_rules": [],
            "scoring_rubric": ensure_scoring_rubric(None),
        })

    return {
        "job_direction": job_direction,
        "interview_style": "本地兜底电话面试",
        "question_source": "fallback",
        "generation_error": "",
        "questions": questions,
    }


def build_fallback_adaptive_question(index, job_direction, resume_text, job_desc, answer, memory=None):
    memory = memory or build_initial_interview_memory(resume_text, job_desc, {"job_direction": job_direction})
    jd_evidence = extract_jd_evidence(job_desc)
    anchor = choose_memory_anchor(memory, answer)
    missing_focus = choose_next_gap(memory, job_desc, index)
    weakness = choose_answer_weakness(memory)
    if index > 1 and missing_focus == "活动策划":
        uncovered = [point for point in memory.get("uncovered_points", []) if point]
        for preferred in ["数据复盘", "跨部门沟通", "用户洞察", "用户增长"]:
            if preferred in uncovered:
                missing_focus = preferred
                break
    question_text = build_contextual_question_text(
        job_direction=job_direction,
        jd_evidence=jd_evidence,
        anchor=anchor,
        missing_focus=missing_focus,
        weakness=weakness,
    )
    return {
        "id": f"q{index}",
        "stage": "adaptive",
        "type": "动态下一题",
        "difficulty": "medium",
        "question": question_text,
        "intent": f"承接前面回答，继续核验{missing_focus}以及经历真实性。",
        "evidence_from_resume": extract_resume_evidence(resume_text),
        "evidence_from_jd": jd_evidence,
        "expected_points": ["承接前文事实", missing_focus, "个人动作", "结果或复盘"],
        "bad_answer_signals": ["没有回应上一轮内容", "泛泛而谈", f"没有说明{missing_focus}"],
        "followup_rules": [],
        "scoring_rubric": ensure_scoring_rubric(None),
    }


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
    app.run(host="127.0.0.1", port=port, debug=debug, use_reloader=debug)
