import { ModuleId, ModuleViewModel, UserRole } from "../fixtureData";
import type { JobScreenId } from "../../modules/job/JobModule";
import { Sidebar } from "./Sidebar";
import { Workspace } from "./Workspace";
import { ReviewPanel } from "./ReviewPanel";
import { DesktopRuntimeSnapshot, MaterialKind, UserRecord } from "../../shared/desktop/desktopBridge";
import { AlgorithmPracticeRuntimeClient } from "../../shared/api/algorithm.js";
import { MockInterviewRuntimeClient } from "../../shared/api/mock";
import { JobRuntimeClient } from "../../shared/api/job";
import { PrepViewModel } from "../../shared/api/prep";

type ShellLayoutProps = {
  activeModule: ModuleViewModel;
  activeModuleId: ModuleId;
  desktopSnapshot: DesktopRuntimeSnapshot | null;
  prepViewModel: PrepViewModel;
  prepIsLoading: boolean;
  users: UserRecord[];
  newUsername: string;
  newPassword: string;
  newRole: "admin" | "member";
  userErrorMessage: string;
  currentUserRole: UserRole | null;
  mockRuntimeClient: MockInterviewRuntimeClient;
  algorithmRuntimeClient: AlgorithmPracticeRuntimeClient;
  jobRuntimeClient: JobRuntimeClient;
  selectedJobIds: string[];
  onSelectedJobIdsChange: (ids: string[]) => void;
  jobActiveScreen: JobScreenId;
  onJobActiveScreenChange: (screen: JobScreenId) => void;
  onModuleChange: (moduleId: ModuleId) => void;
  onSelectMaterialFile: (kind: MaterialKind) => void;
  onNewUsernameChange: (value: string) => void;
  onNewPasswordChange: (value: string) => void;
  onNewRoleChange: (value: "admin" | "member") => void;
  onLogout: () => void;
  onCreateUser: () => void;
  onRefreshUsers: () => void;
  onToggleUserStatus: (username: string, status: "enabled" | "disabled") => void;
};

export function ShellLayout({
  activeModule,
  activeModuleId,
  desktopSnapshot,
  prepViewModel,
  prepIsLoading,
  users,
  newUsername,
  newPassword,
  newRole,
  userErrorMessage,
  currentUserRole,
  mockRuntimeClient,
  algorithmRuntimeClient,
  jobRuntimeClient,
  selectedJobIds,
  onSelectedJobIdsChange,
  jobActiveScreen,
  onJobActiveScreenChange,
  onModuleChange,
  onSelectMaterialFile,
  onNewUsernameChange,
  onNewPasswordChange,
  onNewRoleChange,
  onLogout,
  onCreateUser,
  onRefreshUsers,
  onToggleUserStatus,
}: ShellLayoutProps) {
  const isUsersModule = activeModuleId === "users";
  const isJobWithoutReview = activeModuleId === "job" && jobActiveScreen !== "jobs";
  const hideReview = isUsersModule || isJobWithoutReview;

  const layoutClass = isUsersModule
    ? "shell-layout users-minimal"
    : hideReview
      ? "shell-layout no-review"
      : "shell-layout";

  return (
    <main className={layoutClass}>
      <Sidebar
        activeModuleId={activeModuleId}
        desktopSnapshot={desktopSnapshot}
        currentUserRole={currentUserRole}
        onModuleChange={onModuleChange}
      />
      <Workspace
        activeModule={activeModule}
        prepViewModel={prepViewModel}
        prepIsLoading={prepIsLoading}
        desktopSnapshot={desktopSnapshot}
        users={users}
        newUsername={newUsername}
        newPassword={newPassword}
        newRole={newRole}
        userErrorMessage={userErrorMessage}
        currentUserRole={currentUserRole}
        mockRuntimeClient={mockRuntimeClient}
        algorithmRuntimeClient={algorithmRuntimeClient}
        jobRuntimeClient={jobRuntimeClient}
        selectedJobIds={selectedJobIds}
        onSelectedJobIdsChange={onSelectedJobIdsChange}
        jobActiveScreen={jobActiveScreen}
        onJobActiveScreenChange={onJobActiveScreenChange}
        onSelectMaterialFile={onSelectMaterialFile}
        onNewUsernameChange={onNewUsernameChange}
        onNewPasswordChange={onNewPasswordChange}
        onNewRoleChange={onNewRoleChange}
        onLogout={onLogout}
        onCreateUser={onCreateUser}
        onRefreshUsers={onRefreshUsers}
        onToggleUserStatus={onToggleUserStatus}
      />
      {!isUsersModule ? <ReviewPanel activeModule={activeModule} prepViewModel={prepViewModel} selectedJobIds={selectedJobIds} jobActiveScreen={jobActiveScreen} /> : null}
    </main>
  );
}
