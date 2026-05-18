import { ModuleId, moduleViewModels } from "../fixtureData";

type SidebarProps = {
  activeModuleId: ModuleId;
  onModuleChange: (moduleId: ModuleId) => void;
};

export function Sidebar({ activeModuleId, onModuleChange }: SidebarProps) {
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
          <strong>Runtime facade</strong>
          <p>面试准备已对齐真实会话数据形状。</p>
        </div>
      </section>
    </aside>
  );
}
