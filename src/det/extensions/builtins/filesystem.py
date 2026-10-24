"""Built-in connectors for local filesystem formats (CSV, Parquet, JSON)."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class CSVConnector(BaseConnector):
    """Connector for local CSV and TSV files or globs."""

    key = "csv"
    label = "CSV Filesystem"
    description = "Read local CSV or TSV files directly into DuckDB."
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="path",
                label="File Path or Glob",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="data/input/*.csv",
                description="Local filesystem path or glob pattern.",
            ),
            ConnectorField(
                name="header",
                label="Has Header",
                field_type=FieldType.BOOLEAN,
                default=True,
                description="Whether first line contains column names.",
            ),
            ConnectorField(
                name="delimiter",
                label="Delimiter",
                field_type=FieldType.TEXT,
                default=",",
                placeholder=",",
                description="Field separator character.",
            ),
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        path = str(options.get("path", "")).replace("'", "''")
        header = "true" if options.get("header", True) else "false"
        delim = str(options.get("delimiter", ",")).replace("'", "''")
        return f"read_csv_auto('{path}', header={header}, delim='{delim}')"

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


class ParquetConnector(BaseConnector):
    """Connector for local Parquet files or columnar datasets."""

    key = "parquet"
    label = "Parquet Filesystem"
    description = "High-performance vectorized scanner for local Parquet files."
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="path",
                label="File Path or Glob",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="data/tables/*.parquet",
                description="Local path or glob pattern pointing to Parquet files.",
            )
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        path = str(options.get("path", "")).replace("'", "''")
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
        sql = f"SELECT 1 FROM ({self.get_read_sql(options)}) LIMIT 1"
        con.execute(sql).fetchall()
        return True


class JSONConnector(BaseConnector):
    """Connector for JSON and newline-delimited JSON (NDJSON) files."""

    key = "json"
    label = "JSON Filesystem"
    description = "Read JSON or NDJSON documents into structured DuckDB columns."
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="path",
                label="File Path or Glob",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="data/events/*.json",
                description="Local path to JSON or NDJSON files.",
            ),
            ConnectorField(
                name="format",
                label="JSON Format",
                field_type=FieldType.SELECT,
                default="auto",
                choices=["auto", "records", "array"],
                description="Format structure of JSON documents.",
            ),
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        path = str(options.get("path", "")).replace("'", "''")
        fmt = str(options.get("format", "auto")).replace("'", "''")
        return f"read_json_auto('{path}', format='{fmt}')"

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

