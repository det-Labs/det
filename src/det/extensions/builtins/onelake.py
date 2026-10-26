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
                required=False,
                placeholder="Enterprise-Analytics",
                description="Microsoft Fabric workspace identifier.",
            ),
            ConnectorField(
                name="lakehouse",
                label="Lakehouse Name",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="BronzeLake",
                description="Target lakehouse container name.",
            ),
            ConnectorField(
                name="table",
                label="Delta Table Name",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="sales_transactions",
                description="Name of the Delta table in OneLake.",
            ),
            ConnectorField(
                name="path",
                label="Direct OneLake ABFSS URI (Optional)",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="abfss://workspace@onelake.dfs.fabric.microsoft.com/lakehouse.Lakehouse/Tables/table",
                description="Direct ABFSS URI. If supplied, overrides workspace/lakehouse/table.",
            ),
            ConnectorField(
                name="connection_string",
                label="Connection String",
                field_type=FieldType.PASSWORD,
                required=False,
                is_secret=True,
                description="Fabric / Azure Connection String (supports ${ONELAKE_CONN_STR}).",
            ),
            ConnectorField(
                name="tenant_id",
                label="Tenant ID (Entra ID)",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="00000000-0000-0000-0000-000000000000",
                description="Microsoft Entra Tenant ID for Fabric Service Principal.",
            ),
            ConnectorField(
                name="client_id",
                label="Client ID (Service Principal)",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="00000000-0000-0000-0000-000000000000",
                description="Fabric Service Principal App ID.",
            ),
            ConnectorField(
                name="client_secret",
                label="Client Secret",
                field_type=FieldType.PASSWORD,
                required=False,
                is_secret=True,
                description="Fabric Service Principal Client Secret (supports ${FABRIC_CLIENT_SECRET}).",
            ),
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        direct_path = options.get("path")
        if direct_path:
            return f"delta_scan('{str(direct_path).replace("'", "''")}')"

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
        from det.engine.session import load_or_install_extension
        load_or_install_extension(con, "azure")
        sql = f"SELECT 1 FROM ({self.get_read_sql(options)}) LIMIT 1"
        con.execute(sql).fetchall()
        return True

