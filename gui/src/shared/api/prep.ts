export type PrepStatus = "ready" | "missing_inputs" | "failed";

export type PrepViewModel = {
  sessionId: string;
  status: PrepStatus;
  resumeSummary: {
    name: string;
    headline: string;
    highlights: string[];
  };
  jdSummary: {
    role: string;
    focus: string[];
  };
  matchSummary: {
    score: number | string;
    strengths: string[];
    risks: string[];
    followUpFocus: string[];
  };
  missingInputs: string[];
  errorMessage?: string | null;
};

export const prepViewModel: PrepViewModel = {
  sessionId: "fixture-prep-session",
  status: "ready",
  resumeSummary: {
    name: "Alice",
    headline: "Python 检索服务负责人",
    highlights: ["Python 工程实践", "知识库检索链路", "可靠性治理"],
  },
  jdSummary: {
    role: "后端工程师",
    focus: ["Python", "检索链路", "稳定性", "CLI 交互体验"],
  },
  matchSummary: {
    score: 91,
    strengths: ["检索系统经验", "能解释工程取舍", "有端到端交付记录"],
    risks: ["压测案例需要补充", "跨团队协作证据需要量化"],
    followUpFocus: ["SLA 取舍", "检索召回评估", "异常状态下的用户反馈"],
  },
  missingInputs: [],
};

export function getPrepViewModel(): PrepViewModel {
  return missingInputsPrepViewModel(["resume_text"]);
}

export function missingInputsPrepViewModel(missingInputs: string[]): PrepViewModel {
  return {
    sessionId: "gui-prep-session",
    status: "missing_inputs",
    resumeSummary: {
      name: "",
      headline: "",
      highlights: [],
    },
    jdSummary: {
      role: "",
      focus: [],
    },
    matchSummary: {
      score: "未评分",
      strengths: [],
      risks: [],
      followUpFocus: [],
    },
    missingInputs,
  };
}

export function failedPrepViewModel(errorMessage: string): PrepViewModel {
  return {
    sessionId: "gui-prep-session",
    status: "failed",
    resumeSummary: {
      name: "",
      headline: "",
      highlights: [],
    },
    jdSummary: {
      role: "",
      focus: [],
    },
    matchSummary: {
      score: "未评分",
      strengths: [],
      risks: [],
      followUpFocus: [],
    },
    missingInputs: [],
    errorMessage,
  };
}

export function normalizePrepViewModel(rawViewModel: unknown): PrepViewModel {
  const rawRecord = isRecord(rawViewModel) ? rawViewModel : {};
  const resumeSummary = recordValue(rawRecord.resumeSummary ?? rawRecord.resume_summary);
  const jdSummary = recordValue(rawRecord.jdSummary ?? rawRecord.jd_summary);
  const matchSummary = recordValue(rawRecord.matchSummary ?? rawRecord.match_summary);

  return {
    sessionId: stringValue(rawRecord.sessionId ?? rawRecord.session_id, "gui-prep-session"),
    status: prepStatusValue(rawRecord.status),
    resumeSummary: {
      name: stringValue(resumeSummary.name, ""),
      headline: stringValue(resumeSummary.headline, ""),
      highlights: stringListValue(resumeSummary.highlights),
    },
    jdSummary: {
      role: stringValue(jdSummary.role, ""),
      focus: stringListValue(jdSummary.focus),
    },
    matchSummary: {
      score: typeof matchSummary.score === "number" ? matchSummary.score : stringValue(matchSummary.score, "未评分"),
      strengths: stringListValue(matchSummary.strengths),
      risks: stringListValue(matchSummary.risks),
      followUpFocus: stringListValue(matchSummary.followUpFocus ?? matchSummary.follow_up_focus),
    },
    missingInputs: stringListValue(rawRecord.missingInputs ?? rawRecord.missing_inputs),
    errorMessage: rawRecord.errorMessage === null || rawRecord.error_message === null
      ? null
      : stringValue(rawRecord.errorMessage ?? rawRecord.error_message, ""),
  };
}

function prepStatusValue(value: unknown): PrepViewModel["status"] {
  if (value === "ready" || value === "failed") {
    return value;
  }
  return "missing_inputs";
}

function recordValue(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function stringListValue(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item).trim()).filter(Boolean);
}
