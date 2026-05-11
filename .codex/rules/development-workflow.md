# Development Workflow Rules

## 主 Agent 边界

- 主 agent 不负责任何代码、功能开发和修改。
- 主 agent 只负责协调、拆分、指派、答疑、审查调度、合并、推送、删除 worktree、更新任务状态。
- 主 agent 禁止在主分支直接开发。
- 主 agent 禁止跳过 subagent、跳过 review、跳过测试、跳过推送。

## 每任务流程

每个 TODO 任务必须按顺序执行：

1. 创建独立 worktree 和任务分支。
2. 派发 fresh `implementer` subagent。
3. `implementer` 在任务 worktree 内实现、测试、自检、提交。
4. 派发 `reviewer` subagent。
5. `reviewer` 同时完成规格符合性审查和代码质量审查。
6. 审查失败时，由同一个 `implementer` 修复并重新审查。
7. 审查通过后，在任务 worktree 运行最小必要测试。
8. 合并任务分支到主分支。
9. 主 agent 在主分支更新 `TODO.md` 任务状态并提交。
10. 推送主分支到远端。
11. 确认主分支包含任务提交和 TODO 状态更新。
12. 删除任务 worktree。

## Worktree 规则

- 每个任务一个 worktree。
- worktree 命名格式：`../ai-agent-task-<task-id>`。
- 分支命名格式：`task/<task-id>-<short-name>`。
- 合并前必须确认任务分支有提交。
- 合并前必须确认测试通过。
- 合并前必须确认 `reviewer` 结论为可继续。
- `TODO.md` 任务状态只由主 agent 更新。
- `TODO.md` 最终状态更新必须发生在任务分支合并后、主分支推送前。
- 推送远端前禁止删除 worktree。
- 删除 worktree 前必须确认主分支包含任务提交。
- 删除 worktree 前必须确认主分支已推送远端。

## Review 规则

- 只使用一个 `reviewer` subagent 做审查。
- `reviewer` 必须同时覆盖规格符合性和代码质量。
- `reviewer` 发现问题后不得合并。
- `reviewer` 通过不能替代测试。
- 最终验收使用 `final_reviewer` subagent。
