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
5. 路由明确时直接执行；处理方向不确定时询问用户选择。
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

**Status:** `[x]`  
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

**Status:** `[x]`  
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

**Status:** `[x]`  
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

**Status:** `[x]`  
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

**Status:** `[x]`  
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

**Status:** `[x]`
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

**Status:** `[x]`  
**Owner:** implementer  
**Dependencies:** Task 6

**Files:**

- Create: `src/interview_agent/router.py`
- Create: `src/interview_agent/planner.py`
- Test: `tests/test_router_planner.py`
1. [操作] 编写自然语言路由测试 → verify: “生成 Go 面试题” 命中 `question_generate`
2. [操作] 实现规则兜底路由 → verify: 常见关键词不依赖 LLM 也能命中节点
3. [操作] 实现 LLM 分类接口 → verify: fake LLM 返回候选节点
4. [操作] 定义 `PlanStep`、`ExecutionPlan` → verify: 多节点内部步骤可生成
5. [操作] 实现多节点计划生成 → verify: 缺 JD 时计划包含 `jd_parse` + `question_generate`
6. [操作] 实现不确定路由选择 → verify: `uv run pytest tests/test_cli.py -k "ambiguous_route_asks_user_to_choose_direction"`
7. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Task 8A: Node Executor And Session State

**Status:** `[x]`  
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

**Status:** `[x]`  
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

**Status:** `[x]`  
**Owner:** implementer  
**Dependencies:** Task 8B

**Files:**

- Create/Modify: `src/interview_agent/cli.py`
- Test: `tests/test_cli.py`
1. [操作] 编写启动检查测试 → verify: 知识库缺失时只提示离线构建命令
2. [操作] 验证启动时不构建知识库 → verify: `uv run pytest tests/test_cli.py -k "does_not_build_knowledge_base_on_startup"`
3. [操作] 实现交互入口 → verify: `uv run interview-agent` 进入输入提示
4. [操作] 实现自然语言请求循环 → verify: 路由明确时直接执行，路由不确定时询问方向
5. [操作] 实现缺输入补齐交互 → verify: 缺 JD 时可输入文本或选择文件
6. [操作] 实现多节点内部执行 → verify: 不展示内部执行计划或节点名
7. [操作] 实现直接节点命令 → verify: `/node question_generate` 可触发指定节点
8. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Evolution Phase 2A: 普通请求编排入口拆分

**Status:** `[x]`  
**Owner:** implementer  
**Dependencies:** Phase 1

**Files:**

- Create: `src/interview_agent/orchestrator.py`
- Modify: `src/interview_agent/cli.py`
- Test: `tests/test_cli.py`
1. [操作] 新增 `run_user_request()` 承接普通请求编排 → verify: `rtk uv run pytest tests/test_cli.py -k "natural_language_request or missing_jd_input"`
2. [操作] `cli.main()` 将非模拟面试请求委派给 `run_user_request()` → verify: `rtk uv run pytest tests/test_cli.py -k "matched_node or missing_jd_input"`
3. [操作] 确认节点 handler 不读取用户输入 → verify: `rtk rg "input_func" src/interview_agent/nodes src/interview_agent/agents.py`
4. [操作] 合并审查 → verify: reviewer 同时确认规格符合性和代码质量通过

## Final Review

**Status:** `[~]`  
**Owner:** final_reviewer  
**Dependencies:** Task 0-9

1. [操作] 运行全量测试 → verify: `uv run pytest`
2. [操作] 运行知识库构建 → verify: `uv run python -m interview_agent.kb.build --source /Users/cynicism/Desktop/面试 --config config/interview-agent.toml --db data/interview_agent.sqlite`
3. [操作] 启动交互式 Agent → verify: `uv run interview-agent --config config/interview-agent.toml`
4. [操作] 手工验证单节点 → verify: `/node knowledge_search`
5. [操作] 手工验证明确路由多节点 → verify: 不展示执行计划，补齐输入后直接生成结果
6. [操作] 手工验证不确定路由 → verify: 询问用户处理方向后再执行
7. [操作] 手工验证 KB 未 ready → verify: 只提示离线构建命令
8. [操作] 最终验收审查 → verify: final_reviewer 同时确认需求、架构、测试、流程合规且无阻塞问题

## Evolution Phase 6: 端到端验收场景固化

**Status:** `[x]`
**Owner:** final_reviewer
**Dependencies:** Phase 2、Phase 3、Phase 4、Phase 5

1. [x] [操作] 运行端到端 CLI 流测试 → verify: `rtk uv run pytest tests/test_e2e_cli_flow.py`：4 passed
2. [x] [操作] 运行模拟面试验收测试 → verify: `rtk uv run pytest tests/test_cli.py -k "mock"`：23 passed
3. [x] [操作] 运行全量测试 → verify: `rtk uv run pytest`：175 passed
4. [ ] [操作] 手工构建知识库 → verify: `rtk uv run python -m interview_agent.kb.build --source /Users/cynicism/Desktop/面试 --config config/interview-agent.toml --db data/interview_agent.sqlite`
5. [ ] [操作] 手工启动交互式 Agent → verify: `rtk uv run interview-agent --config config/interview-agent.toml`
6. [x] [操作] 固化手工验证清单，覆盖明确路由、缺输入补齐、不确定路由、模拟面试和失败恢复 → verify: CLI 不展示内部节点名，不访问网络，不修改 `/Users/cynicism/Desktop/面试`

## Feature Track: 求职投递功能

**Status:** `[ ]`  
**Owner:** main agent / implementer / reviewer  
**Dependencies:** 已有简历解析、JD 解析、匹配评估、GUI runtime

**Reference Docs:**

- `docs/job-application-feature-design.md`
- `docs/job-application-development-tasks.md`

1. [操作] 按 `docs/job-application-development-tasks.md` 逐项执行 JOB-001 到 JOB-019 → verify: 每个任务均有独立 worktree、implementer 提交、reviewer 结论、最小必要测试和观测证据
   - [x] JOB-001 求职数据模型与存储设计 → verify: `rtk uv run pytest -p no:cacheprovider tests/test_storage.py`：14 passed；reviewer 第三次复审 `可继续`
   - [x] JOB-002 求职画像生成 → verify: `rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py`：32 passed；reviewer 复审 `可继续`
   - [x] JOB-003 平台适配器接口 → verify: `rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`：49 passed；reviewer `可继续`
   - [x] JOB-004 Chrome 会话隔离与敏感信息脱敏边界 → verify: `rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_interview_nodes.py tests/test_storage.py`：71 passed；reviewer 复审 `可继续`
   - [x] JOB-005 适配器夹具与契约测试基建 → verify: `rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py`：44 passed；reviewer 第四次复审 `可继续`
2. [操作] 每个任务合并后由主 agent 更新本 TODO 状态与专项任务文档状态 → verify: `rtk git diff -- docs/TODO.md docs/job-application-development-tasks.md`
3. [操作] 功能完成后由主 agent 更新 `HISTORY.md` → verify: HISTORY 记录包含任务编号、功能名称、测试命令、reviewer 结论和影响范围
4. [操作] 涉及架构变更后由主 agent 更新 `docs/architecture.md` 与 `docs/architecture.svg` → verify: `rtk xmllint --noout docs/architecture.svg`
