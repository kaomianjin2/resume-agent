import assert from "node:assert/strict";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { snapshotWithDesktopError } from "../.test-build/shared/desktop/desktopSnapshot.js";
import { LoginPasswordInput } from "../.test-build/app/LoginPasswordInput.js";
import { ReviewPanel } from "../.test-build/app/layout/ReviewPanel.js";
import {
  DEFAULT_ACTIVE_MODULE_ID,
  getVisibleModuleViewModels,
  moduleViewModels,
} from "../.test-build/app/fixtureData.js";
import { AlgorithmModule, buildHighlightedCode } from "../.test-build/modules/algorithm/AlgorithmModule.js";
import { MockModule } from "../.test-build/modules/mock/MockModule.js";
import { PrepModule } from "../.test-build/modules/prep/PrepModule.js";
import { UserModule } from "../.test-build/modules/users/UserModule.js";
import { failedPrepViewModel, missingInputsPrepViewModel, prepViewModel } from "../.test-build/shared/api/prep.js";

test("snapshotWithDesktopError preserves previous snapshot and records error message", () => {
  const previousSnapshot = {
    isDesktopShell: true,
    pythonRuntimeRunning: true,
    knowledgeBaseStatus: "ready",
    configPath: "config/interview-agent.toml",
    resumePath: "/tmp/resume.pdf",
    jdPath: "/tmp/jd.md",
    lastError: null,
    currentUser: "alice",
    currentUserRole: "admin",
  };

  const snapshot = snapshotWithDesktopError(new Error("invoke failed"), previousSnapshot, true);

  assert.deepEqual(snapshot, {
    ...previousSnapshot,
    lastError: "invoke failed",
  });
});

test("snapshotWithDesktopError creates visible fallback state when no snapshot exists", () => {
  const snapshot = snapshotWithDesktopError("dialog failed", null, true);

  assert.deepEqual(snapshot, {
    isDesktopShell: true,
    pythonRuntimeRunning: false,
    knowledgeBaseStatus: "unavailable",
    configPath: "config/interview-agent.toml",
    resumePath: null,
    jdPath: null,
    lastError: "dialog failed",
    currentUser: null,
    currentUserRole: null,
  });
});

test("algorithm module renders editable textarea for code input", () => {
  const markup = renderToStaticMarkup(React.createElement(AlgorithmModule));

  assert.match(markup, /id="algorithm-editor"/);
  assert.match(markup, /class="code-editor-input"/);
});

test("buildHighlightedCode marks keywords and numbers with token classes", () => {
  const highlightedNodes = buildHighlightedCode("def solve(nums):\n    return 1", "python");
  const markup = renderToStaticMarkup(React.createElement("code", null, highlightedNodes));

  assert.match(markup, /class="token-keyword"[^>]*>def</);
  assert.match(markup, /class="token-keyword"[^>]*>return</);
  assert.match(markup, /class="token-number"[^>]*>1</);
});

test("prep module hides prepared data until resume is imported", () => {
  const markup = renderToStaticMarkup(React.createElement(PrepModule, {
    viewModel: missingInputsPrepViewModel(["resume_text"]),
  }));

  assert.match(markup, /简历摘要/);
  assert.match(markup, /岗位重点/);
  assert.match(markup, /匹配度/);
  assert.match(markup, /优势/);
  assert.match(markup, /风险/);
  assert.match(markup, /追问重点/);
  assert.match(markup, /缺少 <strong>简历<\/strong>，导入后展示候选人摘要。/);
  assert.doesNotMatch(markup, /Alice/);
  assert.doesNotMatch(markup, /匹配度 <strong>91 \/ 100<\/strong>/);
});

test("prep module renders prepared data after resume and JD are imported", () => {
  const markup = renderToStaticMarkup(React.createElement(PrepModule, {
    viewModel: prepViewModel,
  }));

  assert.match(markup, /Alice/);
  assert.match(markup, /匹配度 <strong>91 \/ 100<\/strong>/);
});

test("prep module renders parsing progress while materials are being prepared", () => {
  const markup = renderToStaticMarkup(React.createElement(PrepModule, {
    viewModel: missingInputsPrepViewModel([]),
    isLoading: true,
  }));

  assert.match(markup, /正在解析导入材料/);
  assert.match(markup, /解析进程/);
});

test("prep module renders failed preparation state", () => {
  const markup = renderToStaticMarkup(React.createElement(PrepModule, {
    viewModel: failedPrepViewModel("JD 文件无法解析"),
  }));

  assert.match(markup, /材料解析失败/);
  assert.match(markup, /JD 文件无法解析/);
});

test("prep module renders resume-only prepared data without empty JD copy", () => {
  const markup = renderToStaticMarkup(React.createElement(PrepModule, {
    viewModel: {
      ...prepViewModel,
      jdSummary: { role: "", focus: [] },
      matchSummary: {
        score: "未评分",
        strengths: [],
        risks: [],
        followUpFocus: [],
      },
    },
  }));

  assert.match(markup, /Alice/);
  assert.doesNotMatch(markup, /岗位关注 <strong><\/strong>/);
  assert.match(markup, /JD 解析结果为空，请重新导入可解析的 JD。/);
  assert.match(markup, /补齐简历和 JD 后生成整体匹配度。/);
  assert.doesNotMatch(markup, /未评分 \/ 100/);
});

test("prep module does not render punctuation-only resume summaries", () => {
  const markup = renderToStaticMarkup(React.createElement(PrepModule, {
    viewModel: {
      ...prepViewModel,
      resumeSummary: {
        name: "",
        headline: "",
        highlights: [],
      },
    },
  }));

  assert.doesNotMatch(markup, /：；。/);
  assert.match(markup, /简历解析结果为空，请重新导入可解析的简历。/);
});

test("review panel derives prep metrics from current view model", () => {
  const activeModule = moduleViewModels.find((moduleViewModel) => moduleViewModel.id === "prep");
  const markup = renderToStaticMarkup(React.createElement(ReviewPanel, {
    activeModule,
    prepViewModel: {
      ...prepViewModel,
      matchSummary: {
        score: "未评分",
        strengths: [],
        risks: [],
        followUpFocus: [],
      },
    },
  }));

  assert.match(markup, /准备完整度<\/div><div class="score">67<\/div>/);
  assert.match(markup, /匹配度<\/div><div class="metric-value">未评分<\/div>/);
  assert.match(markup, /追问点<\/div><div class="metric-value">0 个<\/div>/);
  assert.match(markup, /材料状态<\/div><div class="metric-value">解析中<\/div>/);
});

test("mock module blocks start until prepared interview materials exist", () => {
  const markup = renderToStaticMarkup(React.createElement(MockModule, {
    materialsReady: false,
  }));

  assert.match(markup, /请先导入简历，并完成面试准备。/);
  assert.match(markup, /disabled="">开始模拟<\/button>/);
});

test("login form hides password by default and renders visibility toggle", () => {
  const markup = renderToStaticMarkup(React.createElement(LoginPasswordInput, {
    value: "secret",
    visible: false,
    onChange: () => {},
    onVisibleChange: () => {},
  }));

  assert.match(markup, /type="password"/);
  assert.match(markup, /aria-label="显示密码"/);
  assert.match(markup, />显示<\/button>/);
});

test("user module keeps user-management scope and renders management actions", () => {
  const markup = renderToStaticMarkup(React.createElement(UserModule, {
    users: [
      { userId: "001", username: "alice", role: "admin", status: "enabled" },
      { userId: "002", username: "bob", role: "member", status: "disabled" },
    ],
    newUsername: "new_user",
    newPassword: "secret",
    newRole: "member",
    errorMessage: "用户名不能为空",
    onNewUsernameChange: () => {},
    onNewPasswordChange: () => {},
    onNewRoleChange: () => {},
    onCreateUser: () => {},
    onRefresh: () => {},
    onToggleStatus: () => {},
  }));

  assert.match(markup, /新增用户/);
  assert.match(markup, /刷新列表/);
  assert.match(markup, /alice/);
  assert.match(markup, /bob/);
  assert.match(markup, /禁用/);
  assert.match(markup, /启用/);
  assert.match(markup, /用户名不能为空/);
  assert.doesNotMatch(markup, /退出登录/);
  assert.doesNotMatch(markup, /登录并进入首页/);
});

test("module navigation starts with prep and shows user management only for admins", () => {
  assert.equal(DEFAULT_ACTIVE_MODULE_ID, "prep");
  assert.deepEqual(moduleViewModels.map((moduleViewModel) => moduleViewModel.id), [
    "prep",
    "mock",
    "algorithm",
    "users",
  ]);
  assert.deepEqual(getVisibleModuleViewModels("admin").map((moduleViewModel) => moduleViewModel.id), [
    "prep",
    "mock",
    "algorithm",
    "users",
  ]);
  assert.deepEqual(getVisibleModuleViewModels("member").map((moduleViewModel) => moduleViewModel.id), [
    "prep",
    "mock",
    "algorithm",
  ]);
});
