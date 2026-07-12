"""
讯飞星火认知大模型客户端。
通过 HTTP API (OpenAI 兼容格式) 调用，Bearer Token 鉴权。
"""
import os
import requests
from backend_errors import UpstreamServiceError
from config import IFLYTEK_SPARK_API_PASSWORD, IFLYTEK_SPARK_HTTP_TIMEOUT, SPARK_URL


class SparkLLMClient:
    def __init__(self, api_password=None, timeout=None):
        self.api_password = api_password or IFLYTEK_SPARK_API_PASSWORD
        self.timeout = timeout if timeout is not None else IFLYTEK_SPARK_HTTP_TIMEOUT
        self.url = SPARK_URL

    def chat(self, messages, model="lite", temperature=0.7, max_tokens=4096, stream=False):
        """
        调用星火大模型进行对话。
        :param messages: 消息列表，格式 [{"role": "user", "content": "..."}]
        :param model: 模型名称，lite / generalv3 / pro-128k 等
        :param temperature: 温度参数
        :param max_tokens: 最大输出 token 数
        :param stream: 是否流式输出
        :return: 模型回复文本
        """
        headers = {
            "Authorization": f"Bearer {self.api_password}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        response = requests.post(self.url, headers=headers, json=payload, timeout=self.timeout, verify=True)

        if response.status_code != 200:
            raise UpstreamServiceError(
                "spark",
                "Spark service request failed",
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise UpstreamServiceError("spark", "Spark service returned invalid JSON") from exc

        if "code" in data and data.get("code") != 0:
            raise UpstreamServiceError(
                "spark",
                f"Spark service returned error code {data.get('code')}",
            )

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("星火大模型未返回有效回复")

        return choices[0]["message"]["content"]

    def analyze_resume(self, resume_text, job_description):
        return self.analyze_resume_structured(resume_text, job_description)

    def analyze_resume_structured(self, resume_text, job_description):
        system_prompt = """你是资深招聘 HR，拥有 10 年技术岗招聘经验。请分析这份简历，从真实招聘决策视角输出严格 JSON。

你必须逐条核对 JD 中的硬性要求是否满足，判断经历可信度，识别风险点，并给出面试深挖方向。

输出格式必须是严格 JSON 对象：
{
  "match_score": 75,
  "match_score_reason": "评分逻辑简述",
  "hard_requirements_check": [
    {"requirement": "JD 中的硬性要求（学历/年限/技术栈/行业等）", "met": true, "evidence": "简历中的证据或'简历中未体现'"}
  ],
  "experience_credibility": {
    "score": 80,
    "concerns": ["时间线矛盾/项目规模夸大/职责描述过泛等具体疑点"]
  },
  "project_contribution_clarity": [
    {"project": "项目名", "personal_role": "个人角色是否明确", "impact_quantified": "个人贡献是否有量化数据"}
  ],
  "risk_flags": [
    {"type": "频繁跳槽/空档期/技能与经历不匹配/学历不达标/缺少核心技能", "detail": "具体描述"}
  ],
  "core_info": {
    "name": "姓名",
    "education": "学历",
    "years": "工作年限",
    "position": "当前/最近职位",
    "skills": ["技能1", "技能2"]
  },
  "advantages": ["优势1", "优势2"],
  "gaps": ["不足1", "不足2"],
  "deep_dive_topics": [
    "面试中值得深挖的 3-5 个具体点，要结合简历中的模糊描述或值得验证的经历"
  ],
  "improvement_suggestions": {
    "structure": "结构层面建议",
    "content": "内容层面建议",
    "keywords": "关键词优化建议",
    "quantification": "量化成果建议"
  },
  "interview_prep_advice": ["准备方向1", "准备方向2"]
}

分析要求：
1. hard_requirements_check 必须逐条对照 JD，不能只有一两条笼统的
2. experience_credibility 要真实挑刺——时间线是否合理、项目规模描述是否可信、职责是否像个人贡献而非团队成果
3. project_contribution_clarity 要逐个项目判断个人角色是否明确、是否有量化数据
4. risk_flags 要从招聘方视角找风险：稳定性风险、能力真实性风险、匹配度风险
5. deep_dive_topics 要是面试中值得追问的具体点，不是泛泛的"深入了解项目"
6. 只输出 JSON，不要 Markdown，不要解释"""

        user_prompt = f"""请分析以下简历与目标岗位的匹配度，从招聘决策视角输出 JSON。

【目标岗位描述】
{job_description}

【简历内容】
{resume_text}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        raw = self.chat(messages, model="generalv3", temperature=0.3, max_tokens=4096)
        return raw

    def score_answer_dimensions(self, question, answer, job_direction, question_intent=""):
        system_prompt = """你是面试评分官。请对候选人的面试回答进行多维度评分。

评分维度（每项 0-20 分）：
1. relevance (相关性)：回答是否紧扣题目，有没有跑题或答非所问
2. structure (结构性)：是否 STAR 结构（背景-任务-行动-结果），逻辑是否清晰
3. concreteness (具体性)：有没有具体项目名、技术细节、数据指标
4. job_fit (岗位匹配)：回答体现的能力是否真正匹配目标岗位
5. expression (表达清晰度)：语言是否清晰、自信、有条理，口语流畅度

额外判断：
- risk_flags：回答中是否有自相矛盾、过度夸大、回避关键问题的信号
- better_example：如果回答有改进空间，给一个更优回答的简短示范（2-3句话）

输出严格 JSON：
{
  "scores": {"relevance": 16, "structure": 14, "concreteness": 15, "job_fit": 13, "expression": 14},
  "total": 72,
  "comment": "简短评语（2-3句话，点出最好和最差的维度）",
  "risk_flags": [],
  "better_example": "更优回答示范（如果回答已经很好则为空字符串）"
}

规则：
- 如果 answer 为空或只有几个字，所有分数给 0-5 分
- 如果 answer 明显跑题，relevance 给 0-8 分
- 如果 answer 全是空话没有具体内容，concreteness 给 0-8 分
- 不要因为回答长就给高分，要判断内容质量
- 只输出 JSON，不要 Markdown"""

        user_prompt = f"""请评分。

【岗位方向】{job_direction}
【题目意图】{question_intent or "考察岗位匹配度"}
【面试题目】{question}
【候选人回答】{answer or "（未作答）"}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        raw = self.chat(
            messages,
            model=os.getenv("IFLYTEK_SPARK_MODEL", "generalv3"),
            temperature=0.3,
            max_tokens=2048,
        )
        return raw

    def generate_interview_questions(self, resume_text, job_desc, count, job_direction):
        system_prompt = build_interview_question_system_prompt(job_direction)
        user_prompt = f"""请根据下面的信息生成一场真实电话面试的题目 JSON。

【岗位方向】
{job_direction}

【题目数量】
{count}

【目标岗位 JD】
{job_desc or "用户没有提供完整 JD，请根据简历和岗位方向生成通用但具体的问题。"}

【候选人简历文本】
{resume_text}

要求：
1. 必须输出 {count} 道题。
2. 每道题都要像真人面试官口头提问，不要像考试题或 AI 模板。
3. 每一道题都必须绑定候选人简历或 JD 的具体证据，不允许生成和材料无关的通用题。
4. 每道题必须填写 evidence_from_resume 和 evidence_from_jd，至少一个字段不能为空。
5. question 文本里必须自然引用一个具体证据点，例如项目名、技术栈、岗位职责、能力要求或业务场景。
6. 如果简历文本太少或像 OCR 失败结果，请优先围绕 JD 出题，并在 evidence_from_resume 写“简历信息不足”。
7. 每个岗位方向的问题侧重点必须不同，不要套用同一套通用问题。
8. 只输出合法 JSON，不要 Markdown，不要解释。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.chat(
            messages,
            model=os.getenv("IFLYTEK_SPARK_MODEL", "generalv3"),
            temperature=0.82,
            max_tokens=4096,
        )

    def generate_adaptive_interview_question(
        self, resume_text, job_desc, job_direction,
        current_question, answer, asked_questions,
        conversation_memory=None, next_index=1,
    ):
        asked_parts = []
        for idx, item in enumerate(asked_questions or []):
            asked_parts.append(f"{idx + 1}. Q: {item.get('content') or item.get('question') or item}")
        asked_text = chr(10).join(asked_parts)
        memory = conversation_memory or {}
        turns_parts = []
        for t_i, t in enumerate((memory.get("turns") or [])[-4:]):
            q_text = t.get('question', '')
            a_text = t.get('answer', '')
            turns_parts.append(f"第{t_i+1}轮 -> 问: {q_text}\n  候选人答: {a_text}")
        turns_text = chr(10).join(turns_parts)
        covered_text = "、".join(memory.get("covered_points") or []) or "暂无"
        uncovered_text = "、".join(memory.get("uncovered_points") or []) or "暂无"

        system_prompt = """你是一个有10年经验的真实面试官。现在面试进行到第""" + str(next_index) + """题。

=== 你的面试风格 ===
你认真听候选人的每一句话。如果候选人说"不知道"、"没做过"、"不太了解"，你不会强行追问那个方向——你会换一个角度，换一个话题，或者降低难度。你像一个人，不像一个照着题库念的机器。

=== 处理不同回答的策略 ===
1. 如果候选人给出了具体内容（项目名/技术点/数据/角色描述）：
   → 顺着这个点深挖一层，或者切换到简历中另一个还没问过的项目/技能
2. 如果候选人说"不知道"/"没做过"/"不太了解"/"这个不太清楚"：
   → 不要追问这个话题！换到简历或JD中另一个完全不同的方向
   → 或者降低难度，问一个更基础、更开放的问题
   → 或者直接问候选人：那你在哪个方面比较有经验？引导他说出自己能聊的内容
3. 如果候选人回答很短（<30字）：
   → 温和地问一个更具体、更容易回答的问题
4. 如果候选人前面已经详细聊过项目A：
   → 下一题必须换到项目B、技能C、或行为题——不能再绕着A打转

=== 出题策略 ===
- 优先覆盖"尚未覆盖的JD能力点"中最重要的一项
- 每次只问一个核心问题
- 口语化，像面试官直接说出来

=== 禁止事项 ===
- 禁止把"我不知道"当作一个真实的经历去追问细节
- 禁止连续两题围绕同一个项目或同一个技能
- 禁止用"请结合""请问"开头——直接问

只输出JSON。{
  "id": "q""" + str(next_index) + """,
  "stage": "adaptive",
  "type": "动态下一题",
  "difficulty": "medium",
  "question": "口语化的下一题",
  "intent": "想考察什么",
  "evidence_from_resume": "依据简历哪个信息点",
  "evidence_from_jd": "依据JD哪个要求",
  "expected_points": ["期待的要点"],
  "bad_answer_signals": ["回答不好的特征"],
  "scoring_rubric": {"relevance":20,"structure":20,"concreteness":20,"job_fit":20,"expression":20}
}"""

        user_prompt = f"""现在需要生成第{next_index}题。

=== 候选人简历 ===
{resume_text}

=== 目标岗位JD ===
{job_desc or "JD未提供"}

=== 岗位方向 ===
{job_direction}

=== 已问过的问题（换话题！） ===
{asked_text or "暂无"}

=== 面试进展 ===
已覆盖：{covered_text}
未覆盖（优先选）：{uncovered_text}

=== 最近对话 ===
{turns_text or "暂无"}

=== 刚才问的 ===
{current_question}

=== 候选人刚才回答 ===
{answer or "（未作答）"}

=== 生成指令 ===
1. 先判断候选人回答质量：有实质内容还是"不知道"/空泛/很短？
2. 有实质内容：抓住具体点自然延伸，或切换到未问过的方向
3. "不知道"/空泛/很短：直接换话题！降低难度！不要再追问原方向！
4. 只输出第{next_index}题JSON"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.chat(
            messages,
            model=os.getenv("IFLYTEK_SPARK_MODEL", "generalv3"),
            temperature=0.72,
            max_tokens=1600,
        )

def build_interview_question_system_prompt(job_direction):
    role_rules = {
        "后端开发": (
            "后端岗要重点追问接口设计、数据库、缓存、异常处理、并发、日志排查、服务稳定性、第三方服务调用和工程边界。"
            "不要只问语言语法，要围绕候选人项目里的数据流、接口职责和真实线上问题追问。"
        ),
        "前端开发": (
            "前端岗要重点追问组件拆分、状态管理、接口联调、页面性能、兼容性、交互细节、异常状态和用户体验。"
            "问题要落在具体页面、具体交互和真实开发协作上。"
        ),
        "算法": (
            "算法岗要重点追问数据来源、标注质量、特征/模型选择、训练验证、指标解释、误差分析、线上落地和算力成本。"
            "不要只问概念定义，要让候选人解释实验过程和失败复盘。"
        ),
        "测试开发": (
            "测试岗要重点追问测试方案、用例设计、边界场景、自动化、缺陷定位、接口测试、性能测试和上线风险判断。"
            "问题要体现质量意识和推动问题闭环的能力。"
        ),
        "产品经理": (
            "产品岗要重点追问用户洞察、需求拆解、优先级、原型设计、指标定义、跨部门沟通和上线后复盘。"
            "问题要像真实业务面试，少问空泛的产品理念，多问具体场景和取舍。"
        ),
        "运营": (
            "运营岗要重点追问活动目标、用户分层、内容策略、渠道投放、转化漏斗、数据复盘和资源受限时的取舍。"
            "问题要关注动作、指标、结果和下一步迭代。"
        ),
        "数据分析": (
            "数据分析岗要重点追问指标体系、SQL、看板、归因分析、异常波动、业务解释和分析结论如何推动决策。"
            "问题要避免只考工具名，要让候选人讲清楚指标背后的业务判断。"
        ),
    }
    direction_rule = role_rules.get(job_direction, "通用岗位要重点追问经历真实性、岗位匹配、沟通协作、学习能力和复盘能力。")
    return f"""你是一名真实电话面试官，正在给大学生或校招候选人做模拟面试。

你的目标不是生成漂亮的题库，而是生成一场像真人电话面试一样的追问脚本。

岗位差异化规则：
{direction_rule}

通用面试规则：
- 题目要自然、短促、口语化，像面试官直接问出来。
- 不要出现“作为 AI”“以下是”“当然可以”“请你详细阐述一下以下问题”等 AI 味表达。
- 不要所有题都用“请结合……”开头，句式要有变化。
- 不要生成泛泛的励志题、鸡汤题或百科题。
- 题目必须能考察真实经历，优先围绕简历项目、岗位 JD 和实习/校招场景。
- 一次只问一个核心问题，不要在一个 question 里塞三四个问题。
- 每道题都要准备追问规则，用来判断候选人回答不清楚时怎么继续问。

输出格式必须是严格 JSON 对象：
{{
  "job_direction": "{job_direction}",
  "interview_style": "真实电话面试",
  "questions": [
    {{
      "id": "q1",
      "stage": "self_intro | project_deep_dive | technical_skill | behavior | hr_fit | reverse_question",
      "type": "中文题型名称",
      "difficulty": "easy | medium | hard",
      "question": "面试官口吻的问题",
      "intent": "这题想判断什么",
      "evidence_from_resume": "引用的简历证据，没有则写简历信息不足",
      "evidence_from_jd": "引用的 JD 证据，没有则写岗位要求未明确",
      "expected_points": ["期待回答点1", "期待回答点2"],
      "bad_answer_signals": ["差回答特征1", "差回答特征2"],
      "followup_rules": [
        {{"condition": "触发追问的条件", "question": "追问问题"}}
      ],
      "scoring_rubric": {{
        "relevance": 20,
        "structure": 20,
        "depth": 20,
        "job_fit": 20,
        "expression": 20
      }}
    }}
  ]
}}"""
