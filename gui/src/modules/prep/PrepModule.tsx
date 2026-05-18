import { PrepViewModel } from "../../shared/api/prep";

type PrepModuleProps = {
  viewModel: PrepViewModel;
};

export function PrepModule({ viewModel }: PrepModuleProps) {
  if (viewModel.status === "missing_inputs") {
    return (
      <div className="module-grid prep-module">
        <section className="content-panel wide">
          <p className="meta-label">材料状态</p>
          <h3>请先导入简历和 JD</h3>
          <p className="body-copy">缺少 {viewModel.missingInputs.join("、")}，补齐后展示匹配报告和准备摘要。</p>
        </section>
      </div>
    );
  }

  return (
    <div className="module-grid prep-module">
      <section className="content-panel wide">
        <p className="meta-label">匹配报告</p>
        <h3>{viewModel.jdSummary.role}匹配度：{viewModel.matchSummary.score}</h3>
        <div className="tag-row">
          {viewModel.matchSummary.strengths.map((strengthItem) => (
            <span className="tag" key={strengthItem}>{strengthItem}</span>
          ))}
        </div>
      </section>

      <section className="content-panel">
        <p className="meta-label">候选人画像</p>
        <h3>{viewModel.resumeSummary.name}</h3>
        <p className="body-copy">{viewModel.resumeSummary.headline}</p>
        <ul className="clean-list">
          {viewModel.resumeSummary.highlights.map((highlightItem) => (
            <li key={highlightItem}>{highlightItem}</li>
          ))}
        </ul>
      </section>

      <section className="content-panel">
        <p className="meta-label">岗位重点</p>
        <h3>{viewModel.jdSummary.role}</h3>
        <ul className="clean-list">
          {viewModel.jdSummary.focus.map((focusItem) => (
            <li key={focusItem}>{focusItem}</li>
          ))}
        </ul>
      </section>

      <section className="content-panel">
        <p className="meta-label">风险</p>
        <h3>面试前补强</h3>
        <ul className="clean-list">
          {viewModel.matchSummary.risks.map((riskItem) => (
            <li key={riskItem}>{riskItem}</li>
          ))}
        </ul>
      </section>

      <section className="content-panel">
        <p className="meta-label">追问重点</p>
        <h3>建议验证方向</h3>
        <ul className="clean-list">
          {viewModel.matchSummary.followUpFocus.map((followUpItem) => (
            <li key={followUpItem}>{followUpItem}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
