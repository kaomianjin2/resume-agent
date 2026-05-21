import { PrepViewModel } from "../../shared/api/prep";

type PrepModuleProps = {
  viewModel: PrepViewModel;
};

export function PrepModule({ viewModel }: PrepModuleProps) {
  if (viewModel.status === "missing_inputs") {
    return (
      <div className="prep-module">
        <section className="problem-card">
          <div className="problem-card-body">
            <p className="meta-label">准备摘要</p>
            <h3>把材料先翻译成能直接使用的面试语言</h3>
            <p className="body-copy">这一页只保留结论和追问方向，不展示原始结构化输出。</p>
          </div>
        </section>
        <section className="prep-board">
          <p className="meta-label">材料状态</p>
          <h3>请先导入简历和 JD</h3>
          <p className="body-copy">缺少 {viewModel.missingInputs.join("、")}，补齐后展示匹配报告和准备摘要。</p>
        </section>
      </div>
    );
  }

  return (
    <div className="prep-module">
      <section className="problem-card">
        <div className="problem-card-body">
          <p className="meta-label">准备摘要</p>
          <h3>把材料先翻译成能直接使用的面试语言</h3>
          <p className="body-copy">这一页只保留结论和追问方向，不展示原始结构化输出。</p>
          <div className="summary-strip">
            <span className="tag">简历强项</span>
            <span className="tag">岗位重点</span>
            <span className="tag">追问缺口</span>
          </div>
        </div>
      </section>

      <section className="prep-board">
        <div className="prep-board-head">
          <span className="meta-label">准备包预览</span>
          <span className="body-copy">先看懂，再去模拟面试模块生成题目和追问</span>
        </div>
        <div className="prep-board-body">
          <article className="prep-row">
            <div className="prep-row-label">简历摘要</div>
            <div className="prep-row-text">
              <strong>{viewModel.resumeSummary.name}</strong>：{viewModel.resumeSummary.headline}；{viewModel.resumeSummary.highlights.join("、")}。
            </div>
          </article>
          <article className="prep-row">
            <div className="prep-row-label">岗位重点</div>
            <div className="prep-row-text">
              岗位关注 <strong>{viewModel.jdSummary.role}</strong> 的核心能力，包括 {viewModel.jdSummary.focus.join("、")}。
            </div>
          </article>
          <article className="prep-row">
            <div className="prep-row-label">匹配度</div>
            <div className="prep-row-text">
              整体匹配度 <strong>{viewModel.matchSummary.score} / 100</strong>，匹配报告可直接用于模拟面试。
            </div>
          </article>
          <article className="prep-row">
            <div className="prep-row-label">优势</div>
            <div className="prep-row-text">
              {viewModel.matchSummary.strengths.join("、")}
            </div>
          </article>
          <article className="prep-row">
            <div className="prep-row-label">风险</div>
            <div className="prep-row-text">
              {viewModel.matchSummary.risks.join("、")}
            </div>
          </article>
          <article className="prep-row">
            <div className="prep-row-label">追问重点</div>
            <div className="prep-row-text">
              {viewModel.matchSummary.followUpFocus.join("、")}
            </div>
          </article>
        </div>
      </section>
    </div>
  );
}
