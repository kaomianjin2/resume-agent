# GUI 开发拆分计划

## 结论

GUI 开发按 7 个可追踪阶段推进：先固化设计与边界，再新增 Python GUI Runtime Facade，随后落地 React Web Shell、真实运行时接入、模拟面试闭环、算法练习 MVP，最后再做桌面壳。

## 追踪规则

### 状态枚举

- `[ ]` 未开始
- `[~]` 进行中
- `[x]` 已完成
- `[!]` 阻塞

### 更新规则

- 每个 GUI Phase 只允许在对应任务开始后从 `[ ]` 改为 `[~]`。
- 每个 GUI Phase 必须在最小测试、reviewer 审查、影响文档更新完成后才能改为 `[x]`。
- 阻塞时改为 `[!]`，并在“阻塞原因”中记录具体命令、错误或待决策事项。
- 完成后必须填写“完成证据”，至少包含提交或合并记录、测试命令、reviewer 结论。
- 若涉及运行时入口、节点编排、节点契约、配置边界、外部服务调用或桌面壳，必须同步更新 `docs/architecture.md` 和 `docs/architecture.svg`。
- 新功能完成、测试通过、reviewer 通过并合并到主分支后，必须更新 `docs/HISTORY.md`。

## 总体边界

- 不把运行时改成固定流水线；入口语义仍是自然语言触发能力节点。
- 不在 GUI 启动时构建知识库；启动只检查 `knowledge_base_meta.status = ready`。
- 不读取环境变量作为项目配置；配置仍固定来自 `config/interview-agent.toml`。
- 不修改 `/Users/cynicism/Desktop/面试` 原始资料。
- 不修改数据库结构；节点结果继续写入 `session_state` 和 `node_runs`。
- 不让 GUI 绕过 SQLite 共享节点状态。
- 不让 GUI 向用户展示内部节点名、执行计划或 `candidate_nodes`。
- 不改 LLM、embedding、知识库构建和检索契约。
- 未经用户确认，不安装或升级前端、桌面壳、HTTP 服务依赖。

## 阶段总览

| Phase | 状态 | Owner | 依赖 | 可并行 | Tracking ID | 完成证据 |
| --- | --- | --- | --- | --- | --- | --- |
| GUI Phase 0 设计与边界固化 | `[x]` | main agent | 当前草图 | 否 | `gui-phase-0-plan-boundary` | `39591b0`；Phase 0 静态验收命令通过；reviewer 可继续 |
| GUI Phase 1 Runtime Facade | `[ ]` | implementer | Phase 0 | 否 | `gui-phase-1-runtime-facade` | 待填写 |
| GUI Phase 2 React Web Shell | `[ ]` | implementer | Phase 0 | 可与 Phase 1 协调 | `gui-phase-2-web-shell` | 待填写 |
| GUI Phase 3 面试准备真实接入 | `[ ]` | implementer | Phase 1、Phase 2 | 否 | `gui-phase-3-prep-integration` | 待填写 |
| GUI Phase 4 模拟面试闭环 | `[ ]` | implementer | Phase 1、Phase 2 | 可在 Phase 3 后启动 | `gui-phase-4-mock-interview` | 待填写 |
| GUI Phase 5 算法练习 MVP | `[ ]` | implementer | Phase 2 | 可与 Phase 3/4 并行 | `gui-phase-5-algorithm-mvp` | 待填写 |
| GUI Phase 6 桌面壳集成 | `[ ]` | implementer | Phase 3、Phase 4、Phase 5 | 否 | `gui-phase-6-desktop-shell` | 待填写 |

## 推荐顺序

1. GUI Phase 0：设计与边界固化
2. GUI Phase 1：Runtime Facade
3. GUI Phase 2：React Web Shell
4. GUI Phase 3：面试准备真实接入
5. GUI Phase 4：模拟面试闭环
6. GUI Phase 5：算法练习 MVP
7. GUI Phase 6：桌面壳集成

## GUI Phase 0：设计与边界固化

**Status:** `[x]`
**Owner:** main agent
**Dependencies:** 当前 GUI 草图
**Parallel:** no
**Tracking ID:** `gui-phase-0-plan-boundary`
**Write Scope:** `docs/GUI_DEVELOPMENT_PLAN.md`
**完成证据:** `39591b0`；`rtk rg "面试准备|模拟面试|算法练习|检查面板" docs/GUI_DEVELOPMENT_PLAN.md`；`rtk rg "不修改数据库结构|不在 GUI 启动时构建知识库|config/interview-agent.toml" docs/GUI_DEVELOPMENT_PLAN.md`；`rtk rg "Status:|Tracking ID:|完成证据|阻塞原因|测试命令|可视化验收" docs/GUI_DEVELOPMENT_PLAN.md`；`rtk git diff --check -- docs/GUI_DEVELOPMENT_PLAN.md`；reviewer 结论：可继续
**阻塞原因:** none

### 目标

把 GUI 的模块、边界、阶段、验收命令和流程要求固化为可追踪文档，作为后续 worktree 任务拆分依据。

### 任务清单

1. [操作] 固化 GUI 模块范围 → verify: `rtk rg "面试准备|模拟面试|算法练习|检查面板" docs/GUI_DEVELOPMENT_PLAN.md`
2. [操作] 固化运行时边界 → verify: `rtk rg "不修改数据库结构|不在 GUI 启动时构建知识库|config/interview-agent.toml" docs/GUI_DEVELOPMENT_PLAN.md`
3. [操作] 固化每阶段状态字段 → verify: `rtk rg "Status:|Tracking ID:|完成证据|阻塞原因" docs/GUI_DEVELOPMENT_PLAN.md`
4. [操作] 静态检查文档 → verify: `rtk git diff --check -- docs/GUI_DEVELOPMENT_PLAN.md`

### 测试命令

- `rtk rg "面试准备|模拟面试|算法练习|检查面板" docs/GUI_DEVELOPMENT_PLAN.md`
- `rtk rg "不修改数据库结构|不在 GUI 启动时构建知识库|config/interview-agent.toml" docs/GUI_DEVELOPMENT_PLAN.md`
- `rtk rg "Status:|Tracking ID:|完成证据|阻塞原因|测试命令|可视化验收" docs/GUI_DEVELOPMENT_PLAN.md`
- `rtk git diff --check -- docs/GUI_DEVELOPMENT_PLAN.md`

### 可视化验收

- 文档可直接看到阶段总览表、Phase 0 元数据块、测试命令和可视化验收字段。
- 文档可直接看到 GUI 模块范围：面试准备、模拟面试、算法练习、检查面板。
- 文档可直接看到 GUI 边界：不修改数据库结构、不在 GUI 启动时构建知识库、配置来自 `config/interview-agent.toml`。

### 验收标准

- 文档包含阶段总览、依赖、Owner、Write Scope、测试命令和可视化验收。
- 每个阶段都有唯一 `Tracking ID`。
- 文档不要求立即新增依赖或修改运行时代码。

### 副作用

- 只新增文档。
- 不影响现有 CLI、知识库、数据库、配置和测试。

## GUI Phase 1：Runtime Facade

**Status:** `[ ]`
**Owner:** implementer
**Dependencies:** GUI Phase 0
**Parallel:** no
**Tracking ID:** `gui-phase-1-runtime-facade`
**Write Scope:** `src/interview_agent/gui_runtime.py`、`tests/test_gui_runtime.py`、必要架构文档
**完成证据:** 待填写
**阻塞原因:** none

### 目标

新增 GUI 专用结构化运行时门面，封装现有 Python 后端能力，不新增 HTTP 服务、不新增配置、不修改数据库结构。

### 接口候选

```text
load_runtime(config_path)
create_or_open_session(session_id)
list_nodes()
route_request(message)
build_plan(message, selected_node)
execute_node(session_id, node_name, inputs)
get_session_state(session_id)
```

### 任务清单

1. [操作] 编写 runtime facade 测试 → verify: `rtk uv run pytest tests/test_gui_runtime.py` 先失败
2. [操作] 封装配置读取和 KB ready 状态 → verify: GUI runtime 只读取 `config/interview-agent.toml`
3. [操作] 封装 session 创建和 state 读取 → verify: `get_session_state()` 返回结构化 dict
4. [操作] 封装 route、plan、execute 流程 → verify: 明确路由可执行节点并刷新 session state
5. [操作] 覆盖缺输入和失败路径 → verify: 缺输入不写入成功 state，失败 node_run 不污染成功结果
6. [操作] 运行最小回归 → verify: `rtk uv run pytest tests/test_gui_runtime.py tests/test_executor.py tests/test_router_planner.py`

### 测试命令

- `rtk uv run pytest tests/test_gui_runtime.py`
- `rtk uv run pytest tests/test_gui_runtime.py tests/test_executor.py tests/test_router_planner.py`

### 可视化验收

- GUI 层可读取 runtime status、session 和节点执行结果，但界面不直接消费 CLI 文本输出。
- 用户视角不展示内部节点名、执行计划或 `candidate_nodes`。

### 验收标准

- GUI 可通过 Python facade 获取 status、session、route、execute、state。
- 不暴露 CLI 文本输出作为 GUI 数据源。
- 不展示内部节点名给用户层；内部字段只作为接口数据。

### 副作用

- 新增运行时入口层。
- 涉及架构边界，完成时必须更新 `docs/architecture.md` 和 `docs/architecture.svg`。

## GUI Phase 2：React Web Shell

**Status:** `[ ]`
**Owner:** implementer
**Dependencies:** GUI Phase 0
**Parallel:** 可与 Phase 1 协调
**Tracking ID:** `gui-phase-2-web-shell`
**Write Scope:** `gui/`、必要文档
**完成证据:** 待填写
**阻塞原因:** 需要用户确认允许新增前端依赖

### 目标

基于当前草图落地 Web UI 壳，先使用 fixture 数据驱动模块切换和检查面板，不接真实后端。

### 推荐目录

```text
gui/
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  src/
    main.tsx
    app/
      App.tsx
      layout/
        ShellLayout.tsx
        Sidebar.tsx
        Workspace.tsx
        ReviewPanel.tsx
    modules/
      prep/
      mock/
      algorithm/
    shared/
      api/
      components/
      styles/
```

### 任务清单

1. [操作] 创建 Web Shell 工程 → verify: `rtk npm run build`
2. [操作] 实现三栏布局和响应式结构 → verify: 桌面左中右三栏，移动端纵向堆叠
3. [操作] 实现模块切换 → verify: 点击 `面试准备 / 模拟面试 / 算法练习` 时主区域和检查面板同步变化
4. [操作] 实现 fixture view model → verify: UI 不依赖真实 LLM、KB 或 SQLite
5. [操作] 运行构建和预览 → verify: `rtk npm run build`；`rtk npm run preview` 启动成功后人工访问预览页观察模块切换和布局，完成后 `Ctrl-C` 退出

### 可视化验收

- 面试准备页不展示结构化 JSON。
- 题目生成不作为面试准备页按钮。
- 模拟面试模块包含逐题回答和追问区域。
- 算法练习模块包含题目、语言、编辑器和评审面板。
- 检查面板随当前模块变化。

### 测试命令

- `rtk npm run build`
- `rtk npm run preview` 启动成功后人工访问预览页观察模块切换、检查面板同步和响应式布局，完成后 `Ctrl-C` 退出

### 副作用

- 新增前端工程目录。
- 引入依赖前必须获得用户确认。

### 验收标准

- Web Shell 仅使用 fixture 数据驱动，不接真实后端，不依赖真实 LLM、知识库或 SQLite。
- 模块切换覆盖 `面试准备`、`模拟面试`、`算法练习`，且切换后主区域与检查面板同步更新。
- 布局同时满足桌面三栏和移动端纵向堆叠的响应式要求。
- 本阶段范围仅限已确认前端依赖下的 Web Shell 壳层实现，不新增未确认依赖，也不越界到 Phase 1、Phase 3、Phase 4、Phase 5、Phase 6 的真实接入或桌面壳实现。

## GUI Phase 3：面试准备真实接入

**Status:** `[ ]`
**Owner:** implementer
**Dependencies:** GUI Phase 1、GUI Phase 2
**Parallel:** no
**Tracking ID:** `gui-phase-3-prep-integration`
**Write Scope:** `gui/src/modules/prep/`、`gui/src/shared/api/`、必要 `src/interview_agent/gui_runtime.py` 测试补充
**完成证据:** 待填写
**阻塞原因:** none

### 目标

让面试准备模块接入真实 runtime facade，完成简历解析、JD 解析、匹配报告和准备摘要展示。

### 任务清单

1. [操作] 定义 prep view model → verify: fixture 和真实 runtime 返回同构数据
2. [操作] 接入 `resume_parse` → verify: 导入简历后展示用户可读摘要
3. [操作] 接入 `jd_parse` → verify: 导入 JD 后展示岗位重点
4. [操作] 接入 `jd_match` → verify: 展示匹配度、优势、风险、追问重点
5. [操作] 覆盖缺输入状态 → verify: 未导入简历或 JD 时显示可操作提示
6. [操作] 运行测试 → verify: `rtk uv run pytest tests/test_gui_runtime.py && rtk npm run build`

### 测试命令

- `rtk uv run pytest tests/test_gui_runtime.py`
- `rtk npm run build`

### 可视化验收

- 面试准备页展示简历摘要、岗位重点、匹配度、优势、风险和追问重点，不展示原始结构化数据。
- 页面不出现“生成题目”按钮，题目生成入口只保留在模拟面试模块。

### 验收标准

- 面试准备页展示可读内容，不展示原始结构化数据。
- 准备页不提供“生成题目”按钮。
- 题目生成流程留在模拟面试模块。

### 副作用

- 读取和展示 session state。
- 不修改数据库结构和节点契约。

## GUI Phase 4：模拟面试闭环

**Status:** `[ ]`
**Owner:** implementer
**Dependencies:** GUI Phase 1、GUI Phase 2
**Parallel:** 可在 Phase 3 后启动
**Tracking ID:** `gui-phase-4-mock-interview`
**Write Scope:** `gui/src/modules/mock/`、`gui/src/shared/api/`、必要 runtime facade 测试补充
**完成证据:** 待填写
**阻塞原因:** none

### 目标

GUI 保持现有模拟面试行为：内部先生成层层递进的问题，再逐题询问，并基于回答追问。

### 任务清单

1. [操作] 接入题目生成 → verify: 点击开始模拟后出现第一题
2. [操作] 实现回答提交 → verify: 空回答、正常回答都有明确状态
3. [操作] 接入 `mock_followup` → verify: 提交回答后生成追问
4. [操作] 接入评分和建议 → verify: 回合结束后检查面板展示评分、风险和改进建议
5. [操作] 覆盖中断和空题集 → verify: 用户可结束当前模拟，空题集显示可读错误
6. [操作] 运行测试 → verify: `rtk uv run pytest tests/test_cli.py -k "mock_interview" && rtk npm run build`

### 测试命令

- `rtk uv run pytest tests/test_cli.py -k "mock_interview"`
- `rtk npm run build`

### 可视化验收

- 开始模拟后一次只展示当前问题，不一次性展示全部题目。
- 提交回答后界面出现追问或下一题，并在回合结束后显示评分、风险和改进建议。

### 验收标准

- 不一次性展示所有题目。
- 每轮只展示当前问题、回答区和必要追问。
- 中断后不污染后续会话状态。

### 副作用

- 复用现有模拟面试节点和 session state。
- 不改模拟面试节点契约。

## GUI Phase 5：算法练习 MVP

**Status:** `[ ]`
**Owner:** implementer
**Dependencies:** GUI Phase 2
**Parallel:** 可与 Phase 3/4 并行
**Tracking ID:** `gui-phase-5-algorithm-mvp`
**Write Scope:** `gui/src/modules/algorithm/`、必要测试
**完成证据:** 待填写
**阻塞原因:** none

### 目标

先做算法练习前端 MVP，使用 fixture 数据完成题目、语言、编辑器、运行结果和评审面板展示；真实代码运行和安全沙箱接入另拆任务。

### 任务清单

1. [操作] 实现题目展示 → verify: 题干、约束、示例和标签完整显示
2. [操作] 实现语言切换和编辑区 → verify: Python、JavaScript、Go、Java、C、C++ 可切换
3. [操作] 实现运行结果状态 → verify: 空代码、错误代码、通过用例三种状态可展示
4. [操作] 实现评审面板 fixture → verify: 正确性、复杂度、边界 case、建议列表可展示
5. [操作] 运行构建 → verify: `rtk npm run build`

### 测试命令

- `rtk npm run build`

### 可视化验收

- 算法练习页可切换语言并保留题目、编辑器、运行结果和评审面板四个核心区域。
- 空代码、错误代码、通过用例三种状态都能在界面中被区分。

### 验收标准

- 算法练习不影响面试准备和模拟面试。
- 危险代码执行、安全检测、真实运行器不纳入本阶段。

### 副作用

- 只改前端模块。
- 不新增后端执行能力。

## GUI Phase 6：桌面壳集成

**Status:** `[ ]`
**Owner:** implementer
**Dependencies:** GUI Phase 3、GUI Phase 4、GUI Phase 5
**Parallel:** no
**Tracking ID:** `gui-phase-6-desktop-shell`
**Write Scope:** `desktop/`、`gui/`、必要启动文档
**完成证据:** 待填写
**阻塞原因:** 需要用户确认允许新增桌面壳依赖

### 目标

用桌面壳包装 Web UI，提供本地窗口、文件选择和 Python 后端进程启停；业务逻辑继续由 Python 后端负责。

### 任务清单

1. [操作] 新增桌面壳配置 → verify: `rtk npm run tauri dev` 启动成功后人工观察桌面窗口是否打开，完成后 `Ctrl-C` 退出
2. [操作] 接入本地文件选择 → verify: 导入简历和 JD 不修改原始文件
3. [操作] 启动 Python runtime 进程 → verify: 桌面窗口打开后 GUI 可读取 KB ready 状态
4. [操作] 关闭窗口清理进程 → verify: 关闭窗口后本地后端进程退出
5. [操作] 打包桌面应用 → verify: `rtk npm run tauri build`

### 测试命令

- `rtk npm run tauri dev` 启动成功后人工观察桌面窗口和 GUI 工作台，完成后 `Ctrl-C` 退出
- `rtk npm run tauri build`

### 可视化验收

- 桌面窗口启动后直接进入 GUI 工作台，并能显示 KB ready 状态。
- 导入简历和 JD 使用本地文件选择，不修改 `/Users/cynicism/Desktop/面试` 原始资料。

### 验收标准

- 桌面窗口启动后直接进入工作台。
- 关闭窗口后无残留后端进程。
- 文件导入不触碰 `/Users/cynicism/Desktop/面试` 原始资料。

### 副作用

- 新增桌面壳依赖和配置。
- 涉及新运行入口，必须更新架构文档和架构图。

## 每阶段固定流程

1. [操作] 创建独立 worktree → verify: `rtk git worktree list`
2. [操作] 派发 fresh implementer → verify: implementer 最终列出修改文件和测试命令
3. [操作] implementer 自测并中文提交 → verify: `rtk git log -1 --oneline`
4. [操作] 派发 reviewer → verify: reviewer 结论为可继续
5. [操作] 运行最小必要测试 → verify: 对应 Phase 的测试命令通过
6. [操作] 合并到主分支 → verify: `rtk git log --oneline -5`
7. [操作] 更新 `docs/HISTORY.md` → verify: `rtk rg "<Tracking ID>|GUI Phase" docs/HISTORY.md`
8. [操作] 必要时更新架构文档和架构图 → verify: `rtk git diff -- docs/architecture.md docs/architecture.svg`
9. [操作] 推送主分支 → verify: `rtk git status --short`
10. [操作] 删除任务 worktree → verify: `rtk git worktree list`

## 风险与阻塞清单

- 前端工程、HTTP 服务、Tauri 都会引入依赖；必须在执行对应阶段前获得用户确认。
- GUI 专属测试框架尚未存在；Phase 2 需要同时确定前端测试命令。
- GUI 新入口属于架构变更；漏更新 `docs/architecture.md` 或 `docs/architecture.svg` 会阻塞合并。
- 若 GUI 绕过 `session_state` 直接拼业务状态，会破坏现有运行时边界。
- 若面试准备页重新加入“生成题目”入口，会破坏“题目生成归模拟面试模块”的产品边界。
- 算法练习真实运行用户代码涉及安全边界，必须单独拆分，不混入前端 MVP。
