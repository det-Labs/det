"""Tests for core file-based connectors: CSV, Parquet, Excel, JSON, XML."""

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq
from deltalake import write_deltalake

from det.api import configure_ui, infer_connection_schema, preview_connection
from det.catalog import CatalogStore
from det.connectors import (
    CSV_CONNECTOR,
    DELTA_CONNECTOR,
    EXCEL_CONNECTOR,
    ICEBERG_CONNECTOR,
    JSON_CONNECTOR,
    PARQUET_CONNECTOR,
    XML_CONNECTOR,
    connector_definitions,
    connector_metadata,
    scan_builtin,
)
from det.engine import create_session_context, run_sql
from det.workspace import initialize_workspace


class FileConnectorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        initialize_workspace(self.workspace)
        configure_ui(self.workspace)
        self.store = CatalogStore(self.workspace)
        self.context = create_session_context()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_all_seven_core_connectors_registered_with_unique_guids(self) -> None:
        definitions = connector_definitions()
        keys = [c.key for c in definitions]
        self.assertEqual(keys, ["csv", "parquet", "excel", "json", "xml", "delta", "iceberg"])
        guids = [c.guid for c in definitions]
        self.assertEqual(len(guids), len(set(guids)))
        metadata = connector_metadata()
        self.assertEqual(len(metadata), 7)

    def test_csv_single_and_multi_file_nested_scan_with_sql(self) -> None:
        folder = self.workspace / "data_csv" / "nested"
        folder.mkdir(parents=True)
        (self.workspace / "data_csv" / "file1.csv").write_text(
            "id,name,amount\n1,Alice,100\n2,Bob,50\n", encoding="utf-8"
        )
        (folder / "file2.csv").write_text(
            "id,name,amount\n3,Charlie,200\n", encoding="utf-8"
        )

        df = scan_builtin(
            self.context,
            CSV_CONNECTOR.guid,
            {
                "path": "data_csv",
                "file_pattern": "*.csv",
                "include_subfolders": True,
            },
            self.workspace,
        )
        self.context.register_view("csv_sources", df)
        result = run_sql(
            self.context,
            "SELECT name, amount FROM csv_sources WHERE amount >= 100 ORDER BY amount DESC",
        )
        batches = result.collect()
        table = pa.Table.from_batches(batches)
        self.assertEqual(table.to_pydict(), {"name": ["Charlie", "Alice"], "amount": [200, 100]})

    def test_parquet_single_and_multi_file_nested_scan_with_sql(self) -> None:
        folder = self.workspace / "data_parquet" / "sub"
        folder.mkdir(parents=True)
        t1 = pa.table({"region": ["North", "South"], "sales": [300, 150]})
        t2 = pa.table({"region": ["North", "East"], "sales": [200, 400]})
        pq.write_table(t1, str(self.workspace / "data_parquet" / "part1.parquet"))
        pq.write_table(t2, str(folder / "part2.parquet"))

        df = scan_builtin(
            self.context,
            PARQUET_CONNECTOR.guid,
            {
                "path": "data_parquet",
                "file_pattern": "*.parquet",
                "include_subfolders": True,
            },
            self.workspace,
        )
        self.context.register_view("parquet_sources", df)
        result = run_sql(
            self.context,
            "SELECT region, SUM(sales) AS total FROM parquet_sources GROUP BY region ORDER BY region",
        )
        batches = result.collect()
        table = pa.Table.from_batches(batches)
        self.assertEqual(
            table.to_pydict(),
            {"region": ["East", "North", "South"], "total": [400, 500, 150]},
        )

    def test_excel_single_and_multi_file_nested_scan_with_sql(self) -> None:
        nested_dir = self.workspace / "data_excel" / "q1"
        nested_dir.mkdir(parents=True)

        wb1 = openpyxl.Workbook()
        ws1 = wb1.active
        ws1.title = "Sales"
        ws1.append(["item_id", "product", "qty"])
        ws1.append([101, "Laptop", 5])
        ws1.append([102, "Monitor", 12])
        wb1.save(self.workspace / "data_excel" / "sales_jan.xlsx")
        wb1.close()

        wb2 = openpyxl.Workbook()
        ws2 = wb2.active
        ws2.title = "Sales"
        ws2.append(["item_id", "product", "qty"])
        ws2.append([103, "Mouse", 25])
        wb2.save(nested_dir / "sales_feb.xlsx")
        wb2.close()

        df = scan_builtin(
            self.context,
            EXCEL_CONNECTOR.guid,
            {
                "path": "data_excel",
                "file_pattern": "*.xlsx",
                "include_subfolders": True,
                "sheet_name": "Sales",
            },
            self.workspace,
        )
        self.context.register_view("excel_sales", df)
        result = run_sql(
            self.context,
            "SELECT product, qty FROM excel_sales WHERE qty >= 10 ORDER BY qty DESC",
        )
        batches = result.collect()
        table = pa.Table.from_batches(batches)
        self.assertEqual(
            table.to_pydict(),
            {"product": ["Mouse", "Monitor"], "qty": [25, 12]},
        )

    def test_json_lines_and_json_array_scans_with_sql(self) -> None:
        # 1. Line-delimited JSON
        jsonl_dir = self.workspace / "data_jsonl" / "nested"
        jsonl_dir.mkdir(parents=True)
        (self.workspace / "data_jsonl" / "part1.jsonl").write_text(
            json.dumps({"user": "user1", "status": "active", "points": 10}) + "\n",
            encoding="utf-8",
        )
        (jsonl_dir / "part2.jsonl").write_text(
            json.dumps({"user": "user2", "status": "inactive", "points": 5}) + "\n"
            + json.dumps({"user": "user3", "status": "active", "points": 25}) + "\n",
            encoding="utf-8",
        )

        df_lines = scan_builtin(
            self.context,
            JSON_CONNECTOR.guid,
            {
                "path": "data_jsonl",
                "file_pattern": "*.jsonl",
                "include_subfolders": True,
                "json_format": "lines",
            },
            self.workspace,
        )
        self.context.register_view("jsonl_users", df_lines)
        res_lines = run_sql(
            self.context,
            "SELECT user, points FROM jsonl_users WHERE status = 'active' ORDER BY points DESC",
        )
        self.assertEqual(
            pa.Table.from_batches(res_lines.collect()).to_pydict(),
            {"user": ["user3", "user1"], "points": [25, 10]},
        )

        # 2. JSON Array format
        json_arr_dir = self.workspace / "data_json_arr"
        json_arr_dir.mkdir(parents=True)
        (json_arr_dir / "data.json").write_text(
            json.dumps([
                {"code": "A1", "score": 95},
                {"code": "B2", "score": 82},
            ]),
            encoding="utf-8",
        )
        df_arr = scan_builtin(
            self.context,
            JSON_CONNECTOR.guid,
            {"path": "data_json_arr/data.json", "json_format": "auto"},
            self.workspace,
        )
        self.context.register_view("json_arr", df_arr)
        res_arr = run_sql(self.context, "SELECT code FROM json_arr WHERE score > 90")
        self.assertEqual(
            pa.Table.from_batches(res_arr.collect()).to_pydict(),
            {"code": ["A1"]},
        )

    def test_xml_single_and_multi_file_nested_scan_with_sql(self) -> None:
        xml_dir = self.workspace / "data_xml" / "nested"
        xml_dir.mkdir(parents=True)

        (self.workspace / "data_xml" / "catalog1.xml").write_text(
            '<books><book id="b1"><title>Python Guide</title><price>30.0</price></book></books>',
            encoding="utf-8",
        )
        (xml_dir / "catalog2.xml").write_text(
            '<books><book id="b2"><title>SQL Handbook</title><price>45.5</price></book></books>',
            encoding="utf-8",
        )

        df = scan_builtin(
            self.context,
            XML_CONNECTOR.guid,
            {
                "path": "data_xml",
                "file_pattern": "*.xml",
                "include_subfolders": True,
                "row_tag": "book",
                "flatten_attributes": True,
            },
            self.workspace,
        )
        self.context.register_view("xml_books", df)
        result = run_sql(
            self.context,
            "SELECT id, title, CAST(price AS DOUBLE) AS price FROM xml_books ORDER BY price DESC",
        )
        batches = result.collect()
        table = pa.Table.from_batches(batches)
        self.assertEqual(
            table.to_pydict(),
            {"id": ["b2", "b1"], "title": ["SQL Handbook", "Python Guide"], "price": [45.5, 30.0]},
        )

    def test_delta_single_folder_scan_and_time_travel_with_sql(self) -> None:
        delta_dir = self.workspace / "delta_orders"
        t0 = pa.table({"order_id": [1, 2], "amount": [100.0, 200.0]})
        write_deltalake(delta_dir, t0)

        t1 = pa.table({"order_id": [3, 4], "amount": [300.0, 400.0]})
        write_deltalake(delta_dir, t1, mode="append")

        # 1. Query current Delta table (version 1)
        df_latest = scan_builtin(
            self.context,
            DELTA_CONNECTOR.guid,
            {"path": "delta_orders"},
            self.workspace,
        )
        self.context.register_view("delta_latest", df_latest)
        res_latest = run_sql(
            self.context,
            "SELECT order_id, amount FROM delta_latest WHERE amount >= 200 ORDER BY order_id",
        )
        self.assertEqual(
            pa.Table.from_batches(res_latest.collect()).to_pydict(),
            {"order_id": [2, 3, 4], "amount": [200.0, 300.0, 400.0]},
        )

        # 2. Query historical snapshot (time-travel version 0)
        df_v0 = scan_builtin(
            self.context,
            DELTA_CONNECTOR.guid,
            {"path": "delta_orders", "version": 0},
            self.workspace,
        )
        self.context.register_view("delta_v0", df_v0)
        res_v0 = run_sql(self.context, "SELECT order_id FROM delta_v0 ORDER BY order_id")
        self.assertEqual(
            pa.Table.from_batches(res_v0.collect()).to_pydict(),
            {"order_id": [1, 2]},
        )

    def test_iceberg_scan_with_sql(self) -> None:
        iceberg_dir = self.workspace / "iceberg_data"
        data_dir = iceberg_dir / "data"
        data_dir.mkdir(parents=True)
        pq.write_table(
            pa.table({"item": ["item1", "item2"], "cost": [15.0, 25.0]}),
            str(data_dir / "part1.parquet"),
        )

        df = scan_builtin(
            self.context,
            ICEBERG_CONNECTOR.guid,
            {"path": "iceberg_data"},
            self.workspace,
        )
        self.context.register_view("iceberg_table", df)
        res = run_sql(self.context, "SELECT item, cost FROM iceberg_table WHERE cost > 20.0")
        self.assertEqual(
            pa.Table.from_batches(res.collect()).to_pydict(),
            {"item": ["item2"], "cost": [25.0]},
        )

    def test_catalog_inference_and_preview_for_all_seven_connectors(self) -> None:
        folder_id = self.store.read()["catalog"]["folders"][0]["id"]

        # Create sample data for each connector
        (self.workspace / "test.csv").write_text("c1,c2\nfoo,10\n", encoding="utf-8")
        pq.write_table(pa.table({"p1": ["bar"], "p2": [20]}), str(self.workspace / "test.parquet"))

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["e1", "e2"])
        ws.append(["baz", 30])
        wb.save(self.workspace / "test.xlsx")
        wb.close()

        (self.workspace / "test.json").write_text('{"j1": "qux", "j2": 40}\n', encoding="utf-8")
        (self.workspace / "test.xml").write_text('<root><row><x1>quux</x1><x2>50</x2></row></root>', encoding="utf-8")

        write_deltalake(self.workspace / "test_delta", pa.table({"d1": ["delta_val"], "d2": [60]}))

        iceberg_data = self.workspace / "test_iceberg" / "data"
        iceberg_data.mkdir(parents=True)
        pq.write_table(pa.table({"i1": ["ice_val"], "i2": [70]}), str(iceberg_data / "part.parquet"))

        test_cases = [
            ("csv_conn", CSV_CONNECTOR.guid, {"path": "test.csv", "has_header": True}, ["c1", "c2"]),
            ("parquet_conn", PARQUET_CONNECTOR.guid, {"path": "test.parquet"}, ["p1", "p2"]),
            ("excel_conn", EXCEL_CONNECTOR.guid, {"path": "test.xlsx"}, ["e1", "e2"]),
            ("json_conn", JSON_CONNECTOR.guid, {"path": "test.json"}, ["j1", "j2"]),
            ("xml_conn", XML_CONNECTOR.guid, {"path": "test.xml"}, ["x1", "x2"]),
            ("delta_conn", DELTA_CONNECTOR.guid, {"path": "test_delta"}, ["d1", "d2"]),
            ("iceberg_conn", ICEBERG_CONNECTOR.guid, {"path": "test_iceberg"}, ["i1", "i2"]),
        ]

        for name, connector_guid, options, expected_cols in test_cases:
            with self.subTest(connector=name):
                res = self.store.add_connection(
                    folder_id,
                    {
                        "name": name,
                        "connector": connector_guid,
                        "is_source": True,
                        "options": options,
                    },
                )
                conn_id = res["catalog"]["folders"][0]["connections"][-1]["id"]

                # Infer schema via DataFusion
                inferred = infer_connection_schema(conn_id)
                col_names = [c["name"] for c in inferred["columns"]]
                self.assertEqual(sorted(col_names), sorted(expected_cols))

                # Preview connection via DataFusion SQL
                preview = preview_connection(conn_id)
                self.assertEqual(preview["row_limit"], 50)
                self.assertEqual(len(preview["rows"]), 1)


if __name__ == "__main__":
    unittest.main()
