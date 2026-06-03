import { ChangeEvent, useState } from "react";
import {
  createFallbackMockInterviewClient,
  MATERIALS_REQUIRED_ERROR,
  MockInterviewQuestionType,
  MockInterviewScenario,
  MockInterviewRuntimeClient,
  MockInterviewViewModel,
} from "../../shared/api/mock.js";

const MOCK_SESSION_ID = "gui-mock-session";
const fallbackRuntimeClient = createFallbackMockInterviewClient();
const QUESTION_COUNT_OPTIONS = [3, 5, 8];
const QUESTION_TYPE_OPTIONS: MockInterviewQuestionType[] = ["行为面试", "项目深挖", "技术基础", "系统设计"];
const FOLLOWUP_ROUND_OPTIONS = [0, 1, 2, 3];

type MockModuleProps = {
  materialsReady: boolean;
  runtimeClient?: MockInterviewRuntimeClient;
};

export function MockModule({ materialsReady, runtimeClient = fallbackRuntimeClient }: MockModuleProps) {
  const [scenario, setScenario] = useState<MockInterviewScenario>("default");
  const [questionCount, setQuestionCount] = useState(5);
  const [questionType, setQuestionType] = useState<MockInterviewQuestionType>("行为面试");
  const [followupRounds, setFollowupRounds] = useState(1);
  const [answerDraft, setAnswerDraft] = useState("");
  const [viewModel, setViewModel] = useState<MockInterviewViewModel>(() => runtimeClient.getCurrentViewModel());
  const canSubmit = viewModel.status === "ready_for_answer" || viewModel.status === "answer_required";

  const handleStart = async () => {
    if (!materialsReady) {
      setViewModel({
        ...runtimeClient.getCurrentViewModel(),
        status: "failed",
        errorMessage: MATERIALS_REQUIRED_ERROR,
      });
      return;
    }
    setViewModel(
      await runtimeClient.startMockInterview({
        sessionId: MOCK_SESSION_ID,
        targetRole: "后端工程师",
        questionCount,
        followupRounds,
        questionType,
        scenario,
      }),
    );
    setAnswerDraft("");
  };

  const handleSubmit = async () => {
    setViewModel(await runtimeClient.submitMockAnswer({ sessionId: MOCK_SESSION_ID, answer: answerDraft }));
    if (answerDraft.trim()) {
      setAnswerDraft("");
    }
  };

  const handleEnd = async () => {
    setViewModel(await runtimeClient.endMockInterview({ sessionId: MOCK_SESSION_ID }));
    setAnswerDraft("");
  };

  const handleScenarioChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setScenario(event.target.value as MockInterviewScenario);
  };

  const handleQuestionCountChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setQuestionCount(Number(event.target.value));
  };

  const handleQuestionTypeChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setQuestionType(event.target.value as MockInterviewQuestionType);
  };

  const handleFollowupRoundsChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setFollowupRounds(Number(event.target.value));
  };

  return (
    <div className="mock-module">
      <section className="problem-card mock-current-card">
        <div className="problem-card-body">
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
        <div className="tag-row mock-status-row">
          <span className="tag">题目进度 {viewModel.progress.currentQuestionIndex}/{viewModel.progress.totalQuestions}</span>
          <span className="tag">追问进度 {viewModel.progress.currentFollowupIndex}/{viewModel.progress.totalFollowups}</span>
          <span className="tag">状态 {getStatusLabel(viewModel.status)}</span>
        </div>
        {!materialsReady && <p className="status-copy error-text">{MATERIALS_REQUIRED_ERROR}</p>}
        {viewModel.errorMessage && <p className="status-copy error-text">{viewModel.errorMessage}</p>}
        </div>
      </section>

      <div className="mock-workbench-grid">
        <section className="prep-board mock-config-panel">
          <div className="prep-board-head">
            <span className="meta-label">配置区</span>
            <span className="meta-label">启动前选择题集</span>
          </div>
          <div className="mock-config-body">
            <div className="mock-config-row">
              <label className="field-label" htmlFor="mock-scenario">题集场景</label>
              <select id="mock-scenario" value={scenario} onChange={handleScenarioChange}>
                <option value="default">正常题集</option>
                <option value="empty">空题集</option>
              </select>
            </div>
            <div className="mock-config-row">
              <label className="field-label" htmlFor="mock-question-count">题目数</label>
              <select id="mock-question-count" value={questionCount} onChange={handleQuestionCountChange}>
                {QUESTION_COUNT_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <div className="mock-config-row">
              <label className="field-label" htmlFor="mock-question-type">题型</label>
              <select id="mock-question-type" value={questionType} onChange={handleQuestionTypeChange}>
                {QUESTION_TYPE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <div className="mock-config-row">
              <label className="field-label" htmlFor="mock-followup-rounds">追问轮数</label>
              <select id="mock-followup-rounds" value={followupRounds} onChange={handleFollowupRoundsChange}>
                {FOLLOWUP_ROUND_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            <div className="action-row mock-action-row">
              <button className="primary-button" type="button" onClick={handleStart} disabled={!materialsReady}>
                开始模拟
              </button>
              <button className="quiet-button" type="button" onClick={handleEnd}>
                结束当前模拟
              </button>
            </div>
          </div>
        </section>

        <section className="prep-board mock-answer-panel">
          <div className="prep-board-head">
            <span className="meta-label">作答区</span>
            <span className="meta-label">{canSubmit ? "等待提交" : "等待开始"}</span>
          </div>
          <label className="field-label" htmlFor="mock-answer">当前题回答</label>
          <textarea
            id="mock-answer"
            className="mock-answer-input"
            value={answerDraft}
            onChange={(event) => setAnswerDraft(event.target.value)}
            placeholder={canSubmit ? "输入当前题回答，提交后继续追问或进入下一题。" : "点击开始模拟后输入回答。"}
          />
          <div className="action-row mock-action-row">
            <button className="quiet-button" type="button" onClick={handleSubmit} disabled={!canSubmit}>提交回答</button>
          </div>
        </section>
      </div>

      <section className="prep-board mock-record-panel">
        <div className="prep-board-head">
        <p className="meta-label">回答记录</p>
        <h3>{viewModel.transcript.length > 0 ? "已完成轮次" : "等待首轮回答"}</h3>
        </div>
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

      <section className="content-panel mock-review-summary">
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
