import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import {
  EndMockInterviewRequest,
  MockInterviewViewModel,
  normalizeMockInterviewViewModel,
  StartMockInterviewRequest,
  SubmitMockAnswerRequest,
} from "../api/mock";
import {
  AlgorithmPracticeViewModel,
  normalizeAlgorithmPracticeViewModel,
  StartAlgorithmPracticeRequest,
} from "../api/algorithm";
import {
  ApplicationResult,
  CollectionProgress,
  ConfirmationBatch,
  JobDetail,
  JobListItem,
  JobSearchProfile,
  normalizeApplicationResults,
  normalizeCollectionProgress,
  normalizeConfirmationBatch,
  normalizeJobDetail,
  normalizeJobList,
  normalizeJobSearchProfile,
} from "../api/job";
import { normalizePrepViewModel, PrepViewModel } from "../api/prep";
import {
  DesktopRuntimeSnapshot,
  snapshotWithDesktopError as buildSnapshotWithDesktopError,
} from "./desktopSnapshot";

export type MaterialKind = "resume" | "jd";
export type { DesktopRuntimeSnapshot };
export type UserRecord = {
  userId: string;
  username: string;
  role: "admin" | "member";
  status: "enabled" | "disabled";
};

export async function loadDesktopSnapshot(): Promise<DesktopRuntimeSnapshot> {
  return invoke<DesktopRuntimeSnapshot>("runtime_snapshot");
}

export function snapshotWithDesktopError(
  error: unknown,
  previousSnapshot: DesktopRuntimeSnapshot | null,
): DesktopRuntimeSnapshot {
  return buildSnapshotWithDesktopError(error, previousSnapshot, true);
}

export async function startPythonRuntime(): Promise<DesktopRuntimeSnapshot> {
  return invoke<DesktopRuntimeSnapshot>("start_python_runtime");
}

export async function stopPythonRuntime(): Promise<DesktopRuntimeSnapshot> {
  return invoke<DesktopRuntimeSnapshot>("stop_python_runtime");
}

export async function selectMaterialFile(kind: MaterialKind): Promise<DesktopRuntimeSnapshot> {
  const selectedPath = await open({
    multiple: false,
    directory: false,
    filters: [
      {
        name: "Interview material",
        extensions: kind === "jd"
          ? ["pdf", "docx", "doc", "md", "txt", "png", "jpg", "jpeg", "webp", "bmp", "gif"]
          : ["pdf", "docx", "doc", "md", "txt"],
      },
    ],
  });
  if (typeof selectedPath !== "string") {
    return loadDesktopSnapshot();
  }

  return invoke<DesktopRuntimeSnapshot>("remember_material_file", {
    kind,
    path: selectedPath,
  });
}

export async function prepareInterviewMaterials(sessionId: string): Promise<PrepViewModel> {
  const rawViewModel = await invoke("prepare_interview_materials", { sessionId });
  return normalizePrepViewModel(rawViewModel);
}

export async function startMockInterview(request: StartMockInterviewRequest): Promise<MockInterviewViewModel> {
  const rawViewModel = await invoke("start_mock_interview", { payload: request });
  return normalizeMockInterviewViewModel(rawViewModel);
}

export async function startAlgorithmPractice(request: StartAlgorithmPracticeRequest): Promise<AlgorithmPracticeViewModel> {
  const rawViewModel = await invoke("start_algorithm_practice", { payload: request });
  return normalizeAlgorithmPracticeViewModel(rawViewModel);
}

export async function submitMockAnswer(request: SubmitMockAnswerRequest): Promise<MockInterviewViewModel> {
  const rawViewModel = await invoke("submit_mock_answer", { payload: request });
  return normalizeMockInterviewViewModel(rawViewModel);
}

export async function endMockInterview(request: EndMockInterviewRequest): Promise<MockInterviewViewModel> {
  const rawViewModel = await invoke("end_mock_interview", { sessionId: request.sessionId });
  return normalizeMockInterviewViewModel(rawViewModel);
}

export async function listUsers(): Promise<UserRecord[]> {
  return invoke<UserRecord[]>("list_users");
}

export async function addUser(username: string, password: string, role: "admin" | "member"): Promise<UserRecord> {
  return invoke<UserRecord>("add_user", {
    payload: { username, password, role },
  });
}

export async function updateUserStatus(username: string, status: "enabled" | "disabled"): Promise<boolean> {
  return invoke<boolean>("update_user_status", {
    payload: { username, status },
  });
}

export async function loginUser(username: string, password: string): Promise<UserRecord | null> {
  return invoke<UserRecord | null>("login_user", {
    payload: { username, password },
  });
}

export async function logoutUser(): Promise<void> {
  await invoke("logout_user");
}

export async function prepareJobSearchProfile(
  sessionId: string,
  overrides?: Record<string, unknown>,
): Promise<JobSearchProfile> {
  const rawViewModel = await invoke("prepare_job_search_profile", {
    payload: { sessionId, overrides: overrides ?? {} },
  });
  return normalizeJobSearchProfile(rawViewModel);
}

export async function saveJobSearchProfile(
  sessionId: string,
  overrides: Record<string, unknown>,
): Promise<JobSearchProfile> {
  const rawViewModel = await invoke("prepare_job_search_profile", {
    payload: { sessionId, overrides },
  });
  return normalizeJobSearchProfile(rawViewModel);
}

export async function getJobCollectionProgress(sessionId: string): Promise<CollectionProgress> {
  const rawViewModel = await invoke("get_job_collection_progress", { sessionId });
  return normalizeCollectionProgress(rawViewModel);
}

export async function retryFailedJobCollection(
  sessionId: string,
  collectionTaskId: string,
  platform: string,
): Promise<CollectionProgress> {
  const rawViewModel = await invoke("retry_failed_job_collection_platform", {
    payload: { sessionId, collectionTaskId, platform },
  });
  return normalizeCollectionProgress(rawViewModel);
}

export async function getJobFilterResults(sessionId: string): Promise<JobListItem[]> {
  const rawViewModel = await invoke("list_job_applications", { sessionId });
  if (!Array.isArray(rawViewModel)) return [];
  return normalizeJobList(rawViewModel);
}

export async function getJobEvaluationResults(sessionId: string): Promise<unknown> {
  return invoke("get_job_evaluation_results", { sessionId });
}

export async function getJobDetail(sessionId: string, jobId: string): Promise<JobDetail> {
  const [detailRaw, evaluationRaw] = await Promise.all([
    invoke("get_job_application_detail", { sessionId, jobId }),
    invoke("get_job_evaluation_results", { sessionId }),
  ]);
  if (detailRaw === null || detailRaw === undefined) {
    return { jdSummary: "", strengths: [], risks: [], missingInformation: [], resumeAdvice: [], applicationMessage: "岗位不存在" };
  }
  const r = detailRaw as Record<string, unknown>;
  const jdText = typeof r.jd_text === "string" ? r.jd_text : "";
  const title = typeof r.title === "string" ? r.title : "";
  const company = typeof r.company_name === "string" ? r.company_name : "";
  const location = typeof r.location === "string" ? r.location : "";
  const missing: string[] = [];
  if (!r.salary_range) missing.push("薪资范围");
  if (!r.remote_policy) missing.push("办公方式");
  if (!r.level) missing.push("职级");
  if (!r.experience_requirement) missing.push("经验要求");

  // 尝试从评估结果中合并该岗位的评估数据
  let evaluationForJob: Record<string, unknown> | null = null;
  if (evaluationRaw && typeof evaluationRaw === "object") {
    const evalMap = evaluationRaw as Record<string, unknown>;
    const reports = evalMap.reports ?? evalMap.evaluations ?? evalMap.results;
    if (Array.isArray(reports)) {
      for (const item of reports) {
        if (item && typeof item === "object") {
          const rec = item as Record<string, unknown>;
          const itemJobId = String(rec.job_id ?? rec.jobId ?? rec.platform_job_id ?? "");
          if (itemJobId === jobId) {
            evaluationForJob = rec;
            break;
          }
        }
      }
    }
  }

  if (evaluationForJob) {
    const merged = { ...evaluationForJob, jd_summary: evaluationForJob.jd_summary ?? jdText.slice(0, 500) };
    const normalized = normalizeJobDetail(merged);
    // 补充缺失字段
    if (!normalized.jdSummary) normalized.jdSummary = jdText.slice(0, 500) || `${title} @ ${company} - ${location}`;
    if (normalized.missingInformation.length === 0) normalized.missingInformation = missing;
    return normalized;
  }

  return {
    jdSummary: jdText.slice(0, 500) || `${title} @ ${company} - ${location}`,
    strengths: [],
    risks: [],
    missingInformation: missing,
    resumeAdvice: [],
    applicationMessage: "",
  };
}

export async function getConfirmationBatch(
  sessionId: string,
  _selectedJobIds: string[],
): Promise<ConfirmationBatch> {
  const rawViewModel = await invoke("get_revalidation_results", { sessionId });
  return normalizeConfirmationBatch(rawViewModel);
}

export async function getApplicationResults(sessionId: string): Promise<{ batchId: string; submittedAt: string; results: ApplicationResult[] }> {
  const [bossRaw, lagouRaw, liepinRaw] = await Promise.all([
    invoke("get_boss_submit_results", { sessionId }),
    invoke("get_lagou_submit_results", { sessionId }),
    invoke("get_liepin_submit_results", { sessionId }),
  ]);
  const allResults: ApplicationResult[] = [];
  let latestSubmittedAt = "";
  for (const raw of [bossRaw, lagouRaw, liepinRaw]) {
    const parsed = normalizeApplicationResults(raw);
    allResults.push(...parsed.results);
    if (parsed.submittedAt > latestSubmittedAt) latestSubmittedAt = parsed.submittedAt;
  }
  return { batchId: "aggregate", submittedAt: latestSubmittedAt, results: allResults };
}

export async function submitBatch(sessionId: string, confirmationBatchId: string): Promise<void> {
  await invoke("execute_batch_submission", {
    payload: { sessionId, confirmationBatchId },
  });
}

export async function clearJobData(sessionId: string): Promise<void> {
  await invoke("clear_job_application_data", { sessionId });
}
