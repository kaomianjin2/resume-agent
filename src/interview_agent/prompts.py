from __future__ import annotations


PROMPT_TEMPLATES: dict[str, str] = {
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
}


def get_prompt_template(prompt_name: str) -> str:
    if prompt_name not in PROMPT_TEMPLATES:
        raise KeyError(f"未知 prompt 模板: {prompt_name}")

    return PROMPT_TEMPLATES[prompt_name]


def render_prompt(prompt_name: str, **variables: str) -> str:
    prompt_template = get_prompt_template(prompt_name)
    try:
        return prompt_template.format(**variables)
    except KeyError as error:
        missing_key = error.args[0]
        raise KeyError(f"prompt 模板缺少变量: {prompt_name}.{missing_key}") from error
