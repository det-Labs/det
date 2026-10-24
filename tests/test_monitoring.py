"""Unit tests for pluggable telemetry sinks, quarantine management, and monitoring routes."""

import json
from pathlib import Path
import urllib.request

from det.gui.server import GUIServer
from det.monitoring.base import PipelineRunRecord, QuarantineRecord, TestAuditRecord
from det.monitoring.database_sink import DatabaseTelemetrySink
from det.monitoring.duckdb_sink import DuckDBTelemetrySink
from det.monitoring.file_sink import FileTelemetrySink
from det.monitoring.manager import TelemetryManager
from det.workspace import Workspace


def test_duckdb_telemetry_sink(tmp_path: Path) -> None:
    """Verify DuckDB telemetry sink creates tables and persists runs."""
    sink = DuckDBTelemetrySink(tmp_path / "telemetry.duckdb")
    run = PipelineRunRecord(
        run_id="run_001", project="test_proj", status="SUCCESS",
        started_at="2026-10-24T18:00:00Z", completed_at="2026-10-24T18:00:02Z",
        duration_ms=2000.0, models_executed=5, rows_affected=1500,
        models_detail=[{"model_name": "stg_users", "status": "SUCCESS", "duration_ms": 12.0, "rows_affected": 1500, "error_message": None}],
    )
    sink.record_run(run)
    runs = sink.get_runs()
    assert len(runs) == 1
    assert runs[0].run_id == "run_001"
    assert runs[0].duration_ms == 2000.0
    assert len(runs[0].models_detail) == 1
    assert runs[0].models_detail[0]["model_name"] == "stg_users"


def test_file_telemetry_sink(tmp_path: Path) -> None:
    """Verify FileTelemetrySink appends records to JSONL files and purges."""
    sink = FileTelemetrySink(tmp_path / "telemetry")
    quar = QuarantineRecord(
        record_id="quar_001", run_id="run_001", project="test_proj",
        model_name="fct_orders", test_name="order_amount_positive",
        quarantined_at="2026-10-24T18:00:00Z", raw_payload={"order_id": 99, "amount": -10},
    )
    sink.record_quarantine_rows([quar])
    records = sink.get_quarantine_records()
    assert len(records) == 1
    assert records[0].record_id == "quar_001"

    sink.resolve_quarantine_record("quar_001", "Fixed manually")
    records = sink.get_quarantine_records()
    assert records[0].status == "RESOLVED"

    purged = sink.purge_quarantine_records(["quar_001"])
    assert purged == 1
    assert len(sink.get_quarantine_records()) == 0


def test_database_telemetry_sink(tmp_path: Path) -> None:
    """Verify DatabaseTelemetrySink persists into external database tables."""
    db_file = tmp_path / "external_audit.db"
    sink = DatabaseTelemetrySink(str(db_file), table_prefix="audit_")
    audit = TestAuditRecord(
        audit_id="audit_001", run_id="run_001", project="test_proj",
        model_name="dim_users", test_name="users_id_unique", test_type="unique",
        severity="ERROR", passed=True, failures_count=0, action_taken="NONE",
        details="Zero duplicate keys", executed_at="2026-10-24T18:00:00Z",
    )
    sink.record_test_audits([audit])
    audits = sink.get_test_audits()
    assert len(audits) == 1
    assert audits[0].audit_id == "audit_001"
    assert audits[0].passed is True


def test_telemetry_manager_sink_switching(tmp_path: Path) -> None:
    """Verify TelemetryManager can seamlessly switch sinks at runtime."""
    mgr = TelemetryManager(tmp_path, sink_type="duckdb")
    assert mgr.active_sink_type == "duckdb"

    # Switch to JSONL flat files
    mgr.switch_sink("file")
    assert mgr.active_sink_type == "file"
    mgr.log_run("proj_a", "SUCCESS", 120.0, 3, 500)
    runs = mgr.active_sink.get_runs()
    assert len(runs) == 1

    # Switch to external DB tables
    mgr.switch_sink("database", {"url": str(tmp_path / "custom_audit.db")})
    assert mgr.active_sink_type == "database"
    info = mgr.get_sink_info()
    assert info["active_sink"] == "database"


def _verify_monitoring_queries(port: int) -> str:
    """Verify runs and quarantine endpoints, returning first quarantine record id."""
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/monitoring/runs") as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["total"] >= 1
        assert data["runs"][0]["project"] == "default"
        assert len(data["runs"][0]["models_detail"]) == 1
        assert data["runs"][0]["models_detail"][0]["model_name"] == "m1"
        assert data["limit"] == 100
        assert data["max_limit"] == 5000

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/monitoring/quarantine") as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["total"] >= 1
        return data["records"][0]["record_id"]


def _verify_monitoring_actions(port: int, rec_id: str) -> None:
    """Verify quarantine resolution and sink switching endpoints."""
    resolve_body = json.dumps({"record_id": rec_id, "notes": "Verified"}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/monitoring/quarantine/resolve",
        data=resolve_body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as res:
        assert res.status == 200

    config_body = json.dumps({"sink": "file"}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/monitoring/config",
        data=config_body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as res:
        assert res.status == 200
        data = json.loads(res.read().decode("utf-8"))
        assert data["active_sink"] == "file"


def test_monitoring_api_routes(tmp_path: Path) -> None:
    """Verify /api/monitoring endpoints serve runs, quarantine, and allow sink switching."""
    from tests.test_gui_docs_routes import find_free_port, _setup_test_workspace
    ws = _setup_test_workspace(tmp_path)
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    try:
        ws.monitoring.log_run(
            "default", "SUCCESS", 45.0, 2, 100, models_detail=[
                {"model_name": "m1", "status": "SUCCESS", "started_at": "2026-10-24T18:00:00Z",
                 "duration_ms": 20.0, "rows_affected": 50, "error_message": None}
            ]
        )
        ws.monitoring.log_quarantine("default", "stg_users", "user_id_unique", {"user_id": 1, "name": "Bob"})
        rec_id = _verify_monitoring_queries(port)
        _verify_monitoring_actions(port, rec_id)
    finally:
        server.stop()
        ws.close()

