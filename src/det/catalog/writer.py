"""Atomic YAML serialization for the connections catalog."""

import logging
import os
from pathlib import Path
from typing import Any
import yaml

from det.catalog.base import BaseCatalogWriter
from det.catalog.definitions import ConnectionDefinition

logger = logging.getLogger(__name__)


class CatalogWriter(BaseCatalogWriter):
    """Safely serializes and persists catalog definitions to YAML."""

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
        """Convert definitions dictionary to YAML-ready dictionary structure."""
        return {
            "connections": {
                name: conn.to_dict()
                for name, conn in sorted(connections.items())
            }
        }

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

