import { ModuleViewModel, UserRole } from "../fixtureData";
import { AlgorithmModule } from "../../modules/algorithm/AlgorithmModule";
import { MockModule } from "../../modules/mock/MockModule";
import { PrepModule } from "../../modules/prep/PrepModule";
import { UserModule } from "../../modules/users/UserModule";
import { PrepViewModel } from "../../shared/api/prep";
import { DesktopRuntimeSnapshot, MaterialKind, UserRecord } from "../../shared/desktop/desktopBridge";

type WorkspaceProps = {
  activeModule: ModuleViewModel;
  prepViewModel: PrepViewModel;
  desktopSnapshot: DesktopRuntimeSnapshot | null;
  users: UserRecord[];
  newUsername: string;
  newPassword: string;
  newRole: "admin" | "member";
  userErrorMessage: string;
  currentUserRole: UserRole | null;
  onSelectMaterialFile: (kind: MaterialKind) => void;
  onNewUsernameChange: (value: string) => void;
  onNewPasswordChange: (value: string) => void;
  onNewRoleChange: (value: "admin" | "member") => void;
  onLogout: () => void;
  onCreateUser: () => void;
  onRefreshUsers: () => void;
  onToggleUserStatus: (username: string, status: "enabled" | "disabled") => void;
};

export function Workspace({
  activeModule,
  prepViewModel,
  desktopSnapshot,
  users,
  newUsername,
  newPassword,
  newRole,
  userErrorMessage,
  currentUserRole,
  onSelectMaterialFile,
  onNewUsernameChange,
  onNewPasswordChange,
  onNewRoleChange,
  onLogout,
  onCreateUser,
  onRefreshUsers,
  onToggleUserStatus,
}: WorkspaceProps) {
  const currentUserName = desktopSnapshot?.currentUser ?? "未登录";
  const canManageUsers = currentUserRole === "admin";

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
            <div className="workspace-user-box" aria-label="当前用户信息">
              <span className="workspace-user-name">{currentUserName}</span>
              <span className="workspace-user-state">在线</span>
              <button className="quiet-button" type="button" onClick={onLogout}>退出登录</button>
            </div>
          </div>
        ) : (
          <div className="workspace-actions">
            <button className="quiet-button" type="button">{activeModule.secondaryAction}</button>
            <button className="primary-button" type="button">{activeModule.primaryAction}</button>
            <div className="workspace-user-box" aria-label="当前用户信息">
              <span className="workspace-user-name">{currentUserName}</span>
              <span className="workspace-user-state">在线</span>
              <button className="quiet-button" type="button" onClick={onLogout}>退出登录</button>
            </div>
          </div>
        )}
      </header>

      {activeModule.id === "prep" && <PrepModule viewModel={prepViewModel} />}
      {activeModule.id === "mock" && <MockModule />}
      {activeModule.id === "algorithm" && <AlgorithmModule />}
      {activeModule.id === "users" && canManageUsers && (
        <UserModule
          users={users}
          newUsername={newUsername}
          newPassword={newPassword}
          newRole={newRole}
          errorMessage={userErrorMessage}
          onNewUsernameChange={onNewUsernameChange}
          onNewPasswordChange={onNewPasswordChange}
          onNewRoleChange={onNewRoleChange}
          onCreateUser={onCreateUser}
          onRefresh={onRefreshUsers}
          onToggleStatus={onToggleUserStatus}
        />
      )}
    </section>
  );
}
