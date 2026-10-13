"""Tests verifying all real sample data files in D:\\Learning\\test\\samples."""

import unittest
from pathlib import Path

import pyarrow as pa

from det.connectors import (
    CSV_CONNECTOR,
    DELTA_CONNECTOR,
    EXCEL_CONNECTOR,
    JSON_CONNECTOR,
    PARQUET_CONNECTOR,
    XML_CONNECTOR,
    scan_builtin,
)
from det.engine import create_session_context, run_sql

SAMPLES_DIR = Path(r"D:\Learning\test\samples")


class RealSamplesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not SAMPLES_DIR.exists():
            raise unittest.SkipTest(f"Samples directory {SAMPLES_DIR} does not exist")

    def setUp(self) -> None:
        self.context = create_session_context()

    def test_csv_multi_file_daily_sales_with_sql(self) -> None:
        sales_dir = SAMPLES_DIR / "csv" / "sales_daily"
        df = scan_builtin(
            self.context,
            CSV_CONNECTOR.guid,
            {
                "path": str(sales_dir),
                "file_pattern": "*.csv",
                "has_header": True,
            },
            SAMPLES_DIR,
        )
        self.context.register_view("sales_daily", df)
        res = run_sql(self.context, "SELECT COUNT(*) AS total_rows FROM sales_daily")
        table = pa.Table.from_batches(res.collect())
        self.assertGreater(table["total_rows"][0].as_py(), 0)

    def test_csv_nested_partition_logs_with_sql(self) -> None:
        logs_dir = SAMPLES_DIR / "csv" / "logs"
        df = scan_builtin(
            self.context,
            CSV_CONNECTOR.guid,
            {
                "path": str(logs_dir),
                "file_pattern": "*.csv",
                "include_subfolders": True,
                "has_header": True,
            },
            SAMPLES_DIR,
        )
        self.context.register_view("audit_logs", df)
        res = run_sql(self.context, "SELECT * FROM audit_logs")
        table = pa.Table.from_batches(res.collect())
        self.assertGreater(len(table), 0)

    def test_excel_multiple_sheets_one_at_a_time_with_sql(self) -> None:
        excel_path = SAMPLES_DIR / "excel" / "financial_report.xlsx"

        # 1. Read sheet "Summary"
        df_summary = scan_builtin(
            self.context,
            EXCEL_CONNECTOR.guid,
            {"path": str(excel_path), "sheet_name": "Summary"},
            SAMPLES_DIR,
        )
        self.context.register_view("fin_summary", df_summary)
        res_summary = run_sql(self.context, "SELECT metric, q1_actual FROM fin_summary")
        t_summary = pa.Table.from_batches(res_summary.collect())
        self.assertEqual(len(t_summary), 3)

        # 2. Read sheet "Department_Budgets"
        df_depts = scan_builtin(
            self.context,
            EXCEL_CONNECTOR.guid,
            {"path": str(excel_path), "sheet_name": "Department_Budgets"},
            SAMPLES_DIR,
        )
        self.context.register_view("fin_depts", df_depts)
        res_depts = run_sql(
            self.context,
            "SELECT department, allocated_usd, spent_usd FROM fin_depts WHERE spent_usd > 300000",
        )
        t_depts = pa.Table.from_batches(res_depts.collect())
        self.assertGreater(len(t_depts), 0)

    def test_json_array_products_with_sql(self) -> None:
        products_path = SAMPLES_DIR / "json" / "products.json"
        df = scan_builtin(
            self.context,
            JSON_CONNECTOR.guid,
            {"path": str(products_path), "json_format": "auto"},
            SAMPLES_DIR,
        )
        self.context.register_view("products", df)
        res = run_sql(self.context, "SELECT * FROM products")
        table = pa.Table.from_batches(res.collect())
        self.assertGreater(len(table), 0)

    def test_json_lines_stream_events_with_sql(self) -> None:
        events_path = SAMPLES_DIR / "json" / "stream_events.ndjson"
        df = scan_builtin(
            self.context,
            JSON_CONNECTOR.guid,
            {"path": str(events_path), "json_format": "lines"},
            SAMPLES_DIR,
        )
        self.context.register_view("stream_events", df)
        res = run_sql(self.context, "SELECT * FROM stream_events")
        table = pa.Table.from_batches(res.collect())
        self.assertGreater(len(table), 0)

    def test_parquet_telemetry_multi_file_with_sql(self) -> None:
        parquet_dir = SAMPLES_DIR / "parquet" / "telemetry"
        df = scan_builtin(
            self.context,
            PARQUET_CONNECTOR.guid,
            {"path": str(parquet_dir), "file_pattern": "*.parquet"},
            SAMPLES_DIR,
        )
        self.context.register_view("telemetry", df)
        res = run_sql(self.context, "SELECT * FROM telemetry")
        table = pa.Table.from_batches(res.collect())
        self.assertGreater(len(table), 0)

    def test_xml_books_and_inventory_multi_file_with_sql(self) -> None:
        # 1. Single XML book catalog
        xml_file = SAMPLES_DIR / "xml" / "book_catalog.xml"
        df_books = scan_builtin(
            self.context,
            XML_CONNECTOR.guid,
            {"path": str(xml_file), "row_tag": "book"},
            SAMPLES_DIR,
        )
        self.context.register_view("books", df_books)
        res_books = run_sql(self.context, "SELECT title, author, price FROM books")
        t_books = pa.Table.from_batches(res_books.collect())
        self.assertGreater(len(t_books), 0)

        # 2. Multi-file XML in inventory/
        inv_dir = SAMPLES_DIR / "xml" / "inventory"
        df_inv = scan_builtin(
            self.context,
            XML_CONNECTOR.guid,
            {"path": str(inv_dir), "file_pattern": "*.xml"},
            SAMPLES_DIR,
        )
        self.context.register_view("inventory", df_inv)
        res_inv = run_sql(self.context, "SELECT * FROM inventory")
        t_inv = pa.Table.from_batches(res_inv.collect())
        self.assertGreater(len(t_inv), 0)

    def test_delta_lake_orders_with_sql(self) -> None:
        delta_path = SAMPLES_DIR / "delta" / "orders"
        df = scan_builtin(
            self.context,
            DELTA_CONNECTOR.guid,
            {"path": str(delta_path)},
            SAMPLES_DIR,
        )
        self.context.register_view("delta_orders", df)
        res = run_sql(
            self.context,
            "SELECT customer, amount, status FROM delta_orders WHERE amount > 50.0 ORDER BY amount DESC",
        )
        table = pa.Table.from_batches(res.collect())
        self.assertGreater(len(table), 0)
        self.assertEqual(table["customer"][0].as_py(), "Charlie")


if __name__ == "__main__":
    unittest.main()
