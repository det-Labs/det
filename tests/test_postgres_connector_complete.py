"""Complete automated test suite for PostgreSQL database connector."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from det.catalog import CatalogService
from det.catalog import config as catalog_config
from det.catalog.store import read_catalog_yaml
from det.connectors import get_connector
from det.connectors.databases.postgres_connector import (
    PostgresConnector,
    map_postgres_type_to_standard,
)
from det.connectors.errors import (
    ConnectorValidationError,
    SchemaInferenceError,
)
from det.gui import server


@pytest.fixture(autouse=True)
def isolate_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".det"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    conn_path = config_dir / "connections.yaml"
    monkeypatch.setattr(catalog_config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(catalog_config, "CONFIG_FILE", config_path)
    from det.connectors import connections
    monkeypatch.setattr(connections, "_custom_connections_path", conn_path)
    server.set_service(None)
    yield
    server.set_service(None)


def test_postgres_connector_registration():
    connector = get_connector("postgres")
    assert isinstance(connector, PostgresConnector)
    assert connector.id == "postgres"
    assert connector.name == "PostgreSQL"
    assert connector.group == "Databases"


def test_postgres_type_mapping():
    assert map_postgres_type_to_standard("integer") == "Int64"
    assert map_postgres_type_to_standard("bigint") == "Int64"
    assert map_postgres_type_to_standard("serial") == "Int64"
    assert map_postgres_type_to_standard("numeric") == "Float64"
    assert map_postgres_type_to_standard("double precision") == "Float64"
    assert map_postgres_type_to_standard("character varying") == "String"
    assert map_postgres_type_to_standard("text") == "String"
    assert map_postgres_type_to_standard("boolean") == "Boolean"
    assert map_postgres_type_to_standard("timestamp with time zone") == "DateTime"
    assert map_postgres_type_to_standard("date") == "DateTime"
    assert map_postgres_type_to_standard("jsonb") == "JSON"
    assert map_postgres_type_to_standard("bytea") == "Binary"
    assert map_postgres_type_to_standard("uuid") == "String"


def test_postgres_uri_and_parameter_construction():
    connector = PostgresConnector()

    params = connector._build_connection_params(
        source_config={"host": "pg.internal.net", "port": 5433, "database": "warehouse_db", "sslmode": "require"},
        credentials={"username": "data_eng", "password": "Complex@Password#123!"},
    )
    assert params["host"] == "pg.internal.net"
    assert params["port"] == 5433
    assert params["database"] == "warehouse_db"
    assert params["user"] == "data_eng"
    assert params["password"] == "Complex@Password#123!"
    assert params["sslmode"] == "require"

    uri = connector._get_connection_uri(params)
    assert uri.startswith("postgresql://data_eng:")
    assert "pg.internal.net:5433/warehouse_db?sslmode=require" in uri


@patch.object(PostgresConnector, "_connect")
def test_postgres_connection_testing(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    # Mock cursor context manager and query returns: [table_count]
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = [14]
    mock_connect.return_value = mock_conn

    connector = PostgresConnector()

    # Success case
    res = connector.test_connection(
        source_config={"host": "localhost", "database": "test_db"},
        credentials={"username": "postgres", "password": "secret"},
    )
    assert res.success is True
    assert "Connected successfully" in res.message
    assert res.details.get("table_count") == 14

    # Failure case
    mock_connect.side_effect = Exception("Connection refused to host:5432")
    fail_res = connector.test_connection(
        source_config={"host": "localhost", "database": "test_db"},
    )
    assert fail_res.success is False
    assert "Connection refused" in fail_res.message


@patch.object(PostgresConnector, "_connect")
def test_postgres_object_discovery(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    # Return table_schema, table_name, table_type
    mock_cur.fetchall.return_value = [
        ("public", "customers", "BASE TABLE"),
        ("public", "orders", "BASE TABLE"),
        ("analytics", "monthly_mrr", "VIEW"),
    ]
    mock_connect.return_value = mock_conn

    connector = PostgresConnector()
    objects = connector.discover_objects(
        source_config={"database": "app_db"},
        credentials={"password": "pwd"},
    )

    assert len(objects) == 3
    assert objects[0].name == "customers"  # public schema display name
    assert objects[0].type == "table"
    assert objects[1].name == "orders"
    assert objects[2].name == "analytics.monthly_mrr"  # non-public includes schema
    assert objects[2].type == "view"


@patch.object(PostgresConnector, "_connect")
def test_postgres_schema_inference(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # 1. Column query returns: column_name, data_type, is_nullable
    mock_cur.fetchall.return_value = [
        ("order_id", "bigint", "NO"),
        ("customer_id", "integer", "NO"),
        ("total_usd", "numeric", "YES"),
        ("status", "character varying", "NO"),
        ("is_paid", "boolean", "YES"),
        ("created_at", "timestamp with time zone", "NO"),
        ("payload", "jsonb", "YES"),
    ]
    # 2. Count query returns row count: [1500]
    mock_cur.fetchone.return_value = [1500]
    mock_connect.return_value = mock_conn

    connector = PostgresConnector()
    schema = connector.infer_schema(
        source_config={"database": "app_db"},
        table_options={"schema": "public", "table_name": "orders"},
    )

    assert schema.row_count_estimate == 1500
    assert len(schema.columns) == 7
    col_map = {c.name: c for c in schema.columns}

    assert col_map["order_id"].type == "Int64"
    assert col_map["order_id"].nullable is False
    assert col_map["total_usd"].type == "Float64"
    assert col_map["total_usd"].nullable is True
    assert col_map["status"].type == "String"
    assert col_map["status"].nullable is False
    assert col_map["is_paid"].type == "Boolean"
    assert col_map["created_at"].type == "DateTime"
    assert col_map["payload"].type == "JSON"


@patch.object(PostgresConnector, "_connect")
def test_postgres_preview_and_projections(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Mock cursor description
    mock_cur.description = [
        ("order_id",),
        ("customer",),
        ("amount",),
    ]
    mock_cur.fetchall.return_value = [
        (101, "Alice", 450.50),
        (102, "Bob", 120.00),
    ]
    mock_cur.fetchone.return_value = [250]  # total_rows
    mock_connect.return_value = mock_conn

    connector = PostgresConnector()
    prev = connector.preview(
        source_config={"database": "app_db"},
        table_options={"table_name": "orders", "columns": "order_id, customer, amount"},
        limit=10,
    )

    assert prev.columns == ["order_id", "customer", "amount"]
    assert len(prev.rows) == 2
    assert prev.rows[0]["order_id"] == 101
    assert prev.rows[0]["customer"] == "Alice"
    assert prev.rows[0]["amount"] == 450.50
    assert prev.total_rows == 250


@patch.object(PostgresConnector, "_connect")
def test_postgres_custom_query_mode(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    mock_cur.description = [("customer_id",), ("total_spent",)]
    mock_cur.fetchall.return_value = [(1, 850.00), (2, 320.50)]
    mock_cur.fetchone.return_value = [2]
    mock_connect.return_value = mock_conn

    connector = PostgresConnector()
    custom_sql = "SELECT customer_id, sum(amount) as total_spent FROM orders GROUP BY customer_id"
    prev = connector.preview(
        source_config={"database": "app_db"},
        table_options={"query": custom_sql},
    )

    assert prev.columns == ["customer_id", "total_spent"]
    assert len(prev.rows) == 2
    assert prev.rows[0]["customer_id"] == 1


def test_postgres_catalog_service_integration(tmp_path: Path):
    cat_yaml = tmp_path / "postgres_catalog.yaml"
    service = CatalogService()
    service.create_catalog(cat_yaml, "Postgres Catalog")

    # 1. Create a reusable connection with masked credentials
    service.create_connection(
        name="Production Postgres Warehouse",
        connector="postgres",
        config={"host": "pg.internal.cloud", "port": 5432, "database": "warehouse_prod", "sslmode": "require"},
        credentials={"username": "prod_user", "password": "SuperSecurePostgresPassword123!"},
        description="High-availability PostgreSQL operational analytics cluster",
    )
    conn_list = service.list_connections()
    assert any(c["id"] == "production_postgres_warehouse" for c in conn_list)

    # Verify password is NOT in catalog YAML
    yaml_text = read_catalog_yaml(cat_yaml)
    assert "SuperSecurePostgresPassword123!" not in yaml_text

    # 2. Add table referencing that connection
    service.create_table(
        name="pg_orders",
        namespace="default",
        connector="postgres",
        connection_id="production_postgres_warehouse",
        options={"schema": "public", "table_name": "orders"},
        description="Customer purchase orders table in PostgreSQL",
    )

    state = service.state()
    default_cat = next(c for c in state.categories if c["name"] == "default")
    assert any(t["name"] == "pg_orders" for t in default_cat["tables"])

    # Verify YAML saved table metadata
    saved_yaml = read_catalog_yaml(cat_yaml)
    assert "pg_orders" in saved_yaml
    assert "production_postgres_warehouse" in saved_yaml


def test_postgres_validation_errors():
    connector = PostgresConnector()

    # Missing database
    with pytest.raises(ConnectorValidationError, match="database name is required"):
        connector._build_connection_params(source_config={})

    # Missing table_name and query
    with pytest.raises(SchemaInferenceError, match="Either Table Name or Custom Query"):
        connector.infer_schema(
            source_config={"database": "test_db"},
            table_options={},
        )
