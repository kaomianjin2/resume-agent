from __future__ import annotations

from collections.abc import Callable
from typing import TextIO

from interview_agent.executor import NodeExecutionResult
from interview_agent.nodes.registry import NodeRegistry, UnknownNodeError
from interview_agent.planner import ExecutionPlan, build_execution_plan
from interview_agent.router import RouteResult
from interview_agent.session import SessionStore

SessionAnswerFunc = Callable[[str, dict[str, object], TextIO], bool]
ProcessingHintFunc = Callable[[str], str]
ParseDirectNodeFunc = Callable[[str], str | None]
SelectNodeFunc = Callable[[RouteResult, NodeRegistry, Callable[[str], str], TextIO], str]
PrintPlanFunc = Callable[[TextIO, ExecutionPlan], None]
ExecuteStepFunc = Callable[[object, SessionStore, str, str, Callable[[str], str], TextIO], NodeExecutionResult]
WriteResultFunc = Callable[[TextIO, NodeExecutionResult, str], None]
PromptBuilderFunc = Callable[[str], str]
RouteFunc = Callable[[str, NodeRegistry, object | None], RouteResult]


def run_user_request(
    *,
    normalized_message: str,
    executor: object,
    session_store: SessionStore,
    session_id: str,
    registry: NodeRegistry,
    llm_client: object | None,
    route_func: RouteFunc,
    input_func: Callable[[str], str],
    output: TextIO,
    answer_from_session_if_possible: SessionAnswerFunc,
    build_processing_hint: ProcessingHintFunc,
    parse_direct_node_name: ParseDirectNodeFunc,
    select_node_for_route: SelectNodeFunc,
    print_plan: PrintPlanFunc,
    execute_step_with_prompt: ExecuteStepFunc,
    write_result: WriteResultFunc,
    build_step_transition_prompt: PromptBuilderFunc,
    build_next_need_prompt: PromptBuilderFunc,
    write_line: Callable[[TextIO, str], None],
) -> None:
    session_inputs = session_store.get_all_state(session_id)
    if answer_from_session_if_possible(normalized_message, session_inputs, output):
        return

    write_line(output, build_processing_hint(normalized_message))

    selected_node = _resolve_selected_node(
        normalized_message=normalized_message,
        registry=registry,
        llm_client=llm_client,
        route_func=route_func,
        input_func=input_func,
        output=output,
        parse_direct_node_name=parse_direct_node_name,
        select_node_for_route=select_node_for_route,
        write_line=write_line,
    )
    if selected_node is None:
        return

    try:
        plan = build_execution_plan(
            user_message=normalized_message,
            selected_node=selected_node,
            session_inputs=session_inputs,
            registry=registry,
        )
    except UnknownNodeError:
        write_line(output, "暂不支持这个处理方式，请换一种说法描述你的需求。")
        return
    print_plan(output, plan)

    for step_index, step in enumerate(plan.steps):
        write_line(
            output,
            f"当前进度 {step_index + 1}/{len(plan.steps)}：正在执行{_node_display_name(step.node_name)}。",
        )
        result = execute_step_with_prompt(
            executor,
            session_store,
            session_id,
            step.node_name,
            input_func,
            output,
        )
        write_result(output, result, step.node_name)
        if result.status != "success":
            write_line(output, "请根据错误信息调整输入后继续输入下一步需求，或输入 exit 退出。")
            return
        if step_index < len(plan.steps) - 1:
            write_line(output, build_step_transition_prompt(plan.steps[step_index + 1].node_name))
            continue
        write_line(output, build_next_need_prompt(step.node_name))


def _resolve_selected_node(
    *,
    normalized_message: str,
    registry: NodeRegistry,
    llm_client: object | None,
    route_func: RouteFunc,
    input_func: Callable[[str], str],
    output: TextIO,
    parse_direct_node_name: ParseDirectNodeFunc,
    select_node_for_route: SelectNodeFunc,
    write_line: Callable[[TextIO, str], None],
) -> str | None:
    direct_node_name = parse_direct_node_name(normalized_message)
    if direct_node_name is not None:
        if not direct_node_name:
            write_line(output, "处理方式不能为空，请输入具体需求。")
            return None
        if direct_node_name not in registry.list_names():
            write_line(output, "暂不支持这个处理方式，请换一种说法描述你的需求。")
            return None
        return direct_node_name

    route_result = route_func(normalized_message, registry, llm_client)
    return select_node_for_route(route_result, registry, input_func, output)


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
