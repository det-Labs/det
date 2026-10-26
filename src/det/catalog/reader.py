"""YAML deserialization and secret interpolation for connection catalogs."""

import logging
from pathlib import Path
from typing import Any
import yaml

from det.catalog.base import BaseCatalogReader
from det.catalog.definitions import ConnectionDefinition
from det.engine.secrets import SecretResolver

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


def is_absolute_path(path_str: str) -> bool:
    """Return True if path is an absolute filesystem path on Windows or POSIX."""
    if not path_str or is_remote_uri(path_str):
        return True
    clean = path_str.strip()
    if Path(clean).is_absolute() or clean.startswith(("/", "\\")):
        return True
    import re
    if re.match(r"^[a-zA-Z]:[\\/]", clean):
        return True
    return False


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
        """Instantiate ConnectionDefinition objects from parsed dictionary, enforcing absolute paths."""
        definitions: dict[str, ConnectionDefinition] = {}
        for name, data in connections_map.items():
            if not isinstance(data, dict):
                continue
            item_data = (
                self._secrets.resolve_item(data) if resolve_secrets else data
            )
            options = item_data.get("options", {})
            for key in ("path", "table_path"):
                val = options.get(key)
                if val and isinstance(val, str) and not is_remote_uri(val):
                    if not is_absolute_path(val):
                        raise ValueError(
                            f"Connection '{name}' option '{key}' specifies relative path '{val}'. "
                            "Data file locations must always be full absolute paths in connections.yaml."
                        )
            definitions[name] = ConnectionDefinition.from_dict(name, item_data)
        return definitions

