"""Database table telemetry sink supporting external databases via Catalog connections."""

import json
from pathlib import Path
from typing import Any
import sqlite3

from det.monitoring.base import (
    BaseTelemetrySink,
    PipelineRunRecord,
    QuarantineRecord,
    TestAuditRecord,
)


class DatabaseTelemetrySink(BaseTelemetrySink):
    """Persists pipeline telemetry and audit logs into external database tables."""

    def __init__(self, connection_url_or_path: str, table_prefix: str = "det_") -> None:
        self.target = connection_url_or_path
        self.prefix = table_prefix
        self.runs_table = f"{self.prefix}pipeline_runs"
        self.tests_table = f"{self.prefix}test_audits"
        self.quarantine_table = f"{self.prefix}quarantine_records"
        self.initialize()

    def _get_connection(self) -> sqlite3.Connection:
        """Acquire connection to backing external database (supports sqlite3 file/URI)."""
        db_path = self.target.replace("sqlite:///", "").replace("sqlite://", "")
        Path(db_path).resolve().parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(Path(db_path).resolve()))

    def initialize(self) -> None:
        """Create target audit tables in destination external database."""
        with self._get_connection() as con:
            cur = con.cursor()
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.runs_table} (
                    run_id TEXT PRIMARY KEY, project TEXT, status TEXT,
                    started_at TEXT, completed_at TEXT, duration_ms REAL,
                    models_executed INTEGER, rows_affected INTEGER, error_message TEXT,
                    models_detail TEXT DEFAULT '[]'
                );
            """)
            try:
                cur.execute(f"ALTER TABLE {self.runs_table} ADD COLUMN models_detail TEXT DEFAULT '[]'")
            except Exception:
                pass
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.tests_table} (
                    audit_id TEXT PRIMARY KEY, run_id TEXT, project TEXT,
                    model_name TEXT, test_name TEXT, test_type TEXT,
                    severity TEXT, passed INTEGER, failures_count INTEGER,
                    action_taken TEXT, details TEXT, executed_at TEXT
                );
            """)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.quarantine_table} (
                    record_id TEXT PRIMARY KEY, run_id TEXT, project TEXT,
                    model_name TEXT, test_name TEXT, quarantined_at TEXT,
                    raw_payload TEXT, status TEXT, resolution_notes TEXT
                );
            """)
            con.commit()

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

    _parse_json = _parse_json_list

    def record_run(self, run: PipelineRunRecord) -> None:
        """Persist a completed pipeline execution run record."""
        with self._get_connection() as con:
            cur = con.cursor()
            cur.execute(
                f"""
                INSERT OR REPLACE INTO {self.runs_table} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run.run_id, run.project, run.status, run.started_at, run.completed_at,
                    run.duration_ms, run.models_executed, run.rows_affected, run.error_message,
                    json.dumps(run.models_detail),
                ],
            )
            con.commit()

    def get_runs(
        self,
        project: str | None = None,
        limit: int = 20,
        days: int = 30,
        failed_only: bool = False,
    ) -> list[PipelineRunRecord]:
        """Retrieve recent pipeline execution runs."""
        safe_limit = max(1, min(limit, 5000))
        with self._get_connection() as con:
            cur = con.cursor()
            sql = f"SELECT run_id, project, status, started_at, completed_at, duration_ms, models_executed, rows_affected, error_message, models_detail FROM {self.runs_table}"
            filters = []
            params = []
            if project:
                filters.append("project = ?")
                params.append(project)
            if failed_only:
                filters.append("status = 'FAILED'")
            if filters:
                sql += " WHERE " + " AND ".join(filters)
            sql += " ORDER BY started_at DESC LIMIT ?"
            params.append(safe_limit)
            cur.execute(sql, params)
            rows = cur.fetchall()
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

    def record_quarantine_rows(self, rows: list[QuarantineRecord]) -> None:
        """Persist isolated rows violating data quality assertions."""
        if not rows:
            return
        with self._get_connection() as con:
            cur = con.cursor()
            for q in rows:
                cur.execute(
                    f"""
                    INSERT OR REPLACE INTO {self.quarantine_table} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        q.record_id, q.run_id, q.project, q.model_name, q.test_name,
                        q.quarantined_at, json.dumps(q.raw_payload), q.status, q.resolution_notes,
                    ],
                )
            con.commit()

    def get_quarantine_records(
        self,
        project: str | None = None,
        model: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[QuarantineRecord]:
        """Query quarantine records for review and remediation."""
        with self._get_connection() as con:
            cur = con.cursor()
            sql = f"SELECT record_id, run_id, project, model_name, test_name, quarantined_at, raw_payload, status, resolution_notes FROM {self.quarantine_table}"
            filters = []
            params = []
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
            cur.execute(sql, params)
            rows = cur.fetchall()
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
        """Permanently purge resolved or obsolete quarantine entries."""
        if not record_ids:
            return 0
        with self._get_connection() as con:
            cur = con.cursor()
            q_marks = ", ".join(["?"] * len(record_ids))
            cur.execute(f"DELETE FROM {self.quarantine_table} WHERE record_id IN ({q_marks})", record_ids)
            con.commit()
            return len(record_ids)

    def resolve_quarantine_record(self, record_id: str, notes: str | None = None) -> bool:
        """Mark a quarantine record as reviewed and resolved."""
        with self._get_connection() as con:
            cur = con.cursor()
            cur.execute(
                f"UPDATE {self.quarantine_table} SET status = 'RESOLVED', resolution_notes = ? WHERE record_id = ?",
                [notes or "Resolved", record_id],
            )
            con.commit()
            return cur.rowcount > 0

    def get_run(self, run_id: str) -> PipelineRunRecord | None:
        """Fetch single pipeline run by run_id."""
        with self._get_connection() as con:
            cur = con.cursor()
            cur.execute(
                f"SELECT run_id, project, status, started_at, completed_at, duration_ms, models_executed, rows_affected, error_message, models_detail FROM {self.runs_table} WHERE run_id = ?",
                [run_id],
            )
            r = cur.fetchone()
            if not r:
                return None
            return PipelineRunRecord(
                run_id=r[0], project=r[1], status=r[2], started_at=r[3], completed_at=r[4],
                duration_ms=float(r[5] or 0), models_executed=int(r[6] or 0), rows_affected=int(r[7] or 0),
                error_message=r[8],
                models_detail=self._parse_json_list(r[9] if len(r) > 9 else None),
            )

    def clean(self, days: int = 30, project: str | None = None) -> dict[str, int]:
        """Purge telemetry runs and test audits older than N days."""
        import datetime
        cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).isoformat()
        with self._get_connection() as con:
            cur = con.cursor()
            sql_runs = f"DELETE FROM {self.runs_table} WHERE started_at < ?"
            sql_audits = f"DELETE FROM {self.tests_table} WHERE executed_at < ?"
            p_runs: list[Any] = [cutoff]
            p_audits: list[Any] = [cutoff]
            if project:
                sql_runs += " AND project = ?"
                p_runs.append(project)
                sql_audits += " AND project = ?"
                p_audits.append(project)
            cur.execute(sql_runs, p_runs)
            p_r = cur.rowcount
            cur.execute(sql_audits, p_audits)
            p_a = cur.rowcount
            con.commit()
            return {"purged_runs": max(0, p_r), "purged_audits": max(0, p_a)}

    def record_test_audits(self, audits: list[TestAuditRecord]) -> None:
        """Persist batch of data quality test evaluation audits."""
        if not audits:
            return
        with self._get_connection() as con:
            cur = con.cursor()
            for a in audits:
                cur.execute(
                    f"""
                    INSERT OR REPLACE INTO {self.tests_table} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        a.audit_id, a.run_id, a.project, a.model_name, a.test_name,
                        a.test_type, a.severity, 1 if a.passed else 0, a.failures_count,
                        a.action_taken, a.details, a.executed_at,
                    ],
                )
            con.commit()

    def get_test_audits(
        self, run_id: str | None = None, project: str | None = None, limit: int = 100
    ) -> list[TestAuditRecord]:
        """Query test execution results filtered by run_id or project."""
        with self._get_connection() as con:
            cur = con.cursor()
            sql = f"SELECT audit_id, run_id, project, model_name, test_name, test_type, severity, passed, failures_count, action_taken, details, executed_at FROM {self.tests_table}"
            filters = []
            params = []
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
            cur.execute(sql, params)
            rows = cur.fetchall()
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
        """Persist isolated rows violating data quality assertions."""
        if not rows:
            return
        with self._get_connection() as con:
            cur = con.cursor()
            for q in rows:
                cur.execute(
                    f"""
                    INSERT OR REPLACE INTO {self.quarantine_table} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        q.record_id, q.run_id, q.project, q.model_name, q.test_name,
                        q.quarantined_at, json.dumps(q.raw_payload), q.status, q.resolution_notes,
                    ],
                )
            con.commit()

    def get_quarantine_records(
        self,
        project: str | None = None,
        model: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[QuarantineRecord]:
        """Query quarantine records for review and remediation."""
        with self._get_connection() as con:
            cur = con.cursor()
            sql = f"SELECT record_id, run_id, project, model_name, test_name, quarantined_at, raw_payload, status, resolution_notes FROM {self.quarantine_table}"
            filters = []
            params = []
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
            cur.execute(sql, params)
            rows = cur.fetchall()
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
        """Permanently purge resolved or obsolete quarantine entries."""
        if not record_ids:
            return 0
        with self._get_connection() as con:
            cur = con.cursor()
            q_marks = ", ".join(["?"] * len(record_ids))
            cur.execute(f"DELETE FROM {self.quarantine_table} WHERE record_id IN ({q_marks})", record_ids)
            con.commit()
            return len(record_ids)

    def resolve_quarantine_record(self, record_id: str, notes: str | None = None) -> bool:
        """Mark a quarantine record as reviewed and resolved."""
        with self._get_connection() as con:
            cur = con.cursor()
            cur.execute(
                f"UPDATE {self.quarantine_table} SET status = 'RESOLVED', resolution_notes = ? WHERE record_id = ?",
                [notes or "Resolved", record_id],
            )
            con.commit()
            return cur.rowcount > 0
