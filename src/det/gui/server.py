"""Embedded HTTP server hosting the modular Web IDE and REST endpoints."""

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import threading
from typing import Any

from det.extensions.registry import global_registry
from det.gui.base import BaseGUIServer
from det.gui.routes.catalog_routes import CatalogRouteHandler
from det.gui.routes.common import read_json_body, send_error_json, send_json
from det.gui.routes.demo_routes import DemoRouteHandler
from det.gui.routes.docs_routes import DocsRouteHandler
from det.gui.routes.explorer_routes import ExplorerRouteHandler
from det.gui.routes.monitoring_routes import MonitoringRouteHandler
from det.gui.routes.pipeline_routes import PipelineRouteHandler
from det.gui.routes.status_routes import StatusRouteHandler
from det.gui.routes.ui_routes import UIRouteHandler
from det.workspace import Workspace

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


class ThreadedGUIServer(ThreadingHTTPServer):
    """Multi-threaded HTTP server with fast daemon workers and port reuse."""

    daemon_threads = True
    allow_reuse_address = True
    _workspace_lock: threading.Lock = threading.Lock()


class GUIRequestHandler(SimpleHTTPRequestHandler):
    """Dispatches API routes and serves static frontend assets."""

    def __init__(
        self,
        *args: Any,
        catalog_handler: CatalogRouteHandler,
        status_handler: StatusRouteHandler,
        ui_handler: UIRouteHandler,
        explorer_handler: ExplorerRouteHandler,
        pipeline_handler: PipelineRouteHandler,
        docs_handler: DocsRouteHandler,
        monitoring_handler: MonitoringRouteHandler,
        demo_handler: DemoRouteHandler,
        **kwargs: Any,
    ) -> None:
        self.catalog_h = catalog_handler
        self.status_h = status_handler
        self.ui_h = ui_handler
        self.explorer_h = explorer_handler
        self.pipeline_h = pipeline_handler
        self.docs_h = docs_handler
        self.monitoring_h = monitoring_handler
        self.demo_h = demo_handler
        if not STATIC_DIR.exists():
            STATIC_DIR.mkdir(parents=True, exist_ok=True)
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _get_workspace_lock(self) -> threading.Lock:
        """Resolve server workspace serialization lock."""
        return getattr(self.server, "_workspace_lock", None) or threading.Lock()

    def _build_init_payload(self) -> dict[str, Any]:
        """Compose all bootstrap data into a single serialized payload for fast startup."""
        manifest = {
            "modules": [m.to_dict() for m in self.ui_h._modules],
            "themes": [t.to_dict() for t in self.ui_h._themes],
        }
        try:
            explorer = self.explorer_h._build_explorer_tree()
        except Exception:
            explorer = {"projects": [], "connections": []}

        try:
            status = self.status_h._build_status_payload()
        except Exception:
            status = {"status": "ready"}

        try:
            connectors = global_registry.list_schemas()
        except Exception:
            connectors = []

        try:
            connections = [
                {"name": c.name, "folder": c.folder, **c.to_dict()}
                for c in self.catalog_h._workspace.catalog.list_connections()
            ]
        except Exception:
            connections = []

        try:
            pipelines = self.pipeline_h._list_pipelines()
        except Exception:
            pipelines = []

        return {
            "workspace_root": str(self.catalog_h._workspace.root),
            "modules": manifest["modules"],
            "themes": manifest["themes"],
            "explorer": explorer,
            "status": status,
            "connectors": connectors,
            "connections": connections,
            "pipelines": pipelines,
        }

    def do_GET(self) -> None:
        """Handle incoming GET requests."""
        raw_path = self.path.split("?")[0]
        lock = self._get_workspace_lock()

        try:
            if raw_path == "/api/init":
                with lock:
                    init_data = self._build_init_payload()
                    send_json(self, init_data)
                    return

            if raw_path.startswith("/api/"):
                with lock:
                    if self.demo_h.handle_get(self, raw_path):
                        return
                    if self.catalog_h.handle_get(self, raw_path):
                        return
                    if self.status_h.handle_get(self, raw_path):
                        return
                    if self.ui_h.handle_get(self, raw_path):
                        return
                    if self.explorer_h.handle_get(self, raw_path):
                        return
                    if self.pipeline_h.handle_get(self, raw_path):
                        return
                    if self.docs_h.handle_get(self, raw_path):
                        return
                    if self.monitoring_h.handle_get(self, raw_path):
                        return
                send_error_json(self, f"API endpoint not found: {raw_path}", status_code=404)
                return

            if not (STATIC_DIR / "index.html").exists() and raw_path in ("/", "/index.html"):
                msg = (
                    "<!DOCTYPE html><html><head><title>det Web IDE Error</title></head>"
                    "<body style='font-family:sans-serif;padding:40px;background:#0f172a;color:#f8fafc;'>"
                    "<h2>det Web IDE Frontend Assets Not Found</h2>"
                    f"<p>Static assets expected at <code>{STATIC_DIR}</code> were not found.</p>"
                    "<p>Please reinstall det-core or update to the latest release: <code>pip install --upgrade det-core</code></p>"
                    "</body></html>"
                )
                self.send_response(500)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(msg.encode("utf-8"))))
                self.end_headers()
                self.wfile.write(msg.encode("utf-8"))
                return

            super().do_GET()
        except Exception as exc:
            logger.exception("Error handling GET %s: %s", raw_path, exc)
            if raw_path.startswith("/api/"):
                send_error_json(self, str(exc), status_code=500)

    def do_POST(self) -> None:
        """Handle incoming POST requests."""
        raw_path = self.path.split("?")[0]
        lock = self._get_workspace_lock()

        try:
            body = read_json_body(self)
            with lock:
                if self.demo_h.handle_post(self, raw_path, body):
                    return
                if self.catalog_h.handle_post(self, raw_path, body):
                    return
                if self.status_h.handle_post(self, raw_path, body):
                    return
                if self.ui_h.handle_post(self, raw_path, body):
                    return
                if self.explorer_h.handle_post(self, raw_path, body):
                    return
                if self.pipeline_h.handle_post(self, raw_path, body):
                    return
                if self.docs_h.handle_post(self, raw_path, body):
                    return
                if self.monitoring_h.handle_post(self, raw_path, body):
                    return
            send_error_json(self, f"Endpoint not found: {raw_path}", status_code=404)
        except Exception as exc:
            logger.exception("Error handling POST %s: %s", raw_path, exc)
            send_error_json(self, str(exc), status_code=500)

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def end_headers(self) -> None:
        """Send cache-control headers to prevent stale browser caching of assets."""
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


class GUIServer(BaseGUIServer):
    """Coordinates lifecycle of embedded HTTP server for the Web IDE."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.catalog_handler = CatalogRouteHandler(workspace)
        self.status_handler = StatusRouteHandler(workspace)
        self.ui_handler = UIRouteHandler()
        self.explorer_handler = ExplorerRouteHandler(workspace)
        self.pipeline_handler = PipelineRouteHandler(workspace)
        self.docs_handler = DocsRouteHandler(workspace)
        self.monitoring_handler = MonitoringRouteHandler(workspace)
        self.demo_handler = DemoRouteHandler(workspace)
        self._lock = threading.Lock()
        self._server: ThreadedGUIServer | None = None
        self._thread: threading.Thread | None = None

    def start(self, host: str = "127.0.0.1", port: int = 8080, blocking: bool = True) -> None:
        """Start HTTP server."""
        handler_factory = functools.partial(
            GUIRequestHandler,
            catalog_handler=self.catalog_handler,
            status_handler=self.status_handler,
            ui_handler=self.ui_handler,
            explorer_handler=self.explorer_handler,
            pipeline_handler=self.pipeline_handler,
            docs_handler=self.docs_handler,
            monitoring_handler=self.monitoring_handler,
            demo_handler=self.demo_handler,
        )
        self._server = ThreadedGUIServer((host, port), handler_factory)
        self._server._workspace_lock = self._lock
        logger.info("det Web IDE launched at http://%s:%d", host, port)

        if blocking:
            try:
                self._server.serve_forever()
            except KeyboardInterrupt:
                self.stop()
        else:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Safely terminate HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


def start_gui_server(
    workspace: Workspace,
    host: str = "127.0.0.1",
    port: int = 8080,
    blocking: bool = True,
) -> GUIServer:
    """Convenience helper to launch Web IDE server."""
    server = GUIServer(workspace)
    server.start(host=host, port=port, blocking=blocking)
    return server
