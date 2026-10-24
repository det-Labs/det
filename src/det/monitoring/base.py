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
    """Violating data row routed to quarantine sink for human remediation."""

    record_id: str
    run_id: str
    project: str
    model_name: str
    test_name: str
    quarantined_at: str
    raw_payload: dict[str, Any]
    status: str = "QUARANTINED"
    resolution_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert quarantine record to JSON dictionary."""
        return asdict(self)


def generate_telemetry_id(prefix: str = "run") -> str:
    """Generate high-entropy unique identifier for audit telemetry."""
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}_{uuid.uuid4().hex[:6]}"


class BaseTelemetrySink(ABC):
    """Abstract protocol for swappable telemetry, audit logging, and quarantine sinks."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize backing storage schema and tables."""

    @abstractmethod
    def record_run(self, run: PipelineRunRecord) -> None:
        """Persist a completed pipeline execution run record."""

    @abstractmethod
    def get_runs(self, project: str | None = None, limit: int = 50) -> list[PipelineRunRecord]:
        """Retrieve recent pipeline execution runs."""

    @abstractmethod
    def record_test_audits(self, audits: list[TestAuditRecord]) -> None:
        """Persist batch of data quality test evaluation audits."""

    @abstractmethod
    def get_test_audits(
        self, run_id: str | None = None, project: str | None = None, limit: int = 100
    ) -> list[TestAuditRecord]:
        """Query test execution results filtered by run_id or project."""

    @abstractmethod
    def record_quarantine_rows(self, rows: list[QuarantineRecord]) -> None:
        """Persist isolated rows violating data quality assertions."""

    @abstractmethod
    def get_quarantine_records(
        self,
        project: str | None = None,
        model: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[QuarantineRecord]:
        """Query quarantine records for review and remediation."""

    @abstractmethod
    def purge_quarantine_records(self, record_ids: list[str]) -> int:
        """Permanently purge resolved or obsolete quarantine entries."""

    @abstractmethod
    def resolve_quarantine_record(self, record_id: str, notes: str | None = None) -> bool:
        """Mark a quarantine record as reviewed and resolved."""
