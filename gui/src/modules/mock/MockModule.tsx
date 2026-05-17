export function MockModule() {
  return (
    <div className="module-grid mock-module">
      <section className="content-panel wide">
        <p className="meta-label">当前主问题</p>
        <h3>请说明你如何设计一个离线构建、运行时只读的知识库检索链路。</h3>
        <p className="body-copy">观察点：边界划分、失败恢复、索引状态检查、用户可见反馈。</p>
      </section>

      <section className="content-panel answer-pad">
        <p className="meta-label">逐题回答</p>
        <h3>候选回答记录</h3>
        <div className="text-surface">等待输入当前题回答，提交后进入追问判断。</div>
      </section>

      <section className="content-panel followup-panel">
        <p className="meta-label">追问区域</p>
        <h3>建议追问</h3>
        <ul className="clean-list">
          <li>如果索引状态不是 ready，你会如何阻断运行时调用？</li>
          <li>如何向用户解释构建失败而不暴露内部实现？</li>
        </ul>
      </section>
    </div>
  );
}
