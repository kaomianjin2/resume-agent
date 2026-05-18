export type MockInterviewScenario = "default" | "empty";

export type MockInterviewStatus =
  | "idle"
  | "ready_for_answer"
  | "answer_required"
  | "completed"
  | "failed"
  | "ended";

export type MockInterviewViewModel = {
  sessionId: string;
  status: MockInterviewStatus;
  errorMessage: string | null;
  currentPrompt: {
    kind: "question" | "followup";
    label: string;
    text: string;
  } | null;
  progress: {
    currentQuestionIndex: number;
    totalQuestions: number;
    currentFollowupIndex: number;
    totalFollowups: number;
  };
  reviewPanel: {
    averageScore: number;
    risks: string[];
    suggestions: string[];
  } | null;
  transcript: Array<{
    promptKind: "question" | "followup";
    promptText: string;
    answer: string;
    score: number;
  }>;
};

type ScoreReport = {
  score: number;
  risks: string[];
  suggestions: string[];
};

export type MockInterviewSession = {
  scenario: MockInterviewScenario;
  questions: string[];
  currentQuestionIndex: number;
  pendingFollowups: string[];
  currentFollowupIndex: number;
  totalFollowups: number;
  currentPromptKind: "question" | "followup" | null;
  currentPromptText: string;
  transcript: MockInterviewViewModel["transcript"];
  scoreReports: ScoreReport[];
  viewModel: MockInterviewViewModel;
};

const DEFAULT_SESSION_ID = "fixture-mock-session";
const DEFAULT_QUESTIONS = [
  "介绍你最近一次线上延迟排查。",
  "如果延迟再次出现，你会如何设计预防机制？",
];

const FOLLOWUP_BY_QUESTION: Record<string, string[]> = {
  "介绍你最近一次线上延迟排查。": ["你如何判断瓶颈在数据库？"],
};

const SCORE_REPORT_BY_PROMPT: Record<string, ScoreReport> = {
  "介绍你最近一次线上延迟排查。": {
    score: 8,
    risks: [],
    suggestions: [],
  },
  "你如何判断瓶颈在数据库？": {
    score: 6,
    risks: ["缺少数据库瓶颈判定证据"],
    suggestions: ["补充监控指标、定位步骤和验证闭环"],
  },
  "如果延迟再次出现，你会如何设计预防机制？": {
    score: 7,
    risks: ["预防方案还不够具体"],
    suggestions: ["说明告警阈值、容量治理和复盘机制"],
  },
};

export function createIdleMockInterviewSession(): MockInterviewSession {
  const viewModel: MockInterviewViewModel = {
    sessionId: DEFAULT_SESSION_ID,
    status: "idle",
    errorMessage: null,
    currentPrompt: null,
    progress: {
      currentQuestionIndex: 0,
      totalQuestions: 0,
      currentFollowupIndex: 0,
      totalFollowups: 0,
    },
    reviewPanel: null,
    transcript: [],
  };

  return {
    scenario: "default",
    questions: [],
    currentQuestionIndex: 0,
    pendingFollowups: [],
    currentFollowupIndex: 0,
    totalFollowups: 0,
    currentPromptKind: null,
    currentPromptText: "",
    transcript: [],
    scoreReports: [],
    viewModel,
  };
}

export function startMockInterview(
  _previousSession: MockInterviewSession,
  scenario: MockInterviewScenario,
): MockInterviewSession {
  const idleSession = createIdleMockInterviewSession();

  if (scenario === "empty") {
    return buildMockInterviewSession({
      ...idleSession,
      scenario,
      viewModel: {
        ...idleSession.viewModel,
        status: "failed",
        errorMessage: "还没有生成可用于模拟面试的问题。",
      },
    });
  }

  return buildMockInterviewSession({
    ...idleSession,
    scenario,
    questions: DEFAULT_QUESTIONS,
    currentPromptKind: "question",
    currentPromptText: DEFAULT_QUESTIONS[0],
    viewModel: {
      ...idleSession.viewModel,
      status: "ready_for_answer",
      errorMessage: null,
    },
  });
}

export function submitMockInterviewAnswer(
  previousSession: MockInterviewSession,
  answer: string,
): MockInterviewSession {
  if (previousSession.viewModel.status === "idle" || previousSession.viewModel.status === "failed" || previousSession.viewModel.status === "ended") {
    return previousSession;
  }

  if (!answer.trim()) {
    return buildMockInterviewSession({
      ...previousSession,
      viewModel: {
        ...previousSession.viewModel,
        status: "answer_required",
        errorMessage: "请先输入当前题回答。",
      },
    });
  }

  const promptText = previousSession.currentPromptText;
  const promptKind = previousSession.currentPromptKind ?? "question";
  const scoreReport = SCORE_REPORT_BY_PROMPT[promptText] ?? {
    score: 7,
    risks: [],
    suggestions: [],
  };
  const transcript = previousSession.transcript.concat({
    promptKind,
    promptText,
    answer: answer.trim(),
    score: scoreReport.score,
  });
  const scoreReports = previousSession.scoreReports.concat(scoreReport);

  if (promptKind === "question") {
    const followups = FOLLOWUP_BY_QUESTION[promptText] ?? [];
    if (followups.length > 0) {
      return buildMockInterviewSession({
        ...previousSession,
        transcript,
        scoreReports,
        pendingFollowups: followups.slice(1),
        currentFollowupIndex: 1,
        totalFollowups: followups.length,
        currentPromptKind: "followup",
        currentPromptText: followups[0],
        viewModel: {
          ...previousSession.viewModel,
          status: "ready_for_answer",
          errorMessage: null,
        },
      });
    }
  }

  if (promptKind === "followup" && previousSession.pendingFollowups.length > 0) {
    return buildMockInterviewSession({
      ...previousSession,
      transcript,
      scoreReports,
      pendingFollowups: previousSession.pendingFollowups.slice(1),
      currentFollowupIndex: previousSession.currentFollowupIndex + 1,
      currentPromptKind: "followup",
      currentPromptText: previousSession.pendingFollowups[0],
      viewModel: {
        ...previousSession.viewModel,
        status: "ready_for_answer",
        errorMessage: null,
      },
    });
  }

  const nextQuestionIndex = previousSession.currentQuestionIndex + 1;
  if (nextQuestionIndex < previousSession.questions.length) {
    return buildMockInterviewSession({
      ...previousSession,
      transcript,
      scoreReports,
      currentQuestionIndex: nextQuestionIndex,
      pendingFollowups: [],
      currentFollowupIndex: 0,
      totalFollowups: 0,
      currentPromptKind: "question",
      currentPromptText: previousSession.questions[nextQuestionIndex],
      viewModel: {
        ...previousSession.viewModel,
        status: "ready_for_answer",
        errorMessage: null,
      },
    });
  }

  return buildMockInterviewSession({
    ...previousSession,
    transcript,
    scoreReports,
    pendingFollowups: [],
    currentFollowupIndex: 0,
    totalFollowups: 0,
    currentPromptKind: null,
    currentPromptText: "",
    viewModel: {
      ...previousSession.viewModel,
      status: "completed",
      errorMessage: null,
      reviewPanel: buildReviewPanel(scoreReports),
    },
  });
}

export function endMockInterview(previousSession: MockInterviewSession): MockInterviewSession {
  const idleSession = createIdleMockInterviewSession();
  return buildMockInterviewSession({
    ...idleSession,
    scenario: previousSession.scenario,
    viewModel: {
      ...idleSession.viewModel,
      status: "ended",
    },
  });
}

function buildMockInterviewSession(session: MockInterviewSession): MockInterviewSession {
  const currentPrompt =
    session.currentPromptKind && session.currentPromptText
      ? {
          kind: session.currentPromptKind,
          label:
            session.currentPromptKind === "question"
              ? `第 ${session.currentQuestionIndex + 1} 题`
              : `追问 ${session.currentFollowupIndex}`,
          text: session.currentPromptText,
        }
      : null;

  return {
    ...session,
    viewModel: {
      sessionId: DEFAULT_SESSION_ID,
      status: session.viewModel.status,
      errorMessage: session.viewModel.errorMessage,
      currentPrompt,
      progress: {
        currentQuestionIndex:
          currentPrompt?.kind === "question" || currentPrompt?.kind === "followup"
            ? session.currentQuestionIndex + 1
            : 0,
        totalQuestions: session.questions.length,
        currentFollowupIndex: session.currentFollowupIndex,
        totalFollowups: session.totalFollowups,
      },
      reviewPanel: session.viewModel.reviewPanel,
      transcript: session.transcript,
    },
  };
}

function buildReviewPanel(scoreReports: ScoreReport[]): MockInterviewViewModel["reviewPanel"] {
  const averageScore = Number(
    (scoreReports.reduce((totalScore, scoreReport) => totalScore + scoreReport.score, 0) / scoreReports.length).toFixed(1),
  );

  return {
    averageScore,
    risks: scoreReports.flatMap((scoreReport) => scoreReport.risks),
    suggestions: scoreReports.flatMap((scoreReport) => scoreReport.suggestions),
  };
}
