import { useEffect, useState } from "react";
import { ShellLayout } from "./layout/ShellLayout";
import {
  DEFAULT_ACTIVE_MODULE_ID,
  getModuleViewModel,
  ModuleId,
} from "./fixtureData";
import {
  addUser,
  clearJobData,
  DesktopRuntimeSnapshot,
  endMockInterview,
  getApplicationResults,
  getConfirmationBatch as bridgeGetConfirmationBatch,
  getJobCollectionProgress,
  getJobDetail as bridgeGetJobDetail,
  getJobFilterResults,
  listUsers,
  loginUser,
  loadDesktopSnapshot,
  logoutUser,
  MaterialKind,
  prepareInterviewMaterials,
  prepareJobSearchProfile,
  saveJobSearchProfile,
  selectMaterialFile,
  snapshotWithDesktopError,
  startAlgorithmPractice,
  startMockInterview,
  submitBatch,
  submitMockAnswer,
  updateUserStatus,
  UserRecord,
} from "../shared/desktop/desktopBridge";
import { AlgorithmPracticeRuntimeClient, defaultAlgorithmPracticeViewModel } from "../shared/api/algorithm.js";
import { MockInterviewRuntimeClient, MockInterviewViewModel } from "../shared/api/mock";
import { JobRuntimeClient } from "../shared/api/job.js";
import type { JobScreenId } from "../modules/job/JobModule";
import { failedPrepViewModel, getPrepViewModel, missingInputsPrepViewModel } from "../shared/api/prep";
import { LoginPasswordInput } from "./LoginPasswordInput";

const idleMockViewModel: MockInterviewViewModel = {
  sessionId: "",
  status: "idle",
  errorMessage: null,
  currentPrompt: null,
  progress: { currentQuestionIndex: 0, totalQuestions: 0, currentFollowupIndex: 0, totalFollowups: 0 },
  reviewPanel: null,
  transcript: [],
};

const mockRuntimeClient: MockInterviewRuntimeClient = {
  startMockInterview,
  submitMockAnswer,
  endMockInterview,
  getCurrentViewModel: () => idleMockViewModel,
};

const algorithmRuntimeClient: AlgorithmPracticeRuntimeClient = {
  startAlgorithmPractice,
  getCurrentViewModel: () => defaultAlgorithmPracticeViewModel,
};

const jobRuntimeClient: JobRuntimeClient = {
  getJobSearchProfile: prepareJobSearchProfile,
  saveJobSearchProfile,
  getCollectionProgress: getJobCollectionProgress,
  getJobList: getJobFilterResults,
  getJobDetail: (jobId: string) => bridgeGetJobDetail("gui-mock-session", jobId),
  getConfirmationBatch: bridgeGetConfirmationBatch,
  getApplicationResults,
  submitBatch,
  clearJobData,
};

export function App() {
  const [activeModuleId, setActiveModuleId] = useState<ModuleId>(DEFAULT_ACTIVE_MODULE_ID);
  const [desktopSnapshot, setDesktopSnapshot] = useState<DesktopRuntimeSnapshot | null>(null);
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
  const [selectedJobIds, setSelectedJobIds] = useState<string[]>([]);
  const [jobActiveScreen, setJobActiveScreen] = useState<JobScreenId>("jobs");
  const activeModule = getModuleViewModel(activeModuleId);
  const currentUser = desktopSnapshot?.currentUser ?? null;
  const currentUserRole = desktopSnapshot?.currentUserRole ?? null;
  const isLoggedIn = Boolean(currentUser);

  useEffect(() => {
    if (activeModuleId === "users" && currentUserRole !== "admin") {
      setActiveModuleId(DEFAULT_ACTIVE_MODULE_ID);
    }
  }, [activeModuleId, currentUserRole]);

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
        isDesktopShell: true,
        pythonRuntimeRunning: false,
        knowledgeBaseStatus: "unknown",
        configPath: "config/interview-agent.toml",
        resumePath: null,
        jdPath: null,
        lastError: null,
        currentUser: null,
        currentUserRole: null,
      }), currentUser, currentUserRole }}
      prepViewModel={prepViewModel}
      prepIsLoading={prepIsLoading}
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
      onSelectedJobIdsChange={setSelectedJobIds}
      jobActiveScreen={jobActiveScreen}
      onJobActiveScreenChange={setJobActiveScreen}
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
