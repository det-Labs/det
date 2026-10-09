import os
import pytest
from det.catalog import CatalogStore, DatasetDescriptor

@pytest.fixture
def catalog_store(tmp_path):
    catalog_file = tmp_path / "catalog.yaml"
    return CatalogStore(filepath=str(catalog_file))

def test_register_and_resolve(catalog_store):
    dataset = DatasetDescriptor(
        name="test_data",
        namespace="test_ns",
        location="s3://bucket/test_data.parquet",
        type="parquet"
    )

    catalog_store.register(dataset)

    resolved = catalog_store.resolve("test_data", "test_ns")
    assert resolved is not None
    assert resolved.name == "test_data"
    assert resolved.namespace == "test_ns"
    assert resolved.location == "s3://bucket/test_data.parquet"
    assert resolved.type == "parquet"
    assert resolved.tags is None

def test_search(catalog_store):
    dataset1 = DatasetDescriptor(
        name="sales",
        namespace="finance",
        location="s3://bucket/sales.parquet",
        type="parquet",
        tags=["important", "daily"]
    )
    dataset2 = DatasetDescriptor(
        name="logs",
        namespace="engineering",
        location="s3://bucket/logs.csv",
        type="csv",
        tags=["daily"]
    )

    catalog_store.register(dataset1)
    catalog_store.register(dataset2)

    results_tag = catalog_store.search(tags=["daily"])
    assert len(results_tag) == 2

    results_ns = catalog_store.search(namespace="finance")
    assert len(results_ns) == 1
    assert results_ns[0].name == "sales"

    results_type = catalog_store.search(dataset_type="csv")
    assert len(results_type) == 1
    assert results_type[0].name == "logs"

def test_update_existing(catalog_store):
    dataset = DatasetDescriptor(
        name="test_data",
        namespace="default",
        location="s3://bucket/test_data.parquet",
        type="parquet"
    )
    catalog_store.register(dataset)

    # Update row count
    dataset.row_count = 1000
    catalog_store.register(dataset)

    resolved = catalog_store.resolve("test_data", "default")
    assert resolved is not None
    assert resolved.row_count == 1000
    assert len(catalog_store._read_catalog()["datasets"]) == 1

def test_concurrent_lock(catalog_store):
    # This just ensures lock file gets created and no syntax errors in the fcntl logic
    dataset = DatasetDescriptor(
        name="test_data",
        namespace="default",
        location="s3://bucket/test_data.parquet",
        type="parquet"
    )
    catalog_store.register(dataset)
    assert os.path.exists(f"{catalog_store.filepath}.lock")
