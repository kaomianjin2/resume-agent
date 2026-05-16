from __future__ import annotations

from typing import TextIO

from interview_agent.executor import NodeExecutionResult


def write_result(output: TextIO, result: NodeExecutionResult, node_name: str) -> None:
    if result.status == "success":
        write_success_output(output, node_name, result.output)
        return
    write_line(output, format_error(output, "处理失败。"))
    if result.error_message:
        write_line(output, f"{format_error(output, '错误信息')}: {result.error_message}")


def write_success_output(output: TextIO, node_name: str, result_output: dict[str, object]) -> None:
    if node_name == "algorithm_practice":
        practice_set = result_output.get("practice_set")
        if isinstance(practice_set, dict):
            write_line(output, format_title(output, "我生成了这些算法和数据结构练习："))
            _write_mapping_summary(output, practice_set)
        return

    if node_name == "question_generate":
        questions = result_output.get("questions")
        if isinstance(questions, list) and questions:
            write_line(output, format_title(output, "我生成了这些面试题："))
            _write_list(output, questions)
        return

    if node_name == "knowledge_search":
        search_results = result_output.get("search_results")
        if isinstance(search_results, list) and search_results:
            write_line(output, format_title(output, "我找到这些准备资料："))
            _write_list(output, search_results[:3])
            return
        if isinstance(search_results, list):
            write_line(output, "未检索到相关知识片段。")
        return

    if node_name == "jd_parse":
        requirements = result_output.get("jd_requirements")
        if isinstance(requirements, dict):
            write_line(output, format_title(output, "我整理出的岗位要求："))
            _write_mapping_summary(output, requirements)
        return

    if node_name == "resume_parse":
        profile = result_output.get("resume_profile")
        if isinstance(profile, dict):
            write_line(output, format_title(output, "我整理出的简历信息："))
            _write_mapping_summary(output, profile)
        return

    if node_name == "jd_match":
        match_report = result_output.get("match_report")
        if isinstance(match_report, dict):
            write_line(output, format_title(output, "我整理出的匹配分析："))
            _write_mapping_summary(output, match_report)
        return

    if node_name == "mock_followup":
        followups = result_output.get("followup_questions")
        if isinstance(followups, list) and followups:
            write_line(output, format_title(output, "我建议继续追问："))
            _write_list(output, followups)
        return

    if node_name == "answer_score":
        score_report = result_output.get("score_report")
        if isinstance(score_report, dict):
            write_line(output, format_title(output, "我对回答的评分反馈："))
            _write_mapping_summary(output, score_report)
        return

    if node_name == "weakness_train":
        training_plan = result_output.get("training_plan")
        if isinstance(training_plan, dict):
            write_line(output, format_title(output, "我整理出的薄弱点训练计划："))
            _write_mapping_summary(output, training_plan)
        return

    if node_name == "resume_optimize":
        optimization_advice = result_output.get("optimization_advice")
        if isinstance(optimization_advice, dict):
            write_line(output, format_title(output, "我给出的简历优化建议："))
            _write_resume_optimization_advice(output, optimization_advice)
        return

    if node_name == "project_extract":
        project_experiences = result_output.get("project_experiences")
        if isinstance(project_experiences, list) and project_experiences:
            write_line(output, format_title(output, "我提取出的项目经历重点："))
            _write_list(output, project_experiences)
        return

    if node_name == "session_summary":
        summary = result_output.get("summary")
        if isinstance(summary, dict):
            write_line(output, format_title(output, "我整理出的本轮总结："))
            _write_mapping_summary(output, summary)


def write_existing_list(
    *,
    output: TextIO,
    session_inputs: dict[str, object],
    key: str,
    title: str,
    next_prompt: str,
) -> bool:
    values = session_inputs.get(key)
    if not isinstance(values, list) or not values:
        return False
    write_line(output, format_title(output, title))
    _write_list(output, values)
    write_line(output, next_prompt)
    return True


def write_existing_mapping(
    *,
    output: TextIO,
    session_inputs: dict[str, object],
    key: str,
    title: str,
    next_prompt: str,
) -> bool:
    values = session_inputs.get(key)
    if not isinstance(values, dict) or not values:
        return False
    write_line(output, format_title(output, title))
    _write_mapping_summary(output, values)
    write_line(output, next_prompt)
    return True


def write_existing_text(
    *,
    output: TextIO,
    session_inputs: dict[str, object],
    key: str,
    title: str,
    next_prompt: str,
) -> bool:
    value = session_inputs.get(key)
    if not isinstance(value, str) or not value.strip():
        return False
    write_line(output, format_title(output, title))
    write_line(output, _format_output_value(value))
    write_line(output, next_prompt)
    return True


def _write_list(output: TextIO, items: list[object]) -> None:
    for index, item in enumerate(items, start=1):
        write_line(output, f"{format_index(output, f'{index}.')} {_format_output_value(item)}")


def _write_mapping_summary(output: TextIO, values: dict[str, object]) -> None:
    for key, value in list(values.items())[:6]:
        formatted_key = format_key(output, _format_output_key(key))
        write_line(output, f"- {formatted_key}: {_format_output_value(value)}")


def _write_resume_optimization_advice(output: TextIO, values: dict[str, object]) -> None:
    preferred_keys = (
        "overall_match",
        "overall_match_assessment",
        "priority_actions",
        "high_priority_actions",
        "section_level_optimization",
        "jd_alignment_keywords_to_embed",
        "rewritten_summary_example",
        "rewritten_experience_bullet_example",
        "summary",
        "suggestions",
    )
    written_keys: set[str] = set()
    for key in preferred_keys:
        if key not in values:
            continue
        _write_structured_output_item(
            output,
            _format_resume_optimization_key(key),
            values[key],
            indent_level=0,
        )
        written_keys.add(key)

    for key, value in values.items():
        if key in written_keys:
            continue
        _write_structured_output_item(
            output,
            _format_resume_optimization_key(key),
            value,
            indent_level=0,
        )


def _write_structured_output_item(
    output: TextIO,
    label: str,
    value: object,
    *,
    indent_level: int,
) -> None:
    indent = "  " * indent_level
    formatted_label = format_key(output, label)
    if isinstance(value, dict):
        write_line(output, f"{indent}- {formatted_label}：")
        for child_key, child_value in value.items():
            _write_structured_output_item(
                output,
                _format_resume_optimization_key(child_key),
                child_value,
                indent_level=indent_level + 1,
            )
        return
    if isinstance(value, list):
        write_line(output, f"{indent}- {formatted_label}：")
        for item in value:
            if isinstance(item, dict):
                _write_structured_output_item(output, "明细", item, indent_level=indent_level + 1)
                continue
            write_line(output, f"{'  ' * (indent_level + 1)}- {_format_output_value(item)}")
        return
    write_line(output, f"{indent}- {formatted_label}：{_format_output_value(value)}")


def _format_resume_optimization_key(key: str) -> str:
    labels = {
        "overall_match": "整体匹配",
        "overall_match_assessment": "整体匹配评估",
        "target_jd": "目标岗位",
        "target_role": "目标岗位",
        "match_score": "匹配分",
        "strengths": "优势",
        "risks": "风险",
        "priority_actions": "优先处理动作",
        "high_priority_actions": "优先处理动作",
        "section_level_optimization": "分模块优化建议",
        "basic_info": "基础信息",
        "summary": "职业摘要",
        "skills": "技能表达",
        "experience": "工作经历",
        "projects": "项目经历",
        "issues": "问题",
        "suggestion": "建议",
        "suggestions": "建议",
        "jd_alignment_keywords_to_embed": "需嵌入的招聘关键词",
        "rewritten_summary_example": "优化后摘要示例",
        "rewritten_experience_bullet_example": "优化后经历示例",
        "bullets": "要点",
        "gaps": "缺口",
        "priority": "优先级",
        "action": "动作",
        "details": "详细说明",
        "actions": "行动项",
        "examples": "示例",
    }
    return labels.get(key, _format_output_key(key))


def _format_output_key(key: str) -> str:
    labels = {
        "name": "姓名",
        "role": "岗位",
        "target_role": "目标岗位",
        "skills": "技能",
        "projects": "项目经历",
        "experience": "经验",
        "strengths": "优势",
        "weaknesses": "薄弱点",
        "risks": "风险",
        "score": "评分",
        "summary": "总结",
        "suggestions": "建议",
    }
    return labels.get(key, key)


def _format_output_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "、".join(_format_output_value(item) for item in value[:6])
    if isinstance(value, dict):
        return "；".join(
            f"{key}: {_format_output_value(item)}"
            for key, item in list(value.items())[:4]
        )
    return str(value)


def format_title(output: TextIO, text: str) -> str:
    return _style_terminal_text(output, text, "1;95")


def format_status(output: TextIO, text: str) -> str:
    return _style_terminal_text(output, text, "1;96")


def format_key(output: TextIO, text: str) -> str:
    return _style_terminal_text(output, text, "1;94")


def format_index(output: TextIO, text: str) -> str:
    return _style_terminal_text(output, text, "1;33")


def format_error(output: TextIO, text: str) -> str:
    return _style_terminal_text(output, text, "1;91")


def _style_terminal_text(output: TextIO, text: str, style_code: str) -> str:
    if not getattr(output, "isatty", lambda: False)():
        return text
    return f"\033[{style_code}m{text}\033[0m"


def write_line(output: TextIO, message: str) -> None:
    output.write(message + "\n")
    output.flush()
