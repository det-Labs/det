"""Telemetry coordinator managing active and pluggable audit logging sinks."""

import datetime
from pathlib import Path
from typing import Any

from det.monitoring.base import (
    BaseTelemetrySink,
    PipelineRunRecord,
    QuarantineRecord,
    TestAuditRecord,
    generate_telemetry_id,
)
from det.monitoring.database_sink import DatabaseTelemetrySink
from det.monitoring.duckdb_sink import DuckDBTelemetrySink
from det.monitoring.file_sink import FileTelemetrySink


class TelemetryManager:
    """Extensible telemetry registry and dispatcher supporting swappable sinks."""

    def __init__(
        self,
        workspace_root: Path | str,
        sink_type: str = "duckdb",
        sink_config: dict[str, Any] | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self._sink_factories: dict[str, Any] = {
            "duckdb": self._create_duckdb_sink,
            "file": self._create_file_sink,
            "database": self._create_database_sink,
        }
        self.active_sink_type = sink_type
        self.sink_config = sink_config or {}
        self.active_sink: BaseTelemetrySink = self._create_sink(sink_type, self.sink_config)

    def register_sink_factory(self, name: str, factory: Any) -> None:
        """Register a custom telemetry sink provider from an extension or plugin."""
        self._sink_factories[name] = factory

    def switch_sink(self, sink_type: str, config: dict[str, Any] | None = None) -> None:
        """Switch active telemetry persistence sink."""
        if sink_type not in self._sink_factories:
            raise ValueError(f"Unknown telemetry sink: '{sink_type}'. Available: {list(self._sink_factories.keys())}")
        self.sink_config = config or {}
        self.active_sink_type = sink_type
        self.active_sink = self._create_sink(sink_type, self.sink_config)

    def _create_sink(self, sink_type: str, config: dict[str, Any]) -> BaseTelemetrySink:
        """Instantiate telemetry sink implementation."""
        factory = self._sink_factories[sink_type]
        return factory(config)

    def _create_duckdb_sink(self, config: dict[str, Any]) -> DuckDBTelemetrySink:
        """Create standard DuckDB file telemetry sink."""
        path = config.get("path") or (self.workspace_root / ".det" / "telemetry.duckdb")
        return DuckDBTelemetrySink(Path(path).resolve())

    def _create_file_sink(self, config: dict[str, Any]) -> FileTelemetrySink:
        """Create JSONL flat-file telemetry sink."""
        path = config.get("directory") or (self.workspace_root / ".det" / "telemetry")
        return FileTelemetrySink(Path(path).resolve())

    def _create_database_sink(self, config: dict[str, Any]) -> DatabaseTelemetrySink:
        """Create external database table telemetry sink."""
        url = config.get("url") or str((self.workspace_root / ".det" / "external_audit.db").resolve())
        prefix = config.get("table_prefix", "det_")
        return DatabaseTelemetrySink(url, table_prefix=prefix)

    def get_sink_info(self) -> dict[str, Any]:
        """Return information about the currently active monitoring sink with absolute path."""
        path_str = ""
        if hasattr(self.active_sink, "db_path"):
            path_str = str(self.active_sink.db_path.resolve())
        elif hasattr(self.active_sink, "directory"):
            path_str = str(self.active_sink.directory.resolve())
        elif hasattr(self.active_sink, "target"):
            path_str = str(self.active_sink.target)

        total_runs = len(self.active_sink.get_runs(limit=5000))
        total_audits = len(self.active_sink.get_test_audits(limit=5000))

        return {
            "active_sink": self.active_sink_type,
            "available_sinks": list(self._sink_factories.keys()),
            "storage_path": path_str,
            "total_runs": total_runs,
            "total_audits": total_audits,
            "config": self.sink_config,
        }

    def log_run(
        self,
        project: str,
        status: str,
        duration_ms: float,
        models_executed: int,
        rows_affected: int,
        error_message: str | None = None,
        run_id: str | None = None,
        models_detail: list[dict[str, Any]] | None = None,
    ) -> PipelineRunRecord:
        """Log pipeline execution batch telemetry."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rec = PipelineRunRecord(
            run_id=run_id or generate_telemetry_id("run"),
            project=project,
            status=status,
            started_at=now,
            completed_at=now,
            duration_ms=duration_ms,
            models_executed=models_executed,
            rows_affected=rows_affected,
            error_message=error_message,
            models_detail=models_detail or [],
        )
        self.active_sink.record_run(rec)
        return rec

    def get_runs(
        self,
        project: str | None = None,
        limit: int = 20,
        days: int = 30,
        failed_only: bool = False,
    ) -> list[PipelineRunRecord]:
        """Retrieve recent pipeline execution runs with inclusive priority."""
        return self.active_sink.get_runs(
            project=project, limit=limit, days=days, failed_only=failed_only
        )

    def get_run(self, run_id: str) -> PipelineRunRecord | None:
        """Fetch single pipeline run by run_id."""
        return self.active_sink.get_run(run_id)

    def get_test_audits(
        self, run_id: str | None = None, project: str | None = None, limit: int = 100
    ) -> list[TestAuditRecord]:
        """Query test execution results filtered by run_id or project."""
        return self.active_sink.get_test_audits(run_id=run_id, project=project, limit=limit)

    def clean(self, days: int = 30, project: str | None = None) -> dict[str, int]:
        """Purge telemetry runs and test audits older than N days."""
        return self.active_sink.clean(days=days, project=project)

    def log_quarantine(
        self,
        project: str,
        model_name: str,
        test_name: str,
        raw_payload: dict[str, Any],
        run_id: str | None = None,
    ) -> QuarantineRecord:
        """Record an isolated violating row to the active quarantine sink."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rec = QuarantineRecord(
            record_id=generate_telemetry_id("quar"),
            run_id=run_id or generate_telemetry_id("run"),
            project=project,
            model_name=model_name,
            test_name=test_name,
            quarantined_at=now,
            raw_payload=raw_payload,
            status="QUARANTINED",
        )
        self.active_sink.record_quarantine_rows([rec])
        return rec
