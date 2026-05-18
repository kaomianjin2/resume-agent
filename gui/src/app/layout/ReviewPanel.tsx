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
        <p>{activeModule.id === "prep" ? "面试准备已对齐 runtime facade 的准备结果结构。" : "本模块仍使用 Web Shell fixture 数据展示。"}</p>
      </section>
    </aside>
  );
}
