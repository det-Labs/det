"""Central catalog manager coordinating definitions, persistence, and health probes."""

import logging
from pathlib import Path
from typing import Any
import duckdb

from det.catalog.base import (
    BaseCatalogManager,
    ConnectionTestResult,
)
from det.catalog.definitions import ConnectionDefinition
from det.catalog.reader import CatalogReader
from det.catalog.tester import ConnectionTester
from det.catalog.writer import CatalogWriter

logger = logging.getLogger(__name__)


class CatalogManager(BaseCatalogManager):
    """Coordinates connection definitions, file persistence, and health testing."""

    def __init__(
        self,
        file_path: Path,
        reader: CatalogReader | None = None,
        writer: CatalogWriter | None = None,
        tester: ConnectionTester | None = None,
        auto_load: bool = True,
    ) -> None:
        self._file_path = file_path
        self._reader = reader or CatalogReader()
        self._writer = writer or CatalogWriter()
        self._tester = tester or ConnectionTester()
        self._connections: dict[str, ConnectionDefinition] = {}

        if auto_load and self._file_path.exists():
            self.load()

    @property
    def file_path(self) -> Path:
        """Return path to connections catalog file."""
        return self._file_path

    def load(self, resolve_secrets: bool = False) -> None:
        """Load connection definitions from YAML file into memory."""
        self._connections = self._reader.read_yaml(
            self._file_path, resolve_secrets=resolve_secrets
        )
        logger.debug("Loaded %d connections from '%s'", len(self._connections), self._file_path)

    def save(self) -> None:
        """Persist current in-memory connection definitions to disk."""
        self._writer.write_yaml(self._file_path, self._connections)

    def list_connections(self) -> list[ConnectionDefinition]:
        """Return sorted list of all active connection definitions."""
        return sorted(self._connections.values(), key=lambda c: c.name)

    def get_connection(self, name: str) -> ConnectionDefinition | None:
        """Retrieve a connection definition by its identifier."""
        return self._connections.get(name)

    def add_connection(
        self, conn_def: ConnectionDefinition, persist: bool = True
    ) -> None:
        """Register or update a connection definition, optionally saving to disk."""
        self._connections[conn_def.name] = conn_def
        if persist:
            self.save()

    def delete_connection(self, name: str, persist: bool = True) -> bool:
        """Remove a connection definition from the catalog."""
        if name not in self._connections:
            return False
        del self._connections[name]
        if persist:
            self.save()
        return True

    def test_connection(
        self, con: duckdb.DuckDBPyConnection, name: str
    ) -> ConnectionTestResult:
        """Run health check against a registered connection."""
        conn_def = self.get_connection(name)
        if conn_def is None:
            raise KeyError(f"Connection '{name}' not found in catalog.")
        return self._tester.test_connection(con, conn_def)

    def test_all(
        self, con: duckdb.DuckDBPyConnection
    ) -> dict[str, ConnectionTestResult]:
        """Run health check across all registered connections."""
        return {
            name: self._tester.test_connection(con, conn_def)
            for name, conn_def in self._connections.items()
        }

    def get_mountable_items(self) -> list[ConnectionDefinition]:
        """Return list of all connection definitions as Mountable instances."""
        return list(self._connections.values())

