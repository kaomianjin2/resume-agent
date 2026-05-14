from __future__ import annotations

from collections.abc import Callable
from io import StringIO
from pathlib import Path
import sqlite3

from interview_agent import cli
from interview_agent.nodes.registry import NodeRegistry
from interview_agent.nodes.spec import NodeContext, NodeSpec
from interview_agent.session import SessionStore
from interview_agent.storage import initialize_database, set_knowledge_base_status


DEFAULT_SESSION_ID = "interactive-cli-session"


def test_e2e_cli_generates_questions_after_resume_and_jd_backfill(tmp_path: Path) -> None:
    database_path, config_path = prepare_runtime(tmp_path, knowledge_base_ready=True)
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(
            [
                "生成面试题",
                "Alice 有 6 年 Go 后端经验",
                "负责 Go 服务开发",
                "后端工程师",
                "exit",
            ]
        ),
        output=output,
        registry_builder=build_e2e_registry,
        route_func=lambda user_message, registry, llm_client=None: cli.RouteResult(
            selected_node="question_generate",
            candidate_nodes=["question_generate"],
            via="rule",
            needs_user_choice=False,
        ),
    )

    session_store = SessionStore(database_path)
    output_text = output.getvalue()
    assert exit_code == 0
    assert "当前进度 1/3：正在执行简历解析。" in output_text
    assert "当前进度 2/3：正在执行JD 解析。" in output_text
    assert "当前进度 3/3：正在执行面试题生成。" in output_text
    assert "我生成了这些面试题：" in output_text
    assert "Alice:后端工程师:JD:负责 Go 服务开发" in output_text
    assert "resume_parse" not in output_text
    assert "jd_parse" not in output_text
    assert "question_generate" not in output_text
    assert session_store.get_state(DEFAULT_SESSION_ID, "candidate_profile") == {"name": "Alice"}
    assert session_store.get_state(DEFAULT_SESSION_ID, "jd_requirements") == {
        "role": "JD:负责 Go 服务开发"
    }
    assert session_store.get_state(DEFAULT_SESSION_ID, "questions") == [
        "Alice:后端工程师:JD:负责 Go 服务开发"
    ]


def test_e2e_ambiguous_route_only_shows_user_facing_directions(tmp_path: Path) -> None:
    database_path, config_path = prepare_runtime(tmp_path, knowledge_base_ready=True)
    SessionStore(database_path).set_state(DEFAULT_SESSION_ID, "session_transcript", "已生成题目并完成一轮练习")
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["整理一下", "2", "exit"]),
        output=output,
        registry_builder=build_ambiguous_registry,
        route_func=lambda user_message, registry, llm_client=None: cli.RouteResult(
            selected_node="resume_optimize",
            candidate_nodes=["resume_optimize", "session_summary"],
            via="llm",
            needs_user_choice=True,
        ),
    )

    output_text = output.getvalue()
    assert exit_code == 0
    assert "我识别到几种处理方向，请选择一个继续：" in output_text
    assert "1. 给出简历优化建议" in output_text
    assert "2. 总结本轮准备内容" in output_text
    assert "请输入序号: " in output_text
    assert "我整理出的本轮总结：" in output_text
    assert "resume_optimize" not in output_text
    assert "session_summary" not in output_text
    assert "执行计划" not in output_text


def test_e2e_knowledge_base_not_ready_exits_before_executor_initialization(tmp_path: Path) -> None:
    _, config_path = prepare_runtime(tmp_path, knowledge_base_ready=False)
    output = StringIO()
    executor_factory_called = False

    def fail_executor_factory(
        database_path: Path,
        registry: NodeRegistry,
        services: dict[str, object],
    ) -> object:
        del database_path, registry, services
        nonlocal executor_factory_called
        executor_factory_called = True
        raise AssertionError("KB 未 ready 时不应初始化执行器")

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["exit"]),
        output=output,
        registry_builder=build_e2e_registry,
        executor_factory=fail_executor_factory,
    )

    output_text = output.getvalue()
    assert exit_code == 1
    assert executor_factory_called is False
    assert "知识库未就绪，请先执行离线构建：" in output_text
    assert "uv run python -m interview_agent.kb.build" in output_text
    assert "请输入需求" not in output_text


def test_e2e_failure_recovery_records_failed_run_without_overwriting_state(tmp_path: Path) -> None:
    database_path, config_path = prepare_runtime(tmp_path, knowledge_base_ready=True)
    session_store = SessionStore(database_path)
    session_store.set_state(DEFAULT_SESSION_ID, "candidate_profile", {"name": "Alice"})
    session_store.set_state(DEFAULT_SESSION_ID, "target_role", "后端工程师")
    session_store.set_state(DEFAULT_SESSION_ID, "jd_requirements", {"role": "既有 JD"})
    session_store.set_state(DEFAULT_SESSION_ID, "questions", ["既有题目"])
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["生成面试题", "exit"]),
        output=output,
        registry_builder=build_failure_registry,
        route_func=lambda user_message, registry, llm_client=None: cli.RouteResult(
            selected_node="question_generate",
            candidate_nodes=["question_generate"],
            via="rule",
            needs_user_choice=False,
        ),
    )

    assert exit_code == 0
    assert "处理失败。" in output.getvalue()
    assert "错误信息: 模拟节点失败" in output.getvalue()
    assert session_store.get_state(DEFAULT_SESSION_ID, "questions") == ["既有题目"]
    assert read_node_runs(database_path) == [("question_generate", "failed", None, "模拟节点失败")]


def prepare_runtime(tmp_path: Path, *, knowledge_base_ready: bool) -> tuple[Path, Path]:
    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    if knowledge_base_ready:
        set_knowledge_base_status(database_path, "ready")
    return database_path, write_config(tmp_path, database_path)


def write_config(tmp_path: Path, database_path: Path) -> Path:
    config_path = tmp_path / "interview-agent.toml"
    config_path.write_text(
        "\n".join(
            [
                "[llm]",
                'base_url = "https://example.test/v1"',
                'api_key = "test-key"',
                'model = "fake-model"',
                "",
                "[embedding]",
                'provider = "local"',
                'model_name = "fake-embedding"',
                'model_path = "./models/fake"',
                "",
                "[storage]",
                f'database_path = "{database_path.as_posix()}"',
                "",
                "[knowledge_base]",
                f'source = "{tmp_path.as_posix()}"',
                "chunk_size = 900",
                "chunk_overlap = 120",
                "top_k = 8",
                'index_version = "v1"',
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def build_input(values: list[str]) -> Callable[[str], str]:
    remaining_values = iter(values)

    def input_func(prompt: str) -> str:
        del prompt
        return next(remaining_values)

    return input_func


def build_e2e_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="resume_parse",
                description="parse resume",
                required_inputs=("resume_text",),
                optional_inputs=(),
                outputs=("resume_profile", "candidate_profile"),
                handler=resume_parse_handler,
            ),
            NodeSpec(
                name="jd_parse",
                description="parse jd",
                required_inputs=("jd_text",),
                optional_inputs=(),
                outputs=("jd_requirements",),
                handler=jd_parse_handler,
            ),
            NodeSpec(
                name="question_generate",
                description="generate question",
                required_inputs=("candidate_profile", "target_role"),
                optional_inputs=("jd_requirements",),
                outputs=("questions",),
                handler=question_generate_handler,
            ),
        ]
    )


def build_ambiguous_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="resume_optimize",
                description="optimize resume",
                required_inputs=("resume_text", "target_role"),
                optional_inputs=(),
                outputs=("optimization_advice",),
                handler=resume_optimize_handler,
            ),
            NodeSpec(
                name="session_summary",
                description="summarize session",
                required_inputs=("session_transcript",),
                optional_inputs=(),
                outputs=("summary",),
                handler=session_summary_handler,
            ),
        ]
    )


def build_failure_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="question_generate",
                description="generate question",
                required_inputs=("candidate_profile", "target_role"),
                optional_inputs=(),
                outputs=("questions",),
                handler=failing_question_generate_handler,
            ),
        ]
    )


def resume_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    resume_text = str(inputs["resume_text"])
    name = "Alice" if "Alice" in resume_text else "Unknown"
    return {
        "resume_profile": {"name": name},
        "candidate_profile": {"name": name},
    }


def jd_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    return {"jd_requirements": {"role": f"JD:{inputs['jd_text']}"}}


def question_generate_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    candidate_profile = inputs["candidate_profile"]
    jd_requirements = inputs["jd_requirements"]
    assert isinstance(candidate_profile, dict)
    assert isinstance(jd_requirements, dict)
    return {
        "questions": [
            f"{candidate_profile['name']}:{inputs['target_role']}:{jd_requirements['role']}"
        ]
    }


def resume_optimize_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    return {"optimization_advice": {"summary": "建议突出 Go 服务经验"}}


def session_summary_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    return {"summary": {"summary": f"总结：{inputs['session_transcript']}"}}


def failing_question_generate_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    raise RuntimeError("模拟节点失败")


def read_node_runs(database_path: Path) -> list[tuple[str, str, str | None, str | None]]:
    with sqlite3.connect(database_path) as connection:
        return [
            (row[0], row[1], row[2], row[3])
            for row in connection.execute(
                "SELECT node_name, status, output_payload, error_message FROM node_runs ORDER BY started_at"
            ).fetchall()
        ]
