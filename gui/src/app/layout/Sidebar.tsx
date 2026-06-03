import { getVisibleModuleViewModels, ModuleId, UserRole } from "../fixtureData";
import { DesktopRuntimeSnapshot } from "../../shared/desktop/desktopBridge";
import brandLogo from "../../../src-tauri/icons/logo.jpg";

type SidebarProps = {
  activeModuleId: ModuleId;
  desktopSnapshot: DesktopRuntimeSnapshot | null;
  currentUserRole: UserRole | null;
  onModuleChange: (moduleId: ModuleId) => void;
};

export function Sidebar({
  activeModuleId,
  desktopSnapshot,
  currentUserRole,
  onModuleChange,
}: SidebarProps) {
  const knowledgeBaseStatus = desktopSnapshot?.knowledgeBaseStatus ?? "checking";
  const statusLabel = knowledgeBaseStatus === "ready" ? "知识库 ready" : `知识库 ${knowledgeBaseStatus}`;
  const visibleModuleViewModels = getVisibleModuleViewModels(currentUserRole);

  return (
    <aside className="sidebar" aria-label="模块导航">
      <section className="brand-block">
        <img className="brand-mark" src={brandLogo} alt="Interview Agent Logo" />
        <h1>Interview Agent</h1>
      </section>

      <nav className="module-nav">
        {visibleModuleViewModels.map((moduleViewModel) => (
          <button
            className={moduleViewModel.id === activeModuleId ? "nav-button active" : "nav-button"}
            key={moduleViewModel.id}
            type="button"
            onClick={() => onModuleChange(moduleViewModel.id)}
          >
            <span>{moduleViewModel.label}</span>
          </button>
        ))}
      </nav>

      <section className="runtime-strip">
        <div className="status-pill">
          <span>{statusLabel}</span>
          <span className="status-dot" aria-hidden="true" />
        </div>
        {desktopSnapshot?.lastError && <p className="runtime-error">{desktopSnapshot.lastError}</p>}
      </section>
    </aside>
  );
}
