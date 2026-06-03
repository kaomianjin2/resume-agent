# GUI UI Restore v2 追踪计划

## 结论

旧计划作废。从 `gui-ui-restore-v2-foundation` 重新追踪：先按 `docs/gui-mvp-cyberpunk-mockup.html` 还原 GUI 视觉骨架，再补齐模拟面试的题目数、题型、追问轮数选择。

## 总体目标

- 视觉真源：`docs/gui-mvp-cyberpunk-mockup.html`。
- 实现目标：GUI 保持当前真实数据与运行时能力，同时恢复原型的深色霓虹工作台、三栏布局、玻璃面板、紧凑信息密度。
- 功能目标：模拟面试开始前支持配置题目数、题型、追问轮数，配置值进入启动路径。
- 追踪目标：每个 Task 都能独立进入、独立验收、独立写入完成证据。

## Frontend Design 拆分原则

- 视觉方向：延续原型的 cyberpunk operational console，不做营销页、英雄区或装饰性卡片堆叠。
- 信息密度：面向重复使用的工作台，优先紧凑、可扫描、稳定，不使用大段说明文案占据首屏。
- 控件形态：选择项使用明确的分段控件、按钮组或 select；主要命令使用按钮；状态使用 tag，不用正文解释操作方式。
- 布局稳定：固定格式元素必须有稳定尺寸、gap、min/max 约束，避免 hover、状态文本、长选项导致布局跳动。
- 响应式验收：桌面、窄桌面、移动宽度都必须截图和 DOM 量测；无横向滚动、无文本重叠。
- 视觉副作用：不得把准备页改回通用卡片网格，不得引入与原型冲突的新色板、圆角体系或装饰背景。

## 边界

- 本次落计划只修改 `docs/GUI_UI_RESTORE_PLAN.md`。
- 不实现代码。
- 不更新 `docs/HISTORY.md`；等代码实现和验证完成后再更新。
- 不新增或升级依赖。
- 不修改 `.env`、`.gitignore`、密钥、证书、生产配置。
- 不修改数据库结构、部署流程。
- 不修改 `/Users/cynicism/Desktop/面试` 原始资料。
- 不删除文件。

## 状态规则

- `[ ]` 未开始
- `[~]` 进行中
- `[x]` 已完成
- `[!]` 阻塞

## 更新规则

- Task 开始时，将状态从 `[ ]` 改为 `[~]`。
- Task 完成时，将状态改为 `[x]`，并填写“完成证据”。
- Task 阻塞时，将状态改为 `[!]`，并填写命令、错误、待决策项。
- 不允许在未验证前写入完成证据。
- 每个 Task 的完成证据必须包含至少一个可复跑命令或截图路径。

## Task Overview

| Task | 状态 | Tracking ID | 依赖 | 主要影响范围 | 完成证据 |
| --- | --- | --- | --- | --- | --- |
| Task 0：基线复核与旧计划冻结 | `[x]` | `gui-ui-restore-v2-foundation` | 无 | `docs/GUI_UI_RESTORE_PLAN.md` | `rtk rg "app|shell|workspace|problem-card|prep-board|review-panel" docs/gui-mvp-cyberpunk-mockup.html`；`rtk rg "ShellLayout|Workspace|ReviewPanel|PrepModule|MockModule" gui/src`；`rtk rg "StartMockInterviewRequest|questionCount|followupRounds|startMockInterview" gui/src src/interview_agent/gui_runtime.py`；`rtk rg "旧计划作废|gui-ui-restore-v2-foundation" docs/GUI_UI_RESTORE_PLAN.md` |
| Task 1：Shell 三栏与视觉系统还原 | `[x]` | `gui-ui-restore-v2-shell-visual-system` | Task 0 | `gui/src/app/layout/`、`gui/src/shared/styles/global.css` | `rtk npm run build`；`output/playwright/gui-ui-restore-task1-1440x900.png`；`output/playwright/gui-ui-restore-task1-1180x900.png`；`output/playwright/gui-ui-restore-task1-820x900.png`；DOM 量测 1440x900 为 `220px 780px 360px`、`scrollWidth === clientWidth`、`navFocusOutline = solid 2px rgb(70, 246, 255)`；1180x900 无横向滚动；820x900 无横向滚动 |
| Task 2：面试准备页首屏还原 | `[x]` | `gui-ui-restore-v2-prep-first-screen` | Task 1 | `gui/src/modules/prep/PrepModule.tsx`、`gui/src/shared/styles/global.css` | `rtk npm run build`；`output/playwright/gui-ui-restore-task2-1440x900.png`；`output/playwright/gui-ui-restore-task2-1180x900.png`；`output/playwright/gui-ui-restore-task2-820x900.png`；DOM 量测 1440x900 为 `scrollWidth === clientWidth`、6 个业务槽位 `简历摘要`/`岗位重点`/`匹配度`/`优势`/`风险`/`追问重点`、`problemCardHeight = 161`、`prepBoardTop = 297`、`prepBoardGap = 12px`、`prepRowPadding = 12px 16px`、`prepRowColumns = 180px 474px`、`hasGenerateQuestionButton = false`；1180x900 为 `scrollWidth === clientWidth`、`prepRows = 6`、`importButtons = 导入简历/导入 JD`、`problemCardHeight = 161`、`prepBoardTop = 297`、`reviewPanelGridColumn = 2`；820x900 为 `scrollWidth === clientWidth`、`prepRows` 保持 6 个槽位、`problemCardWidth = 750`、`hasGenerateQuestionButton = false` |
| Task 3：右侧检查面板还原 | `[x]` | `gui-ui-restore-v2-review-panel` | Task 1、Task 2 | `gui/src/app/layout/ReviewPanel.tsx`、`gui/src/shared/styles/global.css` | `rtk npm run build`；`output/playwright/gui-ui-restore-task3-1440x900.png`；DOM 量测 1440x900 为 `title = 准备检查`、`score = 92`、metrics 为 `匹配度`/`追问点`/`材料状态`、动态匹配分 `91 / 100`、suggestions 为 `补齐项目背景`/`优先准备弱项`/`保留常见问题`、`suggestionCount = 3`、`panelWidth = 360`、`scrollWidth === clientWidth`；非 prep 模块量测为 `title = 模拟面试检查`、metrics 为 `就绪项`/`待检查`/`边界项`、`suggestionCount = 3` |
| Task 4：响应式与无溢出验收 | `[x]` | `gui-ui-restore-v2-responsive-qa` | Task 1、Task 2、Task 3 | `gui/src/shared/styles/global.css` | `rtk npm run build`；`output/playwright/gui-ui-restore-task4-1440x900.png`；`output/playwright/gui-ui-restore-task4-1180x900.png`；`output/playwright/gui-ui-restore-task4-820x900.png`；DOM 量测 1440x900 为 `scrollWidth === clientWidth`、`.shell-layout` 列宽 `220px 780px 360px`、按钮溢出数 `0`；1180x900 为 `scrollWidth === clientWidth`、双列 `200px 918px`、右栏 `grid-column = 2`；820x900 为 `scrollWidth === clientWidth`、单列 `792px`、右栏 `grid-column = auto` |
| Task 5：模拟面试入口重排 | `[x]` | `gui-ui-restore-v2-mock-entry-layout` | Task 1、Task 4 | `gui/src/modules/mock/MockModule.tsx`、`gui/src/shared/styles/global.css` | `rtk npm run build`；`output/playwright/gui-ui-restore-task5-1440x900.png`；`output/playwright/gui-ui-restore-task5-1180x900.png`；`output/playwright/gui-ui-restore-task5-820x900.png`；DOM 量测 1440x900 为 `scrollWidth === clientWidth`、当前题/配置区/作答区/记录区存在、mock 内唯一主按钮 `开始模拟`、次级按钮 `结束当前模拟`/`提交回答`、状态行 `题目进度 0/0`/`追问进度 0/0`/`状态 未开始`、按钮溢出数 `0`；1180x900 为 `scrollWidth === clientWidth`、mock workbench 双列 `310.312px 551.688px`、可见按钮 `开始模拟`/`结束当前模拟`/`提交回答`、按钮溢出数 `0`；820x900 为 `scrollWidth === clientWidth`、mock workbench 单列 `750px`、四个主区域宽度均为 `750`、按钮溢出数 `0`；交互验证开始模拟后显示 `第 1 题`，空回答提交显示 `请先输入当前题回答。`，有效回答提交后记录区显示 `已完成轮次` 且输入清空 |
| Task 6：模拟面试选择补齐 | `[x]` | `gui-ui-restore-v2-mock-options` | Task 5 | `gui/src/modules/mock/MockModule.tsx`、`gui/src/shared/api/mock.ts`、必要 runtime adapter | `rtk npm run build`；`rtk uv run pytest tests/test_gui_runtime.py`；`output/playwright/gui-ui-restore-task6-1440x900.png`；`output/playwright/gui-ui-restore-task6-1180x900.png`；`output/playwright/gui-ui-restore-task6-820x900.png`；DOM 量测 1440x900 为 `scrollWidth === clientWidth`、`shellColumns = 220px 780px 360px`、题目数/题型/追问轮数三组选择都存在且默认值分别为 `5`/`行为面试`/`1`、开始模拟后 `题目进度 1/5`；1180x900 为 `scrollWidth === clientWidth`、`shellColumns = 200px 918px`、选择控件与按钮无重叠；820x900 为 `scrollWidth === clientWidth`、`shellColumns = 792px`、选择控件纵向堆叠且无横向滚动 |
| Task 7：端到端验收与记录 | `[x]` | `gui-ui-restore-v2-final-acceptance` | Task 1-6 | `docs/GUI_UI_RESTORE_PLAN.md`、实现完成后 `docs/HISTORY.md` | `rtk npm run build`；`rtk uv run pytest tests/test_gui_runtime.py -k mock_interview`；`curl -I http://127.0.0.1:4173`；`output/playwright/gui-ui-restore-task7-1440x900.png`；`output/playwright/gui-ui-restore-task7-1180x900.png`；`output/playwright/gui-ui-restore-task7-820x900.png`；DOM 量测 1440x900 准备页 `scrollWidth === clientWidth`、列宽 `220px 780px 360px`、6 个业务槽位完整、右栏 `准备检查`/`92`/三条建议、无 `生成题目` 按钮；1180x900 列宽 `200px 918px` 且右栏在第二列；820x900 单列 `792px`；mock 默认启动为 `题目进度 1/5`；选择 `8`/`项目深挖`/`0` 后启动为 `题目进度 1/8`、`追问进度 0/0`，提交后直接进入第 2 题 |

## Task 0：基线复核与旧计划冻结

**Status:** `[x]`
**Tracking ID:** `gui-ui-restore-v2-foundation`
**Owner:** main agent
**Dependencies:** none
**Write Scope:** `docs/GUI_UI_RESTORE_PLAN.md`

### 目标

确认 v2 计划替代旧计划，并在动代码前复核原型、现状和影响范围。

### 任务清单

1. [操作] 读取原型关键结构 → verify: `rtk rg "app|shell|workspace|problem-card|prep-board|review-panel" docs/gui-mvp-cyberpunk-mockup.html`
2. [操作] 读取 GUI 布局入口 → verify: `rtk rg "ShellLayout|Workspace|ReviewPanel|PrepModule|MockModule" gui/src`
3. [操作] 读取 mock runtime 边界 → verify: `rtk rg "StartMockInterviewRequest|questionCount|followupRounds|startMockInterview" gui/src src/interview_agent/gui_runtime.py`
4. [操作] 标记本计划为 v2 唯一执行入口 → verify: `rtk rg "旧计划作废|gui-ui-restore-v2-foundation" docs/GUI_UI_RESTORE_PLAN.md`

### 验收标准

- 明确旧计划作废。
- 明确视觉真源是 `docs/gui-mvp-cyberpunk-mockup.html`。
- 明确 mock 当前已有 `questionCount`、`followupRounds`，题型需要补齐传参路径。
- 不改代码。

### 完成证据

- `rtk rg "app|shell|workspace|problem-card|prep-board|review-panel" docs/gui-mvp-cyberpunk-mockup.html`
- `rtk rg "ShellLayout|Workspace|ReviewPanel|PrepModule|MockModule" gui/src`
- `rtk rg "StartMockInterviewRequest|questionCount|followupRounds|startMockInterview" gui/src src/interview_agent/gui_runtime.py`
- `rtk rg "旧计划作废|gui-ui-restore-v2-foundation" docs/GUI_UI_RESTORE_PLAN.md`

## Task 1：Shell 三栏与视觉系统还原

**Status:** `[x]`
**Tracking ID:** `gui-ui-restore-v2-shell-visual-system`
**Owner:** implementer
**Dependencies:** Task 0
**Write Scope:** `gui/src/app/layout/`、`gui/src/shared/styles/global.css`

### 目标

还原原型的应用级视觉系统：左侧导航、中间工作区、右侧检查面板、深色霓虹背景、玻璃面板、8px 圆角和紧凑间距。

### 任务清单

1. [操作] 阅读 `ShellLayout.tsx`、`Sidebar.tsx`、`Workspace.tsx`、`ReviewPanel.tsx` 调用关系 → verify: 明确三栏由哪些组件组成
2. [操作] 对齐 `.shell-layout` 与原型 `.app` 三栏结构 → verify: 1440x900 下列宽接近 `220px minmax(500px, 1fr) 360px`
3. [操作] 对齐全局色板、面板、边框、阴影、背景网格 → verify: CSS 变量和核心选择器与原型语义一致
4. [操作] 检查导航 active、focus、hover 状态 → verify: 可键盘聚焦，状态不改变布局尺寸
5. [操作] 构建验证 → verify: `cd gui && rtk npm run build`

### 验收标准

- 1440x900 下呈现稳定三栏工作台。
- 左栏、中栏、右栏不重叠。
- 背景、面板、边框、阴影与原型视觉语言一致。
- 不引入新的配色体系或营销页式布局。

### 完成证据

- `rtk npm run build`
- `output/playwright/gui-ui-restore-task1-1440x900.png`
- `output/playwright/gui-ui-restore-task1-1180x900.png`
- `output/playwright/gui-ui-restore-task1-820x900.png`
- DOM 量测: 1440x900 `220px 780px 360px`，`scrollWidth === clientWidth`，`navFocusOutline = solid 2px rgb(70, 246, 255)`；1180x900 无横向滚动；820x900 无横向滚动

## Task 2：面试准备页首屏还原

**Status:** `[x]`
**Tracking ID:** `gui-ui-restore-v2-prep-first-screen`
**Owner:** implementer
**Dependencies:** Task 1
**Write Scope:** `gui/src/modules/prep/PrepModule.tsx`、`gui/src/shared/styles/global.css`

### 目标

准备页首屏对齐原型：顶部操作区、摘要卡、准备板。保留真实业务槽位，不回退成通用卡片网格。

### 任务清单

1. [操作] 阅读 `PrepModule.tsx` 和 `PrepViewModel` → verify: 明确 `简历摘要`、`岗位重点`、`匹配度`、`优势`、`风险`、`追问重点` 来源
2. [操作] 对齐工作区顶部标题、摘要、导入按钮 → verify: `导入简历`、`导入 JD` 在准备页仍可点击
3. [操作] 对齐 `problem-card` 视觉层级 → verify: 标题、tag、摘要文本不重叠
4. [操作] 对齐 `prep-board` 行式预览 → verify: 6 个业务槽位完整显示，非通用卡片网格
5. [操作] 检查禁止项 → verify: 准备页不新增 `生成题目` 按钮
6. [操作] 构建验证 → verify: `cd gui && rtk npm run build`

### 验收标准

- 准备页首屏结构与原型一致。
- 保留 `简历摘要`、`岗位重点`、`匹配度`、`优势`、`风险`、`追问重点`。
- 无按钮重叠、文本溢出、横向滚动。
- 不修改真实业务数据来源。

### 完成证据

- `rtk npm run build`
- `output/playwright/gui-ui-restore-task2-1440x900.png`
- `output/playwright/gui-ui-restore-task2-1180x900.png`
- `output/playwright/gui-ui-restore-task2-820x900.png`
- DOM 量测 1440x900：`scrollWidth === clientWidth`、6 个业务槽位 `简历摘要`/`岗位重点`/`匹配度`/`优势`/`风险`/`追问重点`、`problemCardHeight = 161`、`prepBoardTop = 297`、`prepBoardGap = 12px`、`prepRowPadding = 12px 16px`、`prepRowColumns = 180px 474px`、`hasGenerateQuestionButton = false`
- DOM 量测 1180x900：`scrollWidth === clientWidth`、`prepRows = 6`、`importButtons = 导入简历/导入 JD`、`problemCardHeight = 161`、`prepBoardTop = 297`、`reviewPanelGridColumn = 2`
- DOM 量测 820x900：`scrollWidth === clientWidth`、6 个业务槽位保持可见、`problemCardWidth = 750`、`hasGenerateQuestionButton = false`

## Task 3：右侧检查面板还原

**Status:** `[x]`
**Tracking ID:** `gui-ui-restore-v2-review-panel`
**Owner:** implementer
**Dependencies:** Task 1、Task 2
**Write Scope:** `gui/src/app/layout/ReviewPanel.tsx`、`gui/src/shared/styles/global.css`

### 目标

右侧检查面板恢复原型的信息结构：标题区、分数卡、metrics、suggestions，并保留动态匹配分。

### 任务清单

1. [操作] 阅读 `ReviewPanel.tsx` 各模块分支 → verify: 明确 prep、mock、algorithm 下的右栏显示
2. [操作] 对齐右栏 grid 结构 → verify: 标题、分数卡、metrics、suggestions 顺序稳定
3. [操作] 对齐分数卡视觉 → verify: 大号分数、说明文案、霓虹发光不溢出
4. [操作] 对齐 metrics 区域 → verify: `匹配度`、`追问点`、`材料状态` 正常显示
5. [操作] 对齐 suggestions 区域 → verify: prep 下显示 `补齐项目背景`、`优先准备弱项`、`保留常见问题`
6. [操作] 构建验证 → verify: `cd gui && rtk npm run build`

### 验收标准

- 右栏结构与原型一致。
- prep suggestions 数量为 3。
- 动态匹配分保留。
- 非 prep 模块右栏不被破坏。

### 完成证据

- `rtk npm run build`
- `output/playwright/gui-ui-restore-task3-1440x900.png`
- DOM 量测 1440x900：`title = 准备检查`、`score = 92`、metrics 为 `匹配度`/`追问点`/`材料状态`、动态匹配分 `91 / 100`、suggestions 为 `补齐项目背景`/`优先准备弱项`/`保留常见问题`、`suggestionCount = 3`、`panelWidth = 360`、`scrollWidth === clientWidth`
- 非 prep 模块量测：`title = 模拟面试检查`、metrics 为 `就绪项`/`待检查`/`边界项`、suggestions 为 `主问题`/`逐题回答`/`追问区域`、`suggestionCount = 3`、无横向溢出

## Task 4：响应式与无溢出验收

**Status:** `[x]`
**Tracking ID:** `gui-ui-restore-v2-responsive-qa`
**Owner:** implementer
**Dependencies:** Task 1、Task 2、Task 3
**Write Scope:** `gui/src/shared/styles/global.css`

### 目标

让 GUI 在 1440x900、1180x900、820x900 三个视口下保持原型级布局行为和内容可读性。

### 任务清单

1. [操作] 验证 1440x900 三栏布局 → verify: DOM 量测 `.shell-layout` 列宽和截图
2. [操作] 验证 1180x900 双列布局 → verify: 右栏移动到第二列下方，无横向滚动
3. [操作] 验证 820x900 单列布局 → verify: 左栏、中栏、右栏纵向堆叠
4. [操作] 检查按钮和长文本 → verify: 所有按钮文字不溢出父元素
5. [操作] 检查文档宽度 → verify: `document.documentElement.scrollWidth === document.documentElement.clientWidth`
6. [操作] 构建验证 → verify: `cd gui && rtk npm run build`

### 验收标准

- 三个视口截图均留存。
- 三个视口均无横向滚动。
- 导航、按钮、面板标题、tag、正文无重叠。
- hover、focus、状态切换不导致布局跳动。

### 完成证据

- `rtk npm run build`
- `output/playwright/gui-ui-restore-task4-1440x900.png`
- `output/playwright/gui-ui-restore-task4-1180x900.png`
- `output/playwright/gui-ui-restore-task4-820x900.png`
- DOM 量测 1440x900：`scrollWidth === clientWidth`、`.shell-layout` 列宽 `220px 780px 360px`、左栏/中栏/右栏互不重叠、按钮溢出数 `0`
- DOM 量测 1180x900：`scrollWidth === clientWidth`、`.shell-layout` 双列 `200px 918px`、右栏位于第二列下方，`reviewGridColumn = 2`
- DOM 量测 820x900：`scrollWidth === clientWidth`、`.shell-layout` 单列 `792px`、左栏/中栏/右栏纵向堆叠，`reviewGridColumn = auto`

## Task 5：模拟面试入口重排

**Status:** `[x]`
**Tracking ID:** `gui-ui-restore-v2-mock-entry-layout`
**Owner:** implementer
**Dependencies:** Task 1、Task 4
**Write Scope:** `gui/src/modules/mock/MockModule.tsx`、`gui/src/shared/styles/global.css`

### 目标

把模拟面试入口从通用内容面板重排为与原型工作台一致的操作区：当前题、配置区、作答区、记录区，降低视觉割裂。

### 任务清单

1. [操作] 阅读 `MockModule.tsx` 状态和事件处理 → verify: 明确 `scenario`、`answerDraft`、`viewModel`、`handleStart`、`handleSubmit`、`handleEnd`
2. [操作] 设计 mock 页面布局分区 → verify: 当前题、配置、作答、记录各自边界清楚
3. [操作] 对齐按钮层级 → verify: `开始模拟` 为主按钮，`提交回答`、`结束当前模拟` 为次级按钮
4. [操作] 对齐状态 tag → verify: 题目进度、追问进度、状态在同一状态行内稳定显示
5. [操作] 构建验证 → verify: `cd gui && rtk npm run build`

### 验收标准

- 模拟面试入口与整体 Shell 视觉一致。
- 当前题、配置、作答、记录区分明确。
- 原有开始、提交、结束能力保留。
- 空题集场景仍可触发错误状态。

### 完成证据

- `rtk npm run build`
- `output/playwright/gui-ui-restore-task5-1440x900.png`
- `output/playwright/gui-ui-restore-task5-1180x900.png`
- `output/playwright/gui-ui-restore-task5-820x900.png`
- DOM 量测 1440x900：`scrollWidth === clientWidth`、当前题/配置区/作答区/记录区存在、mock 内唯一主按钮 `开始模拟`、次级按钮 `结束当前模拟`/`提交回答`、状态行 `题目进度 0/0`/`追问进度 0/0`/`状态 未开始`、按钮溢出数 `0`
- DOM 量测 1180x900：`scrollWidth === clientWidth`、mock workbench 双列 `310.312px 551.688px`、可见按钮 `开始模拟`/`结束当前模拟`/`提交回答`、按钮溢出数 `0`
- DOM 量测 820x900：`scrollWidth === clientWidth`、mock workbench 单列 `750px`、当前题/配置区/作答区/记录区宽度均为 `750`、按钮溢出数 `0`
- 交互验证：点击 `开始模拟` 后显示 `第 1 题`；空回答提交显示 `请先输入当前题回答。`；有效回答提交后记录区显示 `已完成轮次` 且输入框清空

## Task 6：模拟面试选择补齐

**Status:** `[x]`
**Tracking ID:** `gui-ui-restore-v2-mock-options`
**Owner:** implementer
**Dependencies:** Task 5
**Write Scope:** `gui/src/modules/mock/MockModule.tsx`、`gui/src/shared/api/mock.ts`、必要 runtime adapter

### 目标

模拟面试开始前提供题目数、题型、追问轮数选择，并将选择项传入启动路径。

### 必备选择项

- 题目数：`3`、`5`、`8`
- 题型：`行为面试`、`项目深挖`、`技术基础`、`系统设计`
- 追问轮数：`0`、`1`、`2`、`3`

### 任务清单

1. [操作] 阅读 `StartMockInterviewRequest` 和 `startMockInterview` 调用方 → verify: 明确当前仅传 `questionCount`、`followupRounds`、`scenario`
2. [操作] 增加题目数状态和控件 → verify: 可选择 `3`、`5`、`8`
3. [操作] 增加题型状态和控件 → verify: 可选择 `行为面试`、`项目深挖`、`技术基础`、`系统设计`
4. [操作] 增加追问轮数状态和控件 → verify: 可选择 `0`、`1`、`2`、`3`
5. [操作] 将题目数传入启动路径 → verify: `startMockInterview` request 使用用户选择的 `questionCount`
6. [操作] 将追问轮数传入启动路径 → verify: `startMockInterview` request 使用用户选择的 `followupRounds`
7. [操作] 将题型传入启动路径 → verify: request 或 runtime adapter 中存在可验证字段，不只停留在 UI 状态
8. [操作] 验证默认值 → verify: 不操作选择项时可以直接开始模拟
9. [操作] 验证边界值 → verify: `0` 追问轮数不生成追问，`8` 题不会导致布局溢出
10. [操作] 构建验证 → verify: `cd gui && rtk npm run build`

### 验收标准

- 开始模拟前可配置题目数。
- 开始模拟前可配置题型。
- 开始模拟前可配置追问轮数。
- 默认配置存在，用户不改选项也能启动。
- 选择值进入模拟面试启动路径。
- 控件在 1440x900、1180x900、820x900 下不重叠。

### 完成证据

- `rtk npm run build`
- `rtk uv run pytest tests/test_gui_runtime.py`
- `output/playwright/gui-ui-restore-task6-1440x900.png`
- `output/playwright/gui-ui-restore-task6-1180x900.png`
- `output/playwright/gui-ui-restore-task6-820x900.png`
- DOM 量测 1440x900：`scrollWidth === clientWidth`、`shellColumns = 220px 780px 360px`、题目数/题型/追问轮数三组选项完整，默认值为 `5`/`行为面试`/`1`，开始模拟后 `题目进度 1/5`
- DOM 量测 1180x900：`scrollWidth === clientWidth`、`shellColumns = 200px 918px`、题目数/题型/追问轮数选择与按钮无重叠
- DOM 量测 820x900：`scrollWidth === clientWidth`、`shellColumns = 792px`、选择控件纵向堆叠，无横向滚动

## Task 7：端到端验收与记录

**Status:** `[x]`
**Tracking ID:** `gui-ui-restore-v2-final-acceptance`
**Owner:** main agent
**Dependencies:** Task 1、Task 2、Task 3、Task 4、Task 5、Task 6
**Write Scope:** `docs/GUI_UI_RESTORE_PLAN.md`、实现完成后 `docs/HISTORY.md`

### 目标

完成构建、三视口截图、模拟面试配置交互和完成证据回写。代码实现完成并验证后，再更新 `docs/HISTORY.md`。

### 任务清单

1. [操作] 运行构建 → verify: `cd gui && rtk npm run build`
2. [操作] 运行 mock 相关 runtime 测试 → verify: `rtk uv run pytest tests/test_gui_runtime.py -k mock_interview`
3. [操作] 启动 GUI 预览 → verify: `cd gui && rtk npm run preview -- --port 4173`
4. [操作] 采集 1440x900 截图 → verify: Playwright 生成截图
5. [操作] 采集 1180x900 截图 → verify: Playwright 生成截图
6. [操作] 采集 820x900 截图 → verify: Playwright 生成截图
7. [操作] 验证准备页还原 → verify: 首屏结构与原型一致
8. [操作] 验证模拟面试配置 → verify: 题目数、题型、追问轮数均能选择并启动
9. [操作] 验证默认配置 → verify: 不改选项可直接开始模拟
10. [操作] 回写完成证据 → verify: `rtk rg "完成证据|gui-ui-restore-v2-final-acceptance" docs/GUI_UI_RESTORE_PLAN.md`
11. [操作] 实现完成后更新历史记录 → verify: `rtk rg "gui-ui-restore-v2" docs/HISTORY.md`

### 验收标准

- `rtk npm run build` 通过。
- `rtk uv run pytest tests/test_gui_runtime.py -k mock_interview` 通过。
- 三个视口截图验收通过。
- 准备页、右栏、模拟面试入口视觉一致。
- 模拟面试题目数、题型、追问轮数选择通过。
- 完成证据已写回本计划。
- 实现完成后，`docs/HISTORY.md` 记录本次交付。

### 完成证据

- `cd gui && rtk npm run build`
- `rtk uv run pytest tests/test_gui_runtime.py -k mock_interview`
- `cd gui && rtk npm run preview -- --port 4173`
- `curl -I http://127.0.0.1:4173`
- `output/playwright/gui-ui-restore-task7-1440x900.png`
- `output/playwright/gui-ui-restore-task7-1180x900.png`
- `output/playwright/gui-ui-restore-task7-820x900.png`
- 1440x900 准备页 DOM 量测：`scrollWidth === clientWidth`、`.shell-layout = 220px 780px 360px`、准备页 6 个业务槽位为 `简历摘要`/`岗位重点`/`匹配度`/`优势`/`风险`/`追问重点`、导入按钮为 `导入简历`/`导入 JD`、`hasGenerateQuestionButton = false`、右栏标题 `准备检查`、分数 `92`、建议为 `补齐项目背景`/`优先准备弱项`/`保留常见问题`、按钮溢出数 `0`。
- 1180x900 DOM 量测：`scrollWidth === clientWidth`、`.shell-layout = 200px 918px`、右栏 `grid-column = 2`、按钮溢出数 `0`。
- 820x900 DOM 量测：`scrollWidth === clientWidth`、`.shell-layout = 792px`、右栏 `grid-column = auto`、6 个准备页业务槽位完整、按钮溢出数 `0`。
- 模拟面试默认配置 DOM 量测：题目数选项 `3`/`5`/`8`、题型选项 `行为面试`/`项目深挖`/`技术基础`/`系统设计`、追问轮数选项 `0`/`1`/`2`/`3`、默认值 `5`/`行为面试`/`1`，默认点击 `开始模拟` 后状态为 `题目进度 1/5`、`追问进度 0/0`、`状态 待回答`。
- 模拟面试改选配置 DOM 量测：选择 `8`/`项目深挖`/`0` 后点击 `开始模拟`，状态为 `题目进度 1/8`、`追问进度 0/0`、`状态 待回答`；提交有效回答后直接进入 `第 2 题`，记录区标题为 `已完成轮次`，回答输入框清空。

## 执行顺序

1. Task 0：基线复核与旧计划冻结
2. Task 1：Shell 三栏与视觉系统还原
3. Task 2：面试准备页首屏还原
4. Task 3：右侧检查面板还原
5. Task 4：响应式与无溢出验收
6. Task 5：模拟面试入口重排
7. Task 6：模拟面试选择补齐
8. Task 7：端到端验收与记录

## 可并行性

- Task 1 必须先做。
- Task 2 与 Task 3 可在 Task 1 后并行。
- Task 4 必须在 Task 2、Task 3 后执行。
- Task 5 必须在 Task 4 后执行。
- Task 6 必须在 Task 5 后执行。
- Task 7 必须最后执行。

## Test Plan

```bash
cd /Users/cynicism/Desktop/ai-agent
rtk rg "旧计划作废|gui-ui-restore-v2|Task 6：模拟面试选择补齐|完成证据" docs/GUI_UI_RESTORE_PLAN.md
```

```bash
cd /Users/cynicism/Desktop/ai-agent/gui
rtk npm run build
```

```bash
cd /Users/cynicism/Desktop/ai-agent
rtk uv run pytest tests/test_gui_runtime.py -k mock_interview
```

```bash
cd /Users/cynicism/Desktop/ai-agent/gui
rtk npm run preview -- --port 4173
```

```bash
rtk /Users/cynicism/.codex/skills/playwright/scripts/playwright_cli.sh open http://127.0.0.1:4173
rtk /Users/cynicism/.codex/skills/playwright/scripts/playwright_cli.sh resize 1440 900
rtk /Users/cynicism/.codex/skills/playwright/scripts/playwright_cli.sh screenshot
rtk /Users/cynicism/.codex/skills/playwright/scripts/playwright_cli.sh resize 1180 900
rtk /Users/cynicism/.codex/skills/playwright/scripts/playwright_cli.sh screenshot
rtk /Users/cynicism/.codex/skills/playwright/scripts/playwright_cli.sh resize 820 900
rtk /Users/cynicism/.codex/skills/playwright/scripts/playwright_cli.sh screenshot
```

## Assumptions

- 当前阶段只落追踪计划，不实现代码。
- 后续实现前必须重新阅读被改函数及其调用方。
- 题型传参路径以后续实现时的 runtime adapter 实际边界为准，但不得只停留在前端静态状态。
- 若 Task 6 需要修改后端 facade 或 runtime 请求结构，必须在进入 Task 6 前重新确认影响范围。
