"""Test catalog preview and schema inference for all sample sources."""

import shutil
import unittest
from det.api import get_catalog_store, infer_connection_schema, preview_connection
from tests.fixtures import setup_test_workspace


class TestCatalogPreviews(unittest.TestCase):
    def setUp(self):
        self.temp_dir, self.workspace = setup_test_workspace()
        self.store = get_catalog_store()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_all_catalog_connections_preview(self):
        catalog_data = self.store.read()["catalog"]
        folders = catalog_data["folders"]
        self.assertGreaterEqual(len(folders), 6)

        total_tested = 0
        for folder in folders:
            connections = folder.get("connections", [])
            for conn in connections:
                if not conn["is_source"]:
                    continue
                result = preview_connection(conn["id"])
                self.assertIn("rows", result)
                self.assertIn("columns", result)
                self.assertGreater(len(result["rows"]), 0, f"Expected rows for {conn['name']}")
                self.assertLessEqual(len(result["rows"]), 50)
                total_tested += 1

        self.assertGreaterEqual(total_tested, 7)

    def test_schema_inference_returns_columns(self):
        catalog_data = self.store.read()["catalog"]
        folders = catalog_data["folders"]
        csv_folder = next(f for f in folders if f["name"] == "Core_CSV")
        conn = csv_folder["connections"][0]
        inferred = infer_connection_schema(conn["id"])
        self.assertIn("columns", inferred)
        col_names = [c["name"] for c in inferred["columns"]]
        self.assertIn("customer_id", col_names)


if __name__ == "__main__":
    unittest.main()
