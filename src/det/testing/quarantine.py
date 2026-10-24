"""Quarantine sink handler segregating failing rows into dedicated inspection tables."""

import logging
from typing import Any
import duckdb

from det.testing.base import BaseQuarantineHandler

logger = logging.getLogger(__name__)


class QuarantineHandler(BaseQuarantineHandler):
    """Routes violating rows into a _quarantine_<model> sink table without pipeline failure."""

    def quarantine_records(
        self,
        con: duckdb.DuckDBPyConnection,
        model_name: str,
        test_name: str,
        failing_query: str,
    ) -> str:
        """Extract violating rows into _quarantine_<model> table and return table name."""
        quarantine_table = self.get_quarantine_table_name(model_name)
        self._ensure_quarantine_table(con, quarantine_table, test_name, failing_query)
        self._insert_failing_rows(con, quarantine_table, test_name, failing_query)
        logger.info("Quarantined failing records for '%s' into '%s'", model_name, quarantine_table)
        return quarantine_table

    def get_quarantine_table_name(self, model_name: str) -> str:
        """Return standardized quarantine table name for a model."""
        return f"_quarantine_{model_name}"

    def get_quarantined_count(
        self, con: duckdb.DuckDBPyConnection, model_name: str
    ) -> int:
        """Return count of quarantined rows for a model, or 0 if table absent."""
        quarantine_table = self.get_quarantine_table_name(model_name)
        try:
            res = con.execute(f"SELECT COUNT(*) FROM {quarantine_table}").fetchall()
            return int(res[0][0]) if res else 0
        except Exception:
            return 0

    def get_quarantined_rows(
        self,
        con: duckdb.DuckDBPyConnection,
        model_name: str,
        limit: int = 100,
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Fetch columns and sample rows from the quarantine table for UI inspection."""
        quarantine_table = self.get_quarantine_table_name(model_name)
        try:
            cursor = con.execute(f"SELECT * FROM {quarantine_table} LIMIT {limit}")
            cols = [desc[0] for desc in cursor.description] if cursor.description else []
            return cols, cursor.fetchall()
        except Exception as exc:
            logger.warning("Error fetching quarantined rows: %s", exc)
            return [], []

    def _ensure_quarantine_table(
        self,
        con: duckdb.DuckDBPyConnection,
        table_name: str,
        test_name: str,
        failing_query: str,
    ) -> None:
        """Create empty quarantine table with metadata columns if not present."""
        create_sql = (
            f"CREATE TABLE IF NOT EXISTS {table_name} AS "
            f"SELECT *, CAST(CURRENT_TIMESTAMP AS TIMESTAMP) AS quarantined_at, '{test_name}' AS failure_reason "
            f"FROM ({failing_query}) WHERE 1=0"
        )
        con.execute(create_sql)

    def _insert_failing_rows(
        self,
        con: duckdb.DuckDBPyConnection,
        table_name: str,
        test_name: str,
        failing_query: str,
    ) -> None:
        """Insert violating rows into quarantine table with metadata tags."""
        insert_sql = (
            f"INSERT INTO {table_name} BY NAME "
            f"SELECT *, CAST(CURRENT_TIMESTAMP AS TIMESTAMP) AS quarantined_at, '{test_name}' AS failure_reason "
            f"FROM ({failing_query})"
        )
        con.execute(insert_sql)
