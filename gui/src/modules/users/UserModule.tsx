type UserRecord = {
  userId: string;
  username: string;
  role: "admin" | "member";
  status: "enabled" | "disabled";
};

type UserModuleProps = {
  users: UserRecord[];
  newUsername: string;
  newPassword: string;
  newRole: "admin" | "member";
  errorMessage: string;
  onNewUsernameChange: (value: string) => void;
  onNewPasswordChange: (value: string) => void;
  onNewRoleChange: (value: "admin" | "member") => void;
  onCreateUser: () => void;
  onRefresh: () => void;
  onToggleStatus: (username: string, status: "enabled" | "disabled") => void;
};

export function UserModule({
  users,
  newUsername,
  newPassword,
  newRole,
  errorMessage,
  onNewUsernameChange,
  onNewPasswordChange,
  onNewRoleChange,
  onCreateUser,
  onRefresh,
  onToggleStatus,
}: UserModuleProps) {
  const hasUsers = users.length > 0;
  const enabledUserCount = users.filter((userRecord) => userRecord.status === "enabled").length;
  const disabledUserCount = users.length - enabledUserCount;

  return (
    <section className="users-module" aria-label="用户管理模块">
      <div className="users-overview" aria-label="用户统计">
        <div>
          <span className="users-overview-label">全部用户</span>
          <strong>{users.length}</strong>
        </div>
        <div>
          <span className="users-overview-label">启用</span>
          <strong>{enabledUserCount}</strong>
        </div>
        <div>
          <span className="users-overview-label">禁用</span>
          <strong>{disabledUserCount}</strong>
        </div>
      </div>

      <div className="users-management-grid">
        <article className="users-card users-create-card">
          <div className="users-section-head">
            <div>
              <h3>新增用户</h3>
              <p>填写基础账号信息后创建。</p>
            </div>
            <button className="quiet-button" type="button" onClick={onRefresh}>刷新列表</button>
          </div>
          <label className="users-field">
            <span>用户名</span>
            <input value={newUsername} onChange={(event) => onNewUsernameChange(event.target.value)} placeholder="例如 new_user" />
          </label>
          <label className="users-field">
            <span>密码</span>
            <input value={newPassword} onChange={(event) => onNewPasswordChange(event.target.value)} placeholder="输入初始密码" type="password" />
          </label>
          <label className="users-field">
            <span>角色</span>
            <select value={newRole} onChange={(event) => onNewRoleChange(event.target.value as "admin" | "member")}>
              <option value="member">member</option>
              <option value="admin">admin</option>
            </select>
          </label>
          <div className="users-form-actions">
            <button className="primary-button" type="button" onClick={onCreateUser}>创建用户</button>
          </div>
          {errorMessage ? <p className="runtime-error">{errorMessage}</p> : null}
        </article>

        <article className="users-card users-list-card">
          <div className="users-section-head">
            <div>
              <h3>用户列表</h3>
              <p>按账号、角色与状态集中管理。</p>
            </div>
          </div>
          {hasUsers ? (
            <div className="user-table" role="table" aria-label="用户列表">
              <div className="user-table-row user-table-head" role="row">
                <span role="columnheader">用户</span>
                <span role="columnheader">角色</span>
                <span role="columnheader">状态</span>
                <span role="columnheader">操作</span>
              </div>
              {users.map((userRecord) => (
                <div className="user-table-row" key={userRecord.userId} role="row">
                  <span className="user-name-cell" role="cell">
                    <strong>{userRecord.username}</strong>
                    <small>ID {userRecord.userId}</small>
                  </span>
                  <span role="cell">
                    <span className="meta-pill">{userRecord.role}</span>
                  </span>
                  <span role="cell">
                    <span className={userRecord.status === "enabled" ? "status-chip enabled" : "status-chip disabled"}>
                      {userRecord.status === "enabled" ? "启用" : "禁用"}
                    </span>
                  </span>
                  <span className="user-action-cell" role="cell">
                    {userRecord.status === "enabled" ? (
                      <button className="quiet-button" type="button" onClick={() => onToggleStatus(userRecord.username, "disabled")}>禁用</button>
                    ) : (
                      <button className="quiet-button" type="button" onClick={() => onToggleStatus(userRecord.username, "enabled")}>启用</button>
                    )}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="users-empty-state">暂无用户，请先创建账号。</p>
          )}
        </article>
      </div>
    </section>
  );
}
