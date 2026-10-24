"""Built-in connector for Amazon S3, MinIO, and Cloudflare R2 object stores."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class S3Connector(BaseConnector):
    """Connector reading objects from S3-compatible cloud storage."""

    key = "s3"
    label = "Amazon S3 / Object Store"
    description = "Query Parquet or CSV files stored in S3, MinIO, or Cloudflare R2."
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return cls._get_location_fields() + cls._get_auth_fields()

    @classmethod
    def _get_location_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="path",
                label="S3 URI or Glob",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="s3://my-bucket/lake/*.parquet",
                description="S3 URI path to object(s).",
            ),
            ConnectorField(
                name="region",
                label="AWS Region",
                field_type=FieldType.TEXT,
                required=False,
                default="us-east-1",
                placeholder="us-east-1",
                description="AWS region where the bucket resides.",
            ),
        ]

    @classmethod
    def _get_auth_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="key_id",
                label="Access Key ID",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="AKIA...",
                description="AWS Access Key (supports ${ENV_VAR}).",
            ),
            ConnectorField(
                name="secret_key",
                label="Secret Access Key",
                field_type=FieldType.PASSWORD,
                required=False,
                is_secret=True,
                description="AWS Secret Key (supports ${ENV_VAR}).",
            ),
            ConnectorField(
                name="endpoint",
                label="Custom Endpoint",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="minio.internal:9000",
                description="Custom endpoint URL for MinIO, Ceph, or Cloudflare R2.",
            ),
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        path = str(options.get("path", "")).replace("'", "''")
        if path.endswith((".csv", ".tsv")):
            return f"read_csv_auto('{path}')"
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

