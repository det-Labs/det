"""Tests for ETL Pipeline execution, multi-stage DataFusion SQL, destination writes, and Monitoring telemetry."""

import shutil
import unittest
from pathlib import Path

from det.api import (
    configure_ui,
    get_monitoring_store,
    get_monitoring_summary,
    get_pipeline,
    get_pipeline_run,
    get_pipeline_store,
    list_pipeline_folders,
    list_pipeline_runs,
    list_pipelines,
    run_pipeline,
    save_pipeline,
)
from det.runner import PipelineRunner
from tests.fixtures import setup_test_workspace


class TestETLAndMonitoring(unittest.TestCase):
    def setUp(self):
        self.temp_dir, self.workspace = setup_test_workspace()
        self.pipeline_store = get_pipeline_store()
        self.monitoring_store = get_monitoring_store()
        self.runner = PipelineRunner(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pipeline_store_folders_and_listing(self):
        folders = list_pipeline_folders()
        self.assertIn("demo", folders)
        self.assertIn("retail_samples", folders)

        all_pipelines = list_pipelines()
        names = [p["name"] for p in all_pipelines]
        self.assertIn("summarize", names)
        self.assertIn("multi_source_customers", names)

        demo_pipelines = list_pipelines(folder="demo")
        self.assertEqual(len(demo_pipelines), 1)
        self.assertEqual(demo_pipelines[0]["name"], "summarize")

    def test_run_demo_summarize_pipeline(self):
        pipeline = get_pipeline("demo/summarize")
        self.assertEqual(pipeline["name"], "summarize")

        run_result = run_pipeline("demo/summarize")
        self.assertEqual(run_result["status"], "SUCCESS", f"Run failed with: {run_result.get('error')}")
        self.assertEqual(len(run_result["steps"]), 1)

        step = run_result["steps"][0]
        self.assertEqual(step["step_name"], "totals")
        self.assertGreater(step["rows_processed"], 0)
        self.assertEqual(len(step["destinations"]), 1)

        dest_metric = step["destinations"][0]
        self.assertEqual(dest_metric["format"], "csv")
        self.assertTrue(Path(dest_metric["target_path"]).is_file())

        # Verify monitoring persisted the run
        recorded = get_pipeline_run(run_result["run_id"])
        self.assertEqual(recorded["status"], "SUCCESS")
        self.assertEqual(recorded["pipeline_name_at_run"], "summarize")

    def test_run_multi_step_dag_pipeline(self):
        run_result = run_pipeline("retail_samples/multi_source_customers")
        self.assertEqual(run_result["status"], "SUCCESS", f"Run failed with: {run_result.get('error')}")
        self.assertEqual(len(run_result["steps"]), 2)

        # Step 1: customer_spending
        step1 = run_result["steps"][0]
        self.assertEqual(step1["step_name"], "customer_spending")
        self.assertGreater(step1["rows_processed"], 0)

        # Step 2: curated_customer_report queries step 1 output
        step2 = run_result["steps"][1]
        self.assertEqual(step2["step_name"], "curated_customer_report")
        self.assertGreater(step2["rows_processed"], 0)
        self.assertEqual(len(step2["destinations"]), 2)

        # Check parquet destination
        parquet_dest = next(d for d in step2["destinations"] if d["format"] == "parquet")
        self.assertTrue(Path(parquet_dest["target_path"]).is_file())

        # Check delta destination
        delta_dest = next(d for d in step2["destinations"] if d["format"] == "delta")
        self.assertTrue(Path(delta_dest["target_path"]).is_dir())

    def test_pipeline_failure_records_error_in_monitoring(self):
        failing_pipeline = {
            "name": "failing_test_pipeline",
            "folder": "demo",
            "catalog": "default.yaml",
            "steps": [
                {
                    "name": "bad_step",
                    "sql": "SELECT * FROM NonExistentTable_12345",
                }
            ],
        }
        run_result = run_pipeline(failing_pipeline)
        self.assertEqual(run_result["status"], "FAILED")
        self.assertIn("error", run_result)
        self.assertIn("nonexistenttable_12345", run_result["error"].lower())

        # Check monitoring recorded the failure
        recorded = get_pipeline_run(run_result["run_id"])
        self.assertEqual(recorded["status"], "FAILED")

        # Check workspace summary reflects failures
        summary = get_monitoring_summary()
        self.assertGreater(summary["failures"], 0)
        self.assertIn("success_rate", summary)

    def test_pre_flight_pipeline_validation_and_schema_derivation(self):
        from det.api import validate_pipeline

        # 1. Valid pipeline validation returns schemas for each step
        res = validate_pipeline("demo/summarize")
        self.assertTrue(res["valid"])
        self.assertEqual(len(res["steps"]), 1)
        step_schema = res["steps"][0]["schema"]
        col_names = [c["name"] for c in step_schema]
        self.assertIn("customer_id", col_names)
        self.assertIn("total_sales_usd", col_names)

        # 2. Invalid table name generates user-friendly hints
        invalid_pipeline = {
            "name": "typo_test",
            "folder": "demo",
            "catalog": "default.yaml",
            "steps": [
                {
                    "name": "typo_step",
                    "sql": "SELECT * FROM Orders_Daily_Typo",
                }
            ],
        }
        res_invalid = validate_pipeline(invalid_pipeline)
        self.assertFalse(res_invalid["valid"])
        self.assertIn("Orders_Daily", " ".join(res_invalid["hints"]))

    def test_interactive_step_sql_hinting(self):
        from det.api import validate_step_sql

        # 1. Valid SQL derives schema
        res = validate_step_sql(
            "SELECT customer_id, name, balance * 1.05 AS new_balance FROM Customers",
            catalog_file="default.yaml",
        )
        self.assertTrue(res["valid"])
        cols = {c["name"]: c["data_type"] for c in res["schema"]}
        self.assertIn("customer_id", cols)
        self.assertIn("new_balance", cols)

        # 2. Unknown column gives schema hints
        res_bad_col = validate_step_sql(
            "SELECT cust_id FROM Customers",
            catalog_file="default.yaml",
        )
        self.assertFalse(res_bad_col["valid"])
        self.assertIn("customer_id", " ".join(res_bad_col["hints"]))

    def test_pipeline_log_retrieval_and_filtering(self):
        from det.api import list_pipeline_runs, get_monitoring_store
        store = get_monitoring_store()

        # Test listing runs with date filtering
        runs = list_pipeline_runs(limit=10)
        self.assertIsInstance(runs, list)

        if runs:
            latest = runs[0]
            started = latest.get("started_at")
            if started:
                # Filter with date_from set to after latest run should return fewer/no runs
                future_runs = list_pipeline_runs(date_from="2099-01-01T00:00:00Z")
                self.assertEqual(len(future_runs), 0)

                # Filter with date_to set to past should return 0 runs
                past_runs = list_pipeline_runs(date_to="2000-01-01T00:00:00Z")
                self.assertEqual(len(past_runs), 0)

            # Test retrieving pipeline log by pipeline identifier / GUID / name
            p_id = latest.get("pipeline_id")
            if p_id:
                log_data = store.get_pipeline_log(p_id)
                self.assertEqual(log_data.get("pipeline_id"), p_id)
                self.assertIn("runs", log_data)
                # Each run should have log_entries
                for r in log_data["runs"]:
                    self.assertIn("log_entries", r)
                    self.assertGreater(len(r["log_entries"]), 0)

    def test_monitoring_synthetic_log_entries(self):
        from det.monitoring import synthesize_log_entries

        dummy_run = {
            "run_id": "test-run-123",
            "pipeline_name_at_run": "test_p",
            "folder_at_run": "analytics",
            "status": "SUCCESS",
            "started_at": "2026-10-12T10:00:00Z",
            "completed_at": "2026-10-12T10:00:01Z",
            "total_duration_seconds": 1.0,
            "sources": [{"source_name": "Orders", "connector_type": "csv", "rows_read": 100, "duration_ms": 12.0}],
            "steps": [
                {
                    "step_name": "step_1",
                    "rows_processed": 50,
                    "duration_ms": 35.0,
                    "destinations": [{"destination_name": "out", "rows_written": 50, "duration_ms": 8.0, "format": "parquet"}],
                }
            ],
            "warnings": ["Warning test"],
        }
        logs = synthesize_log_entries(dummy_run)
        self.assertGreater(len(logs), 0)
        levels = [l["level"] for l in logs]
        self.assertIn("INFO", levels)
        self.assertIn("SCAN", levels)
        self.assertIn("STEP", levels)
        self.assertIn("WRITE", levels)
        self.assertIn("WARN", levels)
        self.assertIn("SUCCESS", levels)


if __name__ == "__main__":
    unittest.main()
