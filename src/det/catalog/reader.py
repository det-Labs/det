"""YAML deserialization and secret interpolation for connection catalogs."""

import logging
from pathlib import Path
from typing import Any
import yaml

from det.catalog.base import BaseCatalogReader
from det.catalog.definitions import ConnectionDefinition
from det.engine.secrets import SecretResolver

logger = logging.getLogger(__name__)


class CatalogReader(BaseCatalogReader):
    """Reads connections catalog from YAML configuration files."""

    def __init__(self, secret_resolver: SecretResolver | None = None) -> None:
        self._secrets = secret_resolver or SecretResolver()

    def read_yaml(
        self, file_path: Path, resolve_secrets: bool = False
    ) -> dict[str, ConnectionDefinition]:
        """Read and parse connections from a YAML file."""
        if not file_path.exists():
            logger.debug("Catalog file '%s' does not exist; returning empty.", file_path)
            return {}

        raw_data = self._load_raw_yaml(file_path)
        connections_map = self._extract_connections_block(raw_data)
        return self._parse_definitions(connections_map, resolve_secrets)

    def _load_raw_yaml(self, file_path: Path) -> dict[str, Any]:
        """Safely load and validate YAML content from file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                return content if isinstance(content, dict) else {}
        except Exception as exc:
            logger.error("Failed to parse YAML from '%s': %s", file_path, exc)
            raise ValueError(f"Corrupt or invalid YAML in '{file_path}': {exc}") from exc

    def _extract_connections_block(
        self, raw_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalize connections block whether under top-level 'connections' or root."""
        if "connections" in raw_data and isinstance(raw_data["connections"], dict):
            return raw_data["connections"]
        return raw_data

    def _parse_definitions(
        self,
        connections_map: dict[str, Any],
        resolve_secrets: bool,
    ) -> dict[str, ConnectionDefinition]:
        """Instantiate ConnectionDefinition objects from parsed dictionary."""
        definitions: dict[str, ConnectionDefinition] = {}
        for name, data in connections_map.items():
            if not isinstance(data, dict):
                continue
            item_data = (
                self._secrets.resolve_item(data) if resolve_secrets else data
            )
            definitions[name] = ConnectionDefinition.from_dict(name, item_data)
        return definitions

