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

    def __init__(self, workspace_root: Path | str, sink_type: str = "duckdb", sink_config: dict[str, Any] | None = None) -> None:
        self.workspace_root = Path(workspace_root)
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
        """Switch active telemetry persistence sink (e.g. to external DB table or files)."""
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
        return DuckDBTelemetrySink(path)

    def _create_file_sink(self, config: dict[str, Any]) -> FileTelemetrySink:
        """Create JSONL flat-file telemetry sink."""
        path = config.get("directory") or (self.workspace_root / ".det" / "telemetry")
        return FileTelemetrySink(path)

    def _create_database_sink(self, config: dict[str, Any]) -> DatabaseTelemetrySink:
        """Create external database table telemetry sink."""
        url = config.get("url") or str(self.workspace_root / ".det" / "external_audit.db")
        prefix = config.get("table_prefix", "det_")
        return DatabaseTelemetrySink(url, table_prefix=prefix)

    def get_sink_info(self) -> dict[str, Any]:
        """Return information about the currently active monitoring sink."""
        return {
            "active_sink": self.active_sink_type,
            "available_sinks": list(self._sink_factories.keys()),
            "config": self.sink_config,
        }

    def log_run(
        self, project: str, status: str, duration_ms: float, models_executed: int,
        rows_affected: int, error_message: str | None = None, run_id: str | None = None,
        models_detail: list[dict[str, Any]] | None = None,
    ) -> PipelineRunRecord:
        """Log pipeline execution batch telemetry."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rec = PipelineRunRecord(
            run_id=run_id or generate_telemetry_id("run"),
            project=project, status=status, started_at=now, completed_at=now,
            duration_ms=duration_ms, models_executed=models_executed,
            rows_affected=rows_affected, error_message=error_message,
            models_detail=models_detail or [],
        )
        self.active_sink.record_run(rec)
        return rec

    def log_quarantine(
        self, project: str, model_name: str, test_name: str, raw_payload: dict[str, Any],
        run_id: str | None = None,
    ) -> QuarantineRecord:
        """Record an isolated violating row to the active quarantine sink."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rec = QuarantineRecord(
            record_id=generate_telemetry_id("quar"),
            run_id=run_id or generate_telemetry_id("run"),
            project=project, model_name=model_name, test_name=test_name,
            quarantined_at=now, raw_payload=raw_payload, status="QUARANTINED",
        )
        self.active_sink.record_quarantine_rows([rec])
        return rec

