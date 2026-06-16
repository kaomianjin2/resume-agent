from __future__ import annotations


PROMPT_TEMPLATES: dict[str, str] = {
    "algorithm_practice": (
        "你是算法和数据结构练习教练。\n"
        "练习主题：{practice_topic}\n"
        "难度：{difficulty}\n"
        "题目数量：{question_count}\n"
        "请输出算法和数据结构练习 JSON。"
    ),
    "practice_answer_review": (
        "你是算法练习答案评审助手。\n"
        "题目：{practice_question}\n"
        "参考答案：{reference_answer}\n"
        "用户回答：{answer}\n"
        "请判断用户回答是否正确，并输出 JSON。"
    ),
    "knowledge_search": (
        "你是知识库检索助手。\n"
        "问题：{question}\n"
        "上下文：{context}\n"
        "请基于上下文给出结构化 JSON 结果。"
    ),
    "resume_parse": (
        "你是简历解析助手。\n"
        "简历内容：{resume_text}\n"
        "请提取结构化 JSON。"
    ),
    "project_extract": (
        "你是项目经历提炼助手。\n"
        "简历内容：{resume_text}\n"
        "请抽取项目经历并输出 JSON。"
    ),
    "jd_parse": (
        "你是 JD 解析助手。\n"
        "JD 内容：{jd_text}\n"
        "请提取岗位要求并输出 JSON。"
    ),
    "jd_match": (
        "你是 JD 匹配助手。\n"
        "简历信息：{resume_profile}\n"
        "岗位要求：{jd_requirements}\n"
        "请输出匹配分析 JSON。"
    ),
    "question_generate": (
        "你是面试题生成助手。\n"
        "候选人画像：{candidate_profile}\n"
        "目标岗位：{target_role}\n"
        "题型：{question_type}\n"
        "请输出面试题 JSON。"
    ),
    "mock_followup": (
        "你是追问生成助手。\n"
        "原始问题：{question}\n"
        "候选人回答：{answer}\n"
        "请输出追问 JSON。"
    ),
    "answer_score": (
        "你是回答评分助手。\n"
        "问题：{question}\n"
        "回答：{answer}\n"
        "评分标准：{rubric}\n"
        "请输出评分 JSON。"
    ),
    "weakness_train": (
        "你是薄弱点训练助手。\n"
        "薄弱点：{weaknesses}\n"
        "训练目标：{goal}\n"
        "请输出训练计划 JSON。"
    ),
    "resume_optimize": (
        "你是简历优化助手。\n"
        "原始简历：{resume_text}\n"
        "目标岗位：{target_role}\n"
        "请输出优化建议 JSON。"
    ),
    "session_summary": (
        "你是会话总结助手。\n"
        "会话记录：{session_transcript}\n"
        "请输出总结 JSON。"
    ),
    "job_evaluation": (
        "你是岗位评估与投递建议助手。\n"
        "候选人画像：{resume_profile}\n"
        "岗位结构化信息：{job_structured}\n"
        "岗位 JD 文本：{jd_text}\n"
        "请对候选人与该岗位的匹配度进行评估，输出结构化 JSON。\n"
        "JSON 必须包含：score（0-100 整数）、hard_filter_status（字符串）、"
        "strengths（字符串数组）、risks（字符串数组）、missing_information（字符串数组）、"
        "resume_improvement_advice（字符串数组）、application_message（字符串）、"
        "recommended（布尔值）、recommendation_reason（字符串）。"
    ),
}


PROMPT_OUTPUT_KEYS: dict[str, tuple[str, ...]] = {
    "algorithm_practice": ("practice_set",),
    "practice_answer_review": ("practice_answer_feedback",),
    "knowledge_search": ("search_results",),
    "resume_parse": ("resume_profile",),
    "project_extract": ("project_experiences",),
    "jd_parse": ("jd_requirements",),
    "jd_match": ("match_report",),
    "question_generate": ("questions",),
    "mock_followup": ("followup_questions",),
    "answer_score": ("score_report",),
    "weakness_train": ("training_plan",),
    "resume_optimize": ("optimization_advice",),
    "session_summary": ("summary",),
    "job_evaluation": ("evaluation_report",),
}

PROMPT_OUTPUT_SCHEMA_HINTS: dict[str, str] = {
    "algorithm_practice": "practice_set 必须是对象，且包含 topic、difficulty、exercises；exercises 必须是数组。",
    "practice_answer_review": "practice_answer_feedback 必须是对象，且包含 is_correct、feedback、correct_answer。",
    "knowledge_search": "search_results 必须是数组。",
    "resume_parse": "resume_profile 必须是对象。",
    "project_extract": "project_experiences 必须是数组。",
    "jd_parse": "jd_requirements 必须是对象。",
    "jd_match": "match_report 必须是对象。",
    "question_generate": "questions 必须是字符串数组。",
    "mock_followup": "followup_questions 必须是字符串数组。",
    "answer_score": "score_report 必须是对象，且包含 score、gaps、suggestions、reference_answer。",
    "weakness_train": "training_plan 必须是对象，且包含 focus、steps、drills、schedule。",
    "resume_optimize": "optimization_advice 必须是对象，且包含 summary、bullets、risks、rewrite_examples。",
    "session_summary": "summary 必须是对象。",
    "job_evaluation": (
        "evaluation_report 必须是对象，且包含 score、hard_filter_status、strengths、"
        "risks、missing_information、resume_improvement_advice、application_message、"
        "recommended、recommendation_reason。"
    ),
}


def get_prompt_template(prompt_name: str) -> str:
    if prompt_name not in PROMPT_TEMPLATES:
        raise KeyError(f"未知 prompt 模板: {prompt_name}")

    return PROMPT_TEMPLATES[prompt_name]


def render_prompt(prompt_name: str, **variables: str) -> str:
    prompt_template = get_prompt_template(prompt_name)
    try:
        rendered_prompt = prompt_template.format(**variables)
    except KeyError as error:
        missing_key = error.args[0]
        raise KeyError(f"prompt 模板缺少变量: {prompt_name}.{missing_key}") from error

    output_keys = PROMPT_OUTPUT_KEYS[prompt_name]
    output_key_list = ", ".join(output_keys)
    schema_hint = PROMPT_OUTPUT_SCHEMA_HINTS[prompt_name]
    return (
        f"{rendered_prompt}\n"
        "只返回 JSON 对象，不要输出 Markdown 或解释文字。\n"
        f"JSON 顶层必须只包含字段: {output_key_list}。\n"
        f"{schema_hint}"
    )
