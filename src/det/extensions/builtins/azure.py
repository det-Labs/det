"""Built-in connector for Microsoft Azure Blob Storage and Azure Data Lake Storage (ADLS Gen2)."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class AzureConnector(BaseConnector):
    """Connector querying Parquet, Delta, or CSV files from Azure Storage (azure:// or abfss://)."""

    key = "azure"
    label = "Azure Blob / ADLS Gen2"
    description = "Query Parquet, Delta Lake, or CSV files from Azure Blob Storage or ADLS Gen2."
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return cls._get_location_fields() + cls._get_auth_fields()

    @classmethod
    def _get_location_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="path",
                label="Azure Storage URI",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="azure://mycontainer/data/*.parquet",
                description="Azure URI (e.g. azure://<container>/path or abfss://<container>@<account>.dfs.core.windows.net/path).",
            ),
            ConnectorField(
                name="account_name",
                label="Storage Account Name",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="mystorageaccount",
                description="Azure Storage Account identifier.",
            ),
        ]

    @classmethod
    def _get_auth_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="connection_string",
                label="Connection String",
                field_type=FieldType.PASSWORD,
                required=False,
                is_secret=True,
                description="Azure Storage Connection String (supports ${AZURE_STORAGE_CONNECTION_STRING}).",
            ),
            ConnectorField(
                name="tenant_id",
                label="Tenant ID (Entra ID / SP)",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="00000000-0000-0000-0000-000000000000",
                description="Azure AD Tenant ID for Service Principal authentication.",
            ),
            ConnectorField(
                name="client_id",
                label="Client ID (Service Principal)",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="00000000-0000-0000-0000-000000000000",
                description="Azure Service Principal Application (Client) ID.",
            ),
            ConnectorField(
                name="client_secret",
                label="Client Secret",
                field_type=FieldType.PASSWORD,
                required=False,
                is_secret=True,
                description="Azure Service Principal Client Secret (supports ${AZURE_CLIENT_SECRET}).",
            ),
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        path = str(options.get("path", "")).replace("'", "''")
        if path.endswith(".delta") or "/_delta_log" in path:
            return f"delta_scan('{path}')"
        if path.endswith((".csv", ".tsv")):
            return f"read_csv_auto('{path}')"
        if path.endswith((".json", ".ndjson")):
            return f"read_json_auto('{path}')"
        return f"read_parquet('{path}')"

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

