import assert from "node:assert/strict";
import { test } from "node:test";
import { snapshotWithDesktopError } from "../.test-build/desktopSnapshot.js";

test("snapshotWithDesktopError preserves previous snapshot and records error message", () => {
  const previousSnapshot = {
    isDesktopShell: true,
    pythonRuntimeRunning: true,
    knowledgeBaseStatus: "ready",
    configPath: "config/interview-agent.toml",
    resumePath: "/tmp/resume.pdf",
    jdPath: "/tmp/jd.md",
    lastError: null,
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
  });
});
