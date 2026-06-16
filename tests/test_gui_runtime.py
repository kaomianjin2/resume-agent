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


def test_job_platform_adapter_error_redacts_sensitive_message_and_url_summary() -> None:
    from dataclasses import asdict

    from interview_agent.job_platform_adapters import (
        FakeJobPlatformAdapter,
        JobSearchRequest,
        PlatformAdapterError,
        PlatformAdapterErrorType,
    )

    adapter = FakeJobPlatformAdapter(
        platform="boss",
        search_error=PlatformAdapterError(
            error_type=PlatformAdapterErrorType.LOGIN_EXPIRED,
            platform="boss",
            stage="search",
            message="登录失败: account_id=alice 手机号 13800000000 验证码 123456",
            page_url="https://example.com/jobs?token=secret&session_id=chrome-secret&query=python",
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
    assert result.errors[0].message == "浏览器自动化错误已脱敏"
    assert result.errors[0].page_url == "https://example.com/jobs"
    assert _contains_sensitive_adapter_payload(asdict(result)) is False


def test_job_platform_adapter_error_summary_does_not_expose_field_name() -> None:
    from dataclasses import asdict

    from interview_agent.job_platform_adapters import (
        FakeJobPlatformAdapter,
        JobSearchRequest,
        PlatformAdapterError,
        PlatformAdapterErrorType,
    )

    adapter = FakeJobPlatformAdapter(
        platform="boss",
        search_error=PlatformAdapterError(
            error_type=PlatformAdapterErrorType.CAPTCHA_REQUIRED,
            platform="boss",
            stage="search",
            message="需要人工处理",
            page_url="https://example.com/jobs?query=python",
            field_name="account_id",
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
    assert result.errors[0].field_name is None
    assert _contains_sensitive_adapter_payload(asdict(result)) is False


def test_job_platform_adapter_sanitizes_sensitive_submit_result_without_raising() -> None:
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
        platform_job_id="liepin-sensitive",
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
        tech_stack=["OAuth token bucket"],
        benefits=[],
        published_at=None,
        detail_url="https://example.com/liepin/jobs/sensitive",
        jd_text="负责 auth service 和 mobile backend",
        collected_at="2026-06-10T10:05:00+00:00",
        field_confidence={"session_id": "业务追踪字段"},
    )
    adapter = FakeJobPlatformAdapter(
        platform="liepin",
        jobs=[fake_job],
        submit_results={
            "liepin-sensitive": ApplicationSubmissionResult(
                platform="liepin",
                platform_job_id="liepin-sensitive",
                status="failed",
                error=PlatformAdapterError(
                    error_type=PlatformAdapterErrorType.LOGIN_EXPIRED,
                    platform="liepin",
                    stage="submit",
                    message="cookie=sid-secret token=secret 手机号 13800000000",
                    page_url="https://example.com/apply?token=secret&session_id=chrome-secret",
                    field_name="cookie",
                ),
                platform_message="验证码 123456",
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
    assert result.error.error_type is PlatformAdapterErrorType.LOGIN_EXPIRED
    assert result.error.message == "浏览器自动化错误已脱敏"
    assert result.error.page_url == "https://example.com/apply"
    assert result.error.field_name is None
    assert result.platform_message == "浏览器自动化错误已脱敏"
    assert _contains_sensitive_adapter_payload(asdict(result)) is False


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


def test_job_platform_contract_parses_fixture_list_and_detail_fields() -> None:
    from dataclasses import asdict

    from interview_agent.job_platform_adapters import (
        parse_job_detail_fixture,
        parse_job_list_fixture,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"

    jobs = parse_job_list_fixture((fixture_dir / "list.html").read_text())
    detail = parse_job_detail_fixture((fixture_dir / "detail.html").read_text())

    assert len(jobs) == 1
    expected_list_job = {
        "platform": "boss",
        "platform_job_id": "boss-frontend-001",
        "title": "资深后端工程师",
        "company_name": "示例科技",
        "location": "上海",
        "remote_policy": "hybrid",
        "salary_range": "35k-50k",
        "level": "高级",
        "experience_requirement": "5年",
        "education_requirement": "本科",
        "industry": "AI 工具",
        "company_size": "100-500人",
        "funding_stage": "B轮",
        "tech_stack": ["Python", "PostgreSQL", "FastAPI"],
        "benefits": ["五险一金", "弹性工作"],
        "published_at": "2026-06-10T09:00:00+08:00",
        "detail_url": "https://example.com/boss/jobs/boss-frontend-001",
        "jd_text": "负责后端服务与平台稳定性。",
        "collected_at": "2026-06-10T09:05:00+08:00",
        "field_confidence": {
            "platform": "fixture",
            "platform_job_id": "fixture",
            "title": "fixture",
            "company_name": "fixture",
            "location": "fixture",
            "remote_policy": "fixture",
            "salary_range": "fixture",
            "level": "fixture",
            "experience_requirement": "fixture",
            "education_requirement": "fixture",
            "industry": "fixture",
            "company_size": "fixture",
            "funding_stage": "fixture",
            "tech_stack": "fixture",
            "benefits": "fixture",
            "published_at": "fixture",
            "detail_url": "fixture",
            "jd_text": "fixture",
            "collected_at": "fixture",
        },
    }
    expected_detail_job = {
        **expected_list_job,
        "jd_text": "负责后端服务与平台稳定性。 需要维护 PostgreSQL 查询性能并建设 FastAPI 服务。",
        "collected_at": "2026-06-10T09:06:00+08:00",
    }

    assert asdict(jobs[0]) == expected_list_job
    assert asdict(detail) == expected_detail_job


def test_job_platform_contract_preserves_nested_field_text() -> None:
    from interview_agent.job_platform_adapters import parse_job_detail_fixture

    detail = parse_job_detail_fixture(
        """
        <article data-job-detail>
          <span data-field="platform">boss</span>
          <span data-field="platform_job_id">boss-nested-001</span>
          <h1 data-field="title">后端工程师</h1>
          <span data-field="company_name">示例科技</span>
          <span data-field="location">上海</span>
          <a data-field="detail_url" href="https://example.com/jobs/nested">详情</a>
          <section data-field="jd_text">
            负责核心服务 <strong>稳定性</strong> 和 <span>性能优化</span> 建设。
          </section>
          <time data-field="collected_at">2026-06-10T09:06:00+08:00</time>
        </article>
        """
    )

    assert detail.jd_text == "负责核心服务 稳定性 和 性能优化 建设。"


def test_job_platform_contract_parses_multiple_list_cards_without_cross_contamination() -> None:
    from interview_agent.job_platform_adapters import parse_job_list_fixture

    jobs = parse_job_list_fixture(
        """
        <section data-job-list>
          <article data-job-card>
            <span data-field="platform">boss</span>
            <span data-field="platform_job_id">boss-list-001</span>
            <h2 data-field="title">后端工程师</h2>
            <span data-field="company_name">第一家公司</span>
            <span data-field="location">上海</span>
            <span data-field="tech_stack">Python,PostgreSQL</span>
            <a data-field="detail_url" href="https://example.com/jobs/001">详情</a>
            <p data-field="jd_text">负责服务端。</p>
            <time data-field="collected_at">2026-06-10T09:05:00+08:00</time>
          </article>
          <article data-job-card>
            <span data-field="platform">boss</span>
            <span data-field="platform_job_id">boss-list-002</span>
            <h2 data-field="title">平台工程师</h2>
            <span data-field="company_name">第二家公司</span>
            <span data-field="location">杭州</span>
            <span data-field="benefits">补充医疗,弹性工作</span>
            <a data-field="detail_url" href="https://example.com/jobs/002">详情</a>
            <p data-field="jd_text">负责平台建设。</p>
            <time data-field="collected_at">2026-06-10T09:08:00+08:00</time>
          </article>
        </section>
        """
    )

    assert [job.platform_job_id for job in jobs] == ["boss-list-001", "boss-list-002"]
    assert jobs[0].company_name == "第一家公司"
    assert jobs[0].tech_stack == ["Python", "PostgreSQL"]
    assert jobs[0].benefits == []
    assert jobs[0].remote_policy is None
    assert jobs[0].field_confidence["tech_stack"] == "fixture"
    assert jobs[0].field_confidence["benefits"] == "missing"
    assert jobs[0].field_confidence["remote_policy"] == "missing"
    assert jobs[1].company_name == "第二家公司"
    assert jobs[1].tech_stack == []
    assert jobs[1].benefits == ["补充医疗", "弹性工作"]
    assert jobs[1].field_confidence["tech_stack"] == "missing"
    assert jobs[1].field_confidence["benefits"] == "fixture"


def test_job_platform_contract_reports_missing_required_fixture_field() -> None:
    import pytest

    from interview_agent.job_platform_adapters import parse_job_detail_fixture

    with pytest.raises(ValueError, match="company_name"):
        parse_job_detail_fixture(
            """
            <article data-job-detail>
              <span data-field="platform">boss</span>
              <span data-field="platform_job_id">boss-missing-001</span>
              <h1 data-field="title">后端工程师</h1>
              <span data-field="location">上海</span>
              <a data-field="detail_url" href="https://example.com/jobs/missing">详情</a>
              <section data-field="jd_text">负责后端服务。</section>
              <time data-field="collected_at">2026-06-10T09:06:00+08:00</time>
            </article>
            """
        )


def test_job_platform_contract_classifies_fixture_error_states() -> None:
    from interview_agent.job_platform_adapters import (
        PlatformAdapterErrorType,
        classify_job_platform_fixture_error,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    expected_error_types = {
        "login_expired.html": PlatformAdapterErrorType.LOGIN_EXPIRED,
        "captcha.html": PlatformAdapterErrorType.CAPTCHA_REQUIRED,
        "button_unavailable.html": PlatformAdapterErrorType.BUTTON_UNAVAILABLE,
        "already_applied.html": PlatformAdapterErrorType.DUPLICATE_APPLICATION,
    }

    for fixture_name, expected_error_type in expected_error_types.items():
        error = classify_job_platform_fixture_error(
            platform="boss",
            stage="submit",
            html=(fixture_dir / fixture_name).read_text(),
        )

        assert error is not None
        assert error.error_type is expected_error_type
        assert error.platform == "boss"
        assert error.stage == "submit"
        assert _contains_sensitive_adapter_payload(error.__dict__) is False


def test_job_platform_contract_rejects_unconfirmed_submission_without_sensitive_payload() -> None:
    from dataclasses import asdict

    from interview_agent.job_platform_adapters import (
        ConfirmationApplicationRequest,
        FakeJobPlatformAdapter,
        PlatformAdapterErrorType,
        parse_job_detail_fixture,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    job = parse_job_detail_fixture((fixture_dir / "detail.html").read_text())
    adapter = FakeJobPlatformAdapter(platform="boss", jobs=[job])

    result = adapter.submit_application(
        ConfirmationApplicationRequest(
            confirmation_batch_id="batch-unconfirmed",
            job=job,
            application_message="您好，我对该岗位感兴趣。",
            confirmed=False,
        )
    )

    assert result.status == "skipped"
    assert result.status != "submitted"
    assert result.error is not None
    assert result.error.error_type is PlatformAdapterErrorType.BUTTON_UNAVAILABLE
    assert _contains_sensitive_adapter_payload(asdict(result)) is False


def test_boss_readonly_adapter_searches_list_and_reads_full_detail() -> None:
    from interview_agent.job_platform_adapters import (
        BossReadonlyJobPlatformAdapter,
        JobSearchRequest,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    adapter = BossReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "boss_list.html").read_text(),
        detail_html_by_job_id={
            "boss-backend-001": (fixture_dir / "boss_detail.html").read_text(),
        },
    )

    result = adapter.search_jobs(
        JobSearchRequest(
            job_profile={"target_roles": ["后端工程师"]},
            hard_filters={"cities": ["上海"]},
            ranking_preferences={"technical_skills": ["Python"]},
            keyword="后端工程师 Python",
        )
    )

    assert result.status == "success"
    assert result.platform == "boss"
    assert [job.platform_job_id for job in result.jobs] == ["boss-backend-001"]

    listed_jobs = adapter.collect_job_list(result.search_id)
    detail = adapter.read_job_detail("boss-backend-001")

    assert listed_jobs[0].title == "BOSS 后端工程师"
    assert listed_jobs[0].company_name == "直聘样例科技"
    assert listed_jobs[0].salary_range == "30k-45k"
    assert listed_jobs[0].tech_stack == ["Python", "FastAPI", "PostgreSQL"]
    assert detail.jd_text == "负责 BOSS 渠道后端服务。 深入建设岗位推荐、搜索和数据服务。"
    assert detail.field_confidence["salary_range"] == "fixture"
    assert adapter.is_already_applied("boss-backend-001") is False


def test_boss_readonly_adapter_marks_missing_optional_fields_low_confidence() -> None:
    from interview_agent.job_platform_adapters import BossReadonlyJobPlatformAdapter, JobSearchRequest

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    adapter = BossReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "boss_list_missing_fields.html").read_text(),
        detail_html_by_job_id={
            "boss-low-confidence-001": (fixture_dir / "boss_detail.html").read_text(),
        },
    )

    result = adapter.search_jobs(
        JobSearchRequest(
            job_profile={},
            hard_filters={},
            ranking_preferences={},
            keyword="后端工程师",
        )
    )

    assert result.status == "success"
    assert result.jobs[0].salary_range is None
    assert result.jobs[0].company_size is None
    assert result.jobs[0].field_confidence["salary_range"] == "low_confidence"
    assert result.jobs[0].field_confidence["company_size"] == "low_confidence"


def test_boss_readonly_adapter_classifies_platform_states_and_already_applied() -> None:
    from interview_agent.job_platform_adapters import (
        BossReadonlyJobPlatformAdapter,
        JobSearchRequest,
        PlatformAdapterErrorType,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    request = JobSearchRequest(job_profile={}, hard_filters={}, ranking_preferences={}, keyword="后端工程师")
    expected_errors = {
        "boss_login_expired.html": PlatformAdapterErrorType.LOGIN_EXPIRED,
        "boss_captcha.html": PlatformAdapterErrorType.CAPTCHA_REQUIRED,
        "boss_rate_limited.html": PlatformAdapterErrorType.RATE_LIMITED,
        "boss_structure_changed.html": PlatformAdapterErrorType.PAGE_STRUCTURE_CHANGED,
    }

    for fixture_name, expected_error_type in expected_errors.items():
        adapter = BossReadonlyJobPlatformAdapter(
            list_html=(fixture_dir / fixture_name).read_text(),
            detail_html_by_job_id={},
        )

        result = adapter.search_jobs(request)

        assert result.status == "failed"
        assert result.errors[0].error_type is expected_error_type
        assert result.errors[0].platform == "boss"
        assert result.errors[0].stage == "search"
        assert _contains_sensitive_adapter_payload(result.errors[0].__dict__) is False

    applied_adapter = BossReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "boss_list.html").read_text(),
        detail_html_by_job_id={"boss-backend-001": (fixture_dir / "boss_detail.html").read_text()},
        state_html_by_job_id={"boss-backend-001": (fixture_dir / "boss_already_applied.html").read_text()},
    )

    assert applied_adapter.is_already_applied("boss-backend-001") is True


def test_boss_readonly_adapter_propagates_detail_and_state_platform_errors() -> None:
    import pytest

    from interview_agent.job_platform_adapters import (
        BossReadonlyJobPlatformAdapter,
        PlatformAdapterError,
        PlatformAdapterErrorType,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    expected_errors = {
        "boss_login_expired.html": PlatformAdapterErrorType.LOGIN_EXPIRED,
        "boss_captcha.html": PlatformAdapterErrorType.CAPTCHA_REQUIRED,
        "boss_rate_limited.html": PlatformAdapterErrorType.RATE_LIMITED,
        "boss_structure_changed.html": PlatformAdapterErrorType.PAGE_STRUCTURE_CHANGED,
    }

    for fixture_name, expected_error_type in expected_errors.items():
        detail_adapter = BossReadonlyJobPlatformAdapter(
            list_html=(fixture_dir / "boss_list.html").read_text(),
            detail_html_by_job_id={"boss-backend-001": (fixture_dir / fixture_name).read_text()},
        )
        state_adapter = BossReadonlyJobPlatformAdapter(
            list_html=(fixture_dir / "boss_list.html").read_text(),
            detail_html_by_job_id={"boss-backend-001": (fixture_dir / "boss_detail.html").read_text()},
            state_html_by_job_id={"boss-backend-001": (fixture_dir / fixture_name).read_text()},
        )

        with pytest.raises(PlatformAdapterError) as detail_error:
            detail_adapter.read_job_detail("boss-backend-001")
        with pytest.raises(PlatformAdapterError) as state_error:
            state_adapter.is_already_applied("boss-backend-001")

        assert detail_error.value.error_type is expected_error_type
        assert detail_error.value.stage == "detail"
        assert state_error.value.error_type is expected_error_type
        assert state_error.value.stage == "state"


def test_job_collection_orchestrator_records_boss_detail_platform_errors() -> None:
    from interview_agent.job_collection import JobCollectionOrchestrator
    from interview_agent.job_platform_adapters import BossReadonlyJobPlatformAdapter

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    adapter = BossReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "boss_list.html").read_text(),
        detail_html_by_job_id={"boss-backend-001": (fixture_dir / "boss_rate_limited.html").read_text()},
    )
    orchestrator = JobCollectionOrchestrator({"boss": adapter})

    result = orchestrator.collect(
        collection_task_id="collection-boss-detail-error-001",
        platforms=["boss"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={"cities": ["上海"]},
        ranking_preferences={"technical_skills": ["Python"]},
        keyword="后端工程师 Python",
    )

    assert result["status"] == "backoff"
    assert result["platform_progress"]["boss"]["status"] == "backoff"
    assert result["platform_progress"]["boss"]["failure_reason"] == "rate_limited"


def test_boss_readonly_adapter_never_submits_application() -> None:
    from dataclasses import asdict

    from interview_agent.job_platform_adapters import (
        BossReadonlyJobPlatformAdapter,
        ConfirmationApplicationRequest,
        PlatformAdapterErrorType,
        parse_job_detail_fixture,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    job = parse_job_detail_fixture((fixture_dir / "boss_detail.html").read_text())
    adapter = BossReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "boss_list.html").read_text(),
        detail_html_by_job_id={"boss-backend-001": (fixture_dir / "boss_detail.html").read_text()},
    )

    result = adapter.submit_application(
        ConfirmationApplicationRequest(
            confirmation_batch_id="batch-confirmed",
            job=job,
            application_message="您好，我对该岗位感兴趣。",
            confirmed=True,
        )
    )

    assert result.status == "skipped"
    assert result.status != "submitted"
    assert result.submitted_at is None
    assert result.error is not None
    assert result.error.error_type is PlatformAdapterErrorType.BUTTON_UNAVAILABLE
    assert _contains_sensitive_adapter_payload(asdict(result)) is False


def test_job_collection_orchestrator_collects_with_boss_readonly_adapter() -> None:
    from interview_agent.job_collection import JobCollectionOrchestrator
    from interview_agent.job_platform_adapters import BossReadonlyJobPlatformAdapter

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    adapter = BossReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "boss_list.html").read_text(),
        detail_html_by_job_id={"boss-backend-001": (fixture_dir / "boss_detail.html").read_text()},
    )
    orchestrator = JobCollectionOrchestrator({"boss": adapter})

    result = orchestrator.collect(
        collection_task_id="collection-boss-readonly-001",
        platforms=["boss"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={"cities": ["上海"]},
        ranking_preferences={"technical_skills": ["Python"]},
        keyword="后端工程师 Python",
    )

    assert result["status"] == "success"
    assert [job.platform_job_id for job in result["jobs"]] == ["boss-backend-001"]
    assert result["jobs"][0].jd_text == "负责 BOSS 渠道后端服务。 深入建设岗位推荐、搜索和数据服务。"
    assert result["platform_progress"]["boss"]["status"] == "completed"


def test_lagou_readonly_adapter_searches_list_and_reads_full_detail() -> None:
    from interview_agent.job_platform_adapters import (
        LagouReadonlyJobPlatformAdapter,
        JobSearchRequest,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    adapter = LagouReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "lagou_list.html").read_text(),
        detail_html_by_job_id={
            "lagou-backend-001": (fixture_dir / "lagou_detail.html").read_text(),
        },
    )

    result = adapter.search_jobs(
        JobSearchRequest(
            job_profile={"target_roles": ["后端工程师"]},
            hard_filters={"cities": ["北京"]},
            ranking_preferences={"technical_skills": ["Go"]},
            keyword="后端工程师 Go",
        )
    )

    assert result.status == "success"
    assert result.platform == "lagou"
    assert [job.platform_job_id for job in result.jobs] == ["lagou-backend-001"]

    listed_jobs = adapter.collect_job_list(result.search_id)
    detail = adapter.read_job_detail("lagou-backend-001")

    assert listed_jobs[0].title == "拉勾后端工程师"
    assert listed_jobs[0].company_name == "拉勾样例科技"
    assert listed_jobs[0].salary_range == "25k-40k"
    assert listed_jobs[0].tech_stack == ["Go", "Kubernetes", "MySQL"]
    assert detail.jd_text == "负责拉勾渠道后端微服务开发。 参与岗位搜索、推荐系统与数据平台建设。"
    assert detail.field_confidence["salary_range"] == "fixture"
    assert adapter.is_already_applied("lagou-backend-001") is False


def test_lagou_readonly_adapter_marks_missing_optional_fields_low_confidence() -> None:
    from interview_agent.job_platform_adapters import LagouReadonlyJobPlatformAdapter, JobSearchRequest

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    adapter = LagouReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "lagou_list_missing_fields.html").read_text(),
        detail_html_by_job_id={
            "lagou-low-confidence-001": (fixture_dir / "lagou_detail.html").read_text(),
        },
    )

    result = adapter.search_jobs(
        JobSearchRequest(
            job_profile={},
            hard_filters={},
            ranking_preferences={},
            keyword="后端工程师",
        )
    )

    assert result.status == "success"
    assert result.jobs[0].salary_range is None
    assert result.jobs[0].company_size is None
    assert result.jobs[0].field_confidence["salary_range"] == "low_confidence"
    assert result.jobs[0].field_confidence["company_size"] == "low_confidence"


def test_lagou_readonly_adapter_classifies_platform_states_and_already_applied() -> None:
    from interview_agent.job_platform_adapters import (
        LagouReadonlyJobPlatformAdapter,
        JobSearchRequest,
        PlatformAdapterErrorType,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    request = JobSearchRequest(job_profile={}, hard_filters={}, ranking_preferences={}, keyword="后端工程师")
    expected_errors = {
        "lagou_login_expired.html": PlatformAdapterErrorType.LOGIN_EXPIRED,
        "lagou_captcha.html": PlatformAdapterErrorType.CAPTCHA_REQUIRED,
        "lagou_rate_limited.html": PlatformAdapterErrorType.RATE_LIMITED,
        "lagou_structure_changed.html": PlatformAdapterErrorType.PAGE_STRUCTURE_CHANGED,
    }

    for fixture_name, expected_error_type in expected_errors.items():
        adapter = LagouReadonlyJobPlatformAdapter(
            list_html=(fixture_dir / fixture_name).read_text(),
            detail_html_by_job_id={},
        )

        result = adapter.search_jobs(request)

        assert result.status == "failed"
        assert result.errors[0].error_type is expected_error_type
        assert result.errors[0].platform == "lagou"
        assert result.errors[0].stage == "search"
        assert _contains_sensitive_adapter_payload(result.errors[0].__dict__) is False

    applied_adapter = LagouReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "lagou_list.html").read_text(),
        detail_html_by_job_id={"lagou-backend-001": (fixture_dir / "lagou_detail.html").read_text()},
        state_html_by_job_id={"lagou-backend-001": (fixture_dir / "lagou_already_applied.html").read_text()},
    )

    assert applied_adapter.is_already_applied("lagou-backend-001") is True


def test_lagou_readonly_adapter_propagates_detail_and_state_platform_errors() -> None:
    import pytest

    from interview_agent.job_platform_adapters import (
        LagouReadonlyJobPlatformAdapter,
        PlatformAdapterError,
        PlatformAdapterErrorType,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    expected_errors = {
        "lagou_login_expired.html": PlatformAdapterErrorType.LOGIN_EXPIRED,
        "lagou_captcha.html": PlatformAdapterErrorType.CAPTCHA_REQUIRED,
        "lagou_rate_limited.html": PlatformAdapterErrorType.RATE_LIMITED,
        "lagou_structure_changed.html": PlatformAdapterErrorType.PAGE_STRUCTURE_CHANGED,
    }

    for fixture_name, expected_error_type in expected_errors.items():
        detail_adapter = LagouReadonlyJobPlatformAdapter(
            list_html=(fixture_dir / "lagou_list.html").read_text(),
            detail_html_by_job_id={"lagou-backend-001": (fixture_dir / fixture_name).read_text()},
        )
        state_adapter = LagouReadonlyJobPlatformAdapter(
            list_html=(fixture_dir / "lagou_list.html").read_text(),
            detail_html_by_job_id={"lagou-backend-001": (fixture_dir / "lagou_detail.html").read_text()},
            state_html_by_job_id={"lagou-backend-001": (fixture_dir / fixture_name).read_text()},
        )

        with pytest.raises(PlatformAdapterError) as detail_error:
            detail_adapter.read_job_detail("lagou-backend-001")
        with pytest.raises(PlatformAdapterError) as state_error:
            state_adapter.is_already_applied("lagou-backend-001")

        assert detail_error.value.error_type is expected_error_type
        assert detail_error.value.stage == "detail"
        assert state_error.value.error_type is expected_error_type
        assert state_error.value.stage == "state"


def test_job_collection_orchestrator_records_lagou_detail_platform_errors() -> None:
    from interview_agent.job_collection import JobCollectionOrchestrator
    from interview_agent.job_platform_adapters import LagouReadonlyJobPlatformAdapter

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    adapter = LagouReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "lagou_list.html").read_text(),
        detail_html_by_job_id={"lagou-backend-001": (fixture_dir / "lagou_rate_limited.html").read_text()},
    )
    orchestrator = JobCollectionOrchestrator({"lagou": adapter})

    result = orchestrator.collect(
        collection_task_id="collection-lagou-detail-error-001",
        platforms=["lagou"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={"cities": ["北京"]},
        ranking_preferences={"technical_skills": ["Go"]},
        keyword="后端工程师 Go",
    )

    assert result["status"] == "backoff"
    assert result["platform_progress"]["lagou"]["status"] == "backoff"
    assert result["platform_progress"]["lagou"]["failure_reason"] == "rate_limited"


def test_lagou_readonly_adapter_never_submits_application() -> None:
    from dataclasses import asdict

    from interview_agent.job_platform_adapters import (
        LagouReadonlyJobPlatformAdapter,
        ConfirmationApplicationRequest,
        PlatformAdapterErrorType,
        parse_job_detail_fixture,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    job = parse_job_detail_fixture((fixture_dir / "lagou_detail.html").read_text())
    adapter = LagouReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "lagou_list.html").read_text(),
        detail_html_by_job_id={"lagou-backend-001": (fixture_dir / "lagou_detail.html").read_text()},
    )

    result = adapter.submit_application(
        ConfirmationApplicationRequest(
            confirmation_batch_id="batch-confirmed",
            job=job,
            application_message="您好，我对该岗位感兴趣。",
            confirmed=True,
        )
    )

    assert result.status == "skipped"
    assert result.status != "submitted"
    assert result.submitted_at is None
    assert result.error is not None
    assert result.error.error_type is PlatformAdapterErrorType.BUTTON_UNAVAILABLE
    assert _contains_sensitive_adapter_payload(asdict(result)) is False


def test_job_collection_orchestrator_collects_with_lagou_readonly_adapter() -> None:
    from interview_agent.job_collection import JobCollectionOrchestrator
    from interview_agent.job_platform_adapters import LagouReadonlyJobPlatformAdapter

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    adapter = LagouReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "lagou_list.html").read_text(),
        detail_html_by_job_id={"lagou-backend-001": (fixture_dir / "lagou_detail.html").read_text()},
    )
    orchestrator = JobCollectionOrchestrator({"lagou": adapter})

    result = orchestrator.collect(
        collection_task_id="collection-lagou-readonly-001",
        platforms=["lagou"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={"cities": ["北京"]},
        ranking_preferences={"technical_skills": ["Go"]},
        keyword="后端工程师 Go",
    )

    assert result["status"] == "success"
    assert [job.platform_job_id for job in result["jobs"]] == ["lagou-backend-001"]
    assert result["jobs"][0].jd_text == "负责拉勾渠道后端微服务开发。 参与岗位搜索、推荐系统与数据平台建设。"
    assert result["platform_progress"]["lagou"]["status"] == "completed"


def test_liepin_readonly_adapter_searches_list_and_reads_full_detail() -> None:
    from interview_agent.job_platform_adapters import (
        LiepinReadonlyJobPlatformAdapter,
        JobSearchRequest,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    adapter = LiepinReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "liepin_list.html").read_text(),
        detail_html_by_job_id={
            "liepin-backend-001": (fixture_dir / "liepin_detail.html").read_text(),
        },
    )

    result = adapter.search_jobs(
        JobSearchRequest(
            job_profile={"target_roles": ["后端工程师"]},
            hard_filters={"cities": ["上海"]},
            ranking_preferences={"technical_skills": ["Python"]},
            keyword="后端工程师 Python",
        )
    )

    assert result.status == "success"
    assert result.platform == "liepin"
    assert [job.platform_job_id for job in result.jobs] == ["liepin-backend-001"]

    listed_jobs = adapter.collect_job_list(result.search_id)
    detail = adapter.read_job_detail("liepin-backend-001")

    assert listed_jobs[0].title == "猎聘后端工程师"
    assert listed_jobs[0].company_name == "猎聘样例科技"
    assert listed_jobs[0].salary_range == "30k-50k"
    assert listed_jobs[0].tech_stack == ["Python", "Go", "Kubernetes"]
    assert detail.jd_text == "负责猎聘渠道后端微服务开发。 参与搜索推荐系统与数据中台建设。"
    assert detail.field_confidence["salary_range"] == "fixture"
    assert adapter.is_already_applied("liepin-backend-001") is False


def test_liepin_readonly_adapter_marks_missing_optional_fields_low_confidence() -> None:
    from interview_agent.job_platform_adapters import LiepinReadonlyJobPlatformAdapter, JobSearchRequest

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    adapter = LiepinReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "liepin_list_missing_fields.html").read_text(),
        detail_html_by_job_id={
            "liepin-low-confidence-001": (fixture_dir / "liepin_detail.html").read_text(),
        },
    )

    result = adapter.search_jobs(
        JobSearchRequest(
            job_profile={},
            hard_filters={},
            ranking_preferences={},
            keyword="后端工程师",
        )
    )

    assert result.status == "success"
    assert result.jobs[0].salary_range is None
    assert result.jobs[0].company_size is None
    assert result.jobs[0].field_confidence["salary_range"] == "low_confidence"
    assert result.jobs[0].field_confidence["company_size"] == "low_confidence"


def test_liepin_readonly_adapter_classifies_platform_states_and_already_applied() -> None:
    from interview_agent.job_platform_adapters import (
        LiepinReadonlyJobPlatformAdapter,
        JobSearchRequest,
        PlatformAdapterErrorType,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    request = JobSearchRequest(job_profile={}, hard_filters={}, ranking_preferences={}, keyword="后端工程师")
    expected_errors = {
        "liepin_login_expired.html": PlatformAdapterErrorType.LOGIN_EXPIRED,
        "liepin_captcha.html": PlatformAdapterErrorType.CAPTCHA_REQUIRED,
        "liepin_rate_limited.html": PlatformAdapterErrorType.RATE_LIMITED,
        "liepin_structure_changed.html": PlatformAdapterErrorType.PAGE_STRUCTURE_CHANGED,
    }

    for fixture_name, expected_error_type in expected_errors.items():
        adapter = LiepinReadonlyJobPlatformAdapter(
            list_html=(fixture_dir / fixture_name).read_text(),
            detail_html_by_job_id={},
        )

        result = adapter.search_jobs(request)

        assert result.status == "failed"
        assert result.errors[0].error_type is expected_error_type
        assert result.errors[0].platform == "liepin"
        assert result.errors[0].stage == "search"
        assert _contains_sensitive_adapter_payload(result.errors[0].__dict__) is False

    applied_adapter = LiepinReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "liepin_list.html").read_text(),
        detail_html_by_job_id={"liepin-backend-001": (fixture_dir / "liepin_detail.html").read_text()},
        state_html_by_job_id={"liepin-backend-001": (fixture_dir / "liepin_already_applied.html").read_text()},
    )

    assert applied_adapter.is_already_applied("liepin-backend-001") is True


def test_liepin_readonly_adapter_propagates_detail_and_state_platform_errors() -> None:
    import pytest

    from interview_agent.job_platform_adapters import (
        LiepinReadonlyJobPlatformAdapter,
        PlatformAdapterError,
        PlatformAdapterErrorType,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    expected_errors = {
        "liepin_login_expired.html": PlatformAdapterErrorType.LOGIN_EXPIRED,
        "liepin_captcha.html": PlatformAdapterErrorType.CAPTCHA_REQUIRED,
        "liepin_rate_limited.html": PlatformAdapterErrorType.RATE_LIMITED,
        "liepin_structure_changed.html": PlatformAdapterErrorType.PAGE_STRUCTURE_CHANGED,
    }

    for fixture_name, expected_error_type in expected_errors.items():
        detail_adapter = LiepinReadonlyJobPlatformAdapter(
            list_html=(fixture_dir / "liepin_list.html").read_text(),
            detail_html_by_job_id={"liepin-backend-001": (fixture_dir / fixture_name).read_text()},
        )
        state_adapter = LiepinReadonlyJobPlatformAdapter(
            list_html=(fixture_dir / "liepin_list.html").read_text(),
            detail_html_by_job_id={"liepin-backend-001": (fixture_dir / "liepin_detail.html").read_text()},
            state_html_by_job_id={"liepin-backend-001": (fixture_dir / fixture_name).read_text()},
        )

        with pytest.raises(PlatformAdapterError) as detail_error:
            detail_adapter.read_job_detail("liepin-backend-001")
        with pytest.raises(PlatformAdapterError) as state_error:
            state_adapter.is_already_applied("liepin-backend-001")

        assert detail_error.value.error_type is expected_error_type
        assert detail_error.value.stage == "detail"
        assert state_error.value.error_type is expected_error_type
        assert state_error.value.stage == "state"


def test_job_collection_orchestrator_records_liepin_detail_platform_errors() -> None:
    from interview_agent.job_collection import JobCollectionOrchestrator
    from interview_agent.job_platform_adapters import LiepinReadonlyJobPlatformAdapter

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    adapter = LiepinReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "liepin_list.html").read_text(),
        detail_html_by_job_id={"liepin-backend-001": (fixture_dir / "liepin_rate_limited.html").read_text()},
    )
    orchestrator = JobCollectionOrchestrator({"liepin": adapter})

    result = orchestrator.collect(
        collection_task_id="collection-liepin-detail-error-001",
        platforms=["liepin"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={"cities": ["上海"]},
        ranking_preferences={"technical_skills": ["Python"]},
        keyword="后端工程师 Python",
    )

    assert result["status"] == "backoff"
    assert result["platform_progress"]["liepin"]["status"] == "backoff"
    assert result["platform_progress"]["liepin"]["failure_reason"] == "rate_limited"


def test_liepin_readonly_adapter_never_submits_application() -> None:
    from dataclasses import asdict

    from interview_agent.job_platform_adapters import (
        LiepinReadonlyJobPlatformAdapter,
        ConfirmationApplicationRequest,
        PlatformAdapterErrorType,
        parse_job_detail_fixture,
    )

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    job = parse_job_detail_fixture((fixture_dir / "liepin_detail.html").read_text())
    adapter = LiepinReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "liepin_list.html").read_text(),
        detail_html_by_job_id={"liepin-backend-001": (fixture_dir / "liepin_detail.html").read_text()},
    )

    result = adapter.submit_application(
        ConfirmationApplicationRequest(
            confirmation_batch_id="batch-confirmed",
            job=job,
            application_message="您好，我对该岗位很感兴趣。",
            confirmed=True,
        )
    )

    assert result.status == "skipped"
    assert result.status != "submitted"
    assert result.submitted_at is None
    assert result.error is not None
    assert result.error.error_type is PlatformAdapterErrorType.BUTTON_UNAVAILABLE
    assert _contains_sensitive_adapter_payload(asdict(result)) is False


def test_job_collection_orchestrator_collects_with_liepin_readonly_adapter() -> None:
    from interview_agent.job_collection import JobCollectionOrchestrator
    from interview_agent.job_platform_adapters import LiepinReadonlyJobPlatformAdapter

    fixture_dir = Path(__file__).parent / "fixtures" / "job_platform"
    adapter = LiepinReadonlyJobPlatformAdapter(
        list_html=(fixture_dir / "liepin_list.html").read_text(),
        detail_html_by_job_id={"liepin-backend-001": (fixture_dir / "liepin_detail.html").read_text()},
    )
    orchestrator = JobCollectionOrchestrator({"liepin": adapter})

    result = orchestrator.collect(
        collection_task_id="collection-liepin-readonly-001",
        platforms=["liepin"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={"cities": ["上海"]},
        ranking_preferences={"technical_skills": ["Python"]},
        keyword="后端工程师 Python",
    )

    assert result["status"] == "success"
    assert [job.platform_job_id for job in result["jobs"]] == ["liepin-backend-001"]
    assert result["jobs"][0].jd_text == "负责猎聘渠道后端微服务开发。 参与搜索推荐系统与数据中台建设。"
    assert result["platform_progress"]["liepin"]["status"] == "completed"


def test_job_collection_orchestrator_keeps_successful_platform_results_and_retries_failed_platform() -> None:
    from interview_agent.job_collection import JobCollectionOrchestrator
    from interview_agent.job_platform_adapters import (
        FakeJobPlatformAdapter,
        PlatformAdapterError,
        PlatformAdapterErrorType,
        StandardJob,
    )

    boss_job = StandardJob(
        platform="boss",
        platform_job_id="boss-collection-001",
        title="后端工程师",
        company_name="示例科技",
        location="上海",
        remote_policy="hybrid",
        salary_range="35k-50k",
        level="高级",
        experience_requirement="5年",
        education_requirement="本科",
        industry="AI 工具",
        company_size="100-500人",
        funding_stage="B轮",
        tech_stack=["Python"],
        benefits=["五险一金"],
        published_at="2026-06-10T09:00:00+08:00",
        detail_url="https://example.com/boss/jobs/collection-001",
        jd_text="负责后端服务。",
        collected_at="2026-06-10T09:05:00+08:00",
        field_confidence={"salary_range": "fixture"},
    )
    orchestrator = JobCollectionOrchestrator(
        {
            "boss": FakeJobPlatformAdapter(platform="boss", jobs=[boss_job]),
            "lagou": FakeJobPlatformAdapter(
                platform="lagou",
                search_error=PlatformAdapterError(
                    error_type=PlatformAdapterErrorType.PAGE_STRUCTURE_CHANGED,
                    platform="lagou",
                    stage="search",
                    message="列表结构变化",
                ),
            ),
        }
    )

    first_result = orchestrator.collect(
        collection_task_id="collection-001",
        platforms=["boss", "lagou"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={"cities": ["上海"]},
        ranking_preferences={"technical_skills": ["Python"]},
        keyword="后端工程师 Python",
    )

    assert first_result["status"] == "partial"
    assert [job.platform_job_id for job in first_result["jobs"]] == ["boss-collection-001"]
    assert [event["status"] for event in first_result["platform_progress"]["boss"]["events"]] == [
        "started",
        "page_collected",
        "detail_collected",
        "completed",
    ]
    assert first_result["platform_progress"]["boss"]["collected_job_count"] == 1
    assert first_result["platform_progress"]["lagou"]["status"] == "failed"
    assert first_result["platform_progress"]["lagou"]["failure_reason"] == "page_structure_changed"
    assert first_result["platform_progress"]["lagou"]["retry_count"] == 0

    retry_job = StandardJob(
        platform="lagou",
        platform_job_id="lagou-collection-001",
        title="平台工程师",
        company_name="示例云",
        location="杭州",
        remote_policy=None,
        salary_range=None,
        level=None,
        experience_requirement=None,
        education_requirement=None,
        industry=None,
        company_size=None,
        funding_stage=None,
        tech_stack=["Python"],
        benefits=[],
        published_at=None,
        detail_url="https://example.com/lagou/jobs/collection-001",
        jd_text="负责平台建设。",
        collected_at="2026-06-10T09:10:00+08:00",
        field_confidence={"salary_range": "missing"},
    )
    retry_result = orchestrator.retry_failed_platform(
        collection_task_id="collection-001",
        platform="lagou",
        adapter=FakeJobPlatformAdapter(platform="lagou", jobs=[retry_job]),
    )

    assert retry_result["status"] == "success"
    assert [job.platform_job_id for job in retry_result["jobs"]] == ["boss-collection-001", "lagou-collection-001"]
    assert retry_result["platform_progress"]["boss"]["status"] == "completed"
    assert retry_result["platform_progress"]["boss"]["collected_job_count"] == 1
    assert retry_result["platform_progress"]["lagou"]["status"] == "completed"
    assert retry_result["platform_progress"]["lagou"]["retry_count"] == 1
    assert retry_result["platform_progress"]["lagou"]["failure_reason"] is None


def test_runtime_collects_jobs_and_exposes_collection_progress_view_model(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import (
        FakeJobPlatformAdapter,
        PlatformAdapterError,
        PlatformAdapterErrorType,
        StandardJob,
    )

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("job-collection-session")
    boss_job = StandardJob(
        platform="boss",
        platform_job_id="boss-runtime-001",
        title="后端工程师",
        company_name="示例科技",
        location="上海",
        remote_policy="hybrid",
        salary_range="35k-50k",
        level="高级",
        experience_requirement="5年",
        education_requirement="本科",
        industry="AI 工具",
        company_size="100-500人",
        funding_stage="B轮",
        tech_stack=["Python"],
        benefits=[],
        published_at="2026-06-10T09:00:00+08:00",
        detail_url="https://example.com/boss/jobs/runtime-001",
        jd_text="负责后端服务。",
        collected_at="2026-06-10T09:05:00+08:00",
        field_confidence={"salary_range": "fixture"},
    )

    view_model = runtime.collect_job_applications(
        session_id="job-collection-session",
        collection_task_id="collection-runtime-001",
        adapters={
            "boss": FakeJobPlatformAdapter(platform="boss", jobs=[boss_job]),
            "liepin": FakeJobPlatformAdapter(
                platform="liepin",
                search_error=PlatformAdapterError(
                    error_type=PlatformAdapterErrorType.LOGIN_EXPIRED,
                    platform="liepin",
                    stage="search",
                    message="登录失效",
                ),
            ),
        },
        platforms=["boss", "liepin"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={"cities": ["上海"]},
        ranking_preferences={},
        keyword="后端工程师",
    )

    assert view_model["status"] == "partial"
    assert view_model["summary"] == {
        "platform_count": 2,
        "completed_platform_count": 1,
        "failed_platform_count": 1,
        "manual_takeover_platform_count": 0,
        "backoff_platform_count": 0,
        "collected_job_count": 1,
    }
    assert view_model["platforms"]["boss"]["status"] == "completed"
    assert view_model["platforms"]["boss"]["collected_job_count"] == 1
    assert view_model["platforms"]["liepin"]["status"] == "failed"
    assert view_model["platforms"]["liepin"]["failure_reason"] == "login_expired"
    assert view_model["jobs"][0]["platform_job_id"] == "boss-runtime-001"
    assert runtime.get_job_collection_progress(session_id="job-collection-session") == view_model
    assert _contains_sensitive_adapter_payload(view_model) is False


def test_runtime_retries_failed_job_collection_platform_and_saves_new_view_model(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter, PlatformAdapterError, PlatformAdapterErrorType

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("job-retry-session")
    runtime.collect_job_applications(
        session_id="job-retry-session",
        collection_task_id="collection-retry-001",
        adapters={
            "boss": FakeJobPlatformAdapter(platform="boss", jobs=[_standard_job(platform="boss", platform_job_id="boss-retry-001")]),
            "lagou": FakeJobPlatformAdapter(
                platform="lagou",
                search_error=PlatformAdapterError(
                    error_type=PlatformAdapterErrorType.PAGE_STRUCTURE_CHANGED,
                    platform="lagou",
                    stage="search",
                    message="列表结构变化",
                ),
            ),
        },
        platforms=["boss", "lagou"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={},
        ranking_preferences={},
        keyword="后端工程师",
    )

    retry_view_model = runtime.retry_failed_job_collection_platform(
        session_id="job-retry-session",
        collection_task_id="collection-retry-001",
        platform="lagou",
        adapter=FakeJobPlatformAdapter(platform="lagou", jobs=[_standard_job(platform="lagou", platform_job_id="lagou-retry-001")]),
    )

    assert retry_view_model["status"] == "success"
    assert [job["platform_job_id"] for job in retry_view_model["jobs"]] == ["boss-retry-001", "lagou-retry-001"]
    assert retry_view_model["platforms"]["lagou"]["status"] == "completed"
    assert retry_view_model["platforms"]["lagou"]["retry_count"] == 1
    assert [event["status"] for event in retry_view_model["platforms"]["lagou"]["events"]] == [
        "started",
        "failed",
        "retrying",
        "started",
        "page_collected",
        "detail_collected",
        "completed",
    ]
    assert runtime.get_job_collection_progress(session_id="job-retry-session") == retry_view_model


def test_runtime_reads_running_job_collection_progress_during_collection(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter, JobSearchRequest, PlatformExecutionResult
    from interview_agent.storage import get_collection_progress

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("job-running-session")
    observed_progress: list[dict[str, object]] = []

    class ObservingAdapter(FakeJobPlatformAdapter):
        def search_jobs(self, request: JobSearchRequest) -> PlatformExecutionResult:
            observed_progress.append(runtime.get_job_collection_progress(session_id="job-running-session"))
            persisted_started_progress = get_collection_progress(database_path, collection_task_id="collection-running-001", platform="boss")
            assert persisted_started_progress is not None
            assert persisted_started_progress["status"] == "started"
            return super().search_jobs(request)

    view_model = runtime.collect_job_applications(
        session_id="job-running-session",
        collection_task_id="collection-running-001",
        adapters={
            "boss": ObservingAdapter(platform="boss", jobs=[_standard_job(platform="boss", platform_job_id="boss-running-001")]),
        },
        platforms=["boss"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={},
        ranking_preferences={},
        keyword="后端工程师",
    )

    assert observed_progress[0]["status"] == "running"
    assert observed_progress[0]["platforms"]["boss"]["status"] == "started"
    assert observed_progress[0]["platforms"]["boss"]["events"] == [
        {"status": "started", "current_page": 0, "last_job_offset": 0}
    ]
    persisted_progress = get_collection_progress(database_path, collection_task_id="collection-running-001", platform="boss")
    assert persisted_progress is not None
    assert persisted_progress["status"] == "completed"
    assert view_model["platforms"]["boss"]["status"] == "completed"


def test_job_collection_orchestrator_isolates_platform_exceptions_from_search_list_and_detail() -> None:
    from interview_agent.job_collection import JobCollectionOrchestrator
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter, JobSearchRequest, PlatformExecutionResult, StandardJob

    class ThrowingAdapter(FakeJobPlatformAdapter):
        def search_jobs(self, request: JobSearchRequest) -> PlatformExecutionResult:
            raise RuntimeError("cookie=sid-secret token=secret session=chrome")

    class ThrowingListAdapter(FakeJobPlatformAdapter):
        def collect_job_list(self, search_id: str) -> list[StandardJob]:
            raise ValueError("列表结构变化 token=secret")

    class ThrowingDetailAdapter(FakeJobPlatformAdapter):
        def read_job_detail(self, platform_job_id: str) -> StandardJob:
            raise ValueError("详情结构变化 cookie=sid-secret")

    orchestrator = JobCollectionOrchestrator(
        {
            "boss": ThrowingAdapter(platform="boss"),
            "lagou": ThrowingListAdapter(platform="lagou", jobs=[_standard_job(platform="lagou", platform_job_id="lagou-list-001")]),
            "boss_detail": ThrowingDetailAdapter(platform="boss_detail", jobs=[_standard_job(platform="boss_detail", platform_job_id="boss-detail-001")]),
            "liepin": FakeJobPlatformAdapter(platform="liepin", jobs=[_standard_job(platform="liepin", platform_job_id="liepin-safe-001")]),
        }
    )

    result = orchestrator.collect(
        collection_task_id="collection-exception-001",
        platforms=["boss", "lagou", "boss_detail", "liepin"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={},
        ranking_preferences={},
        keyword="后端工程师",
    )

    assert result["status"] == "partial"
    assert [job.platform_job_id for job in result["jobs"]] == ["liepin-safe-001"]
    assert result["platform_progress"]["boss"]["status"] == "failed"
    assert result["platform_progress"]["boss"]["failure_reason"] == "platform_exception"
    assert result["platform_progress"]["lagou"]["status"] == "failed"
    assert result["platform_progress"]["lagou"]["failure_reason"] == "platform_exception"
    assert result["platform_progress"]["boss_detail"]["status"] == "failed"
    assert result["platform_progress"]["boss_detail"]["failure_reason"] == "platform_exception"
    assert result["platform_progress"]["liepin"]["status"] == "completed"
    assert _contains_sensitive_adapter_payload(result["platform_progress"]["boss"]) is False
    assert _contains_sensitive_adapter_payload(result["platform_progress"]["lagou"]) is False
    assert _contains_sensitive_adapter_payload(result["platform_progress"]["boss_detail"]) is False


def test_job_collection_orchestrator_records_retrying_event_before_retry_attempt(tmp_path: Path) -> None:
    from interview_agent.job_collection import JobCollectionOrchestrator
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter, PlatformAdapterError, PlatformAdapterErrorType
    from interview_agent.storage import get_collection_progress

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    observed_persisted_retrying_progress: list[dict[str, object]] = []

    def observe_retrying_progress(result: dict[str, object]) -> None:
        platform_progress = result["platform_progress"]["lagou"]
        if platform_progress["status"] != "retrying":
            return
        persisted_progress = get_collection_progress(database_path, collection_task_id="collection-retrying-001", platform="lagou")
        assert persisted_progress is not None
        observed_persisted_retrying_progress.append(persisted_progress)

    orchestrator = JobCollectionOrchestrator(
        {
            "lagou": FakeJobPlatformAdapter(
                platform="lagou",
                search_error=PlatformAdapterError(
                    error_type=PlatformAdapterErrorType.RATE_LIMITED,
                    platform="lagou",
                    stage="search",
                    message="限流",
                ),
            )
        },
        database_path=database_path,
        progress_callback=observe_retrying_progress,
    )
    orchestrator.collect(
        collection_task_id="collection-retrying-001",
        platforms=["lagou"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={},
        ranking_preferences={},
        keyword="后端工程师",
    )

    result = orchestrator.retry_failed_platform(
        collection_task_id="collection-retrying-001",
        platform="lagou",
        adapter=FakeJobPlatformAdapter(platform="lagou", jobs=[_standard_job(platform="lagou", platform_job_id="lagou-retrying-001")]),
    )

    assert [event["status"] for event in result["platform_progress"]["lagou"]["events"]] == [
        "started",
        "backoff",
        "retrying",
        "started",
        "page_collected",
        "detail_collected",
        "completed",
    ]
    assert result["platform_progress"]["lagou"]["status"] == "completed"
    assert result["platform_progress"]["lagou"]["failure_reason"] is None
    assert observed_persisted_retrying_progress == [
        {
            "collection_task_id": "collection-retrying-001",
            "platform": "lagou",
            "current_page": 0,
            "last_job_offset": 0,
            "retry_count": 1,
            "failure_reason": None,
            "manual_takeover_required": False,
            "status": "retrying",
        }
    ]


def test_runtime_pauses_manual_takeover_platform_and_resumes_only_that_platform(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter, PlatformAdapterError, PlatformAdapterErrorType
    from interview_agent.storage import get_collection_progress

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("job-manual-takeover-session")

    view_model = runtime.collect_job_applications(
        session_id="job-manual-takeover-session",
        collection_task_id="collection-manual-takeover-001",
        adapters={
            "boss": FakeJobPlatformAdapter(platform="boss", jobs=[_standard_job(platform="boss", platform_job_id="boss-manual-001")]),
            "liepin": FakeJobPlatformAdapter(
                platform="liepin",
                search_error=PlatformAdapterError(
                    error_type=PlatformAdapterErrorType.CAPTCHA_REQUIRED,
                    platform="liepin",
                    stage="search",
                    message="验证码触发 cookie=sid-secret token=secret account_id=42",
                    page_url="https://example.com/liepin/search?token=secret",
                ),
            ),
        },
        platforms=["boss", "liepin"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={},
        ranking_preferences={},
        keyword="后端工程师",
    )

    liepin_progress = view_model["platforms"]["liepin"]
    assert liepin_progress["status"] == "manual_takeover"
    assert liepin_progress["failure_reason"] == "captcha_required"
    assert liepin_progress["manual_takeover_required"] is True
    assert liepin_progress["risk_control"] == {
        "type": "manual_takeover",
        "reason": "captcha_required",
        "hint": "平台要求人工处理后再恢复采集",
    }
    assert view_model["summary"]["manual_takeover_platform_count"] == 1
    assert view_model["platforms"]["boss"]["status"] == "completed"
    assert [job["platform_job_id"] for job in view_model["jobs"]] == ["boss-manual-001"]
    assert _contains_sensitive_adapter_payload(view_model) is False

    persisted_progress = get_collection_progress(database_path, collection_task_id="collection-manual-takeover-001", platform="liepin")
    assert persisted_progress is not None
    assert persisted_progress["status"] == "manual_takeover"
    assert persisted_progress["manual_takeover_required"] is True

    resumed_view_model = runtime.retry_failed_job_collection_platform(
        session_id="job-manual-takeover-session",
        collection_task_id="collection-manual-takeover-001",
        platform="liepin",
        adapter=FakeJobPlatformAdapter(platform="liepin", jobs=[_standard_job(platform="liepin", platform_job_id="liepin-manual-001")]),
    )

    assert resumed_view_model["status"] == "success"
    assert [job["platform_job_id"] for job in resumed_view_model["jobs"]] == ["boss-manual-001", "liepin-manual-001"]
    assert resumed_view_model["platforms"]["boss"]["status"] == "completed"
    assert resumed_view_model["platforms"]["boss"]["collected_job_count"] == 1
    assert resumed_view_model["platforms"]["liepin"]["status"] == "completed"
    assert resumed_view_model["platforms"]["liepin"]["manual_takeover_required"] is False


@pytest.mark.parametrize(
    "error_type",
    [
        "ACCOUNT_RISK_CONTROL",
        "FORCED_POPUP",
    ],
)
def test_runtime_classifies_account_risk_and_forced_popup_as_manual_takeover(tmp_path: Path, error_type: str) -> None:
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter, PlatformAdapterError, PlatformAdapterErrorType

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session(f"job-{error_type.lower()}-session")

    view_model = runtime.collect_job_applications(
        session_id=f"job-{error_type.lower()}-session",
        collection_task_id=f"collection-{error_type.lower()}-001",
        adapters={
            "boss": FakeJobPlatformAdapter(
                platform="boss",
                search_error=PlatformAdapterError(
                    error_type=getattr(PlatformAdapterErrorType, error_type),
                    platform="boss",
                    stage="search",
                    message="平台要求人工处理 token=secret",
                ),
            )
        },
        platforms=["boss"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={},
        ranking_preferences={},
        keyword="后端工程师",
    )

    assert view_model["status"] == "manual_takeover"
    assert view_model["platforms"]["boss"]["status"] == "manual_takeover"
    assert view_model["platforms"]["boss"]["manual_takeover_required"] is True
    assert view_model["summary"]["manual_takeover_platform_count"] == 1
    assert _contains_sensitive_adapter_payload(view_model) is False


def test_runtime_records_rate_limit_backoff_without_sensitive_session_payload(tmp_path: Path) -> None:
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter, PlatformAdapterError, PlatformAdapterErrorType

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("job-backoff-session")

    view_model = runtime.collect_job_applications(
        session_id="job-backoff-session",
        collection_task_id="collection-backoff-001",
        adapters={
            "lagou": FakeJobPlatformAdapter(
                platform="lagou",
                search_error=PlatformAdapterError(
                    error_type=PlatformAdapterErrorType.RATE_LIMITED,
                    platform="lagou",
                    stage="search",
                    message="请求过快 cookie=sid-secret token=secret session=chrome",
                    page_url="https://example.com/lagou/search?cookie=secret",
                ),
            )
        },
        platforms=["lagou"],
        job_profile={"target_roles": ["后端工程师"]},
        hard_filters={},
        ranking_preferences={},
        keyword="后端工程师",
    )

    assert view_model["status"] == "backoff"
    assert view_model["summary"]["backoff_platform_count"] == 1
    assert view_model["platforms"]["lagou"]["status"] == "backoff"
    assert view_model["platforms"]["lagou"]["failure_reason"] == "rate_limited"
    assert view_model["platforms"]["lagou"]["manual_takeover_required"] is False
    assert view_model["platforms"]["lagou"]["risk_control"] == {
        "type": "backoff",
        "reason": "rate_limited",
        "hint": "平台限流，已进入退避状态",
    }
    assert _contains_sensitive_adapter_payload(view_model) is False


    assert _contains_sensitive_adapter_payload(view_model) is False


# ---------------------------------------------------------------------------
# JOB-011: 岗位筛选与排序
# ---------------------------------------------------------------------------


_JOB_FILTER_UNSET = object()


def _make_job_for_filter(
    *,
    platform: str = "boss",
    platform_job_id: str = "j1",
    title: str = "后端工程师",
    company_name: str = "示例科技",
    location: str = "上海",
    remote_policy: str | None = "hybrid",
    salary_range: str | None = "35k-50k",
    level: str | None = "高级",
    experience_requirement: str | None = "5年",
    education_requirement: str | None = "本科",
    industry: str | None = "AI 工具",
    company_size: str | None = "100-500人",
    funding_stage: str | None = "B轮",
    tech_stack: list[str] | None = _JOB_FILTER_UNSET,  # type: ignore[assignment]
    benefits: list[str] | None = _JOB_FILTER_UNSET,  # type: ignore[assignment]
    published_at: str | None = "2026-06-10T09:00:00+08:00",
) -> object:
    from interview_agent.job_platform_adapters import StandardJob

    resolved_tech_stack = tech_stack if tech_stack is not _JOB_FILTER_UNSET else ["Python"]
    resolved_benefits = benefits if benefits is not _JOB_FILTER_UNSET else []

    return StandardJob(
        platform=platform,
        platform_job_id=platform_job_id,
        title=title,
        company_name=company_name,
        location=location,
        remote_policy=remote_policy,
        salary_range=salary_range,
        level=level,
        experience_requirement=experience_requirement,
        education_requirement=education_requirement,
        industry=industry,
        company_size=company_size,
        funding_stage=funding_stage,
        tech_stack=resolved_tech_stack,
        benefits=resolved_benefits,
        published_at=published_at,
        detail_url=f"https://example.com/{platform}/jobs/{platform_job_id}",
        jd_text="负责后端服务。",
        collected_at="2026-06-10T09:05:00+08:00",
        field_confidence={},
    )


def _setup_filter_runtime(tmp_path: Path):
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("filter-session")
    return runtime


def test_filter_jobs_by_city_excludes_non_matching(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [
        _make_job_for_filter(platform_job_id="j-shanghai", location="上海"),
        _make_job_for_filter(platform_job_id="j-beijing", location="北京"),
        _make_job_for_filter(platform_job_id="j-shanghai2", location="上海"),
    ]

    result = runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={"cities": ["上海"]},
        ranking_preferences={},
    )

    assert result["total_job_count"] == 3
    assert result["candidate_count"] == 2
    assert result["excluded_count"] == 1
    candidate_ids = [j["platform_job_id"] for j in result["candidates"]]
    assert "j-shanghai" in candidate_ids
    assert "j-shanghai2" in candidate_ids
    assert "j-beijing" not in candidate_ids
    assert result["excluded"][0]["reason"] == "city_mismatch"


def test_filter_jobs_by_remote_policy_excludes_non_matching(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [
        _make_job_for_filter(platform_job_id="j-remote", remote_policy="remote"),
        _make_job_for_filter(platform_job_id="j-onsite", remote_policy="onsite"),
        _make_job_for_filter(platform_job_id="j-hybrid", remote_policy="hybrid"),
    ]

    result = runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={"remote_policy": "remote"},
        ranking_preferences={},
    )

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["platform_job_id"] == "j-remote"
    assert result["excluded_count"] == 2


def test_filter_jobs_by_salary_min_excludes_below_threshold(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [
        _make_job_for_filter(platform_job_id="j-high", salary_range="40k-60k"),
        _make_job_for_filter(platform_job_id="j-low", salary_range="10k-15k"),
        _make_job_for_filter(platform_job_id="j-mid", salary_range="25k-35k"),
    ]

    result = runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={"salary_min": 20},
        ranking_preferences={},
    )

    assert result["candidate_count"] == 2
    candidate_ids = [j["platform_job_id"] for j in result["candidates"]]
    assert "j-low" not in candidate_ids
    assert result["excluded"][0]["platform_job_id"] == "j-low"
    assert result["excluded"][0]["reason"] == "salary_below_minimum"


def test_filter_jobs_by_education_excludes_below_required(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [
        _make_job_for_filter(platform_job_id="j-bachelor", education_requirement="本科"),
        _make_job_for_filter(platform_job_id="j-master", education_requirement="硕士"),
        _make_job_for_filter(platform_job_id="j-college", education_requirement="大专"),
    ]

    result = runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={"education": "本科"},
        ranking_preferences={},
    )

    candidate_ids = [j["platform_job_id"] for j in result["candidates"]]
    assert "j-bachelor" in candidate_ids
    assert "j-master" in candidate_ids
    assert "j-college" not in candidate_ids
    assert result["excluded"][0]["reason"] == "education_below_required"


def test_filter_jobs_by_experience_range_excludes_out_of_range(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [
        _make_job_for_filter(platform_job_id="j-3yr", experience_requirement="3年"),
        _make_job_for_filter(platform_job_id="j-8yr", experience_requirement="8年"),
        _make_job_for_filter(platform_job_id="j-1yr", experience_requirement="1年"),
    ]

    result = runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={"experience_years_min": 2, "experience_years_max": 6},
        ranking_preferences={},
    )

    candidate_ids = [j["platform_job_id"] for j in result["candidates"]]
    assert "j-3yr" in candidate_ids
    assert "j-8yr" not in candidate_ids
    assert "j-1yr" not in candidate_ids


def test_filter_jobs_by_company_blacklist_excludes_matching(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [
        _make_job_for_filter(platform_job_id="j-good", company_name="好公司"),
        _make_job_for_filter(platform_job_id="j-bad", company_name="坏公司"),
    ]

    result = runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={"company_blacklist": ["坏公司"]},
        ranking_preferences={},
    )

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["platform_job_id"] == "j-good"
    assert result["excluded"][0]["reason"] == "company_blacklisted"


def test_filter_jobs_excludes_already_applied(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [
        _make_job_for_filter(platform_job_id="j-new"),
        _make_job_for_filter(platform_job_id="j-applied"),
    ]

    result = runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={},
        ranking_preferences={},
        already_applied_job_ids=["j-applied"],
    )

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["platform_job_id"] == "j-new"
    assert result["excluded"][0]["reason"] == "already_applied"


def test_filter_jobs_marks_low_confidence_for_missing_fields(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [
        _make_job_for_filter(
            platform_job_id="j-missing",
            remote_policy=None,
            salary_range=None,
            level=None,
            industry=None,
            funding_stage=None,
            tech_stack=[],
        ),
    ]

    result = runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={},
        ranking_preferences={},
    )

    assert result["candidate_count"] == 1
    candidate = result["candidates"][0]
    assert "remote_policy" in candidate["low_confidence_fields"]
    assert "salary_range" in candidate["low_confidence_fields"]
    assert "level" in candidate["low_confidence_fields"]
    assert "industry" in candidate["low_confidence_fields"]
    assert "funding_stage" in candidate["low_confidence_fields"]
    assert "tech_stack" in candidate["low_confidence_fields"]


def test_filter_jobs_missing_fields_not_excluded(tmp_path: Path) -> None:
    """缺失字段的岗位应保留在候选列表中，不被丢弃。"""
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [
        _make_job_for_filter(
            platform_job_id="j-complete",
            remote_policy="remote",
            salary_range="30k-50k",
            education_requirement="本科",
        ),
        _make_job_for_filter(
            platform_job_id="j-incomplete",
            remote_policy=None,
            salary_range=None,
            education_requirement=None,
        ),
    ]

    result = runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={"cities": ["上海"]},
        ranking_preferences={},
    )

    assert result["candidate_count"] == 2
    candidate_ids = [j["platform_job_id"] for j in result["candidates"]]
    assert "j-complete" in candidate_ids
    assert "j-incomplete" in candidate_ids


def test_filter_jobs_ranking_preferences_change_order(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [
        _make_job_for_filter(
            platform_job_id="j-no-match",
            tech_stack=["Java"],
            industry="传统行业",
        ),
        _make_job_for_filter(
            platform_job_id="j-partial-match",
            tech_stack=["Python", "Go"],
            industry="AI 工具",
        ),
        _make_job_for_filter(
            platform_job_id="j-full-match",
            tech_stack=["Python", "Go", "Kubernetes"],
            industry="AI 工具",
            funding_stage="B轮",
            company_size="100-500人",
        ),
    ]

    result = runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={},
        ranking_preferences={
            "technical_skills": ["Python", "Go", "Kubernetes"],
            "industries": ["AI 工具"],
            "funding_stages": ["B轮"],
            "company_sizes": ["100-500人"],
        },
    )

    candidate_ids = [j["platform_job_id"] for j in result["candidates"]]
    # full-match 应排第一，partial-match 排第二，no-match 排最后
    assert candidate_ids[0] == "j-full-match"
    assert candidate_ids[-1] == "j-no-match"
    # full-match 得分应最高
    assert result["candidates"][0]["rank_score"] > result["candidates"][1]["rank_score"]


def test_filter_jobs_no_filters_returns_all_jobs(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [
        _make_job_for_filter(platform_job_id="j1"),
        _make_job_for_filter(platform_job_id="j2"),
        _make_job_for_filter(platform_job_id="j3"),
    ]

    result = runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={},
        ranking_preferences={},
    )

    assert result["total_job_count"] == 3
    assert result["candidate_count"] == 3
    assert result["excluded_count"] == 0


def test_filter_jobs_multiple_hard_filters_combined(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [
        _make_job_for_filter(
            platform_job_id="j-perfect",
            location="上海",
            salary_range="35k-50k",
            education_requirement="本科",
            experience_requirement="5年",
            company_name="好公司",
        ),
        _make_job_for_filter(
            platform_job_id="j-wrong-city",
            location="北京",
            salary_range="35k-50k",
            education_requirement="本科",
            experience_requirement="5年",
            company_name="好公司",
        ),
        _make_job_for_filter(
            platform_job_id="j-low-salary",
            location="上海",
            salary_range="10k-15k",
            education_requirement="本科",
            experience_requirement="5年",
            company_name="好公司",
        ),
        _make_job_for_filter(
            platform_job_id="j-blacklisted",
            location="上海",
            salary_range="35k-50k",
            education_requirement="本科",
            experience_requirement="5年",
            company_name="坏公司",
        ),
    ]

    result = runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={
            "cities": ["上海"],
            "salary_min": 20,
            "company_blacklist": ["坏公司"],
        },
        ranking_preferences={},
    )

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["platform_job_id"] == "j-perfect"
    assert result["excluded_count"] == 3
    excluded_reasons = {e["platform_job_id"]: e["reason"] for e in result["excluded"]}
    assert excluded_reasons["j-wrong-city"] == "city_mismatch"
    assert excluded_reasons["j-low-salary"] == "salary_below_minimum"
    assert excluded_reasons["j-blacklisted"] == "company_blacklisted"


def test_filter_jobs_stores_result_in_session_state(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)
    jobs = [_make_job_for_filter(platform_job_id="j1")]

    runtime.filter_and_rank_jobs(
        session_id="filter-session",
        jobs=jobs,
        hard_filters={},
        ranking_preferences={},
    )

    stored = runtime.get_job_filter_results(session_id="filter-session")
    assert stored is not None
    assert stored["status"] == "ready"
    assert stored["candidate_count"] == 1


def test_filter_jobs_returns_none_when_no_results(tmp_path: Path) -> None:
    runtime = _setup_filter_runtime(tmp_path)

    result = runtime.get_job_filter_results(session_id="filter-session")
    assert result is None


# ---------------------------------------------------------------------------
# JOB-012 岗位评估与建议定向测试
# ---------------------------------------------------------------------------


def _make_evaluation_report(*, score: int = 85) -> dict[str, object]:
    return {
        "score": score,
        "hard_filter_status": "pass",
        "strengths": ["Python 经验丰富", "检索系统背景匹配"],
        "risks": ["缺少分布式系统经验"],
        "missing_information": [],
        "resume_improvement_advice": ["突出分布式项目经验"],
        "application_message": "您好，我对该岗位非常感兴趣……",
        "recommended": True,
        "recommendation_reason": "技能匹配度高，建议投递。",
    }


def job_evaluation_handler(context: NodeContext, inputs: dict[str, object]) -> dict[str, object]:
    del context
    job_structured = inputs.get("job_structured", {})
    resume_profile = inputs.get("resume_profile", {})
    assert isinstance(resume_profile, dict)
    assert isinstance(job_structured, dict)
    title = str(job_structured.get("title", ""))
    if "评估失败岗位" in title:
        raise RuntimeError("模拟评估失败")
    return {"evaluation_report": _make_evaluation_report()}


def build_job_evaluation_registry() -> NodeRegistry:
    return NodeRegistry(
        [
            NodeSpec(
                name="job_evaluation",
                description="Evaluate job match.",
                required_inputs=("resume_profile", "job_structured", "jd_text"),
                optional_inputs=(),
                outputs=("evaluation_report",),
                handler=job_evaluation_handler,
            ),
        ]
    )


def _setup_evaluation_runtime(tmp_path: Path):
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(
        write_config(tmp_path, database_path),
        registry_builder=build_job_evaluation_registry,
        services_builder=build_services,
    )
    runtime.create_or_open_session("eval-session")
    return runtime


def _make_eval_job(
    *,
    platform: str = "boss",
    platform_job_id: str = "j1",
    title: str = "后端工程师",
    jd_text: str = "负责后端服务开发。",
) -> object:
    from interview_agent.job_platform_adapters import StandardJob

    return StandardJob(
        platform=platform,
        platform_job_id=platform_job_id,
        title=title,
        company_name="示例科技",
        location="上海",
        remote_policy="hybrid",
        salary_range="35k-50k",
        level="高级",
        experience_requirement="5年",
        education_requirement="本科",
        industry="AI 工具",
        company_size="100-500人",
        funding_stage="B轮",
        tech_stack=["Python", "Go"],
        benefits=["年终奖"],
        published_at="2026-06-10T09:00:00+08:00",
        detail_url=f"https://example.com/{platform}/jobs/{platform_job_id}",
        jd_text=jd_text,
        collected_at="2026-06-10T09:05:00+08:00",
        field_confidence={},
    )


def test_evaluate_jobs_returns_complete_evaluation_report(tmp_path: Path) -> None:
    runtime = _setup_evaluation_runtime(tmp_path)
    jobs = [_make_eval_job(platform_job_id="j1")]
    resume_profile = {"name": "Alice", "skills": ["Python", "Go"], "years_of_experience": 5}

    result = runtime.evaluate_jobs(
        session_id="eval-session",
        resume_profile=resume_profile,
        jobs=jobs,
    )

    assert result["status"] == "ready"
    assert result["total_job_count"] == 1
    assert result["evaluated_count"] == 1
    assert result["failed_count"] == 0
    evaluation = result["evaluations"][0]
    assert evaluation["platform_job_id"] == "j1"
    report = evaluation["evaluation_report"]
    assert report["score"] == 85
    assert isinstance(report["strengths"], list) and report["strengths"]
    assert isinstance(report["risks"], list)
    assert isinstance(report["application_message"], str) and report["application_message"]
    assert report["recommended"] is True
    assert isinstance(report["recommendation_reason"], str)


def test_evaluate_jobs_batch_multiple_jobs(tmp_path: Path) -> None:
    runtime = _setup_evaluation_runtime(tmp_path)
    jobs = [
        _make_eval_job(platform_job_id="j1"),
        _make_eval_job(platform_job_id="j2", platform="lagou"),
        _make_eval_job(platform_job_id="j3", platform="liepin"),
    ]
    resume_profile = {"name": "Bob", "skills": ["Python"]}

    result = runtime.evaluate_jobs(
        session_id="eval-session",
        resume_profile=resume_profile,
        jobs=jobs,
    )

    assert result["total_job_count"] == 3
    assert result["evaluated_count"] == 3
    assert result["failed_count"] == 0
    platform_ids = [(e["platform"], e["platform_job_id"]) for e in result["evaluations"]]
    assert ("boss", "j1") in platform_ids
    assert ("lagou", "j2") in platform_ids
    assert ("liepin", "j3") in platform_ids


def test_evaluate_jobs_single_failure_does_not_affect_others(tmp_path: Path) -> None:
    runtime = _setup_evaluation_runtime(tmp_path)
    jobs = [
        _make_eval_job(platform_job_id="j-ok"),
        _make_eval_job(platform_job_id="j-fail", title="评估失败岗位"),
        _make_eval_job(platform_job_id="j-ok2"),
    ]
    resume_profile = {"name": "Alice"}

    result = runtime.evaluate_jobs(
        session_id="eval-session",
        resume_profile=resume_profile,
        jobs=jobs,
    )

    assert result["total_job_count"] == 3
    assert result["evaluated_count"] == 2
    assert result["failed_count"] == 1
    ok_ids = [e["platform_job_id"] for e in result["evaluations"]]
    assert "j-ok" in ok_ids
    assert "j-ok2" in ok_ids
    failed = result["failed_jobs"][0]
    assert failed["platform_job_id"] == "j-fail"
    assert "模拟评估失败" in failed["error_message"]


def test_evaluate_jobs_stores_results_in_session_state(tmp_path: Path) -> None:
    runtime = _setup_evaluation_runtime(tmp_path)
    jobs = [_make_eval_job(platform_job_id="j1")]
    resume_profile = {"name": "Alice"}

    runtime.evaluate_jobs(
        session_id="eval-session",
        resume_profile=resume_profile,
        jobs=jobs,
    )

    stored = runtime.get_job_evaluation_results(session_id="eval-session")
    assert stored is not None
    assert stored["status"] == "ready"
    assert stored["evaluated_count"] == 1


def test_evaluate_jobs_returns_none_when_no_results(tmp_path: Path) -> None:
    runtime = _setup_evaluation_runtime(tmp_path)

    result = runtime.get_job_evaluation_results(session_id="eval-session")
    assert result is None


def test_evaluate_jobs_empty_job_list(tmp_path: Path) -> None:
    runtime = _setup_evaluation_runtime(tmp_path)
    resume_profile = {"name": "Alice"}

    result = runtime.evaluate_jobs(
        session_id="eval-session",
        resume_profile=resume_profile,
        jobs=[],
    )

    assert result["total_job_count"] == 0
    assert result["evaluated_count"] == 0
    assert result["failed_count"] == 0
    assert result["evaluations"] == []
    assert result["failed_jobs"] == []


def test_evaluate_jobs_evaluation_report_fields_complete(tmp_path: Path) -> None:
    runtime = _setup_evaluation_runtime(tmp_path)
    jobs = [_make_eval_job(platform_job_id="j1")]
    resume_profile = {"name": "Alice", "skills": ["Python"]}

    result = runtime.evaluate_jobs(
        session_id="eval-session",
        resume_profile=resume_profile,
        jobs=jobs,
    )

    report = result["evaluations"][0]["evaluation_report"]
    required_fields = [
        "score", "hard_filter_status", "strengths", "risks",
        "missing_information", "resume_improvement_advice",
        "application_message", "recommended", "recommendation_reason",
    ]
    for field_name in required_fields:
        assert field_name in report, f"评估报告缺少字段: {field_name}"


def test_evaluate_jobs_prompt_does_not_contain_sensitive_payload(tmp_path: Path) -> None:
    runtime = _setup_evaluation_runtime(tmp_path)
    jobs = [_make_eval_job(platform_job_id="j1")]
    resume_profile = {"name": "Alice", "skills": ["Python"]}

    result = runtime.evaluate_jobs(
        session_id="eval-session",
        resume_profile=resume_profile,
        jobs=jobs,
    )

    assert result["evaluated_count"] == 1
    from interview_agent.sensitive import contains_sensitive_payload
    assert not contains_sensitive_payload(resume_profile)
    assert not contains_sensitive_payload(result["evaluations"])


def _contains_sensitive_adapter_payload(value: object) -> bool:
    sensitive_markers = ("cookie", "token", "session", "password", "credential", "account_id")
    return any(marker in _flatten_text(value).lower() for marker in sensitive_markers)


def _flatten_text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for pair in value.items() for item in pair)
    if isinstance(value, list | tuple | set):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def _standard_job(*, platform: str, platform_job_id: str) -> object:
    from interview_agent.job_platform_adapters import StandardJob

    return StandardJob(
        platform=platform,
        platform_job_id=platform_job_id,
        title="后端工程师",
        company_name="示例科技",
        location="上海",
        remote_policy="hybrid",
        salary_range="35k-50k",
        level="高级",
        experience_requirement="5年",
        education_requirement="本科",
        industry="AI 工具",
        company_size="100-500人",
        funding_stage="B轮",
        tech_stack=["Python"],
        benefits=[],
        published_at="2026-06-10T09:00:00+08:00",
        detail_url=f"https://example.com/{platform}/jobs/{platform_job_id}",
        jd_text="负责后端服务。",
        collected_at="2026-06-10T09:05:00+08:00",
        field_confidence={"salary_range": "fixture"},
    )


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


# ---------------------------------------------------------------------------
# JOB-014 确认批次重校验测试
# ---------------------------------------------------------------------------


def _make_standard_job(
    *,
    platform: str = "boss",
    platform_job_id: str = "pj-1",
    title: str = "后端工程师",
    company_name: str = "测试公司",
    location: str = "上海",
    salary_range: str = "30k-50k",
    education_requirement: str = "本科",
    experience_requirement: str = "3年",
    level: str = "mid",
    jd_text: str = "负责后端开发",
) -> "StandardJob":
    from interview_agent.job_platform_adapters import StandardJob
    return StandardJob(
        platform=platform,
        platform_job_id=platform_job_id,
        title=title,
        company_name=company_name,
        location=location,
        remote_policy=None,
        salary_range=salary_range,
        level=level,
        experience_requirement=experience_requirement,
        education_requirement=education_requirement,
        industry=None,
        company_size=None,
        funding_stage=None,
        tech_stack=[],
        benefits=[],
        published_at=None,
        detail_url=f"https://example.com/jobs/{platform_job_id}",
        jd_text=jd_text,
        collected_at="2026-06-10T09:00:00+00:00",
        field_confidence={},
    )


def _save_job_and_approve(
    database_path,
    *,
    platform: str = "boss",
    platform_job_id: str = "pj-1",
    title: str = "后端工程师",
    company_name: str = "测试公司",
    location: str = "上海",
    salary_range: str = "30k-50k",
    jd_text: str = "负责后端开发",
    education_requirement: str = "本科",
    experience_requirement: str = "3年",
    level: str = "mid",
    batch_id: str = "batch-001",
) -> str:
    from interview_agent.storage import save_job_application, update_job_application_status
    job = save_job_application(
        database_path,
        platform=platform,
        platform_job_id=platform_job_id,
        job_url=f"https://example.com/jobs/{platform_job_id}",
        company_name=company_name,
        title=title,
        location=location,
        employment_type="full_time",
        salary_range=salary_range,
        posted_at="2026-06-10T09:00:00+00:00",
        remote_policy=None,
        level=level,
        experience_requirement=experience_requirement,
        education_requirement=education_requirement,
        industry="tech",
        company_size="100-499",
        funding_stage="series_a",
        tech_stack="python",
        benefits="meal",
        published_at="2026-06-09T09:00:00+00:00",
        detail_url=f"https://example.com/jobs/{platform_job_id}",
        jd_text=jd_text,
        collected_at="2026-06-10T09:05:00+00:00",
        field_confidence='{"title":"high"}',
        normalized_payload=f'{{"platform":"{platform}"}}',
    )
    update_job_application_status(
        database_path,
        job_id=job["job_id"],
        status="approved",
        confirmation_batch_id=batch_id,
        confirmation_status="confirmed",
    )
    return job["job_id"]


def test_revalidate_skips_offline_job(tmp_path: Path) -> None:
    """岗位下线时跳过，标记为 skipped，原因 job_offline。"""
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(write_config(tmp_path, database_path), registry_builder=build_registry, services_builder=build_services)
    runtime.create_or_open_session("session-001")

    job_id = _save_job_and_approve(database_path, platform_job_id="offline-1")
    # 适配器中没有这个岗位 → read_job_detail 抛异常
    adapter = FakeJobPlatformAdapter(platform="boss", jobs=[])

    result = runtime.revalidate_confirmation_batch(
        session_id="session-001",
        confirmation_batch_id="batch-001",
        adapters={"boss": adapter},
    )

    assert result["status"] == "ready"
    assert result["submittable_count"] == 0
    assert result["skipped_count"] == 1
    assert result["skipped_jobs"][0]["reason"] == "job_offline"
    assert any(r["job_id"] == job_id and r["reason"] == "job_offline" for r in result["stale_reasons"])


def test_revalidate_marks_duplicate_when_already_applied(tmp_path: Path) -> None:
    """已投递时写入 duplicate。"""
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(write_config(tmp_path, database_path), registry_builder=build_registry, services_builder=build_services)
    runtime.create_or_open_session("session-001")

    job = _make_standard_job(platform_job_id="dup-1")
    job_id = _save_job_and_approve(database_path, platform_job_id="dup-1")
    adapter = FakeJobPlatformAdapter(platform="boss", jobs=[job], applied_job_ids={"dup-1"})

    result = runtime.revalidate_confirmation_batch(
        session_id="session-001",
        confirmation_batch_id="batch-001",
        adapters={"boss": adapter},
    )

    assert result["status"] == "ready"
    assert result["submittable_count"] == 0
    assert result["skipped_count"] == 1
    assert result["skipped_jobs"][0]["reason"] == "already_applied"
    assert any(r["job_id"] == job_id and r["reason"] == "already_applied" for r in result["stale_reasons"])

    # 验证存储中状态已更新为 duplicate
    from interview_agent.storage import get_confirmation_batch
    batch = get_confirmation_batch(database_path, confirmation_batch_id="batch-001")
    record = [r for r in batch["records"] if r["job_id"] == job_id][0]
    assert record["status"] == "duplicate"
    assert record["duplicate_detected"] is True


def test_revalidate_skips_when_button_unavailable(tmp_path: Path) -> None:
    """按钮失效时写入 skipped。"""
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(write_config(tmp_path, database_path), registry_builder=build_registry, services_builder=build_services)
    runtime.create_or_open_session("session-001")

    job = _make_standard_job(platform_job_id="btn-1")
    job_id = _save_job_and_approve(database_path, platform_job_id="btn-1")
    adapter = FakeJobPlatformAdapter(platform="boss", jobs=[job], unavailable_button_job_ids={"btn-1"})

    result = runtime.revalidate_confirmation_batch(
        session_id="session-001",
        confirmation_batch_id="batch-001",
        adapters={"boss": adapter},
    )

    assert result["status"] == "ready"
    assert result["submittable_count"] == 0
    assert result["skipped_count"] == 1
    assert result["skipped_jobs"][0]["reason"] == "button_unavailable"
    assert any(r["job_id"] == job_id and r["reason"] == "button_unavailable" for r in result["stale_reasons"])


def test_revalidate_skips_when_jd_changed(tmp_path: Path) -> None:
    """JD 变化时跳过，原因 jd_changed。"""
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(write_config(tmp_path, database_path), registry_builder=build_registry, services_builder=build_services)
    runtime.create_or_open_session("session-001")

    job_id = _save_job_and_approve(database_path, platform_job_id="jd-1", salary_range="30k-50k")
    # 平台返回的薪资发生了变化
    changed_job = _make_standard_job(platform_job_id="jd-1", salary_range="20k-35k")
    adapter = FakeJobPlatformAdapter(platform="boss", jobs=[changed_job])

    result = runtime.revalidate_confirmation_batch(
        session_id="session-001",
        confirmation_batch_id="batch-001",
        adapters={"boss": adapter},
    )

    assert result["status"] == "ready"
    assert result["submittable_count"] == 0
    assert result["skipped_count"] == 1
    assert result["skipped_jobs"][0]["reason"] == "jd_changed"
    assert any(r["job_id"] == job_id and r["reason"] == "jd_changed" for r in result["stale_reasons"])


def test_revalidate_keeps_approved_when_all_checks_pass(tmp_path: Path) -> None:
    """正常通过所有检查时保持 approved。"""
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(write_config(tmp_path, database_path), registry_builder=build_registry, services_builder=build_services)
    runtime.create_or_open_session("session-001")

    job = _make_standard_job(platform_job_id="ok-1")
    job_id = _save_job_and_approve(database_path, platform_job_id="ok-1")
    adapter = FakeJobPlatformAdapter(platform="boss", jobs=[job])

    result = runtime.revalidate_confirmation_batch(
        session_id="session-001",
        confirmation_batch_id="batch-001",
        adapters={"boss": adapter},
    )

    assert result["status"] == "ready"
    assert result["submittable_count"] == 1
    assert result["skipped_count"] == 0
    assert result["submittable_jobs"][0]["job_id"] == job_id
    assert result["submittable_jobs"][0]["platform"] == "boss"
    assert result["submittable_jobs"][0]["platform_job_id"] == "ok-1"

    # 验证存储中状态仍为 approved
    from interview_agent.storage import get_confirmation_batch
    batch = get_confirmation_batch(database_path, confirmation_batch_id="batch-001")
    record = [r for r in batch["records"] if r["job_id"] == job_id][0]
    assert record["status"] == "approved"


def test_revalidate_mixed_scenario(tmp_path: Path) -> None:
    """混合场景：部分通过，部分跳过。"""
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(write_config(tmp_path, database_path), registry_builder=build_registry, services_builder=build_services)
    runtime.create_or_open_session("session-001")

    # 岗位 1：正常通过
    good_job = _make_standard_job(platform_job_id="mix-ok")
    good_id = _save_job_and_approve(database_path, platform_job_id="mix-ok")
    # 岗位 2：已下线（不在适配器中）
    _save_job_and_approve(database_path, platform_job_id="mix-offline")
    # 岗位 3：已投递
    dup_job = _make_standard_job(platform_job_id="mix-dup")
    _save_job_and_approve(database_path, platform_job_id="mix-dup")
    # 岗位 4：JD 变化（location 改变）
    changed_job = _make_standard_job(platform_job_id="mix-changed", location="北京")
    _save_job_and_approve(database_path, platform_job_id="mix-changed", location="上海")

    adapter = FakeJobPlatformAdapter(
        platform="boss",
        jobs=[good_job, dup_job, changed_job],
        applied_job_ids={"mix-dup"},
    )

    result = runtime.revalidate_confirmation_batch(
        session_id="session-001",
        confirmation_batch_id="batch-001",
        adapters={"boss": adapter},
    )

    assert result["status"] == "ready"
    assert result["total_count"] == 4
    assert result["submittable_count"] == 1
    assert result["skipped_count"] == 3
    assert result["submittable_jobs"][0]["job_id"] == good_id

    reasons = {s["reason"] for s in result["skipped_jobs"]}
    assert "job_offline" in reasons
    assert "already_applied" in reasons
    assert "jd_changed" in reasons


def test_revalidate_empty_batch(tmp_path: Path) -> None:
    """空批次处理：无 approved 岗位时返回 empty。"""
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.storage import save_job_application, update_job_application_status

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(write_config(tmp_path, database_path), registry_builder=build_registry, services_builder=build_services)
    runtime.create_or_open_session("session-001")

    # 保存一个岗位但不标记为 approved（保持 pending_review）
    job = save_job_application(
        database_path,
        platform="boss",
        platform_job_id="pj-empty",
        job_url="https://example.com/jobs/pj-empty",
        company_name="测试公司",
        title="后端工程师",
        location="上海",
        employment_type="full_time",
        salary_range="30k-50k",
        posted_at="2026-06-10T09:00:00+00:00",
        remote_policy=None,
        level="mid",
        experience_requirement="3年",
        education_requirement="本科",
        industry="tech",
        company_size="100-499",
        funding_stage="series_a",
        tech_stack="python",
        benefits="meal",
        published_at="2026-06-09T09:00:00+00:00",
        detail_url="https://example.com/jobs/pj-empty",
        jd_text="负责后端开发",
        collected_at="2026-06-10T09:05:00+00:00",
        field_confidence='{"title":"high"}',
        normalized_payload='{"platform":"boss"}',
    )
    update_job_application_status(
        database_path,
        job_id=job["job_id"],
        status="submitted",
        confirmation_batch_id="batch-empty",
        confirmation_status="confirmed",
    )

    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter
    adapter = FakeJobPlatformAdapter(platform="boss", jobs=[])

    result = runtime.revalidate_confirmation_batch(
        session_id="session-001",
        confirmation_batch_id="batch-empty",
        adapters={"boss": adapter},
    )

    assert result["status"] == "empty"
    assert result["total_count"] == 0
    assert result["submittable_count"] == 0
    assert result["skipped_count"] == 0


def test_revalidate_nonexistent_batch_returns_not_found(tmp_path: Path) -> None:
    """不存在的批次返回 not_found。"""
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(write_config(tmp_path, database_path), registry_builder=build_registry, services_builder=build_services)
    runtime.create_or_open_session("session-001")

    adapter = FakeJobPlatformAdapter(platform="boss", jobs=[])

    result = runtime.revalidate_confirmation_batch(
        session_id="session-001",
        confirmation_batch_id="nonexistent-batch",
        adapters={"boss": adapter},
    )

    assert result["status"] == "not_found"
    assert result["total_count"] == 0


def test_revalidate_storage_status_correctly_updated(tmp_path: Path) -> None:
    """验证重校验后存储中各岗位状态正确更新。"""
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter
    from interview_agent.storage import get_confirmation_batch

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(write_config(tmp_path, database_path), registry_builder=build_registry, services_builder=build_services)
    runtime.create_or_open_session("session-001")

    # 岗位 1：正常通过
    good_job = _make_standard_job(platform_job_id="st-ok")
    good_id = _save_job_and_approve(database_path, platform_job_id="st-ok")
    # 岗位 2：已投递 → duplicate
    dup_job = _make_standard_job(platform_job_id="st-dup")
    dup_id = _save_job_and_approve(database_path, platform_job_id="st-dup")
    # 岗位 3：按钮不可用 → skipped
    btn_job = _make_standard_job(platform_job_id="st-btn")
    btn_id = _save_job_and_approve(database_path, platform_job_id="st-btn")

    adapter = FakeJobPlatformAdapter(
        platform="boss",
        jobs=[good_job, dup_job, btn_job],
        applied_job_ids={"st-dup"},
        unavailable_button_job_ids={"st-btn"},
    )

    runtime.revalidate_confirmation_batch(
        session_id="session-001",
        confirmation_batch_id="batch-001",
        adapters={"boss": adapter},
    )

    batch = get_confirmation_batch(database_path, confirmation_batch_id="batch-001")
    records_by_id = {r["job_id"]: r for r in batch["records"]}

    # 正常通过的岗位保持 approved
    assert records_by_id[good_id]["status"] == "approved"
    # 已投递的岗位标记为 duplicate
    assert records_by_id[dup_id]["status"] == "duplicate"
    assert records_by_id[dup_id]["duplicate_detected"] is True
    # 按钮不可用的岗位标记为 skipped
    assert records_by_id[btn_id]["status"] == "skipped"
    assert records_by_id[btn_id]["failure_reason"] == "button_unavailable"


def test_revalidate_jd_changed_detects_location_education_and_experience(tmp_path: Path) -> None:
    """验证 JD 变化检测覆盖地点、学历和经验字段。"""
    from interview_agent.gui_runtime import _jd_critical_fields_changed

    stored_job = {
        "salary_range": "30k-50k",
        "location": "上海",
        "education_requirement": "本科",
        "experience_requirement": "3年",
        "level": "mid",
        "jd_text": "负责后端开发",
    }

    # 地点变化
    changed_location = _make_standard_job(location="北京")
    assert _jd_critical_fields_changed(stored_job, changed_location) is True

    # 学历变化
    changed_education = _make_standard_job(education_requirement="硕士")
    assert _jd_critical_fields_changed(stored_job, changed_education) is True

    # 经验变化
    changed_experience = _make_standard_job(experience_requirement="5年")
    assert _jd_critical_fields_changed(stored_job, changed_experience) is True

    # 级别变化
    changed_level = _make_standard_job(level="senior")
    assert _jd_critical_fields_changed(stored_job, changed_level) is True

    # 没有变化
    unchanged = _make_standard_job()
    assert _jd_critical_fields_changed(stored_job, unchanged) is False


def test_revalidate_saves_results_to_session_store(tmp_path: Path) -> None:
    """重校验结果保存到 session store，可通过 get_revalidation_results 读取。"""
    from interview_agent.gui_runtime import load_runtime
    from interview_agent.job_platform_adapters import FakeJobPlatformAdapter

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(write_config(tmp_path, database_path), registry_builder=build_registry, services_builder=build_services)
    runtime.create_or_open_session("session-001")

    job = _make_standard_job(platform_job_id="sv-1")
    _save_job_and_approve(database_path, platform_job_id="sv-1")
    adapter = FakeJobPlatformAdapter(platform="boss", jobs=[job])

    runtime.revalidate_confirmation_batch(
        session_id="session-001",
        confirmation_batch_id="batch-001",
        adapters={"boss": adapter},
    )

    stored = runtime.get_revalidation_results(session_id="session-001")
    assert stored is not None
    assert stored["status"] == "ready"
    assert stored["submittable_count"] == 1
    assert stored["session_id"] == "session-001"


def test_get_revalidation_results_returns_none_when_no_results(tmp_path: Path) -> None:
    """未执行重校验时 get_revalidation_results 返回 None。"""
    from interview_agent.gui_runtime import load_runtime

    database_path = tmp_path / "runtime.sqlite3"
    initialize_database(database_path)
    set_knowledge_base_status(database_path, "ready")
    runtime = load_runtime(write_config(tmp_path, database_path), registry_builder=build_registry, services_builder=build_services)
    runtime.create_or_open_session("session-001")

    result = runtime.get_revalidation_results(session_id="session-001")
    assert result is None


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
