import { ChangeEvent, useState } from "react";
import {
  createIdleMockInterviewSession,
  endMockInterview,
  MockInterviewScenario,
  startMockInterview,
  submitMockInterviewAnswer,
} from "../../shared/api/mock";

export function MockModule() {
  const [scenario, setScenario] = useState<MockInterviewScenario>("default");
  const [answerDraft, setAnswerDraft] = useState("");
  const [session, setSession] = useState(() => createIdleMockInterviewSession());
  const viewModel = session.viewModel;
  const canSubmit = viewModel.status === "ready_for_answer" || viewModel.status === "answer_required";

  const handleStart = () => {
    setSession((previousSession) => startMockInterview(previousSession, scenario));
    setAnswerDraft("");
  };

  const handleSubmit = () => {
    setSession((previousSession) => submitMockInterviewAnswer(previousSession, answerDraft));
    if (answerDraft.trim()) {
      setAnswerDraft("");
    }
  };

  const handleEnd = () => {
    setSession((previousSession) => endMockInterview(previousSession));
    setAnswerDraft("");
  };

  const handleScenarioChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setScenario(event.target.value as MockInterviewScenario);
  };

  return (
    <div className="module-grid mock-module">
      <section className="content-panel wide">
        <p className="meta-label">当前回合</p>
        {viewModel.currentPrompt ? (
          <>
            <h3>{viewModel.currentPrompt.label}</h3>
            <p className="body-copy">{viewModel.currentPrompt.text}</p>
          </>
        ) : (
          <>
            <h3>{getSessionTitle(viewModel.status)}</h3>
            <p className="body-copy">{getSessionDescription(viewModel.status)}</p>
          </>
        )}
        <div className="tag-row">
          <span className="tag">题目进度 {viewModel.progress.currentQuestionIndex}/{viewModel.progress.totalQuestions}</span>
          <span className="tag">追问进度 {viewModel.progress.currentFollowupIndex}/{viewModel.progress.totalFollowups}</span>
          <span className="tag">状态 {getStatusLabel(viewModel.status)}</span>
        </div>
        {viewModel.errorMessage && <p className="status-copy error-text">{viewModel.errorMessage}</p>}
      </section>

      <section className="content-panel answer-pad">
        <p className="meta-label">开始与作答</p>
        <label className="field-label" htmlFor="mock-scenario">题集场景</label>
        <select id="mock-scenario" value={scenario} onChange={handleScenarioChange}>
          <option value="default">正常题集</option>
          <option value="empty">空题集</option>
        </select>
        <label className="field-label" htmlFor="mock-answer">当前题回答</label>
        <textarea
          id="mock-answer"
          className="mock-answer-input"
          value={answerDraft}
          onChange={(event) => setAnswerDraft(event.target.value)}
          placeholder={canSubmit ? "输入当前题回答，提交后继续追问或进入下一题。" : "点击开始模拟后输入回答。"}
        />
        <div className="action-row">
          <button className="primary-button" type="button" onClick={handleStart}>开始模拟</button>
          <button className="quiet-button" type="button" onClick={handleSubmit} disabled={!canSubmit}>提交回答</button>
          <button className="quiet-button" type="button" onClick={handleEnd}>结束当前模拟</button>
        </div>
      </section>

      <section className="content-panel followup-panel">
        <p className="meta-label">回答记录</p>
        <h3>{viewModel.transcript.length > 0 ? "已完成轮次" : "等待首轮回答"}</h3>
        {viewModel.transcript.length > 0 ? (
          <ul className="clean-list transcript-list">
            {viewModel.transcript.map((transcriptItem) => (
              <li key={`${transcriptItem.promptKind}-${transcriptItem.promptText}`}>
                <strong>{transcriptItem.promptKind === "question" ? "主问题" : "追问"}：</strong>
                {transcriptItem.promptText}
                <br />
                <span className="body-copy">回答：{transcriptItem.answer}</span>
                <br />
                <span className="body-copy">评分：{transcriptItem.score}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-surface">开始模拟后一次只展示当前题；提交后在这里累计当前回合记录。</div>
        )}
      </section>

      <section className="content-panel">
        <p className="meta-label">评审面板</p>
        {viewModel.reviewPanel ? (
          <>
            <h3>平均分 {viewModel.reviewPanel.averageScore}</h3>
            <p className="field-label">风险</p>
            <ul className="clean-list">
              {viewModel.reviewPanel.risks.map((riskItem) => (
                <li key={riskItem}>{riskItem}</li>
              ))}
            </ul>
            <p className="field-label">改进建议</p>
            <ul className="clean-list">
              {viewModel.reviewPanel.suggestions.map((suggestionItem) => (
                <li key={suggestionItem}>{suggestionItem}</li>
              ))}
            </ul>
          </>
        ) : (
          <>
            <h3>等待回合结束</h3>
            <p className="body-copy">完成当前题集后展示评分、风险和改进建议。</p>
          </>
        )}
      </section>
    </div>
  );
}

function getSessionTitle(status: string): string {
  if (status === "failed") {
    return "题集生成失败";
  }
  if (status === "completed") {
    return "模拟面试已完成";
  }
  if (status === "ended") {
    return "本轮模拟已结束";
  }
  return "等待开始模拟";
}

function getSessionDescription(status: string): string {
  if (status === "failed") {
    return "当前场景没有可用题目，请切回正常题集重新开始。";
  }
  if (status === "completed") {
    return "本轮问题和追问已结束，可查看右侧评审面板或重新开始。";
  }
  if (status === "ended") {
    return "当前模拟已清空，不会把中断状态带入下一轮。";
  }
  return "先生成层层递进的问题，再逐题问答并按回答生成追问。";
}

function getStatusLabel(status: string): string {
  if (status === "ready_for_answer") {
    return "待回答";
  }
  if (status === "answer_required") {
    return "缺少回答";
  }
  if (status === "completed") {
    return "已完成";
  }
  if (status === "failed") {
    return "失败";
  }
  if (status === "ended") {
    return "已结束";
  }
  return "未开始";
}
