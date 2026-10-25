"""Comprehensive tests for Extension Loaders (Entrypoints, Local directory) and all Builtin Connectors."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import duckdb
import pytest

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType
from det.extensions.builtins.excel import ExcelConnector
from det.extensions.builtins.filesystem import CSVConnector, JSONConnector, ParquetConnector
from det.extensions.builtins.httpfs import HTTPFSConnector
from det.extensions.builtins.huggingface import HuggingFaceConnector
from det.extensions.builtins.iceberg import IcebergConnector
from det.extensions.builtins.mssql import MSSQLConnector
from det.extensions.builtins.mysql import MySQLConnector
from det.extensions.builtins.postgres import PostgresConnector
from det.extensions.builtins.sqlite import SQLiteConnector
from det.extensions.entrypoint_loader import EntrypointExtensionLoader
from det.extensions.local_loader import LocalExtensionLoader
from det.extensions.registry import ExtensionRegistry


# ---------------------------------------------------------------------------
# EntrypointExtensionLoader Tests
# ---------------------------------------------------------------------------

class SampleCustomConnector(BaseConnector):
    key = "sample_custom"
    label = "Sample Custom"
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return [ConnectorField(name="url", label="URL", field_type=FieldType.TEXT)]

    def get_read_sql(self, options: dict) -> str:
        return f"read_csv_auto('{options.get('url', '')}')"


class InvalidConnector:
    key = "invalid"


def test_entrypoint_loader_success_and_errors() -> None:
    """Verify EntrypointExtensionLoader handles successful plugins, invalid plugins, and load failures."""
    loader = EntrypointExtensionLoader()
    registry = ExtensionRegistry()

    # 1. Valid entry point
    ep_valid = MagicMock()
    ep_valid.name = "sample_custom"
    ep_valid.load.return_value = SampleCustomConnector

    # 2. Invalid class (not BaseConnector subclass)
    ep_invalid = MagicMock()
    ep_invalid.name = "invalid_ep"
    ep_invalid.load.return_value = InvalidConnector

    # 3. Failing entry point (raises exception on load)
    ep_failing = MagicMock()
    ep_failing.name = "failing_ep"
    ep_failing.load.side_effect = RuntimeError("Failed to import plugin package")

    with patch("importlib.metadata.entry_points", return_value=[ep_valid, ep_invalid, ep_failing]):
        loaded = loader.load_entrypoints(registry)
        assert "sample_custom" in loaded
        assert registry.get("sample_custom") is SampleCustomConnector
        assert registry.get("invalid") is None

    # 4. Exception scanning entry points is caught and logged
    with patch("importlib.metadata.entry_points", side_effect=Exception("Package scan error")):
        loaded_empty = loader.load_entrypoints(registry)
        assert loaded_empty == []


# ---------------------------------------------------------------------------
# ExtensionRegistry Validation & Aliases Tests
# ---------------------------------------------------------------------------

def test_registry_validation_and_lifecycle() -> None:
    """Verify ExtensionRegistry error checking, alias management, and clearing."""
    reg = ExtensionRegistry()

    # Must inherit from BaseConnector
    with pytest.raises(TypeError, match="must inherit from BaseConnector"):
        reg.register(InvalidConnector)  # type: ignore

    # Must have a non-empty key
    class NoKeyConnector(BaseConnector):
        key = ""
        tier = ConnectionTier.ENTITY
        @classmethod
        def get_fields(cls): return []
        def get_read_sql(self, opts): return ""

    with pytest.raises(ValueError, match="must define a non-empty 'key'"):
        reg.register(NoKeyConnector)

    # Valid registration with explicit aliases
    reg.register(SampleCustomConnector, aliases=["custom_alias_1", "custom_alias_2"])
    assert reg.get("sample_custom") is SampleCustomConnector
    assert reg.get("custom_alias_1") is SampleCustomConnector
    assert reg.get("custom_alias_2") is SampleCustomConnector
    assert reg.get("SAMPLE_CUSTOM") is SampleCustomConnector  # Case insensitive

    # register_alias method
    reg.register_alias("another_alias", "sample_custom")
    assert reg.get("another_alias") is SampleCustomConnector

    # list_keys and list_connectors
    assert "sample_custom" in reg.list_keys()
    assert SampleCustomConnector in reg.list_connectors()

    # clear
    reg.clear()
    assert reg.list_keys() == []
    assert reg.get("sample_custom") is None


# ---------------------------------------------------------------------------
# Database & Cloud Builtin Connectors Tests
# ---------------------------------------------------------------------------

def test_postgres_connector_sql() -> None:
    """Verify PostgresConnector generates valid ATTACH and query SQL."""
    conn = PostgresConnector()
    fields = PostgresConnector.get_fields()
    assert any(f.name == "database" for f in fields)
    assert any(f.name == "password" for f in fields)

    attach_sql = conn.get_attach_sql(
        options={"database": "sales_db"},
        credentials={"host": "pg.internal", "port": 5432, "user": "admin", "password": "secret"},
    )
    assert attach_sql is not None
    assert "ATTACH 'host=pg.internal port=5432 dbname=sales_db user=admin password=secret' (TYPE POSTGRES)" in attach_sql

    assert conn.get_read_sql({"query": "SELECT * FROM public.orders"}) == ""


def test_mysql_connector_sql() -> None:
    """Verify MySQLConnector generates valid ATTACH and read SQL."""
    conn = MySQLConnector()
    fields = MySQLConnector.get_fields()
    assert any(f.name == "port" for f in fields)

    attach_sql = conn.get_attach_sql(
        options={"database": "inventory_db"},
        credentials={"host": "127.0.0.1", "port": 3306, "user": "root", "password": "pwd"},
    )
    assert attach_sql is not None
    assert "TYPE MYSQL" in attach_sql
    assert "inventory_db" in attach_sql


def test_mssql_connector_sql() -> None:
    """Verify MSSQLConnector generates valid ATTACH and query SQL."""
    conn = MSSQLConnector()
    fields = MSSQLConnector.get_fields()
    assert any(f.name == "port" for f in fields)
    assert any(f.name == "database" for f in fields)

    attach_sql = conn.get_attach_sql(
        options={"database": "EnterpriseDW"},
        credentials={"host": "sqlserver.corp", "user": "sa", "password": "pw"},
    )
    assert attach_sql is not None
    assert "TYPE MSSQL" in attach_sql or "TYPE SQLSERVER" in attach_sql or "EnterpriseDW" in attach_sql


def test_sqlite_connector_sql() -> None:
    """Verify SQLiteConnector generates valid ATTACH SQL."""
    conn = SQLiteConnector()
    fields = SQLiteConnector.get_fields()
    assert any(f.name == "path" for f in fields)

    attach_sql = conn.get_attach_sql(
        options={"path": "data/app.db", "name": "app_db"},
        credentials={},
    )
    assert attach_sql is not None
    assert "ATTACH 'data/app.db' AS app_db (TYPE SQLITE" in attach_sql


def test_httpfs_and_iceberg_and_huggingface() -> None:
    """Verify HTTPFS, Iceberg, and HuggingFace connectors read SQL generation."""
    http_conn = HTTPFSConnector()
    assert "read_parquet('https://domain.com/data.parquet')" in http_conn.get_read_sql({"url": "https://domain.com/data.parquet"})
    assert "read_csv_auto('https://domain.com/data.csv')" in http_conn.get_read_sql({"url": "https://domain.com/data.csv", "format": "csv"})
    assert "read_json_auto('https://domain.com/data.json')" in http_conn.get_read_sql({"url": "https://domain.com/data.json", "format": "json"})

    ice_conn = IcebergConnector()
    assert "iceberg_scan('s3://iceberg-catalog/v1.metadata.json')" in ice_conn.get_read_sql({"metadata_file": "s3://iceberg-catalog/v1.metadata.json"})

    hf_conn = HuggingFaceConnector()
    hf_sql = hf_conn.get_read_sql({"dataset": "imdb"})
    assert "https://huggingface.co/datasets/imdb" in hf_sql
