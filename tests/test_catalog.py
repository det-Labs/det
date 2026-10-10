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


def test_catalog_create_catalog(tmp_path: Path):
    initial_path = tmp_path / "initial.yaml"
    service = CatalogService(initial_path)

    new_cat = tmp_path / "created.yaml"
    created_path = service.create_catalog(new_cat, name="Created Test Catalog")
    assert created_path == new_cat.resolve()
    assert service.active_path == new_cat.resolve()
    assert len(service.list_datasets()) == 0

    # Overwrite check without overwrite flag should raise FileExistsError
    with pytest.raises(FileExistsError):
        service.create_catalog(new_cat, overwrite=False)

    # Overwrite check with overwrite=True should succeed
    service.create_catalog(new_cat, overwrite=True)
    assert service.active_path == new_cat.resolve()


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


def test_directory_dataset_scanning_parquet(tmp_path: Path):
    """Test multi-file partitioned parquet directory scanning with extraneous files."""
    parq_dir = tmp_path / "sales_lake"
    (parq_dir / "year=2026").mkdir(parents=True)
    (parq_dir / "year=2025").mkdir(parents=True)

    df1 = pl.DataFrame({"id": [1, 2], "val": [10.5, 20.0]})
    df2 = pl.DataFrame({"id": [3, 4], "val": [30.5, 40.0]})
    df1.write_parquet(parq_dir / "year=2026" / "part-001.parquet")
    df2.write_parquet(parq_dir / "year=2025" / "part-002.parquet")

    # Add extraneous non-parquet file often found in data lakes
    (parq_dir / "_SUCCESS").write_text("")
    (parq_dir / "notes.txt").write_text("Export metadata")

    service = CatalogService(tmp_path / "cat.yaml")
    scan = service.scan_path(parq_dir)

    assert scan.format == "parquet (directory)"
    col_names = [c.name for c in scan.columns]
    assert "id" in col_names
    assert "val" in col_names
    assert len(scan.sample_preview) > 0


def test_directory_dataset_scanning_csv_and_json(tmp_path: Path):
    """Test directory scanning for multi-file CSV and NDJSON directories."""
    csv_dir = tmp_path / "csv_drops"
    csv_dir.mkdir()
    pl.DataFrame({"code": ["A", "B"], "qty": [100, 200]}).write_csv(csv_dir / "drop1.csv")
    pl.DataFrame({"code": ["C", "D"], "qty": [300, 400]}).write_csv(csv_dir / "drop2.csv")

    service = CatalogService(tmp_path / "cat.yaml")
    csv_scan = service.scan_path(csv_dir)
    assert csv_scan.format == "csv (directory)"
    assert [c.name for c in csv_scan.columns] == ["code", "qty"]

    # Test NDJSON directory
    json_dir = tmp_path / "json_drops"
    json_dir.mkdir()
    pl.DataFrame({"event": ["click", "view"], "ts": [1, 2]}).write_ndjson(json_dir / "e1.ndjson")
    json_scan = service.scan_path(json_dir)
    assert json_scan.format == "ndjson (directory)"
    assert [c.name for c in json_scan.columns] == ["event", "ts"]


def test_directory_dataset_schema_mismatch_error(tmp_path: Path):
    """Test that querying a directory with incompatible parquet schemas raises a SchemaError."""
    mismatch_dir = tmp_path / "mismatch"
    mismatch_dir.mkdir()

    pl.DataFrame({"col_a": [1, 2]}).write_parquet(mismatch_dir / "f1.parquet")
    # col_a has string type instead of int64
    pl.DataFrame({"col_a": ["bad", "types"]}).write_parquet(mismatch_dir / "f2.parquet")

    service = CatalogService(tmp_path / "cat.yaml")
    scan = service.scan_path(mismatch_dir)
    assert scan.format == "parquet (directory)"

    # When querying the unified dataset across partitions, Polars raises SchemaError
    with pytest.raises(pl.exceptions.SchemaError):
        pl.scan_parquet(f"{mismatch_dir.as_posix()}/**/*.parquet").collect()
