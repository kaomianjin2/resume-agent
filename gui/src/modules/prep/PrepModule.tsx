const requirementItems = ["后端服务治理", "Python 工程实践", "知识库检索链路", "CLI 交互体验"];
const candidateItems = ["有检索系统经验", "能解释工程取舍", "需要补充压测案例"];

export function PrepModule() {
  return (
    <div className="module-grid prep-module">
      <section className="content-panel wide">
        <p className="meta-label">岗位要求</p>
        <h3>核心匹配方向</h3>
        <div className="tag-row">
          {requirementItems.map((requirementItem) => (
            <span className="tag" key={requirementItem}>{requirementItem}</span>
          ))}
        </div>
      </section>

      <section className="content-panel">
        <p className="meta-label">候选人画像</p>
        <h3>面试前速览</h3>
        <ul className="clean-list">
          {candidateItems.map((candidateItem) => (
            <li key={candidateItem}>{candidateItem}</li>
          ))}
        </ul>
      </section>

      <section className="content-panel">
        <p className="meta-label">准备清单</p>
        <h3>下一步</h3>
        <ol className="clean-list">
          <li>确认岗位关键词</li>
          <li>标注候选人可验证证据</li>
          <li>准备追问方向</li>
        </ol>
      </section>
    </div>
  );
}
