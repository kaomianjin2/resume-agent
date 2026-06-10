import { useEffect, useRef, useState } from "react";
import { ConfirmationBatch } from "../../shared/api/job";

type ConfirmModalProps = {
  open: boolean;
  batch: ConfirmationBatch;
  onClose: () => void;
  onConfirm: () => void;
};

const validationStatusVariant: Record<string, "good" | "warn" | "bad"> = {
  ready: "good",
  "stale-skipped": "warn",
  "duplicate-blocked": "bad",
  "button-disabled": "bad",
};

export function ConfirmModal({ open, batch, onClose, onConfirm }: ConfirmModalProps) {
  const [confirmed, setConfirmed] = useState(false);
  const titleRef = useRef<HTMLHeadingElement | null>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (open) {
      setConfirmed(false);
      lastFocusedRef.current = document.activeElement as HTMLElement | null;
      titleRef.current?.focus();
    } else if (lastFocusedRef.current?.focus) {
      lastFocusedRef.current.focus();
    }
  }, [open]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (!open) return;
      if (event.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="job-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title">
      <div className="job-modal-card">
        <div className="job-modal-head">
          <div>
            <h2 id="confirm-modal-title" tabIndex={-1} ref={titleRef}>批量确认投递</h2>
            <p className="muted-text">投递前最后确认，本批次提交后逐个平台执行。</p>
          </div>
          <button className="job-icon-button" type="button" aria-label="关闭" onClick={onClose}>×</button>
        </div>

        <div className="job-confirm-grid">
          <div className="job-metric-card">
            <span className="job-metric-label">岗位</span>
            <strong className="job-metric-value">{batch.jobCount}</strong>
          </div>
          <div className="job-metric-card">
            <span className="job-metric-label">平台</span>
            <strong className="job-metric-value">{batch.platformCount}</strong>
          </div>
          <div className="job-metric-card">
            <span className="job-metric-label">高风险</span>
            <strong className="job-metric-value warn">{batch.highRiskCount}</strong>
          </div>
          <div className="job-metric-card">
            <span className="job-metric-label">重复拦截</span>
            <strong className="job-metric-value bad">{batch.duplicateCount}</strong>
          </div>
        </div>

        <div className="job-grid-2">
          <div className="job-card">
            <h3>风险提示</h3>
            <div className="job-risk-list" style={{ marginTop: 12 }}>
              {batch.risks.map((risk) => (
                <div className="job-risk-item" key={risk.title}>
                  <strong>{risk.title}</strong>
                  <span className="muted-text">{risk.detail}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="job-card">
            <h3>简历摘要</h3>
            <p className="muted-text" style={{ marginTop: 10 }}>{batch.resumeSummary}</p>
          </div>
        </div>

        <div className="job-card">
          <div className="job-card-head">
            <h3>投递前重校验结果</h3>
            <span className="job-state-tag warn">提交集合会按此列表执行</span>
          </div>
          <div className="job-validation-list">
            {batch.validations.map((validation) => (
              <div className="job-validation-row" key={validation.jobRef}>
                <strong>{validation.jobRef}</strong>
                <span className={`job-state-tag ${validationStatusVariant[validation.status] ?? ""}`}>
                  {validation.status}
                </span>
                <span className="muted-text">{validation.reason}</span>
                {validation.willSubmit ? (
                  <span className="job-state-tag good">将提交</span>
                ) : validation.status === "stale-skipped" ? (
                  <button className="ghost-button" type="button">重新确认</button>
                ) : validation.status === "duplicate-blocked" ? (
                  <span className="job-state-tag bad">不提交</span>
                ) : (
                  <span className="job-state-tag bad">跳过</span>
                )}
              </div>
            ))}
          </div>
        </div>

        <label className="job-confirm-checkbox">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />
          <span>已审核岗位、风险和投递话术，允许本批次执行投递。未确认、重复或陈旧岗位会在提交前被跳过。</span>
        </label>

        <div className="job-actions">
          <button className="ghost-button" type="button" onClick={onClose}>返回修改选择</button>
          <button
            className="primary-button"
            type="button"
            disabled={!confirmed}
            onClick={() => { onConfirm(); onClose(); }}
          >
            确认并创建批次
          </button>
        </div>
      </div>
    </div>
  );
}
