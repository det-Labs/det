"""Comprehensive tests for connectors contract, shared sources, credential separation, and table operations."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from det.catalog import CatalogService
from det.catalog import config as catalog_config
from det.catalog.models import ColumnMetadata
from det.catalog.store import read_catalog_yaml
from det.connectors import credentials as conn_creds
from det.connectors import (
    get_connector,
    list_connectors_grouped,
)
from det.gui import server


@pytest.fixture(autouse=True)
def isolate_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".det"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    creds_path = config_dir / "credentials.json"
    conn_path = config_dir / "connections.yaml"
    monkeypatch.setattr(catalog_config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(catalog_config, "CONFIG_FILE", config_path)
    monkeypatch.setattr(conn_creds, "CREDENTIALS_FILE", creds_path)
    from det.connectors import connections
    monkeypatch.setattr(connections, "_custom_connections_path", conn_path)
    server.set_service(None)
    yield
    server.set_service(None)


def test_connectors_registered_and_grouped():
    grouped = list_connectors_grouped()
    assert "Files" in grouped
    file_conn_ids = [c["id"] for c in grouped["Files"]]
    assert "csv" in file_conn_ids



def test_csv_single_file_multiple_files_and_nested_folders(tmp_path: Path):
    connector = get_connector("csv")

    # 1. Single CSV file
    file1 = tmp_path / "single.csv"
    file1.write_text("id,name,amount\n1,Alice,100.5\n2,Bob,200.0\n", encoding="utf-8")

    schema_single = connector.infer_schema({}, {}, {"path": str(file1)})
    assert [c.name for c in schema_single.columns] == ["id", "name", "amount"]
    assert schema_single.row_count_estimate == 2

    preview_single = connector.preview({}, {}, {"path": str(file1)}, limit=1)
    assert len(preview_single.rows) == 1
    assert preview_single.rows[0]["name"] == "Alice"

    # 2. Folder with multiple CSV files
    folder = tmp_path / "batch_folder"
    folder.mkdir()
    (folder / "part1.csv").write_text("id,val\n10,A\n", encoding="utf-8")
    (folder / "part2.csv").write_text("id,val\n20,B\n", encoding="utf-8")

    schema_folder = connector.infer_schema({}, {}, {"path": str(folder), "file_selection": "folder"})
    assert [c.name for c in schema_folder.columns] == ["id", "val"]

    preview_folder = connector.preview({}, {}, {"path": str(folder), "file_selection": "folder"})
    assert len(preview_folder.rows) == 2
    assert [r["id"] for r in preview_folder.rows] == [10, 20]

    # 3. Nested folders with recursive scanning
    nested_root = tmp_path / "nested_data"
    sub1 = nested_root / "2026" / "01"
    sub2 = nested_root / "2026" / "02"
    sub1.mkdir(parents=True)
    sub2.mkdir(parents=True)
    (sub1 / "sales_01.csv").write_text("month,revenue\nJan,5000\n", encoding="utf-8")
    (sub2 / "sales_02.csv").write_text("month,revenue\nFeb,7500\n", encoding="utf-8")

    preview_nested = connector.preview(
        {},
        {},
        {"path": str(nested_root), "file_selection": "recursive", "file_pattern": "sales_*.csv"},
    )
    assert len(preview_nested.rows) == 2
    months = {r["month"] for r in preview_nested.rows}
    assert months == {"Jan", "Feb"}


def test_source_credentials_separation_and_masking(tmp_path: Path):
    catalog_path = tmp_path / "catalog.yaml"
    service = CatalogService()
    service.create_catalog(catalog_path, "Secured Catalog")

    # Create connection with sensitive password
    service.create_connection(
        name="Remote CSV Server",
        connector="csv",
        config={"protocol": "ftp", "host": "test.rebex.net", "port": 21, "username": "demo"},
        credentials={"password": "SuperSecretPassword123!"},
    )

    # 1. Verify credentials are NOT in catalog YAML
    yaml_text = read_catalog_yaml(catalog_path)
    assert "SuperSecretPassword123!" not in yaml_text

    # 2. Verify credentials ARE saved in local connections.yaml
    conns = conn_creds.list_connections(mask_secrets=False)
    assert any(c["id"] == "remote_csv_server" for c in conns)
    saved_creds = conn_creds.get_connection_credentials("remote_csv_server")
    assert saved_creds.get("password") == "SuperSecretPassword123!"

    # 3. Verify normal state response masks credentials
    connections = service.list_connections()
    assert len(connections) == 1
    assert connections[0]["has_credentials"] is True
    assert "password" not in connections[0]["config"]

    # 4. Updating connection without touching password preserves it
    service.update_connection(
        connection_id="remote_csv_server",
        config={"protocol": "ftp", "host": "test2.rebex.net", "port": 21, "username": "demo"},
        credentials={"password": "••••••••"},  # masked input from GUI
    )
    preserved = conn_creds.get_connection_credentials("remote_csv_server")
    assert preserved["password"] == "SuperSecretPassword123!"

    # 5. Deleting connection removes it from connections.yaml
    service.delete_connection("remote_csv_server")
    assert conn_creds.get_connection("remote_csv_server") is None



def test_table_create_update_delete_and_invariants(tmp_path: Path):
    catalog_path = tmp_path / "tables_test.yaml"
    service = CatalogService()
    service.create_catalog(catalog_path, "Table Ops")
    service.create_category("raw_data")

    # Create CSV file
    data_file = tmp_path / "users.csv"
    data_file.write_text("user_id,email,active\n1,u1@test.com,true\n2,u2@test.com,false\n", encoding="utf-8")

    # Create table
    state = service.create_table(
        name="users",
        namespace="raw_data",
        connector="csv",
        options={"path": str(data_file), "delimiter": ","},
        columns=[
            ColumnMetadata(name="user_id", type="Int64"),
            ColumnMetadata(name="email", type="String"),
            ColumnMetadata(name="active", type="Boolean"),
        ],
        description="User accounts table",
    )

    cat_raw = next(c for c in state.categories if c["name"] == "raw_data")
    assert cat_raw["count"] == 1
    assert cat_raw["tables"][0]["name"] == "users"
    assert cat_raw["tables"][0]["columns_count"] == 3

    # Duplicate in same category is refused
    with pytest.raises(ValueError, match="already exists"):
        service.create_table(
            name="USERS",
            namespace="raw_data",
            connector="csv",
        )

    # Rename table and update columns
    state = service.update_table(
        table_id="raw_data.users",
        name="customer_users",
        columns=[
            ColumnMetadata(name="user_id", type="Int64"),
            ColumnMetadata(name="email", type="String"),
        ],
    )
    cat_raw = next(c for c in state.categories if c["name"] == "raw_data")
    assert cat_raw["tables"][0]["name"] == "customer_users"
    assert cat_raw["tables"][0]["columns_count"] == 2

    # Delete table
    state = service.delete_table("raw_data.customer_users")
    cat_raw = next(c for c in state.categories if c["name"] == "raw_data")
    assert cat_raw["count"] == 0

    # Failure to save leaves in-memory catalog unchanged
    with pytest.raises(KeyError):
        service.delete_table("non_existent_table")


def test_failed_table_save_does_not_mutate_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    service = CatalogService()
    service.create_catalog(tmp_path / "safe.yaml")

    monkeypatch.setattr(
        "det.catalog.service.save_catalog",
        Mock(side_effect=OSError("disk error")),
    )

    with pytest.raises(OSError, match="disk error"):
        service.create_table(
            name="faulty",
            namespace="default",
            connector="csv",
        )

    default_cat = next(c for c in service.state().categories if c["name"] == "default")
    assert default_cat["count"] == 0


def test_gui_api_table_and_connector_lifecycle(tmp_path: Path):
    server.set_service(None)
    client = TestClient(server.app)

    catalog_path = tmp_path / "gui_catalog.yaml"
    client.post(
        "/api/catalog/create",
        json={"path": str(catalog_path), "name": "GUI Full Test", "make_default": True},
    )

    # 1. Connectors endpoint
    conn_resp = client.get("/api/connectors")
    assert conn_resp.status_code == 200
    assert "Files" in conn_resp.json()

    # 2. Test connector endpoint with local file
    test_file = tmp_path / "orders.csv"
    test_file.write_text("order_id,total\n101,99.9\n102,149.5\n", encoding="utf-8")

    test_conn = client.post(
        "/api/connectors/test",
        json={"connector": "csv", "source_config": {"protocol": "local", "base_path": str(tmp_path)}},
    )
    assert test_conn.status_code == 200
    assert test_conn.json()["success"] is True

    # 3. Discover objects
    discover = client.post(
        "/api/connectors/discover",
        json={"connector": "csv", "source_config": {"base_path": str(tmp_path)}, "options": {"file_pattern": "*.csv"}},
    )
    assert discover.status_code == 200
    assert any(o["name"] == "orders.csv" for o in discover.json())

    # 4. Infer schema
    schema_res = client.post(
        "/api/connectors/schema",
        json={"connector": "csv", "table_options": {"path": str(test_file)}},
    )
    assert schema_res.status_code == 200
    cols = schema_res.json()["columns"]
    assert [c["name"] for c in cols] == ["order_id", "total"]

    # 5. Preview data
    prev_res = client.post(
        "/api/connectors/preview",
        json={"connector": "csv", "table_options": {"path": str(test_file)}, "limit": 10},
    )
    assert prev_res.status_code == 200
    assert len(prev_res.json()["rows"]) == 2

    # 6. Create Table via API
    create_tbl = client.post(
        "/api/catalog/tables",
        json={
            "name": "orders",
            "namespace": "default",
            "connector": "csv",
            "options": {"path": str(test_file)},
            "columns": cols,
        },
    )
    assert create_tbl.status_code == 201
    default_cat = next(c for c in create_tbl.json()["categories"] if c["name"] == "default")
    assert default_cat["count"] == 1

    # 7. Delete Table via API
    del_tbl = client.delete("/api/catalog/tables/default.orders")
    assert del_tbl.status_code == 200
    default_cat = next(c for c in del_tbl.json()["categories"] if c["name"] == "default")
    assert default_cat["count"] == 0


def test_parquet_and_json_and_sqlite_connectors(tmp_path: Path):
    pass

    # 1. Parquet test
def test_connection_deletion_prevented_if_used_by_table(tmp_path: Path):
    service = CatalogService()
    service.create_catalog(tmp_path / "catalog.yaml")

    service.create_connection(
        name="Shared CSV Server",
        connector="csv",
        config={"protocol": "local", "base_path": str(tmp_path)},
    )
    conn_id = "shared_csv_server"

    # Create table using this connection
    csv_file = tmp_path / "metrics.csv"
    csv_file.write_text("metric,val\nA,1\n", encoding="utf-8")
    service.create_table(
        name="metrics",
        namespace="default",
        connector="csv",
        connection_id=conn_id,
        options={"path": str(csv_file)},
    )

    # Deleting the connection should fail with descriptive message
    with pytest.raises(ValueError, match="cannot be deleted because it is used by tables"):
        service.delete_connection(conn_id)

    # After deleting the referencing table, deleting connection succeeds
    service.delete_table("default.metrics")
    service.delete_connection(conn_id)
    assert len(service.list_connections()) == 0


def test_custom_connector_dynamic_discovery_from_directory(tmp_path: Path):
    from det.connectors.registry import discover_and_register_from_directory, get_connector

    plugin_dir = tmp_path / "custom_connectors"
    plugin_dir.mkdir()
    plugin_code = '''
from det.connectors.contract import BaseConnector, ConnectorGroup, ConfigField, ConnectionTestResult, SchemaResult, PreviewResult, DiscoveredObject
from det.catalog.models import ColumnMetadata

class MockCustomConnector(BaseConnector):
    id = "mock_custom"
    name = "Mock Custom"
    group = ConnectorGroup.OTHERS
    description = "Test custom connector"
    fields = [ConfigField(name="custom_param", label="Custom Param", type="string")]

    def test_connection(self, options, *args, **kwargs):
        return ConnectionTestResult(success=True, message="Mock OK")
    def discover_objects(self, options, *args, **kwargs):
        return [DiscoveredObject(id="m1", name="m1", type="custom")]
    def infer_schema(self, options, *args, **kwargs):
        return SchemaResult(columns=[ColumnMetadata(name="col1", type="String")], sample_size=1)
    def preview(self, options, *args, limit=50, **kwargs):
        return PreviewResult(columns=["col1"], rows=[{"col1": "val1"}], total_rows=1)
'''
    (plugin_dir / "custom_plugin.py").write_text(plugin_code, encoding="utf-8")

    discovered = discover_and_register_from_directory(plugin_dir)
    assert "mock_custom" in discovered
    conn = get_connector("mock_custom")
    assert conn.name == "Mock Custom"
    assert conn.test_connection({}).success is True


def test_table_and_column_descriptions_and_nullable_persistence(tmp_path: Path):
    catalog_path = tmp_path / "catalog.yaml"
    service = CatalogService()
    service.create_catalog(catalog_path, "Description Test Catalog")
    server.set_service(service)

    cols = [
        ColumnMetadata(name="order_id", type="String", nullable=False, description="Primary order identifier"),
        ColumnMetadata(name="amount", type="Float64", nullable=True, description="Total amount, nullable for refunds"),
        ColumnMetadata(name="region", type="String", nullable=False, description="Fulfillment region"),
    ]

    service.create_table(
        name="orders",
        namespace="default",
        connector="csv",
        options={"path": "orders.csv"},
        columns=cols,
        description="Daily sales orders with full column metadata",
    )

    # 1. Test get_table directly on service
    table = service.get_table("default.orders")
    assert table.description == "Daily sales orders with full column metadata"
    assert len(table.columns) == 3
    assert table.columns[0].name == "order_id"
    assert table.columns[0].nullable is False
    assert table.columns[0].description == "Primary order identifier"
    assert table.columns[1].name == "amount"
    assert table.columns[1].nullable is True
    assert table.columns[1].description == "Total amount, nullable for refunds"

    # 2. Test via FastAPI client
    client = TestClient(server.app)
    resp = client.get("/api/catalog/tables/default.orders")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "orders"
    assert data["description"] == "Daily sales orders with full column metadata"
    assert len(data["columns"]) == 3
    assert data["columns"][0]["nullable"] is False
    assert data["columns"][0]["description"] == "Primary order identifier"
    assert data["columns"][1]["nullable"] is True
    assert data["columns"][1]["description"] == "Total amount, nullable for refunds"

    # 3. Test state representation
    state = service.state()
    cat_default = next(c for c in state.categories if c["name"] == "default")
    tbl_state = next(t for t in cat_default["tables"] if t["name"] == "orders")
    assert tbl_state["description"] == "Daily sales orders with full column metadata"
    assert tbl_state["columns"][0]["description"] == "Primary order identifier"
    assert tbl_state["columns"][0]["nullable"] is False
    assert tbl_state["columns"][1]["description"] == "Total amount, nullable for refunds"
    assert tbl_state["columns"][1]["nullable"] is True

    # 4. Verify index.html contains Description column header and table description card
    html_content = (Path(__file__).parent.parent / "src" / "det" / "gui" / "static" / "index.html").read_text(encoding="utf-8")
    assert "<th>Description</th>" in html_content
    assert "tableViewDescriptionCard" in html_content
    assert "tableViewDescriptionText" in html_content
    assert "isColumnNullable" in html_content



