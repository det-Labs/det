"""Built-in connector for Google Cloud Storage (GCS)."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class GCSConnector(BaseConnector):
    """Connector querying Parquet, Delta, or CSV files from Google Cloud Storage (gcs:// or gs://)."""

    key = "gcs"
    label = "Google Cloud Storage (GCS)"
    description = "Query Parquet, Delta Lake, or CSV files stored in Google Cloud Storage buckets."
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return cls._get_location_fields() + cls._get_auth_fields()

    @classmethod
    def _get_location_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="path",
                label="GCS URI or Glob",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="gcs://my-bucket/lake/*.parquet",
                description="GCS URI path (gcs://... or gs://...).",
            ),
            ConnectorField(
                name="endpoint",
                label="Custom Endpoint",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="storage.googleapis.com",
                description="Custom GCS endpoint URL if using local emulator or proxy.",
            ),
        ]

    @classmethod
    def _get_auth_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="key_id",
                label="HMAC Access Key ID",
                field_type=FieldType.TEXT,
                required=False,
                placeholder="GOOG...",
                description="GCS HMAC Key (supports ${GCS_KEY_ID}).",
            ),
            ConnectorField(
                name="secret_key",
                label="HMAC Secret Key",
                field_type=FieldType.PASSWORD,
                required=False,
                is_secret=True,
                description="GCS HMAC Secret Key (supports ${GCS_SECRET_KEY}).",
            ),
            ConnectorField(
                name="bearer_token",
                label="OAuth Bearer Token",
                field_type=FieldType.PASSWORD,
                required=False,
                is_secret=True,
                description="Google OAuth2 Bearer token (supports ${GCS_BEARER_TOKEN}).",
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
        load_or_install_extension(con, "httpfs")
        sql = f"SELECT 1 FROM ({self.get_read_sql(options)}) LIMIT 1"
        con.execute(sql).fetchall()
        return True

