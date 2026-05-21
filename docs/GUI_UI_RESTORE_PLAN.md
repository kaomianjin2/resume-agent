# GUI UI 原型视觉级完全还原计划

## 结论

按“视觉级完全还原”执行：`docs/gui-mvp-cyberpunk-mockup.html` 是唯一视觉真源。允许保留当前真实业务数据和值，但布局、组件形态、间距、字号、面板密度、响应式行为必须对齐原型。

## 追踪规则

### 状态枚举

- `[ ]` 未开始
- `[~]` 进行中
- `[x]` 已完成
- `[!]` 阻塞

### 更新规则

- 每个 Task 开始后，将状态从 `[ ]` 改为 `[~]`。
- 每个 Task 完成后，必须填写“完成证据”。
- 阻塞时改为 `[!]`，并记录具体命令、错误或待决策项。
- 所有 Task 完成后，必须执行最终视觉验收并更新 `docs/HISTORY.md`。
- 本计划只允许修改 GUI UI 还原直接相关文件，不修改后端、接口、配置、数据库、依赖和部署流程。

## 总体边界

- 不修改 `src/interview_agent/`。
- 不修改 `config/interview-agent.toml`。
- 不新增或升级依赖。
- 不修改数据库结构。
- 不修改 Tauri 桌面壳行为。
- 不删除文件。
- 不将真实业务数据改成原型静态假数据。
- 不把准备页改回通用卡片网格。
- 不在面试准备页新增“生成题目”按钮。

## 成功标准

1. 主题完全匹配原型：深色背景、青紫粉霓虹、玻璃面板、网格背景。
2. 三栏布局完全匹配原型：左侧导航、中间工作区、右侧检查面板。
3. 准备页首屏结构完全匹配原型：顶部操作区、`problem-card`、`prep-board`。
4. 右侧检查面板完全匹配原型结构：分数卡、metrics、3 条 suggestions。
5. 1440x900、1180x900、820x900 三个视口截图无结构性差异。
6. `rtk npm run build` 通过。
7. Playwright 截图已留存并完成对照审查。

## 阶段总览

| Task | 状态 | Tracking ID | 依赖 | 影响范围 | 完成证据 |
| --- | --- | --- | --- | --- | --- |
| Task 0 审查基线固化 | `[ ]` | `gui-ui-restore-0-baseline` | 无 | 文档与截图 | 待填写 |
| Task 1 中栏布局还原 | `[ ]` | `gui-ui-restore-1-workspace` | Task 0 | `global.css` | 待填写 |
| Task 2 准备板密度还原 | `[ ]` | `gui-ui-restore-2-prep-board` | Task 1 | `global.css`、`PrepModule.tsx` | 待填写 |
| Task 3 右侧检查面板还原 | `[ ]` | `gui-ui-restore-3-review-panel` | Task 1 | `global.css`、`ReviewPanel.tsx` | 待填写 |
| Task 4 响应式还原 | `[ ]` | `gui-ui-restore-4-responsive` | Task 1-3 | `global.css` | 待填写 |
| Task 5 最终视觉验收与记录 | `[ ]` | `gui-ui-restore-5-final-review` | Task 1-4 | `docs/HISTORY.md` | 待填写 |

## Task 0：审查基线固化

**Status:** `[ ]`
**Tracking ID:** `gui-ui-restore-0-baseline`
**Owner:** main agent
**Dependencies:** none
**Write Scope:** 无代码修改；只读审查
**完成证据:** 待填写
**阻塞原因:** none

### 目标

在修改前固定原型与当前实现的可比对基线，避免后续凭感觉改 UI。

### 任务清单

1. [操作] 读取原型关键结构 → verify: `rtk rg "problem-card|prep-board|review-panel|score-card|suggestions" docs/gui-mvp-cyberpunk-mockup.html`
2. [操作] 读取当前实现关键结构 → verify: `rtk rg "problem-card|prep-board|review-panel|score-card|suggestions" gui/src`
3. [操作] 构建当前 GUI → verify: `cd gui && rtk npm run build`
4. [操作] 生成原型与当前实现截图 → verify: `.playwright-cli/` 下出现两张 1440x900 截图
5. [操作] 记录差异清单 → verify: 差异只聚焦视觉结构，不包含业务数据值

### 验收标准

- 明确当前差异项：中栏布局高度、准备板密度、右侧 suggestions 数量、响应式行为。
- 不改任何源码。
- 不把动态业务值列为必须逐字还原项。

## Task 1：中栏布局还原

**Status:** `[ ]`
**Tracking ID:** `gui-ui-restore-1-workspace`
**Owner:** implementer
**Dependencies:** Task 0
**Write Scope:** `gui/src/shared/styles/global.css`
**完成证据:** 待填写
**阻塞原因:** none

### 目标

让中间工作区重新匹配原型的三段结构：顶部栏、摘要卡、准备板。修复当前 `problem-card` 被拉高的问题。

### 任务清单

1. [操作] 阅读 `Workspace.tsx` 与当前 CSS 调用关系 → verify: 明确 `.workspace`、`.workspace-header`、`.prep-module` 的调用链
2. [操作] 将 `.workspace` 调整为原型节奏 → verify: 计算样式接近 `grid-template-rows: auto auto minmax(420px, 1fr)`
3. [操作] 确保 `.prep-module` 不拉伸 `problem-card` → verify: 1440x900 下 `problem-card` 高度接近原型截图
4. [操作] 保持顶部按钮布局不变 → verify: `导入简历`、`导入 JD` 仍在右上角
5. [操作] 构建验证 → verify: `cd gui && rtk npm run build`

### 验收标准

- `problem-card` 不再占据异常高度。
- `prep-board` 起点与原型接近。
- 页面标题、摘要文案、按钮不重叠。
- 不修改业务数据来源。

## Task 2：准备板密度还原

**Status:** `[ ]`
**Tracking ID:** `gui-ui-restore-2-prep-board`
**Owner:** implementer
**Dependencies:** Task 1
**Write Scope:** `gui/src/shared/styles/global.css`、`gui/src/modules/prep/PrepModule.tsx`
**完成证据:** 待填写
**阻塞原因:** none

### 目标

保留当前 6 行真实业务摘要，但视觉上必须仍是原型的行式预览，不得呈现为通用卡片网格或拥挤表格。

### 任务清单

1. [操作] 对齐 `.prep-board` gap、padding、边框、背景 → verify: 与原型 CSS 值一致
2. [操作] 对齐 `.prep-row` padding 与行高 → verify: 使用原型尺度 `14px 16px`、`line-height: 1.7`
3. [操作] 检查 6 行业务内容的首屏可读性 → verify: 文本不溢出、不重叠、不挤压右侧栏
4. [操作] 保留业务槽位 → verify: 页面仍显示 `简历摘要`、`岗位重点`、`匹配度`、`优势`、`风险`、`追问重点`
5. [操作] 构建验证 → verify: `cd gui && rtk npm run build`

### 验收标准

- 准备板视觉语言与原型一致。
- 保留当前 6 个业务槽位。
- 不出现 `module-grid` 或通用 `content-panel` 卡片网格观感。
- 不新增“生成题目”按钮。

## Task 3：右侧检查面板还原

**Status:** `[ ]`
**Tracking ID:** `gui-ui-restore-3-review-panel`
**Owner:** implementer
**Dependencies:** Task 1
**Write Scope:** `gui/src/shared/styles/global.css`、`gui/src/app/layout/ReviewPanel.tsx`
**完成证据:** 待填写
**阻塞原因:** none

### 目标

右侧检查面板恢复原型结构：顶部标题、分数卡、metrics、3 条 suggestions。

### 任务清单

1. [操作] 将 `.review-panel` grid 结构对齐原型 → verify: `grid-template-rows` 与原型结构一致
2. [操作] 保留分数卡视觉 → verify: 大号 `92`、cyan glow、说明文案正常显示
3. [操作] 保留 metrics 两列结构 → verify: `匹配度`、`追问点`、`材料状态` 显示正常
4. [操作] 补齐第三条 suggestion → verify: 显示 `补齐项目背景`、`优先准备弱项`、`保留常见问题`
5. [操作] 保留动态匹配分 → verify: `prepViewModel.matchSummary.score` 仍作为匹配度来源
6. [操作] 构建验证 → verify: `cd gui && rtk npm run build`

### 验收标准

- 右栏结构与原型一致。
- suggestions 数量为 3。
- 动态匹配分保留。
- 非 prep 模块的 ReviewPanel 行为不被破坏。

## Task 4：响应式还原

**Status:** `[ ]`
**Tracking ID:** `gui-ui-restore-4-responsive`
**Owner:** implementer
**Dependencies:** Task 1、Task 2、Task 3
**Write Scope:** `gui/src/shared/styles/global.css`
**完成证据:** 待填写
**阻塞原因:** none

### 目标

恢复原型在 1180px 与 820px 断点下的布局行为。

### 任务清单

1. [操作] 验证 1440x900 三栏布局 → verify: 左 220px、中间自适应、右 360px
2. [操作] 验证 1180x900 双列布局 → verify: 右栏移动到第二列下方
3. [操作] 验证 820x900 单列布局 → verify: 三栏纵向堆叠，按钮不重叠
4. [操作] 修正断点下 `problem-card`、`review-head`、`workspace-header` 的纵向排列 → verify: 小屏无横向溢出
5. [操作] 构建验证 → verify: `cd gui && rtk npm run build`

### 验收标准

- 1440x900 与原型三栏一致。
- 1180x900 与原型断点一致。
- 820x900 与原型单列一致。
- 无文本重叠、按钮溢出、横向滚动。

## Task 5：最终视觉验收与记录

**Status:** `[ ]`
**Tracking ID:** `gui-ui-restore-5-final-review`
**Owner:** main agent
**Dependencies:** Task 1、Task 2、Task 3、Task 4
**Write Scope:** `docs/HISTORY.md`
**完成证据:** 待填写
**阻塞原因:** none

### 目标

完成最终浏览器验收，确认“视觉级完全还原”达标，并写入历史记录。

### 任务清单

1. [操作] 运行构建 → verify: `cd gui && rtk npm run build`
2. [操作] 启动当前 GUI 静态服务 → verify: `cd gui/dist && rtk python3 -m http.server 4173`
3. [操作] 启动原型静态服务 → verify: `rtk python3 -m http.server 4174`
4. [操作] 采集 1440x900 当前实现截图 → verify: `.playwright-cli/` 生成当前实现截图
5. [操作] 采集 1440x900 原型截图 → verify: `.playwright-cli/` 生成原型截图
6. [操作] 采集 1180x900 和 820x900 当前实现截图 → verify: `.playwright-cli/` 生成响应式截图
7. [操作] 对照关键 DOM 样式 → verify: 三栏、面板、导航、摘要卡、准备板、右栏结构与原型一致
8. [操作] 停止本地服务与浏览器会话 → verify: Playwright close，HTTP server 已退出
9. [操作] 更新 `docs/HISTORY.md` → verify: `rtk rg "GUI UI 原型视觉级完全还原|gui-ui-restore" docs/HISTORY.md`
10. [操作] 查看最终状态 → verify: `rtk git status --short`

### 验收命令

```bash
cd /Users/cynicism/Desktop/ai-agent/gui
rtk npm run build
```

```bash
cd /Users/cynicism/Desktop/ai-agent/gui/dist
rtk python3 -m http.server 4173
```

```bash
cd /Users/cynicism/Desktop/ai-agent
rtk python3 -m http.server 4174
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

```bash
rtk /Users/cynicism/.codex/skills/playwright/scripts/playwright_cli.sh -s=mockup open http://127.0.0.1:4174/docs/gui-mvp-cyberpunk-mockup.html
rtk /Users/cynicism/.codex/skills/playwright/scripts/playwright_cli.sh -s=mockup resize 1440 900
rtk /Users/cynicism/.codex/skills/playwright/scripts/playwright_cli.sh -s=mockup screenshot
```

### 最终验收标准

- `rtk npm run build` 通过。
- 当前实现与原型在 1440x900 下无结构性差异。
- 当前实现与原型在 1180x900、820x900 下断点行为一致。
- 允许差异仅限业务文案和值。
- `docs/HISTORY.md` 记录本次还原、测试命令、截图验收结论。
- 未修改后端、配置、数据库、依赖、部署流程。

## 执行顺序

1. Task 0：审查基线固化
2. Task 1：中栏布局还原
3. Task 2：准备板密度还原
4. Task 3：右侧检查面板还原
5. Task 4：响应式还原
6. Task 5：最终视觉验收与记录

## 可并行性

- Task 1 必须先做。
- Task 2 与 Task 3 可在 Task 1 后并行。
- Task 4 必须在 Task 2、Task 3 后执行。
- Task 5 必须最后执行。

## 风险与控制

- 风险：6 行真实业务内容比原型 3 行更高，导致首屏密度偏离。
  - 控制：只压缩行式预览密度，不删业务槽位。
- 风险：修复 prep 页面时影响 mock 或 algorithm 页面。
  - 控制：CSS 只改通用布局必要项；非 prep 页面完成后至少点击一次模块切换检查。
- 风险：截图对照只看桌面导致移动断点回退。
  - 控制：必须验收 1440、1180、820 三个视口。
- 风险：把视觉级还原误做成像素级数据还原。
  - 控制：保留动态业务值，验收只比较结构、样式、布局、密度。

## 完成后必须更新

- `docs/HISTORY.md`
  - 记录标题：`2026-05-21 - GUI UI 原型视觉级完全还原`
  - 记录 Tracking ID：`gui-ui-restore`
  - 记录测试命令：`rtk npm run build`、Playwright 三视口截图
  - 记录审查结论：视觉级完全还原通过，业务数据值保留动态来源
