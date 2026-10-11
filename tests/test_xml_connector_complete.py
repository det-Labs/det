"""Complete test suite for the XML Connector.

Covers:
1. Single XML file with root element records.
2. Specific row tag selection (row_tag="book").
3. Multiple XML files in a folder (folder mode).
4. Recursive nested subfolders (recursive mode).
5. Column projection (table_options["columns"]).
6. Object discovery: discovering row tags for a file and files for a directory.
7. Reusable Connection integration in CatalogService and connections.yaml.
8. Remote HTTP XML endpoint loading.
9. Error handling for missing files and malformed XML syntax.
"""

from pathlib import Path

import pytest

from det.catalog import config as catalog_config
from det.catalog.service import CatalogService
from det.connectors.errors import PreviewError, SchemaInferenceError
from det.connectors.files.xml_connector import XMLConnector


@pytest.fixture(autouse=True)
def isolate_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".det"
    config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(catalog_config, "CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(catalog_config, "CONFIG_DIR", config_dir)


# =========================================================================
# 1. Single XML File
# =========================================================================

def test_xml_single_file_records(tmp_path: Path):
    connector = XMLConnector()
    file_path = tmp_path / "catalog.xml"

    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <catalog>
        <book id="bk101">
            <author>Gambardella, Matthew</author>
            <title>XML Developer's Guide</title>
            <price>44.95</price>
        </book>
        <book id="bk102">
            <author>Ralls, Kim</author>
            <title>Midnight Rain</title>
            <price>5.95</price>
        </book>
    </catalog>
    """
    file_path.write_text(xml_content, encoding="utf-8")

    schema = connector.infer_schema({}, {}, {"path": str(file_path), "row_tag": "book"})
    assert len(schema.columns) == 4
    col_names = [c.name for c in schema.columns]
    assert "id" in col_names
    assert "author" in col_names
    assert "title" in col_names
    assert "price" in col_names
    assert schema.row_count_estimate == 2

    prev = connector.preview({}, {}, {"path": str(file_path), "row_tag": "book"}, limit=1)
    assert len(prev.rows) == 1
    assert prev.rows[0]["id"] == "bk101"
    assert prev.rows[0]["title"] == "XML Developer's Guide"


# =========================================================================
# 2. Row Tag Selection in Deep Hierarchy
# =========================================================================

def test_xml_row_tag_deep_hierarchy(tmp_path: Path):
    connector = XMLConnector()
    file_path = tmp_path / "deep.xml"

    xml_content = """<response status="success">
        <metadata>
            <generated>2024</generated>
        </metadata>
        <data>
            <items>
                <item code="A1"><name>First</name><qty>10</qty></item>
                <item code="B2"><name>Second</name><qty>20</qty></item>
            </items>
        </data>
    </response>"""
    file_path.write_text(xml_content, encoding="utf-8")

    schema = connector.infer_schema({}, {}, {"path": str(file_path), "row_tag": "item"})
    col_names = [c.name for c in schema.columns]
    assert "code" in col_names
    assert "name" in col_names
    assert "qty" in col_names
    assert schema.row_count_estimate == 2

    prev = connector.preview({}, {}, {"path": str(file_path), "row_tag": "item"}, limit=5)
    assert len(prev.rows) == 2
    assert prev.rows[0]["code"] == "A1"
    assert prev.rows[1]["name"] == "Second"


# =========================================================================
# 3. Multiple XML Files in a Folder
# =========================================================================

def test_xml_multiple_files_in_folder(tmp_path: Path):
    connector = XMLConnector()
    folder = tmp_path / "xml_batches"
    folder.mkdir()

    (folder / "part1.xml").write_text("<root><r><id>1</id><val>X</val></r></root>", encoding="utf-8")
    (folder / "part2.xml").write_text("<root><r><id>2</id><val>Y</val></r></root>", encoding="utf-8")

    schema = connector.infer_schema({}, {}, {
        "path": str(folder),
        "file_selection": "folder",
        "file_pattern": "*.xml",
        "row_tag": "r",
    })
    assert len(schema.columns) == 2
    assert schema.row_count_estimate == 2

    prev = connector.preview({}, {}, {
        "path": str(folder),
        "file_selection": "folder",
        "row_tag": "r",
    }, limit=10)
    assert len(prev.rows) == 2
    ids = [r["id"] for r in prev.rows]
    assert sorted(ids) == ["1", "2"]


# =========================================================================
# 4. Recursive Nested Subfolders
# =========================================================================

def test_xml_recursive_nested_subfolders(tmp_path: Path):
    connector = XMLConnector()
    root_dir = tmp_path / "deep_xml"
    s1 = root_dir / "dept_a"
    s2 = root_dir / "dept_b"
    s1.mkdir(parents=True)
    s2.mkdir(parents=True)

    (s1 / "data.xml").write_text("<list><emp><name>John</name></emp></list>", encoding="utf-8")
    (s2 / "data.xml").write_text("<list><emp><name>Jane</name></emp></list>", encoding="utf-8")

    schema = connector.infer_schema({}, {}, {
        "path": str(root_dir),
        "file_selection": "recursive",
        "file_pattern": "*.xml",
        "row_tag": "emp",
    })
    assert len(schema.columns) == 1
    assert schema.columns[0].name == "name"
    assert schema.row_count_estimate == 2

    prev = connector.preview({}, {}, {
        "path": str(root_dir),
        "file_selection": "recursive",
        "row_tag": "emp",
    }, limit=10)
    assert len(prev.rows) == 2
    names = {r["name"] for r in prev.rows}
    assert names == {"John", "Jane"}


# =========================================================================
# 5. Column Projection
# =========================================================================

def test_xml_column_projection(tmp_path: Path):
    connector = XMLConnector()
    file_path = tmp_path / "proj.xml"

    xml_content = "<records><rec><c1>1</c1><c2>2</c2><c3>3</c3></rec></records>"
    file_path.write_text(xml_content, encoding="utf-8")

    schema = connector.infer_schema({}, {}, {
        "path": str(file_path),
        "columns": "c1, c3",
        "row_tag": "rec",
    })
    assert [c.name for c in schema.columns] == ["c1", "c3"]

    prev = connector.preview({}, {}, {
        "path": str(file_path),
        "columns": "c1, c3",
        "row_tag": "rec",
    })
    assert prev.columns == ["c1", "c3"]
    assert "c2" not in prev.rows[0]


# =========================================================================
# 6. Object Discovery (Tags & Files)
# =========================================================================

def test_xml_discovery_tags_and_files(tmp_path: Path):
    connector = XMLConnector()
    folder = tmp_path / "xml_discovery"
    folder.mkdir()

    file_1 = folder / "doc1.xml"
    file_1.write_text("<root><user/><audit/><settings/></root>", encoding="utf-8")

    file_2 = folder / "doc2.xml"
    file_2.write_text("<root><item/></root>", encoding="utf-8")

    # Discover files in folder
    file_objs = connector.discover_objects({"base_path": str(folder)}, {})
    assert len(file_objs) == 2
    assert {o.name for o in file_objs} == {"doc1.xml", "doc2.xml"}

    # Discover tags in single file
    tag_objs = connector.discover_objects({"base_path": str(folder)}, {}, {"path": "doc1.xml"})
    assert len(tag_objs) == 3
    tag_names = {t.name for t in tag_objs}
    assert tag_names == {"audit", "settings", "user"}


# =========================================================================
# 7. Reusable Connection & CatalogService Workflow
# =========================================================================

def test_xml_catalog_service_integration(tmp_path: Path):
    cat_yaml = tmp_path / "catalog.yaml"
    service = CatalogService()
    service.create_catalog(cat_yaml, "XML Catalog")

    storage_dir = tmp_path / "xml_feed_dir"
    storage_dir.mkdir()

    xml_feed = "<feed><article><id>art-1</id><title>Breaking News</title></article></feed>"
    (storage_dir / "feed.xml").write_text(xml_feed, encoding="utf-8")

    # Create connection
    state = service.create_connection(
        name="XML Feed Store",
        connector="xml",
        config={"protocol": "local", "base_path": str(storage_dir)},
        credentials={"password": "XMLSecretApiKey"},
        description="Local store for XML feeds",
    )
    conn_obj = state.sources[0]
    assert conn_obj["name"] == "XML Feed Store"
    assert "password" not in conn_obj["config"]

    # Secret must not be in catalog YAML
    assert "XMLSecretApiKey" not in cat_yaml.read_text(encoding="utf-8")

    # Create table referencing connection
    state = service.create_table(
        name="feed",
        namespace="default",
        connector="xml",
        connection_id=conn_obj["id"],
        options={"path": "feed.xml", "row_tag": "article"},
    )
    assert len(state.categories[0]["tables"]) == 1

    # Infer schema
    schema = service.infer_table_schema(
        connector_id="xml",
        connection_id=conn_obj["id"],
        table_options={"path": "feed.xml", "row_tag": "article"},
    )
    assert len(schema.columns) == 2
    assert schema.columns[0].name == "id"

    # Preview data
    preview = service.preview_table_data(
        connector_id="xml",
        connection_id=conn_obj["id"],
        table_options={"path": "feed.xml", "row_tag": "article"},
        limit=5,
    )
    assert len(preview.rows) == 1
    assert preview.rows[0]["title"] == "Breaking News"


# =========================================================================
# 8. Remote HTTP XML Endpoint
# =========================================================================

def test_xml_remote_http_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    connector = XMLConnector()
    remote_data = b"<rates><curr code='USD'><val>1.0</val></curr><curr code='EUR'><val>0.92</val></curr></rates>"

    class MockResponse:
        status_code = 200
        is_success = True
        content = remote_data
        url = "https://mock.rates.io/latest.xml"

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
    res = connector.test_connection({"protocol": "http", "base_path": "https://mock.rates.io/latest.xml"}, {})
    assert res.success is True

    # Infer schema
    schema = connector.infer_schema(
        {"protocol": "http", "base_path": "https://mock.rates.io"},
        {},
        {"path": "latest.xml", "row_tag": "curr"},
    )
    assert len(schema.columns) == 2
    assert [c.name for c in schema.columns] == ["code", "val"]

    # Preview data
    prev = connector.preview(
        {"protocol": "http", "base_path": "https://mock.rates.io"},
        {},
        {"path": "latest.xml", "row_tag": "curr"},
        limit=1,
    )
    assert len(prev.rows) == 1
    assert prev.rows[0]["code"] == "USD"


# =========================================================================
# 9. Error Handling
# =========================================================================

def test_xml_error_handling(tmp_path: Path):
    connector = XMLConnector()

    # Missing file
    with pytest.raises(SchemaInferenceError) as exc_info:
        connector.infer_schema({}, {}, {"path": str(tmp_path / "not_there.xml")})
    assert "does not exist" in str(exc_info.value).lower()

    # Malformed XML syntax
    corrupt_file = tmp_path / "broken.xml"
    corrupt_file.write_text("<root><unclosed_tag></root>", encoding="utf-8")

    with pytest.raises(SchemaInferenceError) as exc_info:
        connector.infer_schema({}, {}, {"path": str(corrupt_file)})
    assert "failed" in str(exc_info.value).lower()

    with pytest.raises(PreviewError) as exc_info:
        connector.preview({}, {}, {"path": str(corrupt_file)})
    assert "failed" in str(exc_info.value).lower()

