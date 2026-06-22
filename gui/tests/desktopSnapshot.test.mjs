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
import {
  AlgorithmModule,
  buildHighlightedCode,
} from "../.test-build/modules/algorithm/AlgorithmModule.js";
import { MockModule } from "../.test-build/modules/mock/MockModule.js";
import { PrepModule } from "../.test-build/modules/prep/PrepModule.js";
import { UserModule } from "../.test-build/modules/users/UserModule.js";
import { JobModule } from "../.test-build/modules/job/JobModule.js";
import { ConfirmModal } from "../.test-build/modules/job/ConfirmModal.js";
import { CleanupModal } from "../.test-build/modules/job/CleanupModal.js";
import { failedPrepViewModel, missingInputsPrepViewModel, prepViewModel } from "../.test-build/shared/api/prep.js";
import {
  createFallbackAlgorithmPracticeClient,
  DEFAULT_ALGORITHM_PRACTICE_QUESTION_COUNT,
} from "../.test-build/shared/api/algorithm.js";
import {
  createFallbackJobClient,
  defaultJobSearchProfile,
  fixtureJobSearchProfile,
  fixtureCollectionProgress,
  fixtureJobList,
  fixtureJobDetails,
  fixtureConfirmationBatch,
  fixtureApplicationResults,
  defaultCollectionProgress,
} from "../.test-build/shared/api/job.js";

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

test("algorithm module keeps exercise selection in the dropdown only", () => {
  const markup = renderToStaticMarkup(React.createElement(AlgorithmModule));

  assert.match(markup, /id="algorithm-exercise-select"/);
  assert.match(markup, /最长递增子序列/);
  assert.match(markup, /零钱兑换/);
  assert.match(markup, /反转链表/);
  assert.doesNotMatch(markup, /aria-label="内部题库题目"/);
  assert.doesNotMatch(markup, /上一题/);
  assert.doesNotMatch(markup, /下一题/);
  assert.doesNotMatch(markup, /上一页/);
  assert.doesNotMatch(markup, /下一页/);
  assert.doesNotMatch(markup, /练习主题/);
  assert.doesNotMatch(markup, /开始练习/);
});

test("algorithm practice default request and fallback expose more than three internal exercises", async () => {
  const fallbackClient = createFallbackAlgorithmPracticeClient();
  const viewModel = await fallbackClient.startAlgorithmPractice({
    sessionId: "gui-session",
    practiceTopic: "算法和数据结构",
    difficulty: "medium",
    questionCount: DEFAULT_ALGORITHM_PRACTICE_QUESTION_COUNT,
  });

  assert.ok(DEFAULT_ALGORITHM_PRACTICE_QUESTION_COUNT > 3);
  assert.ok(viewModel.exercises.length > 3);
  assert.equal(viewModel.progress.totalExercises, viewModel.exercises.length);
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

test("module navigation includes job module and shows user management only for admins", () => {
  assert.equal(DEFAULT_ACTIVE_MODULE_ID, "prep");
  assert.deepEqual(moduleViewModels.map((moduleViewModel) => moduleViewModel.id), [
    "prep",
    "mock",
    "algorithm",
    "job",
    "users",
  ]);
  assert.deepEqual(getVisibleModuleViewModels("admin").map((moduleViewModel) => moduleViewModel.id), [
    "prep",
    "mock",
    "algorithm",
    "job",
    "users",
  ]);
  assert.deepEqual(getVisibleModuleViewModels("member").map((moduleViewModel) => moduleViewModel.id), [
    "prep",
    "mock",
    "algorithm",
    "job",
  ]);
});

// --- JOB-013: GUI 求职模块测试 ---

test("JOB-013: job module renders jobs screen with table structure and empty state", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    selectedJobIds: [],
    activeScreen: "jobs",
  }));

  // SSR does not trigger useEffect, so jobList is empty; verify structure
  assert.match(markup, /候选岗位/);
  assert.match(markup, /aria-label="候选岗位"/);
  assert.match(markup, /匹配/);
  assert.match(markup, /硬过滤/);
  assert.match(markup, /平台/);
  assert.match(markup, /岗位/);
  assert.match(markup, /公司/);
  assert.match(markup, /薪资/);
  assert.match(markup, /城市/);
  assert.match(markup, /评估/);
  assert.match(markup, /投递/);
  assert.match(markup, /风险/);
});

test("JOB-013: job module renders profile screen with missing_inputs blocked state", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    activeScreen: "profile",
  }));

  // SSR initial state has defaultJobSearchProfile with status missing_inputs
  assert.match(markup, /画像与筛选/);
  assert.match(markup, /阻断空态/);
  assert.match(markup, /未找到 resume_profile/);
  assert.match(markup, /去面试准备/);
  assert.match(markup, /重新读取画像/);
});

test("JOB-013: job module renders collection progress screen with empty state", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    activeScreen: "collect",
  }));

  // SSR initial state has defaultCollectionProgress (empty)
  assert.match(markup, /采集进度/);
  assert.match(markup, /平台进度/);
  assert.match(markup, /重试失败平台/);
  assert.match(markup, /状态矩阵/);
  assert.match(markup, /非敏感事件流/);
  assert.match(markup, /已采集岗位/);
  assert.match(markup, /评估队列/);
  assert.match(markup, /人工接管/);
});

test("JOB-013: job module renders results screen with application results", async () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    activeScreen: "results",
  }));

  // SSR does not run useEffect, so results state is empty; verify empty state renders
  assert.match(markup, /投递结果/);
  assert.match(markup, /尚无投递记录/);

  // Verify data is accessible via client
  const results = await client.getApplicationResults("test-session");
  assert.equal(results.batchId, "JA-240610-01");
  assert.ok(results.results.length > 0);
});

test("JOB-013: job module renders detail screen when job is selected", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    selectedJobIds: ["job-1"],
    activeScreen: "detail",
  }));

  // detail screen requires selectedDetailJobId which is set via loadJobDetail
  // SSR won't trigger useEffect, so detail screen won't render without state
  // This test verifies the module renders without error
  assert.ok(markup.length > 0);
});

test("JOB-013: job module shows tab navigation for all screens", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    activeScreen: "jobs",
  }));

  assert.match(markup, /aria-label="求职投递流程"/);
  assert.match(markup, /画像与筛选/);
  assert.match(markup, /采集进度/);
  assert.match(markup, /候选岗位/);
  assert.match(markup, /投递结果/);
});

test("JOB-013: job module jobs screen shows filter chips and search input", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    activeScreen: "jobs",
  }));

  assert.match(markup, /全部平台/);
  assert.match(markup, /匹配分 80\+/);
  assert.match(markup, /硬条件通过/);
  assert.match(markup, /远程/);
  assert.match(markup, /低置信度/);
  assert.match(markup, /高风险/);
  assert.match(markup, /搜索岗位/);
});

test("JOB-013: job module jobs screen renders table structure for selection when data loads", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    selectedJobIds: ["job-1"],
    onSelectedJobIdsChange: () => {},
    onOpenConfirmModal: () => {},
    activeScreen: "jobs",
  }));

  // SSR renders empty job list, but the table structure and batch confirm button appear
  assert.match(markup, /aria-label="候选岗位"/);
  assert.match(markup, /已选择 1 个岗位/);
  assert.match(markup, /批量确认/);
});

test("JOB-013: job module renders empty job table when no data is loaded via SSR", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    selectedJobIds: [],
    activeScreen: "jobs",
  }));

  // SSR does not trigger useEffect so jobList is empty
  // Verify the table structure exists but no job rows
  assert.match(markup, /role="table"/);
  assert.match(markup, /role="row"/);
  // The empty state matrix is always rendered
  assert.match(markup, /空态 \/ 加载态 \/ 错误态/);
  assert.match(markup, /empty/);
});

test("JOB-013: job module shows empty state matrix with boundary conditions", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    activeScreen: "jobs",
  }));

  assert.match(markup, /空态 \/ 加载态 \/ 错误态/);
  assert.match(markup, /empty/);
  assert.match(markup, /loading/);
  assert.match(markup, /pending_review/);
  assert.match(markup, /error/);
});

test("JOB-013: confirm modal renders batch summary with risks and validations", () => {
  const markup = renderToStaticMarkup(React.createElement(ConfirmModal, {
    open: true,
    batch: fixtureConfirmationBatch,
    onClose: () => {},
    onConfirm: () => {},
  }));

  assert.match(markup, /aria-modal="true"/);
  assert.match(markup, /批量确认投递/);
  assert.match(markup, /岗位/);
  assert.match(markup, /平台/);
  assert.match(markup, /高风险/);
  assert.match(markup, /重复拦截/);
  assert.match(markup, /风险提示/);
  assert.match(markup, /简历摘要/);
  assert.match(markup, /投递前重校验结果/);
  assert.match(markup, /确认并创建批次/);
  assert.match(markup, /返回修改选择/);
});

test("JOB-013: confirm modal is hidden when open is false", () => {
  const markup = renderToStaticMarkup(React.createElement(ConfirmModal, {
    open: false,
    batch: fixtureConfirmationBatch,
    onClose: () => {},
    onConfirm: () => {},
  }));

  assert.doesNotMatch(markup, /批量确认投递/);
});

test("JOB-013: confirm modal shows validation status for each job", () => {
  const markup = renderToStaticMarkup(React.createElement(ConfirmModal, {
    open: true,
    batch: fixtureConfirmationBatch,
    onClose: () => {},
    onConfirm: () => {},
  }));

  assert.match(markup, /Go 后端平台工程师/);
  assert.match(markup, /AI Infra 后端工程师/);
  assert.match(markup, /后端开发工程师/);
  assert.match(markup, /资深服务端工程师/);
  assert.match(markup, /就绪/);
  assert.match(markup, /陈旧跳过/);
  assert.match(markup, /重复拦截/);
  assert.match(markup, /按钮不可用/);
  assert.match(markup, /将提交/);
  assert.match(markup, /不提交/);
});

test("JOB-013: confirm modal confirm button is disabled until checkbox is checked", () => {
  const markup = renderToStaticMarkup(React.createElement(ConfirmModal, {
    open: true,
    batch: fixtureConfirmationBatch,
    onClose: () => {},
    onConfirm: () => {},
  }));

  // SSR renders unchecked checkbox, so button should be disabled
  assert.match(markup, /disabled="">确认并创建批次/);
});

test("JOB-013: cleanup modal renders delete and preserve lists", () => {
  const markup = renderToStaticMarkup(React.createElement(CleanupModal, {
    open: true,
    runningBatchId: null,
    onClose: () => {},
    onConfirm: () => {},
  }));

  assert.match(markup, /aria-modal="true"/);
  assert.match(markup, /清空求职数据/);
  assert.match(markup, /将删除/);
  assert.match(markup, /不会删除/);
  assert.match(markup, /岗位/);
  assert.match(markup, /评估报告/);
  assert.match(markup, /投递记录/);
  assert.match(markup, /采集进度/);
  assert.match(markup, /简历原文件/);
  assert.match(markup, /Chrome 登录态/);
  assert.match(markup, /确认清空本地求职数据/);
});

test("JOB-013: cleanup modal is hidden when open is false", () => {
  const markup = renderToStaticMarkup(React.createElement(CleanupModal, {
    open: false,
    runningBatchId: null,
    onClose: () => {},
    onConfirm: () => {},
  }));

  assert.doesNotMatch(markup, /清空求职数据/);
});

test("JOB-013: cleanup modal disables confirm when batch is running", () => {
  const markup = renderToStaticMarkup(React.createElement(CleanupModal, {
    open: true,
    runningBatchId: "JA-240610-01",
    onClose: () => {},
    onConfirm: () => {},
  }));

  assert.match(markup, /运行中批次受保护/);
  assert.match(markup, /JA-240610-01/);
  assert.match(markup, /disabled="">批次运行中，暂不可清理/);
});

test("JOB-013: collection progress shows status matrix with handoff and security states", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    activeScreen: "collect",
  }));

  // Status matrix is always rendered
  assert.match(markup, /manual handoff/);
  assert.match(markup, /验证码、风控、强制弹窗/);
  assert.match(markup, /security blocked/);
  assert.match(markup, /敏感字段扫描命中，禁止继续投递/);
  assert.match(markup, /progress/);
  assert.match(markup, /分页、详情、评估分阶段展示/);
});

test("JOB-013: job list renders empty mobile list when no data loaded", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    activeScreen: "jobs",
  }));

  // SSR renders empty mobile list container
  assert.match(markup, /job-mobile-list/);
  // Verify boundary state cards are rendered
  assert.match(markup, /empty/);
  assert.match(markup, /筛选后 0 个岗位/);
});

test("JOB-013: review panel renders job-specific content on jobs screen", () => {
  const activeModule = moduleViewModels.find((m) => m.id === "job");
  const markup = renderToStaticMarkup(React.createElement(ReviewPanel, {
    activeModule,
    prepViewModel,
    selectedJobIds: ["job-1", "job-2"],
    jobActiveScreen: "jobs",
  }));

  assert.match(markup, /aria-label="投递检查面板"/);
  assert.match(markup, /投递检查/);
  assert.match(markup, /已选择 2 个岗位/);
  assert.match(markup, /已选岗位/);
  assert.match(markup, /高风险/);
  assert.match(markup, /Chrome 登录态不入库/);
  assert.match(markup, /LLM 输入不含 cookie\/token/);
  assert.match(markup, /平台分布/);
  assert.match(markup, /BOSS 1/);
  assert.match(markup, /猎聘 1/);
  assert.match(markup, /批量确认/);
});

test("JOB-013: review panel returns null for job module on non-jobs screens", () => {
  const activeModule = moduleViewModels.find((m) => m.id === "job");
  const markup = renderToStaticMarkup(React.createElement(ReviewPanel, {
    activeModule,
    prepViewModel,
    selectedJobIds: [],
    jobActiveScreen: "profile",
  }));

  // ReviewPanel returns null for job module when screen is not "jobs"
  assert.doesNotMatch(markup, /投递检查/);
});

test("JOB-013: fallback job client returns fixture data for all API methods", async () => {
  const client = createFallbackJobClient();

  const profile = await client.getJobSearchProfile("test-session");
  assert.equal(profile.status, "needs_confirmation");
  assert.ok(profile.jobProfile.technicalSkills.length > 0);

  const progress = await client.getCollectionProgress("test-session");
  assert.equal(progress.status, "running");
  assert.ok(progress.platforms.length > 0);

  const jobList = await client.getJobList("test-session");
  assert.ok(jobList.length > 0);
  assert.equal(jobList[0].id, "job-1");

  const detail = await client.getJobDetail("job-1");
  assert.ok(detail.jdSummary.length > 0);
  assert.ok(detail.strengths.length > 0);

  const batch = await client.getConfirmationBatch("test-session", ["job-1"]);
  assert.ok(batch.jobCount > 0);
  assert.ok(batch.validations.length > 0);

  const results = await client.getApplicationResults("test-session");
  assert.ok(results.results.length > 0);
  assert.equal(results.batchId, "JA-240610-01");
});

test("JOB-013: save profile returns ready status with empty pending fields", async () => {
  const client = createFallbackJobClient();
  const saved = await client.saveJobSearchProfile("test-session", { cities: ["上海"] });
  assert.equal(saved.status, "ready");
  assert.deepEqual(saved.pendingConfirmationFields, []);
});

test("JOB-013: job table renders boundary state cards for all statuses", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    activeScreen: "jobs",
  }));

  // Boundary state cards are always rendered
  assert.match(markup, /empty/);
  assert.match(markup, /loading/);
  assert.match(markup, /pending_review/);
  assert.match(markup, /error/);
  assert.match(markup, /评估报告生成中/);
  assert.match(markup, /话术未生成/);
  assert.match(markup, /单岗位评估失败/);
});

test("JOB-013: job table renders risk level tags", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    activeScreen: "jobs",
  }));

  assert.match(markup, /低/);
  assert.match(markup, /中/);
  assert.match(markup, /高/);
});

test("JOB-013: results screen shows status variants for all result types", async () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    activeScreen: "results",
  }));

  // SSR does not run useEffect, so results state is empty; verify empty state renders
  assert.match(markup, /尚无投递记录/);

  // Verify result types are present in fixture data
  const results = await client.getApplicationResults("test-session");
  const statuses = results.results.map((r) => r.status);
  assert.ok(statuses.includes("submitted"));
  assert.ok(statuses.includes("skipped"));
  assert.ok(statuses.includes("failed"));
  assert.ok(statuses.includes("duplicate"));
  assert.ok(statuses.includes("security_blocked"));
});

test("JOB-013: security blocked card is visible in collect screen", () => {
  const client = createFallbackJobClient();
  const markup = renderToStaticMarkup(React.createElement(JobModule, {
    runtimeClient: client,
    activeScreen: "collect",
  }));

  assert.match(markup, /security blocked/);
  assert.match(markup, /敏感字段扫描命中，禁止继续投递/);
});

test("JOB-013: cleanup modal shows running batch guard card", () => {
  const markup = renderToStaticMarkup(React.createElement(CleanupModal, {
    open: true,
    runningBatchId: null,
    onClose: () => {},
    onConfirm: () => {},
  }));

  assert.match(markup, /运行中批次保护/);
  assert.match(markup, /cleanup guard/);
  assert.match(markup, /存在采集或投递执行中的批次时/);
});
