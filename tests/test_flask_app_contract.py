import importlib
import io
import os
import tempfile
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = next(p for p in ROOT.iterdir() if p.is_dir() and (p / "front.html").exists())
BACKEND_DIR = ROOT / "后端"


class FlaskAppContractTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(BACKEND_DIR))
        sys.modules.pop("app", None)
        app_module = importlib.import_module("app")
        app_module.config.IFLYTEK_APP_ID = ""
        app_module.config.IFLYTEK_API_KEY = ""
        app_module.config.IFLYTEK_API_SECRET = ""
        app_module.config.IFLYTEK_SPARK_API_PASSWORD = ""
        app_module.config.XFYUN_APPID = ""
        app_module.config.XFYUN_API_KEY = ""
        app_module.config.XFYUN_API_SECRET = ""
        self.client = app_module.create_app({"TESTING": True}).test_client()

    def tearDown(self):
        try:
            sys.path.remove(str(BACKEND_DIR))
        except ValueError:
            pass

    def test_index_serves_frontend_html(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        self.assertIn("求职智能助手".encode("utf-8"), response.data)
        response.close()

    def test_unified_route_serves_alias_page(self):
        response = self.client.get("/unified.html")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        self.assertIn("window.location.replace('/front.html')".encode("utf-8"), response.data)
        response.close()

    def test_health_reports_runtime_status_without_secrets(self):
        app_module = sys.modules["app"]
        app_module.config.IFLYTEK_SPARK_API_PASSWORD = "spark-secret"
        app_module.config.XFYUN_APPID = "appid"
        app_module.config.XFYUN_API_KEY = "api-key"
        app_module.config.XFYUN_API_SECRET = "api-secret"

        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["code"], 0)
        data = payload["data"]
        self.assertEqual(data["status"], "ok")
        self.assertNotIn("env_file_present", data)
        self.assertIn("ffmpeg_available", data)
        self.assertTrue(data["spark_configured"])
        self.assertTrue(data["voice_configured"])
        self.assertIn("frontend_dir_exists", data)
        joined = str(payload)
        self.assertNotIn("spark-secret", joined)
        self.assertNotIn("api-secret", joined)

    def test_frontend_dir_can_be_overridden_for_packaged_app(self):
        sys.modules.pop("app", None)
        with tempfile.TemporaryDirectory() as tmpdir:
            frontend_dir = Path(tmpdir) / "frontend"
            frontend_dir.mkdir()
            (frontend_dir / "front.html").write_text("packaged frontend", encoding="utf-8")
            (frontend_dir / "unified.html").write_text("packaged unified", encoding="utf-8")

            old_frontend_dir = os.environ.get("FRONTEND_DIR")
            os.environ["FRONTEND_DIR"] = str(frontend_dir)
            try:
                app_module = importlib.import_module("app")
                client = app_module.create_app({"TESTING": True}).test_client()
                response = client.get("/")
                response_data = response.data
                response.close()
            finally:
                sys.modules.pop("app", None)
                if old_frontend_dir is None:
                    os.environ.pop("FRONTEND_DIR", None)
                else:
                    os.environ["FRONTEND_DIR"] = old_frontend_dir

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data, b"packaged frontend")

    def test_windows_start_script_bootstraps_backend(self):
        script = ROOT / "start_windows.bat"

        self.assertTrue(script.exists())
        content = script.read_text(encoding="utf-8")
        self.assertIn("requirements.txt", content)
        self.assertIn("后端\\app.py", content)
        self.assertIn("http://127.0.0.1:5000/", content)
        self.assertIn("FLASK_DEBUG=0", content)
        self.assertIn('findstr /C:"\\"status\\":\\"ok\\"" >nul', content)

    def test_launcher_script_searches_for_next_available_port(self):
        script = ROOT / "启动求职助手.bat"

        self.assertTrue(script.exists())
        content = script.read_text(encoding="utf-8")
        self.assertIn(":find_free_port", content)
        self.assertIn("PORT_SEARCH_ATTEMPTS", content)
        self.assertIn("set /a PORT+=1", content)
        self.assertIn("goto find_free_port", content)

    def test_analyze_requires_image_and_job_description(self):
        response = self.client.post("/api/analyze", data={})

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["code"], 1)
        self.assertIn("image", payload["message"])

    def test_analyze_returns_frontend_shape(self):
        response = self.client.post(
            "/api/analyze",
            data={
                "job_desc": "Python backend developer with Flask and API experience",
                "resume_text": "Candidate: test\nProjects: Flask API service\nSkills: Python, Flask, SQL",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["code"], 0)
        data = payload["data"]
        self.assertIn("match_score", data)
        self.assertIn("core_info", data)
        self.assertIn("advantages", data)
        self.assertIn("disadvantages", data)
        self.assertIn("suggestions", data)
        self.assertIn("resume_text", data)
        self.assertIn("analysis_id", data)

    def test_resume_analysis_uses_resume_specific_chinese_suggestions(self):
        response = self.client.post(
            "/api/analyze",
            data={
                "job_desc": "产品运营实习，要求用户增长、活动策划、数据复盘、社群运营和跨部门沟通。",
                "resume_text": (
                    "姓名：李明\n"
                    "学校：南方大学\n"
                    "学历：本科\n"
                    "目标岗位：产品运营实习\n"
                    "项目：校园活动增长\n"
                    "负责：社群运营、活动策划、问卷调研、数据复盘\n"
                    "成果：活动参与人数从 120 提升到 260，社群转化率提升 18%"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["core_info"]["name"], "李明")
        self.assertEqual(data["core_info"]["education"], "本科")
        self.assertIn("产品运营", data["core_info"]["position"])
        self.assertTrue(any(skill in data["core_info"]["skills"] for skill in ["社群运营", "活动策划", "数据复盘", "问卷调研"]))
        gaps_text = "\n".join(data["disadvantages"])
        self.assertIn("校园活动增长", gaps_text)
        self.assertNotRegex(gaps_text, r"[A-Za-z]{4,}")

        suggestions = data["suggestions"]
        joined = "\n".join(str(value) for value in suggestions.values())
        for key in ["structure", "content", "keywords", "quantification"]:
            self.assertIn(key, suggestions)
            self.assertTrue(any(term in suggestions[key] for term in ["校园活动增长", "社群运营", "活动策划", "数据复盘", "120", "260", "18%", "用户增长"]))
            self.assertNotRegex(suggestions[key], r"[A-Za-z]{4,}")
        self.assertNotIn("Use clear sections", joined)
        self.assertIn("校园活动增长", joined)
        self.assertIn("用户增长", joined)

    def test_resume_analysis_suggestions_vary_without_becoming_generic(self):
        app_module = sys.modules["app"]
        resume_text = (
            "姓名：李明\n"
            "项目：校园活动增长\n"
            "负责：社群运营、活动策划、数据复盘\n"
            "成果：活动参与人数从 120 提升到 260，社群转化率提升 18%"
        )
        job_desc = "产品运营实习，要求用户增长、活动策划、数据复盘。"

        first = app_module.build_resume_analysis(resume_text, job_desc)["suggestions"]
        second = app_module.build_resume_analysis(resume_text, job_desc)["suggestions"]

        self.assertNotEqual(first, second)
        for suggestions in (first, second):
            joined = "\n".join(suggestions.values())
            self.assertIn("校园活动增长", joined)
            self.assertIn("数据复盘", joined)
            self.assertNotIn("Prioritize experience", joined)

    def test_analyze_image_without_ocr_does_not_use_demo_resume(self):
        response = self.client.post(
            "/api/analyze",
            data={
                "job_desc": "Python backend developer with Flask and API experience",
                "image": (io.BytesIO(b"fake image bytes"), "resume.png"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 422)
        payload = response.get_json()
        self.assertEqual(payload["code"], 1)
        self.assertIn("讯飞 OCR 配置", payload["message"])
        self.assertIn("图片清晰度", payload["message"])

    def test_analyze_image_returns_helpful_error_when_ocr_service_fails(self):
        app_module = sys.modules["app"]

        class FailingOCRClient:
            def extract_text(self, image_path):
                raise RuntimeError("HTTPSConnectionPool: SSL WRONG_SIGNATURE_TYPE")

        with patch.object(app_module.config, "IFLYTEK_APP_ID", "appid"):
            with patch.object(app_module.config, "IFLYTEK_API_KEY", "key"):
                with patch.object(app_module, "IFlyTekOCRClient", FailingOCRClient, create=True):
                    response = self.client.post(
                        "/api/analyze",
                        data={
                            "job_desc": "Python backend developer with Flask and API experience",
                            "image": (io.BytesIO(b"fake image bytes"), "resume.png"),
                        },
                        content_type="multipart/form-data",
                    )

        self.assertEqual(response.status_code, 422)
        payload = response.get_json()
        self.assertEqual(payload["code"], 1)
        self.assertIn("\u004f\u0043\u0052 \u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528", payload["message"])
        self.assertIn("\u8baf\u98de OCR \u914d\u7f6e", payload["message"])
        self.assertNotIn("\u8bf7\u7c98\u8d34\u7b80\u5386\u6587\u672c", payload["message"])

    def test_analyze_prefers_manual_resume_text_over_demo_ocr_fallback(self):
        manual_text = "姓名：张三\n项目：校园二手交易平台\n技术：Vue、Spring Boot、MySQL\n负责：商品发布和订单接口"
        response = self.client.post(
            "/api/analyze",
            data={
                "job_desc": "Java 后端开发实习，要求 Spring Boot、MySQL、接口设计",
                "resume_text": manual_text,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["resume_text"], manual_text)

    def test_analyze_image_can_feed_interview_by_analysis_id(self):
        app_module = sys.modules["app"]
        extracted_text = "Candidate: test\nProjects: Flask API service\nSkills: Python, Flask, SQL"

        class FakeOCRClient:
            def extract_text(self, image_path):
                return extracted_text

        with patch.object(app_module.config, "IFLYTEK_APP_ID", "appid"):
            with patch.object(app_module.config, "IFLYTEK_API_KEY", "key"):
                with patch.object(app_module, "IFlyTekOCRClient", FakeOCRClient, create=True):
                    analyze = self.client.post(
                        "/api/analyze",
                        data={
                            "job_desc": "Python backend developer with Flask and API experience",
                            "image": (io.BytesIO(b"fake image bytes"), "resume.png"),
                        },
                        content_type="multipart/form-data",
                    )

        self.assertEqual(analyze.status_code, 200)
        analyze_payload = analyze.get_json()
        analysis_id = analyze_payload["data"]["analysis_id"]

        start = self.client.post(
            "/api/interview/start",
            json={
                "analysis_id": analysis_id,
                "question_count": 1,
            },
        )

        self.assertEqual(start.status_code, 200)
        start_payload = start.get_json()
        self.assertEqual(start_payload["code"], 0)
        session = app_module.SESSIONS[start_payload["data"]["session_id"]]
        self.assertEqual(session["resume_text"], extracted_text)
        self.assertEqual(session["job_desc"], "Python backend developer with Flask and API experience")

    def test_expired_analysis_is_cleaned_before_interview_start(self):
        app_module = sys.modules["app"]
        analysis_id = "expired-analysis"
        app_module.ANALYSES[analysis_id] = {
            "resume_text": "old resume",
            "job_desc": "old jd",
            "created_at": time.time() - (app_module.ANALYSIS_TTL_SECONDS + 5),
            "last_accessed": time.time() - (app_module.ANALYSIS_TTL_SECONDS + 5),
        }

        response = self.client.post(
            "/api/interview/start",
            json={"analysis_id": analysis_id, "question_count": 1},
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotIn(analysis_id, app_module.ANALYSES)

    def test_interview_flow_returns_questions_and_feedback(self):
        start = self.client.post(
            "/api/interview/start",
            json={
                "resume_text": "Python Flask API project experience",
                "job_desc": "Backend developer",
                "question_count": 2,
            },
        )
        self.assertEqual(start.status_code, 200)
        start_payload = start.get_json()
        self.assertEqual(start_payload["code"], 0)
        session_id = start_payload["data"]["session_id"]
        questions = start_payload["data"]["questions"]
        self.assertEqual(len(questions), 2)

        answer = self.client.post(
            "/api/interview/answer",
            json={
                "session_id": session_id,
                "question_id": questions[0]["id"],
                "answer": "I built Flask APIs and integrated external services.",
            },
        )
        self.assertEqual(answer.status_code, 200)
        self.assertEqual(answer.get_json()["code"], 0)

        feedback = self.client.post("/api/interview/feedback", json={"session_id": session_id})
        self.assertEqual(feedback.status_code, 200)
        feedback_payload = feedback.get_json()
        self.assertEqual(feedback_payload["code"], 0)
        data = feedback_payload["data"]
        self.assertIn("total_score", data)
        self.assertIn("summary", data)
        self.assertIn("reviews", data)

    def test_interview_start_logs_session_creation_metadata(self):
        with self.assertLogs("app", level="INFO") as logs:
            response = self.client.post(
                "/api/interview/start",
                json={
                    "resume_text": "Python Flask API project experience",
                    "job_desc": "Backend developer",
                    "question_count": 1,
                },
            )

        self.assertEqual(response.status_code, 200)
        joined = "\n".join(logs.output)
        self.assertIn("Created interview session", joined)
        self.assertIn("question_count=1", joined)
        self.assertIn("resume_source=direct", joined)

    def test_expired_session_is_cleaned_before_answer_submit(self):
        app_module = sys.modules["app"]
        session_id = "expired-session"
        app_module.SESSIONS[session_id] = {
            "resume_text": "resume",
            "job_desc": "jd",
            "questions": [{"id": "q1", "content": "请介绍一下自己", "type": "暖场破冰"}],
            "interview_plan": {"questions": []},
            "answers": {},
            "conversation_memory": {},
            "created_at": time.time() - (app_module.SESSION_TTL_SECONDS + 5),
            "last_accessed": time.time() - (app_module.SESSION_TTL_SECONDS + 5),
        }

        response = self.client.post(
            "/api/interview/answer",
            json={"session_id": session_id, "question_id": "q1", "answer": "test"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotIn(session_id, app_module.SESSIONS)

    def test_interview_start_uses_structured_llm_questions_when_available(self):
        app_module = sys.modules["app"]
        llm_payload = {
            "job_direction": "后端开发实习",
            "interview_style": "标准电话技术一面",
            "questions": [
                {
                    "id": "backend-project",
                    "stage": "project_deep_dive",
                    "type": "项目深挖",
                    "difficulty": "medium",
                    "question": "你简历里提到 Flask 接口项目，先讲一下这个项目的数据流和你负责的部分。",
                    "intent": "判断项目真实性和个人贡献。",
                    "expected_points": ["项目背景", "数据流", "个人贡献"],
                    "bad_answer_signals": ["只说我们做了", "没有讲清楚个人职责"],
                    "followup_rules": [
                        {
                            "condition": "没有说明个人贡献",
                            "question": "这个项目里你自己独立完成了哪些模块？",
                        }
                    ],
                    "scoring_rubric": {
                        "relevance": 20,
                        "structure": 20,
                        "depth": 25,
                        "personal_contribution": 20,
                        "expression": 15,
                    },
                }
            ],
        }

        test_case = self

        class FakeSparkClient:
            def generate_interview_questions(self, resume_text, job_desc, count, job_direction):
                test_case.assertEqual(count, 1)
                test_case.assertEqual(job_direction, "后端开发")
                return llm_payload

        with patch.object(app_module.config, "IFLYTEK_SPARK_API_PASSWORD", "test-password"):
            with patch.object(app_module, "SparkLLMClient", FakeSparkClient, create=True):
                response = self.client.post(
                    "/api/interview/start",
                    json={
                        "resume_text": "我做过 Python Flask API 和数据库项目。",
                        "job_desc": "后端开发实习，要求 Python、Flask、SQL 和接口设计能力。",
                        "question_count": 1,
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["data"]["question_source"], "spark")
        questions = payload["data"]["questions"]
        self.assertEqual(
            questions,
            [
                {
                    "id": "backend-project",
                    "type": "项目深挖",
                    "content": "你简历里提到 Flask 接口项目，先讲一下这个项目的数据流和你负责的部分。",
                }
            ],
        )
        session = app_module.SESSIONS[payload["data"]["session_id"]]
        self.assertEqual(session["interview_plan"]["job_direction"], "后端开发实习")
        self.assertEqual(session["interview_plan"]["questions"][0]["intent"], "判断项目真实性和个人贡献。")

    def test_interview_start_falls_back_to_role_specific_questions_without_llm(self):
        response = self.client.post(
            "/api/interview/start",
            json={
                "resume_text": "参与过用户访谈、竞品分析和需求文档撰写。",
                "job_desc": "产品经理实习，负责需求分析、原型设计和跨部门沟通。",
                "question_count": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["data"]["question_source"], "fallback")
        questions = payload["data"]["questions"]
        self.assertEqual(len(questions), 3)
        self.assertTrue(any("用户" in question["content"] or "需求" in question["content"] for question in questions))
        self.assertTrue(any("原型" in question["content"] or "跨部门" in question["content"] for question in questions))

    def test_interview_generation_prioritizes_target_job_over_resume_side_skills(self):
        app_module = sys.modules["app"]

        plan = app_module.generate_interview_plan(
            resume_text=(
                "项目：校园二手交易平台\n"
                "技术：Vue、Spring Boot、MySQL、Redis\n"
                "负责：商品发布接口、订单接口、Redis 缓存和异常处理\n"
                "成果：接口平均响应从 800ms 降到 300ms"
            ),
            job_desc="Java 后端开发实习，要求 Spring Boot、MySQL、Redis、REST API 设计，负责业务接口开发和性能优化。",
            count=3,
        )

        self.assertEqual(plan["job_direction"], "后端开发")
        joined = "\n".join(question["question"] for question in plan["questions"])
        self.assertIn("校园二手交易平台", joined)
        self.assertTrue("Spring Boot" in joined or "Redis" in joined or "MySQL" in joined)
        self.assertIn("后端", joined)

    def test_spark_questions_are_grounded_when_model_returns_generic_question(self):
        app_module = sys.modules["app"]
        llm_payload = {
            "job_direction": "后端开发",
            "interview_style": "真实电话面试",
            "questions": [
                {
                    "id": "q1",
                    "stage": "self_intro",
                    "type": "自我介绍",
                    "difficulty": "easy",
                    "question": "请你简单介绍一下自己。",
                    "intent": "了解候选人。",
                    "expected_points": [],
                    "bad_answer_signals": [],
                    "followup_rules": [],
                    "scoring_rubric": {},
                }
            ],
        }

        class FakeSparkClient:
            def generate_interview_questions(self, resume_text, job_desc, count, job_direction):
                return llm_payload

        with patch.object(app_module.config, "IFLYTEK_SPARK_API_PASSWORD", "test-password"):
            with patch.object(app_module, "SparkLLMClient", FakeSparkClient, create=True):
                plan = app_module.generate_interview_plan(
                    resume_text="项目：校园二手交易平台\n技术：Spring Boot、MySQL\n负责：订单接口",
                    job_desc="Java 后端开发实习，要求 Spring Boot、MySQL、REST API 设计。",
                    count=1,
                )

        question = plan["questions"][0]
        self.assertIn("校园二手交易平台", question["question"])
        self.assertTrue("Spring Boot" in question["question"] or "MySQL" in question["question"])
        self.assertTrue(question["evidence_from_resume"])
        self.assertTrue(question["evidence_from_jd"])

    def test_resume_evidence_keeps_structured_lines_readable(self):
        app_module = sys.modules["app"]

        evidence = app_module.extract_resume_evidence(
            "项目：校园二手交易平台\n"
            "技术：Vue、Spring Boot、MySQL、Redis\n"
            "负责：商品发布接口、订单接口、Redis 缓存和异常处理\n"
            "成果：接口平均响应从 800ms 降到 300ms"
        )

        self.assertIn("校园二手交易平台", evidence)
        self.assertIn("Spring Boot", evidence)
        self.assertIn("商品发布接口", evidence)
        self.assertFalse(evidence.endswith("；Vue、S"))

    def test_fallback_questions_for_non_engineering_roles_are_grounded(self):
        app_module = sys.modules["app"]

        plan = app_module.generate_interview_plan(
            resume_text=(
                "项目：校园社团活动增长\n"
                "技术：问卷调研、用户分层、活动数据复盘\n"
                "负责：拉新活动策划、社群转化和复盘报告"
            ),
            job_desc="产品运营实习，要求用户洞察、活动策划、数据复盘和跨部门沟通。",
            count=5,
        )

        joined = "\n".join(question["question"] for question in plan["questions"])
        self.assertIn("校园社团活动增长", joined)
        self.assertTrue("用户洞察" in joined or "活动策划" in joined or "数据复盘" in joined)

    def test_fallback_questions_prioritize_jd_and_use_second_person(self):
        app_module = sys.modules["app"]

        plan = app_module.generate_interview_plan(
            resume_text=(
                "姓名：张三\n"
                "项目：校园二手交易平台\n"
                "技术：Vue、Spring Boot、MySQL"
            ),
            job_desc="目标岗位：产品运营实习。要求用户增长、活动策划、数据复盘、社群运营和跨部门沟通。",
            count=5,
        )

        joined = "\n".join(question["question"] for question in plan["questions"])
        self.assertIn("产品运营", joined)
        self.assertTrue(any(keyword in joined for keyword in ["用户增长", "活动策划", "数据复盘", "社群运营", "跨部门沟通"]))
        self.assertIn("你", joined)
        self.assertNotIn("张三", joined)
        self.assertNotIn("姓名", joined)
        self.assertNotIn("简历里提到", joined)

    def test_interview_answer_does_not_return_followup(self):
        app_module = sys.modules["app"]
        session_id = "followup-session"
        app_module.SESSIONS[session_id] = {
            "resume_text": "Python Flask API project",
            "job_desc": "Backend developer",
            "questions": [
                {
                    "id": "q1",
                    "type": "项目深挖",
                    "content": "讲一下你的 Flask 项目。",
                }
            ],
            "interview_plan": {
                "job_direction": "后端开发",
                "interview_style": "真实电话面试",
                "questions": [
                    {
                        "id": "q1",
                        "stage": "project_deep_dive",
                        "type": "项目深挖",
                        "difficulty": "medium",
                        "question": "讲一下你的 Flask 项目。",
                        "intent": "判断项目真实性。",
                        "expected_points": ["个人贡献", "技术难点", "结果"],
                        "bad_answer_signals": ["没有个人贡献"],
                        "followup_rules": [
                            {
                                "condition": "没有说明个人贡献",
                                "question": "这个项目里你自己具体负责哪一块？",
                            },
                            {
                                "condition": "没有量化结果",
                                "question": "最后结果怎么衡量？有没有具体数据？",
                            },
                        ],
                        "scoring_rubric": {},
                    }
                ],
            },
            "answers": {},
        }

        first = self.client.post(
            "/api/interview/answer",
            json={
                "session_id": session_id,
                "question_id": "q1",
                "answer": "这个项目主要用了 Flask。",
            },
        )

        self.assertEqual(first.status_code, 200)
        first_payload = first.get_json()
        self.assertEqual(first_payload["code"], 0)
        self.assertTrue(first_payload["data"]["saved"])
        self.assertEqual(first_payload["data"]["followup"], None)
        self.assertEqual(app_module.SESSIONS[session_id]["answers"]["q1"], "这个项目主要用了 Flask。")

        feedback = self.client.post("/api/interview/feedback", json={"session_id": session_id})
        review = feedback.get_json()["data"]["reviews"][0]
        self.assertIn("这个项目主要用了 Flask。", review["answer"])
        self.assertNotIn("追问", review["answer"])

    def test_interview_answer_returns_adaptive_next_question(self):
        app_module = sys.modules["app"]
        session_id = "adaptive-session"
        app_module.SESSIONS[session_id] = {
            "resume_text": "项目：校园活动增长\n负责：社群运营、活动策划、数据复盘",
            "job_desc": "产品运营实习，要求用户增长、活动策划、数据复盘和跨部门沟通。",
            "questions": [
                {"id": "q1", "type": "岗位匹配", "content": "你最匹配产品运营的一段经历是什么？"},
                {"id": "q2", "type": "能力验证", "content": "请继续讲一个运营经历。"},
            ],
            "interview_plan": {
                "job_direction": "产品运营",
                "interview_style": "真实电话面试",
                "questions": [
                    {"id": "q1", "type": "岗位匹配", "question": "你最匹配产品运营的一段经历是什么？"},
                    {"id": "q2", "type": "能力验证", "question": "请继续讲一个运营经历。"},
                ],
            },
            "answers": {},
        }

        response = self.client.post(
            "/api/interview/answer",
            json={
                "session_id": session_id,
                "question_id": "q1",
                "answer": "我负责社群运营和数据复盘，通过活动策划提升用户增长。",
            },
        )

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["followup"], None)
        next_question = payload["data"]["next_question"]
        self.assertEqual(next_question["id"], "q2")
        self.assertIn("你", next_question["content"])
        self.assertTrue(any(keyword in next_question["content"] for keyword in ["社群运营", "数据复盘", "活动策划", "用户增长"]))
        self.assertEqual(app_module.SESSIONS[session_id]["questions"][1]["content"], next_question["content"])

    def test_interview_next_question_uses_conversation_memory_and_uncovered_jd_points(self):
        app_module = sys.modules["app"]
        session_id = "memory-session"
        app_module.SESSIONS[session_id] = {
            "resume_text": "项目：校园活动增长\n负责：问卷调研、社群运营、活动策划",
            "job_desc": "产品运营实习，要求用户洞察、活动策划、数据复盘和跨部门沟通。",
            "questions": [
                {"id": "q1", "type": "岗位匹配", "content": "你做过哪段最能体现产品运营匹配度的经历？"},
                {"id": "q2", "type": "行动拆解", "content": "你当时具体做了什么？"},
                {"id": "q3", "type": "能力验证", "content": "再讲一个运营经历。"},
            ],
            "interview_plan": {
                "job_direction": "产品运营",
                "interview_style": "真实电话面试",
                "questions": [
                    {"id": "q1", "type": "岗位匹配", "question": "你做过哪段最能体现产品运营匹配度的经历？"},
                    {"id": "q2", "type": "行动拆解", "question": "你当时具体做了什么？"},
                    {"id": "q3", "type": "能力验证", "question": "再讲一个运营经历。"},
                ],
            },
            "answers": {},
        }

        first = self.client.post(
            "/api/interview/answer",
            json={
                "session_id": session_id,
                "question_id": "q1",
                "answer": "我先做了问卷调研，发现新生不知道活动入口，所以把重点放在用户洞察上。",
            },
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            "/api/interview/answer",
            json={
                "session_id": session_id,
                "question_id": "q2",
                "answer": "我把报名链路简化，并负责活动策划和社群触达。",
            },
        )

        payload = second.get_json()
        self.assertEqual(second.status_code, 200)
        next_question = payload["data"]["next_question"]
        self.assertEqual(next_question["id"], "q3")
        self.assertIn("你", next_question["content"])
        self.assertIn("问卷调研", next_question["content"])
        self.assertTrue(any(keyword in next_question["content"] for keyword in ["数据复盘", "跨部门沟通"]))
        self.assertNotIn("再讲一个运营经历", next_question["content"])

    def test_chat_returns_answer(self):
        response = self.client.post("/api/chat", json={"text": "面试怎么准备"})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["code"], 0)
        self.assertIn("answer", payload)

    def test_voice_chat_requires_audio(self):
        response = self.client.post("/api/voice-chat", data={})

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["code"], 1)
        self.assertIn("audio", payload["message"])

    def test_voice_chat_reports_empty_speech_recognition_result(self):
        app_module = sys.modules["app"]

        with patch.object(app_module.config, "XFYUN_APPID", "appid"):
            with patch.object(app_module.config, "XFYUN_API_KEY", "key"):
                with patch.object(app_module.config, "XFYUN_API_SECRET", "secret"):
                    with patch.object(app_module, "recognize_audio_with_xfyun", return_value=""):
                        response = self.client.post(
                            "/api/voice-chat",
                            data={"audio": (io.BytesIO(b"fake audio"), "recording.webm")},
                        )

        self.assertEqual(response.status_code, 422)
        payload = response.get_json()
        self.assertEqual(payload["code"], 1)
        self.assertIn("未识别到有效语音", payload["message"])

    def test_voice_chat_transcribe_mode_does_not_generate_chat_answer(self):
        app_module = sys.modules["app"]

        with patch.object(app_module, "transcribe_audio", return_value="我负责订单接口和 Redis 缓存"):
            with patch.object(app_module, "build_chat_answer") as chat_answer:
                response = self.client.post(
                    "/api/voice-chat",
                    data={
                        "mode": "transcribe",
                        "audio": (io.BytesIO(b"fake audio"), "recording.webm"),
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["question"], "我负责订单接口和 Redis 缓存")
        self.assertEqual(payload["answer"], "")
        chat_answer.assert_not_called()

    def test_interview_speak_returns_synthesized_audio(self):
        app_module = sys.modules["app"]

        with patch.object(app_module.config, "XFYUN_APPID", "appid"):
            with patch.object(app_module.config, "XFYUN_API_KEY", "key"):
                with patch.object(app_module.config, "XFYUN_API_SECRET", "secret"):
                    with patch.object(app_module, "synthesize_interviewer_audio", return_value=b"fake mp3 bytes"):
                        response = self.client.post("/api/interview/speak", json={"text": "\u8bed\u97f3\u5408\u6210\u670d\u52a1\u672a\u914d\u7f6e"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "audio/mpeg")
        self.assertEqual(response.data, b"fake mp3 bytes")

    def test_interview_speak_falls_back_fast_without_voice_credentials(self):
        response = self.client.post("/api/interview/speak", json={"text": "\u8bed\u97f3\u5408\u6210\u670d\u52a1\u672a\u914d\u7f6e"})

        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertEqual(payload["code"], 1)
        self.assertIn("\u8bed\u97f3\u5408\u6210\u670d\u52a1\u672a\u914d\u7f6e", payload["message"])

    def test_interview_speak_requires_text(self):
        response = self.client.post("/api/interview/speak", json={})

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["code"], 1)
        self.assertIn("text", payload["message"])

    def test_frontend_uses_image_only_resume_analysis_flow(self):
        front_html = (FRONTEND_DIR / "front.html").read_text(encoding="utf-8")
        unified_html = (FRONTEND_DIR / "unified.html").read_text(encoding="utf-8")

        self.assertNotIn("id=\"resumeText\"", front_html)
        self.assertNotIn("resume_text", front_html)
        self.assertNotIn("manualResumeText", front_html)
        self.assertIn("formData.append('image', resumeFile)", front_html)
        self.assertIn("window.location.replace('/front.html')", unified_html)

    def test_front_interview_tts_helper_is_defined_once(self):
        front_html = (FRONTEND_DIR / "front.html").read_text(encoding="utf-8")
        unified_html = (FRONTEND_DIR / "unified.html").read_text(encoding="utf-8")

        self.assertEqual(front_html.count("function speakInterviewer(text)"), 1)
        self.assertIn("/api/interview/speak", front_html)
        self.assertIn("window.location.replace('/front.html')", unified_html)

    def test_frontend_interview_is_turn_based_with_live_transcription(self):
        front_html = (FRONTEND_DIR / "front.html").read_text(encoding="utf-8")
        unified_html = (FRONTEND_DIR / "unified.html").read_text(encoding="utf-8")

        self.assertIn("function lockCandidateAnswer", front_html)
        self.assertIn("function beginCandidateAnswer", front_html)
        self.assertIn("function startLiveInterviewTranscription", front_html)
        self.assertIn("function stopLiveInterviewTranscription", front_html)
        self.assertIn("SpeechRecognition || window.webkitSpeechRecognition", front_html)
        self.assertIn("recognition.interimResults = true", front_html)
        self.assertIn("speakInterviewer(q.content).then(function() { beginCandidateAnswer(); })", front_html)
        self.assertIn("stopLiveInterviewTranscription();", front_html)
        self.assertIn("toggleInterviewVoiceInput", front_html)
        self.assertIn("startInterviewRecording", front_html)
        self.assertIn("transcribe", front_html)
        self.assertNotIn("onclick=\"document.getElementById('interviewAnswer').focus()\"", front_html)
        self.assertIn("window.location.replace('/front.html')", unified_html)

    def test_frontend_has_no_interview_followup_flow(self):
        front_html = (FRONTEND_DIR / "front.html").read_text(encoding="utf-8")
        unified_html = (FRONTEND_DIR / "unified.html").read_text(encoding="utf-8")

        self.assertNotIn("renderInterviewFollowup", front_html)
        self.assertNotIn("currentFollowup", front_html)
        self.assertNotIn("followup_id", front_html)
        self.assertNotIn("我追问一下", front_html)
        self.assertNotIn("继续追问", front_html)
        self.assertIn("window.location.replace('/front.html')", unified_html)

    def test_frontend_applies_adaptive_next_question(self):
        front_html = (FRONTEND_DIR / "front.html").read_text(encoding="utf-8")
        unified_html = (FRONTEND_DIR / "unified.html").read_text(encoding="utf-8")

        self.assertIn("next_question", front_html)
        self.assertIn("applyAdaptiveNextQuestion", front_html)
        self.assertIn("interviewQuestions[currentQIndex + 1]", front_html)
        self.assertIn("根据你的回答调整下一题", front_html)
        self.assertIn("window.location.replace('/front.html')", unified_html)

    def test_unified_html_is_a_thin_alias_page(self):
        unified_html = (FRONTEND_DIR / "unified.html").read_text(encoding="utf-8")

        self.assertIn("window.location.replace('/front.html')", unified_html)
        self.assertNotIn("function speakInterviewer(text)", unified_html)
        self.assertNotIn("function startLiveInterviewTranscription", unified_html)

    def test_frontend_preserves_live_transcription_text_before_restart(self):
        front_html = (FRONTEND_DIR / "front.html").read_text(encoding="utf-8")

        self.assertIn("var currentText = document.getElementById('interviewAnswer').value.trim();", front_html)
        self.assertIn("if (currentText && currentText !== liveInterviewFinalText) {", front_html)
        self.assertIn("liveInterviewFinalText = currentText;", front_html)

    def test_frontend_clears_previous_answer_before_next_question(self):
        front_html = (FRONTEND_DIR / "front.html").read_text(encoding="utf-8")

        self.assertIn("function resetInterviewAnswerState()", front_html)
        self.assertIn("document.getElementById('interviewAnswer').value = '';", front_html)
        self.assertIn("liveInterviewFinalText = '';", front_html)
        self.assertIn("function renderInterviewQuestion()", front_html)
        self.assertIn("resetInterviewAnswerState();", front_html)

    def test_recognize_audio_with_xfyun_cleans_up_converted_pcm(self):
        app_module = sys.modules["app"]
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "sample.webm"
            audio_path.write_bytes(b"fake-audio")
            pcm_path = audio_path.with_suffix(".pcm")

            def fake_convert(source, target):
                self.assertEqual(Path(source), audio_path)
                self.assertEqual(Path(target), pcm_path)
                pcm_path.write_bytes(b"fake-pcm")

            with patch.object(app_module, "convert_audio_to_pcm", side_effect=fake_convert):
                with patch.object(app_module, "recognize_audio_with_xfyun", wraps=app_module.recognize_audio_with_xfyun):
                    with patch.dict(sys.modules, {"voice_chat_flow": MagicMock(recognize_pcm=MagicMock(return_value="识别成功"))}):
                        result = app_module.recognize_audio_with_xfyun(audio_path)

        self.assertEqual(result, "识别成功")
        self.assertFalse(pcm_path.exists())

    def test_voice_chat_flow_mp3_conversion_cleans_up_temp_pcm(self):
        sys.modules.pop("voice_chat_flow", None)
        voice_module = importlib.import_module("voice_chat_flow")

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "sample.mp3"
            audio_path.write_bytes(b"fake-mp3")
            temp_pcm = Path(tmpdir) / "_tmp_convert.pcm"

            def fake_run(command, capture_output):
                temp_pcm.write_bytes(b"fake-pcm")
                return type("Completed", (), {"returncode": 0, "stderr": b""})()

            fake_event = MagicMock()
            fake_event.wait.return_value = True
            fake_event.is_set.return_value = True
            fake_ws = MagicMock()
            fake_ws.run_forever.side_effect = lambda **kwargs: None

            with patch.object(voice_module, "PROJECT_DIR", Path(tmpdir)):
                with patch.object(voice_module.config, "XFYUN_APPID", "appid"):
                    with patch.object(voice_module.config, "XFYUN_API_SECRET", "secret"):
                        with patch.object(voice_module.config, "XFYUN_API_KEY", "key"):
                            with patch.object(voice_module.subprocess, "run", side_effect=fake_run):
                                with patch.object(voice_module.threading, "Event", return_value=fake_event):
                                    with patch.object(voice_module.websocket, "WebSocketApp", return_value=fake_ws):
                                        result = voice_module.recognize_pcm(audio_path)

        self.assertEqual(result, "")
        self.assertFalse(temp_pcm.exists())

    def test_voice_chat_flow_raises_when_websocket_timeout_expires(self):
        sys.modules.pop("voice_chat_flow", None)
        voice_module = importlib.import_module("voice_chat_flow")

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "sample.pcm"
            audio_path.write_bytes(b"0" * 3200)

            fake_event = MagicMock()
            fake_event.wait.return_value = False
            fake_event.is_set.return_value = False
            fake_ws = MagicMock()
            fake_ws.run_forever.side_effect = lambda **kwargs: None

            with patch.object(voice_module.config, "XFYUN_APPID", "appid"):
                with patch.object(voice_module.config, "XFYUN_API_SECRET", "secret"):
                    with patch.object(voice_module.config, "XFYUN_API_KEY", "key"):
                        with patch.object(voice_module.threading, "Event", return_value=fake_event):
                            with patch.object(voice_module.websocket, "WebSocketApp", return_value=fake_ws):
                                with self.assertRaisesRegex(RuntimeError, "IAT websocket timeout"):
                                    voice_module.recognize_pcm(audio_path)

    def test_voice_chat_logs_mode_and_result_lengths(self):
        app_module = sys.modules["app"]

        with patch.object(app_module, "transcribe_audio", return_value="鎴戣礋璐ｈ鍗曟帴鍙ｅ拰 Redis 缂撳瓨"):
            with patch.object(app_module, "build_chat_answer", return_value="寤鸿鍏堝噯澶囪嚜鎴戜粙缁嶅拰椤圭洰鏁呬簨"):
                with self.assertLogs("app", level="INFO") as logs:
                    response = self.client.post(
                        "/api/voice-chat",
                        data={
                            "mode": "chat",
                            "audio": (io.BytesIO(b"fake audio"), "recording.webm"),
                        },
                    )

        self.assertEqual(response.status_code, 200)
        joined = "\n".join(logs.output)
        self.assertIn("Voice chat request", joined)
        self.assertIn("mode=chat", joined)
        self.assertIn("transcript_chars=", joined)
        self.assertIn("answer_chars=", joined)

    def test_frontend_removes_unused_toggle_interview_recording_helper(self):
        front_html = (FRONTEND_DIR / "front.html").read_text(encoding="utf-8")

        self.assertNotIn("async function toggleInterviewRecording()", front_html)

    def test_voice_chat_flow_logs_recognition_lifecycle(self):
        sys.modules.pop("voice_chat_flow", None)
        voice_module = importlib.import_module("voice_chat_flow")

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "sample.pcm"
            audio_path.write_bytes(b"0" * 3200)

            fake_event = MagicMock()
            fake_event.wait.return_value = True
            fake_event.is_set.return_value = True
            fake_ws = MagicMock()
            fake_ws.run_forever.side_effect = lambda **kwargs: None

            with patch.object(voice_module.config, "XFYUN_APPID", "appid"):
                with patch.object(voice_module.config, "XFYUN_API_SECRET", "secret"):
                    with patch.object(voice_module.config, "XFYUN_API_KEY", "key"):
                        with patch.object(voice_module.threading, "Event", return_value=fake_event):
                            with patch.object(voice_module.websocket, "WebSocketApp", return_value=fake_ws):
                                with self.assertLogs("voice_chat_flow", level="INFO") as logs:
                                    result = voice_module.recognize_pcm(audio_path)

        self.assertEqual(result, "")
        joined = "\n".join(logs.output)
        self.assertIn("Starting IAT recognition", joined)
        self.assertIn("IAT recognition completed", joined)


if __name__ == "__main__":
    unittest.main()
