import assert from "node:assert/strict";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { snapshotWithDesktopError } from "../.test-build/shared/desktop/desktopSnapshot.js";
import {
  DEFAULT_ACTIVE_MODULE_ID,
  getVisibleModuleViewModels,
  moduleViewModels,
} from "../.test-build/app/fixtureData.js";
import { AlgorithmModule, buildHighlightedCode } from "../.test-build/modules/algorithm/AlgorithmModule.js";
import { UserModule } from "../.test-build/modules/users/UserModule.js";

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

test("user module keeps user-management scope and renders card actions", () => {
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
