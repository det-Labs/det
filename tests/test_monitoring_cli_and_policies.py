"""Tests for Monitoring CLI commands and Data Quality Policies (error, warn, drop)."""

from pathlib import Path
import datetime
from unittest.mock import patch
import pytest

from det.cli import main
from det.models.definition import ModelConfig, ModelDefinition
from det.testing.base import TestSeverity, TestType
from det.testing.definitions import TestDefinition
from det.testing.evaluator import TestEvaluator
from det.workspace import Workspace


def test_drop_policy_filters_rows_in_duckdb(tmp_path: Path):
    """Verify that 'drop' test policy strips failing rows from the table in DuckDB."""
    ws = Workspace.init(tmp_path)
    con = ws.engine.session

    # Create table with 2 clean rows and 1 invalid row (null age)
    con.execute("CREATE OR REPLACE TABLE users AS SELECT 1 AS id, 25 AS age UNION ALL SELECT 2, NULL UNION ALL SELECT 3, 30")
    assert con.execute("SELECT COUNT(*) FROM users").fetchall()[0][0] == 3

    # Define test with DROP severity
    t_drop = TestDefinition(
        name="users_age_not_null",
        model_name="users",
        test_type=TestType.NOT_NULL,
        column_name="age",
        severity=TestSeverity.DROP,
    )

    evaluator = TestEvaluator()
    res = evaluator.evaluate_test(con, t_drop)

    assert res.passed is False
    assert res.failing_rows_count == 1
    assert res.severity == TestSeverity.DROP

    # Table in DuckDB must now have exactly 2 clean rows (the NULL row was dropped!)
    remaining = con.execute("SELECT id, age FROM users ORDER BY id").fetchall()
    assert len(remaining) == 2
    assert remaining == [(1, 25), (3, 30)]

    ws.close()


def test_warn_policy_preserves_rows(tmp_path: Path):
    """Verify that 'warn' test policy preserves rows and logs failure count."""
    ws = Workspace.init(tmp_path)
    con = ws.engine.session

    con.execute("CREATE OR REPLACE TABLE orders AS SELECT 1 AS id, -10 AS amount UNION ALL SELECT 2, 50")
    assert con.execute("SELECT COUNT(*) FROM orders").fetchall()[0][0] == 2

    t_warn = TestDefinition(
        name="orders_amount_positive",
        model_name="orders",
        test_type=TestType.EXPRESSION,
        parameters={"expression": "amount > 0"},
        severity=TestSeverity.WARN,
    )

    evaluator = TestEvaluator()
    res = evaluator.evaluate_test(con, t_warn)

    assert res.passed is False
    assert res.failing_rows_count == 1
    assert res.severity == TestSeverity.WARN

    # Rows must NOT be dropped
    assert con.execute("SELECT COUNT(*) FROM orders").fetchall()[0][0] == 2

    ws.close()


def test_monitoring_cli_runs_and_run_detail(tmp_path: Path, monkeypatch, capsys):
    """Test det monitor runs and det monitor run <run_id>."""
    monkeypatch.chdir(tmp_path)
    assert main(["init", str(tmp_path)]) == 0

    ws = Workspace.open(tmp_path)
    # Log 2 runs
    r1 = ws.monitoring.log_run(
        project="default", status="SUCCESS", duration_ms=45.2, models_executed=2, rows_affected=150,
        models_detail=[
            {"model_name": "m1", "status": "SUCCESS", "duration_ms": 20.0, "rows_affected": 100},
            {"model_name": "m2", "status": "SUCCESS", "duration_ms": 25.2, "rows_affected": 50},
        ],
    )
    r2 = ws.monitoring.log_run(
        project="sales", status="FAILED", duration_ms=120.0, models_executed=1, rows_affected=0,
        error_message="Syntax error at model stg_sales",
        models_detail=[
            {"model_name": "stg_sales", "status": "FAILED", "duration_ms": 120.0, "rows_affected": 0, "error_message": "Syntax error"},
        ],
    )
    ws.close()

    # 1. det monitor runs
    ret = main(["monitor", "runs"])
    assert ret == 0
    out = capsys.readouterr().out
    assert r1.run_id in out
    assert r2.run_id in out
    assert "SUCCESS" in out
    assert "FAILED" in out

    # 2. det monitor runs with filter
    ret_filt = main(["monitor", "runs", "--filter", "sales"])
    assert ret_filt == 0
    out_filt = capsys.readouterr().out
    assert r2.run_id in out_filt
    assert r1.run_id not in out_filt

    # 3. det monitor runs --failed
    ret_fail = main(["monitor", "runs", "--failed"])
    assert ret_fail == 0
    out_fail = capsys.readouterr().out
    assert r2.run_id in out_fail
    assert r1.run_id not in out_fail

    # 4. det monitor run <run_id>
    ret_detail = main(["monitor", "run", r1.run_id])
    assert ret_detail == 0
    out_detail = capsys.readouterr().out
    assert "RUN DETAILS" in out_detail
    assert "m1" in out_detail
    assert "m2" in out_detail


def test_monitoring_inclusive_priority(tmp_path: Path):
    """Verify that recent runs has inclusive priority even if runs are older than 30 days."""
    ws = Workspace.init(tmp_path)

    # Insert a run with timestamp 45 days ago
    old_ts = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=45)).isoformat()
    with ws.monitoring.active_sink._get_connection() as con:
        con.execute(
            "INSERT INTO det_pipeline_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ["old_run_01", "monthly_report", "SUCCESS", old_ts, old_ts, 1500.0, 5, 20000, None, "[]"],
        )

    # Query with default limit=20, days=30: inclusive priority MUST return the old run
    runs = ws.monitor_runs(limit=20, days=30)
    assert len(runs) >= 1
    assert runs[0].run_id == "old_run_01"
    assert runs[0].project == "monthly_report"

    ws.close()


def test_monitoring_cli_audits_status_and_clean(tmp_path: Path, monkeypatch, capsys):
    """Test det monitor audits, status, and clean."""
    monkeypatch.chdir(tmp_path)
    assert main(["init", str(tmp_path)]) == 0

    ws = Workspace.open(tmp_path)
    # Record test audits
    from det.monitoring.base import TestAuditRecord, generate_telemetry_id
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ws.monitoring.active_sink.record_test_audits([
        TestAuditRecord(
            audit_id=generate_telemetry_id("audit"), run_id="run_100", project="default",
            model_name="users", test_name="users_id_unique", test_type="unique",
            severity="ERROR", passed=True, failures_count=0, action_taken="PASSED",
            details="PASSED", executed_at=now,
        ),
        TestAuditRecord(
            audit_id=generate_telemetry_id("audit"), run_id="run_100", project="default",
            model_name="users", test_name="users_age_not_null", test_type="not_null",
            severity="DROP", passed=False, failures_count=3, action_taken="DROPPED",
            details="Dropped 3 rows", executed_at=now,
        ),
    ])
    ws.close()

    # 1. det monitor audits
    ret_aud = main(["monitor", "audits"])
    assert ret_aud == 0
    out_aud = capsys.readouterr().out
    assert "users_id_unique" in out_aud
    assert "users_age_not_null" in out_aud
    assert "DROPPED" in out_aud

    # 2. det monitor audits --failed
    ret_aud_f = main(["monitor", "audits", "--failed"])
    assert ret_aud_f == 0
    out_aud_f = capsys.readouterr().out
    assert "users_age_not_null" in out_aud_f
    assert "users_id_unique" not in out_aud_f

    # 3. det monitor status
    ret_stat = main(["monitor", "status"])
    assert ret_stat == 0
    out_stat = capsys.readouterr().out
    assert "DET TELEMETRY & MONITORING STATUS" in out_stat
    assert "duckdb" in out_stat
    assert str(tmp_path.resolve()) in out_stat or ".det" in out_stat

    # 4. det monitor clean --yes
    ret_clean = main(["monitor", "clean", "--days", "0", "--yes"])
    assert ret_clean == 0
    out_clean = capsys.readouterr().out
    assert "[OK] Purged" in out_clean

