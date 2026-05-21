import { ModuleId, ModuleViewModel } from "../fixtureData";
import { Sidebar } from "./Sidebar";
import { Workspace } from "./Workspace";
import { ReviewPanel } from "./ReviewPanel";
import { DesktopRuntimeSnapshot, MaterialKind } from "../../shared/desktop/desktopBridge";
import { PrepViewModel } from "../../shared/api/prep";

type ShellLayoutProps = {
  activeModule: ModuleViewModel;
  activeModuleId: ModuleId;
  desktopSnapshot: DesktopRuntimeSnapshot | null;
  prepViewModel: PrepViewModel;
  onModuleChange: (moduleId: ModuleId) => void;
  onSelectMaterialFile: (kind: MaterialKind) => void;
};

export function ShellLayout({
  activeModule,
  activeModuleId,
  desktopSnapshot,
  prepViewModel,
  onModuleChange,
  onSelectMaterialFile,
}: ShellLayoutProps) {
  return (
    <main className="shell-layout">
      <Sidebar
        activeModuleId={activeModuleId}
        desktopSnapshot={desktopSnapshot}
        onModuleChange={onModuleChange}
      />
      <Workspace
        activeModule={activeModule}
        prepViewModel={prepViewModel}
        onSelectMaterialFile={onSelectMaterialFile}
      />
      <ReviewPanel activeModule={activeModule} prepViewModel={prepViewModel} />
    </main>
  );
}
