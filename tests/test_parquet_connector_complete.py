"""Complete test suite for the Apache Parquet Connector.

Covers:
1. Local single parquet files (various Polars dtypes: int, float, string, bool, datetime, dates).
2. Multiple parquet files in a folder (folder mode).
3. Recursive nested subfolders and Hive partitions (e.g. region=NA/year=2024/data.parquet).
4. Column projection filtering (table_options["columns"]).
5. Connection testing and object discovery.
6. Reusable Connections file (.det/connections.yaml) integration via CatalogService.
7. Remote HTTP endpoint loading and parsing.
8. Robust error handling (missing files, malformed options, corrupted files).
"""

import io
from datetime import date, datetime
from pathlib import Path

import polars as pl
import pytest

from det.catalog import config as catalog_config
from det.catalog.service import CatalogService
from det.connectors.errors import PreviewError, SchemaInferenceError
from det.connectors.files.parquet_connector import ParquetConnector


@pytest.fixture(autouse=True)
def isolate_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".det"
    config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(catalog_config, "CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(catalog_config, "CONFIG_DIR", config_dir)


# =========================================================================
# 1. Local Single Parquet File & Types
# =========================================================================

def test_parquet_single_file_schema_and_preview(tmp_path: Path):
    connector = ParquetConnector()
    file_path = tmp_path / "events.parquet"

    df = pl.DataFrame({
        "event_id": [101, 102, 103],
        "user_name": ["Alice", "Bob", "Charlie"],
        "score": [98.5, 87.2, 91.0],
        "is_active": [True, False, True],
        "created_date": [date(2024, 1, 15), date(2024, 2, 20), date(2024, 3, 25)],
        "timestamp": [
            datetime(2024, 1, 15, 10, 30),
            datetime(2024, 2, 20, 14, 45),
            datetime(2024, 3, 25, 18, 0),
        ],
    })
    df.write_parquet(file_path)

    # Infer schema
    schema = connector.infer_schema({}, {}, {"path": str(file_path), "file_selection": "single"})
    assert len(schema.columns) == 6
    col_dict = {c.name: c.type for c in schema.columns}
    assert col_dict["event_id"] == "Int64"
    assert col_dict["user_name"] == "String"
    assert col_dict["score"] == "Float64"
    assert col_dict["is_active"] == "Boolean"
    assert col_dict["created_date"] == "Date"
    assert "Datetime" in col_dict["timestamp"]
    assert schema.row_count_estimate == 3

    # Preview with limit
    prev = connector.preview({}, {}, {"path": str(file_path)}, limit=2)
    assert len(prev.rows) == 2
    assert prev.columns == ["event_id", "user_name", "score", "is_active", "created_date", "timestamp"]
    assert prev.rows[0]["user_name"] == "Alice"
    assert prev.rows[1]["user_name"] == "Bob"
    assert prev.rows[0]["score"] == 98.5


# =========================================================================
# 2. Multiple Parquet Files in a Folder
# =========================================================================

def test_parquet_multiple_files_in_folder(tmp_path: Path):
    connector = ParquetConnector()
    data_dir = tmp_path / "daily_batches"
    data_dir.mkdir()

    pl.DataFrame({"id": [1, 2], "val": ["A", "B"]}).write_parquet(data_dir / "batch_1.parquet")
    pl.DataFrame({"id": [3, 4], "val": ["C", "D"]}).write_parquet(data_dir / "batch_2.parquet")
    pl.DataFrame({"id": [5, 6], "val": ["E", "F"]}).write_parquet(data_dir / "batch_3.parquet")

    schema = connector.infer_schema({}, {}, {
        "path": str(data_dir),
        "file_selection": "folder",
        "file_pattern": "*.parquet",
    })
    assert len(schema.columns) == 2
    assert schema.row_count_estimate == 6

    prev = connector.preview({}, {}, {
        "path": str(data_dir),
        "file_selection": "folder",
    }, limit=10)
    assert len(prev.rows) == 6
    ids = [r["id"] for r in prev.rows]
    assert set(ids) == {1, 2, 3, 4, 5, 6}


# =========================================================================
# 3. Recursive Nested Folders & Hive Partitions
# =========================================================================

def test_parquet_recursive_hive_partitions(tmp_path: Path):
    connector = ParquetConnector()
    root_dir = tmp_path / "lakehouse_sales"

    p1 = root_dir / "region=NA" / "year=2024"
    p2 = root_dir / "region=EU" / "year=2024"
    p3 = root_dir / "region=APAC" / "year=2025"
    p1.mkdir(parents=True)
    p2.mkdir(parents=True)
    p3.mkdir(parents=True)

    pl.DataFrame({"order_id": [1001], "revenue": [500.0]}).write_parquet(p1 / "data.parquet")
    pl.DataFrame({"order_id": [1002], "revenue": [750.0]}).write_parquet(p2 / "data.parquet")
    pl.DataFrame({"order_id": [1003], "revenue": [1200.0]}).write_parquet(p3 / "data.parquet")

    # In recursive mode, Polars should parse Hive partition keys (region, year) as columns
    schema = connector.infer_schema({}, {}, {
        "path": str(root_dir),
        "file_selection": "recursive",
        "hive_partitioning": True,
    })
    col_names = [c.name for c in schema.columns]
    assert "order_id" in col_names
    assert "revenue" in col_names
    assert "region" in col_names
    assert "year" in col_names
    assert schema.row_count_estimate == 3

    prev = connector.preview({}, {}, {
        "path": str(root_dir),
        "file_selection": "recursive",
        "hive_partitioning": True,
    }, limit=10)
    assert len(prev.rows) == 3
    regions = {r["region"] for r in prev.rows}
    assert regions == {"NA", "EU", "APAC"}


# =========================================================================
# 4. Column Projection
# =========================================================================

def test_parquet_column_projection(tmp_path: Path):
    connector = ParquetConnector()
    file_path = tmp_path / "wide_table.parquet"

    pl.DataFrame({
        "col_a": [1, 2],
        "col_b": ["x", "y"],
        "col_c": [10.0, 20.0],
        "col_d": [True, False],
    }).write_parquet(file_path)

    schema = connector.infer_schema({}, {}, {
        "path": str(file_path),
        "columns": "col_a, col_c",
    })
    assert len(schema.columns) == 2
    assert [c.name for c in schema.columns] == ["col_a", "col_c"]

    prev = connector.preview({}, {}, {
        "path": str(file_path),
        "columns": "col_a, col_c",
    })
    assert prev.columns == ["col_a", "col_c"]
    assert len(prev.rows) == 2
    assert "col_b" not in prev.rows[0]


# =========================================================================
# 5. Connection Test & Object Discovery
# =========================================================================

def test_parquet_connection_test_and_discovery(tmp_path: Path):
    connector = ParquetConnector()
    base_dir = tmp_path / "data_store"
    base_dir.mkdir()

    sub1 = base_dir / "folder1"
    sub1.mkdir()
    pl.DataFrame({"x": [1]}).write_parquet(sub1 / "f1.parquet")
    pl.DataFrame({"x": [2]}).write_parquet(base_dir / "root.parquet")

    # Test valid connection
    res = connector.test_connection({"base_path": str(base_dir)}, {})
    assert res.success is True

    # Test invalid connection
    res_bad = connector.test_connection({"base_path": str(tmp_path / "missing_dir")}, {})
    assert res_bad.success is False

    # Discover objects
    objs = connector.discover_objects({"base_path": str(base_dir)}, {}, {"recursive": True})
    assert len(objs) == 2
    obj_names = {o.name for o in objs}
    assert obj_names == {"f1.parquet", "root.parquet"}


# =========================================================================
# 6. Reusable Connection & CatalogService Workflow
# =========================================================================

def test_parquet_catalog_service_integration(tmp_path: Path):
    cat_yaml = tmp_path / "catalog.yaml"
    service = CatalogService()
    service.create_catalog(cat_yaml, "Parquet Catalog")

    storage_dir = tmp_path / "central_lake"
    storage_dir.mkdir()
    pl.DataFrame({"cust_id": [10, 20], "spent": [150.0, 320.0]}).write_parquet(storage_dir / "customers.parquet")

    # Save reusable connection
    state = service.create_connection(
        name="Central Lake Connection",
        connector="parquet",
        config={"protocol": "local", "base_path": str(storage_dir)},
        credentials={"password": "LakePasswordSecret"},
        description="Local Parquet Lakehouse",
    )
    conn_obj = state.sources[0]
    assert conn_obj["name"] == "Central Lake Connection"
    assert "password" not in conn_obj["config"]

    # Verify secret is not in catalog.yaml
    assert "LakePasswordSecret" not in cat_yaml.read_text(encoding="utf-8")

    # Create table referencing connection
    state = service.create_table(
        name="customers",
        namespace="default",
        connector="parquet",
        connection_id=conn_obj["id"],
        options={"path": "customers.parquet"},
    )
    assert len(state.categories[0]["tables"]) == 1

    # Infer schema through CatalogService
    schema = service.infer_table_schema(
        connector_id="parquet",
        connection_id=conn_obj["id"],
        table_options={"path": "customers.parquet"},
    )
    assert len(schema.columns) == 2
    assert schema.columns[0].name == "cust_id"

    # Preview through CatalogService
    preview = service.preview_table_data(
        connector_id="parquet",
        connection_id=conn_obj["id"],
        table_options={"path": "customers.parquet"},
        limit=5,
    )
    assert len(preview.rows) == 2
    assert preview.rows[0]["cust_id"] == 10
    assert preview.rows[1]["spent"] == 320.0


# =========================================================================
# 7. Remote HTTP Endpoint
# =========================================================================

def test_parquet_remote_http_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    connector = ParquetConnector()
    buf = io.BytesIO()
    pl.DataFrame({"code": ["US", "DE"], "population": [330000000, 84000000]}).write_parquet(buf)
    parquet_bytes = buf.getvalue()

    class MockResponse:
        status_code = 200
        is_success = True
        content = parquet_bytes
        url = "https://mock.storage.org/countries.parquet"

        def raise_for_status(self):
            pass

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def head(self, *args, **kwargs):
            return MockResponse()
        def get(self, *args, **kwargs):
            return MockResponse()

    import httpx
    monkeypatch.setattr(httpx, "Client", MockClient)

    # Test connection
    test_res = connector.test_connection({"protocol": "http", "base_path": "https://mock.storage.org/countries.parquet"}, {})
    assert test_res.success is True

    # Infer schema from remote HTTP endpoint
    schema = connector.infer_schema(
        {"protocol": "http", "base_path": "https://mock.storage.org"},
        {},
        {"path": "countries.parquet"},
    )
    assert len(schema.columns) == 2
    col_names = [c.name for c in schema.columns]
    assert "code" in col_names
    assert "population" in col_names

    # Preview from remote HTTP endpoint
    prev = connector.preview(
        {"protocol": "http", "base_path": "https://mock.storage.org"},
        {},
        {"path": "countries.parquet"},
        limit=1,
    )
    assert len(prev.rows) == 1
    assert prev.rows[0]["code"] == "US"


# =========================================================================
# 8. Error Handling
# =========================================================================

def test_parquet_error_handling(tmp_path: Path):
    connector = ParquetConnector()

    # Missing file path
    with pytest.raises(SchemaInferenceError) as exc_info:
        connector.infer_schema({}, {}, {"path": str(tmp_path / "does_not_exist.parquet")})
    assert "does not exist" in str(exc_info.value).lower()

    # Corrupt / non-parquet file
    corrupt_file = tmp_path / "corrupt.parquet"
    corrupt_file.write_text("THIS IS NOT A VALID PARQUET FILE CONTENT", encoding="utf-8")

    with pytest.raises(SchemaInferenceError) as exc_info:
        connector.infer_schema({}, {}, {"path": str(corrupt_file)})
    assert "parquet" in str(exc_info.value).lower()

    with pytest.raises(PreviewError) as exc_info:
        connector.preview({}, {}, {"path": str(corrupt_file)})
    assert "parquet preview failed" in str(exc_info.value).lower()

