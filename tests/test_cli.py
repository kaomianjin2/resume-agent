from __future__ import annotations

from collections.abc import Callable
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

import pytest

from interview_agent import cli
from interview_agent.config import LLMConfig
from interview_agent.kb.embedding import FakeEmbedder
from interview_agent.kb.retrieval import SQLiteHybridRetriever
from interview_agent.llm import OpenAICompatibleClient
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
    assert "已收到需求，正在分析并整理处理步骤。" in output.getvalue()
    assert "当前进度 1/1：正在执行知识检索。" in output.getvalue()
    assert "我会继续查找相关准备资料。" in output.getvalue()
    assert "这一轮已经完成。接下来是否需要我帮你继续生成面试题、模拟面试，或者查找更具体的准备资料？" in output.getvalue()
    assert "匹配节点" not in output.getvalue()
    assert "候选节点" not in output.getvalue()
    assert "knowledge_search" not in output.getvalue()
    assert "执行结果: success" not in output.getvalue()


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
        input_func=build_input(["生成面试题", str(jd_file), "exit"]),
        output=output,
        registry_builder=build_cli_registry,
        route_func=lambda user_message, registry, llm_client=None: cli.RouteResult(
            selected_node="question_generate",
            candidate_nodes=["question_generate"],
            via="rule",
        ),
    )

    assert exit_code == 0
    assert "已收到需求，正在分析并整理处理步骤。" in output.getvalue()
    assert "当前进度 1/2：正在执行JD 解析。" in output.getvalue()
    assert "当前进度 2/2：正在执行面试题生成。" in output.getvalue()
    assert "我会分几步处理：" in output.getvalue()
    assert "请输入招聘 JD 内容" in output.getvalue()
    assert "我会继续基于已有简历和 JD 生成面试题。" in output.getvalue()
    assert "我生成了这些面试题：" in output.getvalue()
    assert "Alice:后端工程师:JD:负责 Go 服务开发" in output.getvalue()
    assert "这一轮已经完成。接下来是否需要我帮你继续模拟面试、根据回答追问，或者整理薄弱点训练计划？" in output.getvalue()
    assert "执行计划" not in output.getvalue()
    assert "jd_parse" not in output.getvalue()
    assert "question_generate" not in output.getvalue()
    assert "继续执行下一个节点" not in output.getvalue()
    assert session_store.get_state(DEFAULT_SESSION_ID, "jd_text") == "负责 Go 服务开发"
    assert session_store.get_state(DEFAULT_SESSION_ID, "jd_requirements") == {
        "role": "JD:负责 Go 服务开发"
    }
    assert session_store.get_state(DEFAULT_SESSION_ID, "questions") == [
        "Alice:后端工程师:JD:负责 Go 服务开发"
    ]


def test_existing_questions_are_shown_when_user_asks_where_they_are(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    session_store.set_state(DEFAULT_SESSION_ID, "questions", ["解释 Go 调度器", "如何排查线上延迟"])
    output = StringIO()
    calls: list[str] = []

    def spy_executor_factory(
        database_path: Path,
        registry: NodeRegistry,
        services: dict[str, object],
    ) -> object:
        del database_path, registry, services

        class SpyExecutor:
            def execute_node(
                self,
                session_id: str,
                node_name: str,
                inputs: dict[str, object] | None = None,
            ) -> cli.NodeExecutionResult:
                del session_id, inputs
                calls.append(node_name)
                return cli.NodeExecutionResult(
                    run_id="run-id",
                    session_id=DEFAULT_SESSION_ID,
                    node_name=node_name,
                    status="success",
                    output={},
                    missing_inputs=[],
                )

        return SpyExecutor()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["面试题在哪里", "exit"]),
        output=output,
        executor_factory=spy_executor_factory,
    )

    assert exit_code == 0
    assert "刚才生成的面试题在这里：" in output.getvalue()
    assert "解释 Go 调度器" in output.getvalue()
    assert "如何排查线上延迟" in output.getvalue()
    assert calls == []


def test_existing_jd_summary_is_shown_when_user_asks_for_previous_result(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    session_store.set_state(
        DEFAULT_SESSION_ID,
        "jd_requirements",
        {"role": "Go 后端工程师", "skills": ["Go", "微服务"]},
    )
    output = StringIO()
    calls: list[str] = []

    def spy_executor_factory(
        database_path: Path,
        registry: NodeRegistry,
        services: dict[str, object],
    ) -> object:
        del database_path, registry, services

        class SpyExecutor:
            def execute_node(
                self,
                session_id: str,
                node_name: str,
                inputs: dict[str, object] | None = None,
            ) -> cli.NodeExecutionResult:
                del session_id, inputs
                calls.append(node_name)
                return cli.NodeExecutionResult(
                    run_id="run-id",
                    session_id=DEFAULT_SESSION_ID,
                    node_name=node_name,
                    status="success",
                    output={},
                    missing_inputs=[],
                )

        return SpyExecutor()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["刚才的岗位要求是什么", "exit"]),
        output=output,
        executor_factory=spy_executor_factory,
    )

    assert exit_code == 0
    assert "我已经整理出的岗位要求：" in output.getvalue()
    assert "- 岗位: Go 后端工程师" in output.getvalue()
    assert "- 技能: Go、微服务" in output.getvalue()
    assert "jd_parse" not in output.getvalue()
    assert calls == []


def test_existing_resume_summary_is_shown_when_user_asks_to_see_resume(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    session_store.set_state(
        DEFAULT_SESSION_ID,
        "candidate_profile",
        {"name": "Alice", "role": "Golang 工程师", "strengths": ["高并发", "排障"]},
    )
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["给我看看简历信息", "exit"]),
        output=output,
        registry_builder=build_cli_registry,
    )

    assert exit_code == 0
    assert "我已经整理出的简历信息：" in output.getvalue()
    assert "- 姓名: Alice" in output.getvalue()
    assert "- 岗位: Golang 工程师" in output.getvalue()
    assert "- 优势: 高并发、排障" in output.getvalue()
    assert "resume_parse" not in output.getvalue()


def test_missing_jd_input_accepts_docx_file_path(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    session_store.set_state(DEFAULT_SESSION_ID, "candidate_profile", {"name": "Alice"})
    session_store.set_state(DEFAULT_SESSION_ID, "target_role", "后端工程师")
    jd_file = tmp_path / "jd.docx"
    write_docx_fixture(jd_file, "负责 Go 服务开发")
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["生成面试题", str(jd_file), "exit"]),
        output=output,
        registry_builder=build_cli_registry,
        route_func=lambda user_message, registry, llm_client=None: cli.RouteResult(
            selected_node="question_generate",
            candidate_nodes=["question_generate"],
            via="rule",
        ),
    )

    assert exit_code == 0
    assert "我会分几步处理：" in output.getvalue()
    assert "执行结果: success" not in output.getvalue()
    assert session_store.get_state(DEFAULT_SESSION_ID, "jd_text") == "负责 Go 服务开发"


def test_multi_node_plan_executes_without_confirmation(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    session_store.set_state(DEFAULT_SESSION_ID, "candidate_profile", {"name": "Alice"})
    session_store.set_state(DEFAULT_SESSION_ID, "target_role", "后端工程师")
    output = StringIO()
    calls: list[tuple[str, dict[str, object] | None]] = []

    def spy_executor_factory(
        database_path: Path,
        registry: NodeRegistry,
        services: dict[str, object],
    ) -> object:
        del database_path, registry, services

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
        input_func=build_input(["生成面试题", "exit"]),
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
    assert "我会分几步处理：" in output.getvalue()
    assert "确认这样处理？" not in output.getvalue()
    assert "当前进度 1/2：正在执行JD 解析。" in output.getvalue()
    assert "当前进度 2/2：正在执行面试题生成。" in output.getvalue()
    assert [call[0] for call in calls] == ["jd_parse", "question_generate"]


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
    assert "我会继续基于已有简历和 JD 生成面试题。" in output.getvalue()
    assert "指定节点" not in output.getvalue()
    assert "question_generate" not in output.getvalue()
    assert session_store.get_state(DEFAULT_SESSION_ID, "questions") == [
        "Alice:后端工程师:后端 JD"
    ]


def test_mock_interview_generates_questions_then_asks_each_question_and_followup(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    session_store.set_state(DEFAULT_SESSION_ID, "candidate_profile", {"name": "Alice"})
    session_store.set_state(DEFAULT_SESSION_ID, "target_role", "后端工程师")
    session_store.set_state(DEFAULT_SESSION_ID, "jd_requirements", {"role": "后端 JD"})
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["开始模拟面试", "回答一", "追问回答", "回答二", "exit"]),
        output=output,
        registry_builder=build_mock_interview_registry,
    )

    assert exit_code == 0
    assert "我会先生成一组层层递进的面试题，然后逐题开始模拟面试。" in output.getvalue()
    assert "第 1 题：介绍你最近一次线上延迟排查。" in output.getvalue()
    assert "追问 1：你如何判断瓶颈在数据库？" in output.getvalue()
    assert "第 2 题：如果延迟再次出现，你会如何设计预防机制？" in output.getvalue()
    assert "模拟面试已完成。" in output.getvalue()


def test_mock_interview_executes_without_confirmation(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    session_store.set_state(DEFAULT_SESSION_ID, "candidate_profile", {"name": "Alice"})
    session_store.set_state(DEFAULT_SESSION_ID, "target_role", "后端工程师")
    session_store.set_state(DEFAULT_SESSION_ID, "jd_requirements", {"role": "后端 JD"})
    output = StringIO()
    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["开始模拟面试", "回答一", "追问回答", "回答二", "exit"]),
        output=output,
        registry_builder=build_mock_interview_registry,
    )

    assert exit_code == 0
    assert "我会分几步处理：" in output.getvalue()
    assert "确认这样处理？" not in output.getvalue()
    assert "第 1 题：介绍你最近一次线上延迟排查。" in output.getvalue()
    assert "模拟面试已完成。" in output.getvalue()


def test_mock_interview_handles_empty_generated_questions(tmp_path: Path) -> None:
    _, config_path = prepare_ready_runtime(tmp_path)
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["开始模拟面试", "exit"]),
        output=output,
        registry_builder=build_empty_question_registry,
    )

    assert exit_code == 0
    assert "还没有生成可用于模拟面试的问题。" in output.getvalue()


def test_mock_interview_retries_question_generate_after_jd_parse_when_first_try_is_empty(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    session_store.set_state(DEFAULT_SESSION_ID, "candidate_profile", {"name": "Alice"})
    session_store.set_state(DEFAULT_SESSION_ID, "target_role", "后端工程师")
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["开始模拟面试", "负责 Go 服务开发", "候选人回答", "exit"]),
        output=output,
        registry_builder=build_retry_mock_interview_registry,
    )

    assert exit_code == 0
    assert "首轮未生成题目，我会先补齐岗位信息后再试一次。" in output.getvalue()
    assert "第 1 题：请介绍你最近一次 Go 服务性能优化。" in output.getvalue()
    assert "模拟面试已完成。" in output.getvalue()
    assert session_store.get_state(DEFAULT_SESSION_ID, "jd_requirements") == {"role": "JD:负责 Go 服务开发"}


def test_mock_interview_retries_question_generate_after_resume_parse_when_first_try_is_empty(tmp_path: Path) -> None:
    _, config_path = prepare_ready_runtime(tmp_path)
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(
            [
                "开始模拟面试",
                "Alice 有 6 年 Go 后端经验",
                "后端工程师",
                "Alice 有 6 年 Go 后端经验",
                "候选人回答",
                "exit",
            ]
        ),
        output=output,
        registry_builder=build_mock_interview_resume_retry_registry,
    )

    assert exit_code == 0
    assert "首轮未生成题目，我会先补齐候选人信息后再试一次。" in output.getvalue()
    assert "第 1 题：Alice:后端工程师" in output.getvalue()
    assert "模拟面试已完成。" in output.getvalue()


def test_mock_interview_reads_file_path_embedded_in_sentence_for_missing_profile(tmp_path: Path) -> None:
    _, config_path = prepare_ready_runtime(tmp_path)
    resume_file = tmp_path / "resume.txt"
    resume_file.write_text("Alice，有 6 年 Go 后端经验", encoding="utf-8")
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(
            [
                "开始模拟面试",
                f"根据{resume_file}，帮我模拟面试",
                "后端工程师",
                "候选人回答",
                "exit",
            ]
        ),
        output=output,
        registry_builder=build_mock_interview_profile_text_registry,
    )

    assert exit_code == 0
    assert "第 1 题：请介绍你最近一次 Go 服务优化经验。" in output.getvalue()
    assert "模拟面试已完成。" in output.getvalue()


def test_mock_interview_reuses_resume_text_from_docx_sentence_when_retrying_resume_parse(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    resume_file = tmp_path / "resume.docx"
    write_docx_fixture(resume_file, "Alice，有 6 年 Go 后端经验")
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(
            [
                "开始模拟面试",
                f"根据{resume_file}，帮我模拟面试",
                "后端工程师",
                "候选人回答",
                "exit",
            ]
        ),
        output=output,
        registry_builder=build_mock_interview_docx_resume_retry_registry,
    )

    assert exit_code == 0
    assert "首轮未生成题目，我会先补齐候选人信息后再试一次。" in output.getvalue()
    assert "还没有生成可用于模拟面试的问题。" not in output.getvalue()
    assert "第 1 题：Alice:后端工程师" in output.getvalue()
    assert "请输入简历内容" not in output.getvalue()
    assert session_store.get_state(DEFAULT_SESSION_ID, "resume_text") == "Alice，有 6 年 Go 后端经验"
    assert "模拟面试已完成。" in output.getvalue()


def test_default_registry_and_executor_execute_real_handler_with_fake_openai_transport(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["/node jd_parse", "负责 Go 服务开发", "exit"]),
        output=output,
        llm_factory=lambda llm_config: OpenAICompatibleClient(
            llm_config,
            transport=build_fake_transport(
                {
                    "JD 内容：负责 Go 服务开发": {
                        "jd_requirements": {"role": "Go 后端工程师"}
                    }
                }
            ),
        ),
    )

    assert exit_code == 0
    assert "我会先读取招聘 JD，整理岗位要求。" in output.getvalue()
    assert "指定节点" not in output.getvalue()
    assert "jd_parse" not in output.getvalue()
    assert SessionStore(database_path).get_state(DEFAULT_SESSION_ID, "jd_requirements") == {
        "role": "Go 后端工程师"
    }


def test_llm_route_receives_client_on_default_cli_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, config_path = prepare_ready_runtime(tmp_path)
    output = StringIO()
    route_llm_client: OpenAICompatibleClient | None = None
    factory_llm_client: OpenAICompatibleClient | None = None

    monkeypatch.setattr(
        "interview_agent.kb.retrieval.build_embedder",
        lambda embedding_config: FakeEmbedder(vocabulary=("go", "资料")),
    )

    def llm_factory(llm_config: LLMConfig) -> OpenAICompatibleClient:
        nonlocal factory_llm_client
        factory_llm_client = OpenAICompatibleClient(
            llm_config,
            transport=build_fake_transport(
                {"问题：帮我找资料": {"search_results": ["命中"]}}
            ),
        )
        return factory_llm_client

    def route_func(
        user_message: str,
        registry: NodeRegistry,
        llm_client: OpenAICompatibleClient | None = None,
    ) -> cli.RouteResult:
        del user_message, registry
        nonlocal route_llm_client
        route_llm_client = llm_client
        return cli.RouteResult(
            selected_node="knowledge_search",
            candidate_nodes=["knowledge_search"],
            via="llm",
        )

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["帮我找资料", "给我 Go 资料", "exit"]),
        output=output,
        llm_factory=llm_factory,
        route_func=route_func,
    )

    assert exit_code == 0
    assert route_llm_client is factory_llm_client
    assert "执行结果: success" not in output.getvalue()


def test_default_cli_services_include_retriever_for_executor(tmp_path: Path) -> None:
    _, config_path = prepare_ready_runtime(tmp_path)
    output = StringIO()
    captured_services: dict[str, object] = {}

    def executor_factory(
        database_path: Path,
        registry: NodeRegistry,
        services: dict[str, object],
    ) -> object:
        del database_path, registry
        captured_services.update(services)

        class ExitExecutor:
            def execute_node(
                self,
                session_id: str,
                node_name: str,
                inputs: dict[str, object] | None = None,
            ) -> cli.NodeExecutionResult:
                del node_name, inputs
                return cli.NodeExecutionResult(
                    run_id="run-id",
                    session_id=session_id,
                    node_name="knowledge_search",
                    status="success",
                    output={"search_results": []},
                    missing_inputs=[],
                )

        return ExitExecutor()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["帮我找资料", "exit"]),
        output=output,
        executor_factory=executor_factory,
        route_func=lambda user_message, registry, llm_client=None: cli.RouteResult(
            selected_node="knowledge_search",
            candidate_nodes=["knowledge_search"],
            via="rule",
        ),
    )

    assert exit_code == 0
    assert "llm" in captured_services
    assert "retriever" in captured_services
    assert isinstance(captured_services["retriever"], SQLiteHybridRetriever)


def test_default_cli_does_not_build_embedder_on_startup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, config_path = prepare_ready_runtime(tmp_path)
    output = StringIO()

    def fail_build_embedder(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("CLI 启动阶段不应加载 embedder")

    monkeypatch.setattr("interview_agent.kb.retrieval.build_embedder", fail_build_embedder)

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["exit"]),
        output=output,
    )

    assert exit_code == 0
    assert "已退出。" in output.getvalue()


def test_direct_node_command_with_empty_name_prints_friendly_error_and_continues(tmp_path: Path) -> None:
    _, config_path = prepare_ready_runtime(tmp_path)
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["/node", "exit"]),
        output=output,
        registry_builder=build_cli_registry,
    )

    assert exit_code == 0
    assert "处理方式不能为空，请输入具体需求。" in output.getvalue()
    assert "节点" not in output.getvalue()
    assert "已退出。" in output.getvalue()


def test_direct_node_command_with_unknown_name_prints_friendly_error_and_continues(tmp_path: Path) -> None:
    _, config_path = prepare_ready_runtime(tmp_path)
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["/node unknown_node", "exit"]),
        output=output,
        registry_builder=build_cli_registry,
    )

    assert exit_code == 0
    assert "暂不支持这个处理方式，请换一种说法描述你的需求。" in output.getvalue()
    assert "unknown_node" not in output.getvalue()
    assert "未知节点" not in output.getvalue()
    assert "已退出。" in output.getvalue()


def test_missing_input_eof_cancels_current_execution_without_traceback(tmp_path: Path) -> None:
    database_path, config_path = prepare_ready_runtime(tmp_path)
    session_store = SessionStore(database_path)
    session_store.set_state(DEFAULT_SESSION_ID, "candidate_profile", {"name": "Alice"})
    session_store.set_state(DEFAULT_SESSION_ID, "target_role", "后端工程师")
    output = StringIO()

    exit_code = cli.main(
        ["--config", str(config_path)],
        input_func=build_input(["生成面试题"]),
        output=output,
        registry_builder=build_cli_registry,
        route_func=lambda user_message, registry, llm_client=None: cli.RouteResult(
            selected_node="question_generate",
            candidate_nodes=["question_generate"],
            via="rule",
        ),
    )

    assert exit_code == 0
    assert "输入结束，已取消当前执行。" in output.getvalue()
    assert session_store.get_state(DEFAULT_SESSION_ID, "jd_text") is None


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
            NodeSpec(
                name="mock_followup",
                description="follow up",
                required_inputs=("question", "answer"),
                optional_inputs=(),
                outputs=("followup_questions",),
                handler=mock_followup_handler,
            ),
        ]
    )


def build_empty_question_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="question_generate",
                description="generate empty questions",
                required_inputs=(),
                optional_inputs=(),
                outputs=("questions",),
                handler=empty_question_generate_handler,
            ),
            NodeSpec(
                name="mock_followup",
                description="follow up",
                required_inputs=("question", "answer"),
                optional_inputs=(),
                outputs=("followup_questions",),
                handler=mock_followup_handler,
            ),
        ]
    )


def build_mock_interview_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="question_generate",
                description="generate progressive questions",
                required_inputs=("candidate_profile", "target_role"),
                optional_inputs=("jd_requirements",),
                outputs=("questions",),
                handler=mock_interview_question_generate_handler,
            ),
            NodeSpec(
                name="mock_followup",
                description="follow up",
                required_inputs=("question", "answer"),
                optional_inputs=(),
                outputs=("followup_questions",),
                handler=mock_followup_handler,
            ),
        ]
    )


def build_retry_mock_interview_registry() -> NodeRegistry:
    call_counts = {"question_generate": 0}

    def retry_question_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
        del context
        call_counts["question_generate"] += 1
        if call_counts["question_generate"] == 1:
            return {"questions": []}
        requirements = inputs.get("jd_requirements")
        assert isinstance(requirements, dict)
        return {"questions": ["请介绍你最近一次 Go 服务性能优化。"]}

    return NodeRegistry(
        [
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
                description="generate questions with retry",
                required_inputs=("candidate_profile", "target_role"),
                optional_inputs=("jd_requirements",),
                outputs=("questions",),
                handler=retry_question_handler,
            ),
            NodeSpec(
                name="mock_followup",
                description="follow up",
                required_inputs=("question", "answer"),
                optional_inputs=(),
                outputs=("followup_questions",),
                handler=mock_followup_handler,
            ),
        ]
    )


def build_mock_interview_retry_registry() -> NodeRegistry:
    return NodeRegistry(
        [
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
                handler=question_generate_requires_jd_context_handler,
            ),
        ]
    )


def build_mock_interview_resume_retry_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="resume_parse",
                description="parse resume",
                required_inputs=("resume_text",),
                optional_inputs=(),
                outputs=("candidate_profile",),
                handler=resume_parse_handler,
            ),
            NodeSpec(
                name="question_generate",
                description="generate question",
                required_inputs=("candidate_profile", "target_role"),
                optional_inputs=(),
                outputs=("questions",),
                handler=question_generate_requires_profile_handler,
            ),
            NodeSpec(
                name="mock_followup",
                description="follow up",
                required_inputs=("question", "answer"),
                optional_inputs=(),
                outputs=("followup_questions",),
                handler=mock_followup_handler,
            ),
        ]
    )


def build_mock_interview_profile_text_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="question_generate",
                description="generate question from profile text",
                required_inputs=("candidate_profile", "target_role"),
                optional_inputs=(),
                outputs=("questions",),
                handler=question_generate_from_profile_text_handler,
            ),
            NodeSpec(
                name="mock_followup",
                description="follow up",
                required_inputs=("question", "answer"),
                optional_inputs=(),
                outputs=("followup_questions",),
                handler=mock_followup_handler,
            ),
        ]
    )


def build_mock_interview_docx_resume_retry_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="resume_parse",
                description="parse resume",
                required_inputs=("resume_text",),
                optional_inputs=(),
                outputs=("candidate_profile",),
                handler=resume_parse_handler,
            ),
            NodeSpec(
                name="question_generate",
                description="generate question after resume retry",
                required_inputs=("candidate_profile", "target_role"),
                optional_inputs=(),
                outputs=("questions",),
                handler=question_generate_requires_alice_profile_handler,
            ),
            NodeSpec(
                name="mock_followup",
                description="follow up",
                required_inputs=("question", "answer"),
                optional_inputs=(),
                outputs=("followup_questions",),
                handler=mock_followup_handler,
            ),
        ]
    )


def knowledge_search_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    return {"search_results": ["ok"]}


def jd_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    return {"jd_requirements": {"role": f"JD:{inputs['jd_text']}"}}


def resume_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    if "Alice" in inputs["resume_text"]:
        return {"candidate_profile": {"name": "Alice"}}
    return {"candidate_profile": {"name": "Unknown"}}


def question_generate_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    profile = inputs["candidate_profile"]
    assert isinstance(profile, dict)
    requirements = inputs.get("jd_requirements", {})
    assert isinstance(requirements, dict)
    return {
        "questions": [
            f"{profile['name']}:{inputs['target_role']}:{requirements.get('role', 'NO_JD')}",
        ]
    }


def question_generate_requires_jd_context_handler(
    context: NodeContext,
    inputs: dict[str, object],
) -> dict[str, object]:
    del context
    profile = inputs["candidate_profile"]
    assert isinstance(profile, dict)
    requirements = inputs.get("jd_requirements")
    if not isinstance(requirements, dict) or "role" not in requirements:
        return {"questions": []}
    return {
        "questions": [
            f"{profile['name']}:{inputs['target_role']}:{requirements['role']}"
        ]
    }


def question_generate_requires_profile_handler(
    context: NodeContext,
    inputs: dict[str, object],
) -> dict[str, object]:
    del context
    profile = inputs["candidate_profile"]
    if not isinstance(profile, dict):
        return {"questions": []}
    name = profile.get("name")
    if not isinstance(name, str) or not name:
        return {"questions": []}
    return {"questions": [f"{name}:{inputs['target_role']}"]}


def question_generate_from_profile_text_handler(
    context: NodeContext,
    inputs: dict[str, object],
) -> dict[str, object]:
    del context
    profile = inputs["candidate_profile"]
    if isinstance(profile, str) and "Alice" in profile:
        return {"questions": ["请介绍你最近一次 Go 服务优化经验。"]}
    return {"questions": []}


def question_generate_requires_alice_profile_handler(
    context: NodeContext,
    inputs: dict[str, object],
) -> dict[str, object]:
    del context
    profile = inputs["candidate_profile"]
    if not isinstance(profile, dict):
        return {"questions": []}
    if profile.get("name") != "Alice":
        return {"questions": []}
    return {"questions": [f"Alice:{inputs['target_role']}"]}


def mock_interview_question_generate_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    return {
        "questions": [
            "介绍你最近一次线上延迟排查。",
            "如果延迟再次出现，你会如何设计预防机制？",
        ]
    }


def empty_question_generate_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    return {"questions": []}


def mock_followup_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    if inputs["question"] == "介绍你最近一次线上延迟排查。":
        return {"followup_questions": ["你如何判断瓶颈在数据库？"]}
    return {"followup_questions": []}


def build_fake_transport(responses: dict[str, dict[str, object]]) -> Callable[[urllib.request.Request], str]:
    def transport(request: urllib.request.Request) -> str:
        request_body = json.loads(request.data.decode("utf-8"))
        messages = request_body["messages"]
        prompt = messages[-1]["content"]
        for marker, payload in responses.items():
            if marker in prompt:
                return build_openai_response(payload)
        return build_openai_response({"search_results": []})

    return transport


def build_openai_response(content_payload: dict[str, object]) -> str:
    return json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(content_payload, ensure_ascii=False)
                    }
                }
            ]
        },
        ensure_ascii=False,
    )


def write_docx_fixture(path: Path, text: str) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""",
        )
        archive.writestr(
            "word/document.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>
""",
        )
