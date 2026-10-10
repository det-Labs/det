"""det.gui - Web-based graphical interface for det Catalog Explorer."""

from __future__ import annotations

import socket
import threading
import time
import webbrowser
from pathlib import Path

# Python 3.15 lazy imports: defer uvicorn until launch_gui is invoked
lazy import uvicorn

from det.catalog.config import get_default_catalog_path
from det.catalog.service import CatalogService
from det.gui.server import app, set_service


def _find_available_port(host: str, start_port: int, max_attempts: int = 20) -> int:
    """Find the next available TCP port on the host."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return start_port


def launch_gui(
    catalog_path: str | Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8501,
    open_browser: bool = True,
) -> None:
    """Launch the interactive det Catalog Explorer in the local browser.

    Args:
        catalog_path: Optional path to a catalog YAML file. If omitted,
            uses the configured default catalog path.
        host: Host IP address to bind (default 127.0.0.1).
        port: Preferred TCP port to bind (default 8501).
        open_browser: Whether to automatically launch the default browser.
    """
    selected_path = Path(catalog_path).resolve() if catalog_path else get_default_catalog_path()
    service = CatalogService(selected_path)
    set_service(service)

    actual_port = _find_available_port(host, port)
    url = f"http://{host}:{actual_port}"

    print("=" * 60)
    print(f"det Catalog Explorer running at: {url}")
    print(f"Active Catalog File: {selected_path}")
    print("Press Ctrl+C to stop the server.")
    print("=" * 60)

    if open_browser:
        def _open() -> None:
            time.sleep(1.0)
            webbrowser.open(url)

        thread = threading.Thread(target=_open, daemon=True)
        thread.start()

    uvicorn.run(app, host=host, port=actual_port, log_level="warning")


def cli_main() -> None:
    """CLI entrypoint for the det-gui executable."""
    import argparse

    parser = argparse.ArgumentParser(description="det Catalog Explorer Web GUI")
    parser.add_argument("-f", "--file", type=str, default=None, help="Catalog YAML file to open")
    parser.add_argument("-p", "--port", type=int, default=8501, help="Port to run web server on")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    args = parser.parse_args()

    launch_gui(catalog_path=args.file, port=args.port, open_browser=not args.no_browser)


__all__ = ["app", "cli_main", "launch_gui"]
