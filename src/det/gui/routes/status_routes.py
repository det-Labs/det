"""Status and workspace telemetry REST endpoints."""

from http.server import BaseHTTPRequestHandler
from typing import Any
import duckdb

from det.gui.base import BaseRouteHandler
from det.gui.routes.common import send_json
from det.workspace import Workspace


class StatusRouteHandler(BaseRouteHandler):
    """Handles /api/status and workspace diagnostic checks."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def handle_get(self, handler: BaseHTTPRequestHandler, path: str) -> bool:
        """Process GET requests for workspace status."""
        if path == "/api/status":
            status_data = self._build_status_payload()
            send_json(handler, status_data)
            return True
        return False

    def handle_post(
        self, handler: BaseHTTPRequestHandler, path: str, body: dict[str, Any]
    ) -> bool:
        """Handle POST requests for status routes."""
        return False

    def _build_status_payload(self) -> dict[str, Any]:
        """Collect platform and engine telemetry."""
        projects = self._workspace.projects.discover_projects()
        connections = self._workspace.catalog.list_connections()

        return {
            "status": "ready",
            "duckdb_version": duckdb.__version__,
            "workspace_path": str(self._workspace.root),
            "projects_count": len(projects),
            "connections_count": len(connections),
            "default_project": self._workspace.config.default_project,
        }
