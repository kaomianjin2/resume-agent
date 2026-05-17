import { ModuleId, ModuleViewModel } from "../fixtureData";
import { Sidebar } from "./Sidebar";
import { Workspace } from "./Workspace";
import { ReviewPanel } from "./ReviewPanel";

type ShellLayoutProps = {
  activeModule: ModuleViewModel;
  activeModuleId: ModuleId;
  onModuleChange: (moduleId: ModuleId) => void;
};

export function ShellLayout({ activeModule, activeModuleId, onModuleChange }: ShellLayoutProps) {
  return (
    <main className="shell-layout">
      <Sidebar activeModuleId={activeModuleId} onModuleChange={onModuleChange} />
      <Workspace activeModule={activeModule} />
      <ReviewPanel activeModule={activeModule} />
    </main>
  );
}
