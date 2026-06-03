import { ModuleViewModel } from "../fixtureData";
import { PrepViewModel } from "../../shared/api/prep";

type ReviewPanelProps = {
  activeModule: ModuleViewModel;
  prepViewModel: PrepViewModel;
};

const statusText = {
  ready: "就绪",
  review: "待检查",
  blocked: "未启用",
};

export function ReviewPanel({ activeModule, prepViewModel }: ReviewPanelProps) {
  if (activeModule.id === "prep") {
    const reviewState = buildPrepReviewState(prepViewModel);
    return (
      <aside className="review-panel" aria-label="检查面板">
        <header className="review-head">
          <div>
            <h2>准备检查</h2>
            <p className="body-copy">展示解析完整度、匹配度和可追问点。</p>
          </div>
        </header>

        <section className="score-card">
          <div className="metric-label">准备完整度</div>
          <div className="score">{reviewState.completeness}</div>
          <p className="body-copy">{reviewState.summary}</p>
        </section>

        <section className="metrics">
          <div className="metric">
            <div className="metric-label">匹配度</div>
            <div className="metric-value">{reviewState.matchScore}</div>
          </div>
          <div className="metric">
            <div className="metric-label">追问点</div>
            <div className="metric-value">{reviewState.followUpCount} 个</div>
          </div>
          <div className="metric">
            <div className="metric-label">材料状态</div>
            <div className="metric-value">{reviewState.materialStatus}</div>
          </div>
        </section>

        <section className="suggestions">
          <article className="suggestion">
            <strong>补齐项目背景</strong>
            <span>先整理核心项目的规模、目标和个人职责，便于追问时快速展开。</span>
          </article>
          <article className="suggestion">
            <strong>优先准备弱项</strong>
            <span>围绕匹配度最低的知识点做重点复习，避免模拟面试只覆盖强项。</span>
          </article>
          <article className="suggestion">
            <strong>保留常见问题</strong>
            <span>生成 10 到 15 个高频追问即可，正式题目留到模拟面试模块处理。</span>
          </article>
        </section>
      </aside>
    );
  }

  const readyCount = activeModule.checks.filter((checkItem) => checkItem.status === "ready").length;
  const reviewCount = activeModule.checks.filter((checkItem) => checkItem.status === "review").length;
  const blockedCount = activeModule.checks.filter((checkItem) => checkItem.status === "blocked").length;
  const score = Math.round((readyCount / activeModule.checks.length) * 100);

  return (
    <aside className="review-panel" aria-label="检查面板">
      <header className="review-head">
        <div>
          <h2>{activeModule.label}检查</h2>
          <p className="body-copy">展示解析完整度、匹配度和可追问点。</p>
        </div>
      </header>

      <section className="score-card">
        <div className="metric-label">准备完整度</div>
        <div className="score">{score}</div>
        <p className="body-copy">{activeModule.summary}</p>
      </section>

      <section className="metrics">
        <div className="metric">
          <div className="metric-label">就绪项</div>
          <div className="metric-value">{readyCount} 个</div>
        </div>
        <div className="metric">
          <div className="metric-label">待检查</div>
          <div className="metric-value">{reviewCount} 个</div>
        </div>
        <div className="metric">
          <div className="metric-label">边界项</div>
          <div className="metric-value">{blockedCount} 个</div>
        </div>
      </section>

      <section className="suggestions">
        {activeModule.checks.map((checkItem) => (
          <article className="suggestion" key={checkItem.label}>
            <strong>{checkItem.label}</strong>
            <span>{statusText[checkItem.status]}：{checkItem.detail}</span>
          </article>
        ))}
      </section>
    </aside>
  );
}

function buildPrepReviewState(prepViewModel: PrepViewModel) {
  const hasResumeSummary = Boolean(
    prepViewModel.resumeSummary.name ||
    prepViewModel.resumeSummary.headline ||
    prepViewModel.resumeSummary.highlights.length > 0
  );
  const hasJdSummary = Boolean(prepViewModel.jdSummary.role || prepViewModel.jdSummary.focus.length > 0);
  const hasMatchSummary = prepViewModel.matchSummary.score !== "未评分" ||
    prepViewModel.matchSummary.strengths.length > 0 ||
    prepViewModel.matchSummary.risks.length > 0 ||
    prepViewModel.matchSummary.followUpFocus.length > 0;

  if (prepViewModel.status === "failed") {
    return {
      completeness: 0,
      summary: prepViewModel.errorMessage || "材料解析失败，请重新导入。",
      matchScore: "未评分",
      followUpCount: 0,
      materialStatus: "解析失败",
    };
  }

  const completedStepCount = [hasResumeSummary, hasJdSummary, hasMatchSummary].filter(Boolean).length;
  const completeness = Math.round((completedStepCount / 3) * 100);
  const matchScore = typeof prepViewModel.matchSummary.score === "number"
    ? `${prepViewModel.matchSummary.score} / 100`
    : prepViewModel.matchSummary.score;
  const followUpCount = prepViewModel.matchSummary.followUpFocus.length;
  const materialStatus = hasMatchSummary ? "已整理" : hasResumeSummary || hasJdSummary ? "解析中" : "待导入";

  return {
    completeness,
    summary: hasMatchSummary
      ? "简历 / JD 已完成解析，匹配报告可直接用于模拟面试。"
      : "导入简历和 JD 后展示匹配报告与可追问点。",
    matchScore,
    followUpCount,
    materialStatus,
  };
}
