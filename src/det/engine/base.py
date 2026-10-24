"""Base classes, protocols, and data models for the engine subsystem."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
import duckdb


@dataclass(frozen=True)
class EngineConfig:
    """Configuration options for a DuckDB engine session."""

    database: str = ":memory:"
    threads: int | None = None
    memory_limit: str | None = None
    extensions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QueryResult:
    """Encapsulates columnar query results."""

    columns: list[str]
    rows: list[tuple[Any, ...]]

    @property
    def row_count(self) -> int:
        """Return the number of rows returned."""
        return len(self.rows)


@runtime_checkable
class Mountable(Protocol):
    """Protocol for any catalog object that can be mounted into DuckDB."""

    @property
    def name(self) -> str:
        """Name of the connection identifier."""
        ...

    @property
    def tier(self) -> str:
        """Tier: 'entity' or 'database'."""
        ...

    def get_mount_sql(self) -> str:
        """Generate the SQL statement required to mount or bind this connection."""
        ...


@dataclass
class MountReport:
    """Report detailing successfully mounted and failed connections."""

    mounted: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    @property
    def is_successful(self) -> bool:
        """Return True if all attempted connections mounted without error."""
        return len(self.failed) == 0


class BaseSessionManager(ABC):
    """Abstract interface for managing DuckDB connection lifecycles."""

    @abstractmethod
    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Retrieve or initialize the active DuckDB connection."""
        pass

    @abstractmethod
    def close_connection(self) -> None:
        """Safely terminate the active DuckDB connection."""
        pass


class BaseDispatcher(ABC):
    """Abstract interface for executing queries against DuckDB."""

    @abstractmethod
    def execute_query(
        self, con: duckdb.DuckDBPyConnection, sql: str
    ) -> QueryResult:
        """Execute a query returning column names and row tuples."""
        pass

    @abstractmethod
    def execute_to_arrow(
        self, con: duckdb.DuckDBPyConnection, sql: str
    ) -> Any:
        """Execute a query returning an Arrow table."""
        pass


class BaseMounter(ABC):
    """Abstract interface for mounting connections into a DuckDB session."""

    @abstractmethod
    def mount_all(
        self, con: duckdb.DuckDBPyConnection, items: list[Mountable]
    ) -> MountReport:
        """Mount a batch of items, isolating failures and returning a report."""
        pass


class BaseSecretResolver(ABC):
    """Abstract interface for secret resolution and masking."""

    @abstractmethod
    def resolve_value(self, raw: str) -> str:
        """Interpolate environment variables in a raw string."""
        pass

    @abstractmethod
    def mask_secret(self, raw: str) -> str:
        """Mask sensitive secret strings."""
        pass

