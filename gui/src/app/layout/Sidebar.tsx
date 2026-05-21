import { ModuleId, moduleViewModels } from "../fixtureData";
import { DesktopRuntimeSnapshot } from "../../shared/desktop/desktopBridge";

type SidebarProps = {
  activeModuleId: ModuleId;
  desktopSnapshot: DesktopRuntimeSnapshot | null;
  onModuleChange: (moduleId: ModuleId) => void;
};

export function Sidebar({
  activeModuleId,
  desktopSnapshot,
  onModuleChange,
}: SidebarProps) {
  const knowledgeBaseStatus = desktopSnapshot?.knowledgeBaseStatus ?? "checking";
  const statusLabel = knowledgeBaseStatus === "ready" ? "知识库 ready" : `知识库 ${knowledgeBaseStatus}`;

  return (
    <aside className="sidebar" aria-label="模块导航">
      <section className="brand-block">
        <span className="brand-mark" aria-hidden="true" />
        <h1>Interview Agent</h1>
        <p className="brand-subtitle">本地桌面面试工作台</p>
      </section>

      <nav className="module-nav">
        {moduleViewModels.map((moduleViewModel, moduleIndex) => (
          <button
            className={moduleViewModel.id === activeModuleId ? "nav-button active" : "nav-button"}
            key={moduleViewModel.id}
            type="button"
            onClick={() => onModuleChange(moduleViewModel.id)}
          >
            <span>{moduleViewModel.label}</span>
            <small>{String(moduleIndex + 1).padStart(2, "0")}</small>
          </button>
        ))}
      </nav>

      <section className="runtime-strip">
        <div className="status-pill">
          <span>{statusLabel}</span>
          <span className="status-dot" aria-hidden="true" />
        </div>
        <p>桌面壳调用现有 Python 后端，不改知识库构建和会话存储边界。</p>
        {desktopSnapshot?.lastError && <p className="runtime-error">{desktopSnapshot.lastError}</p>}
      </section>
    </aside>
  );
}
