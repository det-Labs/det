"""Tests for ExcelConnector SQL generation and field schemas."""

from det.extensions.builtins.excel import ExcelConnector
from det.extensions.registry import global_registry


def test_excel_connector_registered_in_global_registry() -> None:
    """Verify ExcelConnector is present in global registry."""
    connector_cls = global_registry.get("excel")
    assert connector_cls is ExcelConnector


def test_excel_connector_sql_generation() -> None:
    """Verify ExcelConnector generates read_xlsx with sheet and header options."""
    conn = ExcelConnector()
    sql_default = conn.get_read_sql({"path": "data/sales.xlsx"})
    assert sql_default == "read_xlsx('data/sales.xlsx', header=true)"

    sql_sheet = conn.get_read_sql({"path": "data/sales.xlsx", "sheet": "Q1", "header": False})
    assert sql_sheet == "read_xlsx('data/sales.xlsx', sheet='Q1', header=false)"


def test_excel_connector_fields() -> None:
    """Verify ExcelConnector defines path, sheet, and header fields."""
    fields = ExcelConnector.get_fields()
    field_names = [f.name for f in fields]
    assert "path" in field_names
    assert "sheet" in field_names
    assert "header" in field_names

