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

  return (
    <section className="users-module" aria-label="用户管理模块">
      <article className="users-card">
        <div className="users-section-head">
          <h3>新增用户</h3>
          <button className="quiet-button" type="button" onClick={onRefresh}>刷新列表</button>
        </div>
        <div className="users-form-row">
          <input value={newUsername} onChange={(event) => onNewUsernameChange(event.target.value)} placeholder="用户名" />
          <input value={newPassword} onChange={(event) => onNewPasswordChange(event.target.value)} placeholder="密码" type="password" />
          <select value={newRole} onChange={(event) => onNewRoleChange(event.target.value as "admin" | "member")}>
            <option value="admin">admin</option>
            <option value="member">member</option>
          </select>
        </div>
        <div className="users-form-row">
          <button className="primary-button" type="button" onClick={onCreateUser}>创建用户</button>
        </div>
        {errorMessage ? <p className="runtime-error">{errorMessage}</p> : null}
      </article>

      <article className="users-card users-list-card">
        <h3>用户列表</h3>
        {hasUsers ? (
          <div className="user-list-grid">
            {users.map((userRecord) => (
              <article className="user-list-item" key={userRecord.userId}>
                <div className="user-list-item-head">
                  <strong>{userRecord.username}</strong>
                  <span className={userRecord.status === "enabled" ? "status-chip enabled" : "status-chip disabled"}>
                    {userRecord.status}
                  </span>
                </div>
                <div className="user-list-item-meta">
                  <span className="meta-pill">{userRecord.role}</span>
                  <span className="meta-pill">ID {userRecord.userId}</span>
                </div>
                <div className="user-list-item-actions">
                  {userRecord.status === "enabled" ? (
                    <button className="quiet-button" type="button" onClick={() => onToggleStatus(userRecord.username, "disabled")}>禁用</button>
                  ) : (
                    <button className="quiet-button" type="button" onClick={() => onToggleStatus(userRecord.username, "enabled")}>启用</button>
                  )}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="users-empty-state">暂无用户，请先创建账号。</p>
        )}
      </article>
    </section>
  );
}
