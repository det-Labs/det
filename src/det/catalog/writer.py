"""Atomic YAML serialization for the connections catalog."""

import logging
import os
from pathlib import Path
from typing import Any
import yaml

from det.catalog.base import BaseCatalogWriter
from det.catalog.definitions import ConnectionDefinition

logger = logging.getLogger(__name__)


REMOTE_SCHEMES = (
    "s3://", "gs://", "gcs://", "abfss://", "abfs://",
    "azure://", "r2://", "http://", "https://",
    "postgres://", "postgresql://", "mysql://", "mssql://",
)


def is_remote_uri(uri: str) -> bool:
    """Check if URI points to a cloud/network protocol rather than local filesystem."""
    clean = uri.strip().lower()
    return any(clean.startswith(s) for s in REMOTE_SCHEMES)


def ensure_absolute_path(path_str: str) -> str:
    """Convert a local filesystem path to an absolute full path formatted with forward slashes."""
    if not path_str or is_remote_uri(path_str):
        return path_str
    return Path(path_str.strip()).resolve().as_posix()


class CatalogWriter(BaseCatalogWriter):
    """Safely serializes and persists catalog definitions to YAML, enforcing absolute paths."""

    def write_yaml(
        self, file_path: Path, connections: dict[str, ConnectionDefinition]
    ) -> None:
        """Atomically persist connections dictionary to target YAML file."""
        payload = self._prepare_payload(connections)
        self._ensure_parent_directory(file_path)
        self._atomic_save(file_path, payload)

    def _prepare_payload(
        self, connections: dict[str, ConnectionDefinition]
    ) -> dict[str, Any]:
        """Convert definitions dictionary to YAML-ready dictionary structure, ensuring all local paths are absolute."""
        data = {}
        for name, conn in sorted(connections.items()):
            conn_dict = conn.to_dict()
            options = dict(conn_dict.get("options", {}))
            for key in ("path", "table_path"):
                val = options.get(key)
                if val and isinstance(val, str) and not is_remote_uri(val):
                    options[key] = ensure_absolute_path(val)
            conn_dict["options"] = options
            data[name] = conn_dict
        return {"connections": data}

    def _ensure_parent_directory(self, file_path: Path) -> None:
        """Create parent directory if it does not yet exist."""
        file_path.parent.mkdir(parents=True, exist_ok=True)

    def _atomic_save(self, file_path: Path, payload: dict[str, Any]) -> None:
        """Write content to temporary file, flush, and atomically replace target."""
        tmp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                yaml.dump(payload, f, sort_keys=False, default_flow_style=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, file_path)
            logger.debug("Successfully saved catalog to '%s'", file_path)
        except Exception as exc:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            logger.error("Failed to atomically write catalog to '%s': %s", file_path, exc)
            raise IOError(f"Could not write catalog to '{file_path}': {exc}") from exc

