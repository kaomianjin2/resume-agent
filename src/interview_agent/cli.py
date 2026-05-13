from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
import re
import sys
from typing import Protocol, TextIO

from interview_agent.config import DEFAULT_CONFIG_PATH, ConfigError, LLMConfig, load_config
from interview_agent.executor import NodeExecutionResult, NodeExecutor
from interview_agent.kb.retrieval import SQLiteHybridRetriever
from interview_agent.kb.parser import extract_text
from interview_agent.llm import FakeLLMClient, OpenAICompatibleClient
from interview_agent.nodes.registry import NodeRegistry, UnknownNodeError, build_default_registry
from interview_agent.planner import (
    ExecutionPlan,
    PlanStep,
    build_execution_plan,
)
from interview_agent.router import RouteResult, route_conversation
from interview_agent.session import SessionStore
from interview_agent.storage import get_knowledge_base_status


DEFAULT_SESSION_ID = "interactive-cli-session"
LLMClient = FakeLLMClient | OpenAICompatibleClient
ServiceMap = Mapping[str, object]
InputFunc = Callable[[str], str]
RouteFunc = Callable[[str, NodeRegistry, LLMClient | None], RouteResult]
LLMFactory = Callable[[LLMConfig], LLMClient]


class ExecutorProtocol(Protocol):
    def execute_node(
        self,
        session_id: str,
        node_name: str,
        inputs: dict[str, object] | None = None,
    ) -> NodeExecutionResult: ...


ExecutorFactory = Callable[[Path, NodeRegistry, ServiceMap], ExecutorProtocol]


class InputCancelledError(RuntimeError):
    """Raised when the user stops providing required interactive inputs."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="interview-agent",
        description="Interactive CLI for the interview agent project.",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"配置文件路径，默认值: {DEFAULT_CONFIG_PATH}",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    input_func: InputFunc = input,
    output: TextIO | None = None,
    registry_builder: Callable[[], NodeRegistry] = build_default_registry,
    route_func: RouteFunc = route_conversation,
    executor_factory: ExecutorFactory | None = None,
    llm_factory: LLMFactory = OpenAICompatibleClient,
    session_id: str = DEFAULT_SESSION_ID,
) -> int:
    output_stream = output or sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    config_path = Path(args.config)

    try:
        config = load_config(config_path)
    except ConfigError as error:
        _write_line(output_stream, f"配置错误: {error}")
        return 1

    database_path = Path(config.storage.database_path)
    knowledge_base_status = get_knowledge_base_status(database_path)
    if knowledge_base_status != "ready":
        _write_line(output_stream, "知识库未就绪，请先执行离线构建：")
        _write_line(output_stream, _build_offline_command(config_path, database_path, Path(config.knowledge_base.source)))
        return 1

    registry = registry_builder()
    session_store = SessionStore(database_path)
    session_store.create_session(session_id)
    llm_client = llm_factory(config.llm)
    services = {
        "llm": llm_client,
        "retriever": SQLiteHybridRetriever(database_path, config.embedding),
    }
    executor = (executor_factory or _default_executor_factory)(database_path, registry, services)

    _write_line(output_stream, "请输入需求，输入 exit 退出。")
    while True:
        user_message = _read_line(input_func, output_stream, "> ")
        if user_message is None:
            _write_line(output_stream, "输入结束，已退出。")
            return 0

        normalized_message = user_message.strip()
        if not normalized_message:
            continue
        if normalized_message in {"exit", "quit", "/exit"}:
            _write_line(output_stream, "已退出。")
            return 0

        session_inputs = session_store.get_all_state(session_id)
        if _answer_from_session_if_possible(normalized_message, session_inputs, output_stream):
            continue

        _write_line(output_stream, _build_processing_hint(normalized_message))

        if _is_mock_interview_request(normalized_message):
            _seed_mock_interview_inputs_from_request(
                session_store=session_store,
                session_id=session_id,
                user_message=normalized_message,
            )
            mock_interview_plan = _build_mock_interview_plan(normalized_message)
            _print_plan(output_stream, mock_interview_plan)
            if not _confirm_ambiguous_route(
                route_result=RouteResult(
                    selected_node="question_generate",
                    candidate_nodes=["question_generate"],
                    via="rule",
                ),
                input_func=input_func,
                output=output_stream,
            ):
                _write_line(output_stream, "已取消执行计划。")
                continue
            try:
                _run_mock_interview(
                    executor=executor,
                    session_store=session_store,
                    session_id=session_id,
                    input_func=input_func,
                    output=output_stream,
                    available_node_names=set(registry.list_names()),
                )
            except InputCancelledError:
                _write_line(output_stream, "输入结束，已取消当前模拟面试。")
            continue

        direct_node_name = _parse_direct_node_name(normalized_message)
        if direct_node_name is not None:
            if not direct_node_name:
                _write_line(output_stream, "处理方式不能为空，请输入具体需求。")
                continue
            if direct_node_name not in registry.list_names():
                _write_line(output_stream, "暂不支持这个处理方式，请换一种说法描述你的需求。")
                continue
            selected_node = direct_node_name
        else:
            route_result = route_func(normalized_message, registry, llm_client)
            selected_node = route_result.selected_node
            if not _confirm_ambiguous_route(route_result, input_func, output_stream):
                _write_line(output_stream, "已取消执行计划。")
                continue

        try:
            plan = build_execution_plan(
                user_message=normalized_message,
                selected_node=selected_node,
                session_inputs=session_inputs,
                registry=registry,
            )
        except UnknownNodeError:
            _write_line(output_stream, "暂不支持这个处理方式，请换一种说法描述你的需求。")
            continue
        _print_plan(output_stream, plan)

        for step_index, step in enumerate(plan.steps):
            _write_line(
                output_stream,
                f"当前进度 {step_index + 1}/{len(plan.steps)}：正在执行{_node_display_name(step.node_name)}。",
            )
            try:
                result = _execute_step_with_prompt(
                    executor=executor,
                    session_store=session_store,
                    session_id=session_id,
                    node_name=step.node_name,
                    input_func=input_func,
                    output=output_stream,
                )
            except InputCancelledError:
                _write_line(output_stream, "输入结束，已取消当前执行。")
                break
            _write_result(output_stream, result, step.node_name)
            if result.status != "success":
                _write_line(output_stream, "请根据错误信息调整输入后继续输入下一步需求，或输入 exit 退出。")
                break
            if step_index < len(plan.steps) - 1:
                _write_line(output_stream, _build_step_transition_prompt(plan.steps[step_index + 1].node_name))
                continue
            _write_line(output_stream, _build_next_need_prompt(step.node_name))


def _default_executor_factory(
    database_path: Path,
    registry: NodeRegistry,
    services: ServiceMap,
) -> NodeExecutor:
    return NodeExecutor(database_path, registry, services=dict(services))


def _build_offline_command(config_path: Path, database_path: Path, source_path: Path) -> str:
    return (
        "uv run python -m interview_agent.kb.build "
        f"--source {source_path} --config {config_path} --db {database_path}"
    )


def _is_mock_interview_request(user_message: str) -> bool:
    return _contains_any(user_message.lower(), ("模拟面试", "mock interview"))


def _build_mock_interview_plan(user_message: str) -> ExecutionPlan:
    steps = [
        _build_step("question_generate"),
        _build_step("mock_followup"),
    ]
    return ExecutionPlan(
        plan_id="mock_interview",
        user_message=user_message,
        steps=steps,
        requires_confirmation=True,
        missing_inputs=[],
        summary="question_generate -> mock_followup",
    )


def _build_step(node_name: str) -> PlanStep:
    return PlanStep(
        node_name=node_name,
        title=node_name.replace("_", " ").title(),
        description=_action_statement_for_node(node_name),
    )


def _run_mock_interview(
    executor: ExecutorProtocol,
    session_store: SessionStore,
    session_id: str,
    input_func: InputFunc,
    output: TextIO,
    available_node_names: set[str],
) -> None:
    _write_line(output, "我会先生成一组层层递进的面试题，然后逐题开始模拟面试。")
    question_result = _execute_step_with_prompt(
        executor=executor,
        session_store=session_store,
        session_id=session_id,
        node_name="question_generate",
        input_func=input_func,
        output=output,
    )
    if question_result.status != "success":
        _write_result(output, question_result, "question_generate")
        return

    questions = _read_text_list(question_result.output.get("questions"))
    if not questions:
        questions = _retry_mock_interview_questions(
            executor=executor,
            session_store=session_store,
            session_id=session_id,
            input_func=input_func,
            output=output,
            available_node_names=available_node_names,
        )
    if not questions:
        _write_line(output, "还没有生成可用于模拟面试的问题。")
        return

    for question_index, question in enumerate(questions, start=1):
        answer = _ask_interview_question(output, input_func, f"第 {question_index} 题：{question}")
        _ask_followup_questions(
            executor=executor,
            session_id=session_id,
            question=question,
            answer=answer,
            input_func=input_func,
            output=output,
        )
    _write_line(output, "模拟面试已完成。")
    _write_line(output, _build_next_need_prompt("mock_followup"))


def _seed_mock_interview_inputs_from_request(
    session_store: SessionStore,
    session_id: str,
    user_message: str,
) -> None:
    candidate_path = _extract_file_path(user_message)
    if candidate_path is None:
        return

    try:
        resume_text = _read_input_file(candidate_path)
    except OSError:
        return
    if not resume_text.strip():
        return

    session_store.set_state(session_id, "resume_text", resume_text)
    session_store.set_state(session_id, "candidate_profile", resume_text)


def _retry_mock_interview_questions(
    executor: ExecutorProtocol,
    session_store: SessionStore,
    session_id: str,
    input_func: InputFunc,
    output: TextIO,
    available_node_names: set[str],
) -> list[str]:
    session_inputs = session_store.get_all_state(session_id)
    if _needs_candidate_profile_backfill(session_inputs):
        if "resume_parse" not in available_node_names:
            return []
        _write_line(output, "首轮未生成题目，我会先补齐候选人信息后再试一次。")
        resume_parse_result = _execute_step_with_prompt(
            executor=executor,
            session_store=session_store,
            session_id=session_id,
            node_name="resume_parse",
            input_func=input_func,
            output=output,
        )
        if resume_parse_result.status != "success":
            _write_result(output, resume_parse_result, "resume_parse")
            return []
        _sync_candidate_profile_from_resume_parse_result(
            session_store=session_store,
            session_id=session_id,
            resume_parse_result=resume_parse_result,
        )
        session_inputs = session_store.get_all_state(session_id)

    if "jd_requirements" not in session_inputs:
        if "jd_parse" not in available_node_names:
            return _retry_question_generate(
                executor=executor,
                session_store=session_store,
                session_id=session_id,
                input_func=input_func,
                output=output,
            )
        _write_line(output, "首轮未生成题目，我会先补齐岗位信息后再试一次。")
        jd_parse_result = _execute_step_with_prompt(
            executor=executor,
            session_store=session_store,
            session_id=session_id,
            node_name="jd_parse",
            input_func=input_func,
            output=output,
        )
        if jd_parse_result.status != "success":
            _write_result(output, jd_parse_result, "jd_parse")
            return []

    return _retry_question_generate(
        executor=executor,
        session_store=session_store,
        session_id=session_id,
        input_func=input_func,
        output=output,
    )


def _retry_question_generate(
    executor: ExecutorProtocol,
    session_store: SessionStore,
    session_id: str,
    input_func: InputFunc,
    output: TextIO,
) -> list[str]:
    retry_result = _execute_step_with_prompt(
        executor=executor,
        session_store=session_store,
        session_id=session_id,
        node_name="question_generate",
        input_func=input_func,
        output=output,
    )
    if retry_result.status != "success":
        _write_result(output, retry_result, "question_generate")
        return []
    return _read_text_list(retry_result.output.get("questions"))


def _sync_candidate_profile_from_resume_parse_result(
    session_store: SessionStore,
    session_id: str,
    resume_parse_result: NodeExecutionResult,
) -> None:
    resume_profile = resume_parse_result.output.get("resume_profile")
    if not isinstance(resume_profile, dict) or not resume_profile:
        return
    session_store.set_state(session_id, "candidate_profile", resume_profile)


def _needs_candidate_profile_backfill(session_inputs: dict[str, object]) -> bool:
    candidate_profile = session_inputs.get("candidate_profile")
    if isinstance(candidate_profile, dict) and candidate_profile:
        return False
    return "resume_text" in session_inputs or "resume_profile" not in session_inputs


def _ask_followup_questions(
    executor: ExecutorProtocol,
    session_id: str,
    question: str,
    answer: str,
    input_func: InputFunc,
    output: TextIO,
) -> None:
    followup_result = executor.execute_node(
        session_id=session_id,
        node_name="mock_followup",
        inputs={"question": question, "answer": answer},
    )
    if followup_result.status != "success":
        _write_result(output, followup_result, "mock_followup")
        return

    followup_questions = _read_text_list(followup_result.output.get("followup_questions"))
    for followup_index, followup_question in enumerate(followup_questions, start=1):
        _ask_interview_question(output, input_func, f"追问 {followup_index}：{followup_question}")


def _ask_interview_question(output: TextIO, input_func: InputFunc, prompt: str) -> str:
    answer = _read_line(input_func, output, f"{prompt}\n你的回答: ")
    if answer is None:
        raise InputCancelledError("缺少候选人回答")
    return answer


def _read_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    text_items: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            text_items.append(item)
            continue
        if isinstance(item, dict):
            text_value = _read_first_text_field(item, ("question", "content", "text"))
            if text_value:
                text_items.append(text_value)
    return text_items


def _read_first_text_field(value: dict[object, object], field_names: tuple[str, ...]) -> str | None:
    for field_name in field_names:
        field_value = value.get(field_name)
        if isinstance(field_value, str) and field_value.strip():
            return field_value
    return None


def _answer_from_session_if_possible(
    user_message: str,
    session_inputs: dict[str, object],
    output: TextIO,
) -> bool:
    requested_content = _requested_existing_content(user_message)
    if requested_content is None:
        return False

    if requested_content == "questions":
        if _write_existing_list(
            output=output,
            session_inputs=session_inputs,
            key="questions",
            title="刚才生成的面试题在这里：",
            next_prompt=_build_next_need_prompt("question_generate"),
        ):
            return True
        _write_line(output, "我还没有生成面试题。你可以把 JD 和简历给我，我来生成一组面试题。")
        return True

    if requested_content == "jd":
        if _write_existing_mapping(
            output=output,
            session_inputs=session_inputs,
            key="jd_requirements",
            title="我已经整理出的岗位要求：",
            next_prompt=_build_next_need_prompt("jd_parse"),
        ):
            return True
        if _write_existing_text(
            output=output,
            session_inputs=session_inputs,
            key="jd_text",
            title="当前已有的招聘 JD 内容：",
            next_prompt=_build_next_need_prompt("jd_parse"),
        ):
            return True
        _write_line(output, "我还没有读取招聘 JD。你可以粘贴 JD，或输入 JD 文件路径。")
        return True

    if requested_content == "resume":
        for key in ("candidate_profile", "resume_profile"):
            if _write_existing_mapping(
                output=output,
                session_inputs=session_inputs,
                key=key,
                title="我已经整理出的简历信息：",
                next_prompt=_build_next_need_prompt("resume_parse"),
            ):
                return True
        if _write_existing_text(
            output=output,
            session_inputs=session_inputs,
            key="resume_text",
            title="当前已有的简历内容：",
            next_prompt=_build_next_need_prompt("resume_parse"),
        ):
            return True
        _write_line(output, "我还没有读取简历。你可以粘贴简历内容，或输入简历文件路径。")
        return True

    if requested_content == "match":
        if _write_existing_mapping(
            output=output,
            session_inputs=session_inputs,
            key="match_report",
            title="我已经整理出的匹配分析：",
            next_prompt=_build_next_need_prompt("jd_match"),
        ):
            return True
        _write_line(output, "我还没有生成匹配分析。你可以先提供简历和招聘 JD，我来对比匹配度。")
        return True

    if requested_content == "search":
        if _write_existing_list(
            output=output,
            session_inputs=session_inputs,
            key="search_results",
            title="刚才找到的准备资料在这里：",
            next_prompt=_build_next_need_prompt("knowledge_search"),
        ):
            return True
        _write_line(output, "我还没有查找资料。你可以告诉我想准备的岗位、技术点或面试问题。")
        return True

    return False


def _requested_existing_content(user_message: str) -> str | None:
    if not _asks_to_review_existing_content(user_message):
        return None
    if _contains_any(user_message, ("面试题", "题目", "问题")):
        return "questions"
    if _contains_any(user_message, ("jd", "岗位", "职位", "招聘")):
        return "jd"
    if _contains_any(user_message, ("简历", "候选人", "画像")):
        return "resume"
    if _contains_any(user_message, ("匹配", "契合", "差距")):
        return "match"
    if _contains_any(user_message, ("资料", "知识", "参考")):
        return "search"
    return None


def _asks_to_review_existing_content(user_message: str) -> bool:
    return _contains_any(
        user_message,
        (
            "哪里",
            "在哪",
            "在哪儿",
            "给我",
            "展示",
            "列出",
            "看下",
            "看看",
            "刚才",
            "之前",
            "上面",
            "已经",
            "结果",
            "是什么",
        ),
    )


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _read_line(input_func: InputFunc, output: TextIO, prompt: str) -> str | None:
    output.write(prompt)
    output.flush()
    try:
        return input_func("")
    except (EOFError, StopIteration):
        return None


def _parse_direct_node_name(user_message: str) -> str | None:
    if not user_message.startswith("/node"):
        return None

    segments = user_message.split(maxsplit=1)
    if len(segments) != 2:
        return ""
    return segments[1].strip()


def _print_plan(output: TextIO, plan: ExecutionPlan) -> None:
    if len(plan.steps) == 1:
        _write_line(output, _action_statement_for_node(plan.steps[0].node_name))
        return

    _write_line(output, "我会分几步处理：")
    for index, step in enumerate(plan.steps, start=1):
        _write_line(output, f"{index}. {_action_statement_for_node(step.node_name)}")


def _build_step_transition_prompt(next_node_name: str) -> str:
    return _action_statement_for_node(next_node_name)


def _build_processing_hint(user_message: str) -> str:
    if _parse_direct_node_name(user_message):
        return "已收到节点执行请求，正在准备执行。"
    if _is_mock_interview_request(user_message):
        return "已收到模拟面试需求，正在整理处理步骤。"
    return "已收到需求，正在分析并整理处理步骤。"


def _node_display_name(node_name: str) -> str:
    display_names = {
        "resume_parse": "简历解析",
        "jd_parse": "JD 解析",
        "jd_match": "JD 匹配",
        "question_generate": "面试题生成",
        "mock_followup": "模拟追问",
        "answer_score": "回答评分",
        "weakness_train": "薄弱点训练",
        "resume_optimize": "简历优化",
        "project_extract": "项目提炼",
        "knowledge_search": "知识检索",
        "session_summary": "会话总结",
    }
    return display_names.get(node_name, node_name)


def _build_next_need_prompt(completed_node_name: str) -> str:
    return _action_question_for_node(completed_node_name, prefix="这一轮已经完成。接下来是否需要我")


def _action_statement_for_node(node_name: str) -> str:
    action_statements = {
        "resume_parse": "我会先读取简历内容，整理候选人画像。",
        "jd_parse": "我会先读取招聘 JD，整理岗位要求。",
        "jd_match": "我会继续把简历和招聘 JD 做匹配分析。",
        "question_generate": "我会继续基于已有简历和 JD 生成面试题。",
        "mock_followup": "我会继续基于你的回答做模拟面试追问。",
        "answer_score": "我会继续给你的回答评分并指出改进点。",
        "weakness_train": "我会继续整理薄弱点训练计划。",
        "resume_optimize": "我会继续给出简历优化建议。",
        "project_extract": "我会继续提取项目经历亮点。",
        "knowledge_search": "我会继续查找相关准备资料。",
        "session_summary": "我会继续总结本轮准备内容。",
    }
    return action_statements.get(node_name, "我会继续处理下一步。")


def _action_question_for_node(node_name: str, *, prefix: str) -> str:
    action_questions = {
        "resume_parse": "帮你继续匹配招聘 JD、生成面试题，或者模拟面试",
        "jd_parse": "帮你继续匹配简历、生成针对这份 JD 的面试题，或者规划准备重点",
        "jd_match": "帮你继续生成面试题、优化简历，或者模拟面试追问",
        "question_generate": "帮你继续模拟面试、根据回答追问，或者整理薄弱点训练计划",
        "mock_followup": "帮你继续给回答评分、补充追问，或者整理改进建议",
        "answer_score": "帮你继续整理薄弱点训练计划、生成新题，或者优化回答",
        "weakness_train": "帮你继续生成练习题、模拟面试，或者总结本轮准备计划",
        "resume_optimize": "帮你继续匹配招聘 JD、生成面试题，或者检查简历优化后的表达",
        "project_extract": "帮你继续围绕项目经历生成面试题、模拟追问，或者匹配招聘 JD",
        "knowledge_search": "帮你继续生成面试题、模拟面试，或者查找更具体的准备资料",
        "session_summary": "帮你继续生成下一轮练习计划、补充面试题，或者整理待提升事项",
    }
    action_question = action_questions.get(node_name, "帮你继续处理下一步需求")
    return f"{prefix}{action_question}？"


def _confirm_ambiguous_route(route_result: RouteResult, input_func: InputFunc, output: TextIO) -> bool:
    if route_result.via == "default":
        confirmation_text = _read_line(input_func, output, "我先按“知识检索”处理，是否继续？[y/N]: ")
        return (confirmation_text or "").strip().lower() in {"y", "yes"}
    if len(route_result.candidate_nodes) <= 1:
        return True
    confirmation_text = _read_line(
        input_func,
        output,
        f"检测到多个可能处理方式（{', '.join(route_result.candidate_nodes)}），先按“{route_result.selected_node}”处理，是否继续？[y/N]: ",
    )
    return (confirmation_text or "").strip().lower() in {"y", "yes"}


def _execute_step_with_prompt(
    executor: ExecutorProtocol,
    session_store: SessionStore,
    session_id: str,
    node_name: str,
    input_func: InputFunc,
    output: TextIO,
) -> NodeExecutionResult:
    result = executor.execute_node(session_id=session_id, node_name=node_name, inputs=None)
    while result.status == "missing_inputs":
        provided_inputs = _collect_missing_inputs(
            session_store=session_store,
            session_id=session_id,
            input_names=result.missing_inputs,
            input_func=input_func,
            output=output,
        )
        result = executor.execute_node(session_id=session_id, node_name=node_name, inputs=provided_inputs)
    return result


def _collect_missing_inputs(
    session_store: SessionStore,
    session_id: str,
    input_names: list[str],
    input_func: InputFunc,
    output: TextIO,
) -> dict[str, object]:
    collected_inputs: dict[str, object] = {}
    for input_name in input_names:
        raw_value = _read_line(input_func, output, _input_prompt_for(input_name))
        if raw_value is None:
            raise InputCancelledError("缺少节点输入")
        input_value, source_path = _resolve_input_submission(raw_value)
        if input_name == "candidate_profile" and source_path is not None:
            session_store.set_state(session_id, "resume_text", input_value)
        session_store.set_state(session_id, input_name, input_value)
        collected_inputs[input_name] = input_value
    return collected_inputs


def _resolve_input_submission(raw_value: str) -> tuple[str, Path | None]:
    candidate_path = _extract_file_path(raw_value)
    if candidate_path is None:
        return raw_value, None
    return _read_input_file(candidate_path), candidate_path


def _read_input_file(candidate_path: Path) -> str:
    if candidate_path.suffix.lower() in {".md", ".pdf", ".docx"}:
        return extract_text(candidate_path)
    return candidate_path.read_text(encoding="utf-8")


def _extract_file_path(raw_value: str) -> Path | None:
    direct_path = Path(raw_value.strip())
    if direct_path.is_file():
        return direct_path

    for segment in _PATH_PATTERN.findall(raw_value):
        candidate_path = Path(segment.strip("\"'"))
        if candidate_path.is_file():
            return candidate_path
    return None


_PATH_PATTERN = re.compile(r"(/[^,\s，。；;:：\"'()]+)")


def _input_prompt_for(input_name: str) -> str:
    labels = {
        "resume_text": "简历内容",
        "jd_text": "招聘 JD 内容",
        "candidate_profile": "候选人信息",
        "target_role": "目标岗位",
        "jd_requirements": "岗位要求",
        "question": "面试问题",
        "answer": "候选人回答",
        "rubric": "评分标准",
        "weaknesses": "薄弱点",
        "goal": "训练目标",
        "session_transcript": "本轮沟通内容",
    }
    input_label = labels.get(input_name, "补充信息")
    return f"请输入{input_label}（可直接粘贴文本，或输入文件路径）: "


def _write_result(output: TextIO, result: NodeExecutionResult, node_name: str) -> None:
    if result.status == "success":
        _write_success_output(output, node_name, result.output)
        return
    _write_line(output, "处理失败。")
    if result.error_message:
        _write_line(output, f"错误信息: {result.error_message}")


def _write_success_output(output: TextIO, node_name: str, result_output: dict[str, object]) -> None:
    if node_name == "question_generate":
        questions = result_output.get("questions")
        if isinstance(questions, list) and questions:
            _write_line(output, "我生成了这些面试题：")
            _write_list(output, questions)
        return

    if node_name == "knowledge_search":
        search_results = result_output.get("search_results")
        if isinstance(search_results, list) and search_results:
            _write_line(output, "我找到这些准备资料：")
            _write_list(output, search_results[:3])
        return

    if node_name == "jd_parse":
        requirements = result_output.get("jd_requirements")
        if isinstance(requirements, dict):
            _write_line(output, "我整理出的岗位要求：")
            _write_mapping_summary(output, requirements)
        return

    if node_name == "resume_parse":
        profile = result_output.get("resume_profile")
        if isinstance(profile, dict):
            _write_line(output, "我整理出的简历信息：")
            _write_mapping_summary(output, profile)
        return

    if node_name == "jd_match":
        match_report = result_output.get("match_report")
        if isinstance(match_report, dict):
            _write_line(output, "我整理出的匹配分析：")
            _write_mapping_summary(output, match_report)
        return

    if node_name == "mock_followup":
        followups = result_output.get("followup_questions")
        if isinstance(followups, list) and followups:
            _write_line(output, "我建议继续追问：")
            _write_list(output, followups)
        return

    if node_name == "answer_score":
        score_report = result_output.get("score_report")
        if isinstance(score_report, dict):
            _write_line(output, "我对回答的评分反馈：")
            _write_mapping_summary(output, score_report)
        return

    if node_name == "weakness_train":
        training_plan = result_output.get("training_plan")
        if isinstance(training_plan, dict):
            _write_line(output, "我整理出的薄弱点训练计划：")
            _write_mapping_summary(output, training_plan)
        return

    if node_name == "resume_optimize":
        optimization_advice = result_output.get("optimization_advice")
        if isinstance(optimization_advice, dict):
            _write_line(output, "我给出的简历优化建议：")
            _write_mapping_summary(output, optimization_advice)
        return

    if node_name == "project_extract":
        project_experiences = result_output.get("project_experiences")
        if isinstance(project_experiences, list) and project_experiences:
            _write_line(output, "我提取出的项目经历重点：")
            _write_list(output, project_experiences)
        return

    if node_name == "session_summary":
        summary = result_output.get("summary")
        if isinstance(summary, dict):
            _write_line(output, "我整理出的本轮总结：")
            _write_mapping_summary(output, summary)


def _write_existing_list(
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
    _write_line(output, title)
    _write_list(output, values)
    _write_line(output, next_prompt)
    return True


def _write_existing_mapping(
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
    _write_line(output, title)
    _write_mapping_summary(output, values)
    _write_line(output, next_prompt)
    return True


def _write_existing_text(
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
    _write_line(output, title)
    _write_line(output, _format_output_value(value))
    _write_line(output, next_prompt)
    return True


def _write_list(output: TextIO, items: list[object]) -> None:
    for index, item in enumerate(items, start=1):
        _write_line(output, f"{index}. {_format_output_value(item)}")


def _write_mapping_summary(output: TextIO, values: dict[str, object]) -> None:
    for key, value in list(values.items())[:6]:
        _write_line(output, f"- {_format_output_key(key)}: {_format_output_value(value)}")


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


def _write_line(output: TextIO, message: str) -> None:
    output.write(message + "\n")
    output.flush()


if __name__ == "__main__":
    raise SystemExit(main())
