import { ModuleId, moduleViewModels } from "../fixtureData";
import { DesktopRuntimeSnapshot, MaterialKind } from "../../shared/desktop/desktopBridge";

type SidebarProps = {
  activeModuleId: ModuleId;
  desktopSnapshot: DesktopRuntimeSnapshot | null;
  onModuleChange: (moduleId: ModuleId) => void;
  onSelectMaterialFile: (kind: MaterialKind) => void;
  onStartPythonRuntime: () => void;
  onStopPythonRuntime: () => void;
};

export function Sidebar({
  activeModuleId,
  desktopSnapshot,
  onModuleChange,
  onSelectMaterialFile,
  onStartPythonRuntime,
  onStopPythonRuntime,
}: SidebarProps) {
  const runtimeLabel = desktopSnapshot?.isDesktopShell ? "Desktop shell" : "Web shell";
  const runtimeStatus = desktopSnapshot?.pythonRuntimeRunning ? "Python 运行中" : "Python 未启动";
  const knowledgeBaseStatus = desktopSnapshot?.knowledgeBaseStatus ?? "checking";

  return (
    <aside className="sidebar" aria-label="模块导航">
      <section className="brand-block">
        <span className="brand-mark">IA</span>
        <div>
          <p className="meta-label">Interview Agent</p>
          <h1>面试工作台</h1>
        </div>
      </section>

      <nav className="module-nav">
        {moduleViewModels.map((moduleViewModel) => (
          <button
            className={moduleViewModel.id === activeModuleId ? "nav-button active" : "nav-button"}
            key={moduleViewModel.id}
            type="button"
            onClick={() => onModuleChange(moduleViewModel.id)}
          >
            <span>{moduleViewModel.label}</span>
            <small>{moduleViewModel.eyebrow}</small>
          </button>
        ))}
      </nav>

      <section className="runtime-strip">
        <span className="status-dot" aria-hidden="true" />
        <div>
          <strong>{runtimeLabel}</strong>
          <p>KB {knowledgeBaseStatus} · {runtimeStatus}</p>
          <div className="runtime-actions">
            <button type="button" onClick={onStartPythonRuntime}>启动</button>
            <button type="button" onClick={onStopPythonRuntime}>停止</button>
            <button type="button" onClick={() => onSelectMaterialFile("resume")}>简历</button>
            <button type="button" onClick={() => onSelectMaterialFile("jd")}>JD</button>
          </div>
          <p className="file-choice">简历：{desktopSnapshot?.resumePath ?? "未选择"}</p>
          <p className="file-choice">JD：{desktopSnapshot?.jdPath ?? "未选择"}</p>
          {desktopSnapshot?.lastError && <p className="runtime-error">{desktopSnapshot.lastError}</p>}
        </div>
      </section>
    </aside>
  );
}
