from __future__ import annotations

import sqlite3
from pathlib import Path

from interview_agent.executor import NodeExecutor
from interview_agent.nodes.registry import build_default_registry
from interview_agent.session import SessionStore
from interview_agent.storage import initialize_database


class RecordingLLM:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def complete(self, prompt: str, system_prompt: str | None = None) -> str:
        del system_prompt
        self.prompts.append(prompt)
        for marker, response in self.responses.items():
            if marker in prompt:
                return response
        raise AssertionError(f"unexpected prompt: {prompt}")


class RecordingRetriever:
    def __init__(self, results: list[dict[str, object]]) -> None:
        self.results = results
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, limit: int) -> list[dict[str, object]]:
        self.calls.append((query, limit))
        return self.results[:limit]


NODE_CASES = {
    "knowledge_search": (
        {"question": "How to explain retry?", "top_k": 1},
        "search_results",
        '{"search_results":[{"chunk_id":"chunk-1","summary":"Python retry guidance"}]}',
        '{"search_results":"bad"}',
    ),
    "resume_parse": (
        {"resume_text": "Alice built Python services."},
        "resume_profile",
        '{"resume_profile":{"name":"Alice","skills":["Python"]}}',
        '{"resume_profile":["bad"]}',
    ),
    "project_extract": (
        {"resume_text": "Project Agent improved throughput."},
        "project_experiences",
        '{"project_experiences":[{"name":"Agent","impact":"improved throughput"}]}',
        '{"project_experiences":"bad"}',
    ),
    "jd_parse": (
        {"jd_text": "Need Backend engineer with Python and SQL."},
        "jd_requirements",
        '{"jd_requirements":{"role":"Backend","skills":["Python","SQL"]}}',
        '{"jd_requirements":["bad"]}',
    ),
    "jd_match": (
        {
            "resume_profile": {"name": "Alice", "skills": ["Python"]},
            "jd_requirements": {"role": "Backend", "skills": ["Python", "SQL"]},
        },
        "match_report",
        '{"match_report":{"score":87,"matched_skills":["Python"]}}',
        '{"match_report":"bad"}',
    ),
    "question_generate": (
        {"candidate_profile": {"name": "Alice"}, "target_role": "Backend", "difficulty": "hard"},
        "questions",
        '{"questions":["解释 Python GIL","如何设计重试机制"]}',
        '{"questions":"bad"}',
    ),
    "mock_followup": (
        {"question": "Explain retry.", "answer": "Use backoff.", "rubric": "depth"},
        "followup_questions",
        '{"followup_questions":["给出生产事故案例"]}',
        '{"followup_questions":"bad"}',
    ),
    "answer_score": (
        {"question": "Explain retry.", "answer": "Use backoff.", "rubric": "accuracy"},
        "score_report",
        '{"score_report":{"score":8,"gaps":["缺少指标"],"suggestions":["补充量化指标"],"reference_answer":"先说明策略。"}}',
        '{"score_report":{"score":"bad","gaps":["缺少指标"],"suggestions":["补充量化指标"],"reference_answer":"先说明策略。"}}',
    ),
    "weakness_train": (
        {"weaknesses": ["system design"], "goal": "improve architecture", "candidate_profile": {"name": "Alice"}},
        "training_plan",
        '{"training_plan":{"focus":"system design","steps":["daily drill"],"drills":["mock"],"schedule":["day 1"]}}',
        '{"training_plan":{"focus":"system design","steps":"bad","drills":["mock"],"schedule":["day 1"]}}',
    ),
    "resume_optimize": (
        {
            "resume_text": "Alice built services.",
            "target_role": "Backend",
            "jd_requirements": {"skills": ["Python", "SQL"]},
        },
        "optimization_advice",
        '{"optimization_advice":{"summary":"突出指标","bullets":["补充 SLA 成果"],"risks":["指标缺失"],"rewrite_examples":["将负责改为主导"]}}',
        '{"optimization_advice":{"summary":"突出指标","bullets":"bad","risks":["指标缺失"],"rewrite_examples":["将负责改为主导"]}}',
    ),
    "session_summary": (
        {"session_transcript": "Q: retry? A: backoff."},
        "summary",
        '{"summary":{"highlights":["完成一轮模拟"],"next_steps":["补强 system design"]}}',
        '{"summary":"bad"}',
    ),
}


PROMPT_MARKERS = {
    "knowledge_search": "你是知识库检索助手",
    "resume_parse": "你是简历解析助手",
    "project_extract": "你是项目经历提炼助手",
    "jd_parse": "你是 JD 解析助手",
    "jd_match": "你是 JD 匹配助手",
    "question_generate": "你是面试题生成助手",
    "mock_followup": "你是追问生成助手",
    "answer_score": "你是回答评分助手",
    "weakness_train": "你是薄弱点训练助手",
    "resume_optimize": "你是简历优化助手",
    "session_summary": "你是会话总结助手",
}


def test_interview_runtime_nodes_return_structured_outputs_and_write_session_state(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "interview.sqlite3"
    initialize_database(database_path)
    llm = RecordingLLM(
        responses={
            "你是简历解析助手": '{"resume_profile":{"name":"Alice","skills":["Python"]}}',
            "你是项目经历提炼助手": '{"project_experiences":[{"name":"Agent","impact":"improved throughput"}]}',
            "你是 JD 解析助手": '{"jd_requirements":{"role":"Backend","skills":["Python","SQL"]}}',
            "你是 JD 匹配助手": '{"match_report":{"score":87,"matched_skills":["Python"]}}',
            "你是面试题生成助手": '{"questions":["解释 Python GIL","如何设计重试机制"]}',
            "你是追问生成助手": '{"followup_questions":["给出生产事故案例"]}',
            "你是回答评分助手": (
                '{"score_report":{"score":8,"strengths":["结构清晰"],"gaps":["缺少指标"],'
                '"suggestions":["补充量化指标"],"reference_answer":"先说明策略。"}}'
            ),
            "你是薄弱点训练助手": (
                '{"training_plan":{"focus":"system design","steps":["daily drill"],'
                '"drills":["mock"],"schedule":["day 1"]}}'
            ),
            "你是简历优化助手": (
                '{"optimization_advice":{"summary":"突出指标","bullets":["补充 SLA 成果"],'
                '"risks":["指标缺失"],"rewrite_examples":["将负责改为主导"]}}'
            ),
            "你是会话总结助手": '{"summary":{"highlights":["完成一轮模拟"],"next_steps":["补强 system design"]}}',
            "你是知识库检索助手": '{"search_results":[{"chunk_id":"chunk-1","summary":"Python retry guidance"}]}',
        }
    )
    retriever = RecordingRetriever(
        [
            {
                "chunk_id": "chunk-1",
                "content": "Retry guidance for Python services.",
                "source_path": "kb/retry.md",
                "score": 0.9,
            }
        ]
    )
    executor = NodeExecutor(
        database_path,
        build_default_registry(),
        services={"llm": llm, "retriever": retriever},
    )
    session_id = "session-1"

    executed_nodes = [
        ("resume_parse", {"resume_text": "Alice built Python services."}, "resume_profile"),
        (
            "project_extract",
            {"resume_text": "Project Agent improved throughput."},
            "project_experiences",
        ),
        ("jd_parse", {"jd_text": "Need Backend engineer with Python and SQL."}, "jd_requirements"),
        (
            "jd_match",
            {
                "resume_profile": {"name": "Alice", "skills": ["Python"]},
                "jd_requirements": {"role": "Backend", "skills": ["Python", "SQL"]},
            },
            "match_report",
        ),
        (
            "question_generate",
            {"candidate_profile": {"name": "Alice"}, "target_role": "Backend", "difficulty": "hard"},
            "questions",
        ),
        (
            "mock_followup",
            {"question": "Explain retry.", "answer": "Use backoff.", "rubric": "depth"},
            "followup_questions",
        ),
        (
            "answer_score",
            {"question": "Explain retry.", "answer": "Use backoff.", "rubric": "accuracy"},
            "score_report",
        ),
        (
            "weakness_train",
            {"weaknesses": ["system design"], "goal": "improve architecture", "candidate_profile": {"name": "Alice"}},
            "training_plan",
        ),
        (
            "resume_optimize",
            {
                "resume_text": "Alice built services.",
                "target_role": "Backend",
                "jd_requirements": {"skills": ["Python", "SQL"]},
            },
            "optimization_advice",
        ),
        (
            "session_summary",
            {"session_transcript": "Q: retry? A: backoff."},
            "summary",
        ),
        ("knowledge_search", {"question": "How to explain retry?", "top_k": 1}, "search_results"),
    ]

    for node_name, inputs, output_key in executed_nodes:
        result = executor.execute_node(session_id=session_id, node_name=node_name, inputs=inputs)
        assert result.status == "success"
        assert output_key in result.output

    with sqlite3.connect(database_path) as connection:
        state_keys = {
            row[0]
            for row in connection.execute(
                "SELECT state_key FROM session_state WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        }
        document_count = connection.execute("SELECT COUNT(*) FROM knowledge_documents").fetchone()
        chunk_count = connection.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()

    assert state_keys >= {
        "resume_profile",
        "candidate_profile",
        "project_experiences",
        "jd_requirements",
        "match_report",
        "questions",
        "followup_questions",
        "score_report",
        "training_plan",
        "optimization_advice",
        "summary",
        "search_results",
    }
    assert document_count == (0,)
    assert chunk_count == (0,)


def test_interview_runtime_nodes_accept_minimal_declared_output_structures(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "interview.sqlite3"
    initialize_database(database_path)

    for node_name, (inputs, output_key, response, _) in NODE_CASES.items():
        llm = RecordingLLM({PROMPT_MARKERS[node_name]: response})
        executor = NodeExecutor(
            database_path,
            build_default_registry(),
            services={"llm": llm, "retriever": RecordingRetriever([])},
        )

        result = executor.execute_node(
            session_id=f"session-success-{node_name}",
            node_name=node_name,
            inputs=inputs,
        )

        expected_output_keys = {output_key}
        if node_name == "resume_parse":
            expected_output_keys = {"resume_profile", "candidate_profile"}
        assert result.status == "success"
        assert set(result.output) == expected_output_keys


def test_interview_runtime_nodes_fail_when_declared_output_is_missing(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "interview.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)

    for node_name, (inputs, output_key, _, _) in NODE_CASES.items():
        llm = RecordingLLM({PROMPT_MARKERS[node_name]: '{"unexpected":"value"}'})
        executor = NodeExecutor(
            database_path,
            build_default_registry(),
            services={"llm": llm, "retriever": RecordingRetriever([])},
        )

        result = executor.execute_node(
            session_id=f"session-missing-{node_name}",
            node_name=node_name,
            inputs=inputs,
        )

        assert result.status == "failed"
        assert result.output == {}
        assert session_store.get_state(f"session-missing-{node_name}", output_key) is None


def test_interview_runtime_nodes_fail_when_declared_output_has_invalid_type(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "interview.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)

    for node_name, (inputs, output_key, _, invalid_response) in NODE_CASES.items():
        llm = RecordingLLM({PROMPT_MARKERS[node_name]: invalid_response})
        executor = NodeExecutor(
            database_path,
            build_default_registry(),
            services={"llm": llm, "retriever": RecordingRetriever([])},
        )

        result = executor.execute_node(
            session_id=f"session-invalid-{node_name}",
            node_name=node_name,
            inputs=inputs,
        )

        assert result.status == "failed"
        assert result.output == {}
        assert session_store.get_state(f"session-invalid-{node_name}", output_key) is None


def test_resume_parse_output_can_drive_question_generate_via_sqlite_session_state(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "interview.sqlite3"
    initialize_database(database_path)
    llm = RecordingLLM(
        responses={
            "你是简历解析助手": '{"resume_profile":{"name":"Alice","skills":["Python"],"highlight":"SLA ownership"}}',
            "你是面试题生成助手": '{"questions":["请解释你如何维护 SLA"]}',
        }
    )
    executor = NodeExecutor(
        database_path,
        build_default_registry(),
        services={"llm": llm},
    )

    parse_result = executor.execute_node(
        session_id="session-1",
        node_name="resume_parse",
        inputs={"resume_text": "Alice owned SLA and Python services."},
    )
    question_result = executor.execute_node(
        session_id="session-1",
        node_name="question_generate",
        inputs={"target_role": "Backend"},
    )

    assert parse_result.status == "success"
    assert parse_result.output["resume_profile"] == parse_result.output["candidate_profile"]
    assert question_result.status == "success"
    assert question_result.output == {"questions": ["请解释你如何维护 SLA"]}


def test_session_state_flows_across_resume_jd_question_score_and_training_nodes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "interview.sqlite3"
    initialize_database(database_path)
    llm = RecordingLLM(
        responses={
            "你是简历解析助手": '{"resume_profile":{"name":"Alice","skills":["Python"],"role":"Backend"}}',
            "你是 JD 解析助手": '{"jd_requirements":{"role":"Backend","skills":["Python","SQL"]}}',
            "你是 JD 匹配助手": '{"match_report":{"score":91,"matched_skills":["Python"]}}',
            "你是面试题生成助手": '{"questions":["请解释你如何保障 SLA"]}',
            "你是回答评分助手": (
                '{"score_report":{"score":8,"gaps":["指标不够具体"],'
                '"suggestions":["补充量化指标"],"reference_answer":"先说明策略。"}}'
            ),
            "你是薄弱点训练助手": (
                '{"training_plan":{"focus":"指标量化","steps":["补充量化案例"],'
                '"drills":["每天复盘一个案例"],"schedule":["day 1"]}}'
            ),
        }
    )
    executor = NodeExecutor(
        database_path,
        build_default_registry(),
        services={"llm": llm},
    )

    resume_result = executor.execute_node(
        session_id="session-1",
        node_name="resume_parse",
        inputs={"resume_text": "Alice built Python services and owned SLA."},
    )
    jd_result = executor.execute_node(
        session_id="session-1",
        node_name="jd_parse",
        inputs={"jd_text": "Need Backend engineer with Python and SQL."},
    )
    match_result = executor.execute_node(
        session_id="session-1",
        node_name="jd_match",
    )
    question_result = executor.execute_node(
        session_id="session-1",
        node_name="question_generate",
        inputs={"target_role": "Backend"},
    )
    score_result = executor.execute_node(
        session_id="session-1",
        node_name="answer_score",
        inputs={
            "question": "请解释你如何保障 SLA",
            "answer": "我会建立 SLO、告警和容量预案。",
            "rubric": "按 SLA、告警、容量预案评分",
        },
    )
    training_result = executor.execute_node(
        session_id="session-1",
        node_name="weakness_train",
        inputs={"weaknesses": ["指标量化"], "goal": "补强回答中的量化表达"},
    )

    assert resume_result.status == "success"
    assert jd_result.status == "success"
    assert match_result.status == "success"
    assert question_result.status == "success"
    assert score_result.status == "success"
    assert training_result.status == "success"
    assert resume_result.output["resume_profile"] == resume_result.output["candidate_profile"]
    assert match_result.output == {"match_report": {"score": 91, "matched_skills": ["Python"]}}
    assert question_result.output == {"questions": ["请解释你如何保障 SLA"]}
    assert score_result.output == {
        "score_report": {
            "score": 8,
            "gaps": ["指标不够具体"],
            "suggestions": ["补充量化指标"],
            "reference_answer": "先说明策略。",
        }
    }
    assert training_result.output == {
        "training_plan": {
            "focus": "指标量化",
            "steps": ["补充量化案例"],
            "drills": ["每天复盘一个案例"],
            "schedule": ["day 1"],
        }
    }


def test_prompt_includes_node_inputs_for_fields_not_declared_in_template(tmp_path: Path) -> None:
    database_path = tmp_path / "interview.sqlite3"
    initialize_database(database_path)
    llm = RecordingLLM(
        responses={
            "你是面试题生成助手": '{"questions":["请解释你如何维护 SLA"]}',
            "你是回答评分助手": (
                '{"score_report":{"score":9,"gaps":["缺少容量指标"],'
                '"suggestions":["补充 SLA ownership"],"reference_answer":"先说明指标。"}}'
            ),
        }
    )
    executor = NodeExecutor(
        database_path,
        build_default_registry(),
        services={"llm": llm},
    )

    question_result = executor.execute_node(
        session_id="session-1",
        node_name="question_generate",
        inputs={
            "candidate_profile": {"name": "Alice", "highlight": "SLA ownership"},
            "target_role": "Backend",
            "difficulty": "staff",
            "question_count": 6,
            "jd_requirements": {"must_have": ["Python", "SLA"]},
        },
    )
    score_result = executor.execute_node(
        session_id="session-1",
        node_name="answer_score",
        inputs={
            "question": "如何保障 SLA？",
            "answer": "我会建立告警与容量预案。",
            "rubric": "请按 SLA、告警、容量三个维度评分",
        },
    )

    assert question_result.status == "success"
    assert score_result.status == "success"
    assert 'node_inputs:\n{"candidate_profile":{"highlight":"SLA ownership","name":"Alice"}' in llm.prompts[0]
    assert '"jd_requirements":{"must_have":["Python","SLA"]}' in llm.prompts[0]
    assert '"difficulty":"staff"' in llm.prompts[0]
    assert '"question_count":6' in llm.prompts[0]
    assert '"target_role":"Backend"' in llm.prompts[0]
    assert 'node_inputs:\n{"answer":"我会建立告警与容量预案。"' in llm.prompts[1]
    assert '"rubric":"请按 SLA、告警、容量三个维度评分"' in llm.prompts[1]
    assert "SLA" in llm.prompts[0]
    assert "SLA" in llm.prompts[1]


def test_rag_nodes_read_retrieval_chunks_and_pass_them_into_llm_prompt(tmp_path: Path) -> None:
    database_path = tmp_path / "interview.sqlite3"
    initialize_database(database_path)
    llm = RecordingLLM(
        responses={
            "你是面试题生成助手": '{"questions":["解释 RAG"]}',
            "你是知识库检索助手": '{"search_results":[{"chunk_id":"chunk-1","summary":"RAG summary"}]}',
        }
    )
    retriever = RecordingRetriever(
        [
            {
                "chunk_id": "chunk-1",
                "content": "RAG chunk content for interview preparation.",
                "source_path": "kb/rag.md",
                "score": 0.8,
            }
        ]
    )
    executor = NodeExecutor(
        database_path,
        build_default_registry(),
        services={"llm": llm, "retriever": retriever},
    )

    question_result = executor.execute_node(
        session_id="session-1",
        node_name="question_generate",
        inputs={"candidate_profile": {"name": "Alice"}, "target_role": "Backend"},
    )
    search_result = executor.execute_node(
        session_id="session-1",
        node_name="knowledge_search",
        inputs={"question": "什么是 RAG？", "top_k": 1},
    )

    assert question_result.status == "success"
    assert search_result.status == "success"
    assert retriever.calls == [("Backend Alice", 3), ("什么是 RAG？", 1)]
    assert "rag_context" in llm.prompts[0]
    assert "RAG chunk content for interview preparation." in llm.prompts[0]
    assert "rag_context" in llm.prompts[1]
    assert "RAG chunk content for interview preparation." in llm.prompts[1]


def test_knowledge_search_fails_when_llm_response_is_invalid(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "interview.sqlite3"
    initialize_database(database_path)
    session_store = SessionStore(database_path)
    executor = NodeExecutor(
        database_path,
        build_default_registry(),
        services={
            "llm": RecordingLLM({"你是知识库检索助手": ""}),
            "retriever": RecordingRetriever([]),
        },
    )

    result = executor.execute_node(
        session_id="session-1",
        node_name="knowledge_search",
        inputs={"question": "How to explain retry?"},
    )

    with sqlite3.connect(database_path) as connection:
        run_row = connection.execute(
            "SELECT status, output_payload, error_message FROM node_runs WHERE run_id = ?",
            (result.run_id,),
        ).fetchone()

    assert result.status == "failed"
    assert result.output == {}
    assert result.error_message == "LLM 返回空响应"
    assert session_store.get_state("session-1", "search_results") is None
    assert session_store.get_state("session-1", "message") is None
    assert run_row == ("failed", None, "LLM 返回空响应")


def test_knowledge_search_uses_retriever_chunks_as_base_and_llm_only_adds_non_source_fields(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "interview.sqlite3"
    initialize_database(database_path)
    llm = RecordingLLM(
        responses={
            "你是知识库检索助手": (
                '{"search_results":[{"chunk_id":"tampered","source_path":"tampered.md",'
                '"score":0.01,"content":"tampered","summary":"保留重点","advice":"先讲结论"}]}'
            )
        }
    )
    retriever = RecordingRetriever(
        [
            {
                "chunk_id": "chunk-1",
                "content": "Retry guidance for Python services.",
                "source_path": "kb/retry.md",
                "score": 0.9,
            }
        ]
    )
    executor = NodeExecutor(
        database_path,
        build_default_registry(),
        services={"llm": llm, "retriever": retriever},
    )

    result = executor.execute_node(
        session_id="session-1",
        node_name="knowledge_search",
        inputs={"question": "How to explain retry?", "top_k": 1},
    )

    assert result.status == "success"
    assert result.output == {
        "search_results": [
            {
                "chunk_id": "chunk-1",
                "source_path": "kb/retry.md",
                "score": 0.9,
                "content": "Retry guidance for Python services.",
                "summary": "保留重点",
                "advice": "先讲结论",
            }
        ]
    }


def test_run_structured_node_preserves_rag_source_metadata_from_retriever(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "interview.sqlite3"
    initialize_database(database_path)
    llm = RecordingLLM(
        responses={
            "你是知识库检索助手": (
                '{"search_results":[{"chunk_id":"llm-overwrite","source_path":"llm.md",'
                '"score":0.2,"content":"llm content","summary":"RAG summary"}]}'
            )
        }
    )
    retriever = RecordingRetriever(
        [
            {
                "chunk_id": "chunk-1",
                "content": "RAG chunk content for interview preparation.",
                "source_path": "kb/rag.md",
                "score": 0.8,
            }
        ]
    )
    executor = NodeExecutor(
        database_path,
        build_default_registry(),
        services={"llm": llm, "retriever": retriever},
    )

    result = executor.execute_node(
        session_id="session-1",
        node_name="knowledge_search",
        inputs={"question": "什么是 RAG？", "top_k": 1},
    )

    assert result.status == "success"
    assert result.output["search_results"][0]["chunk_id"] == "chunk-1"
    assert result.output["search_results"][0]["source_path"] == "kb/rag.md"
    assert result.output["search_results"][0]["score"] == 0.8
    assert result.output["search_results"][0]["content"] == "RAG chunk content for interview preparation."
    assert result.output["search_results"][0]["summary"] == "RAG summary"


def test_knowledge_search_returns_empty_results_without_extra_output_keys_when_retriever_has_no_hits(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "interview.sqlite3"
    initialize_database(database_path)
    executor = NodeExecutor(
        database_path,
        build_default_registry(),
        services={
            "llm": RecordingLLM({"你是知识库检索助手": '{"search_results":[]}'}),
            "retriever": RecordingRetriever([]),
        },
    )

    result = executor.execute_node(
        session_id="session-1",
        node_name="knowledge_search",
        inputs={"question": "没有命中的问题"},
    )

    assert result.status == "success"
    assert result.output == {"search_results": []}
    assert "message" not in result.output
