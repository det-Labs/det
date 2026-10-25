"""Comprehensive tests for Telemetry Sinks (DuckDB, SQLite Database, File/JSONL) and TelemetryManager."""

import json
from pathlib import Path
import pytest

from det.monitoring.base import (
    PipelineRunRecord,
    QuarantineRecord,
    TestAuditRecord,
    generate_telemetry_id,
)
from det.monitoring.database_sink import DatabaseTelemetrySink
from det.monitoring.duckdb_sink import DuckDBTelemetrySink
from det.monitoring.file_sink import FileTelemetrySink
from det.monitoring.manager import TelemetryManager


def _sample_run() -> PipelineRunRecord:
    return PipelineRunRecord(
        run_id=generate_telemetry_id(),
        project="analytics",
        status="SUCCESS",
        started_at="2026-10-25T12:00:00Z",
        completed_at="2026-10-25T12:00:05Z",
        duration_ms=5000.0,
        models_executed=5,
        rows_affected=1500,
        error_message=None,
        models_detail=[{"name": "dim_users", "status": "SUCCESS", "duration_ms": 120.0}],
    )


def _sample_audit(run_id: str) -> TestAuditRecord:
    return TestAuditRecord(
        audit_id=generate_telemetry_id(),
        run_id=run_id,
        project="analytics",
        model_name="fct_orders",
        test_name="assert_positive_amount",
        test_type="expression",
        severity="error",
        passed=False,
        failures_count=3,
        action_taken="quarantine",
        details="Negative order amount detected",
        executed_at="2026-10-25T12:00:03Z",
    )


def _sample_quarantine(run_id: str) -> QuarantineRecord:
    return QuarantineRecord(
        record_id=generate_telemetry_id(),
        run_id=run_id,
        project="analytics",
        model_name="fct_orders",
        test_name="assert_positive_amount",
        quarantined_at="2026-10-25T12:00:04Z",
        raw_payload={"order_id": 999, "amount": -45.0},
        status="QUARANTINED",
        resolution_notes="",
    )


# ---------------------------------------------------------------------------
# DatabaseTelemetrySink (SQLite-backed) Tests
# ---------------------------------------------------------------------------

def test_database_sink_crud(tmp_path: Path) -> None:
    """Verify DatabaseTelemetrySink records, queries, updates, and purges runs, audits, and quarantine rows."""
    db_file = tmp_path / "telemetry_test.db"
    sink = DatabaseTelemetrySink(f"sqlite:///{db_file}")

    # 1. Record and query runs
    run1 = _sample_run()
    run2 = _sample_run()
    run2.project = "marketing"
    sink.record_run(run1)
    sink.record_run(run2)

    all_runs = sink.get_runs()
    assert len(all_runs) == 2
    analytics_runs = sink.get_runs(project="analytics")
    assert len(analytics_runs) == 1
    assert analytics_runs[0].run_id == run1.run_id
    assert len(analytics_runs[0].models_detail) == 1

    # 2. Record and query test audits
    audit = _sample_audit(run1.run_id)
    sink.record_test_audits([audit])
    sink.record_test_audits([])  # Test empty list guard

    audits = sink.get_test_audits(run_id=run1.run_id)
    assert len(audits) == 1
    assert audits[0].test_name == "assert_positive_amount"
    assert audits[0].passed is False

    audits_proj = sink.get_test_audits(project="analytics")
    assert len(audits_proj) == 1

    # 3. Record, query, resolve, and purge quarantine records
    q_rec = _sample_quarantine(run1.run_id)
    sink.record_quarantine_rows([q_rec])
    sink.record_quarantine_rows([])  # Test empty list guard

    q_list = sink.get_quarantine_records(project="analytics", model="fct_orders", status="QUARANTINED")
    assert len(q_list) == 1
    assert q_list[0].raw_payload["amount"] == -45.0

    # Resolve record
    resolved = sink.resolve_quarantine_record(q_rec.record_id, notes="Verified chargeback")
    assert resolved is True

    resolved_list = sink.get_quarantine_records(status="RESOLVED")
    assert len(resolved_list) == 1
    assert resolved_list[0].resolution_notes == "Verified chargeback"

    # Purge record
    purged_count = sink.purge_quarantine_records([q_rec.record_id])
    assert purged_count == 1
    assert len(sink.get_quarantine_records()) == 0
    assert sink.purge_quarantine_records([]) == 0


# ---------------------------------------------------------------------------
# DuckDBTelemetrySink Tests
# ---------------------------------------------------------------------------

def test_duckdb_sink_crud(tmp_path: Path) -> None:
    """Verify DuckDBTelemetrySink records, queries, filters, resolves, and purges."""
    duck_file = tmp_path / "telemetry_test.duckdb"
    sink = DuckDBTelemetrySink(duck_file)

    run = _sample_run()
    sink.record_run(run)

    runs = sink.get_runs(project="analytics")
    assert len(runs) == 1
    assert runs[0].run_id == run.run_id

    audit = _sample_audit(run.run_id)
    sink.record_test_audits([audit])
    audits = sink.get_test_audits(project="analytics")
    assert len(audits) == 1
    assert audits[0].failures_count == 3

    q_rec = _sample_quarantine(run.run_id)
    sink.record_quarantine_rows([q_rec])
    records = sink.get_quarantine_records(model="fct_orders")
    assert len(records) == 1

    assert sink.resolve_quarantine_record(q_rec.record_id, notes="Fixed upstream bug") is True
    assert sink.purge_quarantine_records([q_rec.record_id]) == 1
    assert len(sink.get_quarantine_records()) == 0
    assert sink.purge_quarantine_records([]) == 0


# ---------------------------------------------------------------------------
# FileTelemetrySink (JSONL) Tests
# ---------------------------------------------------------------------------

def test_file_sink_crud(tmp_path: Path) -> None:
    """Verify FileTelemetrySink persists and queries JSONL log files safely."""
    sink_dir = tmp_path / "telemetry_logs"
    sink = FileTelemetrySink(sink_dir)

    run = _sample_run()
    sink.record_run(run)
    runs = sink.get_runs(project="analytics")
    assert len(runs) == 1
    assert runs[0].duration_ms == 5000.0

    audit = _sample_audit(run.run_id)
    sink.record_test_audits([audit])
    audits = sink.get_test_audits(run_id=run.run_id)
    assert len(audits) == 1

    q_rec = _sample_quarantine(run.run_id)
    sink.record_quarantine_rows([q_rec])
    q_recs = sink.get_quarantine_records(project="analytics")
    assert len(q_recs) == 1

    assert sink.resolve_quarantine_record(q_rec.record_id, notes="Approved") is True
    assert sink.purge_quarantine_records([q_rec.record_id]) == 1
    assert len(sink.get_quarantine_records()) == 0


# ---------------------------------------------------------------------------
# TelemetryManager Tests
# ---------------------------------------------------------------------------

def test_telemetry_manager_switching_and_factories(tmp_path: Path) -> None:
    """Verify TelemetryManager sink switching, factory registration, and dispatch."""
    manager = TelemetryManager(tmp_path, sink_type="duckdb")
    assert isinstance(manager.active_sink, DuckDBTelemetrySink)

    # Switch to file sink
    manager.switch_sink("file")
    assert isinstance(manager.active_sink, FileTelemetrySink)

    # Switch to database sink
    db_path = tmp_path / "custom.db"
    manager.switch_sink("database", config={"connection_url": f"sqlite:///{db_path}"})
    assert isinstance(manager.active_sink, DatabaseTelemetrySink)

    # Unknown sink type raises ValueError
    with pytest.raises(ValueError, match="Unknown telemetry sink"):
        manager.switch_sink("nonexistent_sink")

    # Custom factory registration
    mock_called = False
    def mock_factory(cfg):
        nonlocal mock_called
        mock_called = True
        return FileTelemetrySink(tmp_path / "mock")

    manager.register_sink_factory("mock_sink", mock_factory)
    manager.switch_sink("mock_sink")
    assert mock_called is True

