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
    """Coordinates connection definitions, file persistence, and health testing.
    
    Strictly binds to connections.yaml within catalog/. Any other yaml files in that
    folder are completely ignored.
    """

    CANONICAL_FILENAME = "connections.yaml"

    def __init__(
        self,
        file_path: Path,
        reader: CatalogReader | None = None,
        writer: CatalogWriter | None = None,
        tester: ConnectionTester | None = None,
        auto_load: bool = True,
    ) -> None:
        p = Path(file_path).resolve()
        if p.is_dir():
            target_file = p / self.CANONICAL_FILENAME
        elif p.name != self.CANONICAL_FILENAME and p.parent.name == "catalog":
            logger.debug(
                "Ignoring non-canonical catalog file '%s'; strictly using '%s'",
                p.name,
                self.CANONICAL_FILENAME,
            )
            target_file = p.parent / self.CANONICAL_FILENAME
        else:
            target_file = p

        self._file_path = target_file
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

    def list_connections(
        self, folder: str | None = None, name_filter: str | None = None
    ) -> list[ConnectionDefinition]:
        """Return sorted list of all active connection definitions, optionally filtered by folder and name substring."""
        conns = sorted(self._connections.values(), key=lambda c: c.name)
        if folder is not None:
            target_f = folder.strip().lower()
            conns = [c for c in conns if (c.folder or "").strip().lower() == target_f]
        if name_filter is not None:
            q = name_filter.strip().lower()
            conns = [c for c in conns if q in c.name.lower()]
        return conns

    def get_connection(self, name: str) -> ConnectionDefinition | None:
        """Retrieve a connection definition by its identifier."""
        return self._connections.get(name)

    def get_connection_details(self, name: str) -> dict[str, Any]:
        """Retrieve complete properties and metadata for a given connection."""
        conn_def = self.get_connection(name)
        if conn_def is None:
            raise KeyError(f"Connection '{name}' not found in catalog.")

        sanitized_creds: dict[str, Any] = {}
        for k, v in conn_def.credentials.items():
            if any(term in k.lower() for term in ("key", "secret", "password", "token", "auth")):
                sanitized_creds[k] = "******"
            else:
                sanitized_creds[k] = v

        return {
            "name": conn_def.name,
            "type": conn_def.type,
            "tier": conn_def.tier_value,
            "folder": conn_def.folder or "(Root)",
            "description": conn_def.description or "",
            "options": dict(conn_def.options or {}),
            "credentials": sanitized_creds,
            "mount_sql": conn_def.get_mount_sql(),
        }

    def display_connection(
        self, con: duckdb.DuckDBPyConnection, name: str, limit: int = 10
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Query and return top N rows from the mounted connection view/table."""
        conn_def = self.get_connection(name)
        if conn_def is None:
            raise KeyError(f"Connection '{name}' not found in catalog.")

        mount_sql = conn_def.get_mount_sql()
        con.execute(mount_sql)
        cursor = con.execute(f"SELECT * FROM {name} LIMIT {int(limit)}")
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return columns, rows

    def add_connection(
        self, conn_def: ConnectionDefinition, persist: bool = True
    ) -> None:
        """Register or update a connection definition, optionally saving to disk."""
        self._connections[conn_def.name] = conn_def
        if persist:
            self.save()

    def delete_connection(self, name: str, persist: bool = True) -> bool:
        """Remove an individual connection definition from the catalog."""
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

    def test_connections(
        self,
        con: duckdb.DuckDBPyConnection,
        connection: str | None = None,
        folder: str | None = None,
    ) -> dict[str, ConnectionTestResult]:
        """Health check a single connection, connections in a folder, or all connections."""
        if connection:
            return {connection: self.test_connection(con, connection)}
        targets = self.list_connections(folder=folder)
        return {
            c.name: self._tester.test_connection(con, c)
            for c in targets
        }

    def get_mountable_items(self) -> list[ConnectionDefinition]:
        """Return list of all connection definitions as Mountable instances."""
        return list(self._connections.values())

