from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import re
from typing import NoReturn, Protocol, TextIO

from interview_agent.executor import NodeExecutionResult
from interview_agent.kb.parser import extract_text
from interview_agent.planner import ExecutionPlan, PlanStep
from interview_agent.session import SessionStore


DEFAULT_MOCK_INTERVIEW_QUESTION_COUNT = 6
DEFAULT_MOCK_FOLLOWUP_ROUNDS = 6
InputFunc = Callable[[str], str]
ExecuteStepFunc = Callable[[object, SessionStore, str, str, InputFunc, TextIO], NodeExecutionResult]
WriteResultFunc = Callable[[TextIO, NodeExecutionResult, str], None]
ReadLineFunc = Callable[[InputFunc, TextIO, str], str | None]
WriteLineFunc = Callable[[TextIO, str], None]
PromptBuilderFunc = Callable[[str], str]
InputCancelledFunc = Callable[[str], NoReturn]


class ExecutorProtocol(Protocol):
    def execute_node(
        self,
        session_id: str,
        node_name: str,
        inputs: dict[str, object] | None = None,
    ) -> NodeExecutionResult: ...


class MockInterviewInterruptedError(RuntimeError):
    """Raised when the user intentionally stops the mock interview."""


def is_mock_interview_request(user_message: str) -> bool:
    return _contains_any(user_message.lower(), ("模拟面试", "mock interview"))


def build_mock_interview_plan(user_message: str) -> ExecutionPlan:
    steps = [
        _build_step("question_generate"),
        _build_step("mock_followup"),
    ]
    return ExecutionPlan(
        plan_id="mock_interview",
        user_message=user_message,
        steps=steps,
        requires_confirmation=False,
        missing_inputs=[],
        summary="question_generate -> mock_followup",
    )


def seed_mock_interview_inputs_from_request(
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


def run_mock_interview(
    *,
    executor: ExecutorProtocol,
    session_store: SessionStore,
    session_id: str,
    input_func: InputFunc,
    output: TextIO,
    available_node_names: set[str],
    execute_step_with_prompt: ExecuteStepFunc,
    write_result: WriteResultFunc,
    read_line: ReadLineFunc,
    write_line: WriteLineFunc,
    build_next_need_prompt: PromptBuilderFunc,
    raise_input_cancelled: InputCancelledFunc,
) -> None:
    write_line(output, "我会先生成一组层层递进的面试题，然后逐题开始模拟面试。")
    write_line(output, "模拟面试中可输入 /stop 中断当前面试。")
    question_count = _collect_mock_interview_question_count(
        session_store=session_store,
        session_id=session_id,
        input_func=input_func,
        output=output,
        read_line=read_line,
        write_line=write_line,
        raise_input_cancelled=raise_input_cancelled,
    )
    followup_rounds = _collect_mock_followup_rounds(
        session_store=session_store,
        session_id=session_id,
        input_func=input_func,
        output=output,
        read_line=read_line,
        write_line=write_line,
        raise_input_cancelled=raise_input_cancelled,
    )
    question_result = execute_step_with_prompt(
        executor,
        session_store,
        session_id,
        "question_generate",
        input_func,
        output,
    )
    if question_result.status != "success":
        write_result(output, question_result, "question_generate")
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
            execute_step_with_prompt=execute_step_with_prompt,
            write_result=write_result,
            write_line=write_line,
        )
    if not questions:
        write_line(output, "还没有生成可用于模拟面试的问题。")
        return
    questions = questions[:question_count]

    for question_index, question in enumerate(questions, start=1):
        answer = _ask_interview_question(
            output,
            input_func,
            f"第 {question_index} 题：{question}",
            read_line=read_line,
            raise_input_cancelled=raise_input_cancelled,
        )
        _offer_reference_answer_if_needed(
            executor=executor,
            session_id=session_id,
            question=question,
            answer=answer,
            input_func=input_func,
            output=output,
            available_node_names=available_node_names,
            read_line=read_line,
            write_line=write_line,
            raise_input_cancelled=raise_input_cancelled,
        )
        _ask_followup_questions(
            executor=executor,
            session_id=session_id,
            question=question,
            answer=answer,
            input_func=input_func,
            output=output,
            available_node_names=available_node_names,
            followup_rounds=followup_rounds,
            write_result=write_result,
            read_line=read_line,
            write_line=write_line,
            raise_input_cancelled=raise_input_cancelled,
        )
    write_line(output, "模拟面试已完成。")
    write_line(output, build_next_need_prompt("mock_followup"))


def build_interview_prompt(output: TextIO, prompt: str) -> str:
    interviewer_label = _style_terminal_text(output, "[面试官]", "1;36")
    candidate_label = _style_terminal_text(output, "[候选人]", "1;32")
    return f"{interviewer_label} {prompt}\n{candidate_label} 你的回答: "


def _build_step(node_name: str) -> PlanStep:
    return PlanStep(
        node_name=node_name,
        title=node_name.replace("_", " ").title(),
        description=_action_statement_for_node(node_name),
    )


def _collect_mock_interview_question_count(
    session_store: SessionStore,
    session_id: str,
    input_func: InputFunc,
    output: TextIO,
    read_line: ReadLineFunc,
    write_line: WriteLineFunc,
    raise_input_cancelled: InputCancelledFunc,
) -> int:
    while True:
        raw_count = read_line(
            input_func,
            output,
            f"请输入本轮模拟面试题目数，直接回车默认 {DEFAULT_MOCK_INTERVIEW_QUESTION_COUNT} 题: ",
        )
        if raw_count is None:
            raise_input_cancelled("缺少模拟面试题目数")
        question_count = _parse_positive_count(raw_count, DEFAULT_MOCK_INTERVIEW_QUESTION_COUNT)
        if question_count is None:
            write_line(output, "题目数必须是正整数，请重新输入。")
            continue
        session_store.set_state(session_id, "question_count", question_count)
        return question_count


def _collect_mock_followup_rounds(
    session_store: SessionStore,
    session_id: str,
    input_func: InputFunc,
    output: TextIO,
    read_line: ReadLineFunc,
    write_line: WriteLineFunc,
    raise_input_cancelled: InputCancelledFunc,
) -> int:
    while True:
        raw_rounds = read_line(
            input_func,
            output,
            f"请输入每题追问轮数，直接回车默认 {DEFAULT_MOCK_FOLLOWUP_ROUNDS} 轮: ",
        )
        if raw_rounds is None:
            raise_input_cancelled("缺少模拟面试追问轮数")
        followup_rounds = _parse_positive_count(raw_rounds, DEFAULT_MOCK_FOLLOWUP_ROUNDS)
        if followup_rounds is None:
            write_line(output, "追问轮数必须是正整数，请重新输入。")
            continue
        session_store.set_state(session_id, "followup_rounds", followup_rounds)
        return followup_rounds


def _parse_positive_count(raw_count: str, default_count: int) -> int | None:
    stripped_count = raw_count.strip()
    if not stripped_count:
        return default_count
    if not stripped_count.isdecimal():
        return None
    parsed_count = int(stripped_count)
    if parsed_count <= 0:
        return None
    return parsed_count


def _retry_mock_interview_questions(
    executor: ExecutorProtocol,
    session_store: SessionStore,
    session_id: str,
    input_func: InputFunc,
    output: TextIO,
    available_node_names: set[str],
    execute_step_with_prompt: ExecuteStepFunc,
    write_result: WriteResultFunc,
    write_line: WriteLineFunc,
) -> list[str]:
    session_inputs = session_store.get_all_state(session_id)
    if _needs_candidate_profile_backfill(session_inputs):
        if "resume_parse" not in available_node_names:
            return []
        write_line(output, "首轮未生成题目，我会先补齐候选人信息后再试一次。")
        resume_parse_result = execute_step_with_prompt(
            executor,
            session_store,
            session_id,
            "resume_parse",
            input_func,
            output,
        )
        if resume_parse_result.status != "success":
            write_result(output, resume_parse_result, "resume_parse")
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
                execute_step_with_prompt=execute_step_with_prompt,
                write_result=write_result,
            )
        write_line(output, "首轮未生成题目，我会先补齐岗位信息后再试一次。")
        jd_parse_result = execute_step_with_prompt(
            executor,
            session_store,
            session_id,
            "jd_parse",
            input_func,
            output,
        )
        if jd_parse_result.status != "success":
            write_result(output, jd_parse_result, "jd_parse")
            return []

    return _retry_question_generate(
        executor=executor,
        session_store=session_store,
        session_id=session_id,
        input_func=input_func,
        output=output,
        execute_step_with_prompt=execute_step_with_prompt,
        write_result=write_result,
    )


def _retry_question_generate(
    executor: ExecutorProtocol,
    session_store: SessionStore,
    session_id: str,
    input_func: InputFunc,
    output: TextIO,
    execute_step_with_prompt: ExecuteStepFunc,
    write_result: WriteResultFunc,
) -> list[str]:
    retry_result = execute_step_with_prompt(
        executor,
        session_store,
        session_id,
        "question_generate",
        input_func,
        output,
    )
    if retry_result.status != "success":
        write_result(output, retry_result, "question_generate")
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
    available_node_names: set[str],
    followup_rounds: int,
    write_result: WriteResultFunc,
    read_line: ReadLineFunc,
    write_line: WriteLineFunc,
    raise_input_cancelled: InputCancelledFunc,
) -> None:
    followup_result = executor.execute_node(
        session_id=session_id,
        node_name="mock_followup",
        inputs={"question": question, "answer": answer},
    )
    if followup_result.status != "success":
        write_result(output, followup_result, "mock_followup")
        return

    followup_questions = _read_text_list(followup_result.output.get("followup_questions"))[:followup_rounds]
    for followup_index, followup_question in enumerate(followup_questions, start=1):
        followup_answer = _ask_interview_question(
            output,
            input_func,
            f"追问 {followup_index}：{followup_question}",
            read_line=read_line,
            raise_input_cancelled=raise_input_cancelled,
        )
        _offer_reference_answer_if_needed(
            executor=executor,
            session_id=session_id,
            question=followup_question,
            answer=followup_answer,
            input_func=input_func,
            output=output,
            available_node_names=available_node_names,
            read_line=read_line,
            write_line=write_line,
            raise_input_cancelled=raise_input_cancelled,
        )


def _offer_reference_answer_if_needed(
    executor: ExecutorProtocol,
    session_id: str,
    question: str,
    answer: str,
    input_func: InputFunc,
    output: TextIO,
    available_node_names: set[str],
    read_line: ReadLineFunc,
    write_line: WriteLineFunc,
    raise_input_cancelled: InputCancelledFunc,
) -> None:
    reference_answer = _build_blank_answer_reference(question, answer)
    prompt = "这个回答还没有展开。是否需要我给出完整答案或答题方案？[y/N]: "
    if reference_answer is None:
        if "answer_score" not in available_node_names:
            return
        score_report = _score_interview_answer(executor, session_id, question, answer)
        if score_report is None or not _needs_reference_answer(score_report):
            return
        reference_answer = _build_scored_reference(score_report)
        prompt = "这个回答还不够完整。是否需要我给出完整答案或答题方案？[y/N]: "

    confirmation_text = read_line(input_func, output, prompt)
    if confirmation_text is None:
        raise_input_cancelled("缺少参考答案确认")
    if not _is_affirmative(confirmation_text):
        return
    _write_reference_answer(output, reference_answer, write_line)


def _build_blank_answer_reference(question: str, answer: str) -> list[str] | None:
    del question
    if answer.strip():
        return None
    return [
        "先正面回答问题，再结合项目背景说明关键动作。",
        "补充可量化结果，例如耗时、指标变化、影响范围。",
        "最后说明复盘结论和后续改进。",
    ]


def _score_interview_answer(
    executor: ExecutorProtocol,
    session_id: str,
    question: str,
    answer: str,
) -> dict[str, object] | None:
    score_result = executor.execute_node(
        session_id=session_id,
        node_name="answer_score",
        inputs={
            "question": question,
            "answer": answer,
            "rubric": "按完整性、准确性、结构化表达和项目细节评分，指出缺口，并给出 reference_answer。",
        },
    )
    if score_result.status != "success":
        return None
    score_report = score_result.output.get("score_report")
    if isinstance(score_report, dict):
        return score_report
    return None


def _needs_reference_answer(score_report: dict[str, object]) -> bool:
    score = score_report.get("score")
    if isinstance(score, int | float) and score < 6:
        return True
    gaps = score_report.get("gaps")
    return isinstance(gaps, list) and bool(gaps)


def _build_scored_reference(score_report: dict[str, object]) -> list[str]:
    reference_answer = score_report.get("reference_answer")
    reference_items = _read_text_list(reference_answer)
    if reference_items:
        return reference_items
    suggestions = _read_text_list(score_report.get("suggestions"))
    if suggestions:
        return suggestions
    return [
        "先给出结论，再说明关键判断依据。",
        "结合项目场景补充做法、指标和取舍。",
        "最后说明结果验证和复盘改进。",
    ]


def _write_reference_answer(
    output: TextIO,
    reference_answer: list[str],
    write_line: WriteLineFunc,
) -> None:
    write_line(output, "参考答案/方案：")
    for item in reference_answer:
        write_line(output, f"- {item}")


def _is_affirmative(value: str) -> bool:
    return value.strip().lower() in {"y", "yes", "需要", "要", "好的", "好"}


def _ask_interview_question(
    output: TextIO,
    input_func: InputFunc,
    prompt: str,
    read_line: ReadLineFunc,
    raise_input_cancelled: InputCancelledFunc,
) -> str:
    answer = read_line(input_func, output, build_interview_prompt(output, prompt))
    if answer is None:
        raise_input_cancelled("缺少候选人回答")
    if _is_mock_interview_interrupt(answer):
        raise MockInterviewInterruptedError("用户中断模拟面试")
    return answer


def _is_mock_interview_interrupt(answer: str) -> bool:
    return answer.strip().lower() in {
        "/stop",
        "stop",
        "中断",
        "中断模拟面试",
        "结束模拟面试",
        "取消模拟面试",
        "退出模拟面试",
    }


def _style_terminal_text(output: TextIO, text: str, style_code: str) -> str:
    is_terminal = getattr(output, "isatty", lambda: False)()
    if not is_terminal:
        return text
    return f"\033[{style_code}m{text}\033[0m"


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


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _action_statement_for_node(node_name: str) -> str:
    action_statements = {
        "question_generate": "我会继续基于已有简历和 JD 生成面试题。",
        "mock_followup": "我会继续基于你的回答做模拟面试追问。",
    }
    return action_statements.get(node_name, "我会继续处理下一步。")


_PATH_PATTERN = re.compile(r"(/[^,\s，。；;:：\"'()]+)")
