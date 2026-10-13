"""Tests for joining multiple data connections on common keys using DataFusion SQL."""

import unittest
from pathlib import Path

import pyarrow as pa

from det.connectors import (
    CSV_CONNECTOR,
    DELTA_CONNECTOR,
    EXCEL_CONNECTOR,
    JSON_CONNECTOR,
    XML_CONNECTOR,
    scan_builtin,
)
from det.engine import create_session_context, run_sql

SAMPLES_DIR = Path(__file__).parent / "fixtures" / "source_data"


class DataWarehouseJoinsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = create_session_context()

    def test_multi_table_sql_join_across_csv_json_xml_excel_and_delta(self) -> None:
        # 1. Customers Dimension (CSV)
        df_customers = scan_builtin(
            self.context,
            CSV_CONNECTOR.guid,
            {"path": str(SAMPLES_DIR / "csv" / "customers.csv"), "has_header": True},
            SAMPLES_DIR,
        )
        self.context.register_view("dim_customers", df_customers)

        # 2. Products Dimension (JSON Array)
        df_products = scan_builtin(
            self.context,
            JSON_CONNECTOR.guid,
            {"path": str(SAMPLES_DIR / "json" / "products.json"), "json_format": "array"},
            SAMPLES_DIR,
        )
        self.context.register_view("dim_products", df_products)

        # 3. Stores Dimension (XML)
        df_stores = scan_builtin(
            self.context,
            XML_CONNECTOR.guid,
            {"path": str(SAMPLES_DIR / "xml" / "stores" / "store_catalog.xml"), "row_tag": "store", "flatten_attributes": True},
            SAMPLES_DIR,
        )
        self.context.register_view("dim_stores", df_stores)

        # 4. Exchange Rates & Targets (Excel)
        df_rates = scan_builtin(
            self.context,
            EXCEL_CONNECTOR.guid,
            {"path": str(SAMPLES_DIR / "excel" / "enterprise_data.xlsx"), "sheet_name": "Exchange_Rates"},
            SAMPLES_DIR,
        )
        self.context.register_view("dim_rates", df_rates)

        # 5. Orders Fact (Multi-file CSV)
        df_orders = scan_builtin(
            self.context,
            CSV_CONNECTOR.guid,
            {
                "path": str(SAMPLES_DIR / "csv" / "orders_daily"),
                "file_pattern": "*.csv",
                "has_header": True,
            },
            SAMPLES_DIR,
        )
        self.context.register_view("fact_orders", df_orders)

        # 6. Delta Lakehouse Fact (Delta Lake ACID table)
        df_delta = scan_builtin(
            self.context,
            DELTA_CONNECTOR.guid,
            {"path": str(SAMPLES_DIR / "delta" / "orders_lakehouse")},
            SAMPLES_DIR,
        )
        self.context.register_view("fact_delta_orders", df_delta)

        # Execute 3-way join: Orders CSV + Customers CSV + Products JSON
        query_3way = """
            SELECT
                o.order_id,
                c.name AS customer_name,
                p.name AS product_name,
                o.quantity,
                o.unit_price,
                ROUND(o.quantity * o.unit_price * (1.0 - o.discount), 2) AS line_total
            FROM fact_orders o
            JOIN dim_customers c ON o.customer_id = c.customer_id
            JOIN dim_products p ON o.product_id = p.product_id
            ORDER BY o.order_id
        """
        res_3way = run_sql(self.context, query_3way)
        t_3way = pa.Table.from_batches(res_3way.collect())
        self.assertEqual(len(t_3way), 8)
        self.assertEqual(t_3way["customer_name"][0].as_py(), "Alice Johnson")
        self.assertEqual(t_3way["product_name"][0].as_py(), "Wireless Noise-Canceling Headphones")

        # Execute 4-way join: Orders CSV + Customers CSV + Products JSON + Stores XML
        query_4way = """
            SELECT
                o.order_id,
                c.name AS customer_name,
                p.name AS product_name,
                s.name AS store_name,
                s.city AS store_city
            FROM fact_orders o
            JOIN dim_customers c ON o.customer_id = c.customer_id
            JOIN dim_products p ON o.product_id = p.product_id
            JOIN dim_stores s ON o.store_id = s.id
            WHERE s.city = 'New York'
            ORDER BY o.order_id
        """
        res_4way = run_sql(self.context, query_4way)
        t_4way = pa.Table.from_batches(res_4way.collect())
        self.assertGreater(len(t_4way), 0)
        self.assertEqual(t_4way["store_city"][0].as_py(), "New York")

        # Execute Delta Lake join: Delta Table + Customers CSV + Products JSON
        query_delta = """
            SELECT
                d.order_id,
                c.name AS customer_name,
                p.name AS product_name,
                d.quantity,
                d.total_amount,
                d.status
            FROM fact_delta_orders d
            JOIN dim_customers c ON d.customer_id = c.customer_id
            JOIN dim_products p ON d.product_id = p.product_id
            ORDER BY d.order_id
        """
        res_delta = run_sql(self.context, query_delta)
        t_delta = pa.Table.from_batches(res_delta.collect())
        self.assertEqual(len(t_delta), 5)
        self.assertEqual(t_delta["status"][0].as_py(), "delivered")


if __name__ == "__main__":
    unittest.main()

