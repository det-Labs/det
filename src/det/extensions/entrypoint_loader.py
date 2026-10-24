"""Loader for third-party connector plugins installed via PyPI entry points."""

import importlib.metadata
import logging
from typing import Any

from det.extensions.base import BaseConnector
from det.extensions.registry import ExtensionRegistry

logger = logging.getLogger(__name__)

ENTRYPOINT_GROUP = "det.connectors"


class EntrypointExtensionLoader:
    """Discovers and registers connectors distributed as Python packages."""

    def load_entrypoints(self, registry: ExtensionRegistry) -> list[str]:
        """Find and register all connectors exposed via entry points."""
        discovered_keys: list[str] = []
        try:
            entry_points = importlib.metadata.entry_points(group=ENTRYPOINT_GROUP)
            for ep in entry_points:
                key = self._load_single_entrypoint(ep, registry)
                if key:
                    discovered_keys.append(key)
        except Exception as exc:
            logger.warning("Error scanning entry points for '%s': %s", ENTRYPOINT_GROUP, exc)
        return discovered_keys

    def _load_single_entrypoint(
        self, ep: Any, registry: ExtensionRegistry
    ) -> str | None:
        """Load an individual entry point and register its connector."""
        try:
            connector_cls = ep.load()
            if issubclass(connector_cls, BaseConnector) and connector_cls is not BaseConnector:
                registry.register(connector_cls)
                return connector_cls.key
            logger.warning("Entrypoint '%s' is not a valid BaseConnector subclass", ep.name)
        except Exception as exc:
            logger.warning("Failed to load entrypoint '%s': %s", ep.name, exc)
        return None

