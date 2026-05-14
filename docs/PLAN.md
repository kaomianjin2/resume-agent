# 技术面试 Agent 实现计划

## 目标

构建一个本地交互式技术面试 Agent，支持：

- 开发期预构建知识库
- 对话式节点调度
- 用户可选能力节点
- 简历解析
- 项目经历提炼
- JD 匹配
- 面试题生成
- 模拟追问
- 答案评分
- 薄弱点训练
- 简历反向优化

## 核心约束

- CLI 是交互式入口，不是固定流水线。
- 用户通过自然语言触发能力节点。
- 处理方向不确定时询问用户选择；路由明确时直接执行。
- 配置落在 `config/interview-agent.toml`。
- 不使用环境变量读取配置。
- 知识库在开发期提前构建。
- `uv run interview-agent` 启动时不接入知识库。
- 启动时只检查知识库 ready 状态。
- 不修改 `/Users/cynicism/Desktop/面试` 原始资料。
- 开发流程、worktree 约束和 subagent 边界见 `.codex/rules/` 与 `.codex/agents/`。

## 架构

```text
Interactive CLI
  ↓
Conversation Router
  ↓
Node Planner
  ↓
Node Executor
  ↓
SQLite Session State + Knowledge Retriever + LLM Client
```

## 配置

配置文件路径：

```text
config/interview-agent.toml
```

示例配置：

```toml
[llm]
base_url = "https://your-openai-compatible-endpoint/v1"
api_key = "your-key"
model = "your-model"

[embedding]
provider = "local"
model_name = "BAAI/bge-m3"
model_path = "./models/bge-m3"

[storage]
database_path = "./data/interview_agent.sqlite"

[knowledge_base]
source = "/Users/cynicism/Desktop/面试"
chunk_size = 900
chunk_overlap = 120
top_k = 8
index_version = "v1"
```

## 知识库

来源：

```bash
/Users/cynicism/Desktop/面试
```

包含：

```text
*.md
*.pdf
*.docx
```

排除：

```text
简历/**
**/离职证明.*
lyjs一起写文档/**
*.png
*.jpg
*.jpeg
*.webp
*.xlsx
```

开发期构建命令：

```bash
uv run python -m interview_agent.kb.build \
  --source /Users/cynicism/Desktop/面试 \
  --config config/interview-agent.toml \
  --db data/interview_agent.sqlite
```

检索方式：

```text
SQLite FTS + 本地 bge-m3 embedding 混合检索
```

## 运行时节点

```text
knowledge_search
resume_parse
project_extract
jd_parse
jd_match
question_generate
mock_followup
answer_score
weakness_train
resume_optimize
session_summary
```

## 执行规则

- 每个节点独立执行。
- 节点之间只通过 SQLite session state 共享数据。
- 缺少节点输入时，CLI 提示用户补齐。
- 单节点可直接执行。
- 路由明确时直接执行内部步骤。
- 处理方向不确定时询问用户选择，不展示内部节点名。
- 节点失败必须写入失败状态，不污染成功结果。


## 验证

```bash
uv run pytest

uv run python -m interview_agent.kb.build \
  --source /Users/cynicism/Desktop/面试 \
  --config config/interview-agent.toml \
  --db data/interview_agent.sqlite

uv run interview-agent
```

## 副作用

- 新增项目文件、配置文件、SQLite 数据库和本地索引。
- 不修改 `/Users/cynicism/Desktop/面试` 原始资料。
- 不覆盖原始简历文件。
