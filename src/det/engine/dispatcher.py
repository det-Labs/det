"""Query execution, error translation, and result dispatching for DuckDB."""

import logging
from typing import Any
import duckdb

from det.engine.base import BaseDispatcher, QueryResult

logger = logging.getLogger(__name__)


class QueryDispatcher(BaseDispatcher):
    """Executes SQL statements against a DuckDB connection and handles errors."""

    def execute_query(
        self, con: duckdb.DuckDBPyConnection, sql: str
    ) -> QueryResult:
        """Execute a SQL query and return column names and row tuples."""
        try:
            cursor = con.execute(sql)
            columns = self._extract_column_names(cursor)
            rows = cursor.fetchall()
            return QueryResult(columns=columns, rows=rows)
        except Exception as exc:
            formatted_msg = self.format_catalog_error(exc)
            logger.error("Query execution error: %s", formatted_msg)
            raise RuntimeError(formatted_msg) from exc

    def execute_to_arrow(
        self, con: duckdb.DuckDBPyConnection, sql: str
    ) -> Any:
        """Execute a SQL query and return the result as a PyArrow Table."""
        try:
            return con.sql(sql).to_arrow_table()
        except Exception as exc:
            if "pyarrow" in str(exc).lower() or not self._is_pyarrow_available():
                raise RuntimeError(
                    "PyArrow is required for Arrow streaming. Install pyarrow."
                ) from exc
            formatted_msg = self.format_catalog_error(exc)
            raise RuntimeError(formatted_msg) from exc

    def format_catalog_error(self, exc: Exception) -> str:
        """Format DuckDB errors into clear, actionable messages."""
        msg = str(exc)
        if isinstance(exc, duckdb.CatalogException):
            return f"Catalog Error: {self._clean_duckdb_message(msg)}"
        if isinstance(exc, duckdb.BinderException):
            return f"Binder Error: {self._clean_duckdb_message(msg)}"
        if isinstance(exc, duckdb.ParserException):
            return f"Syntax Error: {self._clean_duckdb_message(msg)}"
        return f"Database Error: {msg}"

    def _extract_column_names(self, cursor: Any) -> list[str]:
        """Extract column names from cursor description."""
        if cursor.description is None:
            return []
        return [desc[0] for desc in cursor.description]

    def _clean_duckdb_message(self, message: str) -> str:
        """Clean raw DuckDB error message by stripping prefix if repeated."""
        for prefix in ("Catalog Error: ", "Binder Error: ", "Parser Error: "):
            if message.startswith(prefix):
                return message[len(prefix) :].strip()
        return message.strip()

    def _is_pyarrow_available(self) -> bool:
        """Check if pyarrow is imported or importable."""
        try:
            import pyarrow  # type: ignore # noqa: F401

            return True
        except ImportError:
            return False

