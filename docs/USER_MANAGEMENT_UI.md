# 用户管理 UI

## 目标

把用户相关 UI 收敛为两层：

- 登录页单独存在
- 登录后进入 Agent 首页，用户管理模块只做用户管理

## 页面结构

### 登录页

- 用户名
- 密码
- 登录按钮

### Agent 首页

- 左侧模块导航
- 中间业务工作区
- 右上角用户信息区：当前用户、在线状态、退出登录

### 用户管理模块

- 新增用户
- 刷新列表
- 用户卡片列表
- 启用 / 禁用

不包含：

- 登录
- 退出登录

## 预览证据

- 登录页截图：`.playwright-cli/page-2026-05-22T14-27-59-322Z.png`
- 登录后首页截图：`.playwright-cli/page-2026-05-22T14-29-51-221Z.png`
- UI 原型文件：`docs/USER_MANAGEMENT_UI_PROTOTYPE.html`

## 关联实现

- `gui/src/app/App.tsx`
- `gui/src/app/layout/ShellLayout.tsx`
- `gui/src/app/layout/Workspace.tsx`
- `gui/src/modules/users/UserModule.tsx`
- `gui/src/shared/styles/global.css`
