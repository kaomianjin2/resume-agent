export function AlgorithmModule() {
  return (
    <div className="module-grid algorithm-module">
      <section className="content-panel wide">
        <p className="meta-label">题目</p>
        <h3>最长递增子序列</h3>
        <p className="body-copy">给定整数数组，返回最长严格递增子序列的长度。要求说明状态定义和转移过程。</p>
      </section>

      <section className="content-panel">
        <label className="field-label" htmlFor="language">语言</label>
        <select id="language" defaultValue="python">
          <option value="python">Python</option>
          <option value="javascript">JavaScript</option>
          <option value="go">Go</option>
          <option value="java">Java</option>
          <option value="cpp">C++</option>
        </select>
      </section>

      <section className="content-panel editor-panel">
        <p className="meta-label">编辑器</p>
        <pre>{`def length_of_lis(nums):
    dp = [1] * len(nums)
    return max(dp, default=0)`}</pre>
      </section>

      <section className="content-panel review-result">
        <p className="meta-label">评审面板</p>
        <h3>等待提交</h3>
        <p className="body-copy">提交后展示运行结果、复杂度判断和可改进点。</p>
      </section>
    </div>
  );
}
