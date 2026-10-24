"""Tests for built-in connector implementations and dynamic schema generation."""

import duckdb
from det.extensions.builtins.filesystem import CSVConnector, ParquetConnector, JSONConnector
from det.extensions.builtins.sqlite import SQLiteConnector
from det.extensions.builtins.postgres import PostgresConnector
from det.extensions.builtins.mysql import MySQLConnector
from det.extensions.builtins.mssql import MSSQLConnector
from det.extensions.builtins.httpfs import HTTPFSConnector
from det.extensions.builtins.s3 import S3Connector
from det.extensions.builtins.huggingface import HuggingFaceConnector
from det.extensions.builtins.iceberg import IcebergConnector
from det.extensions.builtins.delta_lake import DeltaLakeConnector
from det.extensions.builtins.onelake import OneLakeConnector
from det.extensions.registry import global_registry


def test_all_builtins_registered_in_global_registry() -> None:
    """Verify all 13 built-in connectors are automatically registered in global_registry."""
    expected_keys = {
        "csv", "parquet", "json", "sqlite", "postgres", "mysql",
        "mssql", "httpfs", "s3", "huggingface", "iceberg", "delta_lake", "onelake"
    }
    registered = set(global_registry.list_keys())
    assert expected_keys.issubset(registered)


def test_filesystem_connectors_sql_generation() -> None:
    """Verify SQL generation for CSV, Parquet, and JSON connectors."""
    csv_conn = CSVConnector()
    assert csv_conn.get_read_sql({"path": "data.csv", "header": True, "delimiter": ","}) == (
        "read_csv_auto('data.csv', header=true, delim=',')"
    )

    parquet_conn = ParquetConnector()
    assert parquet_conn.get_read_sql({"path": "data.parquet"}) == "read_parquet('data.parquet')"

    json_conn = JSONConnector()
    assert json_conn.get_read_sql({"path": "data.json", "format": "records"}) == (
        "read_json_auto('data.json', format='records')"
    )


def test_database_connectors_attach_sql() -> None:
    """Verify ATTACH SQL generation for SQLite, Postgres, MySQL, and MSSQL."""
    sqlite_conn = SQLiteConnector()
    assert sqlite_conn.get_attach_sql({"name": "my_sqlite", "path": "test.db", "read_only": True}, {}) == (
        "ATTACH 'test.db' AS my_sqlite (TYPE SQLITE, READ_ONLY)"
    )

    pg_conn = PostgresConnector()
    pg_sql = pg_conn.get_attach_sql(
        {"name": "my_pg", "host": "localhost", "port": 5432, "database": "app"},
        {"user": "pguser", "password": "secret"}
    )
    assert pg_sql == "ATTACH 'host=localhost port=5432 dbname=app user=pguser password=secret' AS my_pg (TYPE POSTGRES)"

    mysql_conn = MySQLConnector()
    mysql_sql = mysql_conn.get_attach_sql(
        {"name": "my_mysql", "host": "127.0.0.1", "port": 3306, "database": "orders"},
        {"user": "root"}
    )
    assert mysql_sql == "ATTACH 'host=127.0.0.1 port=3306 database=orders user=root' AS my_mysql (TYPE MYSQL)"

    mssql_conn = MSSQLConnector()
    mssql_sql = mssql_conn.get_attach_sql(
        {"name": "my_mssql", "host": "sqlsrv", "port": 1433, "database": "dw"},
        {"user": "sa", "password": "pass"}
    )
    assert mssql_sql == "ATTACH 'Server=sqlsrv,1433;Database=dw;User Id=sa;Password=pass;' AS my_mssql (TYPE MSSQL)"


def test_cloud_and_lakehouse_connectors_sql() -> None:
    """Verify SQL expressions for remote cloud and lakehouse sources."""
    httpfs_conn = HTTPFSConnector()
    assert httpfs_conn.get_read_sql({"url": "https://data.com/f.parquet", "format": "parquet"}) == (
        "read_parquet('https://data.com/f.parquet')"
    )

    s3_conn = S3Connector()
    assert s3_conn.get_read_sql({"path": "s3://b/f.parquet"}) == "read_parquet('s3://b/f.parquet')"

    hf_conn = HuggingFaceConnector()
    assert hf_conn.get_read_sql({"dataset": "fka/chatgpt-prompts", "split": "train"}) == (
        "read_parquet('https://huggingface.co/datasets/fka/chatgpt-prompts/resolve/main/data/train.parquet')"
    )

    iceberg_conn = IcebergConnector()
    assert iceberg_conn.get_read_sql({"metadata_file": "s3://lake/meta.json"}) == (
        "iceberg_scan('s3://lake/meta.json')"
    )

    delta_conn = DeltaLakeConnector()
    assert delta_conn.get_read_sql({"table_path": "s3://lake/delta_tbl"}) == (
        "delta_scan('s3://lake/delta_tbl')"
    )

    onelake_conn = OneLakeConnector()
    assert onelake_conn.get_read_sql({"workspace": "ws", "lakehouse": "lake", "table": "tbl"}) == (
        "delta_scan('abfss://ws@onelake.dfs.fabric.microsoft.com/lake.Lakehouse/Tables/tbl')"
    )


def test_connectors_expose_rich_ui_field_schemas() -> None:
    """Verify every connector defines declarative fields with labels and field types."""
    for conn_cls in global_registry.list_connectors():
        fields = conn_cls.get_fields()
        assert len(fields) > 0, f"Connector {conn_cls.key} has no fields defined!"
        for f in fields:
            assert f.name, f"Field in {conn_cls.key} has empty name"
            assert f.label, f"Field in {conn_cls.key} has empty label"
            assert f.field_type.value in {"text", "password", "number", "boolean", "select"}

