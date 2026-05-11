# Interview Agent TODO

## Progress Legend

- `[ ]` 未开始
- `[~]` 进行中
- `[x]` 完成
- `[!]` 阻塞

## Global Success Criteria

1. `uv run pytest` 全部通过。
2. 知识库通过离线命令构建完成。
3. `uv run interview-agent` 不触发知识库接入，只检查知识库 ready 状态。
4. 用户可用自然语言触发任意节点。
5. 多节点串联执行前必须展示计划并获得确认。
6. 所有配置来自 `config/interview-agent.toml`，不读取环境变量。
7. 不修改 `/Users/cynicism/Desktop/面试` 原始资料。
8. 开发流程和 subagent 边界遵循 `.codex/rules/` 与 `.codex/agents/`。

## Task 0: Repository Bootstrap

**Status:** `[x]`  
**Owner:** implementer  
**Dependencies:** none

**Files:**

- Create: `pyproject.toml`
- Create: `src/interview_agent/__init__.py`
- Create: `tests/`
- Create: `config/interview-agent.toml.example`
1. [操作] 初始化 Python 项目结构 → verify: `rtk find . -maxdepth 3 -type f`
2. [操作] 配置 CLI entrypoint `interview-agent` → verify: `uv run interview-agent --help`
3. [操作] 添加基础测试入口 → verify: `uv run pytest`
4. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Task 1: Project Config System

**Status:** `[ ]`  
**Owner:** implementer  
**Dependencies:** Task 0

**Files:**

- Create: `src/interview_agent/config.py`
- Modify: `config/interview-agent.toml.example`
- Test: `tests/test_config.py`
1. [操作] 编写配置读取测试 → verify: `uv run pytest tests/test_config.py` 先失败
2. [操作] 实现默认读取 `config/interview-agent.toml` → verify: 测试可读取 TOML
3. [操作] 实现缺文件、缺字段、字段类型错误提示 → verify: 对应测试通过
4. [操作] 确认不读取环境变量 → verify: `uv run pytest tests/test_config.py -k "does_not_read_environment"`
5. [操作] 确认 example 不包含真实密钥 → verify: example 仅包含占位值
6. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Task 2: SQLite Stable Storage Layer

**Status:** `[ ]`  
**Owner:** implementer  
**Dependencies:** Task 1

**Files:**

- Create: `src/interview_agent/storage.py`
- Create: `src/interview_agent/schema.sql`
- Test: `tests/test_storage.py`
1. [操作] 编写 schema 初始化测试 → verify: `uv run pytest tests/test_storage.py` 先失败
2. [操作] 实现稳定底层表 → verify: 存在 `sessions`、`session_state`、`node_runs`、`knowledge_documents`、`knowledge_chunks`、`knowledge_base_meta`
3. [操作] 实现 `knowledge_base_meta` ready 状态读写 → verify: 测试可写入并读取 `status = ready`
4. [操作] 实现事务封装 → verify: 写入失败时不留下半成品记录
5. [操作] 明确不创建评分/训练业务表 → verify: schema 测试确认不存在提前固化业务表
6. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Task 3: Offline Knowledge Documents Builder

**Status:** `[ ]`  
**Owner:** implementer  
**Dependencies:** Task 2

**Files:**

- Create: `src/interview_agent/kb/file_policy.py`
- Create: `src/interview_agent/kb/build.py`
- Create: `src/interview_agent/kb/parser.py`
- Create: `src/interview_agent/kb/chunking.py`
- Test: `tests/test_kb_file_policy.py`
- Test: `tests/test_kb_build.py`
1. [操作] 编写文件筛选策略测试 → verify: `uv run pytest tests/test_kb_file_policy.py`
2. [操作] 实现 include/exclude 规则 → verify: 简历、离职证明、图片、Excel、公司流程目录被排除
3. [操作] 编写解析测试 → verify: MD/PDF/DOCX fixture 可抽取文本
4. [操作] 实现 chunk 切分和内容 hash → verify: 同一文件重复构建不重复入库
5. [操作] 实现离线构建命令 → verify: `uv run python -m interview_agent.kb.build --source /Users/cynicism/Desktop/面试 --config config/interview-agent.toml --db data/interview_agent.sqlite`
6. [操作] 写入构建状态 → verify: 成功后 `knowledge_base_meta.status = ready`
7. [操作] 确认 Task 3 不做检索排序和 embedding → verify: 测试不依赖 embedding 模型
8. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Task 4: Local Embedding, FTS, And Hybrid Retrieval

**Status:** `[ ]`  
**Owner:** implementer  
**Dependencies:** Task 3

**Files:**

- Create: `src/interview_agent/kb/embedding.py`
- Create: `src/interview_agent/kb/retrieval.py`
- Test: `tests/test_retrieval.py`
1. [操作] 编写 fake embedder 测试 → verify: 测试不下载真实模型
2. [操作] 实现 bge-m3 本地 embedding 适配 → verify: 模型路径来自配置文件
3. [操作] 实现 FTS 表创建和维护 → verify: 关键词查询返回 chunk
4. [操作] 实现 embedding 存储 → verify: chunk 向量可写入和读取
5. [操作] 实现向量检索 → verify: fake vector 查询返回稳定排序
6. [操作] 实现混合排序 → verify: 返回 `chunk_id`、`content`、`score`、`source_path`
7. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Task 5: LLM Client And Structured Output

**Status:** `[ ]`  
**Owner:** implementer  
**Dependencies:** Task 1

**Files:**

- Create: `src/interview_agent/llm.py`
- Create: `src/interview_agent/prompts.py`
- Test: `tests/test_llm.py`
1. [操作] 编写 fake LLM 测试 → verify: 固定 JSON 返回可解析
2. [操作] 实现 OpenAI-compatible client → verify: base_url、api_key、model 来自配置文件
3. [操作] 实现 JSON 输出解析 → verify: 非 JSON 返回明确错误
4. [操作] 实现 prompt 模板管理 → verify: 每个节点能引用对应 prompt
5. [操作] 确认不读取环境变量 → verify: LLM 测试覆盖 `os.environ` 不影响 client
6. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Task 6: Runtime Node Registry

**Status:** `[ ]`  
**Owner:** implementer  
**Dependencies:** Task 2, Task 4, Task 5

**Files:**

- Create: `src/interview_agent/nodes/spec.py`
- Create: `src/interview_agent/nodes/registry.py`
- Test: `tests/test_node_registry.py`
1. [操作] 编写节点注册测试 → verify: 能列出所有节点名称、输入、输出
2. [操作] 定义 `NodeSpec` → verify: 包含 `name`、`description`、`required_inputs`、`optional_inputs`、`outputs`、`handler`
3. [操作] 注册首版节点 → verify: 包含 `knowledge_search`、`resume_parse`、`project_extract`、`jd_parse`、`jd_match`、`question_generate`、`mock_followup`、`answer_score`、`weakness_train`、`resume_optimize`、`session_summary`
4. [操作] 实现至少 2 个 fake node 的依赖检查 → verify: `uv run pytest tests/test_node_registry.py`
5. [操作] 实现查找失败路径 → verify: 未知节点返回明确错误
6. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Task 7: Conversation Router And Planner

**Status:** `[ ]`  
**Owner:** implementer  
**Dependencies:** Task 6

**Files:**

- Create: `src/interview_agent/router.py`
- Create: `src/interview_agent/planner.py`
- Test: `tests/test_router_planner.py`
1. [操作] 编写自然语言路由测试 → verify: “生成 Go 面试题” 命中 `question_generate`
2. [操作] 实现规则兜底路由 → verify: 常见关键词不依赖 LLM 也能命中节点
3. [操作] 实现 LLM 分类接口 → verify: fake LLM 返回候选节点
4. [操作] 定义 `PlanStep`、`ExecutionPlan`、`PlanConfirmation` → verify: 多节点计划可展示
5. [操作] 实现多节点计划生成 → verify: 缺 JD 时计划包含 `jd_parse` + `question_generate`
6. [操作] 实现确认约束 → verify: `uv run pytest tests/test_router_planner.py -k "multi_node_plan_requires_confirmation"`
7. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Task 8A: Node Executor And Session State

**Status:** `[ ]`  
**Owner:** implementer  
**Dependencies:** Task 7

**Files:**

- Create: `src/interview_agent/executor.py`
- Create: `src/interview_agent/session.py`
- Test: `tests/test_executor.py`
1. [操作] 编写单节点执行测试 → verify: fake node 可独立执行并写入结果
2. [操作] 实现 session 状态读写 → verify: `uv run pytest tests/test_executor.py -k "nodes_share_state_only_through_sqlite"`
3. [操作] 实现 node_runs 记录 → verify: 成功、失败状态均可查询
4. [操作] 实现依赖检查 → verify: 缺输入时返回需要补齐的数据项
5. [操作] 实现失败记录 → verify: 节点失败写入错误状态，不污染成功结果
6. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Task 8B: Interview Node Handlers

**Status:** `[ ]`  
**Owner:** implementer  
**Dependencies:** Task 8A

**Files:**

- Create: `src/interview_agent/agents.py`
- Create: `src/interview_agent/nodes/interview.py`
- Test: `tests/test_interview_nodes.py`
1. [操作] 编写 handler 测试 → verify: fake LLM 下每个 handler 输出结构化结果
2. [操作] 实现简历/JD 输入 handler → verify: 简历和 JD 作为 session 输入，不进入知识库
3. [操作] 实现题目、追问、评分、训练、优化 handler → verify: 输出写入 session_state
4. [操作] 实现 RAG context 注入 → verify: 需要知识增强的节点能读取检索 chunk
5. [操作] 避免提前创建评分/训练业务表 → verify: 结果以 node output/session_state 保存
6. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Task 9: Interactive CLI

**Status:** `[ ]`  
**Owner:** implementer  
**Dependencies:** Task 8B

**Files:**

- Create/Modify: `src/interview_agent/cli.py`
- Test: `tests/test_cli.py`
1. [操作] 编写启动检查测试 → verify: 知识库缺失时只提示离线构建命令
2. [操作] 验证启动时不构建知识库 → verify: `uv run pytest tests/test_cli.py -k "does_not_build_knowledge_base_on_startup"`
3. [操作] 实现交互入口 → verify: `uv run interview-agent` 进入输入提示
4. [操作] 实现自然语言请求循环 → verify: 用户输入后展示匹配节点或执行计划
5. [操作] 实现缺输入补齐交互 → verify: 缺 JD 时可输入文本或选择文件
6. [操作] 实现多节点确认 → verify: 未确认时不执行计划
7. [操作] 实现直接节点命令 → verify: `/node question_generate` 可触发指定节点
8. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Final Review

**Status:** `[ ]`  
**Owner:** final_reviewer  
**Dependencies:** Task 0-9

1. [操作] 运行全量测试 → verify: `uv run pytest`
2. [操作] 运行知识库构建 → verify: `uv run python -m interview_agent.kb.build --source /Users/cynicism/Desktop/面试 --config config/interview-agent.toml --db data/interview_agent.sqlite`
3. [操作] 启动交互式 Agent → verify: `uv run interview-agent --config config/interview-agent.toml`
4. [操作] 手工验证单节点 → verify: `/node knowledge_search`
5. [操作] 手工验证未确认多节点 → verify: 多节点计划未确认时不执行
6. [操作] 手工验证确认后多节点 → verify: 确认后生成题目或评分结果
7. [操作] 手工验证 KB 未 ready → verify: 只提示离线构建命令
8. [操作] 最终验收审查 → verify: final_reviewer 同时确认需求、架构、测试、流程合规且无阻塞问题
