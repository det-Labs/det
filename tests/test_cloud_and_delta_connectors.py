"""Comprehensive test suite for Multi-Cloud Connectors (S3, Azure, OneLake, GCS) and Delta Lake write/read."""

from pathlib import Path
import duckdb
import pytest

from det.catalog.base import ConnectionTier
from det.catalog.definitions import ConnectionDefinition
from det.catalog.tester import ConnectionTester
from det.engine.mounter import CatalogMounter
from det.engine.secrets import SecretResolver
from det.extensions.builtins.azure import AzureConnector
from det.extensions.builtins.delta_lake import DeltaConnector, DeltaLakeConnector
from det.extensions.builtins.gcs import GCSConnector
from det.extensions.builtins.onelake import OneLakeConnector
from det.extensions.builtins.s3 import S3Connector
from det.extensions.registry import global_registry
from det.models.base import DestinationSpec, MaterializationType, WriteMode
from det.models.definition import ModelConfig, ModelDefinition
from det.runner import PipelineRunner


def test_builtin_cloud_connectors_registered() -> None:
    """Verify all cloud and delta connectors are registered in global registry."""
    schemas = {s["key"]: s for s in global_registry.list_schemas()}
    assert "s3" in schemas
    assert "azure" in schemas
    assert "gcs" in schemas
    assert "onelake" in schemas
    assert "delta_lake" in schemas
    # Both canonical key and alias resolve to DeltaLakeConnector
    assert global_registry.get("delta") is not None
    assert global_registry.get("delta_lake") is not None

    # Verify field definitions
    assert any(f["name"] == "session_token" for f in schemas["s3"]["fields"])
    assert any(f["name"] == "connection_string" for f in schemas["azure"]["fields"])
    assert any(f["name"] == "key_id" for f in schemas["gcs"]["fields"])
    assert any(f["name"] == "workspace" for f in schemas["onelake"]["fields"])


def test_s3_secret_generation_and_read_sql() -> None:
    """Verify S3 connection secret generation and mount expression."""
    conn = ConnectionDefinition(
        name="raw_s3_orders",
        type="s3",
        tier=ConnectionTier.ENTITY,
        options={"path": "s3://corp-lake/orders/*.parquet", "region": "us-west-2"},
        credentials={"key_id": "AKIA_TEST", "secret_key": "SEC_TEST_123"},
    )
    secret_sql = conn.get_secret_sql()
    assert secret_sql is not None
    assert "CREATE OR REPLACE TEMPORARY SECRET sec_raw_s3_orders" in secret_sql
    assert "TYPE S3" in secret_sql
    assert "KEY_ID 'AKIA_TEST'" in secret_sql
    assert "SECRET 'SEC_TEST_123'" in secret_sql
    assert "REGION 'us-west-2'" in secret_sql

    mount_sql = conn.get_mount_sql()
    assert mount_sql == "CREATE OR REPLACE VIEW raw_s3_orders AS SELECT * FROM read_parquet('s3://corp-lake/orders/*.parquet')"


def test_azure_secret_generation_connection_string_and_sp() -> None:
    """Verify Azure secret SQL for Connection String and Service Principal modes."""
    # 1. Connection string mode
    conn_cs = ConnectionDefinition(
        name="adls_sales",
        type="azure",
        tier=ConnectionTier.ENTITY,
        options={"path": "abfss://sales@acct.dfs.core.windows.net/data.parquet"},
        credentials={"connection_string": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=abc==;"},
    )
    sec_sql = conn_cs.get_secret_sql()
    assert sec_sql is not None
    assert "TYPE AZURE" in sec_sql
    assert "CONNECTION_STRING 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=abc==;'" in sec_sql

    # 2. Service principal mode
    conn_sp = ConnectionDefinition(
        name="adls_sp",
        type="azure",
        tier=ConnectionTier.ENTITY,
        options={"path": "azure://container/folder/*.parquet", "account_name": "acct"},
        credentials={
            "tenant_id": "0000-1111",
            "client_id": "2222-3333",
            "client_secret": "super_secret_sp",
        },
    )
    sec_sp_sql = conn_sp.get_secret_sql()
    assert sec_sp_sql is not None
    assert "PROVIDER SERVICE_PRINCIPAL" in sec_sp_sql
    assert "TENANT_ID '0000-1111'" in sec_sp_sql
    assert "CLIENT_ID '2222-3333'" in sec_sp_sql
    assert "CLIENT_SECRET 'super_secret_sp'" in sec_sp_sql
    assert "ACCOUNT_NAME 'acct'" in sec_sp_sql


def test_onelake_uri_resolution_and_secret() -> None:
    """Verify Fabric OneLake Delta table URI generation and secret SQL."""
    conn_ol = ConnectionDefinition(
        name="fabric_lakehouse",
        type="onelake",
        tier=ConnectionTier.ENTITY,
        options={
            "workspace": "Finance_WS",
            "lakehouse": "SilverLake",
            "table": "gl_entries",
        },
        credentials={"connection_string": "AccountName=fabrictest;AccountKey=key=="},
    )
    sec_sql = conn_ol.get_secret_sql()
    assert sec_sql is not None
    assert "TYPE AZURE" in sec_sql
    assert "CONNECTION_STRING 'AccountName=fabrictest;AccountKey=key=='" in sec_sql

    mount_sql = conn_ol.get_mount_sql()
    expected_uri = "abfss://Finance_WS@onelake.dfs.fabric.microsoft.com/SilverLake.Lakehouse/Tables/gl_entries"
    assert mount_sql == f"CREATE OR REPLACE VIEW fabric_lakehouse AS SELECT * FROM delta_scan('{expected_uri}')"


def test_gcs_hmac_secret_generation() -> None:
    """Verify Google Cloud Storage HMAC secret generation."""
    conn_gcs = ConnectionDefinition(
        name="gcs_telemetry",
        type="gcs",
        tier=ConnectionTier.ENTITY,
        options={"path": "gs://my-bucket/events/*.parquet"},
        credentials={"key_id": "GOOG123456", "secret_key": "gcs_secret_val"},
    )
    sec_sql = conn_gcs.get_secret_sql()
    assert sec_sql is not None
    assert "CREATE OR REPLACE TEMPORARY SECRET sec_gcs_telemetry" in sec_sql
    assert "TYPE GCS" in sec_sql
    assert "KEY_ID 'GOOG123456'" in sec_sql
    assert "SECRET 'gcs_secret_val'" in sec_sql


def test_delta_lake_scan_mounting(tmp_path: Path) -> None:
    """Verify local Delta table read mounting with delta_scan."""
    delta_dir = tmp_path / "delta_customers"
    conn_delta = ConnectionDefinition(
        name="delta_customers",
        type="delta",
        tier=ConnectionTier.ENTITY,
        options={"path": str(delta_dir)},
    )
    mount_sql = conn_delta.get_mount_sql()
    normalized_path = str(delta_dir).replace("\\", "/")
    assert mount_sql == f"CREATE OR REPLACE VIEW delta_customers AS SELECT * FROM delta_scan('{normalized_path}')"


def test_catalog_mounter_executes_secrets_in_duckdb() -> None:
    """Verify CatalogMounter executes generated secrets in DuckDB without error."""
    con = duckdb.connect()
    mounter = CatalogMounter()

    conn = ConnectionDefinition(
        name="my_s3_source",
        type="s3",
        tier=ConnectionTier.ENTITY,
        options={"query": "SELECT 1 AS val", "region": "eu-central-1"},
        credentials={"key_id": "AK_TEST", "secret_key": "SK_TEST"},
    )

    mounter.mount_item(con, conn)

    secrets = con.execute("SELECT name, type, provider FROM duckdb_secrets() WHERE name = 'sec_my_s3_source'").fetchall()
    assert len(secrets) == 1
    assert secrets[0][0] == "sec_my_s3_source"
    assert secrets[0][1] == "s3"


def test_delta_lake_write_and_read_cycle(tmp_path: Path) -> None:
    """End-to-end test: PipelineRunner exports model to Delta Lake, then mounts and queries it."""
    con = duckdb.connect()
    delta_out_dir = tmp_path / "egress_delta"

    # Setup source data
    con.execute("CREATE TABLE staging_metrics AS SELECT 1 AS id, 'CPU' AS metric, 95.5 AS value UNION ALL SELECT 2, 'RAM', 82.1;")

    # Define model with delta destination
    model = ModelDefinition(
        name="staging_metrics",
        compiled_sql="SELECT * FROM staging_metrics",
        config=ModelConfig(
            materialized=MaterializationType.TABLE,
            destinations=[
                DestinationSpec(
                    target="delta_metrics",
                    path=str(delta_out_dir),
                    format="delta",
                    mode=WriteMode.REPLACE,
                )
            ],
        ),
    )

    runner = PipelineRunner(workspace_root=tmp_path)
    runner._publish_destinations(con, model)

    # 1. Verify Delta Lake structure was created
    assert delta_out_dir.exists()
    assert (delta_out_dir / "_delta_log").exists()
    assert any(p.suffix == ".parquet" for p in delta_out_dir.glob("*.parquet"))

    # 2. Mount exported Delta table using det's ConnectionDefinition
    delta_conn = ConnectionDefinition(
        name="delta_metrics_view",
        type="delta",
        tier=ConnectionTier.ENTITY,
        options={"path": str(delta_out_dir)},
    )
    mounter = CatalogMounter()
    mounter.mount_item(con, delta_conn)

    # 3. Query through delta_scan view and verify contents
    res = con.execute("SELECT id, metric, value FROM delta_metrics_view ORDER BY id").fetchall()
    assert len(res) == 2
    assert res[0][0] == 1
    assert res[0][1] == "CPU"
    assert float(res[0][2]) == 95.5
    assert res[1][0] == 2
    assert res[1][1] == "RAM"
    assert float(res[1][2]) == 82.1


def test_connection_tester_with_delta_table(tmp_path: Path) -> None:
    """Verify ConnectionTester probes local Delta Lake table successfully."""
    con = duckdb.connect()
    delta_dir = tmp_path / "health_delta"

    # Write a quick delta table
    from deltalake import write_deltalake
    con.execute("CREATE TABLE test_data AS SELECT 42 AS num, 'ok' AS status;")
    tbl = con.sql("SELECT * FROM test_data").to_arrow_table()
    write_deltalake(str(delta_dir), tbl)

    # Probe with ConnectionTester
    conn_def = ConnectionDefinition(
        name="probe_delta",
        type="delta",
        tier=ConnectionTier.ENTITY,
        options={"path": str(delta_dir)},
    )
    tester = ConnectionTester()
    result = tester.test_connection(con, conn_def)

    assert result.is_healthy
    assert result.latency_ms >= 0
    assert result.error_message is None
