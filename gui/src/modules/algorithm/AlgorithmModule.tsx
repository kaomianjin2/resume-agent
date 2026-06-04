import { ChangeEvent, ReactNode, UIEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  AlgorithmPracticeRuntimeClient,
  createFallbackAlgorithmPracticeClient,
  DEFAULT_ALGORITHM_PRACTICE_QUESTION_COUNT,
  defaultAlgorithmPracticeViewModel,
  defaultInternalAlgorithmExercises,
} from "../../shared/api/algorithm.js";

type LanguageId = "python" | "javascript" | "go" | "java" | "c" | "cpp";
type RunStateId = "empty" | "error" | "passed";

const languageOptions: { id: LanguageId; label: string; code: string }[] = [
  { id: "python", label: "Python", code: "def length_of_lis(nums):\n    dp = [1] * len(nums)\n    return max(dp, default=0)" },
  { id: "javascript", label: "JavaScript", code: "function lengthOfLis(nums) {\n  const dp = Array(nums.length).fill(1);\n  return Math.max(0, ...dp);\n}" },
  { id: "go", label: "Go", code: "func lengthOfLIS(nums []int) int {\n    dp := make([]int, len(nums))\n    return len(dp)\n}" },
  { id: "java", label: "Java", code: "class Solution {\n  int lengthOfLIS(int[] nums) {\n    int[] dp = new int[nums.length];\n    return dp.length;\n  }\n}" },
  { id: "c", label: "C", code: "int length_of_lis(int* nums, int numsSize) {\n    return numsSize;\n}" },
  { id: "cpp", label: "C++", code: "int lengthOfLIS(vector<int>& nums) {\n    vector<int> dp(nums.size(), 1);\n    return dp.size();\n}" },
];

const runStates: Record<RunStateId, { title: string; stdout: string; stderr: string; cases: string }> = {
  empty: {
    title: "空代码",
    stdout: "未运行",
    stderr: "编辑区为空时不会进入评审。",
    cases: "0/3",
  },
  error: {
    title: "错误代码",
    stdout: "case 1 passed",
    stderr: "case 2 failed: expected 4, received 3",
    cases: "1/3",
  },
  passed: {
    title: "通过用例",
    stdout: "case 1 passed\ncase 2 passed\ncase 3 passed",
    stderr: "",
    cases: "3/3",
  },
};

const fallbackRuntimeClient = createFallbackAlgorithmPracticeClient();

type AlgorithmModuleProps = {
  runtimeClient?: AlgorithmPracticeRuntimeClient;
};

export function AlgorithmModule({ runtimeClient = fallbackRuntimeClient }: AlgorithmModuleProps) {
  const [selectedLanguageId, setSelectedLanguageId] = useState<LanguageId>("python");
  const [runStateId, setRunStateId] = useState<RunStateId>("empty");
  const [practiceViewModel, setPracticeViewModel] = useState(defaultAlgorithmPracticeViewModel);
  const [selectedExerciseIndex, setSelectedExerciseIndex] = useState(0);
  const [practiceLoading, setPracticeLoading] = useState(false);
  const [practiceError, setPracticeError] = useState<string | null>(null);
  const selectedLanguage = languageOptions.find((languageOption) => languageOption.id === selectedLanguageId) ?? languageOptions[0];
  const runState = runStates[runStateId];
  const [editorCode, setEditorCode] = useState("");
  const editorInputRef = useRef<HTMLTextAreaElement | null>(null);
  const highlightedCode = useMemo(() => buildHighlightedCode(editorCode, selectedLanguageId), [editorCode, selectedLanguageId]);
  const exercises = practiceViewModel.exercises.length ? practiceViewModel.exercises : defaultInternalAlgorithmExercises;
  const selectedExercise = exercises[selectedExerciseIndex] ?? exercises[0];

  const handleLanguageChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setSelectedLanguageId(event.target.value as LanguageId);
  };

  const handleRunStateChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setRunStateId(event.target.value as RunStateId);
  };

  const handleEditorInput = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setEditorCode(event.target.value);
  };

  const handleExerciseDropdownChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setSelectedExerciseIndex(Number(event.target.value));
  };

  const handleStartPractice = async () => {
    setPracticeLoading(true);
    setPracticeError(null);
    try {
      const viewModel = await runtimeClient.startAlgorithmPractice({
        sessionId: "gui-session",
        practiceTopic: "算法和数据结构",
        difficulty: "medium",
        questionCount: DEFAULT_ALGORITHM_PRACTICE_QUESTION_COUNT,
      });
      setPracticeViewModel(viewModel);
      setSelectedExerciseIndex(0);
      if (viewModel.status === "failed") {
        setPracticeError(viewModel.errorMessage ?? "算法练习启动失败。");
      }
    } catch (error) {
      setPracticeError(error instanceof Error ? error.message : "算法练习启动失败。");
    } finally {
      setPracticeLoading(false);
    }
  };

  const handleEditorScroll = (event: UIEvent<HTMLTextAreaElement>) => {
    const target = event.currentTarget;
    const overlay = target.previousElementSibling as HTMLElement | null;
    if (!overlay) {
      return;
    }
    overlay.scrollTop = target.scrollTop;
    overlay.scrollLeft = target.scrollLeft;
  };

  useEffect(() => {
    if (runStateId === "empty") {
      setEditorCode("");
      return;
    }
    setEditorCode(selectedLanguage.code);
  }, [selectedLanguage.code, runStateId]);

  useEffect(() => {
    setEditorCode("");
    setRunStateId("empty");
  }, [selectedExerciseIndex]);

  useEffect(() => {
    void handleStartPractice();
  }, []);

  useEffect(() => {
    if (!editorInputRef.current) {
      return;
    }
    editorInputRef.current.focus();
  }, [selectedLanguageId, runStateId]);

  return (
    <div className="module-grid algorithm-module">
      <section className="content-panel wide">
        <p className="meta-label">题目</p>
        <h3>{selectedExercise.title}</h3>
        <p className="body-copy">{selectedExercise.prompt}</p>
        <div className="tag-row">
          {selectedExercise.tags.map((tag) => (
            <span className="tag" key={tag}>{tag}</span>
          ))}
        </div>
        <ul className="clean-list">
          {selectedExercise.constraints.map((constraint) => (
            <li key={`constraint-${constraint}`}>约束：{constraint}</li>
          ))}
          {selectedExercise.examples.map((example) => (
            <li key={`example-${example}`}>示例：{example}</li>
          ))}
          {selectedExercise.edgeCases.map((edgeCase) => (
            <li key={`edge-${edgeCase}`}>边界：{edgeCase}</li>
          ))}
        </ul>
      </section>

      <section className="content-panel">
        <p className="meta-label">内部题库</p>
        {practiceLoading && <p className="body-copy">题库加载中</p>}
        {practiceError && <p className="form-error">{practiceError}</p>}
        <label className="field-label" htmlFor="algorithm-exercise-select">选择题目</label>
        <select id="algorithm-exercise-select" value={selectedExerciseIndex} onChange={handleExerciseDropdownChange}>
          {exercises.map((exercise, exerciseIndex) => (
            <option key={exercise.id || exercise.title} value={exerciseIndex}>
              {exerciseIndex + 1}. {exercise.title}
            </option>
          ))}
        </select>
        <label className="field-label" htmlFor="language">语言</label>
        <select id="language" value={selectedLanguageId} onChange={handleLanguageChange}>
          {languageOptions.map((languageOption) => (
            <option key={languageOption.id} value={languageOption.id}>{languageOption.label}</option>
          ))}
        </select>
        <label className="field-label" htmlFor="run-state">运行结果状态</label>
        <select id="run-state" value={runStateId} onChange={handleRunStateChange}>
          <option value="empty">空代码</option>
          <option value="error">错误代码</option>
          <option value="passed">通过用例</option>
        </select>
      </section>

      <section className="content-panel editor-panel">
        <p className="meta-label">编辑器</p>
        <div className="code-editor-shell">
          <pre className="code-editor-highlight" aria-hidden="true">
            <code>{highlightedCode}</code>
          </pre>
          <textarea
            id="algorithm-editor"
            ref={editorInputRef}
            className="code-editor-input"
            value={editorCode}
            onChange={handleEditorInput}
            onScroll={handleEditorScroll}
            spellCheck={false}
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            placeholder="请输入算法代码，空行提交。"
          />
        </div>
      </section>

      <section className="content-panel">
        <p className="meta-label">运行结果</p>
        <h3>{runState.title}</h3>
        <div className="tag-row">
          <span className="tag">用例 {runState.cases}</span>
          <span className="tag">{selectedLanguage.label}</span>
        </div>
        <pre>{`stdout:
${runState.stdout}

stderr:
${runState.stderr || "无"}`}</pre>
      </section>

      <section className="content-panel review-result">
        <p className="meta-label">评审面板</p>
        <h3>fixture 评审</h3>
        <ul className="clean-list">
          <li>正确性：{runStateId === "passed" ? "示例和边界用例通过" : "需要补齐状态转移和空输入处理"}</li>
          <li>复杂度：目标时间 O(n log n)，空间 O(n)</li>
          <li>边界 case：空数组、单元素、重复元素、严格递减数组</li>
          <li>建议：说明 dp / tails 数组含义，并补充二分更新过程</li>
        </ul>
      </section>
    </div>
  );
}

export function buildHighlightedCode(code: string, languageId: LanguageId): ReactNode[] {
  const keywordByLanguage: Record<LanguageId, string[]> = {
    python: ["def", "return", "for", "while", "if", "else", "elif", "in", "len", "max"],
    javascript: ["function", "const", "let", "return", "if", "else", "for", "while", "new", "class"],
    go: ["func", "return", "for", "if", "else", "var", "const", "range", "int"],
    java: ["class", "int", "return", "if", "else", "for", "while", "new", "public", "static"],
    c: ["int", "return", "if", "else", "for", "while", "void"],
    cpp: ["int", "return", "if", "else", "for", "while", "vector", "class", "auto"],
  };
  const keywords = new Set(keywordByLanguage[languageId]);
  const lines = code.split("\n");
  const highlightedNodes: ReactNode[] = [];

  lines.forEach((line, lineIndex) => {
    const commentIndex = line.indexOf("//");
    const pythonCommentIndex = line.indexOf("#");
    const activeCommentIndex = pythonCommentIndex >= 0 && (commentIndex < 0 || pythonCommentIndex < commentIndex)
      ? pythonCommentIndex
      : commentIndex;
    const codePart = activeCommentIndex >= 0 ? line.slice(0, activeCommentIndex) : line;
    const commentPart = activeCommentIndex >= 0 ? line.slice(activeCommentIndex) : "";
    const tokens = codePart.split(/(\b[A-Za-z_][A-Za-z0-9_]*\b|\d+|[()[\]{}.,;:+\-*/<>=!&|]+)/g);

    tokens.forEach((token, tokenIndex) => {
      if (!token) {
        return;
      }
      if (keywords.has(token)) {
        highlightedNodes.push(<span key={`k-${lineIndex}-${tokenIndex}`} className="token-keyword">{token}</span>);
        return;
      }
      if (/^\d+$/.test(token)) {
        highlightedNodes.push(<span key={`n-${lineIndex}-${tokenIndex}`} className="token-number">{token}</span>);
        return;
      }
      highlightedNodes.push(<span key={`t-${lineIndex}-${tokenIndex}`}>{token}</span>);
    });

    if (commentPart) {
      highlightedNodes.push(<span key={`c-${lineIndex}`} className="token-comment">{commentPart}</span>);
    }
    if (lineIndex < lines.length - 1) {
      highlightedNodes.push("\n");
    }
  });

  return highlightedNodes;
}
