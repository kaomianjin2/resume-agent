import { PrepViewModel } from "../../shared/api/prep.js";

type PrepModuleProps = {
  viewModel: PrepViewModel;
  isLoading?: boolean;
};

export function PrepModule({ viewModel, isLoading = false }: PrepModuleProps) {
  const hasResumeSummary = Boolean(
    viewModel.resumeSummary.name ||
    viewModel.resumeSummary.headline ||
    viewModel.resumeSummary.highlights.length > 0
  );
  const hasJdSummary = Boolean(viewModel.jdSummary.role || viewModel.jdSummary.focus.length > 0);
  const hasMatchSummary = viewModel.matchSummary.score !== "未评分" ||
    viewModel.matchSummary.strengths.length > 0 ||
    viewModel.matchSummary.risks.length > 0 ||
    viewModel.matchSummary.followUpFocus.length > 0;

  if (isLoading) {
    return (
      <div className="prep-module">
        <section className="problem-card">
          <div className="problem-card-body">
            <p className="meta-label">准备摘要</p>
            <h3>正在解析导入材料</h3>
            <p className="body-copy">按顺序整理简历、JD 和匹配报告，完成后展示可直接用于模拟面试的摘要。</p>
          </div>
        </section>
        <section className="prep-board">
          <div className="prep-board-head">
            <span className="meta-label">解析进程</span>
            <span className="body-copy">正在更新准备包预览</span>
          </div>
          <div className="prep-board-body">
            <article className="prep-row">
              <div className="prep-row-label">当前状态</div>
              <div className="prep-row-text">正在解析已导入材料。</div>
            </article>
          </div>
        </section>
      </div>
    );
  }

  if (viewModel.status === "failed") {
    return (
      <div className="prep-module">
        <section className="problem-card">
          <div className="problem-card-body">
            <p className="meta-label">准备摘要</p>
            <h3>材料解析失败</h3>
            <p className="body-copy">请重新导入可解析的简历或 JD 文件。</p>
          </div>
        </section>
        <section className="prep-board">
          <div className="prep-board-head">
            <span className="meta-label">解析状态</span>
            <span className="body-copy">准备包未更新</span>
          </div>
          <div className="prep-board-body">
            <article className="prep-row">
              <div className="prep-row-label">失败原因</div>
              <div className="prep-row-text error-text">{viewModel.errorMessage || "材料解析失败。"}</div>
            </article>
          </div>
        </section>
      </div>
    );
  }

  if (viewModel.status === "missing_inputs") {
    const missingInputLabels = viewModel.missingInputs.map(getMissingInputLabel);
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
          <div className="prep-board-head">
            <span className="meta-label">材料状态</span>
            <span className="body-copy">{hasJdSummary ? "JD 已导入，补齐简历后生成匹配报告" : "补齐材料后展示准备包预览"}</span>
          </div>
          <div className="prep-board-body">
            <article className="prep-row">
              <div className="prep-row-label">简历摘要</div>
              <div className="prep-row-text">缺少 <strong>{missingInputLabels.join("、") || "简历"}</strong>，导入后展示候选人摘要。</div>
            </article>
            <article className="prep-row">
              <div className="prep-row-label">岗位重点</div>
              <div className="prep-row-text">{hasJdSummary ? formatJdSummary(viewModel) : "导入 JD 后展示角色、技术栈和核心经验要求。"}</div>
            </article>
            <article className="prep-row">
              <div className="prep-row-label">匹配度</div>
              <div className="prep-row-text">补齐简历和 JD 后生成整体匹配度。</div>
            </article>
            <article className="prep-row">
              <div className="prep-row-label">优势</div>
              <div className="prep-row-text">匹配报告生成后展示可优先展开的候选人优势。</div>
            </article>
            <article className="prep-row">
              <div className="prep-row-label">风险</div>
              <div className="prep-row-text">匹配报告生成后展示经验缺口和需要补证据的风险点。</div>
            </article>
            <article className="prep-row">
              <div className="prep-row-label">追问重点</div>
              <div className="prep-row-text">匹配报告生成后展示模拟面试优先追问方向。</div>
            </article>
          </div>
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
            <div className="prep-row-text">{hasResumeSummary ? formatResumeSummary(viewModel) : "简历解析结果为空，请重新导入可解析的简历。"}</div>
          </article>
          <article className="prep-row">
            <div className="prep-row-label">岗位重点</div>
            <div className="prep-row-text">{hasJdSummary ? formatJdSummary(viewModel) : "JD 解析结果为空，请重新导入可解析的 JD。"}</div>
          </article>
          <article className="prep-row">
            <div className="prep-row-label">匹配度</div>
            <div className="prep-row-text">
              {hasMatchSummary ? <>整体匹配度 <strong>{viewModel.matchSummary.score} / 100</strong>，匹配报告可直接用于模拟面试。</> : "补齐简历和 JD 后生成整体匹配度。"}
            </div>
          </article>
          <article className="prep-row">
            <div className="prep-row-label">优势</div>
            <div className="prep-row-text">{formatMatchList(viewModel.matchSummary.strengths, "匹配报告生成后展示可优先展开的候选人优势。")}</div>
          </article>
          <article className="prep-row">
            <div className="prep-row-label">风险</div>
            <div className="prep-row-text">{formatMatchList(viewModel.matchSummary.risks, "匹配报告生成后展示经验缺口和需要补证据的风险点。")}</div>
          </article>
          <article className="prep-row">
            <div className="prep-row-label">追问重点</div>
            <div className="prep-row-text">{formatMatchList(viewModel.matchSummary.followUpFocus, "匹配报告生成后展示模拟面试优先追问方向。")}</div>
          </article>
        </div>
      </section>
    </div>
  );
}

function formatResumeSummary(viewModel: PrepViewModel): string {
  const summaryParts = [
    viewModel.resumeSummary.name,
    viewModel.resumeSummary.headline,
    viewModel.resumeSummary.highlights.join("、"),
  ].filter(Boolean);
  return summaryParts.join("；");
}

function formatJdSummary(viewModel: PrepViewModel): string {
  const focusText = viewModel.jdSummary.focus.join("、");
  if (viewModel.jdSummary.role && focusText) {
    return `岗位关注 ${viewModel.jdSummary.role} 的核心能力，包括 ${focusText}。`;
  }
  if (viewModel.jdSummary.role) {
    return `岗位关注 ${viewModel.jdSummary.role}。`;
  }
  return focusText || "JD 解析结果为空，请重新导入可解析的 JD。";
}

function getMissingInputLabel(missingInput: string): string {
  if (missingInput === "resume_text") {
    return "简历";
  }
  if (missingInput === "jd_text") {
    return "JD";
  }
  return missingInput;
}

function formatMatchList(items: string[], fallback: string): string {
  return items.length > 0 ? items.join("、") : fallback;
}
