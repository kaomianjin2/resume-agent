# 功能变更历史

本文件记录已完成、已测试、已通过审查的新功能变更。

## 记录规则

- 新功能开发完成后记录。
- 最小必要测试通过后记录。
- `reviewer` 审查通过后记录。
- 任务分支合并到主分支后、推送主分支前记录。

## 记录模板

```markdown
## YYYY-MM-DD - Task N: 功能名称

- 测试命令：`rtk uv run pytest ...`
- reviewer 结论：可继续
- 影响范围：文件 / 函数 / 接口
- 变更摘要：
  - ...
```

## 历史记录

## 2026-05-14 - Phase 0: 当前主线收口

- 测试命令：`rtk uv run pytest tests/test_router_planner.py tests/test_cli.py`；`rtk uv run pytest`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/cli.py` / `_select_node_for_route()`；`tests/test_cli.py`；`docs/EVOLUTION_PLAN.md`
- 变更摘要：
  - 取消多节点确认约束收口完成，路由明确时继续直接执行。
  - 修复规则路由多候选时未询问处理方向的问题。
  - 补充规则路由多候选回归测试，确认不展示内部节点名。
