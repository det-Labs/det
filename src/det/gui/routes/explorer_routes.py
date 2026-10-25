"""Workspace explorer tree endpoints for the left navigation sidebar."""

from http.server import BaseHTTPRequestHandler
from typing import Any

from det.gui.base import BaseRouteHandler
from det.gui.routes.common import send_json
from det.workspace import Workspace


class ExplorerRouteHandler(BaseRouteHandler):
    """Generates hierarchical project, model, and catalog tree for the explorer bar."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def handle_get(self, handler: BaseHTTPRequestHandler, path: str) -> bool:
        """Process GET requests for workspace directory tree."""
        if path == "/api/explorer":
            tree = self._build_explorer_tree()
            send_json(handler, tree)
            return True
        return False

    def handle_post(
        self, handler: BaseHTTPRequestHandler, path: str, body: dict[str, Any]
    ) -> bool:
        """Handle POST requests for explorer routes."""
        return False

    def _build_explorer_tree(self) -> dict[str, Any]:
        """Compose projects and catalog connections into structured navigation nodes."""
        projects_data = []
        for proj_name in self._workspace.projects.discover_projects():
            models = self._workspace.projects.load_project_models(proj_name)
            folder = self._workspace.projects.get_project_folder(proj_name)
            models_list = [
                {"name": m.name, "materialized": m.config.materialized.value}
                for m in models
            ]
            projects_data.append({"name": proj_name, "folder": folder, "models": models_list})

        connections_data = [
            {"name": c.name, "type": c.type, "tier": c.tier.value, "folder": c.folder}
            for c in self._workspace.catalog.list_connections()
        ]

        return {
            "projects": projects_data,
            "connections": connections_data,
        }
