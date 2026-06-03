import { useEffect, useState } from "react";
import { ShellLayout } from "./layout/ShellLayout";
import {
  DEFAULT_ACTIVE_MODULE_ID,
  getModuleViewModel,
  ModuleId,
  UserRole,
} from "./fixtureData";
import {
  addUser,
  DesktopRuntimeSnapshot,
  listUsers,
  loginUser,
  loadDesktopSnapshot,
  MaterialKind,
  logoutUser,
  selectMaterialFile,
  snapshotWithDesktopError,
  updateUserStatus,
  UserRecord,
} from "../shared/desktop/desktopBridge";
import { getPrepViewModel } from "../shared/api/prep";

export function App() {
  const [activeModuleId, setActiveModuleId] = useState<ModuleId>(DEFAULT_ACTIVE_MODULE_ID);
  const [desktopSnapshot, setDesktopSnapshot] = useState<DesktopRuntimeSnapshot | null>(null);
  const [webPreviewUser, setWebPreviewUser] = useState<string | null>(null);
  const [webPreviewRole, setWebPreviewRole] = useState<UserRole | null>(null);
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loginError, setLoginError] = useState("");
  const [userErrorMessage, setUserErrorMessage] = useState("");
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<"admin" | "member">("member");
  const activeModule = getModuleViewModel(activeModuleId);
  const prepViewModel = getPrepViewModel();
  const effectiveCurrentUser = desktopSnapshot?.currentUser ?? webPreviewUser;
  const effectiveCurrentUserRole = desktopSnapshot?.currentUserRole ?? webPreviewRole;
  const isLoggedIn = Boolean(effectiveCurrentUser);

  useEffect(() => {
    if (activeModuleId === "users" && effectiveCurrentUserRole !== "admin") {
      setActiveModuleId(DEFAULT_ACTIVE_MODULE_ID);
    }
  }, [activeModuleId, effectiveCurrentUserRole]);

  useEffect(() => {
    void handleDesktopAction(loadDesktopSnapshot);
    void refreshUsers();
  }, []);

  async function handleSelectMaterialFile(kind: MaterialKind) {
    await handleDesktopAction(() => selectMaterialFile(kind));
  }

  async function handleDesktopAction(action: () => Promise<DesktopRuntimeSnapshot>) {
    try {
      setDesktopSnapshot(await action());
    } catch (error) {
      setDesktopSnapshot((currentSnapshot) => snapshotWithDesktopError(error, currentSnapshot));
    }
  }

  async function refreshUsers() {
    try {
      setUsers(await listUsers());
      setUserErrorMessage("");
    } catch (error) {
      setUserErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleLogin() {
    if (!desktopSnapshot?.isDesktopShell) {
      const previewUsername = loginUsername.trim() || "preview_user";
      setWebPreviewUser(previewUsername);
      setWebPreviewRole("member");
      setActiveModuleId(DEFAULT_ACTIVE_MODULE_ID);
      setLoginError("");
      setLoginPassword("");
      return;
    }

    try {
      const userRecord = await loginUser(loginUsername, loginPassword);
      if (!userRecord) {
        setLoginError("登录失败：用户名或密码错误，或用户已禁用。");
        return;
      }
      setActiveModuleId(DEFAULT_ACTIVE_MODULE_ID);
      setLoginError("");
      setLoginPassword("");
      await handleDesktopAction(loadDesktopSnapshot);
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleLogout() {
    if (!desktopSnapshot?.isDesktopShell) {
      setWebPreviewUser(null);
      setWebPreviewRole(null);
      setActiveModuleId(DEFAULT_ACTIVE_MODULE_ID);
      return;
    }
    await logoutUser();
    setActiveModuleId(DEFAULT_ACTIVE_MODULE_ID);
    await handleDesktopAction(loadDesktopSnapshot);
  }

  async function handleCreateUser() {
    try {
      await addUser(newUsername, newPassword, newRole);
      setNewPassword("");
      setUserErrorMessage("");
      await refreshUsers();
    } catch (error) {
      setUserErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleToggleUserStatus(username: string, status: "enabled" | "disabled") {
    try {
      await updateUserStatus(username, status);
      setUserErrorMessage("");
      await refreshUsers();
      await handleDesktopAction(loadDesktopSnapshot);
    } catch (error) {
      setUserErrorMessage(error instanceof Error ? error.message : String(error));
    }
  }

  if (!isLoggedIn) {
    return (
      <main className="login-shell" aria-label="登录页面">
        <section className="login-card">
          <h1>Interview Agent 登录</h1>
          <p className="login-copy">登录后进入 Agent 首页。</p>
          <div className="login-form-row">
            <input
              value={loginUsername}
              onChange={(event) => setLoginUsername(event.target.value)}
              placeholder="用户名"
            />
            <input
              value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
              placeholder="密码"
              type="password"
            />
          </div>
          <div className="login-form-row">
            <button className="primary-button" type="button" onClick={handleLogin}>登录</button>
          </div>
          {loginError ? <p className="runtime-error">{loginError}</p> : null}
        </section>
      </main>
    );
  }

  return (
    <ShellLayout
      activeModule={activeModule}
      activeModuleId={activeModuleId}
      desktopSnapshot={{ ...(desktopSnapshot ?? {
        isDesktopShell: false,
        pythonRuntimeRunning: false,
        knowledgeBaseStatus: "web-shell",
        configPath: "config/interview-agent.toml",
        resumePath: null,
        jdPath: null,
        lastError: null,
        currentUser: null,
        currentUserRole: null,
      }), currentUser: effectiveCurrentUser, currentUserRole: effectiveCurrentUserRole }}
      prepViewModel={prepViewModel}
      users={users}
      newUsername={newUsername}
      newPassword={newPassword}
      newRole={newRole}
      userErrorMessage={userErrorMessage}
      currentUserRole={effectiveCurrentUserRole}
      onModuleChange={setActiveModuleId}
      onSelectMaterialFile={handleSelectMaterialFile}
      onNewUsernameChange={setNewUsername}
      onNewPasswordChange={setNewPassword}
      onNewRoleChange={setNewRole}
      onLogout={handleLogout}
      onCreateUser={handleCreateUser}
      onRefreshUsers={refreshUsers}
      onToggleUserStatus={handleToggleUserStatus}
    />
  );
}
