"""det.monitoring - Execution telemetry, run tracking, and workspace health.

Pipeline execution logs are stored per pipeline GUID under logs/pipelines/<pipeline_guid>.json
so that run histories are preserved across pipeline renames.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utcnow_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


class SourceReadMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    connector_type: str = ""
    started_at: str = Field(default_factory=_utcnow_iso)
    completed_at: str | None = None
    rows_read: int = 0
    duration_ms: float = 0.0


class DestinationWriteMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination_name: str
    target_path: str
    format: str
    started_at: str = Field(default_factory=_utcnow_iso)
    completed_at: str | None = None
    rows_written: int = 0
    duration_ms: float = 0.0


class StepRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    step_name: str
    sql: str
    status: str = "SUCCESS"  # SUCCESS, FAILED, SKIPPED
    started_at: str = Field(default_factory=_utcnow_iso)
    completed_at: str | None = None
    rows_processed: int = 0
    duration_ms: float = 0.0
    destinations: list[DestinationWriteMetric] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_id: str
    pipeline_id: str
    pipeline_name_at_run: str
    folder_at_run: str
    catalog: str
    status: str = "RUNNING"  # RUNNING, SUCCESS, FAILED
    started_at: str = Field(default_factory=_utcnow_iso)
    completed_at: str | None = None
    total_duration_seconds: float = 0.0
    sources: list[SourceReadMetric] = Field(default_factory=list)
    steps: list[StepRunRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    log_entries: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineLogFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pipeline_id: str
    latest_name: str
    latest_folder: str
    created_at: str = Field(default_factory=_utcnow_iso)
    updated_at: str = Field(default_factory=_utcnow_iso)
    runs: list[RunRecord] = Field(default_factory=list)


class MonitoringStore:
    """Headless monitoring store persisting execution telemetry per pipeline GUID."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.pipelines_log_dir = self.workspace / "logs" / "pipelines"
        self._lock = threading.RLock()
        self.pipelines_log_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, pipeline_id: str, folder: str | None = None) -> Path:
        """Locate existing log file or determine path matching pipelines/<folder> structure."""
        # Search if log file already exists under any folder
        for existing in self.pipelines_log_dir.glob(f"**/{pipeline_id}.json"):
            if existing.is_file():
                # If folder changed, move log file to mirror pipeline's new folder
                if folder and existing.parent.name != folder:
                    new_folder_dir = self.pipelines_log_dir / folder
                    new_folder_dir.mkdir(parents=True, exist_ok=True)
                    new_path = new_folder_dir / f"{pipeline_id}.json"
                    existing.rename(new_path)
                    return new_path
                return existing

        target_folder = folder or "default"
        folder_dir = self.pipelines_log_dir / target_folder
        folder_dir.mkdir(parents=True, exist_ok=True)
        return folder_dir / f"{pipeline_id}.json"

    def record_run(self, run: RunRecord) -> dict[str, Any]:
        """Append or update a run inside the pipeline's GUID log file matching its folder."""
        with self._lock:
            path = self._file_path(run.pipeline_id, folder=run.folder_at_run)
            path.parent.mkdir(parents=True, exist_ok=True)

            if path.is_file():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    log_file = PipelineLogFile.model_validate(data)
                except Exception:
                    log_file = PipelineLogFile(
                        pipeline_id=run.pipeline_id,
                        latest_name=run.pipeline_name_at_run,
                        latest_folder=run.folder_at_run,
                    )
            else:
                log_file = PipelineLogFile(
                    pipeline_id=run.pipeline_id,
                    latest_name=run.pipeline_name_at_run,
                    latest_folder=run.folder_at_run,
                )

            log_file.latest_name = run.pipeline_name_at_run
            log_file.latest_folder = run.folder_at_run
            log_file.updated_at = _utcnow_iso()

            # Find existing run or append
            existing_idx = next(
                (i for i, r in enumerate(log_file.runs) if r.run_id == run.run_id),
                None,
            )
            if existing_idx is not None:
                log_file.runs[existing_idx] = run
            else:
                log_file.runs.append(run)

            serialized = json.dumps(log_file.model_dump(mode="json"), indent=2)

            temporary_name: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    dir=self.pipelines_log_dir,
                    prefix=f".{path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as stream:
                    temporary_name = stream.name
                    stream.write(serialized)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_name, path)
            finally:
                if temporary_name and os.path.exists(temporary_name):
                    os.unlink(temporary_name)

            return run.model_dump(mode="json")

    def get_pipeline_log(self, identifier: str) -> dict[str, Any]:
        """Retrieve all execution runs for a given pipeline GUID, folder/name, or name."""
        with self._lock:
            # 1. Search if log file matches identifier as GUID
            path = self._file_path(identifier)
            if path.is_file():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    for r in data.get("runs", []):
                        r["log_entries"] = synthesize_log_entries(r)
                    return data
                except Exception:
                    pass

            # 2. Search all logs for matching name or folder/name
            clean_ident = identifier.strip().replace("\\", "/")
            for log_file in self.pipelines_log_dir.glob("**/*.json"):
                try:
                    data = json.loads(log_file.read_text(encoding="utf-8"))
                    p_id = data.get("pipeline_id")
                    p_name = data.get("latest_name")
                    p_folder = data.get("latest_folder")
                    p_key = f"{p_folder}/{p_name}" if p_folder else p_name
                    if clean_ident in (p_id, p_name, p_key):
                        for r in data.get("runs", []):
                            r["log_entries"] = synthesize_log_entries(r)
                        return data
                except (json.JSONDecodeError, OSError):
                    continue

        return {"pipeline_id": identifier, "latest_name": identifier, "latest_folder": "", "runs": []}

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Retrieve a specific run by searching pipeline log files."""
        with self._lock:
            for log_file in self.pipelines_log_dir.glob("**/*.json"):
                try:
                    data = json.loads(log_file.read_text(encoding="utf-8"))
                    for run in data.get("runs", []):
                        if run.get("run_id") == run_id:
                            run["log_entries"] = synthesize_log_entries(run)
                            return run
                except (json.JSONDecodeError, OSError):
                    continue
        raise FileNotFoundError(f"Run record not found: {run_id}")

    def list_runs(
        self,
        *,
        pipeline_id: str | None = None,
        pipeline_name: str | None = None,
        folder: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List most recent runs across pipelines or for a specific pipeline with filters."""
        with self._lock:
            if not self.pipelines_log_dir.exists():
                return []

            all_runs: list[dict[str, Any]] = []

            # Target specific pipeline if pipeline_id given
            target_files = (
                [self._file_path(pipeline_id)]
                if pipeline_id and self._file_path(pipeline_id).is_file()
                else list(self.pipelines_log_dir.glob("**/*.json"))
            )

            for log_path in target_files:
                try:
                    data = json.loads(log_path.read_text(encoding="utf-8"))
                    for run in data.get("runs", []):
                        # Filter by pipeline identifier (supports GUID, folder/name, or name)
                        if pipeline_id and pipeline_id not in (
                            run.get("pipeline_id"),
                            run.get("pipeline_name_at_run"),
                            f"{run.get('folder_at_run')}/{run.get('pipeline_name_at_run')}",
                        ):
                            continue
                        if pipeline_name and run.get("pipeline_name_at_run") != pipeline_name:
                            continue
                        if folder and run.get("folder_at_run") != folder:
                            continue
                        if status and status != "ALL" and run.get("status") != status:
                            continue
                        if date_from and (run.get("started_at") or "") < date_from:
                            continue
                        if date_to and (run.get("started_at") or "") > date_to:
                            continue

                        all_runs.append(run)
                except (json.JSONDecodeError, OSError):
                    continue

            # Sort descending by start time
            all_runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)
            result = all_runs[:limit]
            for r in result:
                r["log_entries"] = synthesize_log_entries(r)
            return result

    def workspace_summary(self) -> dict[str, Any]:
        """Return high-level workspace health and run statistics."""
        runs = self.list_runs(limit=100)
        total_runs = len(runs)
        successes = sum(1 for r in runs if r.get("status") == "SUCCESS")
        failures = sum(1 for r in runs if r.get("status") == "FAILED")
        recent_failure = next((r for r in runs if r.get("status") == "FAILED"), None)

        return {
            "total_recorded_runs": total_runs,
            "success_rate": round(successes / total_runs * 100, 1) if total_runs else 100.0,
            "successes": successes,
            "failures": failures,
            "last_failure": recent_failure,
            "health_status": "DEGRADED" if failures > 0 and (failures / max(total_runs, 1)) > 0.2 else "HEALTHY",
        }


def synthesize_log_entries(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Synthesize structured, chronological log entries from a run record."""
    if run.get("log_entries"):
        return run["log_entries"]

    entries: list[dict[str, Any]] = []
    run_id = (run.get("run_id") or "")[:8]
    p_name = run.get("pipeline_name_at_run", "pipeline")
    p_folder = run.get("folder_at_run", "")
    started = run.get("started_at") or _utcnow_iso()
    completed = run.get("completed_at") or started

    entries.append({
        "timestamp": started,
        "level": "INFO",
        "stage": "INIT",
        "message": f"Execution initiated for pipeline '{p_folder}/{p_name}' (Run ID: {run_id}, Catalog: {run.get('catalog', 'default.yaml')})",
    })

    for s in run.get("sources", []):
        entries.append({
            "timestamp": s.get("started_at") or started,
            "level": "SCAN",
            "stage": "SOURCE",
            "message": f"Registered source '{s.get('source_name')}' ({s.get('connector_type', 'connector')}) — scan latency {s.get('duration_ms', 0):.1f}ms ({s.get('rows_read', 0):,} rows)",
        })

    for step in run.get("steps", []):
        st_name = step.get("step_name", "step")
        st_dur = step.get("duration_ms", 0)
        st_rows = step.get("rows_processed", 0)
        entries.append({
            "timestamp": step.get("started_at") or started,
            "level": "STEP",
            "stage": "TRANSFORM",
            "message": f"Step '{st_name}': SQL execution completed in {st_dur:.1f}ms — produced {st_rows:,} rows",
        })
        for dest in step.get("destinations", []):
            d_name = dest.get("destination_name", "dest")
            d_rows = dest.get("rows_written", 0)
            d_dur = dest.get("duration_ms", 0)
            d_fmt = dest.get("format", "file")
            entries.append({
                "timestamp": dest.get("started_at") or step.get("completed_at") or started,
                "level": "WRITE",
                "stage": "DESTINATION",
                "message": f"Step '{st_name}' -> Exported {d_rows:,} rows to destination '{d_name}' ({d_fmt}) in {d_dur:.1f}ms",
            })
        if step.get("error"):
            entries.append({
                "timestamp": step.get("completed_at") or started,
                "level": "ERROR",
                "stage": "STEP",
                "message": f"Step '{st_name}' failure: {step['error']}",
            })

    for w in run.get("warnings", []):
        entries.append({
            "timestamp": completed,
            "level": "WARN",
            "stage": "SYSTEM",
            "message": f"Warning: {w}",
        })

    if run.get("error"):
        entries.append({
            "timestamp": completed,
            "level": "ERROR",
            "stage": "FAILURE",
            "message": f"Pipeline execution failed: {run['error']}",
        })
    else:
        dur_s = run.get("total_duration_seconds", 0)
        entries.append({
            "timestamp": completed,
            "level": "SUCCESS",
            "stage": "COMPLETED",
            "message": f"Pipeline completed successfully with status {run.get('status', 'SUCCESS')} in {dur_s * 1000:.1f}ms",
        })

    return entries
