# 求职投递功能开发任务

## 结论

后续开发必须按本文任务顺序推进，并以 `docs/TODO.md` 中的求职投递专项条目作为正式任务入口。每个任务必须记录状态、验证命令、验证结果和观测证据；架构文档同步不交给 implementer，在任务合并后由主 agent 完成。

## 状态规则

任务状态只允许使用：

- `pending`：未开始。
- `in_progress`：正在执行。
- `blocked`：被外部依赖或待确认事项阻塞。
- `done`：已完成并通过验证。

每个任务更新时必须填写：

- `状态`
- `负责人`
- `开始时间`
- `完成时间`
- `验证命令`
- `验证结果`
- `观测证据`
- `副作用`
- `影响调用方`

## 开发总约束

- 开发前必须先阅读 `docs/job-application-feature-design.md`。
- 开发流程必须遵循 `.codex/rules/development-workflow.md`。
- 修改代码前必须阅读被修改函数及其调用方。
- 每个任务一个独立 worktree 和任务分支。
- 每个任务只允许修改与任务目标直接相关的文件。
- 不得保存平台账号、密码、cookie、token。
- 不得把浏览器会话信息传入 LLM。
- 投递动作必须由用户批量确认后执行。
- `docs/architecture.md` 和 `docs/architecture.svg` 只由主 agent 在任务分支合并后更新。

## 任务清单

### JOB-001 求职数据模型与存储设计

- 状态：`done`
- 负责人：implementer / reviewer
- 开始时间：2026-06-10
- 完成时间：2026-06-10
- 目标：定义标准岗位、筛选条件、评估报告、确认批次、投递记录和采集进度的数据结构与持久化方式。
- 影响范围：SQLite schema、存储层、类型归一化。
- 输入：`docs/job-application-feature-design.md` 中的数据模型。
- 输出：可保存、查询、更新、清空的求职数据。
- 实现要点：
  - 设计岗位、评估、确认批次、投递记录、采集任务和平台进度的持久化结构。
  - 支持重复岗位识别。
  - 支持按确认批次追踪投递状态。
  - 支持清空本地求职数据。
- verify：
  - 岗位保存和查询成功。
  - 重复岗位识别成功。
  - 投递状态可从 `pending_review` 更新到 `submitted`、`failed`、`skipped`、`duplicate`。
  - 采集进度可记录平台、分页、失败原因、重试次数和人工接管状态。
  - 清空求职数据不影响已有面试 session state。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_storage.py
```

- 验证结果：`14 passed in 0.12s`；reviewer 第三次复审结论：`可继续`，无阻断问题。
- 观测证据：
  - 新增/修改测试：`test_job_application_storage_uses_platform_job_id_contract_and_duplicate_detection`、`test_job_application_filters_and_evaluation_are_queryable_after_restart`、`test_confirmation_batch_keeps_batch_metadata_and_job_results_separate`、`test_collection_progress_is_queryable_and_clear_job_application_data_preserve_sessions`、`test_job_application_storage_rejects_sensitive_content_across_all_text_inputs`。
  - 任务提交：`d6a866c`、`91cefc9`、`e8dd20c`。
- 副作用：新增求职相关 SQLite 表；求职存储入口会拒绝明显敏感内容落库。
- 影响调用方：求职模块、平台适配器、采集编排器、投递执行器可读取标准岗位、筛选条件、评估报告、确认批次、投递结果和平台进度。

### JOB-002 求职画像生成

- 状态：`done`
- 负责人：implementer / reviewer
- 开始时间：2026-06-10
- 完成时间：2026-06-10
- 目标：从现有 `resume_profile` 生成岗位搜索画像和默认筛选条件。
- 影响范围：运行时 facade、求职画像服务、GUI 数据模型。
- 输入：`resume_profile`。
- 输出：求职画像、默认搜索词、硬过滤条件、排序偏好。
- 实现要点：
  - 复用现有简历解析结果。
  - 缺失字段进入待确认状态。
  - 支持用户覆盖城市、远程、薪资、职级、经验、学历、行业、公司规模、融资阶段、技术栈、福利、发布时间、黑白名单。
- verify：
  - 完整 `resume_profile` 可生成完整画像。
  - 缺失技能、年限、城市偏好时输出待确认字段。
  - 用户覆盖条件后保存结果。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py
```

- 验证结果：`32 passed in 0.43s`；reviewer 复审结论：`可继续`，无阻断问题。
- 观测证据：
  - 新增/修改测试：`test_runtime_prepares_complete_job_search_profile_from_resume_profile`、`test_runtime_marks_missing_job_search_profile_fields_for_confirmation`、`test_runtime_saves_job_search_profile_with_user_overrides`、`test_runtime_keeps_remote_policy_pending_when_resume_profile_has_no_remote_preference`、`test_runtime_saves_false_remote_policy_override_without_falling_back`、`test_runtime_saves_empty_overrides_as_cleared_job_search_conditions`、`test_runtime_job_search_profile_state_contains_all_job_002_override_dimensions`。
  - 任务提交：`4c75507`、`143f8a4`。
- 副作用：新增求职画像相关 session state：`job_search_profile`、`job_search_filters`。
- 影响调用方：GUI 求职模块和后续岗位搜索任务可读取完整求职画像、默认搜索词、硬过滤条件、排序偏好和待确认字段；现有面试准备、模拟面试、算法练习调用方不变。

### JOB-003 平台适配器接口

- 状态：`done`
- 负责人：implementer / reviewer
- 开始时间：2026-06-10
- 完成时间：2026-06-10
- 目标：定义 BOSS 直聘、拉勾、猎聘共享的平台适配器协议。
- 影响范围：浏览器自动化服务边界、平台适配器接口、错误类型。
- 输入：求职画像、筛选条件、确认投递请求。
- 输出：标准岗位对象、平台执行结果、投递结果。
- 实现要点：
  - 定义只读搜索、列表采集、详情读取、已投递识别接口。
  - 定义确认后投递提交接口。
  - 定义登录失效、页面结构变化、字段缺失、按钮不可用、重复投递、验证码、限流、账号风控、强制弹窗等错误类型。
  - 使用 fake adapter 建立测试边界。
- verify：
  - fake adapter 可模拟成功搜索。
  - fake adapter 可模拟登录失效、验证码、限流和页面结构变化。
  - fake adapter 可模拟投递失败。
  - 适配器返回结果不包含敏感凭据。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py
```

- 验证结果：`49 passed in 0.49s`；reviewer 结论：`可继续`，无阻断问题。
- 观测证据：
  - 新增/修改测试：`test_job_platform_fake_adapter_simulates_successful_readonly_search`、`test_job_platform_fake_adapter_simulates_required_platform_errors`、`test_job_platform_fake_adapter_simulates_submission_failure_without_sensitive_payload`。
  - 红灯证据：新增测试先失败，错误为 `ModuleNotFoundError: No module named 'interview_agent.job_platform_adapters'`，结果 `3 failed, 46 passed`。
  - 任务提交：`7c53c89`。
- 副作用：新增浏览器自动化抽象边界和 fake adapter 测试边界；未修改数据库结构、配置、架构运行路径或平台真实投递行为。
- 影响调用方：三个平台适配器、采集编排器、投递执行器可依赖共享协议、错误类型和 fake adapter；现有 GUI runtime、storage、面试准备、模拟面试、算法练习调用方不变。

### JOB-004 Chrome 会话隔离与敏感信息脱敏边界

- 状态：`done`
- 负责人：implementer / reviewer
- 开始时间：2026-06-10
- 完成时间：2026-06-10
- 目标：确保 Chrome 登录态只存在于用户浏览器进程内，敏感信息不入库、不进日志、不进 LLM。
- 影响范围：浏览器自动化边界、日志、SQLite 写入、session state、prompt 构造。
- 输入：平台适配器接口、浏览器页面状态。
- 输出：统一敏感信息禁止序列化和脱敏检查能力。
- 实现要点：
  - 明确适配器禁止读取、保存、打印 cookie、token、session id。
  - 建立统一敏感字段扫描或断言工具。
  - 日志只记录错误类型、平台、阶段和非敏感 URL 摘要。
  - LLM prompt 只允许包含简历画像、岗位结构化字段和 JD 文本。
- verify：
  - 适配器结果、日志、SQLite、session state、node_runs、LLM prompt 扫描无 cookie、token、session 标识。
  - 错误展示不包含账号凭据、手机号、验证码或浏览器会话信息。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_interview_nodes.py tests/test_storage.py
```

- 验证结果：`71 passed in 0.69s`；reviewer 复审结论：`可继续`，无阻断问题。
- 观测证据：
  - 新增统一敏感扫描工具 `src/interview_agent/sensitive.py`，覆盖敏感字段名、凭据赋值、浏览器会话赋值、邮箱、手机号、验证码和 URL 摘要。
  - 新增/修改测试：`test_job_platform_adapter_error_redacts_sensitive_message_and_url_summary`、`test_job_platform_adapter_error_summary_does_not_expose_field_name`、`test_job_platform_adapter_sanitizes_sensitive_submit_result_without_raising`、`test_node_executor_rejects_sensitive_inputs_before_node_run_is_persisted`、`test_llm_prompt_rejects_contact_and_browser_session_payload`、`test_llm_prompt_allows_business_terms_that_are_not_credentials`、`test_node_executor_persists_safe_error_summary_when_handler_raises_sensitive_exception`、`test_session_state_rejects_browser_session_and_contact_payload`。
  - 红灯证据：首轮新增 4 个测试先失败；reviewer 首轮发现普通业务词误杀、提交错误未脱敏、`field_name` 外泄和节点敏感异常二次抛错后，补充 4 个失败测试再修复。
  - 任务提交：`82cb3c7`、`16eb725`。
- 副作用：新增全链路安全约束；真实敏感字段、凭据赋值、浏览器会话标识、邮箱、手机号和验证码会在 adapter、LLM prompt、session_state、node_runs 和求职存储入口被拒绝或脱敏。
- 影响调用方：所有平台适配器、评估服务、投递执行器和节点执行链路；正常 JD、简历画像和结构化岗位字段中的 `token`、`auth`、`mobile`、普通 `session_id` 业务词可继续通过。

### JOB-005 适配器夹具与契约测试基建

- 状态：`done`
- 目标：建立受控 HTML/页面夹具和适配器契约测试，避免平台任务只依赖宽泛运行时测试。
- 影响范围：测试夹具、适配器契约测试、fake browser/fake adapter。
- 输入：平台适配器接口。
- 输出：可回放的列表解析、详情解析、错误分类和投递约束测试。
- 实现要点：
  - 为列表页、详情页、登录失效、验证码、按钮不可用、已投递状态建立夹具。
  - 契约测试覆盖标准岗位字段和错误类型。
  - 投递接口测试必须证明未确认批次不能提交。
- verify：
  - 夹具可稳定解析列表和详情字段。
  - 错误分类稳定。
  - 确认后投递约束可测试。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py
```

- 观测证据：记录夹具清单、契约测试名和测试输出摘要。
- 副作用：新增平台自动化测试基建。
- 影响调用方：JOB-006 到 JOB-011 的平台实现任务。

#### JOB-005 完成记录

- 状态：done
- 负责人：implementer / reviewer / main agent
- 开始时间：2026-06-10
- 完成时间：2026-06-10
- 修改文件：`src/interview_agent/job_platform_adapters.py`、`tests/test_gui_runtime.py`、`tests/fixtures/job_platform/*.html`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "job_platform_contract"`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py`；`rtk git diff --check main...HEAD`
- 验证结果：`job_platform_contract` 6 passed；`tests/test_gui_runtime.py` 44 passed；diff check 无输出
- 观测证据：夹具清单包含列表页、详情页、登录失效、验证码、按钮不可用、已投递；契约测试覆盖完整 `StandardJob` 字段、嵌套字段、多岗位卡片、必填字段缺失、4 类错误分类和未确认投递拦截；reviewer 第四次复审 `可继续`
- 副作用：新增平台自动化测试基建和 HTML 夹具；未接入真实浏览器、网络、数据库结构、配置或部署流程
- 影响调用方：JOB-006 到 JOB-011 可复用夹具解析、错误分类和投递约束契约
- 后续风险：真实平台适配器仍需在 JOB-006 到 JOB-011 中分别接入平台页面结构和人工接管流程

### JOB-006 多平台采集编排与进度状态

- 状态：`done`
- 目标：实现多平台采集调度和平台级可观测进度状态。
- 影响范围：采集编排器、运行时 facade、存储层进度记录、GUI view model。
- 输入：求职画像、筛选条件、平台适配器接口。
- 输出：平台级开始、翻页、详情采集、完成、失败、重试、人工接管状态。
- 实现要点：
  - 每个平台采集任务独立记录状态。
  - 单个平台失败不清空其他平台结果。
  - 支持失败平台重试。
  - 为 GUI 采集进度页提供稳定状态来源。
- verify：
  - 能观测平台级开始、翻页、完成、失败、重试状态。
  - 单个平台失败时其他平台结果保留。
  - GUI view model 可读取采集进度。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py
```

- 观测证据：记录平台进度状态样例和测试输出摘要。
- 副作用：新增采集任务状态。
- 影响调用方：GUI 采集进度页、平台适配器。

#### JOB-006 完成记录

- 状态：done
- 负责人：implementer / reviewer / main agent
- 开始时间：2026-06-10
- 完成时间：2026-06-10
- 修改文件：`src/interview_agent/job_collection.py`、`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "job_collection_orchestrator or runtime_collects_jobs or retry or running_job_collection"`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`；`rtk git diff --check main...HEAD`
- 验证结果：定向采集编排测试 5 passed；`tests/test_gui_runtime.py tests/test_storage.py` 65 passed；diff check 无输出
- 观测证据：新增 `JobCollectionOrchestrator`，覆盖平台级 `started`、`page_collected`、`detail_collected`、`completed`、`failed`、`retrying` 状态；测试证明单平台失败不影响其他平台结果，失败平台可通过 GUI runtime 重试，运行中 `started` 与重试中 `retrying` 先写入 SQLite 并可通过 `get_collection_progress()` 读取；reviewer 第四次复审 `Can proceed: Yes`
- 副作用：新增 GUI session state `job_collection_progress` 和运行期采集编排器缓存；新增 SQLite 采集进度写入链路；未接入真实浏览器、网络、投递动作、数据库 schema、配置或部署流程
- 影响调用方：GUI 采集进度页可读取稳定进度 view model；后续 JOB-007 到 JOB-011 可复用多平台编排、失败隔离、失败平台重试和持久化进度状态
- 后续风险：真实平台适配器仍需在 JOB-008 到 JOB-010 中接入平台页面结构；验证码、限流、账号风控和人工接管策略仍由 JOB-007 处理

### JOB-007 平台风控与人工接管

- 状态：`done`
- 负责人：implementer / reviewer / main agent
- 开始时间：2026-06-10
- 完成时间：2026-06-10
- 目标：处理验证码、频率限制、账号风控、强制弹窗等平台自动化高风险场景。
- 影响范围：采集编排器、平台适配器错误处理、GUI 状态提示。
- 输入：平台适配器错误类型、采集进度状态。
- 输出：暂停、退避、人工接管、恢复继续和风险提示状态。
- 实现要点：
  - 验证码、账号异常、强制弹窗进入人工接管状态。
  - 频率限制进入平台级退避状态。
  - 用户处理后可恢复对应平台任务。
  - 风控状态纳入采集进度和投递结果。
- verify：
  - 验证码时暂停平台任务。
  - 限流时记录退避状态。
  - 人工恢复后可继续。
  - 风控状态不包含敏感会话信息。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py
```

- 观测证据：记录风控状态样例、人工接管状态样例和测试输出摘要。
- 副作用：平台任务可能暂停等待用户处理。
- 影响调用方：平台采集、平台投递、GUI 进度页。

#### JOB-007 完成记录

- 状态：done
- 负责人：implementer / reviewer / main agent
- 开始时间：2026-06-10
- 完成时间：2026-06-10
- 修改文件：`src/interview_agent/job_collection.py`、`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py`；`rtk git diff --check main...HEAD`
- 验证结果：`tests/test_gui_runtime.py` 54 passed；diff check 无输出；reviewer 结论 `可继续`
- 观测证据：新增验证码、账号风控、强制弹窗进入 `manual_takeover` 的进度状态；新增限流进入 `backoff` 的退避状态；GUI view model summary 新增 `manual_takeover_platform_count` 和 `backoff_platform_count`；测试覆盖人工接管恢复只恢复对应平台并保留其他平台结果，风控 view model 不包含 cookie、token、session 等敏感会话信息。
- 副作用：平台任务遇到验证码、账号风控、强制弹窗或限流时会暂停，等待用户处理或退避恢复。
- 影响调用方：平台采集、平台投递、GUI 进度页可读取人工接管、退避和恢复后的平台状态；普通失败平台重试行为保持兼容。
- 后续风险：真实平台适配器仍需在 JOB-008 到 JOB-010 中接入各平台页面结构，投递阶段风控暂停由 JOB-015 到 JOB-017 继续覆盖。

### JOB-008 BOSS 直聘只读采集适配器

- 状态：`done`
- 负责人：implementer / reviewer / main agent
- 开始时间：2026-06-11
- 完成时间：2026-06-11
- 目标：实现 BOSS 直聘搜索、列表采集、详情解析和已投递识别，不执行投递。
- 影响范围：BOSS 只读适配器、测试夹具。
- 输入：求职画像、筛选条件。
- 输出：标准岗位对象、只读采集结果、错误类型。
- 实现要点：
  - 采集列表页岗位基础字段。
  - 进入详情页读取完整 JD。
  - 识别已投递、登录失效、验证码、限流、页面结构变化。
  - 不点击投递按钮。
- verify：
  - BOSS 夹具可解析岗位字段。
  - 字段缺失被标记为低置信度。
  - 已投递状态可识别。
  - 登录失效和验证码进入对应错误类型。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py
```

- 观测证据：记录 BOSS 夹具、解析输出样例和测试输出摘要。
- 副作用：只读浏览器访问，不产生投递动作。
- 影响调用方：采集编排器、筛选服务。

#### JOB-008 完成记录

- 状态：done
- 负责人：implementer / reviewer / main agent
- 开始时间：2026-06-11
- 完成时间：2026-06-11
- 修改文件：`src/interview_agent/job_platform_adapters.py`、`src/interview_agent/job_collection.py`、`tests/test_gui_runtime.py`、`tests/fixtures/job_platform/boss_*.html`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "boss"`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "boss or job_platform_contract"`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`；`rtk git diff --check main...HEAD`
- 验证结果：BOSS 定向 7 passed；BOSS 与契约测试 13 passed；`tests/test_gui_runtime.py` 61 passed；`tests/test_gui_runtime.py tests/test_storage.py` 76 passed；diff check 无输出；reviewer 复审 `可继续`
- 观测证据：新增 BOSS 列表、详情、缺失字段、已投递、登录失效、验证码、限流和页面结构变化夹具；测试覆盖列表字段解析、详情完整 JD、缺失字段低置信度、search/detail/state 错误传播、已投递识别、只读不投递和编排器详情阶段限流归类为 `backoff`
- 副作用：新增 BOSS 只读夹具适配器和平台错误传播；详情或状态阶段的平台错误不再降级为泛化异常；不执行真实浏览器访问或投递动作
- 影响调用方：采集编排器可通过 BOSS 只读适配器读取标准岗位和完整 JD，并复用既有 `manual_takeover`、`backoff`、`failed` 状态展示平台异常；后续筛选服务可消费标准岗位对象
- 后续风险：真实 BOSS 页面选择器、分页、搜索参数映射和人工接管恢复仍需在真实浏览器接入时验证

### JOB-009 拉勾只读采集适配器

- 状态：`done`
- 目标：实现拉勾搜索、列表采集、详情解析和已投递识别，不执行投递。
- 影响范围：拉勾只读适配器、测试夹具。
- 输入：求职画像、筛选条件。
- 输出：标准岗位对象、只读采集结果、错误类型。
- 实现要点：
  - 处理拉勾页面字段差异。
  - 采集岗位详情和公司信息。
  - 识别已投递、登录失效、验证码、限流、页面结构变化。
  - 不点击投递按钮。
- verify：
  - 拉勾夹具可解析岗位字段。
  - 字段缺失被标记为低置信度。
  - 已投递状态可识别。
  - 登录失效和验证码进入对应错误类型。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py
```

- 观测证据：记录拉勾夹具、解析输出样例和测试输出摘要。
- 副作用：只读浏览器访问，不产生投递动作。
- 影响调用方：采集编排器、筛选服务。

#### JOB-009 完成记录

- 状态：done
- 负责人：implementer / main agent
- 开始时间：2026-06-16
- 完成时间：2026-06-16
- 修改文件：`src/interview_agent/job_platform_adapters.py`、`tests/test_gui_runtime.py`、`tests/fixtures/job_platform/lagou_*.html`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "lagou"`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`；`rtk uv run pytest -p no:cacheprovider`
- 验证结果：拉勾定向 7 passed；`tests/test_gui_runtime.py tests/test_storage.py` 83 passed；全量 293 passed
- 观测证据：新增拉勾列表、详情、缺失字段、已投递、登录失效、验证码、限流和页面结构变化夹具；测试覆盖列表字段解析、详情完整 JD、缺失字段低置信度、search/detail/state 错误传播、已投递识别、只读不投递和编排器详情阶段限流归类为 `backoff`
- 副作用：新增拉勾只读夹具适配器和平台错误传播；不执行真实浏览器访问或投递动作
- 影响调用方：采集编排器可通过拉勾只读适配器读取标准岗位和完整 JD，并复用既有 `manual_takeover`、`backoff`、`failed` 状态展示平台异常；后续筛选服务可消费标准岗位对象
- 后续风险：真实拉勾页面选择器、分页、搜索参数映射和人工接管恢复仍需在真实浏览器接入时验证

### JOB-010 猎聘只读采集适配器

- 状态：`done`
- 目标：实现猎聘搜索、列表采集、详情解析和已投递识别，不执行投递。
- 影响范围：猎聘只读适配器、测试夹具。
- 输入：求职画像、筛选条件。
- 输出：标准岗位对象、只读采集结果、错误类型。
- 实现要点：
  - 处理猎聘页面字段差异。
  - 采集岗位详情和公司信息。
  - 识别已投递、登录失效、验证码、限流、页面结构变化。
  - 不点击投递按钮。
- verify：
  - 猎聘夹具可解析岗位字段。
  - 字段缺失被标记为低置信度。
  - 已投递状态可识别。
  - 登录失效和验证码进入对应错误类型。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py
```

- 观测证据：记录猎聘夹具、解析输出样例和测试输出摘要。
- 副作用：只读浏览器访问，不产生投递动作。
- 影响调用方：采集编排器、筛选服务。

#### JOB-010 完成记录

- 状态：done
- 负责人：implementer / main agent
- 开始时间：2026-06-16
- 完成时间：2026-06-16
- 修改文件：`src/interview_agent/job_platform_adapters.py`、`tests/test_gui_runtime.py`、`tests/fixtures/job_platform/liepin_*.html`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "liepin"`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`；`rtk uv run pytest -p no:cacheprovider`
- 验证结果：猎聘定向 7 passed；`tests/test_gui_runtime.py tests/test_storage.py` 90 passed；全量 300 passed
- 观测证据：新增猎聘列表、详情、缺失字段、已投递、登录失效、验证码、限流和页面结构变化夹具；测试覆盖列表字段解析、详情完整 JD、缺失字段低置信度、search/detail/state 错误传播、已投递识别、只读不投递和编排器详情阶段限流归类为 `backoff`
- 副作用：新增猎聘只读夹具适配器和平台错误传播；不执行真实浏览器访问或投递动作
- 影响调用方：采集编排器可通过猎聘只读适配器读取标准岗位和完整 JD，并复用既有 `manual_takeover`、`backoff`、`failed` 状态展示平台异常；后续筛选服务可消费标准岗位对象
- 后续风险：真实猎聘页面选择器、分页、搜索参数映射和人工接管恢复仍需在真实浏览器接入时验证

### JOB-011 岗位筛选与排序

- 状态：`done`
- 目标：实现全条件筛选，区分硬过滤、排序偏好和低置信度字段。
- 影响范围：筛选服务、评分前候选清单。
- 输入：标准岗位对象、筛选条件对象、历史投递记录。
- 输出：候选岗位清单、排除原因、低置信度标记、排序结果。
- 实现要点：
  - 硬过滤排除明确不符合的岗位。
  - 排序偏好影响推荐顺序。
  - 缺失字段进入低置信度，不直接丢弃。
  - 已投递和重复岗位不进入投递队列。
- verify：
  - 城市、远程、薪资、学历、经验、黑名单、已投递过滤有效。
  - 字段缺失岗位被保留并标记低置信度。
  - 排序偏好改变岗位顺序。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py
```

- 观测证据：记录过滤前后岗位数量和测试输出摘要。
- 副作用：新增筛选结果状态。
- 影响调用方：岗位评估服务、GUI 岗位清单。

#### JOB-011 完成记录

- 状态：done
- 负责人：implementer / main agent
- 开始时间：2026-06-16
- 完成时间：2026-06-16
- 修改文件：`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "filter_jobs"`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`；`rtk uv run pytest -p no:cacheprovider`
- 验证结果：JOB-011 定向 14 passed；`tests/test_gui_runtime.py tests/test_storage.py` 104 passed；全量 314 passed
- 观测证据：新增 `filter_and_rank_jobs` 方法和 `get_job_filter_results` 方法；新增 `_hard_filter_exclusion_reason`、`_low_confidence_fields`、`_ranking_score`、`_parse_salary_low`、`_parse_experience_years` 辅助函数；测试覆盖城市、远程、薪资、学历、经验、黑名单、已投递硬过滤、缺失字段低置信度标记、排序偏好改变岗位顺序、多过滤条件组合、session state 存储和空结果查询
- 副作用：新增 `GuiRuntime.filter_and_rank_jobs()` 和 `get_job_filter_results()`；新增 `JOB_FILTER_RESULTS_KEY` session state；不执行真实浏览器访问、投递动作或数据库 schema 变更
- 影响调用方：岗位评估服务、GUI 岗位清单可消费候选岗位、排除原因、低置信度标记和排序得分；现有采集、投递、面试、算法调用方不变
- 后续风险：真实投递队列仍需在 JOB-012 评估层接入后使用筛选结果；GUI 岗位清单展示仍由 JOB-013 处理

### JOB-012 岗位评估与建议

- 状态：`done`
- 目标：批量执行 JD 解析、简历匹配、风险识别、改进建议、投递话术生成。
- 影响范围：节点契约、prompt、评估服务、LLM 安全边界。
- 输入：`resume_profile`、标准岗位对象、JD 文本。
- 输出：评估报告对象。
- 实现要点：
  - 复用现有结构化节点思路。
  - 输出总分、优势、风险、缺失信息、简历补强建议、投递话术。
  - 控制 LLM 输入，只包含简历画像、岗位结构化字段和 JD 文本。
  - 批量执行时保留单个岗位失败原因。
- verify：
  - 评估报告字段完整。
  - 单个岗位评估失败不影响其他岗位。
  - prompt 和日志中不包含账号凭据、cookie、token。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_interview_nodes.py tests/test_gui_runtime.py
```

- 观测证据：记录评估输出样例、敏感字段扫描结果和测试输出摘要。
- 副作用：新增岗位评估结果。
- 影响调用方：GUI 岗位详情、批量确认弹窗。

#### JOB-012 完成记录

- 状态：done
- 负责人：implementer / main agent
- 开始时间：2026-06-16
- 完成时间：2026-06-16
- 修改文件：`src/interview_agent/prompts.py`、`src/interview_agent/state_contracts.py`、`src/interview_agent/nodes/interview.py`、`src/interview_agent/nodes/registry.py`、`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`、`tests/test_node_registry.py`、`tests/test_llm.py`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "evaluate_jobs"`；`rtk uv run pytest -p no:cacheprovider tests/test_interview_nodes.py tests/test_gui_runtime.py`；`rtk uv run pytest -p no:cacheprovider`
- 验证结果：JOB-012 定向 8 passed；`tests/test_interview_nodes.py tests/test_gui_runtime.py` 115 passed；全量 322 passed
- 观测证据：新增 `job_evaluation` prompt 模板、节点契约和 handler；新增 `GuiRuntime.evaluate_jobs()` 和 `get_job_evaluation_results()`；新增 `JOB_EVALUATION_RESULTS_KEY` session state；新增 `_job_structured_from_standard_job` 辅助函数；测试覆盖评估报告字段完整性、批量多岗位评估、单岗位失败不影响其他岗位、session state 存储、空结果查询、空列表场景和敏感字段扫描
- 副作用：新增 `job_evaluation` 节点和批量评估服务；不执行真实浏览器访问、投递动作或数据库 schema 变更
- 影响调用方：GUI 岗位详情和批量确认弹窗可消费评估报告、匹配分、优势、风险、缺失信息、简历建议和投递话术；现有采集、筛选、投递、面试、算法调用方不变
- 后续风险：真实 LLM 输出可能需根据字段契约做微调；GUI 岗位详情展示仍由 JOB-013 处理

### JOB-013 GUI 求职模块

- 状态：`pending`
- 目标：新增求职画像确认、采集进度、岗位清单、评估详情、批量确认弹窗、投递结果页。
- 影响范围：React 新模块、导航、API view model。
- 输入：求职画像、采集进度、岗位清单、评估报告、投递记录。
- 输出：用户可操作的求职投递 GUI。
- 实现要点：
  - 新增求职模块入口。
  - 展示画像确认表单。
  - 展示岗位采集进度页和失败平台重试入口。
  - 展示岗位清单和筛选控件。
  - 展示岗位详情、风险、建议和话术。
  - 支持勾选岗位并打开批量确认弹窗。
  - 展示投递批次结果。
  - 提供清空求职数据入口。
- verify：
  - 空状态、加载中、失败态、进度态、清单态渲染正确。
  - 采集进度、失败平台重试、筛选、勾选、确认、失败展示可测试。
  - 文本不溢出、不重叠。
- 验证命令：

```bash
rtk npm --prefix gui test
```

- 观测证据：记录前端测试输出和关键页面截图路径。
- 副作用：新增 GUI 模块入口。
- 影响调用方：桌面应用导航和运行时 facade。

### JOB-014 确认批次重校验

- 状态：`done`
- 目标：投递提交前重新校验用户确认的岗位，避免确认对象与实际提交对象不一致。
- 影响范围：投递执行器、平台适配器、投递记录。
- 输入：确认批次、选中岗位、平台实时详情状态。
- 输出：可提交岗位、跳过岗位、陈旧原因。
- 实现要点：
  - 投递前重新检查岗位是否下线。
  - 投递前重新检查是否已投递或按钮不可用。
  - 投递前检查 JD 是否发生关键变化。
  - 陈旧岗位写入 `skipped` 或 `duplicate`，并记录原因。
- verify：
  - 岗位下线时跳过。
  - 已投递时写入 `duplicate`。
  - 按钮失效时写入 `skipped` 或 `failed`。
  - JD 变化时要求重新确认或跳过。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py
```

- 观测证据：记录重校验状态样例和测试输出摘要。
- 副作用：投递前可能减少实际提交岗位。
- 影响调用方：批量投递执行、GUI 投递结果页。

### JOB-015 BOSS 直聘确认后投递适配器

- 状态：`done`
- 目标：实现 BOSS 直聘确认批次内的投递动作。
- 影响范围：BOSS 投递适配器、投递执行器。
- 输入：已重校验确认批次、岗位详情、投递话术。
- 输出：BOSS 投递结果。
- 实现要点：
  - 未确认批次禁止投递。
  - 只处理已通过重校验的岗位。
  - 投递失败记录平台提示和失败原因。
  - 遇到验证码、风控、强制弹窗时进入人工接管状态。
- verify：
  - 未确认批次不能提交。
  - 成功投递写入 `submitted`。
  - 失败投递写入 `failed`。
  - 风控场景暂停并可观测。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py
```

- 观测证据：记录 BOSS 投递夹具、投递状态样例和测试输出摘要。
- 副作用：产生 BOSS 平台投递动作。
- 影响调用方：批量投递执行器。

#### JOB-015 完成记录

- 状态：done
- 负责人：implementer / main agent
- 开始时间：2026-06-17
- 完成时间：2026-06-17
- 修改文件：`src/interview_agent/job_platform_adapters.py`、`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "boss_submit or submit_boss or get_boss_submit"`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`；`rtk uv run pytest -p no:cacheprovider`
- 验证结果：JOB-015 定向 14 passed；`tests/test_gui_runtime.py tests/test_storage.py` 138 passed；全量 348 passed
- 观测证据：新增 `BossSubmitJobPlatformAdapter`，复用只读适配器并添加 `submit_html_by_job_id` 投递夹具；新增 `GuiRuntime.submit_boss_applications()` 和 `get_boss_submit_results()`；新增 `JOB_BOSS_SUBMIT_RESULTS_KEY` session state；新增 `classify_job_platform_fixture_error` 对 `account_risk_control` 和 `forced_popup` 夹具状态的支持；测试覆盖未确认批次拦截、成功投递、失败投递、重复投递、验证码、风控、强制弹窗、按钮失效、混合场景、session state 存储和空结果查询
- 副作用：新增 BOSS 投递适配器和批量投递运行时服务；不执行真实浏览器访问或数据库 schema 变更
- 影响调用方：批量投递执行器可消费 BOSS 投递结果；现有采集、筛选、评估、面试、算法调用方不变
- 后续风险：JOB-016 和 JOB-017 需要复用本适配器模式为拉勾和猎聘实现投递适配器；JOB-018 批量投递执行器需整合重校验与多平台投递

### JOB-016 拉勾确认后投递适配器

- 状态：`done`
- 目标：实现拉勾确认批次内的投递动作。
- 影响范围：拉勾投递适配器、投递执行器。
- 输入：已重校验确认批次、岗位详情、投递话术。
- 输出：拉勾投递结果。
- 实现要点：
  - 未确认批次禁止投递。
  - 只处理已通过重校验的岗位。
  - 投递失败记录平台提示和失败原因。
  - 遇到验证码、风控、强制弹窗时进入人工接管状态。
- verify：
  - 未确认批次不能提交。
  - 成功投递写入 `submitted`。
  - 失败投递写入 `failed`。
  - 风控场景暂停并可观测。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py
```

- 观测证据：记录拉勾投递夹具、投递状态样例和测试输出摘要。
- 副作用：产生拉勾平台投递动作。
- 影响调用方：批量投递执行器。

#### JOB-016 完成记录

- 状态：done
- 负责人：implementer / main agent
- 开始时间：2026-06-17
- 完成时间：2026-06-17
- 修改文件：`src/interview_agent/job_platform_adapters.py`、`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "lagou_submit or submit_lagou or get_lagou_submit"`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`；`rtk uv run pytest -p no:cacheprovider`
- 验证结果：JOB-016 定向 14 passed；`tests/test_gui_runtime.py tests/test_storage.py` 152 passed；全量 362 passed
- 观测证据：新增 `LagouSubmitJobPlatformAdapter`，复用只读适配器并添加 `submit_html_by_job_id` 投递夹具；新增 `GuiRuntime.submit_lagou_applications()` 和 `get_lagou_submit_results()`；新增 `JOB_LAGOU_SUBMIT_RESULTS_KEY` session state；测试覆盖未确认批次拦截、成功投递、失败投递、重复投递、验证码、风控、强制弹窗、按钮失效、混合场景、session state 存储和空结果查询
- 副作用：新增拉勾投递适配器和批量投递运行时服务；不执行真实浏览器访问或数据库 schema 变更
- 影响调用方：批量投递执行器可消费拉勾投递结果；现有采集、筛选、评估、面试、算法调用方不变
- 后续风险：JOB-017 需要复用本适配器模式为猎聘实现投递适配器；JOB-018 批量投递执行器需整合重校验与多平台投递

### JOB-017 猎聘确认后投递适配器

- 状态：`done`
- 目标：实现猎聘确认批次内的投递动作。
- 影响范围：猎聘投递适配器、投递执行器。
- 输入：已重校验确认批次、岗位详情、投递话术。
- 输出：猎聘投递结果。
- 实现要点：
  - 未确认批次禁止投递。
  - 只处理已通过重校验的岗位。
  - 投递失败记录平台提示和失败原因。
  - 遇到验证码、风控、强制弹窗时进入人工接管状态。
- verify：
  - 未确认批次不能提交。
  - 成功投递写入 `submitted`。
  - 失败投递写入 `failed`。
  - 风控场景暂停并可观测。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py
```

- 观测证据：记录猎聘投递夹具、投递状态样例和测试输出摘要。
- 副作用：产生猎聘平台投递动作。
- 影响调用方：批量投递执行器。

#### JOB-017 完成记录

- 状态：done
- 负责人：implementer / main agent
- 开始时间：2026-06-17
- 完成时间：2026-06-17
- 修改文件：`src/interview_agent/job_platform_adapters.py`、`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "liepin_submit or submit_liepin or get_liepin_submit"`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`；`rtk uv run pytest -p no:cacheprovider`
- 验证结果：JOB-017 定向 14 passed；`tests/test_gui_runtime.py tests/test_storage.py` 166 passed；全量 376 passed
- 观测证据：新增 `LiepinSubmitJobPlatformAdapter`，复用只读适配器并添加 `submit_html_by_job_id` 投递夹具；新增 `GuiRuntime.submit_liepin_applications()` 和 `get_liepin_submit_results()`；新增 `JOB_LIEPIN_SUBMIT_RESULTS_KEY` session state；测试覆盖未确认批次拦截、成功投递、失败投递、重复投递、验证码、风控、强制弹窗、按钮失效、混合场景、session state 存储和空结果查询
- 副作用：新增猎聘投递适配器和批量投递运行时服务；不执行真实浏览器访问或数据库 schema 变更
- 影响调用方：批量投递执行器可消费猎聘投递结果；现有采集、筛选、评估、面试、算法调用方不变
- 后续风险：JOB-018 批量投递执行器需整合重校验与多平台投递

### JOB-018 批量投递执行

- 状态：`done`
- 目标：按用户确认批次逐个执行投递并记录状态。
- 影响范围：运行时 facade、投递执行器、平台适配器调用、投递记录。
- 输入：确认批次、选中岗位、投递话术、平台投递适配器。
- 输出：批次投递结果。
- 实现要点：
  - 投递前校验确认批次。
  - 调用 JOB-014 重校验结果。
  - 按平台和岗位逐个执行投递。
  - 成功、失败、跳过、重复拦截均写入投递记录。
  - 部分失败不回滚成功项。
  - 失败项支持重试。
- verify：
  - 成功投递写入 `submitted`。
  - 投递失败写入 `failed` 和失败原因。
  - 已投递写入 `duplicate` 或 `skipped`。
  - 未确认批次不能执行投递。
  - 部分失败时成功项保留。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py
```

- 观测证据：记录批次结果样例和测试输出摘要。
- 副作用：产生平台投递动作。
- 影响调用方：平台投递适配器、投递记录、GUI 结果页。

#### JOB-018 完成记录

- 状态：done
- 负责人：implementer / main agent
- 开始时间：2026-06-17
- 完成时间：2026-06-17
- 修改文件：`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "batch_submit or execute_batch"`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_storage.py`；`rtk uv run pytest -p no:cacheprovider`
- 验证结果：JOB-018 定向 8 passed；`tests/test_gui_runtime.py tests/test_storage.py` 174 passed；全量 384 passed
- 观测证据：新增 `GuiRuntime.execute_batch_submission()` 和 `get_batch_submit_results()`；新增 `JOB_BATCH_SUBMIT_RESULTS_KEY` session state；批量投递执行器整合 JOB-014 重校验与多平台投递适配器；测试覆盖不存在的批次拦截、未确认批次拦截、跨平台（BOSS/拉勾）成功投递、混合结果（成功/失败/重复/风控并存）、部分失败不回滚成功项、重校验跳过陈旧岗位（jd_changed）、session state 存储和空结果查询
- 副作用：新增批量投递执行器和 session state；不执行真实浏览器访问或数据库 schema 变更
- 影响调用方：GUI 批量投递结果页可消费跨平台批次投递结果；现有采集、筛选、评估、面试、算法调用方不变
- 后续风险：JOB-019 安全与隐私验收需对批量投递流程做敏感信息扫描

### JOB-019 安全与隐私验收

- 状态：`done`
- 目标：对求职投递全流程做安全与隐私验收，确认账号凭据、cookie、token 不入库、不进日志、不进 LLM。
- 影响范围：日志、session state、prompt 构造、错误展示、平台适配器输出。
- 输入：岗位采集、评估、投递全流程数据。
- 输出：安全验收结果。
- 实现要点：
  - 扫描 session state、node_runs、日志输出和 prompt 输入。
  - 验证错误展示不包含敏感信息。
  - 验证清空求职数据不影响 Chrome 登录态。
  - 验证人工接管状态不包含敏感会话内容。
- verify：
  - 敏感字段扫描无命中。
  - LLM prompt 只包含简历画像、岗位字段和 JD 文本。
  - 日志只记录错误类型和阶段，不记录凭据。
  - 清空求职数据不影响 Chrome 登录态。
- 验证命令：

```bash
rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_interview_nodes.py tests/test_storage.py
```

- 观测证据：记录扫描命令、扫描结果摘要和测试输出摘要。
- 副作用：无业务副作用。
- 影响调用方：全部求职投递流程。

#### JOB-019 完成记录

- 状态：done
- 负责人：implementer / main agent
- 开始时间：2026-06-17
- 完成时间：2026-06-17
- 修改文件：`src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`
- 验证命令：`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py -k "security or sensitive or sanitize or privacy"`；`rtk uv run pytest -p no:cacheprovider tests/test_gui_runtime.py tests/test_interview_nodes.py tests/test_storage.py`；`rtk uv run pytest -p no:cacheprovider`
- 验证结果：JOB-019 定向 17 passed；联合测试 203 passed；全量 395 passed
- 观测证据：`gui_runtime.py` 四个投递方法异常捕获处添加 `contains_sensitive_payload()` 防御性检查；新增 11 个安全验收测试覆盖异常脱敏（批量 + 三平台）、安全异常保留原文、view_model 清洁性、人工接管无敏感内容、session store 拒绝敏感写入、清求职数据不影响 sessions、评估 prompt 无敏感字段、单平台投递清洁
- 副作用：无业务副作用，仅影响异常消息的脱敏路径
- 影响调用方：全部投递流程的异常展示增加敏感信息脱敏层
- 后续风险：`evaluate_jobs` 异常路径可后续统一脱敏；`platform_message` 字段可考虑应用层预过滤以实现优雅降级

## 主 agent 合并后检查项

以下事项不由 implementer 在任务分支内执行：

- 更新 `docs/TODO.md` 任务状态。
- 新功能完成后更新 `HISTORY.md`。
- 若任务涉及运行时入口、节点编排、节点契约、存储结构、配置边界或外部服务调用，由主 agent 在合并后更新 `docs/architecture.md` 和 `docs/architecture.svg`。
- 推送主分支前验证架构图与当前代码一致。

架构文档验证命令：

```bash
rtk xmllint --noout docs/architecture.svg
```

## 阶段验收

### 阶段 1：数据、画像与安全边界

- 包含任务：JOB-001、JOB-002、JOB-003、JOB-004、JOB-005。
- 验收条件：可保存求职数据，可从简历生成求职画像，适配器契约和敏感信息边界可验证。

### 阶段 2：采集编排与只读平台采集

- 包含任务：JOB-006、JOB-007、JOB-008、JOB-009、JOB-010。
- 验收条件：三个平台都能只读输出标准岗位对象，并能观测登录失效、验证码、限流、页面异常和人工接管状态。

### 阶段 3：筛选、评估与 GUI

- 包含任务：JOB-011、JOB-012、JOB-013。
- 验收条件：候选岗位可筛选排序，每个岗位有评估报告和投递话术，GUI 可展示画像、进度、清单、详情和确认弹窗。

### 阶段 4：投递前重校验与平台投递

- 包含任务：JOB-014、JOB-015、JOB-016、JOB-017、JOB-018。
- 验收条件：用户可批量确认清单，系统投递前重校验，并按平台执行确认后投递。

### 阶段 5：安全与主分支收尾

- 包含任务：JOB-019 与主 agent 合并后检查项。
- 验收条件：敏感信息不入库、不进日志、不进 LLM；主 agent 完成 TODO、HISTORY 和架构文档同步。

## 每次任务完成记录模板

```markdown
### JOB-XXX 完成记录

- 状态：done
- 负责人：
- 开始时间：
- 完成时间：
- 修改文件：
- 验证命令：
- 验证结果：
- 观测证据：
- 副作用：
- 影响调用方：
- 后续风险：
```
