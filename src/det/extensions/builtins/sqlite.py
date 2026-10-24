"""Built-in connector for SQLite databases."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class SQLiteConnector(BaseConnector):
    """Connector attaching external SQLite database files."""

    key = "sqlite"
    label = "SQLite Database"
    description = "Attach a local SQLite database for direct querying."
    tier = ConnectionTier.DATABASE

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="path",
                label="Database Path",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="data/database.db",
                description="Local filesystem path to the SQLite .db or .sqlite file.",
            ),
            ConnectorField(
                name="read_only",
                label="Read Only",
                field_type=FieldType.BOOLEAN,
                default=True,
                description="Attach the database in read-only mode.",
            ),
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        return ""

    def get_attach_sql(
        self, options: dict[str, Any], credentials: dict[str, Any]
    ) -> str | None:
        path = str(options.get("path") or credentials.get("path", "")).replace("'", "''")
        name_clause = f" AS {options['name']}" if "name" in options else ""
        ro_clause = ", READ_ONLY" if options.get("read_only", True) else ""
        return f"ATTACH '{path}'{name_clause} (TYPE SQLITE{ro_clause})"

    def test_connection(
        self,
        con: duckdb.DuckDBPyConnection,
        options: dict[str, Any],
        credentials: dict[str, Any],
    ) -> bool:
        sql = self.get_attach_sql(options, credentials)
        if sql:
            con.execute(sql)
            return True
        return False

