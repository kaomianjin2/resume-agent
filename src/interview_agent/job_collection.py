from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict
from pathlib import Path

from interview_agent.job_platform_adapters import (
    JobPlatformAdapter,
    JobSearchRequest,
    PlatformAdapterError,
    PlatformAdapterErrorType,
    StandardJob,
)
from interview_agent.sensitive import assert_no_sensitive_payload
from interview_agent.storage import record_collection_progress, save_platform_collection_task


MANUAL_TAKEOVER_ERROR_TYPES = {
    PlatformAdapterErrorType.CAPTCHA_REQUIRED,
    PlatformAdapterErrorType.ACCOUNT_RISK_CONTROL,
    PlatformAdapterErrorType.FORCED_POPUP,
}
BACKOFF_ERROR_TYPES = {PlatformAdapterErrorType.RATE_LIMITED}


class JobCollectionOrchestrator:
    def __init__(
        self,
        adapters: Mapping[str, JobPlatformAdapter],
        *,
        database_path: Path | str | None = None,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self._adapters = dict(adapters)
        self._database_path = database_path
        self._progress_callback = progress_callback
        self._requests: dict[str, JobSearchRequest] = {}
        self._platform_progress: dict[str, dict[str, object]] = {}
        self._jobs_by_platform: dict[str, list[StandardJob]] = {}

    def collect(
        self,
        *,
        collection_task_id: str,
        platforms: list[str],
        job_profile: dict[str, object],
        hard_filters: dict[str, object],
        ranking_preferences: dict[str, object],
        keyword: str,
    ) -> dict[str, object]:
        request = JobSearchRequest(
            job_profile=job_profile,
            hard_filters=hard_filters,
            ranking_preferences=ranking_preferences,
            keyword=keyword,
        )
        assert_no_sensitive_payload(request, error_message="采集请求包含敏感凭据")
        self._requests[collection_task_id] = request
        self._ensure_collection_task(collection_task_id, keyword)
        for platform in platforms:
            self._collect_platform(collection_task_id, platform, self._adapters[platform], request, retry_count=0)
        return self._result()

    def retry_failed_platform(
        self,
        *,
        collection_task_id: str,
        platform: str,
        adapter: JobPlatformAdapter | None = None,
    ) -> dict[str, object]:
        if collection_task_id not in self._requests:
            raise ValueError("采集任务不存在")
        progress = self._platform_progress.get(platform)
        if not progress or progress.get("status") not in {"failed", "manual_takeover", "backoff"}:
            raise ValueError("平台没有可恢复采集状态")
        next_retry_count = int(progress.get("retry_count", 0)) + 1
        selected_adapter = adapter or self._adapters[platform]
        self._adapters[platform] = selected_adapter
        self._write_progress(collection_task_id, platform, "retrying", retry_count=next_retry_count)
        self._collect_platform(collection_task_id, platform, selected_adapter, self._requests[collection_task_id], retry_count=next_retry_count)
        return self._result()

    def _collect_platform(
        self,
        collection_task_id: str,
        platform: str,
        adapter: JobPlatformAdapter,
        request: JobSearchRequest,
        *,
        retry_count: int,
    ) -> None:
        try:
            self._write_progress(collection_task_id, platform, "started", retry_count=retry_count)
            result = adapter.search_jobs(request)
            if result.status == "failed":
                self._write_failure(collection_task_id, platform, result.errors, retry_count)
                return

            list_jobs = adapter.collect_job_list(result.search_id)
            self._write_progress(collection_task_id, platform, "page_collected", current_page=1, last_job_offset=len(list_jobs), retry_count=retry_count)
            detail_jobs = [adapter.read_job_detail(job.platform_job_id) for job in list_jobs]
            assert_no_sensitive_payload(detail_jobs, error_message="采集结果包含敏感凭据")
            self._jobs_by_platform[platform] = detail_jobs
            self._write_progress(
                collection_task_id,
                platform,
                "detail_collected",
                current_page=1,
                last_job_offset=len(detail_jobs),
                retry_count=retry_count,
                collected_job_count=len(detail_jobs),
            )
            self._write_progress(
                collection_task_id,
                platform,
                "completed",
                current_page=1,
                last_job_offset=len(detail_jobs),
                retry_count=retry_count,
                collected_job_count=len(detail_jobs),
            )
        except PlatformAdapterError as error:
            self._write_failure(collection_task_id, platform, [error], retry_count)
        except Exception:
            self._write_progress(collection_task_id, platform, "failed", retry_count=retry_count, failure_reason="platform_exception")

    def _write_failure(
        self,
        collection_task_id: str,
        platform: str,
        errors: list[PlatformAdapterError],
        retry_count: int,
    ) -> None:
        error_type = errors[0].error_type if errors else None
        failure_reason = error_type.value if error_type is not None else "unknown_error"
        if error_type in MANUAL_TAKEOVER_ERROR_TYPES:
            self._write_progress(
                collection_task_id,
                platform,
                "manual_takeover",
                retry_count=retry_count,
                failure_reason=failure_reason,
                manual_takeover_required=True,
                risk_control={
                    "type": "manual_takeover",
                    "reason": failure_reason,
                    "hint": "平台要求人工处理后再恢复采集",
                },
            )
            return
        if error_type in BACKOFF_ERROR_TYPES:
            self._write_progress(
                collection_task_id,
                platform,
                "backoff",
                retry_count=retry_count,
                failure_reason=failure_reason,
                risk_control={
                    "type": "backoff",
                    "reason": failure_reason,
                    "hint": "平台限流，已进入退避状态",
                },
            )
            return
        self._write_progress(collection_task_id, platform, "failed", retry_count=retry_count, failure_reason=failure_reason)

    def _write_progress(
        self,
        collection_task_id: str,
        platform: str,
        status: str,
        *,
        current_page: int = 0,
        last_job_offset: int = 0,
        retry_count: int = 0,
        failure_reason: str | None = None,
        collected_job_count: int = 0,
        manual_takeover_required: bool = False,
        risk_control: dict[str, str] | None = None,
    ) -> None:
        progress = self._platform_progress.get(platform)
        if progress is None:
            progress = {
                "platform": platform,
                "status": status,
                "current_page": current_page,
                "last_job_offset": last_job_offset,
                "retry_count": retry_count,
                "failure_reason": failure_reason,
                "manual_takeover_required": manual_takeover_required,
                "collected_job_count": collected_job_count,
                "risk_control": risk_control,
                "events": [],
            }
            self._platform_progress[platform] = progress

        progress.update(
            {
                "status": status,
                "current_page": current_page,
                "last_job_offset": last_job_offset,
                "retry_count": retry_count,
                "failure_reason": failure_reason,
                "manual_takeover_required": manual_takeover_required,
                "collected_job_count": max(int(progress.get("collected_job_count", 0)), collected_job_count),
                "risk_control": risk_control,
            }
        )
        events = list(progress["events"])
        events.append({"status": status, "current_page": current_page, "last_job_offset": last_job_offset})
        progress["events"] = events
        self._persist_progress(collection_task_id, progress)
        if self._progress_callback is not None:
            self._progress_callback(self._result())

    def _persist_progress(self, collection_task_id: str, progress: dict[str, object]) -> None:
        if self._database_path is None:
            return
        record_collection_progress(
            self._database_path,
            collection_task_id=collection_task_id,
            platform=str(progress["platform"]),
            current_page=int(progress["current_page"]),
            last_job_offset=int(progress["last_job_offset"]),
            retry_count=int(progress["retry_count"]),
            failure_reason=progress["failure_reason"] if isinstance(progress["failure_reason"], str) else None,
            manual_takeover_required=bool(progress["manual_takeover_required"]),
            status=str(progress["status"]),
        )

    def _ensure_collection_task(self, collection_task_id: str, keyword: str) -> None:
        if self._database_path is None:
            return
        save_platform_collection_task(
            self._database_path,
            collection_task_id=collection_task_id,
            platform="multi",
            search_keyword=keyword,
            status="running",
        )

    def _result(self) -> dict[str, object]:
        jobs = [job for platform_jobs in self._jobs_by_platform.values() for job in platform_jobs]
        progress = {platform: dict(platform_progress) for platform, platform_progress in self._platform_progress.items()}
        failed_count = sum(1 for platform_progress in progress.values() if platform_progress["status"] == "failed")
        completed_count = sum(1 for platform_progress in progress.values() if platform_progress["status"] == "completed")
        manual_takeover_count = sum(1 for platform_progress in progress.values() if platform_progress["status"] == "manual_takeover")
        backoff_count = sum(1 for platform_progress in progress.values() if platform_progress["status"] == "backoff")
        stopped_statuses = {"completed", "failed", "manual_takeover", "backoff"}
        running_count = sum(1 for platform_progress in progress.values() if platform_progress["status"] not in stopped_statuses)
        risk_control_count = manual_takeover_count + backoff_count
        status = (
            "running"
            if running_count
            else "manual_takeover"
            if manual_takeover_count and not completed_count and not failed_count and not backoff_count
            else "backoff"
            if backoff_count and not completed_count and not failed_count and not manual_takeover_count
            else "failed"
            if failed_count and not completed_count and not risk_control_count
            else "partial"
            if failed_count or risk_control_count
            else "success"
        )
        return {
            "status": status,
            "jobs": jobs,
            "platform_progress": progress,
        }


def job_collection_view_model(result: dict[str, object]) -> dict[str, object]:
    platform_progress = result.get("platform_progress")
    jobs = result.get("jobs")
    if not isinstance(platform_progress, dict) or not isinstance(jobs, list):
        raise ValueError("采集结果格式无效")

    job_view_models = [asdict(job) for job in jobs if isinstance(job, StandardJob)]
    platform_view_models = {str(platform): dict(progress) for platform, progress in platform_progress.items() if isinstance(progress, dict)}
    view_model = {
        "status": result["status"],
        "summary": {
            "platform_count": len(platform_view_models),
            "completed_platform_count": sum(1 for progress in platform_view_models.values() if progress.get("status") == "completed"),
            "failed_platform_count": sum(1 for progress in platform_view_models.values() if progress.get("status") == "failed"),
            "manual_takeover_platform_count": sum(1 for progress in platform_view_models.values() if progress.get("status") == "manual_takeover"),
            "backoff_platform_count": sum(1 for progress in platform_view_models.values() if progress.get("status") == "backoff"),
            "collected_job_count": len(job_view_models),
        },
        "platforms": platform_view_models,
        "jobs": job_view_models,
    }
    assert_no_sensitive_payload(view_model, error_message="采集进度包含敏感凭据")
    return view_model
