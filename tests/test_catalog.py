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
