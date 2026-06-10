export type JobSearchProfileStatus = "ready" | "needs_confirmation" | "missing_inputs";

export type JobSearchProfile = {
  sessionId: string;
  status: JobSearchProfileStatus;
  jobProfile: {
    candidateName: string;
    targetRoles: string[];
    headline: string;
    yearsOfExperience: number | string | null;
    educationLevel: string | null;
    technicalSkills: string[];
    projectKeywords: string[];
  };
  defaultSearchKeywords: string[];
  hardFilters: {
    cities: string[];
    remotePolicy: string | null;
    salaryMin: string | number | null;
    salaryMax: string | number | null;
    levels: string[];
    experienceYearsMin: number | string | null;
    experienceYearsMax: number | string | null;
    education: string | null;
    companyBlacklist: string[];
    companyWhitelist: string[];
  };
  rankingPreferences: {
    industries: string[];
    companySizes: string[];
    fundingStages: string[];
    technicalSkills: string[];
    benefits: string[];
    publishedWithinDays: number | null;
  };
  pendingConfirmationFields: string[];
};

export type CollectionPlatformStatus =
  | "idle"
  | "started"
  | "page_collected"
  | "detail_collected"
  | "completed"
  | "failed"
  | "retrying"
  | "manual_handoff"
  | "rate_limited"
  | "login_expired"
  | "page_changed";

export type CollectionPlatform = {
  platform: string;
  status: CollectionPlatformStatus;
  phase: string;
  collectedCount: number;
  totalCount: number;
  retryCount: number;
  failureReason: string | null;
};

export type CollectionSummary = {
  platformCount: number;
  completedPlatformCount: number;
  failedPlatformCount: number;
  collectedJobCount: number;
};

export type CollectionProgress = {
  status: "idle" | "running" | "completed" | "partial" | "failed";
  summary: CollectionSummary;
  platforms: CollectionPlatform[];
  events: CollectionEvent[];
};

export type CollectionEvent = {
  time: string;
  platform: string;
  message: string;
  status: "running" | "done" | "handoff" | "security_blocked" | "error";
};

export type JobListItem = {
  id: string;
  platform: string;
  platformJobId: string;
  title: string;
  companyName: string;
  location: string;
  remotePolicy: string | null;
  salaryRange: string;
  level: string | null;
  experienceRequirement: string | null;
  educationRequirement: string | null;
  industry: string | null;
  companySize: string | null;
  fundingStage: string | null;
  techStack: string[];
  benefits: string[];
  publishedAt: string | null;
  detailUrl: string | null;
  jdText: string;
  collectedAt: string;
  fieldConfidence: Record<string, "high" | "low" | "missing">;
  score: number;
  hardFilterStatus: "pass" | "edge" | "fail";
  evaluationStatus: "done" | "pending" | "failed";
  applicationStatus: "available" | "pending_review" | "stale" | "submitted" | "failed" | "skipped" | "duplicate";
  riskLevel: "low" | "medium" | "high";
  excludeReason: string | null;
};

export type JobDetail = {
  jdSummary: string;
  strengths: { title: string; detail: string }[];
  risks: { title: string; detail: string }[];
  missingInformation: string[];
  resumeAdvice: { title: string; detail: string }[];
  applicationMessage: string;
};

export type ApplicationResultStatus = "submitted" | "failed" | "skipped" | "duplicate" | "stale-skipped" | "button-disabled" | "security_blocked";

export type ApplicationResult = {
  jobRef: string;
  platform: string;
  companyName: string;
  status: ApplicationResultStatus;
  submittedAt: string | null;
  failureReason: string | null;
  platformMessage: string | null;
  duplicateDetected: boolean;
};

export type ConfirmationValidation = {
  jobRef: string;
  status: "ready" | "stale-skipped" | "duplicate-blocked" | "button-disabled";
  reason: string;
  willSubmit: boolean;
};

export type ConfirmationBatch = {
  batchId: string;
  jobCount: number;
  platformCount: number;
  highRiskCount: number;
  duplicateCount: number;
  platforms: { name: string; count: number }[];
  risks: { title: string; detail: string }[];
  resumeSummary: string;
  validations: ConfirmationValidation[];
};

export type JobRuntimeClient = {
  getJobSearchProfile: (sessionId: string) => Promise<JobSearchProfile>;
  saveJobSearchProfile: (sessionId: string, overrides: Record<string, unknown>) => Promise<JobSearchProfile>;
  getCollectionProgress: (sessionId: string) => Promise<CollectionProgress>;
  getJobList: (sessionId: string) => Promise<JobListItem[]>;
  getJobDetail: (jobId: string) => Promise<JobDetail>;
  getConfirmationBatch: (sessionId: string, selectedJobIds: string[]) => Promise<ConfirmationBatch>;
  getApplicationResults: (sessionId: string) => Promise<{ batchId: string; submittedAt: string; results: ApplicationResult[] }>;
  submitBatch: (sessionId: string, confirmed: boolean) => Promise<void>;
  clearJobData: (sessionId: string) => Promise<void>;
};

export const defaultJobSearchProfile: JobSearchProfile = {
  sessionId: "",
  status: "missing_inputs",
  jobProfile: {
    candidateName: "未命名候选人",
    targetRoles: [],
    headline: "",
    yearsOfExperience: null,
    educationLevel: null,
    technicalSkills: [],
    projectKeywords: [],
  },
  defaultSearchKeywords: [],
  hardFilters: {
    cities: [],
    remotePolicy: null,
    salaryMin: null,
    salaryMax: null,
    levels: [],
    experienceYearsMin: null,
    experienceYearsMax: null,
    education: null,
    companyBlacklist: [],
    companyWhitelist: [],
  },
  rankingPreferences: {
    industries: [],
    companySizes: [],
    fundingStages: [],
    technicalSkills: [],
    benefits: [],
    publishedWithinDays: null,
  },
  pendingConfirmationFields: ["resume_profile"],
};

export const defaultCollectionProgress: CollectionProgress = {
  status: "idle",
  summary: { platformCount: 0, completedPlatformCount: 0, failedPlatformCount: 0, collectedJobCount: 0 },
  platforms: [],
  events: [],
};

export const fixtureJobSearchProfile: JobSearchProfile = {
  sessionId: "gui-mock-session",
  status: "needs_confirmation",
  jobProfile: {
    candidateName: "候选人",
    targetRoles: ["后端工程师", "平台工程师"],
    headline: "后端 / Go / 平台工程，6 年经验",
    yearsOfExperience: 6,
    educationLevel: "本科及以上",
    technicalSkills: ["Go", "Kubernetes", "分布式系统", "gRPC", "消息队列"],
    projectKeywords: ["服务治理", "任务调度", "可观测性建设", "链路追踪"],
  },
  defaultSearchKeywords: ["后端工程师 Go", "平台工程师 Go"],
  hardFilters: {
    cities: ["上海", "杭州", "远程"],
    remotePolicy: null,
    salaryMin: "35k",
    salaryMax: null,
    levels: [],
    experienceYearsMin: 5,
    experienceYearsMax: 8,
    education: "本科及以上",
    companyBlacklist: [],
    companyWhitelist: [],
  },
  rankingPreferences: {
    industries: [],
    companySizes: [],
    fundingStages: ["B 轮以后"],
    technicalSkills: ["Go", "分布式系统"],
    benefits: [],
    publishedWithinDays: null,
  },
  pendingConfirmationFields: ["cities", "salary_min", "funding_stages"],
};

export const fixtureCollectionProgress: CollectionProgress = {
  status: "running",
  summary: { platformCount: 3, completedPlatformCount: 1, failedPlatformCount: 0, collectedJobCount: 128 },
  platforms: [
    { platform: "BOSS 直聘", status: "detail_collected", phase: "第 5 页详情读取", collectedCount: 74, totalCount: 100, retryCount: 0, failureReason: null },
    { platform: "拉勾", status: "manual_handoff", phase: "验证码 / 重试 1 次", collectedCount: 18, totalCount: 50, retryCount: 1, failureReason: "验证码" },
    { platform: "猎聘", status: "completed", phase: "36 个详情已保存", collectedCount: 36, totalCount: 36, retryCount: 0, failureReason: null },
    { platform: "登录态检查", status: "login_expired", phase: "BOSS 详情页要求重新登录", collectedCount: 0, totalCount: 0, retryCount: 0, failureReason: "login expired" },
    { platform: "页面结构", status: "page_changed", phase: "猎聘公司规模字段选择器失效", collectedCount: 0, totalCount: 0, retryCount: 0, failureReason: "保留低置信度" },
    { platform: "频率限制", status: "rate_limited", phase: "拉勾退避 12 分钟", collectedCount: 0, totalCount: 0, retryCount: 2, failureReason: "rate limit" },
  ],
  events: [
    { time: "14:22", platform: "BOSS 直聘", message: "进入第 5 页详情读取", status: "running" },
    { time: "14:19", platform: "拉勾", message: "验证码，需要用户在 Chrome 中处理", status: "handoff" },
    { time: "14:16", platform: "猎聘", message: "36 个岗位完成详情读取", status: "done" },
    { time: "14:12", platform: "安全扫描", message: "node_runs 命中疑似 session 字段，已阻断写入", status: "security_blocked" },
  ],
};

export const fixtureJobList: JobListItem[] = [
  {
    id: "job-1",
    platform: "BOSS",
    platformJobId: "boss-001",
    title: "Go 后端平台工程师",
    companyName: "极星科技",
    location: "上海",
    remotePolicy: null,
    salaryRange: "35-55k",
    level: null,
    experienceRequirement: "5-8 年",
    educationRequirement: "本科",
    industry: null,
    companySize: null,
    fundingStage: null,
    techStack: ["Go", "Kubernetes", "分布式系统"],
    benefits: [],
    publishedAt: null,
    detailUrl: null,
    jdText: "",
    collectedAt: "2026-06-10T14:00:00Z",
    fieldConfidence: {},
    score: 92,
    hardFilterStatus: "pass",
    evaluationStatus: "done",
    applicationStatus: "available",
    riskLevel: "low",
    excludeReason: "全部硬条件通过",
  },
  {
    id: "job-2",
    platform: "猎聘",
    platformJobId: "liepin-001",
    title: "AI Infra 后端工程师",
    companyName: "澜舟智能",
    location: "杭州",
    remotePolicy: null,
    salaryRange: "40-60k",
    level: null,
    experienceRequirement: null,
    educationRequirement: null,
    industry: null,
    companySize: null,
    fundingStage: null,
    techStack: ["Go", "AI Infra", "推理平台"],
    benefits: [],
    publishedAt: null,
    detailUrl: null,
    jdText: "",
    collectedAt: "2026-06-10T14:05:00Z",
    fieldConfidence: { companySize: "low" },
    score: 88,
    hardFilterStatus: "pass",
    evaluationStatus: "done",
    applicationStatus: "stale",
    riskLevel: "medium",
    excludeReason: "低置信度",
  },
  {
    id: "job-3",
    platform: "拉勾",
    platformJobId: "lagou-001",
    title: "资深服务端工程师",
    companyName: "云启网络",
    location: "远程",
    remotePolicy: "远程",
    salaryRange: "30-45k",
    level: null,
    experienceRequirement: null,
    educationRequirement: null,
    industry: null,
    companySize: null,
    fundingStage: null,
    techStack: ["Go", "高并发", "交易系统"],
    benefits: [],
    publishedAt: null,
    detailUrl: null,
    jdText: "",
    collectedAt: "2026-06-10T14:10:00Z",
    fieldConfidence: {},
    score: 83,
    hardFilterStatus: "edge",
    evaluationStatus: "pending",
    applicationStatus: "pending_review",
    riskLevel: "medium",
    excludeReason: "待确认",
  },
  {
    id: "job-4",
    platform: "BOSS",
    platformJobId: "boss-002",
    title: "后端开发工程师",
    companyName: "北辰外包",
    location: "北京",
    remotePolicy: null,
    salaryRange: "25-35k",
    level: null,
    experienceRequirement: null,
    educationRequirement: null,
    industry: null,
    companySize: null,
    fundingStage: null,
    techStack: ["Java"],
    benefits: [],
    publishedAt: null,
    detailUrl: null,
    jdText: "",
    collectedAt: "2026-06-10T14:15:00Z",
    fieldConfidence: {},
    score: 76,
    hardFilterStatus: "fail",
    evaluationStatus: "failed",
    applicationStatus: "duplicate",
    riskLevel: "high",
    excludeReason: "历史已投递且公司黑名单",
  },
];

export const fixtureJobDetails: Record<string, JobDetail> = {
  "job-1": {
    jdSummary: "负责平台服务治理、任务调度、日志链路和服务可观测性建设。要求 Go、Kubernetes、消息队列和高并发服务经验。",
    strengths: [
      { title: "Go 服务治理经验", detail: "简历中已有平台服务和链路追踪项目。" },
      { title: "分布式系统背景", detail: "任务调度和队列处理经验与 JD 高相关。" },
    ],
    risks: [
      { title: "Kubernetes 生产经验不足", detail: "建议补充部署、扩缩容或故障处理案例。" },
      { title: "公司规模字段低置信度", detail: "确认前保留，不直接过滤。" },
    ],
    missingInformation: [],
    resumeAdvice: [
      { title: "补充 Kubernetes 实战案例", detail: "在简历中加入 K8s 集群管理或故障排查经验。" },
    ],
    applicationMessage: "你好，我有 6 年后端与平台工程经验，近期重点做 Go 服务治理、任务调度和可观测性建设。看到岗位关注分布式平台稳定性，和我过往项目匹配度较高，希望进一步沟通。",
  },
  "job-2": {
    jdSummary: "负责 AI 基础设施后端开发，包括模型网关、推理平台和服务编排。要求 Go、Python 和分布式系统经验。",
    strengths: [
      { title: "Go 后端经验", detail: "简历中有大量 Go 服务开发经验。" },
    ],
    risks: [
      { title: "AI Infra 领域经验不足", detail: "建议补充模型部署或推理优化相关项目。" },
      { title: "公司规模字段低置信度", detail: "确认前保留，不直接过滤。" },
    ],
    missingInformation: ["公司规模", "融资阶段"],
    resumeAdvice: [],
    applicationMessage: "你好，我有 6 年后端开发经验，对分布式系统和基础设施方向有深入理解。对 AI Infra 方向非常感兴趣，期待进一步沟通。",
  },
  "job-3": {
    jdSummary: "负责核心交易系统服务端开发，要求高并发和分布式系统经验。",
    strengths: [
      { title: "后端开发经验", detail: "多年后端服务开发背景。" },
    ],
    risks: [
      { title: "交易系统经验不明确", detail: "建议确认是否有金融或交易领域经验。" },
    ],
    missingInformation: [],
    resumeAdvice: [],
    applicationMessage: "你好，我有丰富的后端开发和高并发系统经验，对服务端架构设计有深入理解，期待进一步沟通。",
  },
  "job-4": {
    jdSummary: "外包驻场后端开发，Java 技术栈。",
    strengths: [],
    risks: [
      { title: "外包公司", detail: "已加入黑名单。" },
      { title: "技术栈不匹配", detail: "主要要求 Java，与候选人 Go 方向不符。" },
    ],
    missingInformation: [],
    resumeAdvice: [],
    applicationMessage: "",
  },
};

export const fixtureConfirmationBatch: ConfirmationBatch = {
  batchId: "JA-240610-01",
  jobCount: 2,
  platformCount: 2,
  highRiskCount: 1,
  duplicateCount: 1,
  platforms: [
    { name: "BOSS", count: 1 },
    { name: "猎聘", count: 1 },
  ],
  risks: [
    { title: "猎聘岗位字段低置信度", detail: "公司规模和融资阶段缺失，投递前保留风险提示。" },
    { title: "拉勾处于人工接管", detail: "验证码处理完成前不会提交拉勾岗位。" },
  ],
  resumeSummary: "后端 / Go / 平台工程，6 年经验，重点项目包含服务治理、任务调度、可观测性建设。",
  validations: [
    { jobRef: "Go 后端平台工程师", status: "ready", reason: "岗位在线，JD 未变化，按钮可用", willSubmit: true },
    { jobRef: "AI Infra 后端工程师", status: "stale-skipped", reason: "JD 核心职责变化，需要重新确认", willSubmit: false },
    { jobRef: "后端开发工程师", status: "duplicate-blocked", reason: "历史投递记录命中", willSubmit: false },
    { jobRef: "资深服务端工程师", status: "button-disabled", reason: "平台按钮不可用，写入 skipped", willSubmit: false },
  ],
};

export const fixtureApplicationResults: ApplicationResult[] = [
  { jobRef: "Go 后端平台工程师", platform: "BOSS", companyName: "极星科技", status: "submitted", submittedAt: "2026-06-10T14:40:00Z", failureReason: null, platformMessage: "平台提示：已发送招呼", duplicateDetected: false },
  { jobRef: "AI Infra 后端工程师", platform: "猎聘", companyName: "澜舟智能", status: "skipped", submittedAt: null, failureReason: "重校验发现核心职责变化", platformMessage: null, duplicateDetected: false },
  { jobRef: "资深服务端工程师", platform: "拉勾", companyName: "云启网络", status: "failed", submittedAt: null, failureReason: "验证码", platformMessage: "人工接管后可继续", duplicateDetected: false },
  { jobRef: "后端开发工程师", platform: "BOSS", companyName: "北辰外包", status: "duplicate", submittedAt: null, failureReason: "历史投递记录命中", platformMessage: null, duplicateDetected: true },
  { jobRef: "安全阻断样例", platform: "全平台", companyName: "prompt scan", status: "security_blocked", submittedAt: null, failureReason: "疑似 token 字段，未写入 node_runs", platformMessage: null, duplicateDetected: false },
];

export function createFallbackJobClient(): JobRuntimeClient {
  let selectedJobIds: string[] = [];
  return {
    async getJobSearchProfile() {
      return fixtureJobSearchProfile;
    },
    async saveJobSearchProfile(_sessionId, _overrides) {
      return { ...fixtureJobSearchProfile, status: "ready", pendingConfirmationFields: [] };
    },
    async getCollectionProgress() {
      return fixtureCollectionProgress;
    },
    async getJobList() {
      return fixtureJobList;
    },
    async getJobDetail(jobId: string) {
      return fixtureJobDetails[jobId] ?? fixtureJobDetails["job-1"];
    },
    async getConfirmationBatch(_sessionId, ids) {
      selectedJobIds = ids;
      return fixtureConfirmationBatch;
    },
    async getApplicationResults() {
      return { batchId: "JA-240610-01", submittedAt: "2026-06-10 14:40", results: fixtureApplicationResults };
    },
    async submitBatch(_sessionId, _confirmed) {
      void selectedJobIds;
    },
    async clearJobData(_sessionId) {},
  };
}
