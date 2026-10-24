"""Built-in connector for MySQL databases."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class MySQLConnector(BaseConnector):
    """Connector attaching MySQL databases via DuckDB MySQL extension."""

    key = "mysql"
    label = "MySQL"
    description = "Attach a MySQL database server for federated queries."
    tier = ConnectionTier.DATABASE

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return cls._get_server_fields() + cls._get_auth_fields()

    @classmethod
    def _get_server_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="host",
                label="Host",
                field_type=FieldType.TEXT,
                required=True,
                default="localhost",
                placeholder="localhost",
                description="MySQL server hostname or IP.",
            ),
            ConnectorField(
                name="port",
                label="Port",
                field_type=FieldType.NUMBER,
                required=True,
                default=3306,
                placeholder="3306",
                description="MySQL port number.",
            ),
            ConnectorField(
                name="database",
                label="Database Name",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="app_db",
                description="Target MySQL database.",
            ),
        ]

    @classmethod
    def _get_auth_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="user",
                label="Username",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="root",
                description="MySQL user.",
            ),
            ConnectorField(
                name="password",
                label="Password",
                field_type=FieldType.PASSWORD,
                required=False,
                is_secret=True,
                description="Password credential.",
            ),
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        return ""

    def get_attach_sql(
        self, options: dict[str, Any], credentials: dict[str, Any]
    ) -> str | None:
        conn_str = self._compose_conn_str(options, credentials)
        escaped_str = conn_str.replace("'", "''")
        name_clause = f" AS {options['name']}" if "name" in options else ""
        return f"ATTACH '{escaped_str}'{name_clause} (TYPE MYSQL)"

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

    def _compose_conn_str(
        self, options: dict[str, Any], credentials: dict[str, Any]
    ) -> str:
        """Build MySQL connection parameter string."""
        source = {**options, **credentials}
        host = source.get("host", "localhost")
        port = source.get("port", 3306)
        dbname = source.get("database") or source.get("dbname", "")
        user = source.get("user", "root")
        password = source.get("password")

        parts = [f"host={host}", f"port={port}", f"database={dbname}", f"user={user}"]
        if password:
            parts.append(f"password={password}")
        return " ".join(parts)

