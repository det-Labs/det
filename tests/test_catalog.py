"""Unit tests for det.catalog module."""

from pathlib import Path

import polars as pl
import pytest

from det.catalog import (
    CatalogService,
    DatasetMetadata,
    get_default_catalog_path,
    set_default_catalog_path,
)


@pytest.fixture
def temp_catalog_dir(tmp_path: Path):
    """Fixture providing a temporary directory with dummy data files."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create dummy parquet file
    df = pl.DataFrame({
        "order_id": [1, 2, 3],
        "customer": ["Alice", "Bob", "Charlie"],
        "amount": [99.5, 140.0, 25.25],
    })
    parquet_path = data_dir / "orders.parquet"
    df.write_parquet(parquet_path)

    # Create dummy CSV file
    csv_path = data_dir / "customers.csv"
    csv_df = pl.DataFrame({
        "customer_id": [1, 2],
        "name": ["Alice", "Bob"],
        "region": ["East", "West"],
    })
    csv_df.write_csv(csv_path)

    catalog_path = tmp_path / "test_catalog.yaml"
    return {
        "catalog_path": catalog_path,
        "parquet_path": parquet_path,
        "csv_path": csv_path,
        "tmp_path": tmp_path,
    }


def test_catalog_service_crud_and_scan(temp_catalog_dir):
    catalog_path = temp_catalog_dir["catalog_path"]
    parquet_path = temp_catalog_dir["parquet_path"]
    service = CatalogService(catalog_path)

    # Test auto-scan
    scan_res = service.scan_path(parquet_path)
    assert scan_res.format == "parquet"
    assert scan_res.row_count == 3
    col_names = [c.name for c in scan_res.columns]
    assert "order_id" in col_names
    assert "customer" in col_names
    assert "amount" in col_names

    # Test register
    dataset = DatasetMetadata(
        id="sales.orders",
        name="orders",
        namespace="sales",
        format="parquet",
        location=str(parquet_path),
        description="Orders test table",
        row_count=scan_res.row_count,
        columns=scan_res.columns,
        tags=["sales", "raw"],
    )
    registered = service.register_dataset(dataset)
    assert registered.id == "sales.orders"

    # Test list & get
    all_datasets = service.list_datasets()
    assert len(all_datasets) == 1
    assert service.get_dataset("sales.orders") is not None

    # Test search
    search_res = service.list_datasets(search="customer")
    assert len(search_res) == 1

    # Test update
    dataset.description = "Updated description"
    updated = service.update_dataset("sales.orders", dataset)
    assert updated.description == "Updated description"
    assert service.get_dataset("sales.orders").description == "Updated description"

    # Test switch catalog
    new_cat_path = temp_catalog_dir["tmp_path"] / "second_catalog.yaml"
    service.switch_catalog(new_cat_path)
    assert service.active_path == new_cat_path
    assert len(service.list_datasets()) == 0

    # Switch back and delete
    service.switch_catalog(catalog_path)
    assert len(service.list_datasets()) == 1
    assert service.delete_dataset("sales.orders") is True
    assert len(service.list_datasets()) == 0


def test_default_catalog_persistence(tmp_path: Path, monkeypatch):
    test_conf_dir = tmp_path / ".det"
    monkeypatch.setattr("det.catalog.config.CONFIG_DIR", test_conf_dir)
    monkeypatch.setattr("det.catalog.config.CONFIG_FILE", test_conf_dir / "config.json")

    custom_path = tmp_path / "my_custom_catalog.yaml"
    set_default_catalog_path(custom_path)
    retrieved = get_default_catalog_path()
    assert retrieved == custom_path.resolve()


def test_catalog_namespace_management(tmp_path: Path):
    catalog_path = tmp_path / "ns_test_catalog.yaml"
    service = CatalogService(catalog_path)

    # 1. Create namespaces
    service.create_namespace("analytics")
    service.create_namespace("finance")
    ns_list = service.list_namespaces()
    ns_names = [n["name"] for n in ns_list]
    assert "analytics" in ns_names
    assert "finance" in ns_names

    # 2. Register dataset in analytics
    ds = DatasetMetadata(
        id="analytics.kpi",
        name="kpi",
        namespace="analytics",
        location=str(tmp_path / "kpi.csv"),
        columns=[],
    )
    service.register_dataset(ds)

    # Check counts
    ns_dict = {n["name"]: n["count"] for n in service.list_namespaces()}
    assert ns_dict["analytics"] == 1
    assert ns_dict["finance"] == 0

    # 3. Rename namespace
    updated_count = service.rename_namespace("analytics", "reporting")
    assert updated_count == 1
    reporting_ds = service.get_dataset("reporting.kpi")
    assert reporting_ds is not None
    assert reporting_ds.namespace == "reporting"

    # 4. Delete namespace with reassign to default
    affected = service.delete_namespace("reporting", reassign_to="default")
    assert affected == 1
    default_ds = service.get_dataset("default.kpi")
    assert default_ds is not None
    assert default_ds.namespace == "default"
