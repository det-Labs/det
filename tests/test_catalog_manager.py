"""Tests for CatalogManager lifecycle, CRUD operations, and engine integration."""

from pathlib import Path
from det.catalog.base import ConnectionTier
from det.catalog.definitions import ConnectionDefinition
from det.catalog.manager import CatalogManager
from det.engine.facade import EngineFacade


def test_catalog_manager_crud_operations(tmp_path: Path) -> None:
    """Verify adding, getting, listing, and deleting connection definitions."""
    yaml_path = tmp_path / "catalog" / "connections.yaml"
    manager = CatalogManager(yaml_path)

    conn = ConnectionDefinition(
        name="sales",
        type="csv",
        tier=ConnectionTier.ENTITY,
        options={"path": "sales.csv"},
    )

    # Add and retrieve
    manager.add_connection(conn)
    retrieved = manager.get_connection("sales")
    assert retrieved is not None
    assert retrieved.name == "sales"
    assert yaml_path.exists()

    # List
    all_conns = manager.list_connections()
    assert len(all_conns) == 1

    # Delete
    deleted = manager.delete_connection("sales")
    assert deleted is True
    assert manager.get_connection("sales") is None
    assert len(manager.list_connections()) == 0


def test_catalog_manager_engine_direct_query_integration(tmp_path: Path) -> None:
    """Verify catalog items mount directly into EngineFacade and support direct SQL querying."""
    # Create sample CSV file
    csv_file = tmp_path / "orders.csv"
    csv_file.write_text("order_id,amount\n101,250.5\n102,99.0\n", encoding="utf-8")

    yaml_path = tmp_path / "connections.yaml"
    manager = CatalogManager(yaml_path)

    # Register connection definition
    manager.add_connection(
        ConnectionDefinition(
            name="orders",
            type="csv",
            tier=ConnectionTier.ENTITY,
            options={"path": str(csv_file).replace("\\", "/")},
        )
    )

    # Mount catalog into EngineFacade
    engine = EngineFacade()
    report = engine.mount_all(manager.get_mountable_items())
    assert report.is_successful
    assert "orders" in report.mounted

    # Direct query: query connection name 'orders' directly in SQL!
    result = engine.execute("SELECT order_id, amount FROM orders WHERE amount > 100")
    assert result.columns == ["order_id", "amount"]
    assert result.rows == [(101, 250.5)]

    engine.close()

