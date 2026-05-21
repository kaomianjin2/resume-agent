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

## 2026-05-21 - GUI UI 原型视觉级完全还原

- Tracking ID：`gui-ui-restore`
- 测试命令：`rtk npm run build`；`rtk python3 -m http.server 4173`；`rtk python3 -m http.server 4174`；Playwright 采集 1440x900、1180x900、820x900 当前实现截图；Playwright 采集 1440x900 原型截图；Playwright DOM 量测三视口布局与关键组件样式
- reviewer 结论：最终视觉验收通过；当前实现与 `docs/gui-mvp-cyberpunk-mockup.html` 在 1440x900 下无结构性差异，1180x900、820x900 断点行为一致；业务数据值保留动态来源
- 影响范围：`docs/GUI_UI_RESTORE_PLAN.md`；`docs/HISTORY.md`
- 完成证据：
  - 当前实现截图：`.playwright-cli/page-2026-05-21T09-14-26-873Z.png`、`.playwright-cli/page-2026-05-21T09-14-46-503Z.png`、`.playwright-cli/page-2026-05-21T09-15-07-249Z.png`
  - 原型截图：`.playwright-cli/page-2026-05-21T09-15-36-751Z.png`
  - DOM 量测：1440x900 为 `220px 780px 360px`；1180x900 为 `200px 918px` 且右栏在第二列；820x900 为 `792px` 单列；三视口无横向滚动
- 变更摘要：
  - 完成 GUI UI 还原最终浏览器验收，确认深色霓虹主题、三栏布局、准备页结构、准备板密度和右侧检查面板结构达标。
  - 保留真实业务文案和值的动态来源，不修改后端、配置、数据库、依赖和部署流程。

## 2026-05-21 - GUI UI 原型还原

- 测试命令：`rtk npm run build`；`rtk npm run test:desktop`；`rtk uv run pytest tests/test_gui_runtime.py`；`rtk uv run pytest tests/test_cli.py -k "mock_interview"`；`rtk npm run preview -- --port 4173`；Playwright 桌面截图和控制台验收
- reviewer 结论：subagent 指出 UI 原型还原、prep 信息槽位和右侧检查面板需修复；主 agent 已按原型修复并完成浏览器复核
- 影响范围：`gui/src/app/App.tsx`；`gui/src/app/fixtureData.ts`；`gui/src/app/layout/ShellLayout.tsx`；`gui/src/app/layout/Sidebar.tsx`；`gui/src/app/layout/Workspace.tsx`；`gui/src/app/layout/ReviewPanel.tsx`；`gui/src/modules/prep/PrepModule.tsx`；`gui/src/shared/styles/global.css`；`docs/HISTORY.md`
- 变更摘要：
  - 将 GUI 视觉主题从浅色纸张风格恢复为 `docs/gui-mvp-cyberpunk-mockup.html` 的深色赛博朋克三栏界面。
  - 面试准备页恢复原型标题、摘要卡、导入按钮、准备包预览和 `简历摘要 / 岗位重点 / 匹配度 / 优势 / 风险 / 追问重点` 六个可见信息槽位。
  - 准备检查面板恢复原型的大号准备完整度、匹配度、追问点、材料状态和建议卡片结构。

## 2026-05-20 - GUI Phase 6: 桌面壳集成

- 测试命令：`rtk npm run test:desktop`；`rtk npm run build`；`rtk npm run tauri build`；`cargo test`；`rtk uv run pytest tests/test_gui_runtime.py`
- reviewer 结论：可继续
- 影响范围：`gui/src-tauri/`；`gui/src/shared/desktop/`；`gui/src/app/App.tsx`；`gui/src/app/layout/ShellLayout.tsx`；`gui/src/app/layout/Sidebar.tsx`；`gui/src/shared/styles/global.css`；`gui/tests/desktopSnapshot.test.mjs`；`docs/GUI_DEVELOPMENT_PLAN.md`；`docs/HISTORY.md`；`docs/architecture.md`；`docs/architecture.svg`
- 变更摘要：
  - 新增 Tauri v2 桌面壳配置和 macOS app 打包能力，桌面窗口直接承载 React Web Shell。
  - 桌面桥接层展示 KB 状态、Python runtime 状态、简历/JD 本地文件选择和异常信息。
  - Python runtime 以独立进程组启动，停止或关闭窗口时清理进程树，避免残留后端进程。
  - 前端新增桌面错误快照测试，覆盖 Tauri invoke 或文件选择失败时的 `lastError` 回填。

## 2026-05-19 - GUI Phase 5: 算法练习 MVP

- 测试命令：`rtk npm run build`
- reviewer 结论：主 agent 复审通过，可继续
- 影响范围：`gui/src/modules/algorithm/AlgorithmModule.tsx`；`gui/src/app/fixtureData.ts`；`docs/GUI_DEVELOPMENT_PLAN.md`；`docs/HISTORY.md`
- 变更摘要：
  - 算法练习页使用 fixture 数据展示题干、约束、示例、标签、语言选择、编辑器、运行结果和评审面板。
  - 语言选择覆盖 Python、JavaScript、Go、Java、C、C++，切换后编辑区展示对应示例代码。
  - 运行结果 fixture 覆盖空代码、错误代码、通过用例三种状态；评审面板展示正确性、复杂度、边界 case 和建议。

## 2026-05-19 - GUI Phase 4: 模拟面试闭环

- 测试命令：`rtk uv run pytest tests/test_gui_runtime.py`；`rtk uv run pytest tests/test_cli.py -k "mock_interview"`；`rtk npm run build`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/gui_runtime.py` / `start_mock_interview()`、`submit_mock_answer()`、`end_mock_interview()`；`tests/test_gui_runtime.py`；`gui/src/modules/mock/MockModule.tsx`；`gui/src/shared/api/mock.ts`；`gui/src/shared/styles/global.css`；`docs/GUI_DEVELOPMENT_PLAN.md`；`docs/HISTORY.md`；`docs/architecture.md`；`docs/architecture.svg`
- 变更摘要：
  - GUI runtime facade 新增模拟面试闭环入口，按既有节点契约复用 `question_generate`、`mock_followup`、`answer_score`，并把当前轮次状态写入 SQLite `session_state`。
  - 模拟面试页通过 runtime client interface 展示逐题回答、追问、空回答提示、空题集错误、结束操作和评分/风险/改进建议。
  - 完成态和结束态阻断后续回答提交，避免污染后续会话状态；CLI 模拟面试回归保持通过。

## 2026-05-18 - GUI Phase 3: 面试准备真实接入

- 测试命令：`rtk uv run pytest tests/test_gui_runtime.py`；`rtk npm run build`
- reviewer 结论：未运行 reviewer；本次按用户要求在主 agent 内完成
- 影响范围：`src/interview_agent/gui_runtime.py` / `prepare_interview_materials()`；`tests/test_gui_runtime.py`；`gui/src/modules/prep/PrepModule.tsx`；`gui/src/shared/api/prep.ts`；`gui/src/app/layout/Workspace.tsx`；`gui/src/app/layout/ReviewPanel.tsx`；`docs/GUI_DEVELOPMENT_PLAN.md`；`docs/architecture.md`；`docs/architecture.svg`
- 变更摘要：
  - GUI runtime facade 新增面试准备聚合入口，按既有节点契约串联 `resume_parse`、`jd_parse`、`jd_match`，并返回 GUI 可读 view model。
  - 面试准备页改为展示简历摘要、岗位重点、匹配度、优势、风险和追问重点，不展示原始结构化数据。
  - 准备页移除顶部动作按钮，题目生成入口继续只保留在模拟面试模块。

## 2026-05-17 - GUI Phase 2: React Web Shell

- 测试命令：`rtk npm install`；`rtk npm run build`；`rtk npm run preview -- --port 4173`
- reviewer 结论：未运行 reviewer；本次按用户要求在主 agent 内完成
- 影响范围：`gui/`；`docs/GUI_DEVELOPMENT_PLAN.md`；`docs/HISTORY.md`
- 变更摘要：
  - 新增 React/Vite Web Shell 工程，使用 fixture view model 驱动面试准备、模拟面试、算法练习三个模块。
  - 实现桌面三栏、移动端单列响应式布局，模块切换后主区域与检查面板同步更新。
  - Web Shell 不接真实后端，不依赖真实 LLM、知识库或 SQLite。

## 2026-05-17 - GUI Phase 1: Runtime Facade

- 测试命令：`rtk uv run pytest tests/test_gui_runtime.py`；`rtk uv run pytest tests/test_executor.py tests/test_router_planner.py`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/gui_runtime.py`；`tests/test_gui_runtime.py`；`docs/architecture.md`；`docs/architecture.svg`
- 变更摘要：
  - 新增 GUI 专用 runtime facade，统一暴露配置、KB ready 状态、会话创建、路由、计划、执行和 session state 读取。
  - GUI 层改为直接消费结构化数据，不依赖 CLI 文本输出。
  - 架构图补充 GUI 运行时入口，并同步记录 Phase 1 完成情况。

## 2026-05-17 - GUI Phase 0: 设计与边界固化

- 测试命令：`rtk rg "面试准备|模拟面试|算法练习|检查面板" docs/GUI_DEVELOPMENT_PLAN.md`；`rtk rg "不修改数据库结构|不在 GUI 启动时构建知识库|config/interview-agent.toml" docs/GUI_DEVELOPMENT_PLAN.md`；`rtk rg "Status:|Tracking ID:|完成证据|阻塞原因|测试命令|可视化验收" docs/GUI_DEVELOPMENT_PLAN.md`；`rtk git diff --check -- docs/GUI_DEVELOPMENT_PLAN.md`
- reviewer 结论：可继续
- 影响范围：`docs/GUI_DEVELOPMENT_PLAN.md`
- 变更摘要：
  - 将 GUI 开发拆为 7 个可追踪阶段，并固化 Phase 0 完成状态、阶段依赖、Owner、Write Scope、测试命令和可视化验收。
  - 为 Runtime Facade、React Web Shell、面试准备接入、模拟面试闭环、算法练习 MVP、桌面壳集成补齐测试命令和可视化验收口径。
  - 补齐 React Web Shell 显式验收标准，并明确长驻预览命令的人工观察与 `Ctrl-C` 退出口径。

## 2026-05-16 - Phase 10: 算法练习代码安全检测

- 测试命令：`rtk uv run pytest tests/test_cli.py -k "algorithm_practice or inspect_code_safety or run_code"`
- reviewer 结论：未运行 reviewer；本次按用户要求在主 agent 内完成
- 影响范围：`src/interview_agent/cli.py` / `_run_algorithm_practice()`、`_inspect_code_safety()`、`_write_code_safety_rejection()`；`tests/test_cli.py`
- 变更摘要：
  - 算法练习运行用户代码前新增强制静态安全检测。
  - 检测到进程执行、网络访问、环境变量或密钥读取、破坏性文件操作、文件写入、绝对路径/家目录/父级目录访问、动态代码执行或反射加载时拒绝执行。
  - 拒绝执行时展示检测原因，并跳过代码运行和答案评审节点。

## 2026-05-16 - Phase 9: 算法练习开发语言与代码运行

- 测试命令：`rtk uv run pytest tests/test_cli.py -k "algorithm_practice or run_code"`；`rtk uv run pytest tests/test_cli.py tests/test_interview_nodes.py`
- reviewer 结论：未运行 reviewer；本次按用户提供的执行计划在主 agent 内完成
- 影响范围：`src/interview_agent/cli.py` / `CodeRunResult`、`_run_algorithm_practice()`、`_read_code_language()`、`_read_source_code()`、`_run_code()`、`_write_code_run_result()`、`_build_practice_review_answer()`；`tests/test_cli.py`
- 变更摘要：
  - 算法练习支持选择 Python、JavaScript、Go、Java、C、C++，并以空行提交完整程序。
  - CLI 在临时目录运行或编译用户程序，展示 `stdout`、`stderr`、退出码和超时状态。
  - 答案评审输入追加用户代码与代码运行结果，节点契约、配置、数据库结构和部署流程保持不变。

## 2026-05-16 - Phase 8: CLI 结果展示层拆分

- 测试命令：`rtk uv run pytest tests/test_cli.py -k "terminal_output_styles or non_terminal_output"`；`rtk uv run pytest tests/test_cli.py -k "natural_language_request or matched_node or missing_jd_input"`；`rtk uv run pytest tests/test_cli.py -k "mock"`；`rtk uv run pytest tests/test_e2e_cli_flow.py`；`rtk uv run pytest`
- reviewer 结论：未运行 reviewer；本次按用户提供的执行计划在主 agent 内完成
- 影响范围：`src/interview_agent/cli.py` / `_write_result()`、`_write_success_output()`、`_write_existing_list()`、`_write_existing_mapping()`、`_write_existing_text()`、`_format_title()`、`_format_status()`、`_format_key()`、`_format_index()`、`_format_error()`、`_write_line()`；`src/interview_agent/rendering.py`；`docs/EVOLUTION_PLAN.md`；`docs/architecture.md`；`docs/architecture.svg`
- 变更摘要：
  - 新增 `rendering.py` 承接节点结果展示、已有结果展示、列表/映射格式化、简历优化建议格式化和终端样式。
  - `cli.py` 保留兼容包装函数，继续向普通请求编排和模拟面试流程注入 `write_result` 与 `write_line`。
  - 架构文档和架构图同步标注结果展示层边界。

## 2026-05-14 - Phase 7: 模拟面试流程拆分

- 测试命令：`rtk uv run pytest tests/test_cli.py -k "prompt_styles or module_entry_catches_mock_interview_eof"`；`rtk uv run pytest tests/test_cli.py -k "mock"`；`rtk uv run pytest tests/test_cli.py`；`rtk uv run pytest tests/test_e2e_cli_flow.py`；`rtk uv run pytest`
- reviewer 结论：可继续；复审指出 `mock_interview.py` 未纳入 Git，已通过 `rtk git add` 纳入变更范围
- 影响范围：`src/interview_agent/cli.py` / 模拟面试分支、`_build_interview_prompt()`；`src/interview_agent/mock_interview.py` / 模拟面试流程；`tests/test_cli.py`；`docs/EVOLUTION_PLAN.md`；`docs/architecture.md`；`docs/architecture.svg`
- 变更摘要：
  - 新增 `mock_interview.py` 承接模拟面试请求识别、计划构建、题目数、追问轮数、题目生成重试、追问、参考答案和终端 prompt 样式。
  - `cli.py` 的模拟面试分支改为调用新模块，保留 `_build_interview_prompt()` 作为测试兼容入口。
  - 修复 `python -m interview_agent.cli` 启动时模拟面试 EOF 取消异常类型分裂，并增加模块启动回归测试。
  - 架构文档同步模拟面试流程迁出 CLI 的边界。

## 2026-05-14 - Phase 5: 节点输出质量增强

- 测试命令：`rtk uv run pytest tests/test_interview_nodes.py tests/test_llm.py tests/test_executor.py`；`rtk uv run pytest`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/nodes/interview.py` / 11 个运行时 handler、`_normalize_node_output()`、`_require_object_fields()`；`src/interview_agent/prompts.py` / `render_prompt()`；`tests/test_interview_nodes.py`；`tests/test_llm.py`
- 变更摘要：
  - 11 个运行时节点返回前统一归一化输出，只保留声明的 output key。
  - 缺少声明输出、非法输出类型、非法 JSON 统一记录为 failed node_run，且不写入 `session_state`。
  - `answer_score`、`weakness_train`、`resume_optimize` 增加最小子字段校验。
  - Prompt 模板补充顶层输出字段和复杂输出子字段要求。

## 2026-05-14 - Phase 4: 知识检索链路增强

- 测试命令：`rtk uv run pytest tests/test_interview_nodes.py -k "knowledge_search or rag or empty_results"`；`rtk uv run pytest tests/test_cli.py -k "retriever or knowledge_search"`；`rtk uv run pytest tests/test_kb_file_policy.py tests/test_kb_build.py`；`rtk uv run pytest tests/test_retrieval.py`；`rtk uv run pytest`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/agents.py` / `run_structured_node()`、`_preserve_rag_source_metadata()`；`src/interview_agent/nodes/interview.py` / `knowledge_search_handler()`；`src/interview_agent/kb/retrieval.py` / `SQLiteHybridRetriever.search()`、`hybrid_search()`；`src/interview_agent/cli.py` / 服务装配与知识检索结果展示；`src/interview_agent/kb/file_policy.py`
- 变更摘要：
  - `knowledge_search` 以 retriever chunk 为 `search_results` 基底，保留 `chunk_id`、`source_path`、`score`、`content`，LLM 只补充非来源字段。
  - RAG 输出合并时保护 source metadata，避免 LLM 覆盖真实 chunk 来源。
  - CLI 装配层将 `config.knowledge_base.top_k` 传给默认检索 limit，显式 `top_k` 输入仍优先。
  - 空检索结果保持 `search_results = []` 的节点契约，用户提示留在 CLI 展示层。
  - 离线构建边界新增公司流程资料排除，并补齐中文、英文、混合 query 的混合检索排序回归。

## 2026-05-14 - Phase 3: Session State 契约固化

- 测试命令：`uv run pytest tests/test_node_registry.py tests/test_executor.py tests/test_router_planner.py tests/test_interview_nodes.py`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/state_contracts.py`；`src/interview_agent/nodes/registry.py` / `DEFAULT_NODE_CONTRACTS`；`src/interview_agent/planner.py` / `build_execution_plan()`；`src/interview_agent/session.py` / `SessionStore.set_state()`、`write_session_state()`；`src/interview_agent/executor.py` / `NodeExecutor.execute_node()`
- 变更摘要：
  - 新增集中 state contract，统一定义节点输入、可选输入和输出 key。
  - Registry 与 Planner 复用同一契约来源，减少节点依赖规则重复维护。
  - Session state 写入增加轻量结构校验，失败输出记录为 failed node_run，不污染既有成功状态。
  - 保留 `knowledge_search` 空检索结果的合法成功态：`search_results = []`。

## 2026-05-14 - Phase 2A: 普通请求编排入口拆分

- 测试命令：`rtk uv run pytest tests/test_cli.py -k "natural_language_request or missing_jd_input"`；`rtk uv run pytest tests/test_cli.py -k "matched_node or missing_jd_input"`；`rtk uv run pytest tests/test_cli.py`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/cli.py` / `main()`；`src/interview_agent/orchestrator.py` / `run_user_request()`；`tests/test_cli.py`
- 变更摘要：
  - 新增 `run_user_request()` 承接普通请求编排路径。
  - `cli.main()` 保留启动、输入循环和模拟面试分支，普通请求委派到编排模块。
  - 保持 CLI 参数、节点 handler 接口、SQLite schema、配置和用户可见输出不变。

## 2026-05-14 - Phase 1: 运行时契约硬化

- 测试命令：`rtk uv run pytest tests/test_router_planner.py tests/test_cli.py`；`rtk uv run pytest`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/router.py` / `RouteResult`、`route_conversation()`；`src/interview_agent/cli.py` / `_select_node_for_route()`；`src/interview_agent/planner.py` / `ExecutionPlan`；`docs/architecture.md`；`docs/architecture.svg`
- 变更摘要：
  - `RouteResult` 新增 `needs_user_choice`，Router 统一输出是否需要用户选择。
  - CLI 改为读取 Router 显式契约，不再根据来源或候选数量自行推断。
  - `ExecutionPlan.requires_confirmation` 保持兼容字段并固定为 `False`。
  - 架构文档同步 Router/Planner 职责边界。

## 2026-05-14 - Phase 0: 当前主线收口

- 测试命令：`rtk uv run pytest tests/test_router_planner.py tests/test_cli.py`；`rtk uv run pytest`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/cli.py` / `_select_node_for_route()`；`tests/test_cli.py`；`docs/EVOLUTION_PLAN.md`
- 变更摘要：
  - 取消多节点确认约束收口完成，路由明确时继续直接执行。
  - 修复规则路由多候选时未询问处理方向的问题。
  - 补充规则路由多候选回归测试，确认不展示内部节点名。
