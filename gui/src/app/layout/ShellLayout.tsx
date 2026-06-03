import { ModuleId, ModuleViewModel, UserRole } from "../fixtureData";
import { Sidebar } from "./Sidebar";
import { Workspace } from "./Workspace";
import { ReviewPanel } from "./ReviewPanel";
import { DesktopRuntimeSnapshot, MaterialKind, UserRecord } from "../../shared/desktop/desktopBridge";
import { PrepViewModel } from "../../shared/api/prep";

type ShellLayoutProps = {
  activeModule: ModuleViewModel;
  activeModuleId: ModuleId;
  desktopSnapshot: DesktopRuntimeSnapshot | null;
  prepViewModel: PrepViewModel;
  users: UserRecord[];
  newUsername: string;
  newPassword: string;
  newRole: "admin" | "member";
  userErrorMessage: string;
  currentUserRole: UserRole | null;
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
  users,
  newUsername,
  newPassword,
  newRole,
  userErrorMessage,
  currentUserRole,
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

  return (
    <main className={isUsersModule ? "shell-layout users-minimal" : "shell-layout"}>
      <Sidebar
        activeModuleId={activeModuleId}
        desktopSnapshot={desktopSnapshot}
        currentUserRole={currentUserRole}
        onModuleChange={onModuleChange}
      />
      <Workspace
        activeModule={activeModule}
        prepViewModel={prepViewModel}
        desktopSnapshot={desktopSnapshot}
        users={users}
        newUsername={newUsername}
        newPassword={newPassword}
        newRole={newRole}
        userErrorMessage={userErrorMessage}
        currentUserRole={currentUserRole}
        onSelectMaterialFile={onSelectMaterialFile}
        onNewUsernameChange={onNewUsernameChange}
        onNewPasswordChange={onNewPasswordChange}
        onNewRoleChange={onNewRoleChange}
        onLogout={onLogout}
        onCreateUser={onCreateUser}
        onRefreshUsers={onRefreshUsers}
        onToggleUserStatus={onToggleUserStatus}
      />
      {!isUsersModule ? <ReviewPanel activeModule={activeModule} prepViewModel={prepViewModel} /> : null}
    </main>
  );
}
