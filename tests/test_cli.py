from __future__ import annotations

from collections.abc import Callable
from io import StringIO
from pathlib import Path
import subprocess
import sys

from interview_agent import cli
from interview_agent.nodes.registry import NodeRegistry
from interview_agent.nodes.spec import NodeContext, NodeSpec
from interview_agent.session import SessionStore
from interview_agent.storage import initialize_database, set_knowledge_base_status


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = PROJECT_ROOT / "config" / "interview-agent.toml.example"
DEFAULT_SESSION_ID = "interactive-cli-session"


def run_module_help() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "interview_agent.cli", "--help"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )


def test_module_help_exits_successfully() -> None:
    result = run_module_help()

    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "interview-agent" in result.stdout
    assert "--config" in result.stdout


def test_example_config_exists_with_placeholders_only() -> None:
    content = EXAMPLE_CONFIG.read_text(encoding="utf-8")

    assert 'base_url = "https://your-openai-compatible-endpoint/v1"' in content
    assert 'api_key = "your-key"' in content
    assert 'provider = "your-embedding-provider"' in content
    assert 'database_path = "./path/to/your-database.sqlite"' in content
    assert 'source = "/path/to/your-knowledge-base-source"' in content


def test_startup_only_prints_offline_build_command_when_knowledge_base_not_ready(tmp_path: Path) -> None:
    config_path = write_config(tmp_path, tmp_path / "missing.sqlite3")
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["exit"]),
        output=output,
    )

    assert exit_code == 1
    assert "知识库未就绪" in output.getvalue()
    assert "uv run python -m interview_agent.kb.build" in output.getvalue()
    assert "--config" in output.getvalue()
    assert "--db" in output.getvalue()
    assert "请输入需求" not in output.getvalue()


def test_does_not_build_knowledge_base_on_startup(tmp_path: Path) -> None:
    config_path = write_config(tmp_path, tmp_path / "missing.sqlite3")
    output = StringIO()
    executor_factory_called = False

    def fail_executor_factory(database_path: Path, registry: NodeRegistry) -> object:
        del database_path, registry
        nonlocal executor_factory_called
        executor_factory_called = True
        raise AssertionError("KB 未 ready 时不应初始化执行器")

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["exit"]),
        output=output,
        executor_factory=fail_executor_factory,
    )

    assert exit_code == 1
    assert executor_factory_called is False
    assert "知识库未就绪" in output.getvalue()


def test_interactive_entry_prompts_for_user_input(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["exit"]),
        output=output,
        registry_builder=build_cli_registry,
    )

    assert exit_code == 0
    assert "请输入需求" in output.getvalue()
    assert SessionStore(database_path).get_all_state(DEFAULT_SESSION_ID) == {}


def test_natural_language_request_shows_matched_node(tmp_path: Path) -> None:
    _, config_path = prepare_ready_runtime(tmp_path)
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["帮我找资料", "exit"]),
        output=output,
        registry_builder=build_cli_registry,
        route_func=lambda user_message, registry, llm_client=None: cli.RouteResult(
            selected_node="knowledge_search",
            candidate_nodes=["knowledge_search"],
            via="rule",
        ),
    )

    assert exit_code == 0
    assert "匹配节点: knowledge_search" in output.getvalue()
    assert "执行结果: success" in output.getvalue()


def test_missing_jd_input_accepts_file_path_and_executes_plan(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    session_store.set_state(DEFAULT_SESSION_ID, "candidate_profile", {"name": "Alice"})
    session_store.set_state(DEFAULT_SESSION_ID, "target_role", "后端工程师")
    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("负责 Go 服务开发", encoding="utf-8")
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["生成面试题", "y", str(jd_file), "exit"]),
        output=output,
        registry_builder=build_cli_registry,
        route_func=lambda user_message, registry, llm_client=None: cli.RouteResult(
            selected_node="question_generate",
            candidate_nodes=["question_generate"],
            via="rule",
        ),
    )

    assert exit_code == 0
    assert "执行计划: jd_parse -> question_generate" in output.getvalue()
    assert "请输入 jd_text" in output.getvalue()
    assert session_store.get_state(DEFAULT_SESSION_ID, "jd_text") == "负责 Go 服务开发"
    assert session_store.get_state(DEFAULT_SESSION_ID, "jd_requirements") == {
        "role": "JD:负责 Go 服务开发"
    }
    assert session_store.get_state(DEFAULT_SESSION_ID, "questions") == [
        "Alice:后端工程师:JD:负责 Go 服务开发"
    ]


def test_multi_node_plan_does_not_execute_without_confirmation(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    session_store.set_state(DEFAULT_SESSION_ID, "candidate_profile", {"name": "Alice"})
    session_store.set_state(DEFAULT_SESSION_ID, "target_role", "后端工程师")
    output = StringIO()
    calls: list[tuple[str, dict[str, object] | None]] = []

    def spy_executor_factory(database_path: Path, registry: NodeRegistry) -> object:
        del database_path, registry

        class SpyExecutor:
            def execute_node(
                self,
                session_id: str,
                node_name: str,
                inputs: dict[str, object] | None = None,
            ) -> cli.NodeExecutionResult:
                calls.append((node_name, inputs))
                return cli.NodeExecutionResult(
                    run_id="run-id",
                    session_id=session_id,
                    node_name=node_name,
                    status="success",
                    output={},
                    missing_inputs=[],
                )

        return SpyExecutor()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["生成面试题", "n", "exit"]),
        output=output,
        registry_builder=build_cli_registry,
        executor_factory=spy_executor_factory,
        route_func=lambda user_message, registry, llm_client=None: cli.RouteResult(
            selected_node="question_generate",
            candidate_nodes=["question_generate"],
            via="rule",
        ),
    )

    assert exit_code == 0
    assert "执行计划: jd_parse -> question_generate" in output.getvalue()
    assert "已取消执行计划" in output.getvalue()
    assert calls == []


def test_direct_node_command_executes_selected_node(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    session_store.set_state(DEFAULT_SESSION_ID, "candidate_profile", {"name": "Alice"})
    session_store.set_state(DEFAULT_SESSION_ID, "target_role", "后端工程师")
    session_store.set_state(DEFAULT_SESSION_ID, "jd_requirements", {"role": "后端 JD"})
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["/node question_generate", "exit"]),
        output=output,
        registry_builder=build_cli_registry,
    )

    assert exit_code == 0
    assert "指定节点: question_generate" in output.getvalue()
    assert session_store.get_state(DEFAULT_SESSION_ID, "questions") == [
        "Alice:后端工程师:后端 JD"
    ]


def prepare_ready_runtime(tmp_path: Path) -> tuple[Path, Path]:
    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
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


def build_cli_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="knowledge_search",
                description="search",
                required_inputs=(),
                optional_inputs=(),
                outputs=("search_results",),
                handler=knowledge_search_handler,
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


def knowledge_search_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    return {"search_results": ["ok"]}


def jd_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    return {"jd_requirements": {"role": f"JD:{inputs['jd_text']}"}}


def question_generate_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    profile = inputs["candidate_profile"]
    assert isinstance(profile, dict)
    requirements = inputs.get("jd_requirements", {})
    assert isinstance(requirements, dict)
    return {
        "questions": [
            f"{profile['name']}:{inputs['target_role']}:{requirements.get('role', 'NO_JD')}"
        ]
    }
