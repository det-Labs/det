"""Built-in connector for Delta Lake tables."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class DeltaLakeConnector(BaseConnector):
    """Connector scanning Linux Foundation Delta Lake tables."""

    key = "delta_lake"
    label = "Delta Lake"
    description = "Read ACID Delta Lake transaction logs and Parquet data files."
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="table_path",
                label="Delta Table Path",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="s3://lakehouse/delta/users/",
                description="Directory path containing _delta_log/ directory.",
            )
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        table_path = str(options.get("table_path", "")).replace("'", "''")
        return f"delta_scan('{table_path}')"

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

