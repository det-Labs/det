"""Built-in connector for Microsoft SQL Server."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class MSSQLConnector(BaseConnector):
    """Connector attaching Microsoft SQL Server databases."""

    key = "mssql"
    label = "Microsoft SQL Server"
    description = "Connect to Microsoft SQL Server via ODBC or attached connection."
    tier = ConnectionTier.DATABASE

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return cls._get_server_fields() + cls._get_auth_fields()

    @classmethod
    def _get_server_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="host",
                label="Server Host",
                field_type=FieldType.TEXT,
                required=True,
                default="localhost",
                placeholder="sqlserver.corp",
                description="SQL Server host address.",
            ),
            ConnectorField(
                name="port",
                label="Port",
                field_type=FieldType.NUMBER,
                required=True,
                default=1433,
                placeholder="1433",
                description="MSSQL port.",
            ),
            ConnectorField(
                name="database",
                label="Database Name",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="analytics",
                description="Database catalog name.",
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
                placeholder="sa",
                description="Database login user.",
            ),
            ConnectorField(
                name="password",
                label="Password",
                field_type=FieldType.PASSWORD,
                required=False,
                is_secret=True,
                description="Authentication password.",
            ),
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        return ""

    def get_attach_sql(
        self, options: dict[str, Any], credentials: dict[str, Any]
    ) -> str | None:
        source = {**options, **credentials}
        host = source.get("host", "localhost")
        port = source.get("port", 1433)
        db = source.get("database", "master")
        user = source.get("user", "")
        pwd = source.get("password", "")

        conn_str = f"Server={host},{port};Database={db};User Id={user};Password={pwd};"
        escaped_str = conn_str.replace("'", "''")
        name_clause = f" AS {options['name']}" if "name" in options else ""
        return f"ATTACH '{escaped_str}'{name_clause} (TYPE MSSQL)"

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

