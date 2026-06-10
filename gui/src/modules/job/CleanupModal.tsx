import { useEffect, useRef } from "react";

type CleanupModalProps = {
  open: boolean;
  runningBatchId: string | null;
  onClose: () => void;
  onConfirm: () => void;
};

const willDeleteItems = [
  "岗位",
  "评估报告",
  "投递记录",
  "采集进度",
];

const willNotDeleteItems = [
  "简历原文件",
  "Chrome 登录态",
  "平台账号",
  "面试资料",
];

export function CleanupModal({ open, runningBatchId, onClose, onConfirm }: CleanupModalProps) {
  const titleRef = useRef<HTMLHeadingElement | null>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (open) {
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

  const hasRunningBatch = Boolean(runningBatchId);

  return (
    <div className="job-modal" role="dialog" aria-modal="true" aria-labelledby="cleanup-modal-title">
      <div className="job-modal-card">
        <div className="job-modal-head">
          <div>
            <h2 id="cleanup-modal-title" tabIndex={-1} ref={titleRef}>清空求职数据</h2>
            <p className="muted-text">只删除本模块的本地数据，不影响简历原文件和 Chrome 登录态。</p>
          </div>
          <button className="job-icon-button" type="button" aria-label="关闭" onClick={onClose}>×</button>
        </div>

        {hasRunningBatch && (
          <div className="job-cleanup-protected">
            <strong>运行中批次受保护</strong>
            <span className="muted-text">
              批次 {runningBatchId} 正在执行投递，清理操作将在批次完成后才生效。
            </span>
          </div>
        )}

        <div className="job-grid-2">
          <div className="job-card">
            <h3>将删除</h3>
            <div className="job-chip-row" style={{ marginTop: 12 }}>
              {willDeleteItems.map((item) => (
                <span className="job-state-tag bad" key={item}>{item}</span>
              ))}
            </div>
          </div>
          <div className="job-card">
            <h3>不会删除</h3>
            <div className="job-chip-row" style={{ marginTop: 12 }}>
              {willNotDeleteItems.map((item) => (
                <span className="job-state-tag good" key={item}>{item}</span>
              ))}
            </div>
          </div>
        </div>

        <div className="job-blocked-card">
          <div className="job-blocked-head">
            <h3>运行中批次保护</h3>
            <span className="job-state-tag warn">cleanup guard</span>
          </div>
          <p className="muted-text">存在采集或投递执行中的批次时，清理按钮进入禁用态；用户必须先暂停平台任务或等待批次完成。</p>
        </div>

        <div className="job-actions">
          <button className="ghost-button" type="button" onClick={onClose}>取消</button>
          <button
            className="job-danger-button"
            type="button"
            disabled={hasRunningBatch}
            onClick={() => { onConfirm(); onClose(); }}
          >
            {hasRunningBatch ? "批次运行中，暂不可清理" : "确认清空本地求职数据"}
          </button>
        </div>
      </div>
    </div>
  );
}
