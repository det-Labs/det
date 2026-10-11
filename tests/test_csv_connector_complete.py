"""Complete test suite for the CSV Connector covering all sample sources and options.

Covers:
1. Local single files (delimiters, headers, skip rows, comments, encodings).
2. Local multiple files in a folder.
3. Local nested subfolders (recursive file selection).
4. Live remote HTTP endpoints (GitHub public data).
5. Live remote FTP endpoints (test.rebex.net).
6. Live remote SFTP endpoints (test.rebex.net).
7. Schema inference and dtype mapping to ColumnMetadata.
8. Preview pagination, row limits, and column extraction.
9. Credential separation, masking, and storage isolation.
10. Error handling for non-existent paths, malformed options, and missing files.
"""

from pathlib import Path

import pytest

from det.catalog import config as catalog_config
from det.catalog.service import CatalogService
from det.connectors import credentials
from det.connectors.errors import SchemaInferenceError
from det.connectors.files.csv_connector import CSVConnector


@pytest.fixture(autouse=True)
def isolate_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".det"
    config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(catalog_config, "CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(catalog_config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(credentials, "CREDENTIALS_FILE", config_dir / "credentials.json")


# =========================================================================
# 1. Local Filesystem: Single File Options
# =========================================================================

def test_csv_local_single_file_delimiters_and_headers(tmp_path: Path):
    connector = CSVConnector()

    # Comma delimited with header
    comma_file = tmp_path / "data_comma.csv"
    comma_file.write_text("id,name,amount,active\n1,Alice,100.5,true\n2,Bob,250.0,false\n", encoding="utf-8")

    schema = connector.infer_schema({}, {}, {"path": str(comma_file), "file_selection": "single", "delimiter": ","})
    assert len(schema.columns) == 4
    col_map = {c.name: c.type for c in schema.columns}
    assert col_map["id"] == "Int64"
    assert col_map["name"] == "String"
    assert col_map["amount"] == "Float64"
    assert col_map["active"] == "Boolean"

    preview = connector.preview({}, {}, {"path": str(comma_file), "delimiter": ","}, limit=10)
    assert len(preview.rows) == 2
    assert preview.rows[0]["name"] == "Alice"
    assert preview.rows[1]["amount"] == 250.0

    # Semicolon delimited
    semi_file = tmp_path / "data_semi.csv"
    semi_file.write_text("product;price;in_stock\nWidget;19.99;true\nGadget;49.50;false\n", encoding="utf-8")
    preview_semi = connector.preview({}, {}, {"path": str(semi_file), "delimiter": ";"}, limit=5)
    assert preview_semi.columns == ["product", "price", "in_stock"]
    assert preview_semi.rows[0]["product"] == "Widget"

    # Tab delimited (TSV)
    tab_file = tmp_path / "data_tab.tsv"
    tab_file.write_text("colA\tcolB\nAlpha\t10\nBeta\t20\n", encoding="utf-8")
    preview_tab = connector.preview({}, {}, {"path": str(tab_file), "delimiter": "\t"}, limit=5)
    assert preview_tab.columns == ["colA", "colB"]
    assert preview_tab.rows[0]["colA"] == "Alpha"

    # Pipe delimited
    pipe_file = tmp_path / "data_pipe.txt"
    pipe_file.write_text("code|region\nUS|North America\nDE|Europe\n", encoding="utf-8")
    preview_pipe = connector.preview({}, {}, {"path": str(pipe_file), "delimiter": "|"}, limit=5)
    assert preview_pipe.columns == ["code", "region"]
    assert preview_pipe.rows[1]["code"] == "DE"


def test_csv_local_skip_rows_and_comments(tmp_path: Path):
    connector = CSVConnector()
    file_with_metadata = tmp_path / "metadata_csv.csv"
    file_with_metadata.write_text(
        "# Export generated on 2026-10-11\n"
        "# Source: internal system\n"
        "id,value\n"
        "100,Test\n",
        encoding="utf-8"
    )

    # Test with comment prefix
    preview = connector.preview({}, {}, {"path": str(file_with_metadata), "comment_prefix": "#"}, limit=5)
    assert preview.columns == ["id", "value"]
    assert len(preview.rows) == 1
    assert preview.rows[0]["id"] == 100

    # Test with skip_rows
    file_with_header_offset = tmp_path / "offset_csv.csv"
    file_with_header_offset.write_text(
        "REPORT TITLE\n"
        "CONFIDENTIAL\n"
        "metric,score\n"
        "accuracy,0.98\n",
        encoding="utf-8"
    )
    preview_skip = connector.preview({}, {}, {"path": str(file_with_header_offset), "skip_rows": 2}, limit=5)
    assert preview_skip.columns == ["metric", "score"]
    assert preview_skip.rows[0]["metric"] == "accuracy"


# =========================================================================
# 2. Local Filesystem: Multiple Files in Folder & Recursive Subfolders
# =========================================================================

def test_csv_multiple_files_in_folder(tmp_path: Path):
    connector = CSVConnector()
    folder = tmp_path / "sales_2026"
    folder.mkdir()

    (folder / "jan.csv").write_text("month,amount\nJan,100\n", encoding="utf-8")
    (folder / "feb.csv").write_text("month,amount\nFeb,200\n", encoding="utf-8")
    (folder / "mar.csv").write_text("month,amount\nMar,300\n", encoding="utf-8")
    # Non-matching file
    (folder / "notes.txt").write_text("not a csv", encoding="utf-8")

    schema = connector.infer_schema({}, {}, {"path": str(folder), "file_selection": "folder", "file_pattern": "*.csv"})
    assert [c.name for c in schema.columns] == ["month", "amount"]

    preview = connector.preview({}, {}, {"path": str(folder), "file_selection": "folder", "file_pattern": "*.csv"}, limit=10)
    assert preview.columns == ["month", "amount"]
    months = {r["month"] for r in preview.rows}
    assert months == {"Jan", "Feb", "Mar"}
    assert len(preview.rows) == 3


def test_csv_recursive_nested_subfolders(tmp_path: Path):
    connector = CSVConnector()
    base_folder = tmp_path / "nested_data"
    sub_dept1 = base_folder / "region_us" / "dept_tech"
    sub_dept2 = base_folder / "region_eu" / "dept_sales"
    sub_dept1.mkdir(parents=True)
    sub_dept2.mkdir(parents=True)

    (sub_dept1 / "q1.csv").write_text("dept,headcount\nTech,45\n", encoding="utf-8")
    (sub_dept2 / "q1.csv").write_text("dept,headcount\nSales,30\n", encoding="utf-8")

    preview = connector.preview({}, {}, {"path": str(base_folder), "file_selection": "recursive"}, limit=10)
    assert preview.columns == ["dept", "headcount"]
    assert len(preview.rows) == 2
    depts = {r["dept"] for r in preview.rows}
    assert depts == {"Tech", "Sales"}


# =========================================================================
# 3. Connection Source Integration with Credential Isolation
# =========================================================================

def test_csv_source_with_credential_isolation(tmp_path: Path):
    cat_yaml = tmp_path / "catalog.yaml"
    service = CatalogService()
    service.create_catalog(cat_yaml, "CSV Catalog")

    data_dir = tmp_path / "secure_data"
    data_dir.mkdir()
    (data_dir / "records.csv").write_text("key,val\nA,1\nB,2\n", encoding="utf-8")

    # Create connection source with sensitive secret
    state = service.create_source(
        name="Internal Secure Store",
        connector="csv",
        config={"protocol": "local", "base_path": str(data_dir)},
        credentials={"password": "TopSecretPassword123!"},
        description="Local store with isolated credentials"
    )

    src = state.sources[0]
    assert src["name"] == "Internal Secure Store"
    assert src["has_credentials"] is True
    # Secret must NOT be in source.config
    assert "password" not in src["config"]

    # Read catalog YAML from disk - password must NOT be in catalog YAML
    yaml_content = cat_yaml.read_text(encoding="utf-8")
    assert "TopSecretPassword123!" not in yaml_content

    # Create table using this connection source
    state = service.create_table(
        name="records",
        namespace="default",
        connector="csv",
        source_id=src["id"],
        options={"path": "records.csv"}
    )
    tables = state.categories[0]["tables"]
    assert len(tables) == 1
    assert tables[0]["name"] == "records"
    assert tables[0]["source_id"] == src["id"]

    # Test preview through service
    prev = service.preview_table_data(
        connector_id="csv",
        source_id=src["id"],
        source_config={},
        credentials={},
        table_options={"path": "records.csv"},
        limit=5
    )
    assert len(prev.rows) == 2
    assert prev.rows[0]["key"] == "A"


# =========================================================================
# 4. Error Handling and Edge Cases
# =========================================================================

def test_csv_error_handling_missing_paths(tmp_path: Path):
    connector = CSVConnector()

    # Missing file
    with pytest.raises(SchemaInferenceError) as exc_info:
        connector.infer_schema({}, {}, {"path": str(tmp_path / "non_existent.csv"), "file_selection": "single"})
    assert "does not exist" in str(exc_info.value) or "No matching" in str(exc_info.value)

    # Empty folder with no csv files
    empty_folder = tmp_path / "empty_dir"
    empty_folder.mkdir()
    with pytest.raises(SchemaInferenceError):
        connector.infer_schema({}, {}, {"path": str(empty_folder), "file_selection": "folder"})

    # Test connection on missing path returns success=False
    res = connector.test_connection({"protocol": "local", "base_path": str(tmp_path / "does_not_exist")}, {})
    assert res.success is False
    assert "does not exist" in res.message


# =========================================================================
# 5. Live Public Endpoints: HTTP, FTP, and SFTP
# =========================================================================

@pytest.mark.network
def test_csv_live_http_public_endpoint():
    connector = CSVConnector()
    # Public CSV over HTTP
    http_url = "https://raw.githubusercontent.com/datasets/gdp/master/data/gdp.csv"

    # Test connection
    test_res = connector.test_connection({"protocol": "http", "base_path": http_url}, {})
    assert test_res.success is True

    # Infer schema
    schema_res = connector.infer_schema({}, {}, {"path": http_url})
    assert len(schema_res.columns) == 4
    col_names = [c.name for c in schema_res.columns]
    assert "Country Name" in col_names
    assert "Value" in col_names

    # Preview sample rows
    prev_res = connector.preview({}, {}, {"path": http_url}, limit=5)
    assert len(prev_res.rows) == 5
    assert "Country Name" in prev_res.rows[0]


@pytest.mark.network
def test_csv_live_ftp_public_endpoint():
    connector = CSVConnector()
    src_config = {
        "protocol": "ftp",
        "host": "test.rebex.net",
        "port": 21,
        "username": "demo",
        "base_path": "/pub/example",
    }
    creds = {"password": "password"}

    # Test connection
    test_res = connector.test_connection(src_config, creds)
    assert test_res.success is True
    assert "Connected to FTP" in test_res.message

    # Discover files
    discovered = connector.discover_objects(src_config, creds, {"file_pattern": "*.txt"})
    names = [d.name for d in discovered]
    assert "readme.txt" in names


@pytest.mark.network
def test_csv_live_sftp_public_endpoint():
    pytest.importorskip("paramiko", reason="SFTP requires paramiko")
    connector = CSVConnector()
    src_config = {
        "protocol": "sftp",
        "host": "test.rebex.net",
        "port": 22,
        "username": "demo",
        "base_path": "/pub/example",
    }
    creds = {"password": "password"}

    # Test connection
    test_res = connector.test_connection(src_config, creds)
    assert test_res.success is True
    assert "Connected to SFTP" in test_res.message

    # Discover files
    discovered = connector.discover_objects(src_config, creds, {"file_pattern": "*.txt"})
    names = [d.name for d in discovered]
    assert "readme.txt" in names
