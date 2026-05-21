import { ModuleViewModel } from "../fixtureData";
import { AlgorithmModule } from "../../modules/algorithm/AlgorithmModule";
import { MockModule } from "../../modules/mock/MockModule";
import { PrepModule } from "../../modules/prep/PrepModule";
import { PrepViewModel } from "../../shared/api/prep";
import { MaterialKind } from "../../shared/desktop/desktopBridge";

type WorkspaceProps = {
  activeModule: ModuleViewModel;
  prepViewModel: PrepViewModel;
  onSelectMaterialFile: (kind: MaterialKind) => void;
};

export function Workspace({ activeModule, prepViewModel, onSelectMaterialFile }: WorkspaceProps) {
  return (
    <section className="workspace" aria-labelledby="workspace-title">
      <header className="workspace-header">
        <div>
          <h2 id="workspace-title">{activeModule.title}</h2>
          <p className="workspace-summary">{activeModule.summary}</p>
        </div>
        {activeModule.id === "prep" ? (
          <div className="workspace-actions">
            <button className="quiet-button" type="button" onClick={() => onSelectMaterialFile("resume")}>导入简历</button>
            <button className="primary-button" type="button" onClick={() => onSelectMaterialFile("jd")}>导入 JD</button>
          </div>
        ) : (
          <div className="workspace-actions">
            <button className="quiet-button" type="button">{activeModule.secondaryAction}</button>
            <button className="primary-button" type="button">{activeModule.primaryAction}</button>
          </div>
        )}
      </header>

      {activeModule.id === "prep" && <PrepModule viewModel={prepViewModel} />}
      {activeModule.id === "mock" && <MockModule />}
      {activeModule.id === "algorithm" && <AlgorithmModule />}
    </section>
  );
}
