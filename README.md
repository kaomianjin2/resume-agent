# Interview Agent

本项目是一个本地技术面试 Agent 桌面应用。它基于 Tauri + React 构建桌面 GUI，围绕简历、招聘 JD、知识库资料和模拟面试流程，完成面试准备与求职投递相关任务。

## 功能

- 自然语言触发能力节点
- 简历解析和候选人画像整理
- 招聘 JD 解析和岗位要求整理
- 简历与 JD 匹配分析
- 面试题生成
- 模拟面试、追问和参考答案
- 回答评分和改进建议
- 薄弱点训练计划
- 简历优化建议
- 本地知识库检索

## 架构

```text
Tauri Desktop Shell (Rust)
  ↓
React Web Shell (TypeScript)
  ↓
GUI Runtime Facade (gui_runtime.py)
  ↓
Router → Planner → Executor → Node Handlers
  ↓
SQLite Session State + Knowledge Retriever + LLM Client
```

关键约束：

- 配置固定读取 `config/interview-agent.toml`。
- 不使用环境变量读取项目配置。
- 知识库通过离线命令预构建。
- 运行时启动时只检查知识库 ready 状态，不构建知识库。
- 节点之间只通过 SQLite `session_state` 共享数据。
- 不修改 `/Users/cynicism/Desktop/面试` 原始资料。

更多架构说明见 [docs/architecture.md](docs/architecture.md)。

## 目录

```text
config/                         配置示例
data/                           SQLite 数据库目录
docs/                           计划、架构和历史文档
gui/                            Tauri + React 桌面 GUI
models/                         本地 embedding 模型目录
src/interview_agent/            运行时代码
tests/                          测试
```

## 准备环境

项目使用 Python 3.11+ 和 `uv`。

```bash
uv sync
```

验证运行时入口：

```bash
uv run interview-agent --help
```

## 配置

复制示例配置：

```bash
cp config/interview-agent.toml.example config/interview-agent.toml
```

编辑 `config/interview-agent.toml`：

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

## 构建知识库

知识库来源支持：

```text
*.md
*.pdf
*.docx
```

构建命令：

```bash
uv run python -m interview_agent.kb.build \
  --source /Users/cynicism/Desktop/面试 \
  --config config/interview-agent.toml \
  --db data/interview_agent.sqlite
```

构建成功后，SQLite 中的 `knowledge_base_meta.status` 会写入 `ready`。

## 启动桌面 GUI

开发模式：

```bash
cd gui
npm run tauri dev
```

生产构建：

```bash
cd gui
npm run tauri build
```

Tauri Desktop Shell 会自动启动 Python 运行时进程，加载配置并检查知识库状态。用户通过 React GUI 进行交互，所有操作通过 GUI Runtime Facade 调用 Python 后端。

## 运行测试

全量测试：

```bash
uv run pytest
```

知识库相关测试：

```bash
uv run pytest tests/test_kb_build.py tests/test_retrieval.py
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
job_evaluation
```

## 文档

- [docs/PLAN.md](docs/PLAN.md)：项目目标、约束和实现计划
- [docs/TODO.md](docs/TODO.md)：任务拆解和验收标准
- [docs/architecture.md](docs/architecture.md)：当前架构说明
- [docs/HISTORY.md](docs/HISTORY.md)：已完成变更历史
