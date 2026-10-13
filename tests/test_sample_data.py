"""Tests for the sample_data feature, CLI, and API recreating warehouse datasets in any workspace."""

import shutil
import tempfile
import unittest
from pathlib import Path

from det.api import configure_ui, get_catalog_store, get_pipeline, install_sample_data, run_pipeline
from det.sample_data import install_sample_data as install_sample_pkg
from det.workspace import initialize_workspace


class TestSampleData(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)
        initialize_workspace(self.workspace)
        configure_ui(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_install_sample_data_creates_all_assets(self):
        result = install_sample_data(self.workspace, select_catalog=True)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["catalog"], "sample_warehouse.yaml")
        self.assertEqual(result["pipelines_folder"], "Sample_Warehouse_Pipelines")
        self.assertEqual(result["pipeline_count"], 10)

        # Verify source_data
        src_dir = self.workspace / "source_data"
        self.assertTrue((src_dir / "customers" / "customers.csv").is_file())
        self.assertTrue((src_dir / "stores" / "store_catalog.xml").is_file())
        self.assertTrue((src_dir / "orders" / "2026_Q1" / "orders_jan.csv").is_file())
        self.assertTrue((src_dir / "products" / "products.json").is_file())
        self.assertTrue((src_dir / "finance" / "financial_reference.xlsx").is_file())
        self.assertTrue((src_dir / "returns" / "order_returns.parquet").is_file())
        self.assertTrue((src_dir / "web_analytics" / "clickstream_events.ndjson").is_file())
        self.assertTrue((src_dir / "inventory" / "supplier_shipments").is_dir())

        # Verify catalog
        cat_file = self.workspace / "catalog" / "sample_warehouse.yaml"
        self.assertTrue(cat_file.is_file())
        active_cat = get_catalog_store().describe_catalogs()["active"]
        self.assertEqual(active_cat, "sample_warehouse.yaml")

        # Verify pipelines
        pipelines_dir = self.workspace / "pipelines" / "Sample_Warehouse_Pipelines"
        self.assertTrue(pipelines_dir.is_dir())
        yaml_files = list(pipelines_dir.glob("*.yaml"))
        self.assertEqual(len(yaml_files), 10)

        # Verify pipeline execution against sample warehouse
        pipe = get_pipeline("Sample_Warehouse_Pipelines/stg_customers_cleaned")
        self.assertEqual(pipe["name"], "stg_customers_cleaned")
        self.assertEqual(pipe["catalog"], "sample_warehouse.yaml")

        run_res = run_pipeline("Sample_Warehouse_Pipelines/stg_customers_cleaned")
        self.assertEqual(run_res["status"], "SUCCESS")
        self.assertEqual(len(run_res["steps"]), 1)
        self.assertEqual(run_res["steps"][0]["rows_processed"], 100)


if __name__ == "__main__":
    unittest.main()

