"""Complete test suite for the JSON Connector.

Covers:
1. Standard JSON array ([{...}, {...}]) single file.
2. JSON Lines / NDJSON ({...}\n{...}\n) single file.
3. Multiple JSON files in a folder.
4. Recursive nested subfolders.
5. Column projection (table_options["columns"]).
6. Nested structures (lists, structs).
7. Reusable Connection integration in CatalogService and connections.yaml.
8. Remote HTTP JSON endpoint loading.
9. Error handling for non-existent files and corrupt JSON syntax.
"""

import json
from pathlib import Path

import pytest

from det.catalog import config as catalog_config
from det.catalog.service import CatalogService
from det.connectors.errors import PreviewError, SchemaInferenceError
from det.connectors.files.json_connector import JSONConnector


@pytest.fixture(autouse=True)
def isolate_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".det"
    config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(catalog_config, "CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(catalog_config, "CONFIG_DIR", config_dir)


# =========================================================================
# 1. Standard JSON Array
# =========================================================================

def test_json_standard_array_file(tmp_path: Path):
    connector = JSONConnector()
    file_path = tmp_path / "users.json"

    data = [
        {"user_id": 1, "username": "alice", "active": True, "score": 92.5},
        {"user_id": 2, "username": "bob", "active": False, "score": 78.0},
        {"user_id": 3, "username": "charlie", "active": True, "score": 88.3},
    ]
    file_path.write_text(json.dumps(data), encoding="utf-8")

    schema = connector.infer_schema({}, {}, {"path": str(file_path), "json_format": "array"})
    assert len(schema.columns) == 4
    col_names = [c.name for c in schema.columns]
    assert col_names == ["user_id", "username", "active", "score"]
    assert schema.row_count_estimate == 3

    prev = connector.preview({}, {}, {"path": str(file_path), "json_format": "array"}, limit=2)
    assert len(prev.rows) == 2
    assert prev.rows[0]["username"] == "alice"
    assert prev.rows[1]["score"] == 78.0


# =========================================================================
# 2. JSON Lines / NDJSON
# =========================================================================

def test_json_ndjson_lines_file(tmp_path: Path):
    connector = JSONConnector()
    file_path = tmp_path / "events.ndjson"

    lines = [
        json.dumps({"event": "click", "count": 10}),
        json.dumps({"event": "hover", "count": 25}),
        json.dumps({"event": "submit", "count": 5}),
    ]
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Auto-detect should identify NDJSON based on extension / content
    schema = connector.infer_schema({}, {}, {"path": str(file_path)})
    assert len(schema.columns) == 2
    assert [c.name for c in schema.columns] == ["event", "count"]
    assert schema.row_count_estimate == 3

    prev = connector.preview({}, {}, {"path": str(file_path)}, limit=2)
    assert len(prev.rows) == 2
    assert prev.rows[0]["event"] == "click"
    assert prev.rows[1]["count"] == 25


# =========================================================================
# 3. Multiple JSON Files in a Folder
# =========================================================================

def test_json_multiple_files_in_folder(tmp_path: Path):
    connector = JSONConnector()
    folder = tmp_path / "batch_json"
    folder.mkdir()

    (folder / "b1.json").write_text(json.dumps([{"id": 1, "v": "A"}, {"id": 2, "v": "B"}]), encoding="utf-8")
    (folder / "b2.json").write_text(json.dumps([{"id": 3, "v": "C"}, {"id": 4, "v": "D"}]), encoding="utf-8")

    schema = connector.infer_schema({}, {}, {
        "path": str(folder),
        "file_selection": "folder",
        "file_pattern": "*.json",
        "json_format": "array",
    })
    assert len(schema.columns) == 2
    assert schema.row_count_estimate == 4

    prev = connector.preview({}, {}, {
        "path": str(folder),
        "file_selection": "folder",
        "json_format": "array",
    }, limit=10)
    assert len(prev.rows) == 4
    ids = [r["id"] for r in prev.rows]
    assert sorted(ids) == [1, 2, 3, 4]


# =========================================================================
# 4. Recursive Nested Subfolders
# =========================================================================

def test_json_recursive_nested_subfolders(tmp_path: Path):
    connector = JSONConnector()
    root_dir = tmp_path / "deep_logs"
    s1 = root_dir / "2024" / "01"
    s2 = root_dir / "2024" / "02"
    s1.mkdir(parents=True)
    s2.mkdir(parents=True)

    (s1 / "log.ndjson").write_text(json.dumps({"ts": 100, "msg": "ok"}) + "\n", encoding="utf-8")
    (s2 / "log.ndjson").write_text(json.dumps({"ts": 200, "msg": "warn"}) + "\n", encoding="utf-8")

    schema = connector.infer_schema({}, {}, {
        "path": str(root_dir),
        "file_selection": "recursive",
        "file_pattern": "*.ndjson",
        "json_format": "lines",
    })
    assert len(schema.columns) == 2
    assert schema.row_count_estimate == 2

    prev = connector.preview({}, {}, {
        "path": str(root_dir),
        "file_selection": "recursive",
        "file_pattern": "*.ndjson",
        "json_format": "lines",
    }, limit=10)
    assert len(prev.rows) == 2
    messages = {r["msg"] for r in prev.rows}
    assert messages == {"ok", "warn"}


# =========================================================================
# 5. Column Projection
# =========================================================================

def test_json_column_projection(tmp_path: Path):
    connector = JSONConnector()
    file_path = tmp_path / "wide.json"

    file_path.write_text(json.dumps([
        {"c1": 1, "c2": "A", "c3": 10.5, "c4": True},
        {"c1": 2, "c2": "B", "c3": 20.0, "c4": False},
    ]), encoding="utf-8")

    schema = connector.infer_schema({}, {}, {
        "path": str(file_path),
        "columns": "c1, c3",
        "json_format": "array",
    })
    assert [c.name for c in schema.columns] == ["c1", "c3"]

    prev = connector.preview({}, {}, {
        "path": str(file_path),
        "columns": "c1, c3",
        "json_format": "array",
    })
    assert prev.columns == ["c1", "c3"]
    assert len(prev.rows) == 2
    assert "c2" not in prev.rows[0]


# =========================================================================
# 6. Nested Objects and Arrays
# =========================================================================

def test_json_nested_structures(tmp_path: Path):
    connector = JSONConnector()
    file_path = tmp_path / "nested.ndjson"

    line = json.dumps({
        "id": 1,
        "details": {"role": "admin", "level": 5},
        "tags": ["prod", "us-east"],
    })
    file_path.write_text(line + "\n", encoding="utf-8")

    schema = connector.infer_schema({}, {}, {"path": str(file_path)})
    assert len(schema.columns) == 3
    col_names = [c.name for c in schema.columns]
    assert "details" in col_names
    assert "tags" in col_names

    prev = connector.preview({}, {}, {"path": str(file_path)})
    assert len(prev.rows) == 1
    assert prev.rows[0]["id"] == 1
    # Formatted preview rows serialize dicts/structs cleanly
    assert "admin" in str(prev.rows[0]["details"])


# =========================================================================
# 7. Reusable Connection & CatalogService Workflow
# =========================================================================

def test_json_catalog_service_integration(tmp_path: Path):
    cat_yaml = tmp_path / "catalog.yaml"
    service = CatalogService()
    service.create_catalog(cat_yaml, "JSON Catalog")

    storage_dir = tmp_path / "json_vault"
    storage_dir.mkdir()

    records = [{"item": "Widget", "cost": 12.5}, {"item": "Gadget", "cost": 45.0}]
    (storage_dir / "items.json").write_text(json.dumps(records), encoding="utf-8")

    # Create reusable connection
    state = service.create_connection(
        name="JSON Store Connection",
        connector="json",
        config={"protocol": "local", "base_path": str(storage_dir)},
        credentials={"password": "VaultSecretKey"},
        description="Local store for JSON records",
    )
    conn_obj = state.sources[0]
    assert conn_obj["name"] == "JSON Store Connection"
    assert "password" not in conn_obj["config"]

    # Password must not be in catalog YAML
    assert "VaultSecretKey" not in cat_yaml.read_text(encoding="utf-8")

    # Create table referencing connection
    state = service.create_table(
        name="items",
        namespace="default",
        connector="json",
        connection_id=conn_obj["id"],
        options={"path": "items.json", "json_format": "array"},
    )
    assert len(state.categories[0]["tables"]) == 1

    # Infer schema
    schema = service.infer_table_schema(
        connector_id="json",
        connection_id=conn_obj["id"],
        table_options={"path": "items.json", "json_format": "array"},
    )
    assert len(schema.columns) == 2
    assert schema.columns[0].name == "item"

    # Preview data
    preview = service.preview_table_data(
        connector_id="json",
        connection_id=conn_obj["id"],
        table_options={"path": "items.json", "json_format": "array"},
        limit=5,
    )
    assert len(preview.rows) == 2
    assert preview.rows[0]["item"] == "Widget"


# =========================================================================
# 8. Remote HTTP JSON Endpoint
# =========================================================================

def test_json_remote_http_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    connector = JSONConnector()
    remote_data = json.dumps([{"city": "Paris", "temp": 19.5}, {"city": "Tokyo", "temp": 24.0}]).encode("utf-8")

    class MockResponse:
        status_code = 200
        is_success = True
        content = remote_data
        url = "https://mock.weather.io/cities.json"

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
    res = connector.test_connection({"protocol": "http", "base_path": "https://mock.weather.io/cities.json"}, {})
    assert res.success is True

    # Infer schema
    schema = connector.infer_schema(
        {"protocol": "http", "base_path": "https://mock.weather.io"},
        {},
        {"path": "cities.json", "json_format": "array"},
    )
    assert len(schema.columns) == 2
    assert [c.name for c in schema.columns] == ["city", "temp"]

    # Preview data
    prev = connector.preview(
        {"protocol": "http", "base_path": "https://mock.weather.io"},
        {},
        {"path": "cities.json", "json_format": "array"},
        limit=1,
    )
    assert len(prev.rows) == 1
    assert prev.rows[0]["city"] == "Paris"


# =========================================================================
# 9. Error Handling
# =========================================================================

def test_json_error_handling(tmp_path: Path):
    connector = JSONConnector()

    # Missing file
    with pytest.raises(SchemaInferenceError) as exc_info:
        connector.infer_schema({}, {}, {"path": str(tmp_path / "not_found.json")})
    assert "does not exist" in str(exc_info.value).lower()

    # Malformed JSON
    broken_file = tmp_path / "broken.json"
    broken_file.write_text("{this is not valid json at all", encoding="utf-8")

    with pytest.raises(SchemaInferenceError) as exc_info:
        connector.infer_schema({}, {}, {"path": str(broken_file)})
    assert "failed" in str(exc_info.value).lower()

    with pytest.raises(PreviewError) as exc_info:
        connector.preview({}, {}, {"path": str(broken_file)})
    assert "failed" in str(exc_info.value).lower()

