import { useState } from "react";
import { ShellLayout } from "./layout/ShellLayout";
import { getModuleViewModel, ModuleId } from "./fixtureData";

export function App() {
  const [activeModuleId, setActiveModuleId] = useState<ModuleId>("prep");
  const activeModule = getModuleViewModel(activeModuleId);

  return (
    <ShellLayout
      activeModule={activeModule}
      activeModuleId={activeModuleId}
      onModuleChange={setActiveModuleId}
    />
  );
}
