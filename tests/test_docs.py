import json
import unittest
from pathlib import Path
import tempfile
import shutil

from det.docs import PipelineDocsGenerator
from det.workspace import initialize_workspace
from det.catalog import CatalogStore
from det.pipeline import Pipeline, PipelineStep, PipelineStore
from det.api import configure_api, generate_pipeline_docs


class TestPipelineDocs(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace = Path(self.temp_dir)
        initialize_workspace(self.workspace)
        configure_api(self.workspace)

        # Write dummy CSV file so DataFusion can infer schema during plan evaluation
        (self.workspace / "raw.csv").write_text("event_id,user_id,score\n1,u1,4.5\n", encoding="utf-8")

        # Create sample catalog with connection and column descriptions
        from det.connectors import CSV_CONNECTOR
        self.catalog_store = CatalogStore(self.workspace)
        folder_id = self.catalog_store.read()["catalog"]["folders"][0]["id"]
        self.catalog_store.add_connection(
            folder_id,
            {
                "id": "conn_src_1",
                "name": "raw_events",
                "connector": CSV_CONNECTOR.guid,
                "is_source": True,
                "is_destination": False,
                "description": "Raw streaming events table",
                "options": {"path": "raw.csv"},
                "columns": [
                    {"name": "event_id", "data_type": "string", "nullable": False, "description": "Global unique event UUID"},
                    {"name": "user_id", "data_type": "string", "nullable": True, "description": "User account identifier"},
                    {"name": "score", "data_type": "double", "nullable": True, "description": "Engagement score"},
                ],
            },
        )
        self.catalog_store.add_connection(
            folder_id,
            {
                "id": "conn_dest_1",
                "name": "events_out",
                "connector": CSV_CONNECTOR.guid,
                "is_source": False,
                "is_destination": True,
                "description": "Events export sink",
                "options": {"path": "out.csv"},
                "columns": [],
            },
        )

        # Create pipeline with steps, descriptions, and lineage
        self.pipeline_store = PipelineStore(self.workspace)
        self.test_pipeline = Pipeline(
            name="events_pipeline",
            folder="analytics",
            description="Processes raw events and computes aggregated metrics.",
            catalog="default.yaml",
            steps=[
                PipelineStep(
                    name="filter_events",
                    description="Filter for valid non-null users with positive scores.",
                    sql="SELECT event_id, user_id, score FROM raw_events WHERE score > 0",
                    destinations=[],
                    keep_temporary=True,
                ),
                PipelineStep(
                    name="aggregate_events",
                    description="Aggregate event statistics grouped by user.",
                    sql="SELECT user_id, COUNT(*) AS event_cnt, AVG(score) AS avg_score FROM filter_events GROUP BY user_id",
                    destinations=["events_out"],
                    keep_temporary=False,
                ),
            ],
        )
        self.pipeline_store.save_pipeline(self.test_pipeline)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_html_documentation(self):
        generator = PipelineDocsGenerator(self.workspace)
        html_doc = generator.generate("analytics/events_pipeline", doc_format="html")

        self.assertIn("events_pipeline", html_doc)
        self.assertIn("Processes raw events and computes aggregated metrics.", html_doc)
        self.assertIn("filter_events", html_doc)
        self.assertIn("aggregate_events", html_doc)
        self.assertIn("raw_events", html_doc)
        self.assertIn("events_out", html_doc)
        self.assertIn("Data Lineage", html_doc)
        self.assertIn("User account identifier", html_doc)
        self.assertTrue(html_doc.startswith("<!DOCTYPE html>"))

    def test_generate_markdown_documentation(self):
        generator = PipelineDocsGenerator(self.workspace)
        md_doc = generator.generate("analytics/events_pipeline", doc_format="markdown")

        self.assertIn("# events_pipeline Documentation", md_doc)
        self.assertIn("flowchart LR", md_doc)
        self.assertIn("src_raw_events", md_doc)
        self.assertIn("step_filter_events", md_doc)
        self.assertIn("step_aggregate_events", md_doc)
        self.assertIn("dest_events_out", md_doc)
        self.assertIn("User account identifier", md_doc)

    def test_html_documentation_rich_structure_and_theme(self):
        generator = PipelineDocsGenerator(self.workspace)
        html_doc = generator.generate("analytics/events_pipeline", doc_format="html")

        # 1. Title format: Pipeline Name followed by "Documentation"
        self.assertIn("<title>events_pipeline Documentation</title>", html_doc)
        self.assertIn("events_pipeline Documentation</h1>", html_doc)

        # 2. Theme switcher and design
        self.assertIn("id=\"theme-toggle\"", html_doc)
        self.assertIn("data-theme", html_doc)

        # 3. Metadata: GUID, Created at, Last Modified at, Generation time
        self.assertIn("Pipeline GUID", html_doc)
        self.assertIn("Created at", html_doc)
        self.assertIn("Last Modified at", html_doc)
        self.assertIn("Document Generated", html_doc)

        # 4. DAG Lineage
        self.assertIn("Data Lineage &amp; DAG Dependencies", html_doc)
        self.assertIn("dag-stage-column", html_doc)

        # 5. Navigatable components for sources, steps, destinations
        self.assertIn("id=\"sources\"", html_doc)
        self.assertIn("id=\"src-raw_events\"", html_doc)
        self.assertIn("Referenced by (Pipeline Steps):", html_doc)

        self.assertIn("id=\"steps\"", html_doc)
        self.assertIn("id=\"step-filter_events\"", html_doc)
        self.assertIn("Upstream Dependencies (Inputs):", html_doc)
        self.assertIn("Downstream Consumers (Outputs):", html_doc)

        self.assertIn("id=\"destinations\"", html_doc)
        self.assertIn("id=\"dest-events_out\"", html_doc)
        self.assertIn("Written by (Pipeline Steps):", html_doc)

        # 6. Security notice & secret scan warning
        self.assertIn("Security &amp; Secret Key Scanning", html_doc)
        self.assertIn("Inferred Schema Review", html_doc)

    def test_verify_staleness_detection(self):
        import time
        from det.api import save_pipeline_docs, verify_pipeline_doc_sync

        save_pipeline_docs("analytics/events_pipeline", doc_format="html")
        rel_path = "analytics/events_pipeline.html"

        # Initially up to date
        status = verify_pipeline_doc_sync(rel_path)
        self.assertFalse(status["is_stale"])

        # Modify pipeline file to simulate change after doc generation
        time.sleep(1.1)
        pipe_file = self.workspace / "pipelines" / "analytics" / "events_pipeline.yaml"
        pipe_content = pipe_file.read_text(encoding="utf-8")
        pipe_file.write_text(pipe_content + "\n# updated", encoding="utf-8")

        # Now verification should detect staleness
        status_stale = verify_pipeline_doc_sync(rel_path)
        self.assertTrue(status_stale["is_stale"])
        self.assertIn("modified", status_stale["reason"])

    def test_api_generate_docs(self):
        html_doc = generate_pipeline_docs("analytics/events_pipeline", doc_format="html")
        self.assertIn("events_pipeline", html_doc)
        self.assertIn("<!DOCTYPE html>", html_doc)

    def test_save_pipeline_docs_creates_folder_hierarchy(self):
        from det.api import save_pipeline_docs
        # Ensure documentation directory does not exist yet to test auto-creation
        doc_dir = self.workspace / "documentation"
        if doc_dir.exists():
            shutil.rmtree(doc_dir)

        result_html = save_pipeline_docs("analytics/events_pipeline", doc_format="html")
        expected_html_file = self.workspace / "documentation" / "analytics" / "events_pipeline.html"
        self.assertTrue(expected_html_file.exists())
        self.assertEqual(result_html["saved_path"], "documentation/analytics/events_pipeline.html")
        content = expected_html_file.read_text(encoding="utf-8")
        self.assertIn("events_pipeline", content)

        result_md = save_pipeline_docs("analytics/events_pipeline", doc_format="markdown")
        expected_md_file = self.workspace / "documentation" / "analytics" / "events_pipeline.md"
        self.assertTrue(expected_md_file.exists())
        self.assertEqual(result_md["saved_path"], "documentation/analytics/events_pipeline.md")

    def test_cli_docs_command(self):
        import sys
        from det.cli import main
        # Default without --output replicates hierarchy in documentation/
        old_argv = sys.argv
        try:
            sys.argv = [
                "det",
                "docs",
                "analytics/events_pipeline",
                "--workspace",
                str(self.workspace),
            ]
            main()
            default_file = self.workspace / "documentation" / "analytics" / "events_pipeline.html"
            self.assertTrue(default_file.exists())

            # With --output saves to specified path
            out_file = self.workspace / "custom_doc.html"
            sys.argv = [
                "det",
                "docs",
                "analytics/events_pipeline",
                "--format",
                "html",
                "--output",
                str(out_file),
                "--workspace",
                str(self.workspace),
            ]
            main()
            self.assertTrue(out_file.exists())
            content = out_file.read_text(encoding="utf-8")
            self.assertIn("events_pipeline", content)
            self.assertIn("User account identifier", content)
        finally:
            sys.argv = old_argv


    def test_list_docs_and_empty_folder_filtering(self):
        from det.api import save_pipeline_docs, list_pipeline_docs

        save_pipeline_docs("analytics/events_pipeline", doc_format="html")

        # Create an empty directory inside documentation/
        empty_dir = self.workspace / "documentation" / "empty_folder_without_docs"
        empty_dir.mkdir(parents=True, exist_ok=True)

        docs_list = list_pipeline_docs()
        self.assertEqual(docs_list["total"], 1)
        self.assertIn("analytics", docs_list["folders"])
        # Crucial requirement: empty folders with no docs must NOT be listed
        self.assertNotIn("empty_folder_without_docs", docs_list["folders"])

        item = docs_list["items"][0]
        self.assertEqual(item["folder"], "analytics")
        self.assertEqual(item["filename"], "events_pipeline.html")
        self.assertEqual(item["format"], "html")
        self.assertGreater(item["size_bytes"], 0)

    def test_get_and_regenerate_and_delete_doc(self):
        from det.api import save_pipeline_docs, get_pipeline_doc, regenerate_pipeline_doc, delete_pipeline_doc

        save_pipeline_docs("analytics/events_pipeline", doc_format="markdown")
        rel_path = "analytics/events_pipeline.md"

        # 1. Get doc
        doc_data = get_pipeline_doc(rel_path)
        self.assertEqual(doc_data["rel_path"], rel_path)
        self.assertEqual(doc_data["format"], "md")
        self.assertIn("events_pipeline", doc_data["content"])

        # 2. Regenerate doc
        regen_result = regenerate_pipeline_doc(rel_path)
        self.assertEqual(regen_result["path"], "documentation/analytics/events_pipeline.md")
        self.assertEqual(regen_result["format"], "md")
        self.assertGreater(regen_result["bytes"], 0)

        # 3. Delete doc
        del_result = delete_pipeline_doc(rel_path)
        self.assertTrue(del_result["deleted"])
        self.assertFalse((self.workspace / "documentation" / "analytics" / "events_pipeline.md").exists())


if __name__ == "__main__":
    unittest.main()
