export type PrepViewModel = {
  sessionId: string;
  status: "ready" | "missing_inputs" | "failed";
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
  return prepViewModel;
}
