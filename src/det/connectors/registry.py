"""Connector registry for discovery, lookup, and custom connector loading."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from det.connectors.contract import BaseConnector, ConnectorGroup

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector) -> None:
        self._connectors[connector.id.lower()] = connector

    def unregister(self, connector_id: str) -> None:
        self._connectors.pop(connector_id.lower(), None)

    def clear(self) -> None:
        self._connectors.clear()

    def get(self, connector_id: str) -> BaseConnector:
        key = connector_id.lower()
        if key not in self._connectors:
            raise KeyError(f"Connector '{connector_id}' is not registered.")
        return self._connectors[key]

    def has(self, connector_id: str) -> bool:
        return connector_id.lower() in self._connectors

    def list_all(self) -> list[BaseConnector]:
        return list(self._connectors.values())

    def list_specs(self) -> list[dict[str, Any]]:
        return [c.spec() for c in self._connectors.values()]

    def list_grouped(self) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = {
            ConnectorGroup.DATABASES.value: [],
            ConnectorGroup.FILES.value: [],
            ConnectorGroup.APIS.value: [],
            ConnectorGroup.OTHERS.value: [],
        }
        for connector in self._connectors.values():
            group_name = (
                connector.group.value
                if isinstance(connector.group, ConnectorGroup)
                else str(connector.group)
            )
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(connector.spec())
        return groups

    def discover_and_register_from_directory(self, directory: Path | str) -> list[str]:
        """Scan a folder location for custom connector .py files, instantiate and register them."""
        dir_path = Path(directory).expanduser().resolve()
        loaded: list[str] = []
        if not dir_path.is_dir():
            return loaded

        for file_path in sorted(dir_path.glob("*.py")):
            if file_path.name.startswith(("_", ".")):
                continue
            try:
                module_name = f"det_custom_connector_{file_path.stem}"
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = mod
                    spec.loader.exec_module(mod)
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, BaseConnector)
                            and attr is not BaseConnector
                        ):
                            instance = attr()
                            self.register(instance)
                            loaded.append(instance.id)
            except Exception as exc:
                logger.warning("Failed to load connector from %s: %s", file_path, exc)
        return loaded


_global_registry = ConnectorRegistry()


def get_registry() -> ConnectorRegistry:
    return _global_registry


def register_connector(connector: BaseConnector) -> None:
    _global_registry.register(connector)


def get_connector(connector_id: str) -> BaseConnector:
    return _global_registry.get(connector_id)


def list_connectors() -> list[BaseConnector]:
    return _global_registry.list_all()


def list_connectors_specs() -> list[dict[str, Any]]:
    return _global_registry.list_specs()


def list_connectors_grouped() -> dict[str, list[dict[str, Any]]]:
    # Also discover any custom connectors in standard custom connector folders if they exist
    for custom_dir in [Path.cwd() / "connectors", Path.home() / ".det" / "connectors"]:
        if custom_dir.is_dir():
            _global_registry.discover_and_register_from_directory(custom_dir)
    return _global_registry.list_grouped()


def discover_and_register_from_directory(directory: Path | str) -> list[str]:
    return _global_registry.discover_and_register_from_directory(directory)
