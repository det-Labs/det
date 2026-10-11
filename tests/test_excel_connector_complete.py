"""Complete test suite for the Microsoft Excel Connector.

Covers:
1. Local single workbook (.xlsx) with default first sheet (various dtypes: string, int, float, date).
2. Multi-sheet workbook with sheet selection (sheet_name="Detailed").
3. Header skipping (skip_rows=2, has_header=True).
4. Sheet discovery for a workbook (type="sheet") and file discovery in folder (type="file").
5. Multiple Excel workbooks in a folder (file_selection="folder").
6. Column projection (table_options["columns"]).
7. Reusable Connection integration in CatalogService and connections.yaml.
8. Remote HTTP workbook downloading and parsing.
9. Error handling for non-existent files and corrupt workbooks.
"""

import io
from datetime import date
from pathlib import Path

import openpyxl
import pytest

from det.catalog import config as catalog_config
from det.catalog.service import CatalogService
from det.connectors.errors import PreviewError, SchemaInferenceError
from det.connectors.files.excel_connector import ExcelConnector


@pytest.fixture(autouse=True)
def isolate_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / ".det"
    config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(catalog_config, "CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(catalog_config, "CONFIG_DIR", config_dir)


# =========================================================================
# 1. Single Workbook Default Sheet & Types
# =========================================================================

def test_excel_single_workbook_first_sheet(tmp_path: Path):
    connector = ExcelConnector()
    wb_path = tmp_path / "financials.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Overview"
    ws.append(["dept", "budget", "headcount", "is_approved", "review_date"])
    ws.append(["Engineering", 150000.5, 45, True, date(2024, 5, 1)])
    ws.append(["Marketing", 85000.0, 20, False, date(2024, 5, 2)])
    ws.append(["Sales", 120000.0, 35, True, date(2024, 5, 3)])
    wb.save(wb_path)

    schema = connector.infer_schema({}, {}, {"path": str(wb_path)})
    assert len(schema.columns) == 5
    col_names = [c.name for c in schema.columns]
    assert col_names == ["dept", "budget", "headcount", "is_approved", "review_date"]
    assert schema.row_count_estimate == 3

    prev = connector.preview({}, {}, {"path": str(wb_path)}, limit=2)
    assert len(prev.rows) == 2
    assert prev.rows[0]["dept"] == "Engineering"
    assert prev.rows[0]["headcount"] == 45
    assert prev.rows[1]["dept"] == "Marketing"


# =========================================================================
# 2. Multi-Sheet Selection
# =========================================================================

def test_excel_multi_sheet_selection(tmp_path: Path):
    connector = ExcelConnector()
    wb_path = tmp_path / "multi_sheet.xlsx"

    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Summary"
    ws1.append(["total_rev", "year"])
    ws1.append([999999, 2024])

    ws2 = wb.create_sheet(title="Breakdown")
    ws2.append(["product", "units", "margin"])
    ws2.append(["Laptop", 120, 0.25])
    ws2.append(["Phone", 350, 0.35])
    wb.save(wb_path)

    # Read specific sheet
    schema = connector.infer_schema({}, {}, {"path": str(wb_path), "sheet_name": "Breakdown"})
    assert [c.name for c in schema.columns] == ["product", "units", "margin"]
    assert schema.row_count_estimate == 2

    prev = connector.preview({}, {}, {"path": str(wb_path), "sheet_name": "Breakdown"}, limit=5)
    assert len(prev.rows) == 2
    assert prev.rows[0]["product"] == "Laptop"
    assert prev.rows[1]["units"] == 350


# =========================================================================
# 3. Skip Rows & Header Handling
# =========================================================================

def test_excel_skip_rows_metadata(tmp_path: Path):
    connector = ExcelConnector()
    wb_path = tmp_path / "with_metadata.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["CONFIDENTIAL FINANCIAL REPORT"])
    ws.append(["Generated on 2024-06-01"])
    ws.append(["account_id", "balance"])
    ws.append(["ACC-001", 5400.0])
    ws.append(["ACC-002", 12300.5])
    wb.save(wb_path)

    schema = connector.infer_schema({}, {}, {
        "path": str(wb_path),
        "skip_rows": 2,
        "has_header": True,
    })
    col_names = [c.name for c in schema.columns]
    assert "account_id" in col_names
    assert "balance" in col_names

    prev = connector.preview({}, {}, {
        "path": str(wb_path),
        "skip_rows": 2,
        "has_header": True,
    })
    assert len(prev.rows) == 2
    assert prev.rows[0]["account_id"] == "ACC-001"


# =========================================================================
# 4. Sheet Discovery and Folder File Discovery
# =========================================================================

def test_excel_discovery_sheets_and_files(tmp_path: Path):
    connector = ExcelConnector()
    folder = tmp_path / "reports_dir"
    folder.mkdir()

    wb1 = openpyxl.Workbook()
    wb1.active.title = "Q1_Data"
    wb1.create_sheet("Q1_Audit")
    wb1.save(folder / "q1.xlsx")

    wb2 = openpyxl.Workbook()
    wb2.active.title = "Q2_Data"
    wb2.save(folder / "q2.xlsx")

    # Discover files in folder
    file_objs = connector.discover_objects({"base_path": str(folder)}, {})
    assert len(file_objs) == 2
    assert {o.name for o in file_objs} == {"q1.xlsx", "q2.xlsx"}

    # Discover sheets in single workbook
    sheet_objs = connector.discover_objects({"base_path": str(folder)}, {}, {"path": "q1.xlsx"})
    assert len(sheet_objs) == 2
    assert [s.name for s in sheet_objs] == ["Q1_Data", "Q1_Audit"]
    assert sheet_objs[0].type == "sheet"


# =========================================================================
# 5. Multiple Excel Files in Folder
# =========================================================================

def test_excel_multiple_files_in_folder(tmp_path: Path):
    connector = ExcelConnector()
    batch_dir = tmp_path / "monthly_sheets"
    batch_dir.mkdir()

    for month, val in [("jan", 10), ("feb", 20), ("mar", 30)]:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Data"
        ws.append(["month", "value"])
        ws.append([month, val])
        wb.save(batch_dir / f"{month}.xlsx")

    schema = connector.infer_schema({}, {}, {
        "path": str(batch_dir),
        "file_selection": "folder",
        "file_pattern": "*.xlsx",
    })
    assert len(schema.columns) == 2
    assert schema.row_count_estimate == 3

    prev = connector.preview({}, {}, {
        "path": str(batch_dir),
        "file_selection": "folder",
    }, limit=10)
    assert len(prev.rows) == 3
    months = {r["month"] for r in prev.rows}
    assert months == {"jan", "feb", "mar"}


# =========================================================================
# 6. Column Projection
# =========================================================================

def test_excel_column_projection(tmp_path: Path):
    connector = ExcelConnector()
    wb_path = tmp_path / "projection.xlsx"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["col1", "col2", "col3", "col4"])
    ws.append([1, "A", 10.0, True])
    ws.append([2, "B", 20.0, False])
    wb.save(wb_path)

    schema = connector.infer_schema({}, {}, {
        "path": str(wb_path),
        "columns": "col1, col3",
    })
    assert [c.name for c in schema.columns] == ["col1", "col3"]

    prev = connector.preview({}, {}, {
        "path": str(wb_path),
        "columns": "col1, col3",
    })
    assert prev.columns == ["col1", "col3"]
    assert len(prev.rows) == 2
    assert "col2" not in prev.rows[0]


# =========================================================================
# 7. Reusable Connection & CatalogService Workflow
# =========================================================================

def test_excel_catalog_service_integration(tmp_path: Path):
    cat_yaml = tmp_path / "catalog.yaml"
    service = CatalogService()
    service.create_catalog(cat_yaml, "Excel Catalog")

    storage_dir = tmp_path / "excel_store"
    storage_dir.mkdir()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["store_id", "city", "sales"])
    ws.append(["S01", "New York", 95000])
    ws.append(["S02", "London", 82000])
    wb.save(storage_dir / "stores.xlsx")

    # Create connection
    state = service.create_connection(
        name="Excel Store Connection",
        connector="excel",
        config={"protocol": "local", "base_path": str(storage_dir)},
        credentials={"password": "ExcelSecretPassword"},
        description="Folder of Excel files",
    )
    conn_obj = state.sources[0]
    assert conn_obj["name"] == "Excel Store Connection"
    assert "password" not in conn_obj["config"]

    # Password must not be in catalog YAML
    assert "ExcelSecretPassword" not in cat_yaml.read_text(encoding="utf-8")

    # Create table referencing connection
    state = service.create_table(
        name="stores",
        namespace="default",
        connector="excel",
        connection_id=conn_obj["id"],
        options={"path": "stores.xlsx"},
    )
    assert len(state.categories[0]["tables"]) == 1

    # Infer schema
    schema = service.infer_table_schema(
        connector_id="excel",
        connection_id=conn_obj["id"],
        table_options={"path": "stores.xlsx"},
    )
    assert len(schema.columns) == 3
    assert schema.columns[0].name == "store_id"

    # Preview data
    preview = service.preview_table_data(
        connector_id="excel",
        connection_id=conn_obj["id"],
        table_options={"path": "stores.xlsx"},
        limit=5,
    )
    assert len(preview.rows) == 2
    assert preview.rows[0]["city"] == "New York"


# =========================================================================
# 8. Remote HTTP Workbook Endpoint
# =========================================================================

def test_excel_remote_http_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    connector = ExcelConnector()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ticker", "price"])
    ws.append(["AAPL", 185.5])
    ws.append(["GOOG", 175.2])
    buf = io.BytesIO()
    wb.save(buf)
    excel_bytes = buf.getvalue()

    class MockResponse:
        status_code = 200
        is_success = True
        content = excel_bytes
        url = "https://mock.financials.com/stocks.xlsx"

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
    res = connector.test_connection({"protocol": "http", "base_path": "https://mock.financials.com/stocks.xlsx"}, {})
    assert res.success is True

    # Infer schema from HTTP
    schema = connector.infer_schema(
        {"protocol": "http", "base_path": "https://mock.financials.com"},
        {},
        {"path": "stocks.xlsx"},
    )
    assert len(schema.columns) == 2
    assert [c.name for c in schema.columns] == ["ticker", "price"]

    # Preview from HTTP
    prev = connector.preview(
        {"protocol": "http", "base_path": "https://mock.financials.com"},
        {},
        {"path": "stocks.xlsx"},
        limit=1,
    )
    assert len(prev.rows) == 1
    assert prev.rows[0]["ticker"] == "AAPL"


# =========================================================================
# 9. Error Handling
# =========================================================================

def test_excel_error_handling(tmp_path: Path):
    connector = ExcelConnector()

    # Missing file
    with pytest.raises(SchemaInferenceError) as exc_info:
        connector.infer_schema({}, {}, {"path": str(tmp_path / "missing.xlsx")})
    assert "does not exist" in str(exc_info.value).lower()

    # Corrupt / not an Excel file
    corrupt_file = tmp_path / "corrupt.xlsx"
    corrupt_file.write_text("NOT A VALID EXCEL FILE", encoding="utf-8")

    with pytest.raises(SchemaInferenceError) as exc_info:
        connector.infer_schema({}, {}, {"path": str(corrupt_file)})
    assert "failed" in str(exc_info.value).lower()

    with pytest.raises(PreviewError) as exc_info:
        connector.preview({}, {}, {"path": str(corrupt_file)})
    assert "failed" in str(exc_info.value).lower()

