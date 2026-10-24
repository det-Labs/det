"""Built-in connector for remote HTTP/HTTPS files."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class HTTPFSConnector(BaseConnector):
    """Connector streaming remote datasets directly over HTTP/HTTPS."""

    key = "httpfs"
    label = "HTTP / Web Dataset"
    description = "Stream remote Parquet, CSV, or JSON datasets directly over HTTP/HTTPS."
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="url",
                label="Dataset URL",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="https://example.com/data/export.parquet",
                description="Public or authenticated HTTPS URL.",
            ),
            ConnectorField(
                name="format",
                label="Data Format",
                field_type=FieldType.SELECT,
                default="parquet",
                choices=["parquet", "csv", "json"],
                description="Format of the remote dataset.",
            ),
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        url = str(options.get("url", "")).replace("'", "''")
        fmt = str(options.get("format", "parquet")).lower()
        if fmt == "csv":
            return f"read_csv_auto('{url}')"
        if fmt == "json":
            return f"read_json_auto('{url}')"
        return f"read_parquet('{url}')"

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

