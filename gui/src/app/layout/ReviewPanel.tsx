import { ModuleViewModel } from "../fixtureData";

type ReviewPanelProps = {
  activeModule: ModuleViewModel;
};

const statusText = {
  ready: "就绪",
  review: "待检查",
  blocked: "未启用",
};

export function ReviewPanel({ activeModule }: ReviewPanelProps) {
  return (
    <aside className="review-panel" aria-label="检查面板">
      <header>
        <p className="meta-label">Review Panel</p>
        <h2>{activeModule.label}检查</h2>
      </header>

      <div className="check-list">
        {activeModule.checks.map((checkItem) => (
          <article className={`check-item ${checkItem.status}`} key={checkItem.label}>
            <div>
              <h3>{checkItem.label}</h3>
              <p>{checkItem.detail}</p>
            </div>
            <span>{statusText[checkItem.status]}</span>
          </article>
        ))}
      </div>

      <section className="review-note">
        <h3>当前边界</h3>
        <p>本阶段只验证 Web Shell 壳层、模块切换和 fixture 数据展示。</p>
      </section>
    </aside>
  );
}
