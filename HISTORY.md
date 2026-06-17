# 功能变更历史

## 2026-06-17

### JOB-017 猎聘确认后投递适配器

- 功能名称：猎聘确认后投递适配器
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`
- 测试结果：`166 passed`；全量 `376 passed`
- reviewer 结论：`可继续`，无阻断问题。
- 影响范围：`src/interview_agent/job_platform_adapters.py`、`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 变更摘要：新增 `LiepinSubmitJobPlatformAdapter` 确认后投递适配器，复用猎聘只读适配器并添加 `submit_html_by_job_id` 投递夹具；新增 `GuiRuntime.submit_liepin_applications()` 和 `get_liepin_submit_results()`；新增 `JOB_LIEPIN_SUBMIT_RESULTS_KEY` session state；测试覆盖未确认批次拦截、成功投递、失败投递、重复投递、验证码、风控、强制弹窗、按钮失效、混合场景、session state 存储和空结果查询。不执行真实浏览器访问或数据库 schema 变更。

### JOB-016 拉勾确认后投递适配器

- 功能名称：拉勾确认后投递适配器
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`
- 测试结果：`152 passed`；全量 `362 passed`
- reviewer 结论：`可继续`，无阻断问题。
- 影响范围：`src/interview_agent/job_platform_adapters.py`、`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 变更摘要：新增 `LagouSubmitJobPlatformAdapter` 确认后投递适配器，复用拉勾只读适配器并添加 `submit_html_by_job_id` 投递夹具；新增 `GuiRuntime.submit_lagou_applications()` 和 `get_lagou_submit_results()`；新增 `JOB_LAGOU_SUBMIT_RESULTS_KEY` session state；测试覆盖未确认批次拦截、成功投递、失败投递、重复投递、验证码、风控、强制弹窗、按钮失效、混合场景、session state 存储和空结果查询。不执行真实浏览器访问或数据库 schema 变更。

### JOB-015 BOSS 直聘确认后投递适配器

- 功能名称：BOSS 直聘确认后投递适配器
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`
- 测试结果：`138 passed`；全量 `348 passed`
- reviewer 结论：`可继续`，无阻断问题。
- 影响范围：`src/interview_agent/job_platform_adapters.py`、`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 变更摘要：新增 `BossSubmitJobPlatformAdapter` 确认后投递适配器，复用 BOSS 只读适配器并添加 `submit_html_by_job_id` 投递夹具；新增 `GuiRuntime.submit_boss_applications()` 和 `get_boss_submit_results()`；新增 `JOB_BOSS_SUBMIT_RESULTS_KEY` session state；测试覆盖未确认批次拦截、成功投递、失败投递、重复投递、验证码、风控、强制弹窗、按钮失效、混合场景、session state 存储和空结果查询。不执行真实浏览器访问或数据库 schema 变更。

## 2026-06-16

### JOB-014 确认批次重校验

- 功能名称：确认批次重校验
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`
- 测试结果：`124 passed in 0.95s`；全量 `330 passed`
- reviewer 结论：`可继续`，无阻断问题。
- 影响范围：`src/interview_agent/gui_runtime.py`、`src/interview_agent/job_platform_adapters.py`、`src/interview_agent/storage.py`、`tests/test_gui_runtime.py`
- 变更摘要：新增确认批次重校验功能，投递提交前重新校验用户确认的岗位。对每个 `approved` 岗位依次执行五项检查：岗位下线（`read_job_detail` 异常或返回 None → `job_offline`）、已投递（`is_already_applied` → `duplicate`）、按钮不可用（`is_button_available` → `button_unavailable`）、JD 关键字段变化（薪资/地点/学历/经验/级别/JD 文本 → `jd_changed`）、通过检查保持 `approved`。`JobPlatformAdapter` 协议新增 `is_button_available()` 方法，所有适配器均已实现。存储层新增 `get_job_application_by_id()` 查询方法。重校验结果保存到 session state，支持后续查询。

### JOB-013 GUI 求职模块前端测试与 ESM 导入修复

- 功能名称：GUI 求职模块前端测试与 ESM 导入修复
- 测试命令：`rtk npm --prefix gui test`
- 测试结果：前端测试通过
- reviewer 结论：`可继续`
- 影响范围：`gui/src/modules/job/ConfirmModal.tsx`、`gui/src/modules/job/JobModule.tsx`、`gui/tests/desktopSnapshot.test.mjs`、`gui/tsconfig.desktop-test.json`
- 变更摘要：修复 GUI 求职模块 ESM 导入问题，补充桌面快照测试覆盖确认弹窗和求职模块交互场景。

### JOB-012 岗位评估与建议

- 功能名称：岗位评估与建议
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_interview_nodes.py tests/test_gui_runtime.py`
- 测试结果：`115 passed`；全量 `322 passed`
- reviewer 结论：`可继续`
- 影响范围：`src/interview_agent/gui_runtime.py`、`src/interview_agent/nodes/interview.py`、`src/interview_agent/nodes/registry.py`、`src/interview_agent/prompts.py`、`src/interview_agent/state_contracts.py`、`tests/test_gui_runtime.py`、`tests/test_llm.py`、`tests/test_node_registry.py`
- 变更摘要：新增岗位评估与建议功能，支持对已采集岗位进行匹配度评估、优劣势分析和发展建议生成；注册 `job_evaluation` 节点及对应 prompt 模板；GUI Runtime 提供 `evaluate_jobs()` facade 并保存评估结果到 session state。

## 2026-06-11

### JOB-008 BOSS 直聘只读采集适配器

- 功能名称：BOSS 直聘只读采集适配器
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`
- 测试结果：`76 passed in 0.72s`
- reviewer 结论：复审 `可继续`，无阻断问题。
- 影响范围：`src/interview_agent/job_platform_adapters.py`、`src/interview_agent/job_collection.py`、`tests/test_gui_runtime.py`、`tests/fixtures/job_platform/boss_*.html`
- 变更摘要：新增 BOSS 直聘只读采集适配器和受控 HTML 夹具，支持列表搜索、列表采集、详情完整 JD 读取、已投递识别、缺失字段低置信度标记，以及登录失效、验证码、限流和页面结构变化在 search/detail/state 阶段的错误传播；采集编排器可把详情阶段平台错误归类到既有 `manual_takeover`、`backoff`、`failed` 状态；BOSS 适配器保持只读，确认投递入口固定返回 `skipped`，不产生真实投递动作。

## 2026-06-10

### JOB-007 平台风控与人工接管

- 功能名称：平台风控与人工接管
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py`
- 测试结果：`54 passed in 0.56s`
- reviewer 结论：`可继续`，无阻断问题。
- 影响范围：`src/interview_agent/job_collection.py`、`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 变更摘要：新增求职采集风控状态处理，验证码、账号风控和强制弹窗会进入 `manual_takeover` 并暂停对应平台，限流会进入 `backoff` 并记录退避提示；恢复入口可从普通失败、人工接管和退避状态恢复单个平台，保留其他平台已采集结果；GUI 采集进度 view model 暴露人工接管和退避计数，并继续走敏感信息扫描，避免 cookie、token、session 等浏览器会话信息进入展示状态。

### JOB-006 多平台采集编排与进度状态

- 功能名称：多平台采集编排与进度状态
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`
- 测试结果：`65 passed in 0.59s`
- reviewer 结论：第四次复审 `Can proceed: Yes`，无阻断问题。
- 影响范围：`src/interview_agent/job_collection.py`、`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 变更摘要：新增多平台求职采集编排器和 GUI Runtime 采集 facade，支持平台级开始、翻页、详情采集、完成、失败和重试状态；单个平台失败或抛异常时保留其他平台结果；失败平台可通过 runtime 重试；运行中和重试中的采集进度写入 SQLite 并同步为 GUI view model；未接入真实浏览器、网络、投递动作、配置或部署流程。

### JOB-004 Chrome 会话隔离与敏感信息脱敏边界

- 功能名称：Chrome 会话隔离与敏感信息脱敏边界
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_interview_nodes.py tests/test_storage.py`
- 测试结果：`71 passed in 0.69s`
- reviewer 结论：复审 `可继续`，无阻断问题。
- 影响范围：`src/interview_agent/sensitive.py`、`src/interview_agent/job_platform_adapters.py`、`src/interview_agent/agents.py`、`src/interview_agent/executor.py`、`src/interview_agent/session.py`、`src/interview_agent/storage.py`、`tests/test_gui_runtime.py`、`tests/test_interview_nodes.py`、`tests/test_storage.py`
- 变更摘要：新增统一敏感信息扫描与 URL 摘要边界，覆盖平台适配器结果、提交错误、LLM prompt、`session_state`、`node_runs` 和求职存储入口；adapter 错误只保留错误类型、平台、阶段和非敏感 URL 摘要；节点 handler 抛出敏感异常时写入固定脱敏失败文案；补充测试证明真实敏感内容会被拒绝或脱敏，正常 JD、简历画像和结构化岗位字段中的 `token`、`auth`、`mobile`、普通 `session_id` 业务词不被误杀。

### JOB-003 平台适配器接口

- 功能名称：平台适配器接口
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`
- 测试结果：`49 passed in 0.49s`
- reviewer 结论：`可继续`，无阻断问题。
- 影响范围：`src/interview_agent/job_platform_adapters.py`、`tests/test_gui_runtime.py`
- 变更摘要：新增 BOSS 直聘、拉勾、猎聘共享的平台适配器协议、浏览器自动化边界、标准岗位对象、搜索请求、平台执行结果、确认投递请求、投递结果和统一错误类型；新增 fake adapter 契约测试，覆盖成功搜索、登录失效、验证码、限流、页面结构变化、投递失败和返回结果敏感凭据拦截。

### JOB-002 求职画像生成

- 功能名称：求职画像生成
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py`
- 测试结果：`32 passed in 0.43s`
- reviewer 结论：复审 `可继续`，无阻断问题。
- 影响范围：`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 变更摘要：新增 GUI Runtime 求职画像 facade，从已有 `resume_profile` 生成求职画像、默认搜索词、硬过滤条件、排序偏好和待确认字段；支持用户覆盖城市、远程、薪资、职级、经验、学历、行业、公司规模、融资阶段、技术栈、福利、发布时间、黑白名单，并把画像状态保存到 `session_state`。

### JOB-001 求职数据模型与存储设计

- 功能名称：求职数据模型与存储设计
- 测试命令：`rtk uv run pytest -p no:cacheprovider tests/test_storage.py`
- 测试结果：`14 passed in 0.12s`
- reviewer 结论：第三次复审 `可继续`，无阻断问题。
- 影响范围：`src/interview_agent/schema.sql`、`src/interview_agent/storage.py`、`tests/test_storage.py`
- 变更摘要：新增求职标准岗位、筛选条件、评估报告、确认批次、投递记录、采集任务和平台进度的 SQLite 持久化结构与存储 API；支持重复岗位识别、批次结果查询、平台进度查询、清空求职数据，并拦截明显敏感内容落库。
