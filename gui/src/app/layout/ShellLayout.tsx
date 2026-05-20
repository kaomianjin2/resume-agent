import { ModuleId, ModuleViewModel } from "../fixtureData";
import { Sidebar } from "./Sidebar";
import { Workspace } from "./Workspace";
import { ReviewPanel } from "./ReviewPanel";
import { DesktopRuntimeSnapshot, MaterialKind } from "../../shared/desktop/desktopBridge";

type ShellLayoutProps = {
  activeModule: ModuleViewModel;
  activeModuleId: ModuleId;
  desktopSnapshot: DesktopRuntimeSnapshot | null;
  onModuleChange: (moduleId: ModuleId) => void;
  onSelectMaterialFile: (kind: MaterialKind) => void;
  onStartPythonRuntime: () => void;
  onStopPythonRuntime: () => void;
};

export function ShellLayout({
  activeModule,
  activeModuleId,
  desktopSnapshot,
  onModuleChange,
  onSelectMaterialFile,
  onStartPythonRuntime,
  onStopPythonRuntime,
}: ShellLayoutProps) {
  return (
    <main className="shell-layout">
      <Sidebar
        activeModuleId={activeModuleId}
        desktopSnapshot={desktopSnapshot}
        onModuleChange={onModuleChange}
        onSelectMaterialFile={onSelectMaterialFile}
        onStartPythonRuntime={onStartPythonRuntime}
        onStopPythonRuntime={onStopPythonRuntime}
      />
      <Workspace activeModule={activeModule} />
      <ReviewPanel activeModule={activeModule} />
    </main>
  );
}
