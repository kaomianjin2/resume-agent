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
9. 主 agent 在主分支更新 `TODO.md` 任务状态。
10. 新功能开发完成、测试通过、reviewer 通过后，主 agent 必须更新 `HISTORY.md` 功能变更历史。
11. 若项目架构有变动，主 agent 必须同步更新 `docs/architecture.svg` 和 `docs/architecture.md`。
12. 提交主分支上的 `TODO.md`、`HISTORY.md` 和架构图相关更新。
13. 推送主分支到远端。
14. 确认主分支包含任务提交、TODO 状态更新、HISTORY 记录和架构图更新。
15. 删除任务 worktree。

## Worktree 规则

- 每个任务一个 worktree。
- worktree 命名格式：`../ai-agent-task-<task-id>`。
- 分支命名格式：`task/<task-id>-<short-name>`。
- 合并前必须确认任务分支有提交。
- 合并前必须确认测试通过。
- 合并前必须确认 `reviewer` 结论为可继续。
- `TODO.md` 任务状态只由主 agent 更新。
- `HISTORY.md` 功能变更历史只由主 agent 更新。
- `docs/architecture.svg` 和 `docs/architecture.md` 架构图只由主 agent 更新。
- `TODO.md` 最终状态更新、`HISTORY.md` 记录和架构图更新必须发生在任务分支合并后、主分支推送前。
- 推送远端前禁止删除 worktree。
- 删除 worktree 前必须确认主分支包含任务提交、TODO 状态更新、HISTORY 记录和架构图更新。
- 删除 worktree 前必须确认主分支已推送远端。

## Commit 规则

- 所有 `git commit` 提交信息必须使用中文。
- 提交信息必须准确描述本次变更内容。
- 禁止使用纯英文提交信息。

## 功能变更历史

- 历史文件固定为 `HISTORY.md`。
- 每个完成的新功能必须新增一条记录。
- 记录必须包含日期、任务编号、功能名称、测试命令、reviewer 结论和影响范围。
- 只有满足以下条件后才能记录：
  - 任务分支已合并到主分支。
  - 最小必要测试已通过。
  - `reviewer` 结论为可继续。
- 推送主分支前必须验证 `HISTORY.md` 包含本次功能记录。

## 架构图维护

- 架构图文件固定为 `docs/architecture.svg`。
- 架构说明文件固定为 `docs/architecture.md`。
- 任一变更涉及运行时入口、节点编排、节点契约、存储结构、知识库构建、检索链路、配置边界或外部服务调用时，必须同步更新架构图。
- 推送主分支前必须验证架构图与当前代码、配置边界和运行流程一致。

## Review 规则

- 只使用一个 `reviewer` subagent 做审查。
- `reviewer` 必须同时覆盖规格符合性和代码质量。
- `reviewer` 发现问题后不得合并。
- `reviewer` 通过不能替代测试。
- 最终验收使用 `final_reviewer` subagent。
