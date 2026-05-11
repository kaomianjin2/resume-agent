# AGENTS.md

## 项目入口规则

- 始终使用简体中文。
- 用户指令优先。
- 需求、架构与任务清单见 `PLAN.md` 和 `TODO.md`。
- 开发流程、worktree 约束、主 agent 边界见 `.codex/rules/`。
- 开发 subagent 定义见 `.codex/agents/`。

## 项目边界

- 配置文件落在 `config/interview-agent.toml`。
- 不使用环境变量读取项目配置。
- 知识库在开发期预构建，运行时只检查 ready 状态。
- 不修改 `/Users/cynicism/Desktop/面试` 原始资料。
- 简历、离职证明、图片、Excel、公司流程类资料不得入库。
