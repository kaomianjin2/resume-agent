import { invoke, isTauri } from "@tauri-apps/api/core";
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
  CollectionProgress,
  JobSearchProfile,
} from "../api/job";
import { normalizePrepViewModel, PrepViewModel } from "../api/prep";
import {
  DesktopRuntimeSnapshot,
  snapshotWithDesktopError as buildSnapshotWithDesktopError,
  webSnapshot,
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
  if (!isTauri()) {
    return webSnapshot;
  }
  return invoke<DesktopRuntimeSnapshot>("runtime_snapshot");
}

export function snapshotWithDesktopError(
  error: unknown,
  previousSnapshot: DesktopRuntimeSnapshot | null,
): DesktopRuntimeSnapshot {
  return buildSnapshotWithDesktopError(error, previousSnapshot, isTauri());
}

export async function startPythonRuntime(): Promise<DesktopRuntimeSnapshot> {
  if (!isTauri()) {
    return webSnapshot;
  }
  return invoke<DesktopRuntimeSnapshot>("start_python_runtime");
}

export async function stopPythonRuntime(): Promise<DesktopRuntimeSnapshot> {
  if (!isTauri()) {
    return webSnapshot;
  }
  return invoke<DesktopRuntimeSnapshot>("stop_python_runtime");
}

export async function selectMaterialFile(kind: MaterialKind): Promise<DesktopRuntimeSnapshot> {
  if (!isTauri()) {
    return webSnapshot;
  }

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
  if (!isTauri()) {
    return normalizePrepViewModel(null);
  }
  const rawViewModel = await invoke("prepare_interview_materials", { sessionId });
  return normalizePrepViewModel(rawViewModel);
}

export async function startMockInterview(request: StartMockInterviewRequest): Promise<MockInterviewViewModel> {
  if (!isTauri()) {
    throw new Error("仅桌面模式支持使用导入材料启动模拟面试");
  }
  const rawViewModel = await invoke("start_mock_interview", { payload: request });
  return normalizeMockInterviewViewModel(rawViewModel);
}

export async function startAlgorithmPractice(request: StartAlgorithmPracticeRequest): Promise<AlgorithmPracticeViewModel> {
  if (!isTauri()) {
    return normalizeAlgorithmPracticeViewModel(null);
  }
  const rawViewModel = await invoke("start_algorithm_practice", { payload: request });
  return normalizeAlgorithmPracticeViewModel(rawViewModel);
}

export async function submitMockAnswer(request: SubmitMockAnswerRequest): Promise<MockInterviewViewModel> {
  if (!isTauri()) {
    throw new Error("仅桌面模式支持提交真实模拟面试回答");
  }
  const rawViewModel = await invoke("submit_mock_answer", { payload: request });
  return normalizeMockInterviewViewModel(rawViewModel);
}

export async function endMockInterview(request: EndMockInterviewRequest): Promise<MockInterviewViewModel> {
  if (!isTauri()) {
    throw new Error("仅桌面模式支持结束真实模拟面试");
  }
  const rawViewModel = await invoke("end_mock_interview", { sessionId: request.sessionId });
  return normalizeMockInterviewViewModel(rawViewModel);
}

export async function listUsers(): Promise<UserRecord[]> {
  if (!isTauri()) {
    return [];
  }
  return invoke<UserRecord[]>("list_users");
}

export async function addUser(username: string, password: string, role: "admin" | "member"): Promise<UserRecord> {
  if (!isTauri()) {
    throw new Error("仅桌面模式支持新增用户");
  }
  return invoke<UserRecord>("add_user", {
    payload: { username, password, role },
  });
}

export async function updateUserStatus(username: string, status: "enabled" | "disabled"): Promise<boolean> {
  if (!isTauri()) {
    return false;
  }
  return invoke<boolean>("update_user_status", {
    payload: { username, status },
  });
}

export async function loginUser(username: string, password: string): Promise<UserRecord | null> {
  if (!isTauri()) {
    return null;
  }
  return invoke<UserRecord | null>("login_user", {
    payload: { username, password },
  });
}

export async function logoutUser(): Promise<void> {
  if (!isTauri()) {
    return;
  }
  await invoke("logout_user");
}

export async function prepareJobSearchProfile(
  sessionId: string,
  overrides?: Record<string, unknown>,
): Promise<JobSearchProfile> {
  if (!isTauri()) {
    throw new Error("仅桌面模式支持生成求职画像");
  }
  const rawViewModel = await invoke("prepare_job_search_profile", {
    sessionId,
    overrides: overrides ?? {},
  });
  return rawViewModel as unknown as JobSearchProfile;
}

export async function getJobCollectionProgress(sessionId: string): Promise<CollectionProgress> {
  if (!isTauri()) {
    throw new Error("仅桌面模式支持查看采集进度");
  }
  const rawViewModel = await invoke("get_job_collection_progress", { sessionId });
  return rawViewModel as unknown as CollectionProgress;
}

export async function retryFailedJobCollection(
  sessionId: string,
  collectionTaskId: string,
  platform: string,
): Promise<CollectionProgress> {
  if (!isTauri()) {
    throw new Error("仅桌面模式支持重试采集平台");
  }
  const rawViewModel = await invoke("retry_failed_job_collection_platform", {
    sessionId,
    collectionTaskId,
    platform,
  });
  return rawViewModel as unknown as CollectionProgress;
}
