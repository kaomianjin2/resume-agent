export type AlgorithmExercise = {
  id: string;
  title: string;
  prompt: string;
  tags: string[];
  constraints: string[];
  examples: string[];
  edgeCases: string[];
};

export type AlgorithmPracticeViewModel = {
  sessionId: string;
  status: "idle" | "ready" | "failed";
  errorMessage: string | null;
  topic: string;
  difficulty: string;
  exercises: AlgorithmExercise[];
  currentExerciseIndex: number;
  progress: {
    currentExerciseIndex: number;
    totalExercises: number;
  };
};

export type StartAlgorithmPracticeRequest = {
  sessionId: string;
  practiceTopic: string;
  difficulty?: string;
  questionCount?: number;
};

export type AlgorithmPracticeRuntimeClient = {
  startAlgorithmPractice: (request: StartAlgorithmPracticeRequest) => Promise<AlgorithmPracticeViewModel>;
  getCurrentViewModel: () => AlgorithmPracticeViewModel;
};

export const DEFAULT_ALGORITHM_PRACTICE_QUESTION_COUNT = 100;

export const defaultAlgorithmPracticeViewModel: AlgorithmPracticeViewModel = {
  sessionId: "gui-session",
  status: "idle",
  errorMessage: null,
  topic: "算法和数据结构",
  difficulty: "medium",
  exercises: [],
  currentExerciseIndex: 0,
  progress: {
    currentExerciseIndex: 0,
    totalExercises: 0,
  },
};

export function normalizeAlgorithmPracticeViewModel(rawViewModel: unknown): AlgorithmPracticeViewModel {
  if (!isRecord(rawViewModel)) {
    return defaultAlgorithmPracticeViewModel;
  }

  const exercises = Array.isArray(rawViewModel.exercises)
    ? rawViewModel.exercises.map(normalizeAlgorithmExercise).filter((exercise) => exercise.title || exercise.prompt)
    : [];
  const currentExerciseIndex = numberValue(rawViewModel.current_exercise_index, 0);
  return {
    sessionId: textValue(rawViewModel.session_id, defaultAlgorithmPracticeViewModel.sessionId),
    status: normalizeStatus(rawViewModel.status),
    errorMessage: textOrNull(rawViewModel.error_message),
    topic: textValue(rawViewModel.topic, defaultAlgorithmPracticeViewModel.topic),
    difficulty: textValue(rawViewModel.difficulty, defaultAlgorithmPracticeViewModel.difficulty),
    exercises,
    currentExerciseIndex,
    progress: {
      currentExerciseIndex: numberValue(recordValue(rawViewModel.progress).current_exercise_index, exercises.length ? currentExerciseIndex + 1 : 0),
      totalExercises: numberValue(recordValue(rawViewModel.progress).total_exercises, exercises.length),
    },
  };
}

export function createFallbackAlgorithmPracticeClient(): AlgorithmPracticeRuntimeClient {
  let currentViewModel = defaultAlgorithmPracticeViewModel;
  return {
    async startAlgorithmPractice(request: StartAlgorithmPracticeRequest) {
      currentViewModel = {
        ...defaultAlgorithmPracticeViewModel,
        sessionId: request.sessionId,
        status: "ready",
        topic: request.practiceTopic,
        difficulty: request.difficulty ?? "medium",
        exercises: defaultInternalAlgorithmExercises.slice(0, request.questionCount ?? defaultInternalAlgorithmExercises.length),
        currentExerciseIndex: 0,
        progress: {
          currentExerciseIndex: 1,
          totalExercises: Math.min(request.questionCount ?? defaultInternalAlgorithmExercises.length, defaultInternalAlgorithmExercises.length),
        },
      };
      return currentViewModel;
    },
    getCurrentViewModel() {
      return currentViewModel;
    },
  };
}

export const defaultInternalAlgorithmExercises: AlgorithmExercise[] = [
  {
    id: "fixture-longest-increasing-subsequence",
    title: "最长递增子序列",
    prompt: "给定整数数组，返回最长严格递增子序列的长度。要求说明状态定义和转移过程。",
    tags: ["动态规划", "中等", "数组"],
    constraints: ["1 <= nums.length <= 2500"],
    examples: ["输入 [10,9,2,5,3,7,101,18]，输出 4"],
    edgeCases: ["空数组返回 0", "严格递增数组返回数组长度"],
  },
  {
    id: "fixture-coin-change",
    title: "零钱兑换",
    prompt: "给定硬币面额和总金额，计算凑成金额所需的最少硬币数。",
    tags: ["动态规划", "中等"],
    constraints: ["1 <= amount <= 10000"],
    examples: ["输入 coins = [1,2,5], amount = 11，输出 3"],
    edgeCases: ["无法凑成目标金额时返回 -1"],
  },
  {
    id: "fixture-reverse-linked-list",
    title: "反转链表",
    prompt: "给定单链表头节点，反转链表并返回新的头节点。",
    tags: ["链表", "简单"],
    constraints: ["0 <= 节点数 <= 5000"],
    examples: ["输入 1->2->3，输出 3->2->1"],
    edgeCases: ["空链表返回空", "单节点链表返回原节点"],
  },
  {
    id: "fixture-binary-tree-level-order",
    title: "二叉树层序遍历",
    prompt: "给定二叉树根节点，按层从左到右返回每一层的节点值。",
    tags: ["二叉树", "广度优先搜索", "中等"],
    constraints: ["0 <= 节点数 <= 2000"],
    examples: ["输入 [3,9,20,null,null,15,7]，输出 [[3],[9,20],[15,7]]"],
    edgeCases: ["空树返回空数组"],
  },
  {
    id: "fixture-lru-cache",
    title: "LRU 缓存",
    prompt: "设计支持 get 和 put 的 LRU 缓存，容量满时淘汰最久未使用的键。",
    tags: ["哈希表", "双向链表", "中等"],
    constraints: ["1 <= capacity <= 3000"],
    examples: ["put(1,1), put(2,2), get(1), put(3,3)，键 2 被淘汰"],
    edgeCases: ["重复 put 已存在的 key 时更新值并刷新使用顺序"],
  },
];

function normalizeAlgorithmExercise(rawExercise: unknown): AlgorithmExercise {
  const exercise = recordValue(rawExercise);
  return {
    id: textValue(exercise.id, ""),
    title: textValue(exercise.title, ""),
    prompt: textValue(exercise.prompt, ""),
    tags: textList(exercise.tags),
    constraints: textList(exercise.constraints),
    examples: textList(exercise.examples),
    edgeCases: textList(exercise.edge_cases),
  };
}

function normalizeStatus(value: unknown): AlgorithmPracticeViewModel["status"] {
  if (value === "ready" || value === "failed") {
    return value;
  }
  return "idle";
}

function textList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item).trim()).filter(Boolean);
}

function textValue(value: unknown, fallback: string): string {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  return fallback;
}

function textOrNull(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  return null;
}

function numberValue(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return fallback;
}

function recordValue(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
