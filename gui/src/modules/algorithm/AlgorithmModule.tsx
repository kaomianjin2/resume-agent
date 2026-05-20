import { ChangeEvent, useState } from "react";

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

export function AlgorithmModule() {
  const [selectedLanguageId, setSelectedLanguageId] = useState<LanguageId>("python");
  const [runStateId, setRunStateId] = useState<RunStateId>("empty");
  const selectedLanguage = languageOptions.find((languageOption) => languageOption.id === selectedLanguageId) ?? languageOptions[0];
  const runState = runStates[runStateId];
  const editorCode = runStateId === "empty" ? "" : selectedLanguage.code;

  const handleLanguageChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setSelectedLanguageId(event.target.value as LanguageId);
  };

  const handleRunStateChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setRunStateId(event.target.value as RunStateId);
  };

  return (
    <div className="module-grid algorithm-module">
      <section className="content-panel wide">
        <p className="meta-label">题目</p>
        <h3>最长递增子序列</h3>
        <p className="body-copy">给定整数数组，返回最长严格递增子序列的长度。要求说明状态定义和转移过程。</p>
        <div className="tag-row">
          <span className="tag">动态规划</span>
          <span className="tag">中等</span>
          <span className="tag">数组</span>
        </div>
        <ul className="clean-list">
          <li>约束：1 {"<="} nums.length {"<="} 2500</li>
          <li>示例：输入 [10,9,2,5,3,7,101,18]，输出 4</li>
          <li>边界：空数组返回 0；严格递增数组返回数组长度</li>
        </ul>
      </section>

      <section className="content-panel">
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
        <pre>{editorCode}</pre>
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
