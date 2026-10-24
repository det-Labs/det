"""Base protocols, enums, and data models for the catalog subsystem."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
import duckdb


class ConnectionTier(str, Enum):
    """Architectural classification of a connection."""

    ENTITY = "entity"
    DATABASE = "database"


class ConnectionTestStatus(str, Enum):
    """Health check ping status."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ConnectionTestResult:
    """Outcome of a live connection health check."""

    status: ConnectionTestStatus
    latency_ms: float
    error_message: str | None = None

    @property
    def is_healthy(self) -> bool:
        """Return True if connection probe succeeded."""
        return self.status == ConnectionTestStatus.SUCCESS


class BaseCatalogReader(ABC):
    """Interface for reading and deserializing catalog definitions."""

    @abstractmethod
    def read_yaml(self, file_path: Path) -> dict[str, Any]:
        """Read connections YAML and return dictionary of definitions."""
        pass


class BaseCatalogWriter(ABC):
    """Interface for serializing and writing catalog definitions."""

    @abstractmethod
    def write_yaml(self, file_path: Path, connections: dict[str, Any]) -> None:
        """Persist dictionary of definitions to a YAML file."""
        pass


class BaseConnectionTester(ABC):
    """Interface for executing connection health checks."""

    @abstractmethod
    def test_connection(
        self, con: duckdb.DuckDBPyConnection, conn_def: Any
    ) -> ConnectionTestResult:
        """Probe an active connection and measure roundtrip latency."""
        pass


class BaseCatalogManager(ABC):
    """Interface for managing connection lifecycle and storage."""

    @abstractmethod
    def list_connections(self) -> list[Any]:
        """List all registered connection definitions."""
        pass

    @abstractmethod
    def get_connection(self, name: str) -> Any | None:
        """Retrieve a connection definition by its unique name."""
        pass

