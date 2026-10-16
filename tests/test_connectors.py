"""Tests for core file-based connectors: CSV, Parquet, Excel, JSON, XML."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    POSTGRESQL_CONNECTOR,
    XML_CONNECTOR,
    build_postgres_uri,
    connector_definitions,
    connector_metadata,
    resolve_env_vars,
    scan_builtin,
)
from det.engine import create_session_context, run_sql
from det.runner import PipelineRunner
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

    def test_all_eight_core_connectors_registered_with_unique_guids(self) -> None:
        definitions = connector_definitions()
        keys = [c.key for c in definitions]
        self.assertEqual(keys, ["csv", "parquet", "excel", "json", "xml", "delta", "iceberg", "postgresql"])
        guids = [c.guid for c in definitions]
        self.assertEqual(len(guids), len(set(guids)))
        metadata = connector_metadata()
        self.assertEqual(len(metadata), 8)

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

    def test_resolve_env_vars_with_system_and_workspace_env(self) -> None:
        # 1. System environment variable
        os.environ["DET_TEST_PG_HOST"] = "pg.internal.corp"
        os.environ["DET_TEST_PG_PASS"] = "s3cr3t#123"

        resolved = resolve_env_vars("postgresql://admin:${DET_TEST_PG_PASS}@${DET_TEST_PG_HOST}:5432/db")
        self.assertEqual(resolved, "postgresql://admin:s3cr3t#123@pg.internal.corp:5432/db")

        # 2. Workspace .env file
        env_file = self.workspace / ".env"
        env_file.write_text("DET_ENV_USER=postgres_user\nDET_ENV_PORT=5433\n# comment\n", encoding="utf-8")

        opts = {
            "host": "${DET_TEST_PG_HOST}",
            "port": "${DET_ENV_PORT}",
            "user": "${DET_ENV_USER}",
            "password": "${DET_TEST_PG_PASS}",
            "nested": ["${DET_ENV_USER}", 123],
        }
        resolved_opts = resolve_env_vars(opts, self.workspace)
        self.assertEqual(resolved_opts["host"], "pg.internal.corp")
        self.assertEqual(resolved_opts["port"], "5433")
        self.assertEqual(resolved_opts["user"], "postgres_user")
        self.assertEqual(resolved_opts["password"], "s3cr3t#123")
        self.assertEqual(resolved_opts["nested"], ["postgres_user", 123])

        # 3. Missing variable raises ValueError with informative message
        with self.assertRaises(ValueError) as ctx:
            resolve_env_vars("${NON_EXISTENT_ENV_VAR_12345}", self.workspace)
        self.assertIn("NON_EXISTENT_ENV_VAR_12345", str(ctx.exception))
        self.assertIn("workspace .env or system environment", str(ctx.exception))

    def test_build_postgres_uri(self) -> None:
        # Standard options
        opts = {
            "host": "localhost",
            "port": 5432,
            "database": "sales_db",
            "user": "det_user",
            "password": "my_password",
            "sslmode": "require",
        }
        uri = build_postgres_uri(opts)
        self.assertEqual(uri, "postgresql://det_user:my_password@localhost:5432/sales_db?sslmode=require")

        # Special characters in credentials URL-encoded
        opts_special = {
            "host": "db.cloud.net",
            "port": 5439,
            "database": "analytics",
            "user": "user@domain.com",
            "password": "p@ss:word/123",
            "sslmode": "prefer",
        }
        uri_special = build_postgres_uri(opts_special)
        self.assertEqual(
            uri_special,
            "postgresql://user%40domain.com:p%40ss%3Aword%2F123@db.cloud.net:5439/analytics?sslmode=prefer",
        )

        # URI override takes precedence
        opts_override = {"uri": "postgresql://custom_conn_str:5432/custom_db"}
        self.assertEqual(build_postgres_uri(opts_override), "postgresql://custom_conn_str:5432/custom_db")

        # Missing database raises ValueError
        with self.assertRaises(ValueError):
            build_postgres_uri({"host": "localhost"})

    def test_postgresql_connector_definition(self) -> None:
        self.assertEqual(POSTGRESQL_CONNECTOR.key, "postgresql")
        self.assertEqual(POSTGRESQL_CONNECTOR.label, "PostgreSQL")
        self.assertTrue(POSTGRESQL_CONNECTOR.guid)

        fields_by_name = {f.name: f for f in POSTGRESQL_CONNECTOR.fields}
        self.assertIn("host", fields_by_name)
        self.assertIn("port", fields_by_name)
        self.assertIn("database", fields_by_name)
        self.assertIn("user", fields_by_name)
        self.assertIn("password", fields_by_name)
        self.assertEqual(fields_by_name["password"].kind, "password")
        self.assertIn("sslmode", fields_by_name)
        self.assertIn("schema", fields_by_name)
        self.assertIn("table", fields_by_name)
        self.assertIn("query", fields_by_name)
        self.assertIn("target_table", fields_by_name)
        self.assertIn("write_mode", fields_by_name)

    def test_scan_postgresql_adbc_with_mock(self) -> None:
        mock_table = pa.Table.from_arrays(
            [pa.array([101, 102]), pa.array(["Item A", "Item B"])],
            names=["product_id", "product_name"],
        )

        mock_cursor = MagicMock()
        mock_cursor.fetch_arrow_table.return_value = mock_table
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        with patch("adbc_driver_postgresql.dbapi.connect", return_value=mock_conn) as mock_connect:
            # 1. Scan with table option
            opts = {
                "host": "localhost",
                "database": "store",
                "schema": "public",
                "table": "products",
            }
            df = scan_builtin(self.context, POSTGRESQL_CONNECTOR.guid, opts, self.workspace)
            mock_connect.assert_called_once()
            mock_cursor.execute.assert_called_with('SELECT * FROM "public"."products"')

            # Query the resulting DataFusion DataFrame
            self.context.register_view("pg_products", df)
            result = run_sql(self.context, "SELECT * FROM pg_products WHERE product_id = 101")
            res_table = result.to_arrow_table()
            self.assertEqual(res_table.num_rows, 1)
            self.assertEqual(res_table["product_name"][0].as_py(), "Item A")

        with patch("adbc_driver_postgresql.dbapi.connect", return_value=mock_conn):
            # 2. Scan with custom query option
            opts_query = {
                "host": "localhost",
                "database": "store",
                "query": "SELECT product_id, product_name FROM products WHERE active = true",
            }
            scan_builtin(self.context, POSTGRESQL_CONNECTOR.guid, opts_query, self.workspace)
            mock_cursor.execute.assert_called_with("SELECT product_id, product_name FROM products WHERE active = true")

    def test_write_postgresql_destination_with_mock(self) -> None:
        runner = PipelineRunner(self.workspace)
        test_arrow_table = pa.Table.from_arrays(
            [pa.array([1, 2, 3]), pa.array(["X", "Y", "Z"])],
            names=["id", "val"],
        )

        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        with patch("adbc_driver_postgresql.dbapi.connect", return_value=mock_conn):
            dest_conn = {
                "name": "pg_dest",
                "connector": POSTGRESQL_CONNECTOR.guid,
                "is_destination": True,
                "options": {
                    "host": "localhost",
                    "database": "analytics",
                    "target_schema": "public",
                    "target_table": "transformed_metrics",
                    "write_mode": "create_or_replace",
                },
            }
            metric = runner._write_to_destination(dest_conn, None, test_arrow_table)
            self.assertEqual(metric.destination_name, "pg_dest")
            self.assertEqual(metric.format, "postgresql")
            self.assertEqual(metric.target_path, "public.transformed_metrics")
            self.assertEqual(metric.rows_written, 3)

            # Verified cursor.adbc_ingest called with 'replace' mode
            mock_cursor.adbc_ingest.assert_called_once_with(
                table_name="transformed_metrics",
                data=test_arrow_table,
                mode="replace",
                db_schema_name="public",
            )
            mock_conn.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
