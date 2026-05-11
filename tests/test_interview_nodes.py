from __future__ import annotations

import sqlite3
from pathlib import Path

from interview_agent.executor import NodeExecutor
from interview_agent.nodes.registry import build_default_registry
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
            "你是回答评分助手": '{"score_report":{"score":8,"strengths":["结构清晰"],"gaps":["缺少指标"]}}',
            "你是薄弱点训练助手": '{"training_plan":{"focus":"system design","steps":["daily drill"]}}',
            "你是简历优化助手": '{"optimization_advice":{"summary":"突出指标","bullets":["补充 SLA 成果"]}}',
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
