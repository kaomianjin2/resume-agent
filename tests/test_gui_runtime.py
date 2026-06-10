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


def test_runtime_start_algorithm_practice_builds_selectable_exercise_view_model(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_structured_algorithm_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("algorithm-session")
    runtime.session_store.set_state(
        "algorithm-session",
        "algorithm_practice_bank",
        {
            "topic": "动态规划",
            "difficulty": "medium",
            "exercises": [
                {
                    "title": "最长递增子序列",
                    "prompt": "返回最长严格递增子序列长度。",
                    "tags": ["动态规划", "数组"],
                    "constraints": ["1 <= nums.length <= 2500"],
                    "examples": ["输入 [10,9,2,5,3,7,101,18]，输出 4"],
                    "edge_cases": ["空数组返回 0"],
                },
                {
                    "title": "零钱兑换",
                    "description": "计算凑成金额所需的最少硬币数。",
                    "tags": ["动态规划"],
                },
            ],
        },
    )

    view_model = runtime.start_algorithm_practice(
        session_id="algorithm-session",
        practice_topic="动态规划",
        difficulty="medium",
        question_count=2,
    )

    assert view_model == {
        "session_id": "algorithm-session",
        "status": "ready",
        "error_message": None,
        "topic": "动态规划",
        "difficulty": "medium",
        "exercises": [
            {
                "id": "exercise-1",
                "title": "最长递增子序列",
                "prompt": "返回最长严格递增子序列长度。",
                "tags": ["动态规划", "数组"],
                "constraints": ["1 <= nums.length <= 2500"],
                "examples": ["输入 [10,9,2,5,3,7,101,18]，输出 4"],
                "edge_cases": ["空数组返回 0"],
            },
            {
                "id": "exercise-2",
                "title": "零钱兑换",
                "prompt": "计算凑成金额所需的最少硬币数。",
                "tags": ["动态规划"],
                "constraints": [],
                "examples": [],
                "edge_cases": [],
            },
        ],
        "current_exercise_index": 0,
        "progress": {
            "current_exercise_index": 1,
            "total_exercises": 2,
        },
    }


def test_runtime_start_algorithm_practice_uses_pregenerated_bank_without_generating(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_failing_algorithm_generation_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("algorithm-session")
    runtime.session_store.set_state(
        "algorithm-session",
        "algorithm_practice_bank",
        {
            "topic": "算法和数据结构",
            "difficulty": "medium",
            "exercises": [
                {
                    "title": "反转链表",
                    "prompt": "反转单链表并返回新的头节点。",
                    "tags": ["链表", "简单"],
                    "constraints": ["0 <= 节点数 <= 5000"],
                    "examples": ["输入 1->2->3，输出 3->2->1"],
                    "edge_cases": ["空链表返回空"],
                },
                {
                    "title": "有效括号",
                    "prompt": "判断括号字符串是否合法。",
                    "tags": ["栈", "简单"],
                },
            ],
        },
    )

    view_model = runtime.start_algorithm_practice(
        session_id="algorithm-session",
        practice_topic="链表",
        difficulty="medium",
        question_count=1,
    )

    assert view_model == {
        "session_id": "algorithm-session",
        "status": "ready",
        "error_message": None,
        "topic": "算法和数据结构",
        "difficulty": "medium",
        "exercises": [
            {
                "id": "exercise-1",
                "title": "反转链表",
                "prompt": "反转单链表并返回新的头节点。",
                "tags": ["链表", "简单"],
                "constraints": ["0 <= 节点数 <= 5000"],
                "examples": ["输入 1->2->3，输出 3->2->1"],
                "edge_cases": ["空链表返回空"],
            },
        ],
        "current_exercise_index": 0,
        "progress": {
            "current_exercise_index": 1,
            "total_exercises": 1,
        },
    }


def test_runtime_start_algorithm_practice_reports_empty_exercise_set(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_empty_algorithm_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("algorithm-session")
    runtime.session_store.set_state(
        "algorithm-session",
        "algorithm_practice_bank",
        {
            "topic": "链表",
            "difficulty": "easy",
            "exercises": [],
        },
    )

    view_model = runtime.start_algorithm_practice(
        session_id="algorithm-session",
        practice_topic="链表",
        difficulty="easy",
        question_count=3,
    )

    assert view_model == {
        "session_id": "algorithm-session",
        "status": "failed",
        "error_message": "还没有生成可用于练习的题目。",
        "topic": "链表",
        "difficulty": "easy",
        "exercises": [],
        "current_exercise_index": 0,
        "progress": {
            "current_exercise_index": 0,
            "total_exercises": 0,
        },
    }


def test_runtime_start_algorithm_practice_uses_default_internal_bank(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_failing_algorithm_generation_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("algorithm-session")

    view_model = runtime.start_algorithm_practice(
        session_id="algorithm-session",
        practice_topic="算法和数据结构",
        difficulty="medium",
        question_count=100,
    )

    assert view_model["status"] == "ready"
    assert view_model["topic"] == "内部算法题库"
    assert len(view_model["exercises"]) >= 100
    assert {exercise["title"] for exercise in view_model["exercises"]} >= {
        "最长递增子序列",
        "零钱兑换",
        "反转链表",
        "二叉树层序遍历",
        "LRU 缓存",
    }
    assert view_model["progress"] == {
        "current_exercise_index": 1,
        "total_exercises": len(view_model["exercises"]),
    }


def test_runtime_start_algorithm_practice_filters_default_bank_by_topic(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_failing_algorithm_generation_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("algorithm-session")

    view_model = runtime.start_algorithm_practice(
        session_id="algorithm-session",
        practice_topic="二叉树",
        difficulty="medium",
        question_count=5,
    )

    assert view_model["status"] == "ready"
    assert len(view_model["exercises"]) == 5
    assert all("二叉树" in " ".join(exercise["tags"]) for exercise in view_model["exercises"])


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


def test_runtime_preparation_keeps_synonym_fields_in_summary_and_report(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_synonym_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("prep-session")

    prep_view_model = runtime.prepare_interview_materials(
        session_id="prep-session",
        resume_text="Alice led Python retrieval services.",
        jd_text="Need Backend engineer with Python, retrieval, and reliability.",
    )

    assert prep_view_model["resume_summary"] == {
        "name": "Alice",
        "headline": "后端检索工程师，负责 SLA 和召回评估",
        "highlights": ["Python", "检索系统", "SLA"],
    }
    assert prep_view_model["jd_summary"] == {
        "role": "后端工程师",
        "focus": ["Python", "检索链路", "稳定性"],
    }
    assert prep_view_model["match_summary"] == {
        "score": 88,
        "strengths": ["检索经验贴合", "Python 服务经验"],
        "risks": ["压测案例不足"],
        "follow_up_focus": ["SLA 取舍", "召回评估"],
    }


def test_runtime_preparation_keeps_detailed_resume_summary_fields(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_detailed_resume_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("prep-session")

    prep_view_model = runtime.prepare_interview_materials(
        session_id="prep-session",
        resume_text="Alice led Golang services and payment reliability.",
        jd_text="   ",
    )

    assert prep_view_model["resume_summary"] == {
        "name": "Alice",
        "headline": "Golang 后端工程师，6 年服务端与稳定性治理经验",
        "highlights": [
            "Golang",
            "支付链路",
            "MySQL",
            "Redis",
            "主导交易服务重构",
            "CDN 授权版",
            "P95 延迟从 900ms 降到 180ms",
            "SLA 治理",
            "容量压测",
        ],
    }


def test_runtime_preparation_maps_nested_chinese_resume_jd_and_match_fields(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_nested_chinese_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("prep-session")

    prep_view_model = runtime.prepare_interview_materials(
        session_id="prep-session",
        resume_text="罗天 Golang 6 年经验。",
        jd_text="golang开发工程师，需要高并发和分布式。",
    )

    assert prep_view_model["resume_summary"]["name"] == "罗天"
    assert prep_view_model["resume_summary"]["headline"] == "Golang，6 年经验，本科"
    assert prep_view_model["jd_summary"] == {
        "role": "golang开发工程师",
        "focus": ["负责后端设计开发", "Golang", "高并发", "分布式"],
    }
    assert prep_view_model["match_summary"] == {
        "score": 92,
        "strengths": ["Golang 后端经验充足"],
        "risks": ["出差适配不明确"],
        "follow_up_focus": ["追问高并发项目"],
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
        "missing_inputs": ["resume_text"],
    }
    assert runtime.get_session_state("prep-session") == {}


def test_runtime_prepares_materials_with_resume_only(tmp_path: Path) -> None:
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
        jd_text="   ",
    )

    assert prep_view_model == {
        "session_id": "prep-session",
        "status": "ready",
        "resume_summary": {
            "name": "Alice",
            "headline": "Python 检索服务负责人",
            "highlights": ["Python", "检索系统", "可靠性治理"],
        },
        "jd_summary": {},
        "match_summary": {
            "score": "未评分",
            "strengths": [],
            "risks": [],
            "follow_up_focus": [],
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
        "resume_profile": {
            "name": "Alice",
            "headline": "Python 检索服务负责人",
            "skills": ["Python", "检索系统"],
            "highlights": ["Python", "检索系统", "可靠性治理"],
        },
    }


def test_runtime_prepares_jd_after_resume_import_without_reparsing_resume(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_flaky_resume_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("prep-session")

    resume_view_model = runtime.prepare_interview_materials(
        session_id="prep-session",
        resume_text="Alice led Python retrieval services.",
        jd_text="   ",
    )
    jd_view_model = runtime.prepare_interview_materials(
        session_id="prep-session",
        resume_text="Alice led Python retrieval services.",
        jd_text="Need Backend engineer with Python, retrieval, and reliability.",
    )

    assert resume_view_model["status"] == "ready"
    assert jd_view_model == {
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


def test_runtime_prepares_complete_job_search_profile_from_resume_profile(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("job-session")
    runtime.session_store.set_state(
        "job-session",
        "resume_profile",
        {
            "name": "Alice",
            "headline": "Golang 后端工程师",
            "skills": ["Golang", "MySQL", "Redis"],
            "target_roles": ["后端工程师", "平台工程师"],
            "years_of_experience": 6,
            "education_level": "本科",
            "preferred_cities": ["上海", "杭州"],
            "remote_preference": "hybrid",
            "salary_expectation": {"min": 35, "max": 50, "currency": "CNY", "period": "month"},
            "preferred_levels": ["高级"],
            "preferred_industries": ["AI 工具", "企业服务"],
            "preferred_company_sizes": ["100-500人"],
            "preferred_funding_stages": ["B轮", "C轮"],
            "preferred_benefits": ["五险一金", "弹性工作"],
            "published_within_days": 30,
            "company_blacklist": [],
            "company_whitelist": [],
        },
    )

    view_model = runtime.prepare_job_search_profile(session_id="job-session")

    assert view_model == {
        "session_id": "job-session",
        "status": "ready",
        "job_profile": {
            "candidate_name": "Alice",
            "target_roles": ["后端工程师", "平台工程师"],
            "headline": "Golang 后端工程师",
            "years_of_experience": 6,
            "education_level": "本科",
            "technical_skills": ["Golang", "MySQL", "Redis"],
            "project_keywords": [],
            "search_preferences": {
                "cities": ["上海", "杭州"],
                "remote_policy": "hybrid",
                "salary_min": 35,
                "salary_max": 50,
                "levels": ["高级"],
                "experience_years_min": 6,
                "experience_years_max": 6,
                "education": "本科",
                "industries": ["AI 工具", "企业服务"],
                "company_sizes": ["100-500人"],
                "funding_stages": ["B轮", "C轮"],
                "technical_skills": ["Golang", "MySQL", "Redis"],
                "benefits": ["五险一金", "弹性工作"],
                "published_within_days": 30,
                "company_blacklist": [],
                "company_whitelist": [],
            },
        },
        "default_search_keywords": ["后端工程师 Golang", "平台工程师 Golang"],
        "hard_filters": {
            "cities": ["上海", "杭州"],
            "remote_policy": "hybrid",
            "salary_min": 35,
            "salary_max": 50,
            "levels": ["高级"],
            "experience_years_min": 6,
            "experience_years_max": 6,
            "education": "本科",
            "company_blacklist": [],
            "company_whitelist": [],
        },
        "ranking_preferences": {
            "industries": ["AI 工具", "企业服务"],
            "company_sizes": ["100-500人"],
            "funding_stages": ["B轮", "C轮"],
            "technical_skills": ["Golang", "MySQL", "Redis"],
            "benefits": ["五险一金", "弹性工作"],
            "published_within_days": 30,
        },
        "pending_confirmation_fields": [],
    }
    assert runtime.get_session_state("job-session")["job_search_profile"] == view_model


def test_runtime_marks_missing_job_search_profile_fields_for_confirmation(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("job-session")
    runtime.session_store.set_state(
        "job-session",
        "resume_profile",
        {
            "name": "Alice",
            "headline": "后端工程师",
            "education_level": "本科",
        },
    )

    view_model = runtime.prepare_job_search_profile(session_id="job-session")

    assert view_model["status"] == "needs_confirmation"
    assert view_model["pending_confirmation_fields"] == [
        "technical_skills",
        "years_of_experience",
        "cities",
        "remote_policy",
        "salary",
        "levels",
        "industries",
        "company_sizes",
        "funding_stages",
        "benefits",
        "published_within_days",
        "company_blacklist",
        "company_whitelist",
    ]
    assert view_model["default_search_keywords"] == ["后端工程师"]
    assert view_model["hard_filters"]["cities"] == []
    assert view_model["hard_filters"]["remote_policy"] is None


def test_runtime_saves_job_search_profile_with_user_overrides(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("job-session")
    runtime.session_store.set_state(
        "job-session",
        "resume_profile",
        {
            "name": "Alice",
            "headline": "Python 后端工程师",
            "skills": ["Python"],
            "years_of_experience": 4,
            "preferred_cities": ["上海"],
        },
    )

    view_model = runtime.prepare_job_search_profile(
        session_id="job-session",
        overrides={
            "cities": ["深圳"],
            "remote_policy": "remote",
            "salary_min": 45,
            "salary_max": 70,
            "levels": ["高级"],
            "experience_years_min": 5,
            "experience_years_max": 8,
            "education": "硕士",
            "industries": ["AI 应用"],
            "company_sizes": ["500-1000人"],
            "funding_stages": ["D轮及以上"],
            "technical_skills": ["Python", "LLM"],
            "benefits": ["补充医疗"],
            "published_within_days": 7,
            "company_blacklist": ["低效科技"],
            "company_whitelist": ["理想公司"],
        },
    )

    assert view_model["status"] == "ready"
    assert view_model["job_profile"]["technical_skills"] == ["Python", "LLM"]
    assert view_model["hard_filters"] == {
        "cities": ["深圳"],
        "remote_policy": "remote",
        "salary_min": 45,
        "salary_max": 70,
        "levels": ["高级"],
        "experience_years_min": 5,
        "experience_years_max": 8,
        "education": "硕士",
        "company_blacklist": ["低效科技"],
        "company_whitelist": ["理想公司"],
    }
    assert view_model["ranking_preferences"] == {
        "industries": ["AI 应用"],
        "company_sizes": ["500-1000人"],
        "funding_stages": ["D轮及以上"],
        "technical_skills": ["Python", "LLM"],
        "benefits": ["补充医疗"],
        "published_within_days": 7,
    }
    assert runtime.get_session_state("job-session")["job_search_filters"] == {
        "hard_filters": view_model["hard_filters"],
        "ranking_preferences": view_model["ranking_preferences"],
    }


def test_runtime_keeps_remote_policy_pending_when_resume_profile_has_no_remote_preference(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("job-session")
    runtime.session_store.set_state(
        "job-session",
        "resume_profile",
        {
            "name": "Alice",
            "headline": "Python 后端工程师",
            "skills": ["Python"],
            "years_of_experience": 4,
            "preferred_cities": ["上海"],
            "education_level": "本科",
        },
    )

    view_model = runtime.prepare_job_search_profile(session_id="job-session")

    assert view_model["hard_filters"]["remote_policy"] is None
    assert "remote_policy" in view_model["pending_confirmation_fields"]


def test_runtime_saves_false_remote_policy_override_without_falling_back(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("job-session")
    runtime.session_store.set_state(
        "job-session",
        "resume_profile",
        {
            "name": "Alice",
            "headline": "Python 后端工程师",
            "skills": ["Python"],
            "years_of_experience": 4,
            "preferred_cities": ["上海"],
            "remote_preference": "remote",
            "education_level": "本科",
        },
    )

    view_model = runtime.prepare_job_search_profile(session_id="job-session", overrides={"remote_policy": False})

    assert view_model["hard_filters"]["remote_policy"] is False
    assert runtime.get_session_state("job-session")["job_search_filters"]["hard_filters"]["remote_policy"] is False


def test_runtime_saves_empty_overrides_as_cleared_job_search_conditions(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("job-session")
    runtime.session_store.set_state(
        "job-session",
        "resume_profile",
        {
            "name": "Alice",
            "headline": "Python 后端工程师",
            "skills": ["Python", "Django"],
            "years_of_experience": 4,
            "preferred_cities": ["上海"],
            "remote_preference": "hybrid",
            "education_level": "本科",
            "preferred_industries": ["企业服务"],
            "preferred_benefits": ["弹性工作"],
        },
    )

    view_model = runtime.prepare_job_search_profile(
        session_id="job-session",
        overrides={
            "cities": [],
            "remote_policy": "",
            "technical_skills": [],
            "industries": [],
            "benefits": [],
            "education": None,
        },
    )

    assert view_model["hard_filters"]["cities"] == []
    assert view_model["hard_filters"]["remote_policy"] == ""
    assert view_model["hard_filters"]["education"] is None
    assert view_model["ranking_preferences"]["technical_skills"] == []
    assert view_model["ranking_preferences"]["industries"] == []
    assert view_model["ranking_preferences"]["benefits"] == []
    assert runtime.get_session_state("job-session")["job_search_profile"] == view_model


def test_runtime_job_search_profile_state_contains_all_job_002_override_dimensions(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_prep_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("job-session")
    runtime.session_store.set_state("job-session", "resume_profile", {"name": "Alice", "headline": "后端工程师"})

    view_model = runtime.prepare_job_search_profile(session_id="job-session")

    assert set(view_model["hard_filters"]) == {
        "cities",
        "remote_policy",
        "salary_min",
        "salary_max",
        "levels",
        "experience_years_min",
        "experience_years_max",
        "education",
        "company_blacklist",
        "company_whitelist",
    }
    assert set(view_model["ranking_preferences"]) == {
        "industries",
        "company_sizes",
        "funding_stages",
        "technical_skills",
        "benefits",
        "published_within_days",
    }
    assert set(view_model["job_profile"]["search_preferences"]) == {
        "cities",
        "remote_policy",
        "salary_min",
        "salary_max",
        "levels",
        "experience_years_min",
        "experience_years_max",
        "education",
        "industries",
        "company_sizes",
        "funding_stages",
        "technical_skills",
        "benefits",
        "published_within_days",
        "company_blacklist",
        "company_whitelist",
    }


def test_job_platform_fake_adapter_simulates_successful_readonly_search() -> None:
    from dataclasses import asdict

    from interview_agent.job_platform_adapters import (
        FakeJobPlatformAdapter,
        JobSearchRequest,
        StandardJob,
    )

    fake_job = StandardJob(
        platform="boss",
        platform_job_id="boss-001",
        title="Python 后端工程师",
        company_name="Example",
        location="上海",
        remote_policy="hybrid",
        salary_range="35k-50k",
        level="高级",
        experience_requirement="5年",
        education_requirement="本科",
        industry="AI 工具",
        company_size="100-500人",
        funding_stage="B轮",
        tech_stack=["Python", "PostgreSQL"],
        benefits=["五险一金"],
        published_at="2026-06-10T09:00:00+00:00",
        detail_url="https://example.com/boss/jobs/001",
        jd_text="负责后端服务",
        collected_at="2026-06-10T09:05:00+00:00",
        field_confidence={"salary_range": "high"},
    )
    adapter = FakeJobPlatformAdapter(platform="boss", jobs=[fake_job])

    result = adapter.search_jobs(
        JobSearchRequest(
            job_profile={"target_roles": ["后端工程师"], "technical_skills": ["Python"]},
            hard_filters={"cities": ["上海"]},
            ranking_preferences={"technical_skills": ["Python"]},
            keyword="后端工程师 Python",
        )
    )

    assert result.status == "success"
    assert result.jobs == [fake_job]
    assert adapter.collect_job_list(result.search_id) == [fake_job]
    assert adapter.read_job_detail("boss-001") == fake_job
    assert adapter.is_already_applied("boss-001") is False
    assert _contains_sensitive_adapter_payload(asdict(result)) is False


def test_job_platform_fake_adapter_simulates_required_platform_errors() -> None:
    from interview_agent.job_platform_adapters import (
        FakeJobPlatformAdapter,
        JobSearchRequest,
        PlatformAdapterError,
        PlatformAdapterErrorType,
    )

    for error_type in [
        PlatformAdapterErrorType.LOGIN_EXPIRED,
        PlatformAdapterErrorType.CAPTCHA_REQUIRED,
        PlatformAdapterErrorType.RATE_LIMITED,
        PlatformAdapterErrorType.PAGE_STRUCTURE_CHANGED,
    ]:
        adapter = FakeJobPlatformAdapter(
            platform="lagou",
            search_error=PlatformAdapterError(
                error_type=error_type,
                platform="lagou",
                stage="search",
                message=f"{error_type.value} during search",
            ),
        )

        result = adapter.search_jobs(
            JobSearchRequest(
                job_profile={"target_roles": ["后端工程师"]},
                hard_filters={},
                ranking_preferences={},
                keyword="后端工程师",
            )
        )

        assert result.status == "failed"
        assert result.errors[0].error_type is error_type
        assert result.errors[0].platform == "lagou"
        assert result.jobs == []


def test_job_platform_fake_adapter_simulates_submission_failure_without_sensitive_payload() -> None:
    from dataclasses import asdict

    from interview_agent.job_platform_adapters import (
        ApplicationSubmissionResult,
        ConfirmationApplicationRequest,
        FakeJobPlatformAdapter,
        PlatformAdapterError,
        PlatformAdapterErrorType,
        StandardJob,
    )

    fake_job = StandardJob(
        platform="liepin",
        platform_job_id="liepin-001",
        title="平台工程师",
        company_name="Example",
        location="杭州",
        remote_policy=None,
        salary_range=None,
        level=None,
        experience_requirement=None,
        education_requirement=None,
        industry=None,
        company_size=None,
        funding_stage=None,
        tech_stack=[],
        benefits=[],
        published_at=None,
        detail_url="https://example.com/liepin/jobs/001",
        jd_text="负责平台建设",
        collected_at="2026-06-10T10:05:00+00:00",
        field_confidence={"salary_range": "missing"},
    )
    adapter = FakeJobPlatformAdapter(
        platform="liepin",
        jobs=[fake_job],
        submit_results={
            "liepin-001": ApplicationSubmissionResult(
                platform="liepin",
                platform_job_id="liepin-001",
                status="failed",
                error=PlatformAdapterError(
                    error_type=PlatformAdapterErrorType.BUTTON_UNAVAILABLE,
                    platform="liepin",
                    stage="submit",
                    message="投递按钮不可用",
                ),
                platform_message="按钮不可用",
                duplicate_detected=False,
            )
        },
    )

    result = adapter.submit_application(
        ConfirmationApplicationRequest(
            confirmation_batch_id="batch-001",
            job=fake_job,
            application_message="您好，我对该岗位感兴趣。",
            confirmed=True,
        )
    )

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.error_type is PlatformAdapterErrorType.BUTTON_UNAVAILABLE
    assert _contains_sensitive_adapter_payload(asdict(result)) is False


def _contains_sensitive_adapter_payload(value: object) -> bool:
    sensitive_markers = ("cookie", "token", "session", "password", "credential", "account_id")
    return any(marker in _flatten_text(value).lower() for marker in sensitive_markers)


def _flatten_text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for pair in value.items() for item in pair)
    if isinstance(value, list | tuple | set):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


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
    write_prepared_mock_materials(runtime, "mock-session")

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


def test_runtime_start_mock_interview_passes_question_type_to_generation(tmp_path: Path) -> None:
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
    write_prepared_mock_materials(runtime, "mock-session")

    runtime.start_mock_interview(
        session_id="mock-session",
        target_role="后端工程师",
        question_count=2,
        followup_rounds=1,
        question_type="项目深挖",
    )

    mock_state = runtime.get_session_state("mock-session")["mock_interview_state"]
    assert mock_state["question_type"] == "项目深挖"


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
    write_prepared_mock_materials(runtime, "mock-session")

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


def test_runtime_start_mock_interview_requires_prepared_materials(tmp_path: Path) -> None:
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

    view_model = runtime.start_mock_interview(
        session_id="mock-session",
        target_role="后端工程师",
    )

    assert view_model == {
        "session_id": "mock-session",
        "status": "failed",
        "error_message": "请先导入简历，并完成面试准备。",
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


def test_runtime_start_mock_interview_accepts_resume_only_prepared_materials(tmp_path: Path) -> None:
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

    assert view_model["status"] == "ready_for_answer"
    assert view_model["current_prompt"]["text"] == "介绍你最近一次线上延迟排查。"


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
    write_prepared_mock_materials(runtime, "mock-session")
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
    write_prepared_mock_materials(runtime, "mock-session")
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
    write_prepared_mock_materials(runtime, "mock-session")
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
    write_prepared_mock_materials(runtime, "mock-session")
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


def build_empty_algorithm_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="algorithm_practice",
                description="Generate empty algorithm practice.",
                required_inputs=(),
                optional_inputs=("practice_topic", "difficulty", "question_count"),
                outputs=("practice_set",),
                handler=empty_algorithm_practice_handler,
            ),
        ]
    )


def build_structured_algorithm_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="algorithm_practice",
                description="Generate structured algorithm practice.",
                required_inputs=(),
                optional_inputs=("practice_topic", "difficulty", "question_count"),
                outputs=("practice_set",),
                handler=structured_algorithm_practice_handler,
            ),
        ]
    )


def build_failing_algorithm_generation_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="algorithm_practice",
                description="Algorithm generation must not run when pregenerated bank exists.",
                required_inputs=(),
                optional_inputs=("practice_topic", "difficulty", "question_count"),
                outputs=("practice_set",),
                handler=failing_algorithm_generation_handler,
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


def build_synonym_prep_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="resume_parse",
                description="Parse resume with alternative field names.",
                required_inputs=("resume_text",),
                optional_inputs=(),
                outputs=("resume_profile", "candidate_profile"),
                handler=synonym_resume_parse_handler,
            ),
            NodeSpec(
                name="jd_parse",
                description="Parse JD with alternative field names.",
                required_inputs=("jd_text",),
                optional_inputs=(),
                outputs=("jd_requirements",),
                handler=synonym_jd_parse_handler,
            ),
            NodeSpec(
                name="jd_match",
                description="Match resume and JD with alternative field names.",
                required_inputs=("resume_profile", "jd_requirements"),
                optional_inputs=(),
                outputs=("match_report",),
                handler=synonym_jd_match_handler,
            ),
        ]
    )


def build_flaky_resume_prep_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="resume_parse",
                description="Parse resume once.",
                required_inputs=("resume_text",),
                optional_inputs=(),
                outputs=("resume_profile", "candidate_profile"),
                handler=flaky_resume_parse_handler,
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


def build_detailed_resume_prep_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="resume_parse",
                description="Parse detailed resume.",
                required_inputs=("resume_text",),
                optional_inputs=(),
                outputs=("resume_profile", "candidate_profile"),
                handler=detailed_resume_parse_handler,
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


def build_nested_chinese_prep_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="resume_parse",
                description="Parse nested Chinese resume.",
                required_inputs=("resume_text",),
                optional_inputs=(),
                outputs=("resume_profile", "candidate_profile"),
                handler=nested_chinese_resume_parse_handler,
            ),
            NodeSpec(
                name="jd_parse",
                description="Parse nested Chinese JD.",
                required_inputs=("jd_text",),
                optional_inputs=(),
                outputs=("jd_requirements",),
                handler=nested_chinese_jd_parse_handler,
            ),
            NodeSpec(
                name="jd_match",
                description="Match nested Chinese materials.",
                required_inputs=("resume_profile", "jd_requirements"),
                optional_inputs=(),
                outputs=("match_report",),
                handler=nested_chinese_jd_match_handler,
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
                optional_inputs=("jd_requirements", "question_count", "question_type"),
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
                optional_inputs=("jd_requirements", "question_count", "question_type"),
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


def write_prepared_mock_materials(runtime: object, session_id: str) -> None:
    runtime.session_store.set_state(session_id, "candidate_profile", {"name": "Alice"})
    runtime.session_store.set_state(session_id, "jd_requirements", {"role": "后端工程师"})


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


def structured_algorithm_practice_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    assert context.services["source"] == "fake"
    practice_topic = str(inputs.get("practice_topic", "算法"))
    return {
        "practice_set": {
            "topic": practice_topic,
            "difficulty": "medium",
            "exercises": [
                {
                    "title": "最长递增子序列",
                    "prompt": "返回最长严格递增子序列长度。",
                    "tags": ["动态规划", "数组"],
                    "constraints": ["1 <= nums.length <= 2500"],
                    "examples": ["输入 [10,9,2,5,3,7,101,18]，输出 4"],
                    "edge_cases": ["空数组返回 0"],
                },
                {
                    "title": "零钱兑换",
                    "description": "计算凑成金额所需的最少硬币数。",
                    "tags": ["动态规划"],
                },
            ],
        }
    }


def empty_algorithm_practice_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    return {"practice_set": {"topic": "链表", "difficulty": "easy", "exercises": []}}


def failing_algorithm_generation_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    raise AssertionError("algorithm_practice node must not generate exercises when pregenerated bank exists")


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


def flaky_resume_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del inputs
    invocation_count = int(context.services.get("resume_parse_invocation_count", 0)) + 1
    context.services["resume_parse_invocation_count"] = invocation_count
    if invocation_count > 1:
        raise RuntimeError("resume parser should not run again when importing JD")
    return resume_parse_handler(context, {})


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


def synonym_resume_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    profile = {
        "name": "Alice",
        "summary": "后端检索工程师，负责 SLA 和召回评估",
        "core_skills": ["Python", "检索系统", "SLA"],
    }
    return {"resume_profile": profile, "candidate_profile": profile}


def detailed_resume_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    profile = {
        "name": "Alice",
        "headline": "Golang 后端工程师，6 年服务端与稳定性治理经验",
        "skills": ["Golang", "支付链路", "MySQL", "Redis"],
        "projects": ["主导交易服务重构"],
        "project_experience": [
            {
                "project_name": "CDN 授权版",
                "responsibilities": ["P95 延迟从 900ms 降到 180ms"],
            }
        ],
        "achievements": ["P95 延迟从 900ms 降到 180ms"],
        "responsibilities": ["SLA 治理", "容量压测"],
    }
    return {"resume_profile": profile, "candidate_profile": profile}


def nested_chinese_resume_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    profile = {
        "basic_info": {
            "name": "罗天",
            "primary_position": "Golang",
            "years_of_experience": 6,
            "education_level": "本科",
        },
        "skills": ["Golang", "MySQL"],
    }
    return {"resume_profile": profile, "candidate_profile": profile}


def nested_chinese_jd_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    return {
        "jd_requirements": {
            "岗位名称": "golang开发工程师",
            "岗位职责": ["负责后端设计开发"],
            "任职资格": {
                "技能要求": ["Golang", "高并发"],
                "优先条件": ["分布式"],
            },
        }
    }


def nested_chinese_jd_match_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    return {
        "match_report": {
            "overall_match_score": 92,
            "strengths": ["Golang 后端经验充足"],
            "potential_gaps": ["出差适配不明确"],
            "interview_focus_suggestions": ["追问高并发项目"],
        }
    }


def synonym_jd_parse_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context, inputs
    return {
        "jd_requirements": {
            "title": "后端工程师",
            "requirements": ["Python", "检索链路", "稳定性"],
        }
    }


def synonym_jd_match_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    assert inputs["resume_profile"]["name"] == "Alice"
    assert inputs["jd_requirements"]["title"] == "后端工程师"
    return {
        "match_report": {
            "score": 88,
            "matched_points": ["检索经验贴合", "Python 服务经验"],
            "weaknesses": ["压测案例不足"],
            "interview_focus": ["SLA 取舍", "召回评估"],
        }
    }


def mock_runtime_question_generate_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    assert inputs["candidate_profile"] == {"name": "Alice"}
    assert inputs["target_role"] == "后端工程师"
    assert inputs["question_count"] == 2
    assert inputs["question_type"] in {"行为面试", "项目深挖"}
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
