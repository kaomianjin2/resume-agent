import { useEffect, useState } from "react";
import { ShellLayout } from "./layout/ShellLayout";
import { getModuleViewModel, ModuleId } from "./fixtureData";
import {
  DesktopRuntimeSnapshot,
  loadDesktopSnapshot,
  MaterialKind,
  selectMaterialFile,
  snapshotWithDesktopError,
} from "../shared/desktop/desktopBridge";
import { getPrepViewModel } from "../shared/api/prep";

export function App() {
  const [activeModuleId, setActiveModuleId] = useState<ModuleId>("prep");
  const [desktopSnapshot, setDesktopSnapshot] = useState<DesktopRuntimeSnapshot | null>(null);
  const activeModule = getModuleViewModel(activeModuleId);
  const prepViewModel = getPrepViewModel();

  useEffect(() => {
    void handleDesktopAction(loadDesktopSnapshot);
  }, []);

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
      prepViewModel={prepViewModel}
      onModuleChange={setActiveModuleId}
      onSelectMaterialFile={handleSelectMaterialFile}
    />
  );
}
