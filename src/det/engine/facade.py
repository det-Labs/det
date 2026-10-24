"""EngineFacade unifying session management, mounting, secrets, and query dispatching."""

from typing import Any
import duckdb

from det.engine.base import (
    EngineConfig,
    MountReport,
    Mountable,
    QueryResult,
)
from det.engine.dispatcher import QueryDispatcher
from det.engine.mounter import CatalogMounter
from det.engine.secrets import SecretResolver
from det.engine.session import DuckDBSessionManager


class EngineFacade:
    """Unified entry point for the DuckDB analytical engine subsystem."""

    def __init__(
        self,
        config: EngineConfig | None = None,
        session_manager: DuckDBSessionManager | None = None,
        mounter: CatalogMounter | None = None,
        secrets: SecretResolver | None = None,
        dispatcher: QueryDispatcher | None = None,
    ) -> None:
        self._session_mgr = session_manager or DuckDBSessionManager(config)
        self._mounter = mounter or CatalogMounter()
        self._secrets = secrets or SecretResolver()
        self._dispatcher = dispatcher or QueryDispatcher()

    @property
    def session(self) -> duckdb.DuckDBPyConnection:
        """Return the active DuckDB connection."""
        return self._session_mgr.get_connection()

    def execute(self, sql: str) -> QueryResult:
        """Execute a SQL query and return columns and rows."""
        return self._dispatcher.execute_query(self.session, sql)

    def execute_arrow(self, sql: str) -> Any:
        """Execute a SQL query and return a PyArrow Table."""
        return self._dispatcher.execute_to_arrow(self.session, sql)

    def mount_entity(self, name: str, select_sql: str) -> None:
        """Register an entity as a virtual view in the DuckDB session."""
        self._mounter.bind_entity_view(self.session, name, select_sql)

    def mount_database(
        self, name: str, conn_str: str, db_type: str | None = None
    ) -> None:
        """Attach an external database into the DuckDB session."""
        self._mounter.mount_database(self.session, name, conn_str, db_type)

    def mount_all(self, items: list[Mountable]) -> MountReport:
        """Mount a batch of items and return a MountReport."""
        return self._mounter.mount_all(self.session, items)

    def resolve_secret(self, raw: str) -> str:
        """Resolve environment variable templates in a string."""
        return self._secrets.resolve_value(raw)

    def mask_secret(self, raw: str) -> str:
        """Mask a secret value."""
        return self._secrets.mask_secret(raw)

    def close(self) -> None:
        """Safely close and clean up the active DuckDB session."""
        self._session_mgr.close_connection()

