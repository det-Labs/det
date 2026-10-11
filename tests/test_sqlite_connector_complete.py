"""Complete automated test suite for SQLite database connector."""

import sqlite3
from pathlib import Path

import pytest

from det.catalog import CatalogService
from det.catalog import config as catalog_config
from det.catalog.store import read_catalog_yaml
from det.connectors import get_connector
from det.connectors.databases.sqlite_connector import SQLiteConnector
from det.connectors.errors import (
    DiscoveryError,
    PreviewError,
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


@pytest.fixture
def sample_sqlite_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "ecommerce.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Table 1: Customers
    cursor.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE,
            active BOOLEAN DEFAULT 1,
            balance REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            avatar BLOB
        );
    """)

    customers_data = [
        ("Alice", "Smith", "alice@example.com", 1, 150.50, b"\x89PNG\r\n\x1a\n"),
        ("Bob", "Jones", "bob@example.com", 1, 320.00, None),
        ("Charlie", "Brown", "charlie@example.com", 0, 0.00, None),
        ("Diana", "Prince", "diana@example.com", 1, 980.75, b"\x89PNGavatar"),
    ]
    cursor.executemany("""
        INSERT INTO customers (first_name, last_name, email, active, balance, avatar)
        VALUES (?, ?, ?, ?, ?, ?);
    """, customers_data)

    # Table 2: Orders
    cursor.execute("""
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        );
    """)

    orders_data = [
        (101, 1, 55.00, "COMPLETED"),
        (102, 1, 95.50, "COMPLETED"),
        (103, 2, 320.00, "SHIPPED"),
        (104, 4, 450.25, "PENDING"),
        (105, 4, 530.50, "COMPLETED"),
    ]
    cursor.executemany("""
        INSERT INTO orders (order_id, customer_id, amount, status)
        VALUES (?, ?, ?, ?);
    """, orders_data)

    # View: customer_order_totals
    cursor.execute("""
        CREATE VIEW customer_order_totals AS
        SELECT c.customer_id, c.first_name, c.last_name, count(o.order_id) as total_orders, sum(o.amount) as total_spent
        FROM customers c
        LEFT JOIN orders o ON c.customer_id = o.customer_id
        GROUP BY c.customer_id;
    """)

    conn.commit()
    conn.close()
    return db_file


def test_sqlite_connector_registration():
    connector = get_connector("sqlite")
    assert isinstance(connector, SQLiteConnector)
    assert connector.id == "sqlite"
    assert connector.name == "SQLite"
    assert connector.group == "Databases"


def test_sqlite_connection_testing(sample_sqlite_db: Path, tmp_path: Path):
    connector = SQLiteConnector()

    # Valid connection
    result = connector.test_connection(source_config={"database_path": str(sample_sqlite_db)})
    assert result.success is True
    assert "Connected successfully" in result.message
    assert result.details.get("table_count") == 3  # customers, orders, customer_order_totals

    # Non-existent file
    missing_file = tmp_path / "missing.db"
    fail_res = connector.test_connection(source_config={"database_path": str(missing_file)})
    assert fail_res.success is False
    assert "not found" in fail_res.message.lower()


def test_sqlite_object_discovery(sample_sqlite_db: Path):
    connector = SQLiteConnector()
    objects = connector.discover_objects(source_config={"database_path": str(sample_sqlite_db)})

    obj_names = {obj.name for obj in objects}
    assert "customers" in obj_names
    assert "orders" in obj_names
    assert "customer_order_totals" in obj_names

    types = {obj.name: obj.type for obj in objects}
    assert types["customers"] == "table"
    assert types["orders"] == "table"
    assert types["customer_order_totals"] == "view"


def test_sqlite_schema_inference(sample_sqlite_db: Path):
    connector = SQLiteConnector()

    # Table schema
    schema = connector.infer_schema(
        source_config={"database_path": str(sample_sqlite_db)},
        table_options={"table_name": "customers"},
    )
    assert schema.row_count_estimate == 4
    col_dict = {col.name: col for col in schema.columns}

    assert "customer_id" in col_dict
    assert col_dict["customer_id"].type == "Int64"
    assert "first_name" in col_dict
    assert col_dict["first_name"].type == "String"
    assert "balance" in col_dict
    assert col_dict["balance"].type == "Float64"
    assert "active" in col_dict
    assert col_dict["active"].type == "Boolean"
    assert "avatar" in col_dict
    assert col_dict["avatar"].type == "Binary"


def test_sqlite_preview_and_projections(sample_sqlite_db: Path):
    connector = SQLiteConnector()

    # 1. Full table preview
    preview = connector.preview(
        source_config={"database_path": str(sample_sqlite_db)},
        table_options={"table_name": "customers"},
        limit=10,
    )
    assert len(preview.rows) == 4
    assert preview.total_rows == 4
    assert preview.columns == ["customer_id", "first_name", "last_name", "email", "active", "balance", "created_at", "avatar"]
    assert preview.rows[0]["first_name"] == "Alice"
    assert "<blob" in str(preview.rows[0]["avatar"])

    # 2. Specific columns projection
    proj_preview = connector.preview(
        source_config={"database_path": str(sample_sqlite_db)},
        table_options={"table_name": "customers", "columns": "customer_id, first_name, balance"},
        limit=2,
    )
    assert proj_preview.columns == ["customer_id", "first_name", "balance"]
    assert len(proj_preview.rows) == 2
    assert proj_preview.rows[1]["first_name"] == "Bob"

    # 3. View preview
    view_preview = connector.preview(
        source_config={"database_path": str(sample_sqlite_db)},
        table_options={"table_name": "customer_order_totals"},
    )
    assert len(view_preview.rows) == 4
    alice_view = next(r for r in view_preview.rows if r["first_name"] == "Alice")
    assert alice_view["total_orders"] == 2
    assert float(alice_view["total_spent"]) == 150.5


def test_sqlite_custom_query_mode(sample_sqlite_db: Path):
    connector = SQLiteConnector()
    custom_sql = """
        SELECT o.order_id, c.first_name, o.amount, o.status
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.amount > 100
        ORDER BY o.amount DESC
    """
    # Schema for custom query
    schema = connector.infer_schema(
        source_config={"database_path": str(sample_sqlite_db)},
        table_options={"query": custom_sql},
    )
    col_names = [c.name for c in schema.columns]
    assert col_names == ["order_id", "first_name", "amount", "status"]
    assert schema.row_count_estimate == 3

    # Preview for custom query
    prev = connector.preview(
        source_config={"database_path": str(sample_sqlite_db)},
        table_options={"query": custom_sql},
        limit=2,
    )
    assert len(prev.rows) == 2
    assert prev.rows[0]["first_name"] == "Diana"
    assert float(prev.rows[0]["amount"]) == 530.50


def test_sqlite_polars_dataframe_scan(sample_sqlite_db: Path):
    connector = SQLiteConnector()
    df = connector.read_polars(
        source_config={"database_path": str(sample_sqlite_db)},
        table_options={"table_name": "orders"},
    )
    assert df.shape == (5, 4)
    assert "amount" in df.columns
    assert df["amount"].sum() == 1451.25


def test_sqlite_catalog_service_integration(sample_sqlite_db: Path, tmp_path: Path):
    cat_yaml = tmp_path / "sqlite_catalog.yaml"
    service = CatalogService()
    service.create_catalog(cat_yaml, "SQLite Relational Catalog")

    # 1. Create a reusable connection
    service.create_connection(
        name="Production SQLite Store",
        connector="sqlite",
        config={"database_path": str(sample_sqlite_db)},
        description="Core relational operational database",
    )
    assert any(c["id"] == "production_sqlite_store" for c in service.list_connections())

    # 2. Add table referencing that connection
    service.create_table(
        name="customers_table",
        namespace="default",
        connector="sqlite",
        connection_id="production_sqlite_store",
        options={"table_name": "customers"},
        description="Active customer accounts and balances",
    )

    # 3. Add view referencing that connection
    service.create_table(
        name="order_summaries",
        namespace="default",
        connector="sqlite",
        connection_id="production_sqlite_store",
        options={"table_name": "customer_order_totals"},
    )

    state = service.state()
    default_cat = next(c for c in state.categories if c["name"] == "default")
    assert len(default_cat["tables"]) == 2

    # Verify YAML file saved clean metadata without credentials
    yaml_str = read_catalog_yaml(cat_yaml)
    assert "customers_table" in yaml_str
    assert "order_summaries" in yaml_str
    assert "production_sqlite_store" in yaml_str


def test_sqlite_error_handling(sample_sqlite_db: Path):
    connector = SQLiteConnector()

    # Table does not exist
    with pytest.raises(SchemaInferenceError):
        connector.infer_schema(
            source_config={"database_path": str(sample_sqlite_db)},
            table_options={"table_name": "non_existent_table"},
        )

    # Syntax error in custom query
    with pytest.raises(PreviewError):
        connector.preview(
            source_config={"database_path": str(sample_sqlite_db)},
            table_options={"query": "SELECT INVALID SYNTAX FROM"},
        )

    # Missing database path returns failure in test_connection
    res = connector.test_connection(source_config={})
    assert res.success is False
    assert "required" in res.message.lower()

    # Missing database path raises in discovery
    with pytest.raises(DiscoveryError):
        connector.discover_objects(source_config={})
