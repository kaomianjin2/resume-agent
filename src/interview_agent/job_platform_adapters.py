from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from html.parser import HTMLParser
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
class PlatformAdapterError(Exception):
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


class BossReadonlyJobPlatformAdapter:
    platform = "boss"

    def __init__(
        self,
        *,
        list_html: str,
        detail_html_by_job_id: dict[str, str],
        state_html_by_job_id: dict[str, str] | None = None,
    ) -> None:
        self._list_html = list_html
        self._detail_html_by_job_id = dict(detail_html_by_job_id)
        self._state_html_by_job_id = dict(state_html_by_job_id or {})
        self._last_search_id: str | None = None
        self._list_jobs: list[StandardJob] = []

    def search_jobs(self, request: JobSearchRequest) -> PlatformExecutionResult:
        _assert_no_sensitive_payload(request)
        self._last_search_id = f"{self.platform}-search-{uuid4()}"
        error = classify_job_platform_fixture_error(platform=self.platform, stage="search", html=self._list_html)
        if error is not None:
            return PlatformExecutionResult(
                platform=self.platform,
                status="failed",
                search_id=self._last_search_id,
                errors=[_sanitize_adapter_error(error)],
            )
        self._list_jobs = [_mark_missing_fields_low_confidence(job) for job in parse_job_list_fixture(self._list_html)]
        _assert_no_sensitive_payload(self._list_jobs)
        return PlatformExecutionResult(
            platform=self.platform,
            status="success",
            search_id=self._last_search_id,
            jobs=list(self._list_jobs),
        )

    def collect_job_list(self, search_id: str) -> list[StandardJob]:
        if not self._last_search_id or search_id != self._last_search_id:
            raise ValueError("搜索任务不存在")
        _assert_no_sensitive_payload(self._list_jobs)
        return list(self._list_jobs)

    def read_job_detail(self, platform_job_id: str) -> StandardJob:
        html = self._detail_html_by_job_id.get(platform_job_id)
        if html is None:
            raise ValueError("岗位详情不存在")
        error = classify_job_platform_fixture_error(platform=self.platform, stage="detail", html=html)
        if error is not None:
            raise _sanitize_adapter_error(error)
        job = _mark_missing_fields_low_confidence(parse_job_detail_fixture(html))
        _assert_no_sensitive_payload(job)
        return job

    def is_already_applied(self, platform_job_id: str) -> bool:
        html = self._state_html_by_job_id.get(platform_job_id)
        if html is None:
            return False
        error = classify_job_platform_fixture_error(platform=self.platform, stage="state", html=html)
        if error is not None and error.error_type is not PlatformAdapterErrorType.DUPLICATE_APPLICATION:
            raise _sanitize_adapter_error(error)
        return error is not None and error.error_type is PlatformAdapterErrorType.DUPLICATE_APPLICATION

    def submit_application(self, request: ConfirmationApplicationRequest) -> ApplicationSubmissionResult:
        _assert_no_sensitive_payload(request)
        result = ApplicationSubmissionResult(
            platform=self.platform,
            platform_job_id=request.job.platform_job_id,
            status="skipped",
            error=PlatformAdapterError(
                error_type=PlatformAdapterErrorType.BUTTON_UNAVAILABLE,
                platform=self.platform,
                stage="submit",
                message="BOSS 只读适配器不执行投递",
            ),
        )
        _assert_no_sensitive_payload(result)
        return result


class LiepinReadonlyJobPlatformAdapter:
    platform = "liepin"

    def __init__(
        self,
        *,
        list_html: str,
        detail_html_by_job_id: dict[str, str],
        state_html_by_job_id: dict[str, str] | None = None,
    ) -> None:
        self._list_html = list_html
        self._detail_html_by_job_id = dict(detail_html_by_job_id)
        self._state_html_by_job_id = dict(state_html_by_job_id or {})
        self._last_search_id: str | None = None
        self._list_jobs: list[StandardJob] = []

    def search_jobs(self, request: JobSearchRequest) -> PlatformExecutionResult:
        _assert_no_sensitive_payload(request)
        self._last_search_id = f"{self.platform}-search-{uuid4()}"
        error = classify_job_platform_fixture_error(platform=self.platform, stage="search", html=self._list_html)
        if error is not None:
            return PlatformExecutionResult(
                platform=self.platform,
                status="failed",
                search_id=self._last_search_id,
                errors=[_sanitize_adapter_error(error)],
            )
        self._list_jobs = [_mark_missing_fields_low_confidence(job) for job in parse_job_list_fixture(self._list_html)]
        _assert_no_sensitive_payload(self._list_jobs)
        return PlatformExecutionResult(
            platform=self.platform,
            status="success",
            search_id=self._last_search_id,
            jobs=list(self._list_jobs),
        )

    def collect_job_list(self, search_id: str) -> list[StandardJob]:
        if not self._last_search_id or search_id != self._last_search_id:
            raise ValueError("搜索任务不存在")
        _assert_no_sensitive_payload(self._list_jobs)
        return list(self._list_jobs)

    def read_job_detail(self, platform_job_id: str) -> StandardJob:
        html = self._detail_html_by_job_id.get(platform_job_id)
        if html is None:
            raise ValueError("岗位详情不存在")
        error = classify_job_platform_fixture_error(platform=self.platform, stage="detail", html=html)
        if error is not None:
            raise _sanitize_adapter_error(error)
        job = _mark_missing_fields_low_confidence(parse_job_detail_fixture(html))
        _assert_no_sensitive_payload(job)
        return job

    def is_already_applied(self, platform_job_id: str) -> bool:
        html = self._state_html_by_job_id.get(platform_job_id)
        if html is None:
            return False
        error = classify_job_platform_fixture_error(platform=self.platform, stage="state", html=html)
        if error is not None and error.error_type is not PlatformAdapterErrorType.DUPLICATE_APPLICATION:
            raise _sanitize_adapter_error(error)
        return error is not None and error.error_type is PlatformAdapterErrorType.DUPLICATE_APPLICATION

    def submit_application(self, request: ConfirmationApplicationRequest) -> ApplicationSubmissionResult:
        _assert_no_sensitive_payload(request)
        result = ApplicationSubmissionResult(
            platform=self.platform,
            platform_job_id=request.job.platform_job_id,
            status="skipped",
            error=PlatformAdapterError(
                error_type=PlatformAdapterErrorType.BUTTON_UNAVAILABLE,
                platform=self.platform,
                stage="submit",
                message="猎聘只读适配器不执行投递",
            ),
        )
        _assert_no_sensitive_payload(result)
        return result


class LagouReadonlyJobPlatformAdapter:
    platform = "lagou"

    def __init__(
        self,
        *,
        list_html: str,
        detail_html_by_job_id: dict[str, str],
        state_html_by_job_id: dict[str, str] | None = None,
    ) -> None:
        self._list_html = list_html
        self._detail_html_by_job_id = dict(detail_html_by_job_id)
        self._state_html_by_job_id = dict(state_html_by_job_id or {})
        self._last_search_id: str | None = None
        self._list_jobs: list[StandardJob] = []

    def search_jobs(self, request: JobSearchRequest) -> PlatformExecutionResult:
        _assert_no_sensitive_payload(request)
        self._last_search_id = f"{self.platform}-search-{uuid4()}"
        error = classify_job_platform_fixture_error(platform=self.platform, stage="search", html=self._list_html)
        if error is not None:
            return PlatformExecutionResult(
                platform=self.platform,
                status="failed",
                search_id=self._last_search_id,
                errors=[_sanitize_adapter_error(error)],
            )
        self._list_jobs = [_mark_missing_fields_low_confidence(job) for job in parse_job_list_fixture(self._list_html)]
        _assert_no_sensitive_payload(self._list_jobs)
        return PlatformExecutionResult(
            platform=self.platform,
            status="success",
            search_id=self._last_search_id,
            jobs=list(self._list_jobs),
        )

    def collect_job_list(self, search_id: str) -> list[StandardJob]:
        if not self._last_search_id or search_id != self._last_search_id:
            raise ValueError("搜索任务不存在")
        _assert_no_sensitive_payload(self._list_jobs)
        return list(self._list_jobs)

    def read_job_detail(self, platform_job_id: str) -> StandardJob:
        html = self._detail_html_by_job_id.get(platform_job_id)
        if html is None:
            raise ValueError("岗位详情不存在")
        error = classify_job_platform_fixture_error(platform=self.platform, stage="detail", html=html)
        if error is not None:
            raise _sanitize_adapter_error(error)
        job = _mark_missing_fields_low_confidence(parse_job_detail_fixture(html))
        _assert_no_sensitive_payload(job)
        return job

    def is_already_applied(self, platform_job_id: str) -> bool:
        html = self._state_html_by_job_id.get(platform_job_id)
        if html is None:
            return False
        error = classify_job_platform_fixture_error(platform=self.platform, stage="state", html=html)
        if error is not None and error.error_type is not PlatformAdapterErrorType.DUPLICATE_APPLICATION:
            raise _sanitize_adapter_error(error)
        return error is not None and error.error_type is PlatformAdapterErrorType.DUPLICATE_APPLICATION

    def submit_application(self, request: ConfirmationApplicationRequest) -> ApplicationSubmissionResult:
        _assert_no_sensitive_payload(request)
        result = ApplicationSubmissionResult(
            platform=self.platform,
            platform_job_id=request.job.platform_job_id,
            status="skipped",
            error=PlatformAdapterError(
                error_type=PlatformAdapterErrorType.BUTTON_UNAVAILABLE,
                platform=self.platform,
                stage="submit",
                message="拉勾只读适配器不执行投递",
            ),
        )
        _assert_no_sensitive_payload(result)
        return result


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


def parse_job_list_fixture(html: str) -> list[StandardJob]:
    parser = _JobFixtureParser()
    parser.feed(html)
    parser.close()
    return [_build_standard_job(fields) for fields in parser.job_cards]


def parse_job_detail_fixture(html: str) -> StandardJob:
    parser = _JobFixtureParser()
    parser.feed(html)
    parser.close()
    if not parser.job_detail:
        raise ValueError("岗位详情夹具缺少 data-job-detail")
    return _build_standard_job(parser.job_detail)


def classify_job_platform_fixture_error(*, platform: str, stage: str, html: str) -> PlatformAdapterError | None:
    parser = _JobFixtureParser()
    parser.feed(html)
    parser.close()
    error_type = {
        "login_expired": PlatformAdapterErrorType.LOGIN_EXPIRED,
        "captcha_required": PlatformAdapterErrorType.CAPTCHA_REQUIRED,
        "button_unavailable": PlatformAdapterErrorType.BUTTON_UNAVAILABLE,
        "already_applied": PlatformAdapterErrorType.DUPLICATE_APPLICATION,
        "rate_limited": PlatformAdapterErrorType.RATE_LIMITED,
        "page_structure_changed": PlatformAdapterErrorType.PAGE_STRUCTURE_CHANGED,
    }.get(parser.fixture_state)
    if error_type is None:
        return None
    return PlatformAdapterError(
        error_type=error_type,
        platform=platform,
        stage=stage,
        message="夹具状态触发平台适配器错误",
    )


class _JobFixtureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fixture_state: str | None = None
        self.job_cards: list[dict[str, str]] = []
        self.job_detail: dict[str, str] = {}
        self._current_fields: dict[str, str] | None = None
        self._current_field_name: str | None = None
        self._current_field_tag: str | None = None
        self._current_field_depth = 0
        self._current_field_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("data-fixture-state"):
            self.fixture_state = attributes["data-fixture-state"]
        if "data-job-card" in attributes:
            self._current_fields = {}
        if "data-job-detail" in attributes:
            self._current_fields = {}
            self.job_detail = self._current_fields
        field_name = attributes.get("data-field")
        if field_name and self._current_fields is not None:
            self._current_field_name = field_name
            self._current_field_tag = tag
            self._current_field_depth = 1
            self._current_field_parts = []
            if tag == "a" and field_name == "detail_url":
                self._current_fields[field_name] = attributes.get("href") or ""
            return
        if self._current_field_name is not None:
            self._current_field_depth += 1

    def handle_data(self, data: str) -> None:
        if self._current_field_name is not None:
            self._current_field_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._current_field_name is not None:
            if tag != self._current_field_tag or self._current_field_depth > 1:
                self._current_field_depth -= 1
                return
            value = " ".join(" ".join(self._current_field_parts).split())
            if value and self._current_field_name != "detail_url":
                self._current_fields[self._current_field_name] = value
            self._current_field_name = None
            self._current_field_tag = None
            self._current_field_depth = 0
            self._current_field_parts = []
        if tag == "article" and self._current_fields is not None:
            self.job_cards.append(self._current_fields)
            if self.job_detail is self._current_fields:
                self.job_detail = self._current_fields
            self._current_fields = None


def _build_standard_job(fields: dict[str, str]) -> StandardJob:
    standard_fields = {
        "platform",
        "platform_job_id",
        "title",
        "company_name",
        "location",
        "remote_policy",
        "salary_range",
        "level",
        "experience_requirement",
        "education_requirement",
        "industry",
        "company_size",
        "funding_stage",
        "tech_stack",
        "benefits",
        "published_at",
        "detail_url",
        "jd_text",
        "collected_at",
    }
    required_fields = {
        "platform",
        "platform_job_id",
        "title",
        "company_name",
        "location",
        "detail_url",
        "jd_text",
        "collected_at",
    }
    missing_fields = sorted(field_name for field_name in required_fields if not fields.get(field_name))
    if missing_fields:
        raise ValueError(f"岗位夹具缺少字段: {', '.join(missing_fields)}")
    field_confidence = {
        field_name: "fixture" if fields.get(field_name) else "missing" for field_name in standard_fields
    }
    return StandardJob(
        platform=fields["platform"],
        platform_job_id=fields["platform_job_id"],
        title=fields["title"],
        company_name=fields["company_name"],
        location=fields["location"],
        remote_policy=fields.get("remote_policy"),
        salary_range=fields.get("salary_range"),
        level=fields.get("level"),
        experience_requirement=fields.get("experience_requirement"),
        education_requirement=fields.get("education_requirement"),
        industry=fields.get("industry"),
        company_size=fields.get("company_size"),
        funding_stage=fields.get("funding_stage"),
        tech_stack=_split_fixture_list(fields.get("tech_stack")),
        benefits=_split_fixture_list(fields.get("benefits")),
        published_at=fields.get("published_at"),
        detail_url=fields["detail_url"],
        jd_text=fields["jd_text"],
        collected_at=fields["collected_at"],
        field_confidence=field_confidence,
    )


def _split_fixture_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _mark_missing_fields_low_confidence(job: StandardJob) -> StandardJob:
    field_confidence = {
        field_name: "low_confidence" if confidence == "missing" else confidence
        for field_name, confidence in job.field_confidence.items()
    }
    return replace(job, field_confidence=field_confidence)
