import { useEffect, useState } from "react";
import {
  CollectionPlatform,
  CollectionProgress,
  ConfirmationBatch,
  JobDetail,
  JobListItem,
  JobRuntimeClient,
  JobSearchProfile,
  createFallbackJobClient,
  defaultCollectionProgress,
  defaultJobSearchProfile,
  fixtureApplicationResults,
} from "../../shared/api/job.js";

export type JobScreenId = "profile" | "collect" | "jobs" | "detail" | "results";

type JobModuleProps = {
  runtimeClient?: JobRuntimeClient;
  selectedJobIds?: string[];
  onSelectedJobIdsChange?: (ids: string[]) => void;
  onOpenConfirmModal?: () => void;
  onOpenCleanupModal?: () => void;
  activeScreen?: JobScreenId;
  onActiveScreenChange?: (screen: JobScreenId) => void;
};

const fallbackClient = createFallbackJobClient();

const screenTabs: { id: JobScreenId; label: string; badge?: string; badgeVariant?: "good" | "warn" | "bad" }[] = [
  { id: "profile", label: "画像与筛选", badge: "待确认", badgeVariant: "warn" },
  { id: "collect", label: "采集进度", badge: "运行中", badgeVariant: "good" },
  { id: "jobs", label: "候选岗位", badge: "128" },
  { id: "results", label: "投递结果", badge: "2 失败", badgeVariant: "bad" },
];

const hardFilterStatusLabel: Record<string, string> = {
  pass: "通过",
  edge: "边缘",
  fail: "不通过",
};

const hardFilterStatusVariant: Record<string, "good" | "warn" | "bad"> = {
  pass: "good",
  edge: "warn",
  fail: "bad",
};

const applicationStatusLabel: Record<string, string> = {
  available: "可投递",
  pending_review: "待话术",
  stale: "待重校验",
  submitted: "已投递",
  failed: "失败",
  skipped: "跳过",
  duplicate: "duplicate",
};

const applicationStatusVariant: Record<string, "good" | "warn" | "bad"> = {
  available: "good",
  pending_review: "warn",
  stale: "warn",
  submitted: "good",
  failed: "bad",
  skipped: "bad",
  duplicate: "bad",
};

const riskVariant: Record<string, "good" | "warn" | "bad"> = {
  low: "good",
  medium: "warn",
  high: "bad",
};

const riskLabel: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
};

const platformStatusVariant: Record<string, "good" | "warn" | "bad"> = {
  idle: "warn",
  started: "good",
  page_collected: "good",
  detail_collected: "good",
  completed: "good",
  failed: "bad",
  retrying: "warn",
  manual_handoff: "warn",
  rate_limited: "warn",
  login_expired: "bad",
  page_changed: "bad",
};

const platformStatusLabel: Record<string, string> = {
  idle: "待启动",
  started: "已启动",
  page_collected: "列表采集中",
  detail_collected: "详情读取中",
  completed: "采集完成",
  failed: "失败",
  retrying: "重试中",
  manual_handoff: "人工接管",
  rate_limited: "rate limit",
  login_expired: "login expired",
  page_changed: "page changed",
};

const eventStatusVariant: Record<string, "good" | "warn" | "bad"> = {
  running: "good",
  done: "good",
  handoff: "warn",
  security_blocked: "bad",
  error: "bad",
};

const eventStatusLabel: Record<string, string> = {
  running: "running",
  done: "done",
  handoff: "handoff",
  security_blocked: "security blocked",
  error: "error",
};

const detailTabs = ["JD 摘要", "匹配优势", "风险缺口", "简历建议", "投递话术"];

const resultButtonLabel: Record<string, string> = {
  submitted: "查看",
  skipped: "重新确认",
  failed: "重试",
  duplicate: "忽略",
  "stale-skipped": "重新确认",
  "button-disabled": "查看",
  security_blocked: "查看扫描摘要",
};

const resultStatusLabel: Record<string, string> = {
  submitted: "submitted",
  skipped: "skipped: JD 变化",
  failed: "failed: 验证码",
  duplicate: "duplicate",
  "stale-skipped": "stale-skipped",
  "button-disabled": "button-disabled",
  security_blocked: "security blocked",
};

const resultStatusVariant: Record<string, "good" | "warn" | "bad"> = {
  submitted: "good",
  skipped: "warn",
  failed: "bad",
  duplicate: "bad",
  "stale-skipped": "warn",
  "button-disabled": "bad",
  security_blocked: "bad",
};

export function JobModule({
  runtimeClient = fallbackClient,
  selectedJobIds = [],
  onSelectedJobIdsChange,
  onOpenConfirmModal,
  onOpenCleanupModal,
  activeScreen: controlledScreen,
  onActiveScreenChange,
}: JobModuleProps) {
  const [internalScreen, setInternalScreen] = useState<JobScreenId>("jobs");
  const activeScreen = controlledScreen ?? internalScreen;
  const setActiveScreen = onActiveScreenChange ?? setInternalScreen;
  const [profile, setProfile] = useState<JobSearchProfile>(defaultJobSearchProfile);
  const [collectionProgress, setCollectionProgress] = useState<CollectionProgress>(defaultCollectionProgress);
  const [jobList, setJobList] = useState<JobListItem[]>([]);
  const [selectedDetailJobId, setSelectedDetailJobId] = useState<string | null>(null);
  const [jobDetail, setJobDetail] = useState<JobDetail | null>(null);
  const [activeDetailTab, setActiveDetailTab] = useState("JD 摘要");
  const [profileLoading, setProfileLoading] = useState(false);
  const [listLoading, setListLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const selectedDetailJob = jobList.find((job) => job.id === selectedDetailJobId) ?? null;

  useEffect(() => {
    void loadProfile();
    void loadCollectionProgress();
    void loadJobList();
  }, []);

  async function loadProfile() {
    setProfileLoading(true);
    setProfileError(null);
    try {
      const loadedProfile = await runtimeClient.getJobSearchProfile("gui-mock-session");
      setProfile(loadedProfile);
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "求职画像加载失败");
    } finally {
      setProfileLoading(false);
    }
  }

  async function loadCollectionProgress() {
    try {
      const progress = await runtimeClient.getCollectionProgress("gui-mock-session");
      setCollectionProgress(progress);
    } catch {
      // silent
    }
  }

  async function loadJobList() {
    setListLoading(true);
    try {
      const list = await runtimeClient.getJobList("gui-mock-session");
      setJobList(list);
    } catch {
      // silent
    } finally {
      setListLoading(false);
    }
  }

  async function loadJobDetail(jobId: string) {
    setSelectedDetailJobId(jobId);
    setActiveScreen("detail");
    setActiveDetailTab("JD 摘要");
    try {
      const detail = await runtimeClient.getJobDetail(jobId);
      setJobDetail(detail);
    } catch {
      setJobDetail(null);
    }
  }

  function handleToggleJobSelection(jobId: string, checked: boolean) {
    const next = checked
      ? [...selectedJobIds, jobId]
      : selectedJobIds.filter((id) => id !== jobId);
    onSelectedJobIdsChange?.(next);
  }

  function handleShowScreen(screenId: JobScreenId) {
    setActiveScreen(screenId);
    if (screenId !== "detail") {
      setSelectedDetailJobId(null);
      setJobDetail(null);
    }
  }

  return (
    <div className="job-module">
      <nav className="job-tabs" aria-label="求职投递流程">
        {screenTabs.map((tab) => (
          <button
            className={`job-tab ${activeScreen === tab.id || (tab.id === "jobs" && activeScreen === "detail") ? "active" : ""}`}
            key={tab.id}
            type="button"
            onClick={() => handleShowScreen(tab.id)}
          >
            <span>{tab.label}</span>
            {tab.badge && <span className={`job-state-tag ${tab.badgeVariant ?? ""}`}>{tab.badge}</span>}
          </button>
        ))}
      </nav>

      <div className="job-content">
        {activeScreen === "profile" && (
          <ProfileScreen
            profile={profile}
            loading={profileLoading}
            error={profileError}
            onLoadProfile={loadProfile}
          />
        )}

        {activeScreen === "collect" && (
          <CollectScreen progress={collectionProgress} />
        )}

        {activeScreen === "jobs" && (
          <JobsScreen
            jobList={jobList}
            loading={listLoading}
            selectedJobIds={selectedJobIds}
            onToggleSelection={handleToggleJobSelection}
            onOpenDetail={loadJobDetail}
            onOpenConfirmModal={onOpenConfirmModal}
          />
        )}

        {activeScreen === "detail" && selectedDetailJob && (
          <DetailScreen
            job={selectedDetailJob}
            detail={jobDetail}
            activeTab={activeDetailTab}
            onTabChange={setActiveDetailTab}
            onBack={() => handleShowScreen("jobs")}
          />
        )}

        {activeScreen === "results" && (
          <ResultsScreen
            batchId="JA-240610-01"
            submittedAt="2026-06-10 14:40"
            results={fixtureApplicationResults}
          />
        )}
      </div>
    </div>
  );
}

function ProfileScreen({
  profile,
  loading,
  error,
  onLoadProfile,
}: {
  profile: JobSearchProfile;
  loading: boolean;
  error: string | null;
  onLoadProfile: () => void;
}) {
  const profileCompleteness = profile.status === "missing_inputs" ? 0 : Math.round(
    ((profile.jobProfile.technicalSkills.length > 0 ? 1 : 0) +
      (profile.jobProfile.targetRoles.length > 0 ? 1 : 0) +
      (profile.hardFilters.cities.length > 0 ? 1 : 0) +
      (profile.hardFilters.salaryMin != null ? 1 : 0) +
      (profile.hardFilters.education != null ? 1 : 0) +
      (profile.rankingPreferences.technicalSkills.length > 0 ? 1 : 0) +
      (profile.rankingPreferences.industries.length > 0 ? 1 : 0) +
      (profile.rankingPreferences.fundingStages.length > 0 ? 1 : 0)) / 8 * 100
  );
  const pendingCount = profile.pendingConfirmationFields.length;
  const keywordCount = profile.defaultSearchKeywords.length;

  if (profile.status === "missing_inputs") {
    return (
      <div className="job-screen">
        <div className="job-blocked-card">
          <div className="job-blocked-head">
            <h3>阻断空态：未找到 resume_profile</h3>
            <span className="job-state-tag bad">empty</span>
          </div>
          <p className="muted-text">当用户尚未导入简历或简历解析失败时，只显示"去面试准备"入口，不允许开始采集。</p>
          <div className="job-actions">
            <button className="ghost-button" type="button">去面试准备</button>
            <button className="ghost-button" type="button" onClick={onLoadProfile}>重新读取画像</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="job-screen">
      <div className="job-metric-grid">
        <div className="job-metric-card">
          <span className="job-metric-label">简历画像</span>
          <strong className="job-metric-value">{profileCompleteness}%</strong>
          <span className="muted-text">{profile.jobProfile.technicalSkills.length} 个技能已识别</span>
        </div>
        <div className="job-metric-card">
          <span className="job-metric-label">待确认字段</span>
          <strong className="job-metric-value warn">{pendingCount}</strong>
          <span className="muted-text">{profile.pendingConfirmationFields.join("、") || "无"}</span>
        </div>
        <div className="job-metric-card">
          <span className="job-metric-label">默认搜索词</span>
          <strong className="job-metric-value">{keywordCount}</strong>
          <span className="muted-text">{profile.defaultSearchKeywords.slice(0, 3).join(" / ")}</span>
        </div>
      </div>

      <div className="job-grid-2">
        <div className="job-card">
          <div className="job-card-head">
            <h3>硬过滤</h3>
            <span className="job-state-tag warn">开始采集前确认</span>
          </div>
          <div className="job-form-grid">
            <label className="job-field">
              <span className="job-field-label">城市 {profile.hardFilters.cities.length === 0 && <span className="job-state-tag warn">缺失</span>}</span>
              <input className="job-field-input" defaultValue={profile.hardFilters.cities.join(" / ")} readOnly />
            </label>
            <label className="job-field">
              <span className="job-field-label">薪资下限 {profile.hardFilters.salaryMin == null && <span className="job-state-tag warn">待确认</span>}</span>
              <input className="job-field-input" defaultValue={profile.hardFilters.salaryMin ?? ""} readOnly />
            </label>
            <label className="job-field">
              <span className="job-field-label">经验</span>
              <input className="job-field-input" defaultValue={profile.hardFilters.experienceYearsMin ? `${profile.hardFilters.experienceYearsMin}-${profile.hardFilters.experienceYearsMax} 年` : ""} readOnly />
            </label>
            <label className="job-field">
              <span className="job-field-label">学历</span>
              <input className="job-field-input" defaultValue={profile.hardFilters.education ?? ""} readOnly />
            </label>
          </div>
        </div>

        <div className="job-card">
          <div className="job-card-head">
            <h3>排序偏好</h3>
            <span className="job-state-tag good">不直接排除</span>
          </div>
          <div className="job-chip-row">
            {profile.rankingPreferences.technicalSkills.map((skill) => (
              <span className="job-chip active" key={skill}>{skill}</span>
            ))}
            {profile.rankingPreferences.fundingStages.map((stage) => (
              <span className="job-chip" key={stage}>{stage}</span>
            ))}
            <span className="job-chip">远程优先</span>
          </div>
          <label className="job-field" style={{ marginTop: 14 }}>
            <span className="job-field-label">黑名单公司</span>
            <textarea className="job-textarea" defaultValue={profile.hardFilters.companyBlacklist.join("、")} readOnly />
          </label>
        </div>
      </div>

      <div className="job-actions">
        <button className="ghost-button" type="button">重置为简历推导结果</button>
        <button className="primary-button" type="button">保存画像并开始采集</button>
      </div>

      {loading && <p className="muted-text">画像加载中</p>}
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}

function CollectScreen({ progress }: { progress: CollectionProgress }) {
  const manualHandoffCount = progress.platforms.filter((p) => p.status === "manual_handoff").length;

  return (
    <div className="job-screen">
      <div className="job-metric-grid">
        <div className="job-metric-card">
          <span className="job-metric-label">已采集岗位</span>
          <strong className="job-metric-value">{progress.summary.collectedJobCount}</strong>
          <span className="muted-text">{progress.platforms.reduce((sum, p) => sum + p.collectedCount, 0)} 个已完成详情读取</span>
        </div>
        <div className="job-metric-card">
          <span className="job-metric-label">评估队列</span>
          <strong className="job-metric-value">31</strong>
          <span className="muted-text">后台继续生成报告</span>
        </div>
        <div className="job-metric-card">
          <span className="job-metric-label">人工接管</span>
          <strong className="job-metric-value warn">{manualHandoffCount}</strong>
          <span className="muted-text">{progress.platforms.find((p) => p.status === "manual_handoff")?.platform ?? "无"}</span>
        </div>
      </div>

      <div className="job-card">
        <div className="job-card-head">
          <h3>平台进度</h3>
          <button className="ghost-button" type="button">重试失败平台</button>
        </div>
        <div className="job-platform-list">
          {progress.platforms.map((platform) => (
            <PlatformRow key={platform.platform} platform={platform} />
          ))}
        </div>
      </div>

      <div className="job-card">
        <div className="job-card-head">
          <h3>状态矩阵</h3>
          <span className="job-tag">用于 JOB-013 验收</span>
        </div>
        <div className="job-state-matrix">
          <div className="job-state-card"><strong>loading</strong><span className="job-skeleton" /><span className="muted-text">平台任务创建中</span></div>
          <div className="job-state-card warn"><strong>manual handoff</strong><span className="muted-text">验证码、风控、强制弹窗</span></div>
          <div className="job-state-card bad"><strong>security blocked</strong><span className="muted-text">敏感字段扫描命中，禁止继续投递</span></div>
          <div className="job-state-card good"><strong>progress</strong><span className="muted-text">分页、详情、评估分阶段展示</span></div>
        </div>
      </div>

      <div className="job-card">
        <div className="job-card-head">
          <h3>非敏感事件流</h3>
          <span className="job-state-tag good">已脱敏</span>
        </div>
        <div className="job-event-list">
          {progress.events.map((event, index) => (
            <div className="job-event-row" key={`${event.time}-${index}`}>
              <span className="muted-text">{event.time}</span>
              <strong>{event.platform}</strong>
              <span className="muted-text">{event.message}</span>
              <span className={`job-state-tag ${eventStatusVariant[event.status] ?? ""}`}>{eventStatusLabel[event.status] ?? event.status}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PlatformRow({ platform }: { platform: CollectionPlatform }) {
  const progressPercent = platform.totalCount > 0 ? Math.round((platform.collectedCount / platform.totalCount) * 100) : 0;
  const statusVariant = platformStatusVariant[platform.status] ?? "warn";
  const statusLabel = platformStatusLabel[platform.status] ?? platform.status;

  return (
    <div className="job-platform-row">
      <strong>{platform.platform}</strong>
      <span className={`job-state-tag ${statusVariant}`}>{statusLabel}</span>
      <span className="muted-text">阶段：{platform.phase}</span>
      <div className="job-progress-track">
        <div className="job-progress-fill" style={{ width: `${progressPercent}%` }} />
      </div>
      {platform.status === "manual_handoff" ? (
        <button className="ghost-button" type="button">Chrome 处理后继续</button>
      ) : platform.status === "failed" ? (
        <button className="ghost-button" type="button">重试</button>
      ) : platform.status === "rate_limited" ? (
        <button className="ghost-button" type="button">暂停平台</button>
      ) : platform.status === "login_expired" ? (
        <button className="ghost-button" type="button">Chrome 登录后重试</button>
      ) : platform.status === "page_changed" ? (
        <button className="ghost-button" type="button">查看解析错误</button>
      ) : (
        <span className="muted-text">{platform.collectedCount} / {platform.totalCount}</span>
      )}
    </div>
  );
}

function JobsScreen({
  jobList,
  loading,
  selectedJobIds,
  onToggleSelection,
  onOpenDetail,
  onOpenConfirmModal,
}: {
  jobList: JobListItem[];
  loading: boolean;
  selectedJobIds: string[];
  onToggleSelection: (jobId: string, checked: boolean) => void;
  onOpenDetail: (jobId: string) => void;
  onOpenConfirmModal?: () => void;
}) {
  const selectedCount = selectedJobIds.length;

  return (
    <div className="job-screen">
      <div className="job-filter-row">
        <button className="job-chip active" type="button">全部平台</button>
        <button className="job-chip active" type="button">匹配分 80+</button>
        <button className="job-chip" type="button">硬条件通过</button>
        <button className="job-chip" type="button">排序：匹配分↓</button>
        <button className="job-chip" type="button">远程</button>
        <button className="job-chip" type="button">低置信度</button>
        <button className="job-chip" type="button">高风险</button>
        <input className="job-search-input" placeholder="搜索岗位" defaultValue="Go 后端" />
      </div>

      {loading && <p className="muted-text">岗位列表加载中</p>}

      <div className="job-table" role="table" aria-label="候选岗位">
        <div className="job-row header" role="row">
          <span /><span>匹配</span><span>硬过滤</span><span>平台</span><span>岗位</span><span>公司</span><span>薪资</span><span>城市</span><span>评估</span><span>投递</span><span>风险</span><span>排除 / 保留原因</span>
        </div>
        {jobList.map((job) => {
          const isSelected = selectedJobIds.includes(job.id);
          const isDisabled = job.applicationStatus === "duplicate" || job.hardFilterStatus === "fail";
          return (
            <div className={`job-row ${isSelected ? "selected" : ""}`} key={job.id} role="row">
              <input
                type="checkbox"
                checked={isSelected}
                disabled={isDisabled}
                aria-label={`选择 ${job.title}`}
                onChange={(e) => onToggleSelection(job.id, e.target.checked)}
              />
              <span className="job-score">{job.score}</span>
              <span className={`job-state-tag ${hardFilterStatusVariant[job.hardFilterStatus] ?? ""}`}>{hardFilterStatusLabel[job.hardFilterStatus] ?? job.hardFilterStatus}</span>
              <span>{job.platform}</span>
              <span className="job-title-cell">
                <button className="job-link-button" type="button" onClick={() => onOpenDetail(job.id)}>{job.title}</button>
                <span className="muted-text truncate">{job.techStack.slice(0, 2).join(" / ")}</span>
              </span>
              <span className="truncate">{job.companyName}</span>
              <span>{job.salaryRange}</span>
              <span>{job.location}</span>
              <span className={`job-state-tag ${job.evaluationStatus === "done" ? "good" : job.evaluationStatus === "pending" ? "warn" : "bad"}`}>{job.evaluationStatus === "done" ? "done" : job.evaluationStatus === "pending" ? "pending" : "failed"}</span>
              <span className={`job-state-tag ${applicationStatusVariant[job.applicationStatus] ?? ""}`}>{applicationStatusLabel[job.applicationStatus] ?? job.applicationStatus}</span>
              <span className={`job-state-tag ${riskVariant[job.riskLevel] ?? ""}`}>{riskLabel[job.riskLevel] ?? job.riskLevel}</span>
              <span className="muted-text truncate">{job.excludeReason ?? ""}</span>
            </div>
          );
        })}
      </div>

      <div className="job-mobile-list">
        {jobList.slice(0, 4).map((job) => (
          <div className="job-mobile-card" key={`mobile-${job.id}`}>
            <div className="job-mobile-head">
              <button className="job-link-button" type="button" onClick={() => onOpenDetail(job.id)}>{job.title}</button>
              <span className="job-score">{job.score}</span>
            </div>
            <p className="muted-text">{job.platform} / {job.companyName} / {job.location} / {job.salaryRange}</p>
            <div className="job-chip-row">
              <span className={`job-tag ${hardFilterStatusVariant[job.hardFilterStatus] ?? ""}`}>{hardFilterStatusLabel[job.hardFilterStatus]}过滤</span>
              <span className={`job-tag ${applicationStatusVariant[job.applicationStatus] ?? ""}`}>{applicationStatusLabel[job.applicationStatus]}</span>
              <span className={`job-tag ${riskVariant[job.riskLevel] ?? ""}`}>{riskLabel[job.riskLevel]}风险</span>
            </div>
          </div>
        ))}
      </div>

      <div className="job-card">
        <div className="job-card-head">
          <h3>空态 / 加载态 / 错误态</h3>
          <span className="job-tag">候选清单边界</span>
        </div>
        <div className="job-state-matrix">
          <div className="job-state-card"><strong>empty</strong><span className="muted-text">筛选后 0 个岗位，显示调整筛选入口</span></div>
          <div className="job-state-card"><strong>loading</strong><span className="job-skeleton" /><span className="muted-text">评估报告生成中</span></div>
          <div className="job-state-card warn"><strong>pending_review</strong><span className="muted-text">话术未生成，不允许确认投递</span></div>
          <div className="job-state-card bad"><strong>error</strong><span className="muted-text">单岗位评估失败，可重试，不污染其他岗位</span></div>
        </div>
      </div>

      {selectedCount > 0 && onOpenConfirmModal && (
        <div className="job-actions">
          <span className="muted-text">已选择 {selectedCount} 个岗位</span>
          <button className="primary-button" type="button" onClick={onOpenConfirmModal}>批量确认</button>
        </div>
      )}
    </div>
  );
}

function DetailScreen({
  job,
  detail,
  activeTab,
  onTabChange,
  onBack,
}: {
  job: JobListItem;
  detail: JobDetail | null;
  activeTab: string;
  onTabChange: (tab: string) => void;
  onBack: () => void;
}) {
  return (
    <div className="job-screen">
      <div className="job-detail-layout">
        <div className="job-detail-main">
          <div className="job-card">
            <button className="ghost-button" type="button" onClick={onBack}>返回候选清单</button>
            <div className="job-detail-head">
              <div>
                <h3>{job.title}</h3>
                <p className="muted-text">{job.companyName} / {job.platform} / {job.location} / {job.salaryRange}</p>
              </div>
              <span className="job-score">{job.score}</span>
            </div>
          </div>

          <div className="job-detail-tabs">
            {detailTabs.map((tab) => (
              <button
                className={`job-detail-tab ${activeTab === tab ? "active" : ""}`}
                key={tab}
                type="button"
                onClick={() => onTabChange(tab)}
              >
                {tab}
              </button>
            ))}
          </div>

          {activeTab === "JD 摘要" && detail && (
            <div className="job-card"><h3>JD 摘要</h3><p className="muted-text" style={{ marginTop: 10 }}>{detail.jdSummary}</p></div>
          )}

          {activeTab === "匹配优势" && detail && (
            <div className="job-card">
              <h3>匹配优势</h3>
              <div className="job-advice-list">
                {detail.strengths.map((s) => (
                  <div className="job-advice-item" key={s.title}><strong>{s.title}</strong><span className="muted-text">{s.detail}</span></div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "风险缺口" && detail && (
            <div className="job-card">
              <h3>风险缺口</h3>
              <div className="job-risk-list">
                {detail.risks.map((r) => (
                  <div className="job-risk-item" key={r.title}><strong>{r.title}</strong><span className="muted-text">{r.detail}</span></div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "简历建议" && detail && (
            <div className="job-card">
              <h3>简历建议</h3>
              <div className="job-advice-list">
                {detail.resumeAdvice.length > 0
                  ? detail.resumeAdvice.map((a) => (
                      <div className="job-advice-item" key={a.title}><strong>{a.title}</strong><span className="muted-text">{a.detail}</span></div>
                    ))
                  : <p className="muted-text">暂无简历改进建议。</p>
                }
              </div>
            </div>
          )}

          {activeTab === "投递话术" && detail && (
            <div className="job-card">
              <h3>投递话术</h3>
              <textarea className="job-textarea" style={{ marginTop: 12 }} value={detail.applicationMessage} readOnly />
              <div className="job-actions" style={{ marginTop: 12 }}>
                <button className="ghost-button" type="button">复制</button>
                <button className="primary-button" type="button">加入投递队列</button>
              </div>
            </div>
          )}

          <div className="job-state-matrix">
            <div className="job-state-card"><strong>无选中岗位</strong><span className="muted-text">提示先从候选清单选择岗位</span></div>
            <div className="job-state-card warn"><strong>JD 读取失败</strong><span className="muted-text">保留平台 URL 摘要和重试入口</span></div>
            <div className="job-state-card"><strong>评估生成中</strong><span className="job-skeleton" /><span className="muted-text">不允许加入投递队列</span></div>
            <div className="job-state-card bad"><strong>话术生成失败</strong><span className="muted-text">允许重试，不自动提交</span></div>
          </div>
        </div>

        <aside className="job-card">
          <h3>投递话术</h3>
          <textarea className="job-textarea" style={{ marginTop: 12 }} value={detail?.applicationMessage ?? ""} readOnly />
          <div className="job-actions" style={{ marginTop: 12 }}>
            <button className="ghost-button" type="button">复制</button>
            <button className="primary-button" type="button">加入投递队列</button>
          </div>
        </aside>
      </div>
    </div>
  );
}

function ResultsScreen({
  batchId,
  submittedAt,
  results,
}: {
  batchId: string;
  submittedAt: string;
  results: typeof fixtureApplicationResults;
}) {
  const submittedCount = results.filter((r) => r.status === "submitted").length;
  const failedSkippedCount = results.filter((r) => r.status !== "submitted").length;

  return (
    <div className="job-screen">
      <div className="job-metric-grid">
        <div className="job-metric-card">
          <span className="job-metric-label">批次 ID</span>
          <strong className="job-metric-value">{batchId}</strong>
          <span className="muted-text">{submittedAt}</span>
        </div>
        <div className="job-metric-card">
          <span className="job-metric-label">已提交</span>
          <strong className="job-metric-value good">{submittedCount}</strong>
          <span className="muted-text">平台返回成功</span>
        </div>
        <div className="job-metric-card">
          <span className="job-metric-label">失败 / 跳过</span>
          <strong className="job-metric-value bad">{failedSkippedCount}</strong>
          <span className="muted-text">支持按项重试</span>
        </div>
      </div>

      <div className="job-card">
        <div className="job-card-head">
          <h3>投递结果</h3>
          <button className="ghost-button" type="button">导出摘要</button>
        </div>
        <div className="job-result-list">
          {results.map((result) => (
            <div className="job-result-row" key={result.jobRef}>
              <strong>{result.jobRef}</strong>
              <span className="muted-text">{result.platform} / {result.companyName}</span>
              <span className={`job-state-tag ${resultStatusVariant[result.status] ?? ""}`}>{resultStatusLabel[result.status] ?? result.status}</span>
              <span className="muted-text">{result.platformMessage ?? result.failureReason ?? ""}</span>
              <button className="ghost-button" type="button">
                {resultButtonLabel[result.status] ?? "查看"}
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
