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
        self._aliases: dict[str, str] = {}
        self._lock = threading.Lock()

    def register(
        self,
        connector_cls: type[BaseConnector],
        aliases: list[str] | None = None,
    ) -> None:
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
            canonical_key = connector_cls.key.lower()
            self._connectors[canonical_key] = connector_cls

            # Register any explicit aliases or connector class attributes
            all_aliases = list(aliases or [])
            if hasattr(connector_cls, "aliases") and isinstance(connector_cls.aliases, (list, tuple)):
                all_aliases.extend(connector_cls.aliases)

            for alias in all_aliases:
                self._aliases[alias.lower()] = canonical_key

            logger.debug(
                "Registered connector: '%s' (aliases: %s)",
                canonical_key,
                all_aliases,
            )

    def register_alias(self, alias: str, canonical_key: str) -> None:
        """Register an alternative lookup key pointing to a canonical connector."""
        with self._lock:
            self._aliases[alias.lower()] = canonical_key.lower()

    def get(self, key: str) -> type[BaseConnector] | None:
        """Retrieve a registered connector class by its key or alias."""
        with self._lock:
            key_lower = key.lower()
            canonical = self._aliases.get(key_lower, key_lower)
            return self._connectors.get(canonical)

    def list_keys(self) -> list[str]:
        """Return list of all registered canonical connector keys."""
        with self._lock:
            return sorted(self._connectors.keys())

    def list_connectors(self) -> list[type[BaseConnector]]:
        """Return list of all registered unique connector classes."""
        with self._lock:
            return sorted(self._connectors.values(), key=lambda c: c.key)

    def list_schemas(self) -> list[dict[str, Any]]:
        """Return UI form schemas for all unique registered connectors."""
        with self._lock:
            return [
                conn_cls.get_schema()
                for conn_cls in sorted(self._connectors.values(), key=lambda c: c.key)
            ]

    def clear(self) -> None:
        """Clear all registered connectors and aliases."""
        with self._lock:
            self._connectors.clear()
            self._aliases.clear()


# Default global registry instance
global_registry = ExtensionRegistry()

