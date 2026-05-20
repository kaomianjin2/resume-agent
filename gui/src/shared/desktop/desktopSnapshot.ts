export type DesktopRuntimeSnapshot = {
  isDesktopShell: boolean;
  pythonRuntimeRunning: boolean;
  knowledgeBaseStatus: string;
  configPath: string;
  resumePath: string | null;
  jdPath: string | null;
  lastError: string | null;
};

export const webSnapshot: DesktopRuntimeSnapshot = {
  isDesktopShell: false,
  pythonRuntimeRunning: false,
  knowledgeBaseStatus: "web-shell",
  configPath: "config/interview-agent.toml",
  resumePath: null,
  jdPath: null,
  lastError: null,
};

export function snapshotWithDesktopError(
  error: unknown,
  previousSnapshot: DesktopRuntimeSnapshot | null,
  isDesktopShell: boolean,
): DesktopRuntimeSnapshot {
  const fallbackSnapshot = {
    ...webSnapshot,
    isDesktopShell,
    knowledgeBaseStatus: "unavailable",
  };
  const errorMessage = error instanceof Error ? error.message : String(error);
  return {
    ...(previousSnapshot ?? fallbackSnapshot),
    lastError: errorMessage,
  };
}
