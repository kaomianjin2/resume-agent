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
  endMockInterview,
  listUsers,
  loginUser,
  loadDesktopSnapshot,
  MaterialKind,
  logoutUser,
  prepareInterviewMaterials,
  selectMaterialFile,
  snapshotWithDesktopError,
  startMockInterview,
  submitMockAnswer,
  updateUserStatus,
  UserRecord,
} from "../shared/desktop/desktopBridge";
import { createFallbackMockInterviewClient, MockInterviewRuntimeClient } from "../shared/api/mock";
import { failedPrepViewModel, getPrepViewModel, missingInputsPrepViewModel } from "../shared/api/prep";
import { LoginPasswordInput } from "./LoginPasswordInput";

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
  const [loginPasswordVisible, setLoginPasswordVisible] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<"admin" | "member">("member");
  const [prepViewModel, setPrepViewModel] = useState(getPrepViewModel);
  const [prepIsLoading, setPrepIsLoading] = useState(false);
  const [fallbackMockRuntimeClient] = useState(createFallbackMockInterviewClient);
  const activeModule = getModuleViewModel(activeModuleId);
  const effectiveCurrentUser = desktopSnapshot?.currentUser ?? webPreviewUser;
  const effectiveCurrentUserRole = desktopSnapshot?.currentUserRole ?? webPreviewRole;
  const isLoggedIn = Boolean(effectiveCurrentUser);
  const mockRuntimeClient: MockInterviewRuntimeClient = desktopSnapshot?.isDesktopShell
    ? {
        startMockInterview,
        submitMockAnswer,
        endMockInterview,
        getCurrentViewModel: fallbackMockRuntimeClient.getCurrentViewModel,
      }
    : fallbackMockRuntimeClient;

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
    const nextSnapshot = await handleDesktopAction(() => selectMaterialFile(kind));
    if (!nextSnapshot?.resumePath && !nextSnapshot?.jdPath) {
      return;
    }
    const missingInputs = nextSnapshot.resumePath ? [] : ["resume_text"];
    setPrepViewModel(missingInputsPrepViewModel(missingInputs));
    setPrepIsLoading(true);
    try {
      setPrepViewModel(await prepareInterviewMaterials("gui-mock-session"));
    } catch (error) {
      setPrepViewModel(failedPrepViewModel(error instanceof Error ? error.message : String(error)));
    } finally {
      setPrepIsLoading(false);
    }
  }

  async function handleDesktopAction(action: () => Promise<DesktopRuntimeSnapshot>) {
    try {
      const nextSnapshot = await action();
      setDesktopSnapshot(nextSnapshot);
      return nextSnapshot;
    } catch (error) {
      const nextSnapshot = snapshotWithDesktopError(error, desktopSnapshot);
      setDesktopSnapshot(nextSnapshot);
      return nextSnapshot;
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
      setLoginPasswordVisible(false);
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
      setLoginPasswordVisible(false);
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
            <LoginPasswordInput
              value={loginPassword}
              visible={loginPasswordVisible}
              onChange={setLoginPassword}
              onVisibleChange={setLoginPasswordVisible}
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
      prepIsLoading={prepIsLoading}
      users={users}
      newUsername={newUsername}
      newPassword={newPassword}
      newRole={newRole}
      userErrorMessage={userErrorMessage}
      currentUserRole={effectiveCurrentUserRole}
      mockRuntimeClient={mockRuntimeClient}
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
