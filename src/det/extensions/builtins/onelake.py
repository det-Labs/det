"""Built-in connector for Microsoft Fabric OneLake."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class OneLakeConnector(BaseConnector):
    """Connector reading Microsoft Fabric OneLake Delta tables."""

    key = "onelake"
    label = "Microsoft Fabric OneLake"
    description = "Read Lakehouse Delta tables directly from Microsoft Fabric OneLake."
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="workspace",
                label="Fabric Workspace Name",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="Enterprise-Analytics",
                description="Microsoft Fabric workspace identifier.",
            ),
            ConnectorField(
                name="lakehouse",
                label="Lakehouse Name",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="BronzeLake",
                description="Target lakehouse container name.",
            ),
            ConnectorField(
                name="table",
                label="Delta Table Name",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="sales_transactions",
                description="Name of the Delta table in OneLake.",
            ),
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        workspace = str(options.get("workspace", "")).replace("'", "''")
        lakehouse = str(options.get("lakehouse", "")).replace("'", "''")
        table = str(options.get("table", "")).replace("'", "''")
        uri = (
            f"abfss://{workspace}@onelake.dfs.fabric.microsoft.com/"
            f"{lakehouse}.Lakehouse/Tables/{table}"
        )
        return f"delta_scan('{uri}')"

    def get_attach_sql(
        self, options: dict[str, Any], credentials: dict[str, Any]
    ) -> str | None:
        return None

    def test_connection(
        self,
        con: duckdb.DuckDBPyConnection,
        options: dict[str, Any],
        credentials: dict[str, Any],
    ) -> bool:
        sql = f"SELECT 1 FROM ({self.get_read_sql(options)}) LIMIT 1"
        con.execute(sql).fetchall()
        return True

