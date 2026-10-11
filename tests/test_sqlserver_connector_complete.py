"""Complete automated test suite for Microsoft SQL Server database connector."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from det.catalog import CatalogService
from det.catalog import config as catalog_config
from det.catalog.store import read_catalog_yaml
from det.connectors import get_connector
from det.connectors.databases.sqlserver_connector import (
    SQLServerConnector,
    map_sqlserver_type_to_standard,
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


def test_sqlserver_connector_registration():
    connector = get_connector("sqlserver")
    assert isinstance(connector, SQLServerConnector)
    assert connector.id == "sqlserver"
    assert connector.name == "SQL Server"
    assert connector.group == "Databases"


def test_sqlserver_type_mapping():
    assert map_sqlserver_type_to_standard("int") == "Int64"
    assert map_sqlserver_type_to_standard("bigint") == "Int64"
    assert map_sqlserver_type_to_standard("smallint") == "Int64"
    assert map_sqlserver_type_to_standard("tinyint") == "Int64"
    assert map_sqlserver_type_to_standard("decimal") == "Float64"
    assert map_sqlserver_type_to_standard("numeric") == "Float64"
    assert map_sqlserver_type_to_standard("money") == "Float64"
    assert map_sqlserver_type_to_standard("float") == "Float64"
    assert map_sqlserver_type_to_standard("varchar") == "String"
    assert map_sqlserver_type_to_standard("nvarchar") == "String"
    assert map_sqlserver_type_to_standard("text") == "String"
    assert map_sqlserver_type_to_standard("bit") == "Boolean"
    assert map_sqlserver_type_to_standard("datetime") == "DateTime"
    assert map_sqlserver_type_to_standard("datetime2") == "DateTime"
    assert map_sqlserver_type_to_standard("date") == "DateTime"
    assert map_sqlserver_type_to_standard("varbinary") == "Binary"
    assert map_sqlserver_type_to_standard("uniqueidentifier") == "String"
    assert map_sqlserver_type_to_standard("xml") == "String"


def test_sqlserver_parameter_construction():
    connector = SQLServerConnector()

    params = connector._build_connection_params(
        source_config={"host": "mssql.corp.net", "port": 14333, "database": "FinanceDB"},
        credentials={"username": "sql_admin", "password": "StrongPassword99!"},
    )
    assert params["server"] == "mssql.corp.net"
    assert params["port"] == "14333"
    assert params["database"] == "FinanceDB"
    assert params["user"] == "sql_admin"
    assert params["password"] == "StrongPassword99!"
    assert params["timeout"] == 10


@patch.object(SQLServerConnector, "_connect")
def test_sqlserver_connection_testing(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.fetchone.return_value = [22]
    mock_connect.return_value = mock_conn

    connector = SQLServerConnector()

    # Success case
    res = connector.test_connection(
        source_config={"host": "localhost", "database": "SalesDB"},
        credentials={"username": "sa", "password": "pwd"},
    )
    assert res.success is True
    assert "Connected successfully" in res.message
    assert res.details.get("table_count") == 22

    # Failure case
    mock_connect.side_effect = Exception("Adaptive Server is unavailable or does not exist")
    fail_res = connector.test_connection(
        source_config={"host": "invalid-host", "database": "SalesDB"},
    )
    assert fail_res.success is False
    assert "unavailable" in fail_res.message


@patch.object(SQLServerConnector, "_connect")
def test_sqlserver_object_discovery(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    # Mock TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
    mock_cur.fetchall.return_value = [
        ("dbo", "Customers", "BASE TABLE"),
        ("dbo", "Orders", "BASE TABLE"),
        ("sales", "MonthlyRevenue", "VIEW"),
    ]
    mock_connect.return_value = mock_conn

    connector = SQLServerConnector()
    objects = connector.discover_objects(
        source_config={"database": "SalesDB"},
        credentials={"username": "sa", "password": "pwd"},
    )

    assert len(objects) == 3
    assert objects[0].name == "Customers"
    assert objects[0].type == "table"
    assert objects[1].name == "Orders"
    assert objects[2].name == "sales.MonthlyRevenue"
    assert objects[2].type == "view"


@patch.object(SQLServerConnector, "_connect")
def test_sqlserver_schema_inference(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    # COLUMN_NAME, DATA_TYPE, IS_NULLABLE
    mock_cur.fetchall.return_value = [
        ("OrderID", "bigint", "NO"),
        ("CustomerID", "int", "NO"),
        ("TotalAmount", "decimal", "YES"),
        ("OrderStatus", "nvarchar", "NO"),
        ("IsProcessed", "bit", "YES"),
        ("OrderDate", "datetime2", "NO"),
    ]
    mock_cur.fetchone.return_value = [5420]
    mock_connect.return_value = mock_conn

    connector = SQLServerConnector()
    schema = connector.infer_schema(
        source_config={"database": "SalesDB"},
        table_options={"schema": "dbo", "table_name": "Orders"},
    )

    assert schema.row_count_estimate == 5420
    assert len(schema.columns) == 6
    cols = {c.name: c for c in schema.columns}

    assert cols["OrderID"].type == "Int64"
    assert cols["OrderID"].nullable is False
    assert cols["TotalAmount"].type == "Float64"
    assert cols["TotalAmount"].nullable is True
    assert cols["OrderStatus"].type == "String"
    assert cols["OrderStatus"].nullable is False
    assert cols["IsProcessed"].type == "Boolean"
    assert cols["OrderDate"].type == "DateTime"


@patch.object(SQLServerConnector, "_connect")
def test_sqlserver_preview_and_projections(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    mock_cur.description = [("OrderID",), ("CustomerName",), ("Amount",)]
    mock_cur.fetchall.return_value = [
        (1001, "Acme Industrial", 12500.00),
        (1002, "Global Tech", 8400.50),
    ]
    mock_cur.fetchone.return_value = [100]
    mock_connect.return_value = mock_conn

    connector = SQLServerConnector()
    prev = connector.preview(
        source_config={"database": "SalesDB"},
        table_options={"table_name": "Orders", "columns": "OrderID, CustomerName, Amount"},
        limit=10,
    )

    assert prev.columns == ["OrderID", "CustomerName", "Amount"]
    assert len(prev.rows) == 2
    assert prev.rows[0]["OrderID"] == 1001
    assert prev.rows[0]["CustomerName"] == "Acme Industrial"
    assert prev.rows[0]["Amount"] == 12500.00


@patch.object(SQLServerConnector, "_connect")
def test_sqlserver_custom_query_mode(mock_connect):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur

    mock_cur.description = [("DeptID",), ("BudgetTotal",)]
    mock_cur.fetchall.return_value = [(10, 450000.0), (20, 310000.0)]
    mock_cur.fetchone.return_value = [2]
    mock_connect.return_value = mock_conn

    connector = SQLServerConnector()
    custom_sql = "SELECT DeptID, SUM(Amount) as BudgetTotal FROM DepartmentBudgets GROUP BY DeptID"
    prev = connector.preview(
        source_config={"database": "FinanceDB"},
        table_options={"query": custom_sql},
    )

    assert prev.columns == ["DeptID", "BudgetTotal"]
    assert len(prev.rows) == 2
    assert prev.rows[0]["DeptID"] == 10


def test_sqlserver_catalog_service_integration(tmp_path: Path):
    cat_yaml = tmp_path / "sqlserver_catalog.yaml"
    service = CatalogService()
    service.create_catalog(cat_yaml, "SQL Server Enterprise Catalog")

    # 1. Create a reusable connection with masked credentials
    service.create_connection(
        name="Enterprise MSSQL Server",
        connector="sqlserver",
        config={"host": "mssql.enterprise.local", "port": 1433, "database": "ERP_Prod"},
        credentials={"username": "app_reader", "password": "TopSecretMssqlPassword!#99"},
        description="Production ERP Microsoft SQL Server database cluster",
    )
    conn_list = service.list_connections()
    assert any(c["id"] == "enterprise_mssql_server" for c in conn_list)

    # Verify credentials NOT in catalog YAML
    yaml_text = read_catalog_yaml(cat_yaml)
    assert "TopSecretMssqlPassword!#99" not in yaml_text

    # 2. Add table referencing that connection
    service.create_table(
        name="erp_orders",
        namespace="default",
        connector="sqlserver",
        connection_id="enterprise_mssql_server",
        options={"schema": "dbo", "table_name": "Orders"},
        description="ERP system orders ledger",
    )

    state = service.state()
    default_cat = next(c for c in state.categories if c["name"] == "default")
    assert any(t["name"] == "erp_orders" for t in default_cat["tables"])

    # Verify YAML file saved clean metadata
    saved_yaml = read_catalog_yaml(cat_yaml)
    assert "erp_orders" in saved_yaml
    assert "enterprise_mssql_server" in saved_yaml


def test_sqlserver_validation_errors():
    connector = SQLServerConnector()

    # Missing database name
    with pytest.raises(ConnectorValidationError, match="database name is required"):
        connector._build_connection_params(source_config={})

    # Missing table_name and query
    with pytest.raises(SchemaInferenceError, match="Either Table Name or Custom Query"):
        connector.infer_schema(
            source_config={"database": "SalesDB"},
            table_options={},
        )

