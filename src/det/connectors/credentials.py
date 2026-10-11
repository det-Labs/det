"""Re-exports for backwards compatibility from connections.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from det.connectors import connections


def get_credentials_path() -> Path:
    return connections.get_connections_path()


def __getattr__(name: str) -> Any:
    if name in ("CREDENTIALS_FILE", "CONNECTIONS_FILE"):
        return get_credentials_path()
    if hasattr(connections, name):
        return getattr(connections, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
