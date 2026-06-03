export type MockInterviewScenario = "default" | "empty";
export type MockInterviewQuestionType = "行为面试" | "项目深挖" | "技术基础" | "系统设计";

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

export type StartMockInterviewRequest = {
  sessionId: string;
  targetRole: string;
  questionCount?: number;
  questionType?: MockInterviewQuestionType;
  followupRounds?: number;
  scenario?: MockInterviewScenario;
};

export type SubmitMockAnswerRequest = {
  sessionId: string;
  answer: string;
};

export type EndMockInterviewRequest = {
  sessionId: string;
};

export type MockInterviewRuntimeClient = {
  startMockInterview: (request: StartMockInterviewRequest) => MockInterviewViewModel;
  submitMockAnswer: (request: SubmitMockAnswerRequest) => MockInterviewViewModel;
  endMockInterview: (request: EndMockInterviewRequest) => MockInterviewViewModel;
  getCurrentViewModel: () => MockInterviewViewModel;
};

type ScoreReport = {
  score: number;
  risks: string[];
  suggestions: string[];
};

type MockInterviewFallbackSession = {
  scenario: MockInterviewScenario;
  sessionId: string;
  questionType: MockInterviewQuestionType;
  questions: string[];
  currentQuestionIndex: number;
  followupRounds: number;
  pendingFollowups: string[];
  currentFollowupIndex: number;
  totalFollowups: number;
  currentPromptKind: "question" | "followup" | null;
  currentPromptText: string;
  transcript: MockInterviewViewModel["transcript"];
  scoreReports: ScoreReport[];
  viewModel: MockInterviewViewModel;
};

const FALLBACK_SESSION_ID = "fallback-mock-session";
const DEFAULT_QUESTIONS = [
  "介绍你最近一次线上延迟排查。",
  "如果延迟再次出现，你会如何设计预防机制？",
  "说说你做过的一个高影响力项目。",
  "你如何和产品、测试协作推进复杂需求？",
  "解释一次你优化系统稳定性的经历。",
  "你如何设计一个可观测性方案？",
  "描述一次线上事故复盘后的改进。",
  "如果要重构核心服务，你会如何拆步骤？",
];

const FOLLOWUP_BY_QUESTION: Record<string, string[]> = {
  "介绍你最近一次线上延迟排查。": [
    "你如何判断瓶颈在数据库？",
    "这次排查里你如何验证修复有效？",
    "后续你如何避免同类问题复发？",
  ],
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

export function createFallbackMockInterviewClient(): MockInterviewRuntimeClient {
  let fallbackSession = createIdleFallbackSession(FALLBACK_SESSION_ID);

  return {
    startMockInterview(request: StartMockInterviewRequest) {
      fallbackSession = startFallbackMockInterview(fallbackSession, request);
      return fallbackSession.viewModel;
    },
    submitMockAnswer(request: SubmitMockAnswerRequest) {
      fallbackSession = submitFallbackMockAnswer(fallbackSession, request.answer);
      return fallbackSession.viewModel;
    },
    endMockInterview(request: EndMockInterviewRequest) {
      fallbackSession = endFallbackMockInterview(fallbackSession, request.sessionId);
      return fallbackSession.viewModel;
    },
    getCurrentViewModel() {
      return fallbackSession.viewModel;
    },
  };
}

function createIdleFallbackSession(sessionId: string): MockInterviewFallbackSession {
  const viewModel: MockInterviewViewModel = {
    sessionId,
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
    sessionId,
    questionType: "行为面试",
    questions: [],
    currentQuestionIndex: 0,
    followupRounds: 0,
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

function startFallbackMockInterview(
  _previousSession: MockInterviewFallbackSession,
  request: StartMockInterviewRequest,
): MockInterviewFallbackSession {
  const idleSession = createIdleFallbackSession(request.sessionId);
  const scenario = request.scenario ?? "default";

  if (scenario === "empty") {
    return buildFallbackSession({
      ...idleSession,
      scenario,
      viewModel: {
        ...idleSession.viewModel,
        status: "failed",
        errorMessage: "还没有生成可用于模拟面试的问题。",
      },
    });
  }

  return buildFallbackSession({
    ...idleSession,
    scenario,
    questionType: request.questionType ?? "行为面试",
    questions: DEFAULT_QUESTIONS.slice(0, request.questionCount ?? DEFAULT_QUESTIONS.length),
    currentPromptKind: "question",
    currentPromptText: DEFAULT_QUESTIONS[0],
    followupRounds: request.followupRounds ?? 1,
    viewModel: {
      ...idleSession.viewModel,
      status: "ready_for_answer",
      errorMessage: null,
    },
  });
}

function submitFallbackMockAnswer(
  previousSession: MockInterviewFallbackSession,
  answer: string,
): MockInterviewFallbackSession {
  if (
    previousSession.viewModel.status === "idle" ||
    previousSession.viewModel.status === "failed" ||
    previousSession.viewModel.status === "completed" ||
    previousSession.viewModel.status === "ended"
  ) {
    return previousSession;
  }

  if (!answer.trim()) {
    return buildFallbackSession({
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
    const followups = (FOLLOWUP_BY_QUESTION[promptText] ?? []).slice(0, previousSession.followupRounds);
    if (followups.length > 0) {
      return buildFallbackSession({
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
    return buildFallbackSession({
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
    return buildFallbackSession({
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

  return buildFallbackSession({
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

function endFallbackMockInterview(
  previousSession: MockInterviewFallbackSession,
  sessionId: string,
): MockInterviewFallbackSession {
  const idleSession = createIdleFallbackSession(sessionId);
  return buildFallbackSession({
    ...idleSession,
    scenario: previousSession.scenario,
    viewModel: {
      ...idleSession.viewModel,
      status: "ended",
    },
  });
}

function buildFallbackSession(session: MockInterviewFallbackSession): MockInterviewFallbackSession {
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
      sessionId: session.sessionId,
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
