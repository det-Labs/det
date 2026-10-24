"""Built-in connector for Apache Iceberg tables."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class IcebergConnector(BaseConnector):
    """Connector scanning Apache Iceberg tables and metadata."""

    key = "iceberg"
    label = "Apache Iceberg"
    description = "Vectorized scanner for Apache Iceberg metadata and data files."
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="metadata_file",
                label="Iceberg Metadata Path",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="s3://lakehouse/table/metadata/v1.metadata.json",
                description="Path to Iceberg metadata JSON file.",
            )
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        meta_path = str(options.get("metadata_file", "")).replace("'", "''")
        return f"iceberg_scan('{meta_path}')"

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

