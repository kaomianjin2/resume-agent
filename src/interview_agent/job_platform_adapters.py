from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Protocol
from uuid import uuid4

from interview_agent.sensitive import assert_no_sensitive_payload, flatten_payload, summarize_url


AdapterResultStatus = Literal["success", "failed", "partial"]
ApplicationSubmissionStatus = Literal["submitted", "failed", "skipped", "duplicate"]


class PlatformAdapterErrorType(str, Enum):
    LOGIN_EXPIRED = "login_expired"
    PAGE_STRUCTURE_CHANGED = "page_structure_changed"
    MISSING_FIELD = "missing_field"
    BUTTON_UNAVAILABLE = "button_unavailable"
    DUPLICATE_APPLICATION = "duplicate_application"
    CAPTCHA_REQUIRED = "captcha_required"
    RATE_LIMITED = "rate_limited"
    ACCOUNT_RISK_CONTROL = "account_risk_control"
    FORCED_POPUP = "forced_popup"


@dataclass(frozen=True)
class PlatformAdapterError:
    error_type: PlatformAdapterErrorType
    platform: str
    stage: str
    message: str
    page_url: str | None = None
    field_name: str | None = None


@dataclass(frozen=True)
class StandardJob:
    platform: str
    platform_job_id: str
    title: str
    company_name: str
    location: str
    remote_policy: str | None
    salary_range: str | None
    level: str | None
    experience_requirement: str | None
    education_requirement: str | None
    industry: str | None
    company_size: str | None
    funding_stage: str | None
    tech_stack: list[str]
    benefits: list[str]
    published_at: str | None
    detail_url: str
    jd_text: str
    collected_at: str
    field_confidence: dict[str, str]


@dataclass(frozen=True)
class JobSearchRequest:
    job_profile: dict[str, object]
    hard_filters: dict[str, object]
    ranking_preferences: dict[str, object]
    keyword: str


@dataclass(frozen=True)
class PlatformExecutionResult:
    platform: str
    status: AdapterResultStatus
    search_id: str
    jobs: list[StandardJob] = field(default_factory=list)
    errors: list[PlatformAdapterError] = field(default_factory=list)


@dataclass(frozen=True)
class ConfirmationApplicationRequest:
    confirmation_batch_id: str
    job: StandardJob
    application_message: str
    confirmed: bool


@dataclass(frozen=True)
class ApplicationSubmissionResult:
    platform: str
    platform_job_id: str
    status: ApplicationSubmissionStatus
    error: PlatformAdapterError | None = None
    platform_message: str | None = None
    submitted_at: str | None = None
    duplicate_detected: bool = False


class BrowserAutomationBoundary(Protocol):
    def open_page(self, url: str) -> None:
        """Use an existing browser session without exposing credentials."""


class JobPlatformAdapter(Protocol):
    platform: str

    def search_jobs(self, request: JobSearchRequest) -> PlatformExecutionResult:
        pass

    def collect_job_list(self, search_id: str) -> list[StandardJob]:
        pass

    def read_job_detail(self, platform_job_id: str) -> StandardJob:
        pass

    def is_already_applied(self, platform_job_id: str) -> bool:
        pass

    def submit_application(self, request: ConfirmationApplicationRequest) -> ApplicationSubmissionResult:
        pass


class FakeJobPlatformAdapter:
    def __init__(
        self,
        *,
        platform: str,
        jobs: list[StandardJob] | None = None,
        applied_job_ids: set[str] | None = None,
        search_error: PlatformAdapterError | None = None,
        submit_results: dict[str, ApplicationSubmissionResult] | None = None,
    ) -> None:
        self.platform = platform
        self._jobs = jobs or []
        self._applied_job_ids = applied_job_ids or set()
        self._search_error = search_error
        self._submit_results = submit_results or {}
        self._last_search_id: str | None = None

    def search_jobs(self, request: JobSearchRequest) -> PlatformExecutionResult:
        _assert_no_sensitive_payload(request)
        self._last_search_id = f"{self.platform}-search-{uuid4()}"
        if self._search_error is not None:
            safe_error = _sanitize_adapter_error(self._search_error)
            return PlatformExecutionResult(
                platform=self.platform,
                status="failed",
                search_id=self._last_search_id,
                errors=[safe_error],
            )
        _assert_no_sensitive_payload(self._jobs)
        return PlatformExecutionResult(
            platform=self.platform,
            status="success",
            search_id=self._last_search_id,
            jobs=list(self._jobs),
        )

    def collect_job_list(self, search_id: str) -> list[StandardJob]:
        if not self._last_search_id or search_id != self._last_search_id:
            raise ValueError("搜索任务不存在")
        _assert_no_sensitive_payload(self._jobs)
        return list(self._jobs)

    def read_job_detail(self, platform_job_id: str) -> StandardJob:
        for job in self._jobs:
            if job.platform_job_id == platform_job_id:
                _assert_no_sensitive_payload(job)
                return job
        raise ValueError("岗位不存在")

    def is_already_applied(self, platform_job_id: str) -> bool:
        return platform_job_id in self._applied_job_ids

    def submit_application(self, request: ConfirmationApplicationRequest) -> ApplicationSubmissionResult:
        _assert_no_sensitive_payload(request)
        if not request.confirmed:
            return ApplicationSubmissionResult(
                platform=self.platform,
                platform_job_id=request.job.platform_job_id,
                status="skipped",
                error=PlatformAdapterError(
                    error_type=PlatformAdapterErrorType.BUTTON_UNAVAILABLE,
                    platform=self.platform,
                    stage="submit",
                    message="投递前缺少用户确认",
                ),
            )
        if request.job.platform_job_id in self._submit_results:
            result = self._submit_results[request.job.platform_job_id]
            safe_result = _sanitize_submission_result(result)
            _assert_no_sensitive_payload(safe_result)
            return safe_result
        if request.job.platform_job_id in self._applied_job_ids:
            return ApplicationSubmissionResult(
                platform=self.platform,
                platform_job_id=request.job.platform_job_id,
                status="duplicate",
                error=PlatformAdapterError(
                    error_type=PlatformAdapterErrorType.DUPLICATE_APPLICATION,
                    platform=self.platform,
                    stage="submit",
                    message="重复投递",
                ),
                duplicate_detected=True,
            )
        return ApplicationSubmissionResult(
            platform=self.platform,
            platform_job_id=request.job.platform_job_id,
            status="submitted",
        )


def _assert_no_sensitive_payload(value: object) -> None:
    assert_no_sensitive_payload(value, error_message="适配器结果包含敏感凭据")


def _flatten_payload(value: object) -> str:
    return flatten_payload(value)


def _sanitize_adapter_error(error: PlatformAdapterError) -> PlatformAdapterError:
    safe_error = PlatformAdapterError(
        error_type=error.error_type,
        platform=error.platform,
        stage=error.stage,
        message="浏览器自动化错误已脱敏",
        page_url=summarize_url(error.page_url),
        field_name=None,
    )
    _assert_no_sensitive_payload(safe_error)
    return safe_error


def _sanitize_submission_result(result: ApplicationSubmissionResult) -> ApplicationSubmissionResult:
    safe_error = _sanitize_adapter_error(result.error) if result.error is not None else None
    safe_result = ApplicationSubmissionResult(
        platform=result.platform,
        platform_job_id=result.platform_job_id,
        status=result.status,
        error=safe_error,
        platform_message="浏览器自动化错误已脱敏" if result.platform_message else None,
        submitted_at=result.submitted_at,
        duplicate_detected=result.duplicate_detected,
    )
    _assert_no_sensitive_payload(safe_result)
    return safe_result
