import { ModuleViewModel } from "../fixtureData";
import { AlgorithmModule } from "../../modules/algorithm/AlgorithmModule";
import { MockModule } from "../../modules/mock/MockModule";
import { PrepModule } from "../../modules/prep/PrepModule";

type WorkspaceProps = {
  activeModule: ModuleViewModel;
};

export function Workspace({ activeModule }: WorkspaceProps) {
  return (
    <section className="workspace" aria-labelledby="workspace-title">
      <header className="workspace-header">
        <div>
          <p className="meta-label">{activeModule.eyebrow}</p>
          <h2 id="workspace-title">{activeModule.title}</h2>
          <p className="workspace-summary">{activeModule.summary}</p>
        </div>
        <div className="workspace-actions">
          <button className="quiet-button" type="button">{activeModule.secondaryAction}</button>
          <button className="primary-button" type="button">{activeModule.primaryAction}</button>
        </div>
      </header>

      {activeModule.id === "prep" && <PrepModule />}
      {activeModule.id === "mock" && <MockModule />}
      {activeModule.id === "algorithm" && <AlgorithmModule />}
    </section>
  );
}
