"""File-based JSONL telemetry and audit log sink."""

import json
from pathlib import Path
from typing import Any

from det.monitoring.base import (
    BaseTelemetrySink,
    PipelineRunRecord,
    QuarantineRecord,
    TestAuditRecord,
)


class FileTelemetrySink(BaseTelemetrySink):
    """Persists pipeline runs and test audits in JSONL flat files."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.runs_file = self.directory / "runs.jsonl"
        self.tests_file = self.directory / "test_audits.jsonl"
        self.quarantine_file = self.directory / "quarantine.jsonl"
        self.initialize()

    def initialize(self) -> None:
        """Touch telemetry files if they do not exist."""
        for f in (self.runs_file, self.tests_file, self.quarantine_file):
            if not f.exists():
                f.touch()

    def record_run(self, run: PipelineRunRecord) -> None:
        """Append pipeline execution run to runs.jsonl."""
        with self.runs_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(run.to_dict()) + "\n")

    def get_runs(
        self,
        project: str | None = None,
        limit: int = 20,
        days: int = 30,
        failed_only: bool = False,
    ) -> list[PipelineRunRecord]:
        """Read recent runs from runs.jsonl in reverse chronological order."""
        if not self.runs_file.exists():
            return []
        safe_limit = max(1, min(limit, 5000))
        runs = []
        for line in reversed(self.runs_file.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            data = json.loads(line)
            if failed_only and data.get("status") != "FAILED":
                continue
            if not project or data.get("project") == project:
                data.setdefault("models_detail", [])
                runs.append(PipelineRunRecord(**data))
            if len(runs) >= safe_limit:
                break
        return runs

    def get_run(self, run_id: str) -> PipelineRunRecord | None:
        """Fetch single pipeline run by run_id."""
        for r in self.get_runs(limit=5000):
            if r.run_id == run_id:
                return r
        return None

    def clean(self, days: int = 30, project: str | None = None) -> dict[str, int]:
        """Purge telemetry runs and test audits older than N days."""
        import datetime
        cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).isoformat()
        purged_runs = 0
        if self.runs_file.exists():
            remaining = []
            for line in self.runs_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                d = json.loads(line)
                if d.get("started_at", "") < cutoff and (not project or d.get("project") == project):
                    purged_runs += 1
                else:
                    remaining.append(line)
            self.runs_file.write_text("\n".join(remaining) + ("\n" if remaining else ""), encoding="utf-8")

        purged_audits = 0
        if self.tests_file.exists():
            remaining_audits = []
            for line in self.tests_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                d = json.loads(line)
                if d.get("executed_at", "") < cutoff and (not project or d.get("project") == project):
                    purged_audits += 1
                else:
                    remaining_audits.append(line)
            self.tests_file.write_text("\n".join(remaining_audits) + ("\n" if remaining_audits else ""), encoding="utf-8")

        return {"purged_runs": purged_runs, "purged_audits": purged_audits}

    def record_test_audits(self, audits: list[TestAuditRecord]) -> None:
        """Append test audit logs to test_audits.jsonl."""
        if not audits:
            return
        with self.tests_file.open("a", encoding="utf-8") as f:
            for a in audits:
                f.write(json.dumps(a.to_dict()) + "\n")

    def get_test_audits(
        self, run_id: str | None = None, project: str | None = None, limit: int = 100
    ) -> list[TestAuditRecord]:
        """Read and filter test audit logs from test_audits.jsonl."""
        if not self.tests_file.exists():
            return []
        audits = []
        for line in reversed(self.tests_file.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            data = json.loads(line)
            if run_id and data.get("run_id") != run_id:
                continue
            if project and data.get("project") != project:
                continue
            audits.append(TestAuditRecord(**data))
            if len(audits) >= limit:
                break
        return audits

    def record_quarantine_rows(self, rows: list[QuarantineRecord]) -> None:
        """Append quarantined data records to quarantine.jsonl."""
        if not rows:
            return
        with self.quarantine_file.open("a", encoding="utf-8") as f:
            for q in rows:
                f.write(json.dumps(q.to_dict()) + "\n")

    def get_quarantine_records(
        self,
        project: str | None = None,
        model: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[QuarantineRecord]:
        """Filter and retrieve quarantine entries."""
        if not self.quarantine_file.exists():
            return []
        records = []
        for line in reversed(self.quarantine_file.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            data = json.loads(line)
            if project and data.get("project") != project:
                continue
            if model and data.get("model_name") != model:
                continue
            if status and data.get("status") != status:
                continue
            records.append(QuarantineRecord(**data))
            if len(records) >= limit:
                break
        return records

    def purge_quarantine_records(self, record_ids: list[str]) -> int:
        """Purge quarantine records by recreating file without matching IDs."""
        if not self.quarantine_file.exists() or not record_ids:
            return 0
        target_ids = set(record_ids)
        kept_lines = []
        purged = 0
        for line in self.quarantine_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("record_id") in target_ids:
                purged += 1
            else:
                kept_lines.append(line)
        self.quarantine_file.write_text("\n".join(kept_lines) + ("\n" if kept_lines else ""), encoding="utf-8")
        return purged

    def resolve_quarantine_record(self, record_id: str, notes: str | None = None) -> bool:
        """Update status of a quarantine record in-place."""
        if not self.quarantine_file.exists():
            return False
        found = False
        new_lines = []
        for line in self.quarantine_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("record_id") == record_id:
                data["status"] = "RESOLVED"
                data["resolution_notes"] = notes or "Resolved"
                found = True
            new_lines.append(json.dumps(data))
        self.quarantine_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        return found
