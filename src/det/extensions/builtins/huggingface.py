"""Built-in connector for Hugging Face open datasets."""

from typing import Any
import duckdb

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType


class HuggingFaceConnector(BaseConnector):
    """Connector streaming Hugging Face datasets directly into DuckDB."""

    key = "huggingface"
    label = "Hugging Face Datasets"
    description = "Stream open-access or private Hugging Face tabular datasets via HTTPFS."
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="dataset",
                label="Dataset Identifier",
                field_type=FieldType.TEXT,
                required=True,
                placeholder="fka/awesome-chatgpt-prompts",
                description="Hugging Face repo repository ID.",
            ),
            ConnectorField(
                name="split",
                label="Split Name",
                field_type=FieldType.TEXT,
                required=False,
                default="train",
                placeholder="train",
                description="Dataset split name (e.g. train, test, validation).",
            ),
            ConnectorField(
                name="token",
                label="HF Access Token",
                field_type=FieldType.PASSWORD,
                required=False,
                is_secret=True,
                description="Personal access token for gated or private datasets.",
            ),
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        dataset = str(options.get("dataset", "")).strip("/")
        split = str(options.get("split", "train"))
        # Standard Hugging Face direct parquet resolution URL
        hf_url = f"https://huggingface.co/datasets/{dataset}/resolve/main/data/{split}.parquet"
        escaped_url = hf_url.replace("'", "''")
        return f"read_parquet('{escaped_url}')"

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

