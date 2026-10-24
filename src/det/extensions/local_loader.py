"""Dynamic loader for user-provided drop-in connector extensions."""

import importlib.util
import inspect
import logging
from pathlib import Path
from typing import Any

from det.extensions.base import BaseConnector
from det.extensions.registry import ExtensionRegistry

logger = logging.getLogger(__name__)


class LocalExtensionLoader:
    """Discovers and imports connector classes from local Python script files."""

    def load_directory(
        self, dir_path: Path, registry: ExtensionRegistry
    ) -> list[str]:
        """Scan a directory for Python files and load all discovered connectors."""
        if not dir_path.exists() or not dir_path.is_dir():
            return []

        loaded_keys: list[str] = []
        for file_path in dir_path.glob("*.py"):
            if file_path.name.startswith("__"):
                continue
            keys = self.load_file(file_path, registry)
            loaded_keys.extend(keys)
        return loaded_keys

    def load_file(
        self, file_path: Path, registry: ExtensionRegistry
    ) -> list[str]:
        """Import a single Python file and register any BaseConnector subclasses."""
        try:
            module = self._import_module_from_path(file_path)
            return self._register_connectors_from_module(module, registry)
        except Exception as exc:
            logger.warning("Failed to load extension file '%s': %s", file_path, exc)
            return []

    def _import_module_from_path(self, file_path: Path) -> Any:
        """Dynamically load Python module from file system path."""
        module_name = f"det_ext_{file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for '{file_path}'")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _register_connectors_from_module(
        self, module: Any, registry: ExtensionRegistry
    ) -> list[str]:
        """Inspect module for BaseConnector subclasses and register them."""
        registered_keys: list[str] = []
        for _, member in inspect.getmembers(module, inspect.isclass):
            if issubclass(member, BaseConnector) and member is not BaseConnector:
                try:
                    registry.register(member)
                    registered_keys.append(member.key)
                except Exception as exc:
                    logger.warning("Error registering connector %s: %s", member, exc)
        return registered_keys

