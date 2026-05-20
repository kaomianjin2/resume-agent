import { invoke, isTauri } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import {
  DesktopRuntimeSnapshot,
  snapshotWithDesktopError as buildSnapshotWithDesktopError,
  webSnapshot,
} from "./desktopSnapshot";

export type MaterialKind = "resume" | "jd";
export type { DesktopRuntimeSnapshot };

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
