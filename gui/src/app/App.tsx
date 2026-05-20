import { useEffect, useState } from "react";
import { ShellLayout } from "./layout/ShellLayout";
import { getModuleViewModel, ModuleId } from "./fixtureData";
import {
  DesktopRuntimeSnapshot,
  loadDesktopSnapshot,
  MaterialKind,
  selectMaterialFile,
  snapshotWithDesktopError,
  startPythonRuntime,
  stopPythonRuntime,
} from "../shared/desktop/desktopBridge";

export function App() {
  const [activeModuleId, setActiveModuleId] = useState<ModuleId>("prep");
  const [desktopSnapshot, setDesktopSnapshot] = useState<DesktopRuntimeSnapshot | null>(null);
  const activeModule = getModuleViewModel(activeModuleId);

  useEffect(() => {
    void handleDesktopAction(loadDesktopSnapshot);
  }, []);

  async function handleStartPythonRuntime() {
    await handleDesktopAction(startPythonRuntime);
  }

  async function handleStopPythonRuntime() {
    await handleDesktopAction(stopPythonRuntime);
  }

  async function handleSelectMaterialFile(kind: MaterialKind) {
    await handleDesktopAction(() => selectMaterialFile(kind));
  }

  async function handleDesktopAction(action: () => Promise<DesktopRuntimeSnapshot>) {
    try {
      setDesktopSnapshot(await action());
    } catch (error) {
      setDesktopSnapshot((currentSnapshot) => snapshotWithDesktopError(error, currentSnapshot));
    }
  }

  return (
    <ShellLayout
      activeModule={activeModule}
      activeModuleId={activeModuleId}
      desktopSnapshot={desktopSnapshot}
      onModuleChange={setActiveModuleId}
      onSelectMaterialFile={handleSelectMaterialFile}
      onStartPythonRuntime={handleStartPythonRuntime}
      onStopPythonRuntime={handleStopPythonRuntime}
    />
  );
}
