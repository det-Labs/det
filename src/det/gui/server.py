"""Embedded HTTP server hosting the modular Web IDE and REST endpoints."""

import functools
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import logging
from pathlib import Path
import threading
from typing import Any

from det.gui.base import BaseGUIServer
from det.gui.routes.catalog_routes import CatalogRouteHandler
from det.gui.routes.common import read_json_body, send_error_json
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

    def do_GET(self) -> None:
        """Handle incoming GET requests."""
        raw_path = self.path.split("?")[0]
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

    def do_POST(self) -> None:
        """Handle incoming POST requests."""
        raw_path = self.path.split("?")[0]
        body = read_json_body(self)
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
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self, port: int = 8080, blocking: bool = True) -> None:
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
        self._server = HTTPServer(("127.0.0.1", port), handler_factory)
        logger.info("det Web IDE launched at http://127.0.0.1:%d", port)

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
    workspace: Workspace, port: int = 8080, blocking: bool = True
) -> GUIServer:
    """Convenience helper to launch Web IDE server."""
    server = GUIServer(workspace)
    server.start(port=port, blocking=blocking)
    return server
