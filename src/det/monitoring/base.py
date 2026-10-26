"""Base data classes and protocol definition for extensible monitoring and telemetry sinks."""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
import datetime
from typing import Any
import uuid


@dataclass
class PipelineRunRecord:
    """Historical telemetry for a pipeline execution batch."""

    run_id: str
    project: str
    status: str
    started_at: str
    completed_at: str
    duration_ms: float
    models_executed: int
    rows_affected: int
    error_message: str | None = None
    models_detail: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert run record to JSON dictionary."""
        return asdict(self)


@dataclass
class TestAuditRecord:
    """Audit log entry for an executed data quality assertion."""

    __test__ = False
    audit_id: str
    run_id: str
    project: str
    model_name: str
    test_name: str
    test_type: str
    severity: str
    passed: bool
    failures_count: int
    action_taken: str
    details: str
    executed_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert test audit record to JSON dictionary."""
        return asdict(self)


@dataclass
class QuarantineRecord:
    """Legacy quarantine record definition (deprecated)."""

    record_id: str = ""
    run_id: str = ""
    project: str = ""
    model_name: str = ""
    test_name: str = ""
    quarantined_at: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)
    status: str = "DEPRECATED"
    resolution_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert record to dictionary."""
        return asdict(self)


def generate_telemetry_id(prefix: str = "run") -> str:
    """Generate high-entropy unique identifier for audit telemetry."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}_{uuid.uuid4().hex[:6]}"


class BaseTelemetrySink(ABC):
    """Abstract protocol for swappable telemetry and audit logging sinks."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize backing storage schema and tables."""

    @abstractmethod
    def record_run(self, run: PipelineRunRecord) -> None:
        """Persist a completed pipeline execution run record."""

    @abstractmethod
    def get_runs(
        self,
        project: str | None = None,
        limit: int = 20,
        days: int = 30,
        failed_only: bool = False,
    ) -> list[PipelineRunRecord]:
        """Retrieve recent pipeline execution runs with inclusive priority."""

    @abstractmethod
    def get_run(self, run_id: str) -> PipelineRunRecord | None:
        """Fetch single pipeline run by run_id."""

    @abstractmethod
    def clean(self, days: int = 30, project: str | None = None) -> dict[str, int]:
        """Purge telemetry runs and test audits older than N days."""

    @abstractmethod
    def record_test_audits(self, audits: list[TestAuditRecord]) -> None:
        """Persist batch of data quality test evaluation audits."""

    @abstractmethod
    def get_test_audits(
        self, run_id: str | None = None, project: str | None = None, limit: int = 100
    ) -> list[TestAuditRecord]:
        """Query test execution results filtered by run_id or project."""

    def record_quarantine_rows(self, rows: list[Any]) -> None:
        """Deprecated: quarantine rows are no longer persisted."""
        pass

    def get_quarantine_records(self, **kwargs: Any) -> list[Any]:
        """Deprecated: quarantine records are no longer used."""
        return []

    def purge_quarantine_records(self, record_ids: list[str]) -> int:
        """Deprecated: quarantine records are no longer used."""
        return len(record_ids)

    def resolve_quarantine_record(self, record_id: str, notes: str | None = None) -> bool:
        """Deprecated: quarantine records are no longer used."""
        return True
