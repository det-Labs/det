"""Embedded lightweight HTTP server for previewing documentation locally."""

import functools
import http.server
import logging
from pathlib import Path
import threading

from det.docs.base import BaseDocsServer

logger = logging.getLogger(__name__)


class DocsServer(BaseDocsServer):
    """Serves static documentation files via standard Python HTTP server."""

    def start_server(self, docs_dir: Path, port: int = 8080) -> None:
        """Launch blocking HTTP server serving the target documentation directory."""
        server = self.create_server(docs_dir, port)
        logger.info("Serving documentation on http://127.0.0.1:%d", port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down documentation server.")
        finally:
            server.server_close()

    def create_server(
        self, docs_dir: Path, port: int = 8080
    ) -> http.server.HTTPServer:
        """Instantiate configured HTTPServer bound to docs directory."""
        if not docs_dir.exists():
            raise FileNotFoundError(f"Documentation directory '{docs_dir}' does not exist.")

        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(docs_dir)
        )
        return http.server.HTTPServer(("127.0.0.1", port), handler)

    def serve_in_background(
        self, docs_dir: Path, port: int = 8080
    ) -> tuple[http.server.HTTPServer, threading.Thread]:
        """Launch HTTP server on background thread (useful for tests and IDE previews)."""
        server = self.create_server(docs_dir, port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.debug("Started background docs server on port %d", port)
        return server, thread

