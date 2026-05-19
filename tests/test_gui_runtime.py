from __future__ import annotations

from pathlib import Path

import pytest

from interview_agent.nodes.registry import NodeRegistry
from interview_agent.nodes.spec import NodeContext, NodeSpec
from interview_agent.storage import initialize_database, set_knowledge_base_status


def test_load_runtime_reports_config_and_ready_status(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    config_path = write_config(tmp_path, database_path)

    runtime = load_runtime(config_path, registry_builder=build_registry)

    assert runtime.get_status() == {
        "config_path": config_path.as_posix(),
        "database_path": database_path.as_posix(),
        "knowledge_base_status": "ready",
        "ready": True,
    }


def test_load_runtime_rejects_not_ready_knowledge_base(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import GuiRuntimeError, load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    config_path = write_config(tmp_path, database_path)

    with pytest.raises(GuiRuntimeError, match="知识库未就绪"):
        load_runtime(config_path, registry_builder=build_registry)


def test_runtime_facade_routes_plans_executes_and_reads_session_state(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_registry,
        services_builder=build_services,
    )
    session = runtime.create_or_open_session("gui-session")

    route = runtime.route_request("请帮我练习算法")
    plan = runtime.build_plan(
        message="请帮我练习算法",
        selected_node=route["selected_node"],
        session_id=session["session_id"],
    )
    result = runtime.execute_node(
        session_id=session["session_id"],
        node_name=route["selected_node"],
        inputs={"practice_topic": "动态规划"},
    )

    assert session == {"session_id": "gui-session", "status": "active"}
    assert runtime.list_nodes() == ["algorithm_practice", "failing_node", "knowledge_search"]
    assert route == {
        "selected_node": "algorithm_practice",
        "candidate_nodes": ["algorithm_practice"],
        "via": "rule",
        "needs_user_choice": False,
    }
    assert plan["missing_inputs"] == []
    assert plan["steps"] == [
        {
            "node_name": "algorithm_practice",
            "title": "Algorithm Practice",
            "description": "执行节点 algorithm_practice。",
        }
    ]
    assert result["status"] == "success"
    assert result["output"] == {
        "practice_set": {
            "topic": "动态规划",
            "difficulty": "medium",
            "exercises": ["动态规划 exercise"],
        }
    }
    assert runtime.get_session_state("gui-session") == result["output"]


def test_missing_inputs_and_failed_nodes_do_not_write_success_state(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("gui-session")

    missing_result = runtime.execute_node(
        session_id="gui-session",
        node_name="knowledge_search",
        inputs=None,
    )
    failed_result = runtime.execute_node(
        session_id="gui-session",
        node_name="failing_node",
        inputs={"resume_text": "Alice"},
    )

    assert missing_result["status"] == "missing_inputs"
    assert missing_result["missing_inputs"] == ["question"]
    assert failed_result["status"] == "failed"
    assert runtime.get_session_state("gui-session") == {}


def test_runtime_prepares_interview_materials_as_gui_view_model(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("prep-session")

    prep_view_model = runtime.prepare_interview_materials(
        session_id="prep-session",
        resume_text="Alice led Python retrieval services.",
        jd_text="Need Backend engineer with Python, retrieval, and reliability.",
    )

    assert prep_view_model == {
        "session_id": "prep-session",
        "status": "ready",
        "resume_summary": {
            "name": "Alice",
            "headline": "Python 检索服务负责人",
            "highlights": ["Python", "检索系统", "可靠性治理"],
        },
        "jd_summary": {
            "role": "后端工程师",
            "focus": ["Python", "检索链路", "稳定性"],
        },
        "match_summary": {
            "score": 91,
            "strengths": ["Python 服务经验", "检索系统经验"],
            "risks": ["补充压测案例"],
            "follow_up_focus": ["SLA 取舍", "检索召回评估"],
        },
        "missing_inputs": [],
    }
    assert runtime.get_session_state("prep-session") == {
        "candidate_profile": {
            "name": "Alice",
            "headline": "Python 检索服务负责人",
            "skills": ["Python", "检索系统"],
            "highlights": ["Python", "检索系统", "可靠性治理"],
        },
        "jd_requirements": {
            "role": "后端工程师",
            "must_have": ["Python", "检索链路", "稳定性"],
        },
        "match_report": {
            "score": 91,
            "strengths": ["Python 服务经验", "检索系统经验"],
            "risks": ["补充压测案例"],
            "follow_up_focus": ["SLA 取舍", "检索召回评估"],
        },
        "resume_profile": {
            "name": "Alice",
            "headline": "Python 检索服务负责人",
            "skills": ["Python", "检索系统"],
            "highlights": ["Python", "检索系统", "可靠性治理"],
        },
    }


def test_runtime_preparation_reports_missing_inputs_without_writing_state(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("prep-session")

    prep_view_model = runtime.prepare_interview_materials(session_id="prep-session", resume_text="", jd_text="   ")

    assert prep_view_model == {
        "session_id": "prep-session",
        "status": "missing_inputs",
        "resume_summary": {},
        "jd_summary": {},
        "match_summary": {},
        "missing_inputs": ["resume_text", "jd_text"],
    }
    assert runtime.get_session_state("prep-session") == {}


def test_runtime_starts_mock_interview_and_returns_first_question_only(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_mock_runtime_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("mock-session")
    runtime.session_store.set_state("mock-session", "candidate_profile", {"name": "Alice"})

    view_model = runtime.start_mock_interview(
        session_id="mock-session",
        target_role="后端工程师",
        question_count=2,
        followup_rounds=1,
    )

    assert view_model == {
        "session_id": "mock-session",
        "status": "ready_for_answer",
        "error_message": None,
        "current_prompt": {
            "kind": "question",
            "label": "第 1 题",
            "text": "介绍你最近一次线上延迟排查。",
        },
        "progress": {
            "current_question_index": 1,
            "total_questions": 2,
            "current_followup_index": 0,
            "total_followups": 0,
        },
        "review_panel": None,
        "transcript": [],
    }
    assert runtime.get_session_state("mock-session")["mock_interview_view"]["current_prompt"]["text"] == "介绍你最近一次线上延迟排查。"


def test_runtime_start_mock_interview_reports_empty_question_set(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_empty_mock_runtime_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("mock-session")
    runtime.session_store.set_state("mock-session", "candidate_profile", {"name": "Alice"})

    view_model = runtime.start_mock_interview(
        session_id="mock-session",
        target_role="后端工程师",
    )

    assert view_model == {
        "session_id": "mock-session",
        "status": "failed",
        "error_message": "还没有生成可用于模拟面试的问题。",
        "current_prompt": None,
        "progress": {
            "current_question_index": 0,
            "total_questions": 0,
            "current_followup_index": 0,
            "total_followups": 0,
        },
        "review_panel": None,
        "transcript": [],
    }


def test_runtime_submit_mock_answer_requires_non_blank_answer(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_mock_runtime_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("mock-session")
    runtime.session_store.set_state("mock-session", "candidate_profile", {"name": "Alice"})
    runtime.start_mock_interview(
        session_id="mock-session",
        target_role="后端工程师",
        question_count=2,
        followup_rounds=1,
    )

    view_model = runtime.submit_mock_answer(session_id="mock-session", answer="   ")

    assert view_model["status"] == "answer_required"
    assert view_model["error_message"] == "请先输入当前题回答。"
    assert view_model["current_prompt"] == {
        "kind": "question",
        "label": "第 1 题",
        "text": "介绍你最近一次线上延迟排查。",
    }
    assert view_model["transcript"] == []


def test_runtime_submit_mock_answer_generates_followup_and_final_review(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_mock_runtime_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("mock-session")
    runtime.session_store.set_state("mock-session", "candidate_profile", {"name": "Alice"})
    runtime.start_mock_interview(
        session_id="mock-session",
        target_role="后端工程师",
        question_count=2,
        followup_rounds=1,
    )

    followup_view_model = runtime.submit_mock_answer(session_id="mock-session", answer="我会先看核心指标和慢查询。")
    next_question_view_model = runtime.submit_mock_answer(session_id="mock-session", answer="我会对比调用链与数据库监控。")
    completed_view_model = runtime.submit_mock_answer(session_id="mock-session", answer="我会补充熔断和容量预案。")

    assert followup_view_model["status"] == "ready_for_answer"
    assert followup_view_model["current_prompt"] == {
        "kind": "followup",
        "label": "追问 1",
        "text": "你如何判断瓶颈在数据库？",
    }
    assert followup_view_model["progress"] == {
        "current_question_index": 1,
        "total_questions": 2,
        "current_followup_index": 1,
        "total_followups": 1,
    }
    assert next_question_view_model["current_prompt"] == {
        "kind": "question",
        "label": "第 2 题",
        "text": "如果延迟再次出现，你会如何设计预防机制？",
    }
    assert completed_view_model == {
        "session_id": "mock-session",
        "status": "completed",
        "error_message": None,
        "current_prompt": None,
        "progress": {
            "current_question_index": 2,
            "total_questions": 2,
            "current_followup_index": 0,
            "total_followups": 0,
        },
        "review_panel": {
            "average_score": 7.0,
            "risks": ["缺少数据库瓶颈判定证据", "预防方案还不够具体"],
            "suggestions": ["补充监控指标、定位步骤和验证闭环", "说明告警阈值、容量治理和复盘机制"],
        },
        "transcript": [
            {
                "prompt_kind": "question",
                "prompt_text": "介绍你最近一次线上延迟排查。",
                "answer": "我会先看核心指标和慢查询。",
                "score": 8,
            },
            {
                "prompt_kind": "followup",
                "prompt_text": "你如何判断瓶颈在数据库？",
                "answer": "我会对比调用链与数据库监控。",
                "score": 6,
            },
            {
                "prompt_kind": "question",
                "prompt_text": "如果延迟再次出现，你会如何设计预防机制？",
                "answer": "我会补充熔断和容量预案。",
                "score": 7,
            },
        ],
    }


def test_runtime_submit_mock_answer_after_completed_keeps_completed_state(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_mock_runtime_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("mock-session")
    runtime.session_store.set_state("mock-session", "candidate_profile", {"name": "Alice"})
    runtime.start_mock_interview(
        session_id="mock-session",
        target_role="后端工程师",
        question_count=2,
        followup_rounds=1,
    )
    runtime.submit_mock_answer(session_id="mock-session", answer="我会先看核心指标和慢查询。")
    runtime.submit_mock_answer(session_id="mock-session", answer="我会对比调用链与数据库监控。")
    completed_view_model = runtime.submit_mock_answer(session_id="mock-session", answer="我会补充熔断和容量预案。")

    repeated_submit_view_model = runtime.submit_mock_answer(session_id="mock-session", answer="完成后追加的回答")

    assert repeated_submit_view_model == completed_view_model
    assert len(repeated_submit_view_model["transcript"]) == 3
    assert runtime.get_session_state("mock-session")["mock_interview_view"] == completed_view_model


def test_runtime_end_mock_interview_resets_view_state_without_writing_unrelated_success_state(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_mock_runtime_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("mock-session")
    runtime.session_store.set_state("mock-session", "candidate_profile", {"name": "Alice"})
    runtime.start_mock_interview(
        session_id="mock-session",
        target_role="后端工程师",
        question_count=2,
        followup_rounds=1,
    )

    end_view_model = runtime.end_mock_interview("mock-session")

    assert end_view_model == {
        "session_id": "mock-session",
        "status": "ended",
        "error_message": None,
        "current_prompt": None,
        "progress": {
            "current_question_index": 0,
            "total_questions": 0,
            "current_followup_index": 0,
            "total_followups": 0,
        },
        "review_panel": None,
        "transcript": [],
    }
    assert runtime.get_session_state("mock-session")["mock_interview_view"] == {
        "session_id": "mock-session",
        "status": "idle",
        "error_message": None,
        "current_prompt": None,
        "progress": {
            "current_question_index": 0,
            "total_questions": 0,
            "current_followup_index": 0,
            "total_followups": 0,
        },
        "review_panel": None,
        "transcript": [],
    }


def build_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="algorithm_practice",
                description="Generate algorithm practice.",
                required_inputs=(),
                optional_inputs=("practice_topic",),
                outputs=("practice_set",),
                handler=algorithm_practice_handler,
            ),
            NodeSpec(
                name="knowledge_search",
                description="Search knowledge.",
                required_inputs=("question",),
                optional_inputs=(),
                outputs=("search_results",),
                handler=knowledge_search_handler,
            ),
            NodeSpec(
                name="failing_node",
                description="Failing node.",
                required_inputs=("resume_text",),
                optional_inputs=(),
                outputs=("failed_output",),
                handler=failing_handler,
            ),
        ]
    )


def build_prep_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="resume_parse",
                description="Parse resume.",
                required_inputs=("resume_text",),
                optional_inputs=(),
                outputs=("resume_profile", "candidate_profile"),
                handler=resume_parse_handler,
            ),
            NodeSpec(
                name="jd_parse",
                description="Parse JD.",
                required_inputs=("jd_text",),
                optional_inputs=(),
                outputs=("jd_requirements",),
                handler=jd_parse_handler,
            ),
            NodeSpec(
                name="jd_match",
                description="Match resume and JD.",
                required_inputs=("resume_profile", "jd_requirements"),
                optional_inputs=(),
                outputs=("match_report",),
                handler=jd_match_handler,
            ),
        ]
    )


def build_mock_runtime_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="question_generate",
                description="generate progressive questions",
                required_inputs=("candidate_profile", "target_role"),
                optional_inputs=("jd_requirements", "question_count"),
                outputs=("questions",),
                handler=mock_runtime_question_generate_handler,
            ),
            NodeSpec(
                name="mock_followup",
                description="generate followup questions",
                required_inputs=("question", "answer"),
                optional_inputs=(),
                outputs=("followup_questions",),
                handler=mock_runtime_followup_handler,
            ),
            NodeSpec(
                name="answer_score",
                description="score interview answer",
                required_inputs=("question", "answer", "rubric"),
                optional_inputs=(),
                outputs=("score_report",),
                handler=mock_runtime_answer_score_handler,
            ),
        ]
    )


def build_empty_mock_runtime_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="question_generate",
                description="generate empty questions",
                required_inputs=("candidate_profile", "target_role"),
                optional_inputs=("jd_requirements", "question_count"),
                outputs=("questions",),
                handler=empty_mock_runtime_question_generate_handler,
            ),
            NodeSpec(
                name="mock_followup",
                description="generate followup questions",
                required_inputs=("question", "answer"),
                optional_inputs=(),
                outputs=("followup_questions",),
                handler=mock_runtime_followup_handler,
            ),
            NodeSpec(
                name="answer_score",
                description="score interview answer",
                required_inputs=("question", "answer", "rubric"),
                optional_inputs=(),
                outputs=("score_report",),
                handler=mock_runtime_answer_score_handler,
            ),
        ]
    )


def build_services(config: object) -> dict[str, object]:
    del config
    return {"source": "fake"}


def algorithm_practice_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    assert context.services["source"] == "fake"
    practice_topic = str(inputs.get("practice_topic", "算法"))
    return {
        "practice_set": {
            "topic": practice_topic,
            "difficulty": "medium",
            "exercises": [f"{practice_topic} exercise"],
        }
    }


def knowledge_search_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    return {"search_results": [{"summary": inputs["question"]}]}


def failing_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    raise RuntimeError("handler failed")


def resume_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    profile = {
        "name": "Alice",
        "headline": "Python 检索服务负责人",
        "skills": ["Python", "检索系统"],
        "highlights": ["Python", "检索系统", "可靠性治理"],
    }
    return {"resume_profile": profile, "candidate_profile": profile}


def jd_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    return {
        "jd_requirements": {
            "role": "后端工程师",
            "must_have": ["Python", "检索链路", "稳定性"],
        }
    }


def jd_match_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    assert inputs["resume_profile"]["name"] == "Alice"
    assert inputs["jd_requirements"]["role"] == "后端工程师"
    return {
        "match_report": {
            "score": 91,
            "strengths": ["Python 服务经验", "检索系统经验"],
            "risks": ["补充压测案例"],
            "follow_up_focus": ["SLA 取舍", "检索召回评估"],
        }
    }


def mock_runtime_question_generate_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    assert inputs["candidate_profile"] == {"name": "Alice"}
    assert inputs["target_role"] == "后端工程师"
    assert inputs["question_count"] == 2
    return {
        "questions": [
            "介绍你最近一次线上延迟排查。",
            "如果延迟再次出现，你会如何设计预防机制？",
        ]
    }


def empty_mock_runtime_question_generate_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    return {"questions": []}


def mock_runtime_followup_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    if inputs["question"] == "介绍你最近一次线上延迟排查。":
        return {"followup_questions": ["你如何判断瓶颈在数据库？"]}
    return {"followup_questions": []}


def mock_runtime_answer_score_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    question = inputs["question"]
    if question == "介绍你最近一次线上延迟排查。":
        return {
            "score_report": {
                "score": 8,
                "gaps": [],
                "suggestions": [],
                "reference_answer": [],
            }
        }
    if question == "你如何判断瓶颈在数据库？":
        return {
            "score_report": {
                "score": 6,
                "gaps": ["缺少数据库瓶颈判定证据"],
                "suggestions": ["补充监控指标、定位步骤和验证闭环"],
                "reference_answer": [],
            }
        }
    return {
        "score_report": {
            "score": 7,
            "gaps": ["预防方案还不够具体"],
            "suggestions": ["说明告警阈值、容量治理和复盘机制"],
            "reference_answer": [],
        }
    }


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
