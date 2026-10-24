"""Thread-safe registry for managing pluggable data connectors."""

import logging
import threading
from typing import Any

from det.extensions.base import BaseConnector

logger = logging.getLogger(__name__)


class ExtensionRegistry:
    """Thread-safe catalog of registered data source connectors."""

    def __init__(self) -> None:
        self._connectors: dict[str, type[BaseConnector]] = {}
        self._lock = threading.Lock()

    def register(self, connector_cls: type[BaseConnector]) -> None:
        """Register a new connector class, validating its key and base type."""
        if not issubclass(connector_cls, BaseConnector):
            raise TypeError(
                f"Connector {connector_cls.__name__} must inherit from BaseConnector."
            )
        if not hasattr(connector_cls, "key") or not connector_cls.key:
            raise ValueError(
                f"Connector {connector_cls.__name__} must define a non-empty 'key'."
            )

        with self._lock:
            self._connectors[connector_cls.key.lower()] = connector_cls
            logger.debug("Registered connector: '%s'", connector_cls.key)

    def get(self, key: str) -> type[BaseConnector] | None:
        """Retrieve a registered connector class by its key."""
        with self._lock:
            return self._connectors.get(key.lower())

    def list_keys(self) -> list[str]:
        """Return list of all registered connector keys."""
        with self._lock:
            return sorted(self._connectors.keys())

    def list_connectors(self) -> list[type[BaseConnector]]:
        """Return list of all registered connector classes."""
        with self._lock:
            return sorted(self._connectors.values(), key=lambda c: c.key)

    def list_schemas(self) -> list[dict[str, Any]]:
        """Return UI form schemas for all registered connectors."""
        with self._lock:
            return [
                conn_cls.get_schema()
                for conn_cls in sorted(self._connectors.values(), key=lambda c: c.key)
            ]

    def clear(self) -> None:
        """Clear all registered connectors."""
        with self._lock:
            self._connectors.clear()


# Default global registry instance
global_registry = ExtensionRegistry()

