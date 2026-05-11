# Project Rules Index

本文件是项目规则入口。

## 规则文件

- `development-workflow.md`：主 agent 职责、worktree 流程、subagent 派发、合并、推送、清理规则。
- `runtime-architecture.md`：运行时可选节点、知识库、配置和状态边界。

## 加载原则

- 开始任务前读取本文件。
- 涉及开发执行、任务状态、分支、worktree、合并、推送、清理时读取 `development-workflow.md`。
- 涉及运行时 agent、知识库、配置、节点编排时读取 `runtime-architecture.md`。
- Subagent 只遵守主 agent 为当前任务提供的任务说明、Write Scope 和必要规则片段。
