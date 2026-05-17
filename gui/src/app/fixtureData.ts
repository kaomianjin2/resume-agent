export type ModuleId = "prep" | "mock" | "algorithm";

export type CheckItem = {
  label: string;
  status: "ready" | "review" | "blocked";
  detail: string;
};

export type ModuleViewModel = {
  id: ModuleId;
  label: string;
  eyebrow: string;
  title: string;
  summary: string;
  primaryAction: string;
  secondaryAction: string;
  checks: CheckItem[];
};

export const moduleViewModels: ModuleViewModel[] = [
  {
    id: "prep",
    label: "面试准备",
    eyebrow: "Preparation",
    title: "岗位材料整理台",
    summary: "集中查看岗位要求、候选人亮点和准备清单，先把输入材料组织清楚。",
    primaryAction: "整理材料",
    secondaryAction: "查看匹配点",
    checks: [
      { label: "岗位要求", status: "ready", detail: "已抽取职责、技术栈和经验要求" },
      { label: "简历摘要", status: "ready", detail: "已归纳项目经历、技能和可追问点" },
      { label: "题目生成", status: "blocked", detail: "本页不提供题目生成入口" },
    ],
  },
  {
    id: "mock",
    label: "模拟面试",
    eyebrow: "Mock Interview",
    title: "逐题演练控制台",
    summary: "围绕主问题、候选回答和追问建议组织一轮模拟面试闭环。",
    primaryAction: "开始当前题",
    secondaryAction: "记录回答",
    checks: [
      { label: "主问题", status: "ready", detail: "当前题目已准备" },
      { label: "逐题回答", status: "review", detail: "等待候选人输入完整回答" },
      { label: "追问区域", status: "ready", detail: "已提供追问方向和追问记录" },
    ],
  },
  {
    id: "algorithm",
    label: "算法练习",
    eyebrow: "Algorithm Lab",
    title: "代码练习工作台",
    summary: "把题目、语言、代码编辑区和评审结果放在同一工作流里。",
    primaryAction: "运行示例",
    secondaryAction: "提交评审",
    checks: [
      { label: "题目", status: "ready", detail: "题干和约束已展示" },
      { label: "语言", status: "ready", detail: "当前选择 Python" },
      { label: "评审面板", status: "review", detail: "等待代码提交后生成反馈" },
    ],
  },
];

export function getModuleViewModel(moduleId: ModuleId): ModuleViewModel {
  return moduleViewModels.find((moduleViewModel) => moduleViewModel.id === moduleId) ?? moduleViewModels[0];
}
