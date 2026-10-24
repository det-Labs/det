"""DuckDB-backed persistent telemetry and quarantine storage sink."""

import json
from pathlib import Path
from typing import Any
import duckdb

from det.monitoring.base import (
    BaseTelemetrySink,
    PipelineRunRecord,
    QuarantineRecord,
    TestAuditRecord,
)


class DuckDBTelemetrySink(BaseTelemetrySink):
    """Stores pipeline runs, quality test audits, and quarantined rows in DuckDB."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _get_connection(self) -> duckdb.DuckDBPyConnection:
        """Create fresh connection to DuckDB telemetry database."""
        return duckdb.connect(str(self.db_path))

    def initialize(self) -> None:
        """Create telemetry tables and indexes if they do not exist."""
        with self._get_connection() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS det_pipeline_runs (
                    run_id VARCHAR PRIMARY KEY, project VARCHAR, status VARCHAR,
                    started_at VARCHAR, completed_at VARCHAR, duration_ms DOUBLE,
                    models_executed INTEGER, rows_affected BIGINT, error_message VARCHAR,
                    models_detail VARCHAR DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS det_test_audits (
                    audit_id VARCHAR PRIMARY KEY, run_id VARCHAR, project VARCHAR,
                    model_name VARCHAR, test_name VARCHAR, test_type VARCHAR,
                    severity VARCHAR, passed BOOLEAN, failures_count INTEGER,
                    action_taken VARCHAR, details VARCHAR, executed_at VARCHAR
                );
                CREATE TABLE IF NOT EXISTS det_quarantine_records (
                    record_id VARCHAR PRIMARY KEY, run_id VARCHAR, project VARCHAR,
                    model_name VARCHAR, test_name VARCHAR, quarantined_at VARCHAR,
                    raw_payload VARCHAR, status VARCHAR, resolution_notes VARCHAR
                );
            """)
            try:
                con.execute("ALTER TABLE det_pipeline_runs ADD COLUMN models_detail VARCHAR DEFAULT '[]'")
            except Exception:
                pass

    def record_run(self, run: PipelineRunRecord) -> None:
        """Insert a pipeline run record into det_pipeline_runs."""
        with self._get_connection() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO det_pipeline_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run.run_id, run.project, run.status, run.started_at, run.completed_at,
                    run.duration_ms, run.models_executed, run.rows_affected, run.error_message,
                    json.dumps(run.models_detail),
                ],
            )

    @staticmethod
    def _parse_json_list(val: Any) -> list[dict[str, Any]]:
        """Safely deserialize stored JSON list."""
        if not val:
            return []
        if isinstance(val, list):
            return val
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    def get_runs(self, project: str | None = None, limit: int = 100) -> list[PipelineRunRecord]:
        """Query recent pipeline runs with optional project filter."""
        safe_limit = max(1, min(limit, 5000))
        with self._get_connection() as con:
            sql = "SELECT run_id, project, status, started_at, completed_at, duration_ms, models_executed, rows_affected, error_message, models_detail FROM det_pipeline_runs"
            params: list[Any] = []
            if project:
                sql += " WHERE project = ?"
                params.append(project)
            sql += " ORDER BY started_at DESC LIMIT ?"
            params.append(safe_limit)
            rows = con.execute(sql, params).fetchall()
            return [
                PipelineRunRecord(
                    run_id=r[0], project=r[1], status=r[2], started_at=r[3],
                    completed_at=r[4], duration_ms=float(r[5] or 0),
                    models_executed=int(r[6] or 0), rows_affected=int(r[7] or 0),
                    error_message=r[8],
                    models_detail=self._parse_json_list(r[9] if len(r) > 9 else None),
                )
                for r in rows
            ]

    def record_test_audits(self, audits: list[TestAuditRecord]) -> None:
        """Insert batch of test evaluation audit entries."""
        if not audits:
            return
        with self._get_connection() as con:
            for a in audits:
                con.execute(
                    """
                    INSERT OR REPLACE INTO det_test_audits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        a.audit_id, a.run_id, a.project, a.model_name, a.test_name,
                        a.test_type, a.severity, a.passed, a.failures_count,
                        a.action_taken, a.details, a.executed_at,
                    ],
                )

    def get_test_audits(
        self, run_id: str | None = None, project: str | None = None, limit: int = 100
    ) -> list[TestAuditRecord]:
        """Fetch test audit logs filtered by run_id or project."""
        with self._get_connection() as con:
            sql = "SELECT audit_id, run_id, project, model_name, test_name, test_type, severity, passed, failures_count, action_taken, details, executed_at FROM det_test_audits"
            filters, params = [], []
            if run_id:
                filters.append("run_id = ?")
                params.append(run_id)
            if project:
                filters.append("project = ?")
                params.append(project)
            if filters:
                sql += " WHERE " + " AND ".join(filters)
            sql += " ORDER BY executed_at DESC LIMIT ?"
            params.append(limit)
            rows = con.execute(sql, params).fetchall()
            return [
                TestAuditRecord(
                    audit_id=r[0], run_id=r[1], project=r[2], model_name=r[3],
                    test_name=r[4], test_type=r[5], severity=r[6], passed=bool(r[7]),
                    failures_count=int(r[8] or 0), action_taken=r[9], details=r[10],
                    executed_at=r[11],
                )
                for r in rows
            ]

    def record_quarantine_rows(self, rows: list[QuarantineRecord]) -> None:
        """Insert quarantined rows into det_quarantine_records."""
        if not rows:
            return
        with self._get_connection() as con:
            for q in rows:
                con.execute(
                    """
                    INSERT OR REPLACE INTO det_quarantine_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        q.record_id, q.run_id, q.project, q.model_name, q.test_name,
                        q.quarantined_at, json.dumps(q.raw_payload), q.status, q.resolution_notes,
                    ],
                )

    def get_quarantine_records(
        self,
        project: str | None = None,
        model: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[QuarantineRecord]:
        """Retrieve quarantined rows matching filters."""
        with self._get_connection() as con:
            sql = "SELECT record_id, run_id, project, model_name, test_name, quarantined_at, raw_payload, status, resolution_notes FROM det_quarantine_records"
            filters, params = [], []
            if project:
                filters.append("project = ?")
                params.append(project)
            if model:
                filters.append("model_name = ?")
                params.append(model)
            if status:
                filters.append("status = ?")
                params.append(status)
            if filters:
                sql += " WHERE " + " AND ".join(filters)
            sql += " ORDER BY quarantined_at DESC LIMIT ?"
            params.append(limit)
            rows = con.execute(sql, params).fetchall()
            return [
                QuarantineRecord(
                    record_id=r[0], run_id=r[1], project=r[2], model_name=r[3],
                    test_name=r[4], quarantined_at=r[5],
                    raw_payload=json.loads(r[6]) if isinstance(r[6], str) else (r[6] or {}),
                    status=r[7], resolution_notes=r[8],
                )
                for r in rows
            ]

    def purge_quarantine_records(self, record_ids: list[str]) -> int:
        """Delete quarantine entries by record ID."""
        if not record_ids:
            return 0
        with self._get_connection() as con:
            q_marks = ", ".join(["?"] * len(record_ids))
            con.execute(f"DELETE FROM det_quarantine_records WHERE record_id IN ({q_marks})", record_ids)
            return len(record_ids)

    def resolve_quarantine_record(self, record_id: str, notes: str | None = None) -> bool:
        """Mark quarantine record as resolved with remediation comments."""
        with self._get_connection() as con:
            con.execute(
                """
                UPDATE det_quarantine_records SET status = 'RESOLVED', resolution_notes = ? WHERE record_id = ?
                """,
                [notes or "Manually reviewed and resolved", record_id],
            )
            return True

