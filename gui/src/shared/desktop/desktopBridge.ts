import { invoke, isTauri } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
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
        extensions: ["pdf", "docx", "doc", "md", "txt"],
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
