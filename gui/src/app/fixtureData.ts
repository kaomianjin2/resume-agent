export type ModuleId = "prep" | "mock" | "algorithm" | "job" | "users";
export type UserRole = "admin" | "member";
export const DEFAULT_ACTIVE_MODULE_ID: ModuleId = "prep";

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
    title: "面试准备",
    summary: "把简历、JD 和匹配报告整理成一页可读摘要，再进入模拟面试。",
    primaryAction: "查看摘要",
    secondaryAction: "查看匹配点",
    checks: [
      { label: "岗位重点", status: "ready", detail: "已抽取角色、技术栈和经验要求" },
      { label: "简历摘要", status: "ready", detail: "已归纳候选人亮点和可验证证据" },
      { label: "匹配报告", status: "ready", detail: "已展示匹配度、优势、风险和追问重点" },
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
      { label: "题目", status: "ready", detail: "题干、约束、示例和标签已展示" },
      { label: "语言", status: "ready", detail: "Python、JavaScript、Go、Java、C、C++ 可切换" },
      { label: "运行结果", status: "ready", detail: "空代码、错误代码、通过用例三种状态可展示" },
      { label: "评审面板", status: "review", detail: "正确性、复杂度、边界 case 和建议已展示" },
    ],
  },
  {
    id: "job",
    label: "求职投递",
    eyebrow: "Job Application",
    title: "求职投递",
    summary: "多平台采集岗位、评估匹配、批量确认后执行投递。",
    primaryAction: "开始采集",
    secondaryAction: "刷新进度",
    checks: [
      { label: "求职画像", status: "ready", detail: "已从简历推导岗位方向和筛选条件" },
      { label: "岗位采集", status: "review", detail: "BOSS、拉勾、猎聘三平台采集进度可观测" },
      { label: "筛选与评估", status: "ready", detail: "全条件筛选和匹配评估已就绪" },
      { label: "批量投递", status: "review", detail: "用户确认后执行投递并记录结果" },
    ],
  },
  {
    id: "users",
    label: "用户管理",
    eyebrow: "User Management",
    title: "本地账号管理",
    summary: "管理本地登录账号、角色和启用状态。",
    primaryAction: "新增用户",
    secondaryAction: "刷新列表",
    checks: [
      { label: "账号列表", status: "ready", detail: "可查看用户名、角色和状态" },
      { label: "新增账号", status: "ready", detail: "支持 admin/member 角色" },
      { label: "状态切换", status: "ready", detail: "支持启用与禁用账号" },
    ],
  },
];

export function getVisibleModuleViewModels(currentUserRole: UserRole | null): ModuleViewModel[] {
  if (currentUserRole === "admin") {
    return moduleViewModels;
  }
  return moduleViewModels.filter((moduleViewModel) => moduleViewModel.id !== "users");
}

export function getModuleViewModel(moduleId: ModuleId): ModuleViewModel {
  return moduleViewModels.find((moduleViewModel) => moduleViewModel.id === moduleId) ?? moduleViewModels[0];
}
