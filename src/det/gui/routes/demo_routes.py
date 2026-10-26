"""HTTP route handlers for Demo Workspace onboarding and tour state."""

from http.server import BaseHTTPRequestHandler
from typing import Any

from det.gui.routes.common import send_error_json, send_json
from det.workspace import Workspace


class DemoRouteHandler:
    """Manages demo dataset generation, sample pipeline creation, and tour telemetry."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def handle_get(
        self, handler: BaseHTTPRequestHandler, path: str, query: dict[str, list[str]] | None = None
    ) -> bool:
        """Route GET requests for demo availability and status."""
        raw_path = path.split("?")[0]
        if raw_path == "/api/demo/status":
            has_demo = (
                (self._workspace.root / "pipelines" / "sample_pipelines" / "retail_medallion").exists()
                or (self._workspace.root / "pipelines" / "retail_medallion").exists()
                or (self._workspace.root / "projects" / "sample_pipelines" / "retail_medallion").exists()
                or (self._workspace.root / "projects" / "retail_medallion").exists()
            )
            send_json(handler, {"status": "ok", "has_demo": has_demo, "workspace": str(self._workspace.root)})
            return True
        return False

    def handle_post(
        self, handler: BaseHTTPRequestHandler, path: str, body: dict[str, Any]
    ) -> bool:
        """Route POST requests for triggering demo workspace generation."""
        raw_path = path.split("?")[0]
        if raw_path == "/api/demo/setup":
            use_remote = bool(body.get("remote", False))
            try:
                result = self._workspace.setup_demo(use_remote=use_remote)
                send_json(handler, {
                    "status": "ok",
                    "message": "Demo workspace successfully configured with 4 sample pipelines and datasets.",
                    "details": result,
                })
            except Exception as exc:
                send_error_json(handler, f"Failed to setup demo workspace: {exc}")
            return True
        return False

