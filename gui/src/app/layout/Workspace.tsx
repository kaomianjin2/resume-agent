import { useState } from "react";
import { ModuleViewModel, UserRole } from "../fixtureData";
import { AlgorithmModule } from "../../modules/algorithm/AlgorithmModule";
import { MockModule } from "../../modules/mock/MockModule";
import { PrepModule } from "../../modules/prep/PrepModule";
import { UserModule } from "../../modules/users/UserModule";
import { JobModule, JobScreenId } from "../../modules/job/JobModule";
import { ConfirmModal } from "../../modules/job/ConfirmModal";
import { CleanupModal } from "../../modules/job/CleanupModal";
import { AlgorithmPracticeRuntimeClient } from "../../shared/api/algorithm.js";
import { MockInterviewRuntimeClient } from "../../shared/api/mock";
import { JobRuntimeClient, ConfirmationBatch, defaultConfirmationBatch } from "../../shared/api/job";
import { PrepViewModel } from "../../shared/api/prep";
import { DesktopRuntimeSnapshot, MaterialKind, UserRecord } from "../../shared/desktop/desktopBridge";

type WorkspaceProps = {
  activeModule: ModuleViewModel;
  prepViewModel: PrepViewModel;
  prepIsLoading: boolean;
  desktopSnapshot: DesktopRuntimeSnapshot | null;
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
  prepIsLoading,
  desktopSnapshot,
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
  const materialsReady = prepViewModel.status === "ready";
  const [confirmModalOpen, setConfirmModalOpen] = useState(false);
  const [cleanupModalOpen, setCleanupModalOpen] = useState(false);
  const [confirmBatch, setConfirmBatch] = useState<ConfirmationBatch>(defaultConfirmationBatch);
  const [submitting, setSubmitting] = useState(false);
  const isJobModule = activeModule.id === "job";

  async function handleOpenConfirmModal() {
    try {
      const batch = await jobRuntimeClient.getConfirmationBatch("gui-mock-session", selectedJobIds);
      setConfirmBatch(batch);
      setConfirmModalOpen(true);
    } catch {
      // 获取确认批次失败，仍然打开弹窗显示默认状态
      setConfirmModalOpen(true);
    }
  }

  async function handleConfirmBatch() {
    setSubmitting(true);
    try {
      await jobRuntimeClient.submitBatch("gui-mock-session", confirmBatch.batchId);
      setConfirmModalOpen(false);
    } catch {
      // 投递失败不关闭弹窗，允许用户重试
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCleanupData() {
    try {
      await jobRuntimeClient.clearJobData("gui-mock-session");
    } catch {
      // silent
    }
    setCleanupModalOpen(false);
  }

  return (
    <section className="workspace" aria-labelledby="workspace-title">
      {isJobModule ? (
        <>
          <div className="topbar">
            <div>
              <h2 id="workspace-title">候选岗位</h2>
              <p className="muted-text">筛选、查看详情、勾选后再进入批量确认。</p>
            </div>
            <div className="topbar-actions">
              <button className="icon-button" type="button" title="刷新" aria-label="刷新求职投递数据">⟳</button>
              <button className="icon-button" type="button" title="筛选" aria-label="打开筛选条件">⌕</button>
              <button className="danger-button" type="button" onClick={() => setCleanupModalOpen(true)}>清理数据</button>
            </div>
          </div>

          <JobModule
            runtimeClient={jobRuntimeClient}
            selectedJobIds={selectedJobIds}
            onSelectedJobIdsChange={onSelectedJobIdsChange}
            onOpenConfirmModal={handleOpenConfirmModal}
            onOpenCleanupModal={() => setCleanupModalOpen(true)}
            activeScreen={jobActiveScreen}
            onActiveScreenChange={onJobActiveScreenChange}
          />
          <ConfirmModal
            open={confirmModalOpen}
            batch={confirmBatch}
            onClose={() => setConfirmModalOpen(false)}
            onConfirm={handleConfirmBatch}
          />
          <CleanupModal
            open={cleanupModalOpen}
            runningBatchId={null}
            onClose={() => setCleanupModalOpen(false)}
            onConfirm={handleCleanupData}
          />
        </>
      ) : (
        <>
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

          {activeModule.id === "prep" && <PrepModule viewModel={prepViewModel} isLoading={prepIsLoading} />}
          {activeModule.id === "mock" && <MockModule materialsReady={materialsReady} runtimeClient={mockRuntimeClient} />}
          {activeModule.id === "algorithm" && <AlgorithmModule runtimeClient={algorithmRuntimeClient} />}
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
        </>
      )}
    </section>
  );
}
