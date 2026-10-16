"""Tests for GUI HTTP REST endpoints covering Catalog, Pipelines, and Monitoring."""

import json
import shutil
import unittest
from io import BytesIO

from det.gui import DetRequestHandler
from tests.fixtures import setup_test_workspace


class DummyHandler(DetRequestHandler):
    def __init__(self, method, path, body=None):
        self.command = method
        self.path = path
        self.request_version = "HTTP/1.1"
        self.headers = {"Content-Length": str(len(body or b""))}
        self.rfile = BytesIO(body or b"")
        self.wfile = BytesIO()
        self.response_status = None
        self.response_headers = {}

    def send_response(self, status):
        self.response_status = status

    def send_header(self, key, val):
        self.response_headers[key] = val

    def end_headers(self):
        pass

    def log_message(self, format, *args):
        pass

    def get_json_response(self):
        output = self.wfile.getvalue()
        if output:
            return json.loads(output.decode("utf-8"))
        return None


class TestApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.temp_dir, self.workspace = setup_test_workspace()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_pipelines_endpoint(self):
        handler = DummyHandler("GET", "/api/pipelines")
        handler.do_GET()
        self.assertEqual(handler.response_status, 200)
        data = handler.get_json_response()
        self.assertIn("folders", data)
        self.assertIn("items", data)
        self.assertIn("demo", data["folders"])

    def test_post_pipeline_validate_endpoint(self):
        body = json.dumps({
            "name": "test_pipeline",
            "folder": "demo",
            "catalog": "default.yaml",
            "steps": [
                {
                    "name": "totals",
                    "sql": "SELECT customer_id, count(*) as cnt FROM Customers GROUP BY customer_id",
                }
            ],
        }).encode("utf-8")
        handler = DummyHandler("POST", "/api/pipelines/validate", body)
        handler.do_POST()
        self.assertEqual(handler.response_status, 200)
        data = handler.get_json_response()
        self.assertTrue(data["valid"])
        self.assertEqual(len(data["steps"]), 1)

    def test_post_pipeline_run_endpoint(self):
        body = json.dumps("demo/summarize").encode("utf-8")
        handler = DummyHandler("POST", "/api/pipelines/run", body)
        handler.do_POST()
        self.assertEqual(handler.response_status, 200)
        data = handler.get_json_response()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertIn("steps", data)

    def test_get_monitoring_runs_and_summary_endpoints(self):
        # Trigger a run first so monitoring is guaranteed to have run entries
        run_handler = DummyHandler("POST", "/api/pipelines/run", json.dumps("demo/summarize").encode("utf-8"))
        run_handler.do_POST()
        self.assertEqual(run_handler.response_status, 200)

        handler_runs = DummyHandler("GET", "/api/monitoring/runs")
        handler_runs.do_GET()
        self.assertEqual(handler_runs.response_status, 200)
        runs_data = handler_runs.get_json_response()
        self.assertIn("items", runs_data)
        self.assertGreater(len(runs_data["items"]), 0)

        handler_summary = DummyHandler("GET", "/api/monitoring/summary")
        handler_summary.do_GET()
        self.assertEqual(handler_summary.response_status, 200)
        summary_data = handler_summary.get_json_response()
        self.assertIn("health_status", summary_data)
        self.assertIn("success_rate", summary_data)
    def test_docs_api_endpoints(self):
        # 1. GET /api/docs
        handler_docs = DummyHandler("GET", "/api/docs")
        handler_docs.do_GET()
        self.assertEqual(handler_docs.response_status, 200)
        docs_data = handler_docs.get_json_response()
        self.assertIn("items", docs_data)
        self.assertIn("folders", docs_data)

        # 2. POST /api/pipelines/docs to create one
        body_gen = json.dumps({"pipeline": "demo/summarize", "format": "html"}).encode("utf-8")
        handler_gen = DummyHandler("POST", "/api/pipelines/docs", body_gen)
        handler_gen.do_POST()
        self.assertEqual(handler_gen.response_status, 200)

        # 3. GET /api/docs/item/demo/summarize.html
        handler_item = DummyHandler("GET", "/api/docs/item/demo/summarize.html")
        handler_item.do_GET()
        self.assertEqual(handler_item.response_status, 200)
        item_data = handler_item.get_json_response()
        self.assertEqual(item_data["filename"], "summarize.html")
        self.assertEqual(item_data["format"], "html")

        # 4. POST /api/docs/regenerate
        body_regen = json.dumps({"rel_path": "demo/summarize.html"}).encode("utf-8")
        handler_regen = DummyHandler("POST", "/api/docs/regenerate", body_regen)
        handler_regen.do_POST()
        self.assertEqual(handler_regen.response_status, 200)

        # 5. GET static /documentation/demo/summarize.html
        handler_static = DummyHandler("GET", "/documentation/demo/summarize.html")
        handler_static.do_GET()
        self.assertEqual(handler_static.response_status, 200)
        self.assertIn("text/html", handler_static.response_headers.get("Content-Type", ""))

        # 6. DELETE /api/docs/item/demo/summarize.html
        handler_del = DummyHandler("DELETE", "/api/docs/item/demo/summarize.html")
        handler_del.do_DELETE()
        self.assertEqual(handler_del.response_status, 200)
        del_data = handler_del.get_json_response()
        self.assertTrue(del_data["deleted"])

    def test_help_data_static_endpoint(self):
        handler = DummyHandler("GET", "/help-data.js")
        handler.do_GET()
        self.assertEqual(handler.response_status, 200)
        self.assertIn("text/javascript", handler.response_headers.get("Content-Type", ""))
        content = handler.wfile.getvalue().decode("utf-8")
        self.assertIn("HELP_CATEGORIES", content)
        self.assertIn("NovaMart", content)

    def test_sample_data_install_endpoint(self):
        handler = DummyHandler("POST", "/api/sample-data/install")
        handler.do_POST()
        self.assertEqual(handler.response_status, 200)
        data = handler.get_json_response()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["catalog"], "sample_warehouse.yaml")
        self.assertEqual(data["active_catalog"], "sample_warehouse.yaml")

    def test_discover_tables_endpoint_with_mock(self):
        from unittest.mock import MagicMock, patch
        import pyarrow as pa

        mock_table = pa.Table.from_arrays(
            [pa.array(["public", "rnacen"]), pa.array(["users", "rna"])],
            names=["table_schema", "table_name"],
        )
        mock_cursor = MagicMock()
        mock_cursor.fetch_arrow_table.return_value = mock_table
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        with patch("adbc_driver_postgresql.dbapi.connect", return_value=mock_conn):
            payload = json.dumps({
                "connector": "postgresql",
                "options": {
                    "host": "localhost",
                    "database": "mydb",
                    "user": "postgres",
                },
            }).encode("utf-8")
            handler = DummyHandler("POST", "/api/catalog/discover-tables", body=payload)
            handler.do_POST()
            self.assertEqual(handler.response_status, 200)
            data = handler.get_json_response()
            self.assertTrue(data["success"])
            self.assertEqual(data["count"], 2)
            self.assertEqual(data["tables"], [
                {"schema": "public", "name": "users"},
                {"schema": "rnacen", "name": "rna"},
            ])

    def test_test_connection_endpoint_with_mock(self):
        from unittest.mock import MagicMock, patch

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn

        with patch("adbc_driver_postgresql.dbapi.connect", return_value=mock_conn):
            payload = json.dumps({
                "connector": "postgresql",
                "options": {
                    "host": "localhost",
                    "database": "mydb",
                    "user": "postgres",
                },
            }).encode("utf-8")
            handler = DummyHandler("POST", "/api/catalog/test-connection", body=payload)
            handler.do_POST()
            self.assertEqual(handler.response_status, 200)
            data = handler.get_json_response()
            self.assertTrue(data["success"])
            self.assertEqual(data["message"], "Connected successfully!")

    def test_profiles_endpoints_and_bulk_add(self):
        from det.connectors import POSTGRESQL_CONNECTOR

        # 1. POST /api/catalog/profiles
        profile_payload = json.dumps({
            "name": "my_pg_profile",
            "connector": POSTGRESQL_CONNECTOR.guid,
            "options": {
                "host": "localhost",
                "database": "proddb",
                "user": "appuser",
            },
        }).encode("utf-8")
        handler = DummyHandler("POST", "/api/catalog/profiles", body=profile_payload)
        handler.do_POST()
        self.assertEqual(handler.response_status, 200)
        data = handler.get_json_response()
        initial_count = len(data["catalog"]["folders"][0]["connections"])
        profile_id = data["catalog"]["profiles"][0]["id"]
        folder_id = data["catalog"]["folders"][0]["id"]

        # 2. POST /api/catalog/bulk-add-connections
        bulk_payload = json.dumps({
            "folder_id": folder_id,
            "connections": [
                {
                    "name": "pg_users",
                    "connector": POSTGRESQL_CONNECTOR.guid,
                    "profile": "my_pg_profile",
                    "is_source": True,
                    "options": {"schema": "public", "table": "users"},
                },
                {
                    "name": "pg_orders",
                    "connector": POSTGRESQL_CONNECTOR.guid,
                    "profile": "my_pg_profile",
                    "is_source": True,
                    "options": {"schema": "public", "table": "orders"},
                },
            ],
        }).encode("utf-8")
        handler = DummyHandler("POST", "/api/catalog/bulk-add-connections", body=bulk_payload)
        handler.do_POST()
        self.assertEqual(handler.response_status, 200)
        data = handler.get_json_response()
        folder_conns = data["catalog"]["folders"][0]["connections"]
        self.assertEqual(len(folder_conns), initial_count + 2)
        added_conns = [c for c in folder_conns if c.get("profile") == "my_pg_profile"]
        self.assertEqual(len(added_conns), 2)
        self.assertEqual({c["name"] for c in added_conns}, {"pg_users", "pg_orders"})

        # 3. DELETE /api/catalog/profiles/{id}
        # In use -> error
        handler = DummyHandler("DELETE", f"/api/catalog/profiles/{profile_id}")
        handler.do_DELETE()
        self.assertEqual(handler.response_status, 400)


if __name__ == "__main__":
    unittest.main()

