"""Built-in connector for PostgreSQL databases."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class PostgresConnector(BaseConnector):
    """Connector attaching PostgreSQL databases via native DuckDB postgres scanner."""

    key = "postgres"
    label = "PostgreSQL"
    description = "Attach a remote PostgreSQL database with pushdown predicate support."
    tier = ConnectionTier.DATABASE

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return cls._get_network_fields() + cls._get_auth_fields()

    @classmethod
    def _get_network_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="host",
                label="Host",
                field_type=FieldType.TEXT,
                required=True,
                default="localhost",
                placeholder="localhost",
                description="Database hostname or IP address.",
            ),
            ConnectorField(
                name="port",
                label="Port",
                field_type=FieldType.NUMBER,
                required=True,
                default=5432,
                placeholder="5432",
                description="PostgreSQL port number.",
            ),
            ConnectorField(
                name="database",
                label="Database Name",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="production",
                description="Target database name.",
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
                placeholder="postgres",
                description="User login role.",
            ),
            ConnectorField(
                name="password",
                label="Password",
                field_type=FieldType.PASSWORD,
                required=False,
                is_secret=True,
                description="Authentication password (supports ${ENV_VAR}).",
            ),
            ConnectorField(
                name="schema",
                label="Default Schema",
                field_type=FieldType.TEXT,
                required=False,
                default="public",
                placeholder="public",
                description="Target PostgreSQL schema.",
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
        return f"ATTACH '{escaped_str}'{name_clause} (TYPE POSTGRES)"

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
        """Compose postgres connection parameter string."""
        source = {**options, **credentials}
        host = source.get("host", "localhost")
        port = source.get("port", 5432)
        dbname = source.get("database") or source.get("dbname", "postgres")
        user = source.get("user", "postgres")
        password = source.get("password")

        parts = [f"host={host}", f"port={port}", f"dbname={dbname}", f"user={user}"]
        if password:
            parts.append(f"password={password}")
        return " ".join(parts)

