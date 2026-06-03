from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Protocol, TextIO

from interview_agent.config import DEFAULT_CONFIG_PATH, ConfigError, LLMConfig, load_config
from interview_agent.executor import NodeExecutionResult, NodeExecutor
from interview_agent.kb.retrieval import SQLiteHybridRetriever
from interview_agent.kb.parser import extract_text
from interview_agent.llm import FakeLLMClient, OpenAICompatibleClient
from interview_agent.mock_interview import (
    MockInterviewInterruptedError,
    build_interview_prompt,
    build_mock_interview_plan,
    is_mock_interview_request,
    run_mock_interview,
    seed_mock_interview_inputs_from_request,
)
from interview_agent.nodes.registry import NodeRegistry, build_default_registry
from interview_agent.orchestrator import run_user_request
from interview_agent.planner import ExecutionPlan
from interview_agent import rendering
from interview_agent.router import RouteResult, route_conversation
from interview_agent.session import SessionStore
from interview_agent.storage import (
    create_user,
    get_knowledge_base_status,
    list_users,
    set_user_status,
    verify_login,
)


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


@dataclass(frozen=True)
class CodeRunResult:
    language: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool


def _raise_input_cancelled(message: str) -> None:
    raise InputCancelledError(message)


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
        "retriever": SQLiteHybridRetriever(
            database_path,
            config.embedding,
            default_limit=config.knowledge_base.top_k,
        ),
    }
    executor = (executor_factory or _default_executor_factory)(database_path, registry, services)

    _enable_terminal_line_editing(input_func, output_stream)
    _write_line(output_stream, "请输入需求，输入 exit 退出。")
    current_user: dict[str, str] | None = None
    try:
        while True:
            user_message = _read_line(input_func, output_stream, "> ")
            if user_message is None:
                _write_line(output_stream, "输入结束，已退出。")
                return 0

            normalized_message = user_message.strip()
            if not normalized_message:
                continue
            if normalized_message in {"exit", "quit", "/exit", "退出"}:
                _write_line(output_stream, "已退出。")
                return 0

            command_result = _handle_user_command(
                normalized_message=normalized_message,
                database_path=database_path,
                output=output_stream,
                current_user=current_user,
            )
            if command_result is not None:
                current_user = command_result
                continue

            if is_mock_interview_request(normalized_message):
                session_inputs = session_store.get_all_state(session_id)
                if _answer_from_session_if_possible(normalized_message, session_inputs, output_stream):
                    continue
                _write_line(output_stream, _build_processing_hint(normalized_message))
                seed_mock_interview_inputs_from_request(
                    session_store=session_store,
                    session_id=session_id,
                    user_message=normalized_message,
                )
                mock_interview_plan = build_mock_interview_plan(normalized_message)
                _print_plan(output_stream, mock_interview_plan)
                try:
                    run_mock_interview(
                        executor=executor,
                        session_store=session_store,
                        session_id=session_id,
                        input_func=input_func,
                        output=output_stream,
                        available_node_names=set(registry.list_names()),
                        execute_step_with_prompt=_execute_step_with_prompt,
                        write_result=_write_result,
                        read_line=_read_line,
                        write_line=_write_line,
                        build_next_need_prompt=_build_next_need_prompt,
                        raise_input_cancelled=_raise_input_cancelled,
                    )
                except InputCancelledError:
                    _write_line(output_stream, "输入结束，已取消当前模拟面试。")
                except MockInterviewInterruptedError:
                    _write_line(output_stream, "已中断当前模拟面试。你可以继续输入新的需求，或输入 exit 退出。")
                continue

            if _is_algorithm_practice_request(normalized_message):
                _write_line(output_stream, _build_processing_hint(normalized_message))
                try:
                    _run_algorithm_practice(
                        executor=executor,
                        session_id=session_id,
                        input_func=input_func,
                        output=output_stream,
                    )
                except InputCancelledError:
                    _write_line(output_stream, "输入结束，已取消当前执行。")
                continue

            try:
                run_user_request(
                    normalized_message=normalized_message,
                    executor=executor,
                    session_store=session_store,
                    session_id=session_id,
                    registry=registry,
                    llm_client=llm_client,
                    route_func=route_func,
                    input_func=input_func,
                    output=output_stream,
                    answer_from_session_if_possible=_answer_from_session_if_possible,
                    build_processing_hint=_build_processing_hint,
                    parse_direct_node_name=_parse_direct_node_name,
                    select_node_for_route=_select_node_for_route,
                    print_plan=_print_plan,
                    execute_step_with_prompt=_execute_step_with_prompt,
                    write_result=_write_result,
                    build_step_transition_prompt=_build_step_transition_prompt,
                    build_next_need_prompt=_build_next_need_prompt,
                    write_line=_write_line,
                )
            except InputCancelledError:
                _write_line(output_stream, "输入结束，已取消当前执行。")
    except KeyboardInterrupt:
        _write_line(output_stream, "\n已退出。")
        return 0


def _handle_user_command(
    *,
    normalized_message: str,
    database_path: Path,
    output: TextIO,
    current_user: dict[str, str] | None,
) -> dict[str, str] | None:
    if normalized_message.startswith("/user "):
        command_segments = normalized_message.split()
        if len(command_segments) < 2:
            _write_line(output, "用法: /user list|add|enable|disable ...")
            return current_user
        action = command_segments[1]
        if action == "list":
            users = list_users(database_path)
            if not users:
                _write_line(output, "当前没有用户。")
                return current_user
            for index, user_info in enumerate(users, start=1):
                _write_line(
                    output,
                    f"{index}. {user_info['username']} | 角色: {user_info['role']} | 状态: {user_info['status']}",
                )
            return current_user
        if action == "add":
            if len(command_segments) != 5:
                _write_line(output, "用法: /user add <username> <password> <admin|member>")
                return current_user
            _, _, username, password, role = command_segments
            try:
                created_user = create_user(
                    database_path,
                    username=username,
                    password=password,
                    role=role,
                )
            except (ValueError, Exception) as error:
                _write_line(output, f"创建用户失败: {error}")
                return current_user
            _write_line(output, f"用户已创建: {created_user['username']} ({created_user['role']})")
            return current_user
        if action in {"enable", "disable"}:
            if len(command_segments) != 3:
                _write_line(output, "用法: /user enable|disable <username>")
                return current_user
            username = command_segments[2]
            updated = set_user_status(
                database_path,
                username=username,
                status="enabled" if action == "enable" else "disabled",
            )
            if not updated:
                _write_line(output, "未找到该用户。")
                return current_user
            _write_line(output, f"用户状态已更新: {username} -> {'enabled' if action == 'enable' else 'disabled'}")
            if current_user and current_user.get("username") == username and action == "disable":
                _write_line(output, "当前登录用户已被禁用，已自动退出登录。")
                return None
            return current_user
        _write_line(output, "未知用户命令。用法: /user list|add|enable|disable ...")
        return current_user

    if normalized_message.startswith("/login "):
        command_segments = normalized_message.split()
        if len(command_segments) != 3:
            _write_line(output, "用法: /login <username> <password>")
            return current_user
        _, username, password = command_segments
        user_info = verify_login(database_path, username=username, password=password)
        if user_info is None:
            _write_line(output, "登录失败：用户名或密码错误，或用户已禁用。")
            return current_user
        _write_line(output, f"登录成功：{user_info['username']} ({user_info['role']})")
        return user_info

    if normalized_message == "/logout":
        if current_user is None:
            _write_line(output, "当前未登录。")
            return current_user
        _write_line(output, f"已退出登录：{current_user['username']}")
        return None

    return None


def _default_executor_factory(
    database_path: Path,
    registry: NodeRegistry,
    services: ServiceMap,
) -> NodeExecutor:
    return NodeExecutor(database_path, registry, services=dict(services))


def _enable_terminal_line_editing(input_func: InputFunc, output: TextIO) -> None:
    if input_func is not input:
        return
    if not sys.stdin.isatty():
        return
    if not getattr(output, "isatty", lambda: False)():
        return
    try:
        import readline  # noqa: F401
    except ImportError:
        return


def _build_offline_command(config_path: Path, database_path: Path, source_path: Path) -> str:
    return (
        "uv run python -m interview_agent.kb.build "
        f"--source {source_path} --config {config_path} --db {database_path}"
    )


def _build_interview_prompt(output: TextIO, prompt: str) -> str:
    return build_interview_prompt(output, prompt)


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

    if requested_content == "practice":
        if _write_existing_mapping(
            output=output,
            session_inputs=session_inputs,
            key="practice_set",
            title="刚才生成的练习内容在这里：",
            next_prompt=_build_next_need_prompt("algorithm_practice"),
        ):
            return True
        _write_line(output, "我还没有生成算法和数据结构练习。你可以告诉我想练习的主题、难度或题目数量。")
        return True

    return False


def _requested_existing_content(user_message: str) -> str | None:
    if not _asks_to_review_existing_content(user_message):
        return None
    if _contains_any(user_message, ("算法", "数据结构", "刷题", "练习")):
        return "practice"
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


def _is_algorithm_practice_request(user_message: str) -> bool:
    normalized_message = user_message.lower()
    return _contains_any(
        normalized_message,
        ("算法练习", "数据结构练习", "开始算法", "开始刷题", "刷题", "链表练习", "动态规划练习"),
    )


def _run_algorithm_practice(
    *,
    executor: ExecutorProtocol,
    session_id: str,
    input_func: InputFunc,
    output: TextIO,
) -> None:
    _write_line(output, "我会先生成一组算法和数据结构练习，然后逐题运行完整程序并检查结果。")
    practice_result = executor.execute_node(session_id=session_id, node_name="algorithm_practice", inputs=None)
    if practice_result.status != "success":
        _write_result(output, practice_result, "algorithm_practice")
        return

    exercises = _read_practice_exercises(practice_result.output.get("practice_set"))
    if not exercises:
        _write_line(output, "还没有生成可用于练习的题目。")
        return

    for exercise_index, exercise in enumerate(exercises, start=1):
        title = _read_practice_text(exercise, "title", f"练习题 {exercise_index}")
        prompt = _read_practice_text(exercise, "prompt", "")
        reference_answer = _build_reference_answer(exercise)
        _write_line(output, f"第 {exercise_index} 题：{title}")
        if prompt:
            _write_line(output, prompt)
        language = _read_code_language(input_func, output)
        if language is None:
            raise InputCancelledError("缺少练习回答")
        if not language:
            _write_line(output, "你还没有回答，这道题的参考答案：")
            _write_line(output, reference_answer)
            continue
        source_code = _read_source_code(input_func, output)
        if source_code is None:
            raise InputCancelledError("缺少练习代码")
        if not source_code.strip():
            _write_line(output, "你还没有回答，这道题的参考答案：")
            _write_line(output, reference_answer)
            continue
        safety_issues = _inspect_code_safety(language, source_code)
        if safety_issues:
            _write_code_safety_rejection(output, safety_issues)
            continue
        run_result = _run_code(language, source_code)
        _write_code_run_result(output, run_result)
        review_result = executor.execute_node(
            session_id=session_id,
            node_name="practice_answer_review",
            inputs={
                "practice_question": _join_query_parts(title, prompt),
                "reference_answer": reference_answer,
                "answer": _build_practice_review_answer(source_code, run_result),
            },
        )
        _write_practice_answer_feedback(output, review_result, reference_answer)
    _write_line(output, "算法和数据结构练习已完成。")
    _write_line(output, _build_next_need_prompt("algorithm_practice"))


def _read_practice_exercises(practice_set: object) -> list[dict[str, object]]:
    if not isinstance(practice_set, dict):
        return []
    exercises = practice_set.get("exercises")
    if not isinstance(exercises, list):
        return []
    return [dict(exercise) for exercise in exercises if isinstance(exercise, dict)]


def _read_practice_text(exercise: dict[str, object], key: str, default_value: str) -> str:
    value = exercise.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return default_value


def _build_reference_answer(exercise: dict[str, object]) -> str:
    solution_outline = exercise.get("solution_outline")
    if isinstance(solution_outline, list):
        outline_parts = [str(item).strip() for item in solution_outline if str(item).strip()]
        if outline_parts:
            return " ".join(outline_parts)
    return "这道题暂未生成参考答案。"


def _read_code_language(input_func: InputFunc, output: TextIO) -> str | None:
    _write_line(output, "请选择开发语言：1. Python  2. JavaScript  3. Go  4. Java  5. C  6. C++")
    language_input = _read_line(input_func, output, "语言（直接回车查看答案）: ")
    if language_input is None:
        return None
    if not language_input.strip():
        return ""
    return _normalize_code_language(language_input)


def _normalize_code_language(language_input: str) -> str:
    language_aliases = {
        "1": "python",
        "python": "python",
        "py": "python",
        "2": "javascript",
        "javascript": "javascript",
        "js": "javascript",
        "node": "javascript",
        "3": "go",
        "golang": "go",
        "4": "java",
        "5": "c",
        "6": "cpp",
        "cpp": "cpp",
        "c++": "cpp",
    }
    normalized_input = language_input.strip().lower()
    return language_aliases.get(normalized_input, normalized_input)


def _read_source_code(input_func: InputFunc, output: TextIO) -> str | None:
    _write_line(output, "请粘贴完整程序，最后输入一个空行提交。仅运行可信代码。")
    source_lines: list[str] = []
    while True:
        line = _read_line(input_func, output, "")
        if line is None:
            return None
        if line == "":
            return "\n".join(source_lines)
        source_lines.append(line)


def _inspect_code_safety(language: str, source_code: str) -> list[str]:
    del language
    normalized_source = source_code.lower()
    keyword_rules = (
        (
            "进程或命令执行",
            (
                "subprocess",
                "os.system",
                "popen",
                "execv",
                "processbuilder",
                "runtime.getruntime",
                "child_process",
                "system(",
            ),
        ),
        (
            "网络访问",
            ("socket", "requests", "urllib", "httpclient", "http.get", "fetch(", "xmlhttprequest", "net/http", "java.net"),
        ),
        (
            "环境变量或密钥读取",
            ("os.environ", "os.getenv", "getenv", "process.env", "system.getenv", "openai_api_key", "api_key", "secret", "token"),
        ),
        (
            "文件删除或破坏性文件操作",
            ("os.remove", "os.unlink", "shutil.rmtree", "rm -rf", "remove(", "unlink(", "delete("),
        ),
        (
            "文件写入",
            ("writefile", "createwritestream", "ofstream", "filewriter", "files.write", "os.writefile", "ioutil.writefile"),
        ),
        (
            "绝对路径、家目录或父级目录访问",
            ('"/etc', "'/etc", '"/var', "'/var", '"/tmp', "'/tmp", '"/private', "'/private", '"/users', "'/users", '"/home', "'/home", '"~', "'~", '"..', "'.."),
        ),
        (
            "动态代码执行或反射加载",
            ("eval(", "exec(", "compile(", "function(", "classloader", "reflection", "reflect."),
        ),
    )
    issues: list[str] = []
    for reason, blocked_keywords in keyword_rules:
        if any(blocked_keyword in normalized_source for blocked_keyword in blocked_keywords):
            issues.append(reason)
    if re.search(r"open\s*\([^)]*['\"]w", normalized_source):
        issues.append("文件写入")
    return issues


def _write_code_safety_rejection(output: TextIO, safety_issues: list[str]) -> None:
    _write_line(output, "代码安全检测未通过，已拒绝执行。")
    for safety_issue in safety_issues:
        _write_line(output, f"- {safety_issue}")


def _run_code(language: str, source_code: str, timeout_seconds: int = 5) -> CodeRunResult:
    language_spec = _build_language_spec(language)
    if language_spec is None:
        return CodeRunResult(language=language, exit_code=127, stdout="", stderr="不支持的开发语言。", timed_out=False)
    missing_commands = [command for command in language_spec["commands"] if shutil.which(command) is None]
    if missing_commands:
        return CodeRunResult(
            language=language_spec["label"],
            exit_code=127,
            stdout="",
            stderr="缺少运行命令: " + ", ".join(missing_commands),
            timed_out=False,
        )
    with tempfile.TemporaryDirectory(prefix="interview-agent-code-") as temporary_directory:
        workdir = Path(temporary_directory)
        source_path = workdir / str(language_spec["filename"])
        source_path.write_text(source_code, encoding="utf-8")
        compile_command = language_spec.get("compile_command")
        run_command = list(language_spec["run_command"])
        if isinstance(compile_command, list):
            compile_result = _run_subprocess(compile_command, workdir, timeout_seconds, language_spec["label"])
            if compile_result.exit_code != 0 or compile_result.timed_out:
                return compile_result
        return _run_subprocess(run_command, workdir, timeout_seconds, language_spec["label"])


def _build_language_spec(language: str) -> dict[str, object] | None:
    if language == "python":
        return {"label": "Python", "commands": ["python3"], "filename": "main.py", "run_command": ["python3", "main.py"]}
    if language == "javascript":
        return {"label": "JavaScript", "commands": ["node"], "filename": "main.js", "run_command": ["node", "main.js"]}
    if language == "go":
        return {"label": "Go", "commands": ["go"], "filename": "main.go", "run_command": ["go", "run", "main.go"]}
    if language == "java":
        return {
            "label": "Java",
            "commands": ["javac", "java"],
            "filename": "Main.java",
            "compile_command": ["javac", "Main.java"],
            "run_command": ["java", "Main"],
        }
    if language == "c":
        return {
            "label": "C",
            "commands": ["gcc"],
            "filename": "main.c",
            "compile_command": ["gcc", "main.c", "-o", "main"],
            "run_command": ["./main"],
        }
    if language == "cpp":
        return {
            "label": "C++",
            "commands": ["g++"],
            "filename": "main.cpp",
            "compile_command": ["g++", "main.cpp", "-o", "main"],
            "run_command": ["./main"],
        }
    return None


def _run_subprocess(command: list[str], workdir: Path, timeout_seconds: int, language_label: str) -> CodeRunResult:
    try:
        completed_process = subprocess.run(
            command,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        return CodeRunResult(
            language=language_label,
            exit_code=-1,
            stdout=str(error.output or ""),
            stderr=str(error.stderr or ""),
            timed_out=True,
        )
    return CodeRunResult(
        language=language_label,
        exit_code=completed_process.returncode,
        stdout=completed_process.stdout,
        stderr=completed_process.stderr,
        timed_out=False,
    )


def _write_code_run_result(output: TextIO, run_result: CodeRunResult) -> None:
    _write_line(output, "代码运行结果：")
    _write_line(output, f"语言：{run_result.language}")
    _write_line(output, f"stdout: {run_result.stdout.rstrip()}")
    _write_line(output, f"stderr: {run_result.stderr.rstrip()}")
    _write_line(output, f"退出码：{run_result.exit_code}")
    if run_result.timed_out:
        _write_line(output, "运行状态：超时")


def _build_practice_review_answer(source_code: str, run_result: CodeRunResult) -> str:
    timeout_text = "是" if run_result.timed_out else "否"
    return (
        "用户代码：\n"
        f"{source_code}\n\n"
        "代码运行结果：\n"
        f"语言: {run_result.language}\n"
        f"stdout: {run_result.stdout.rstrip()}\n"
        f"stderr: {run_result.stderr.rstrip()}\n"
        f"退出码: {run_result.exit_code}\n"
        f"是否超时: {timeout_text}"
    )


def _join_query_parts(*parts: str) -> str:
    return " ".join(part.strip() for part in parts if part.strip())


def _write_practice_answer_feedback(
    output: TextIO,
    review_result: NodeExecutionResult,
    fallback_answer: str,
) -> None:
    if review_result.status != "success":
        _write_result(output, review_result, "practice_answer_review")
        return
    feedback = review_result.output.get("practice_answer_feedback")
    if not isinstance(feedback, dict):
        _write_line(output, "回答评审失败。")
        return
    if feedback.get("is_correct") is True:
        _write_line(output, "回答正确。")
        feedback_text = feedback.get("feedback")
        if isinstance(feedback_text, str) and feedback_text.strip():
            _write_line(output, f"反馈：{feedback_text}")
        return

    correct_answer = feedback.get("correct_answer")
    if not isinstance(correct_answer, str) or not correct_answer.strip():
        correct_answer = fallback_answer
    _write_line(output, "回答不正确。")
    feedback_text = feedback.get("feedback")
    if isinstance(feedback_text, str) and feedback_text.strip():
        _write_line(output, f"原因：{feedback_text}")
    _write_line(output, f"正确答案：{correct_answer}")


def _read_line(input_func: InputFunc, output: TextIO, prompt: str) -> str | None:
    output.write(_format_status(output, prompt))
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


def _select_node_for_route(
    route_result: RouteResult,
    registry: NodeRegistry,
    input_func: InputFunc,
    output: TextIO,
) -> str:
    candidate_nodes = _filter_available_candidates(route_result.candidate_nodes, registry)
    if not route_result.needs_user_choice or len(candidate_nodes) <= 1:
        return route_result.selected_node

    _write_line(output, _format_title(output, "我识别到几种处理方向，请选择一个继续："))
    for index, candidate_node in enumerate(candidate_nodes, start=1):
        _write_line(output, f"{_format_index(output, f'{index}.')} {_action_label_for_node(candidate_node)}")

    while True:
        selection = _read_line(input_func, output, "请输入序号: ")
        if selection is None:
            raise InputCancelledError("缺少处理方向选择")
        selected_node = _parse_candidate_selection(selection, candidate_nodes)
        if selected_node is not None:
            return selected_node
        _write_line(output, "请输入列表中的序号。")


def _filter_available_candidates(candidate_nodes: list[str], registry: NodeRegistry) -> list[str]:
    available_nodes = set(registry.list_names())
    filtered_candidates: list[str] = []
    for candidate_node in candidate_nodes:
        if candidate_node not in available_nodes:
            continue
        if candidate_node in filtered_candidates:
            continue
        filtered_candidates.append(candidate_node)
    return filtered_candidates


def _parse_candidate_selection(selection: str, candidate_nodes: list[str]) -> str | None:
    selected_text = selection.strip()
    if not selected_text.isdecimal():
        return None
    selected_index = int(selected_text)
    if selected_index < 1 or selected_index > len(candidate_nodes):
        return None
    return candidate_nodes[selected_index - 1]


def _print_plan(output: TextIO, plan: ExecutionPlan) -> None:
    if len(plan.steps) == 1:
        _write_line(output, _action_statement_for_node(plan.steps[0].node_name))
        return

    _write_line(output, "我会先补齐必要信息，再继续处理。")


def _build_step_transition_prompt(next_node_name: str) -> str:
    return _action_statement_for_node(next_node_name)


def _build_processing_hint(user_message: str) -> str:
    if _parse_direct_node_name(user_message):
        return "已收到请求，我来处理。"
    if is_mock_interview_request(user_message):
        return "已收到模拟面试需求，我来处理。"
    return "已收到需求，我来处理。"


def _build_next_need_prompt(completed_node_name: str) -> str:
    return _action_question_for_node(completed_node_name, prefix="这一轮已经完成。接下来是否需要我")


def _action_statement_for_node(node_name: str) -> str:
    action_statements = {
        "algorithm_practice": "我会继续生成算法和数据结构练习。",
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


def _action_label_for_node(node_name: str) -> str:
    action_labels = {
        "algorithm_practice": "生成算法和数据结构练习",
        "resume_parse": "整理简历信息",
        "jd_parse": "整理岗位要求",
        "jd_match": "分析简历和岗位匹配度",
        "question_generate": "生成面试题",
        "mock_followup": "进行模拟追问",
        "answer_score": "给回答评分并指出改进点",
        "weakness_train": "整理薄弱点训练计划",
        "resume_optimize": "给出简历优化建议",
        "project_extract": "提取项目经历亮点",
        "knowledge_search": "查找相关准备资料",
        "session_summary": "总结本轮准备内容",
    }
    return action_labels.get(node_name, "继续处理下一步")


def _action_question_for_node(node_name: str, *, prefix: str) -> str:
    action_questions = {
        "algorithm_practice": "帮你继续出下一组练习、模拟讲解解法，或者整理薄弱点训练计划",
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
        "practice_topic": "练习主题",
        "practice_question": "练习题目",
        "reference_answer": "参考答案",
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
    rendering.write_result(output, result, node_name)


def _write_success_output(output: TextIO, node_name: str, result_output: dict[str, object]) -> None:
    rendering.write_success_output(output, node_name, result_output)


def _write_existing_list(
    *,
    output: TextIO,
    session_inputs: dict[str, object],
    key: str,
    title: str,
    next_prompt: str,
) -> bool:
    return rendering.write_existing_list(
        output=output,
        session_inputs=session_inputs,
        key=key,
        title=title,
        next_prompt=next_prompt,
    )


def _write_existing_mapping(
    *,
    output: TextIO,
    session_inputs: dict[str, object],
    key: str,
    title: str,
    next_prompt: str,
) -> bool:
    return rendering.write_existing_mapping(
        output=output,
        session_inputs=session_inputs,
        key=key,
        title=title,
        next_prompt=next_prompt,
    )


def _write_existing_text(
    *,
    output: TextIO,
    session_inputs: dict[str, object],
    key: str,
    title: str,
    next_prompt: str,
) -> bool:
    return rendering.write_existing_text(
        output=output,
        session_inputs=session_inputs,
        key=key,
        title=title,
        next_prompt=next_prompt,
    )


def _format_title(output: TextIO, text: str) -> str:
    return rendering.format_title(output, text)


def _format_status(output: TextIO, text: str) -> str:
    return rendering.format_status(output, text)


def _format_key(output: TextIO, text: str) -> str:
    return rendering.format_key(output, text)


def _format_index(output: TextIO, text: str) -> str:
    return rendering.format_index(output, text)


def _format_error(output: TextIO, text: str) -> str:
    return rendering.format_error(output, text)


def _write_line(output: TextIO, message: str) -> None:
    rendering.write_line(output, message)


if __name__ == "__main__":
    raise SystemExit(main())
