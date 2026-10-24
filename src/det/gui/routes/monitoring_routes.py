"""HTTP route handlers for Telemetry, Audit Logs, and Quarantine Monitoring."""

from http.server import BaseHTTPRequestHandler
from typing import Any
import urllib.parse

from det.gui.base import BaseRouteHandler
from det.gui.routes.common import send_error_json, send_json
from det.monitoring.manager import TelemetryManager
from det.workspace import Workspace


class MonitoringRouteHandler(BaseRouteHandler):
    """Provides monitoring telemetry, quarantine inspection, and sink management APIs."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace
        self._telemetry: TelemetryManager = getattr(
            workspace, "monitoring", TelemetryManager(workspace.root)
        )

    def handle_get(
        self, handler: BaseHTTPRequestHandler, path: str, query: dict[str, list[str]] | None = None
    ) -> bool:
        """Handle GET requests for monitoring telemetry, audits, and quarantine."""
        raw_path = path.split("?")[0]
        parsed_url = urllib.parse.urlparse(handler.path)
        active_query = query or urllib.parse.parse_qs(parsed_url.query)

        routes = {
            "/api/monitoring/runs": self._handle_get_runs,
            "/api/monitoring/quarantine": self._handle_get_quarantine,
            "/api/monitoring/audits": self._handle_get_audits,
            "/api/monitoring/config": self._handle_get_config,
        }
        return routes[raw_path](handler, active_query) if raw_path in routes else False

    def _handle_get_runs(self, handler: BaseHTTPRequestHandler, query: dict[str, list[str]]) -> bool:
        """Serve historical execution runs."""
        proj = query.get("project", [None])[0]
        limit = max(1, min(int(query.get("limit", [100])[0]), 5000))
        runs = [r.to_dict() for r in self._telemetry.active_sink.get_runs(project=proj, limit=limit)]
        send_json(handler, {"runs": runs, "total": len(runs), "sink": self._telemetry.active_sink_type, "limit": limit, "max_limit": 5000})
        return True

    def _handle_get_quarantine(self, handler: BaseHTTPRequestHandler, query: dict[str, list[str]]) -> bool:
        """Serve quarantined records."""
        proj, model = query.get("project", [None])[0], query.get("model", [None])[0]
        status = query.get("status", [None])[0]
        limit = max(1, min(int(query.get("limit", [100])[0]), 5000))
        records = [
            q.to_dict()
            for q in self._telemetry.active_sink.get_quarantine_records(
                project=proj, model=model, status=status, limit=limit
            )
        ]
        send_json(handler, {"records": records, "total": len(records), "sink": self._telemetry.active_sink_type, "limit": limit, "max_limit": 5000})
        return True

    def _handle_get_audits(self, handler: BaseHTTPRequestHandler, query: dict[str, list[str]]) -> bool:
        """Serve test execution audit logs."""
        run_id, proj = query.get("run_id", [None])[0], query.get("project", [None])[0]
        limit = max(1, min(int(query.get("limit", [100])[0]), 5000))
        audits = [a.to_dict() for a in self._telemetry.active_sink.get_test_audits(run_id=run_id, project=proj, limit=limit)]
        send_json(handler, {"audits": audits, "total": len(audits), "limit": limit, "max_limit": 5000})
        return True

    def _handle_get_config(self, handler: BaseHTTPRequestHandler, _query: dict[str, list[str]]) -> bool:
        """Serve current monitoring sink configuration."""
        send_json(handler, self._telemetry.get_sink_info())
        return True

    def handle_post(
        self, handler: BaseHTTPRequestHandler, path: str, body: dict[str, Any]
    ) -> bool:
        """Handle POST requests for sink switching, quarantine remediation, and purging."""
        if path == "/api/monitoring/config":
            sink_type = body.get("sink", "duckdb")
            cfg = body.get("config", {})
            try:
                self._telemetry.switch_sink(sink_type, cfg)
                send_json(handler, {"status": "ok", "active_sink": self._telemetry.active_sink_type, "info": self._telemetry.get_sink_info()})
            except Exception as e:
                send_error_json(handler, f"Failed to switch sink: {e}")
            return True

        if path == "/api/monitoring/quarantine/resolve":
            rec_id = body.get("record_id", "")
            notes = body.get("notes", "")
            if not rec_id:
                send_error_json(handler, "record_id is required")
                return True
            ok = self._telemetry.active_sink.resolve_quarantine_record(rec_id, notes=notes)
            send_json(handler, {"status": "ok" if ok else "not_found", "record_id": rec_id})
            return True

        if path == "/api/monitoring/quarantine/purge":
            rec_ids = body.get("record_ids", [])
            purged = self._telemetry.active_sink.purge_quarantine_records(rec_ids)
            send_json(handler, {"status": "ok", "purged_count": purged})
            return True

        return False
