"""Comprehensive scenario and edge-case unit tests for all built-in connectors and loaders."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import duckdb
import pytest

from det.extensions.builtins.azure import AzureConnector
from det.extensions.builtins.delta_lake import DeltaLakeConnector
from det.extensions.builtins.excel import ExcelConnector
from det.extensions.builtins.filesystem import (
    CSVConnector,
    JSONConnector,
    ParquetConnector,
)
from det.extensions.builtins.gcs import GCSConnector
from det.extensions.builtins.httpfs import HTTPFSConnector
from det.extensions.builtins.huggingface import HuggingFaceConnector
from det.extensions.builtins.iceberg import IcebergConnector
from det.extensions.builtins.mssql import MSSQLConnector
from det.extensions.builtins.mysql import MySQLConnector
from det.extensions.builtins.onelake import OneLakeConnector
from det.extensions.builtins.postgres import PostgresConnector
from det.extensions.builtins.s3 import S3Connector
from det.extensions.builtins.sqlite import SQLiteConnector
from det.extensions.local_loader import LocalExtensionLoader
from det.extensions.registry import ExtensionRegistry
from det.runner import PipelineRunner
from det.models.base import DestinationSpec, MaterializationType, WriteMode
from det.models.definition import ModelConfig, ModelDefinition
from det.engine.facade import EngineFacade


def test_filesystem_connectors_get_sql_and_test_connection(tmp_path: Path):
    """Verify CSV, Parquet, and JSON connectors test_connection and SQL generation."""
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("id,val\n1,alpha\n2,beta\n", encoding="utf-8")
    parquet_file = tmp_path / "data.parquet"
    json_file = tmp_path / "data.json"
    json_file.write_text('[{"id": 1, "val": "alpha"}]\n', encoding="utf-8")

    con = duckdb.connect()
    con.execute(f"COPY (SELECT 1 AS id, 'alpha' AS val) TO '{parquet_file.as_posix()}' (FORMAT PARQUET)")

    # CSV
    csv_conn = CSVConnector()
    assert csv_conn.get_attach_sql({}, {}) is None
    csv_read = csv_conn.get_read_sql({"path": str(csv_file), "header": True, "delimiter": ","})
    assert "read_csv_auto" in csv_read
    assert csv_conn.test_connection(con, {"path": str(csv_file)}, {}) is True

    # Parquet
    parquet_conn = ParquetConnector()
    assert parquet_conn.get_attach_sql({}, {}) is None
    p_read = parquet_conn.get_read_sql({"path": str(parquet_file)})
    assert "read_parquet" in p_read
    assert parquet_conn.test_connection(con, {"path": str(parquet_file)}, {}) is True

    # JSON
    json_conn = JSONConnector()
    assert json_conn.get_attach_sql({}, {}) is None
    j_read = json_conn.get_read_sql({"path": str(json_file), "format": "auto"})
    assert "read_json_auto" in j_read
    assert json_conn.test_connection(con, {"path": str(json_file)}, {}) is True

    con.close()


def test_cloud_connectors_get_read_sql_all_formats():
    """Verify get_read_sql across different extensions (.delta, .csv, .tsv, .json, .ndjson, .parquet)."""
    connectors = [AzureConnector(), GCSConnector(), S3Connector()]
    for conn in connectors:
        assert conn.get_attach_sql({}, {}) is None
        assert "delta_scan" in conn.get_read_sql({"path": "s3://bkt/table.delta"})
        assert "delta_scan" in conn.get_read_sql({"path": "abfss://c@a.dfs/tbl/_delta_log"})
        assert "read_csv_auto" in conn.get_read_sql({"path": "s3://bkt/data.csv"})
        assert "read_csv_auto" in conn.get_read_sql({"path": "gs://bkt/data.tsv"})
        assert "read_json_auto" in conn.get_read_sql({"path": "s3://bkt/data.json"})
        assert "read_json_auto" in conn.get_read_sql({"path": "s3://bkt/data.ndjson"})
        assert "read_parquet" in conn.get_read_sql({"path": "s3://bkt/data.parquet"})
        assert "read_parquet" in conn.get_read_sql({"path": "s3://bkt/data_unknown"})


def test_cloud_connectors_test_connection_mocks():
    """Verify test_connection executes safely on Azure, GCS, S3, OneLake, and Delta Lake connectors."""
    mock_con = MagicMock(spec=duckdb.DuckDBPyConnection)
    mock_con.execute.return_value.fetchall.return_value = [(1,)]

    # Azure
    azure = AzureConnector()
    assert azure.test_connection(mock_con, {"path": "abfss://c@a.dfs/data.parquet"}, {}) is True
    mock_con.load_extension.assert_called_with("azure")

    # GCS
    gcs = GCSConnector()
    assert gcs.test_connection(mock_con, {"path": "gs://bkt/data.parquet"}, {}) is True
    mock_con.load_extension.assert_called_with("httpfs")

    # S3
    s3 = S3Connector()
    assert s3.test_connection(mock_con, {"path": "s3://bkt/data.parquet"}, {}) is True

    # OneLake
    onelake = OneLakeConnector()
    assert onelake.get_attach_sql({}, {}) is None
    assert onelake.test_connection(mock_con, {"workspace": "ws", "lakehouse": "lh", "table": "tbl"}, {}) is True

    # Delta Lake
    delta = DeltaLakeConnector()
    assert delta.get_attach_sql({}, {}) is None
    assert delta.test_connection(mock_con, {"path": "C:\\data\\delta_tbl"}, {}) is True

    # Extension load failure resilience
    failing_con = MagicMock(spec=duckdb.DuckDBPyConnection)
    failing_con.load_extension.side_effect = Exception("Extension not found")
    failing_con.execute.return_value.fetchall.return_value = [(1,)]
    assert azure.test_connection(failing_con, {"path": "abfss://c@a.dfs/data.parquet"}, {}) is True
    assert gcs.test_connection(failing_con, {"path": "gs://bkt/data.parquet"}, {}) is True
    assert delta.test_connection(failing_con, {"path": "delta_tbl"}, {}) is True


def test_database_connectors_test_connection():
    """Verify test_connection on SQLite, Postgres, MySQL, MSSQL, HTTPFS, Iceberg, Excel, HuggingFace."""
    mock_con = MagicMock(spec=duckdb.DuckDBPyConnection)
    mock_con.execute.return_value.fetchall.return_value = [(1,)]

    assert SQLiteConnector().test_connection(mock_con, {"path": "test.db"}, {}) is True
    assert PostgresConnector().test_connection(mock_con, {"database": "db"}, {}) is True
    assert MySQLConnector().test_connection(mock_con, {"database": "db"}, {}) is True
    assert MSSQLConnector().test_connection(mock_con, {"database": "db"}, {}) is True
    assert HTTPFSConnector().test_connection(mock_con, {"url": "https://example.com/data.parquet"}, {}) is True
    assert IcebergConnector().test_connection(mock_con, {"metadata_location": "s3://bkt/v1.metadata.json"}, {}) is True
    assert HuggingFaceConnector().test_connection(mock_con, {"dataset": "imdb"}, {}) is True

    excel = ExcelConnector()
    assert excel.test_connection(mock_con, {"path": "data.xlsx"}, {}) is True


def test_local_extension_loader_edge_cases(tmp_path: Path):
    """Test LocalExtensionLoader when path is missing, ignores __init__, or fails registration."""
    loader = LocalExtensionLoader()
    reg = ExtensionRegistry()

    # Missing directory
    assert loader.load_directory(tmp_path / "non_existent", reg) == []

    # Directory with __init__.py and empty files
    ext_dir = tmp_path / "extensions"
    ext_dir.mkdir()
    (ext_dir / "__init__.py").write_text("# Empty init", encoding="utf-8")
    (ext_dir / "valid_ext.py").write_text(
        """from det.extensions.base import BaseConnector, ConnectionTier
class DummyCustom(BaseConnector):
    key = "dummy_custom"
    label = "Dummy"
    description = "Test"
    tier = ConnectionTier.ENTITY
    def get_read_sql(self, options): return "SELECT 1"
    def get_attach_sql(self, options, creds): return None
    def test_connection(self, con, options, creds): return True
""",
        encoding="utf-8",
    )

    loaded = loader.load_directory(ext_dir, reg)
    assert "dummy_custom" in loaded
    assert reg.get("dummy_custom") is not None

    # Load file with invalid module spec
    with patch("importlib.util.spec_from_file_location", return_value=None):
        keys = loader.load_file(ext_dir / "valid_ext.py", reg)
        assert keys == []

    # Load file where registry.register raises an error
    with patch.object(reg, "register", side_effect=Exception("Registration conflict")):
        keys = loader.load_file(ext_dir / "valid_ext.py", reg)
        assert keys == []


def test_runner_delta_import_error(tmp_path: Path):
    """Verify PipelineRunner._export_to_delta raises user-friendly RuntimeError when deltalake missing."""
    engine = EngineFacade()
    runner = PipelineRunner(engine)
    con = engine.session

    with patch.dict("sys.modules", {"deltalake": None}):
        with pytest.raises(RuntimeError, match="Delta Lake export requires the 'deltalake' package"):
            runner._export_to_delta(con, "some_table", str(tmp_path / "delta_table"))
    engine.close()


def test_runner_append_to_database_table():
    """Verify PipelineRunner executes INSERT INTO when mode is WriteMode.APPEND to a target table."""
    engine = EngineFacade()
    runner = PipelineRunner(engine)
    con = engine.session

    con.execute("CREATE TABLE staging_orders (id INTEGER, amount DOUBLE)")
    con.execute("CREATE TABLE orders_mart (id INTEGER, amount DOUBLE)")
    con.execute("INSERT INTO orders_mart VALUES (1, 100.0)")

    model = ModelDefinition(
        name="staging_orders",
        compiled_sql="SELECT 2 AS id, 250.0 AS amount",
        config=ModelConfig(
            materialized=MaterializationType.TABLE,
            destinations=[DestinationSpec(target="orders_mart", mode=WriteMode.APPEND)],
        ),
    )

    runner._execute_single_model(con, model)

    rows = con.execute("SELECT * FROM orders_mart ORDER BY id").fetchall()
    assert rows == [(1, 100.0), (2, 250.0)]
    engine.close()


def test_runner_skips_disabled_model():
    """Verify runner skips models when enabled=False in config."""
    from det.models.dag import ModelDAG
    engine = EngineFacade()
    runner = PipelineRunner(engine)

    dag = ModelDAG()
    disabled_model = ModelDefinition(
        name="disabled_model",
        compiled_sql="SELECT 1/0",  # would fail if executed
        config=ModelConfig(enabled=False),
    )
    dag.add_model(disabled_model)

    report = runner.run_dag(dag)
    assert report.is_successful is True
    assert report.total_models == 0
    engine.close()
