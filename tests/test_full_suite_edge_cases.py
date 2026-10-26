"""Exhaustive edge-case and boundary test suite for robust pipeline execution."""

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import duckdb
import pytest

from det.engine.dispatcher import QueryDispatcher
from det.engine.mounter import CatalogMounter
from det.workspace import Workspace
from det.models.base import DestinationSpec, MaterializationType, WriteMode
from det.models.definition import ModelConfig, ModelDefinition
from det.models.dag import ModelDAG
from det.models.parser import ModelParser
from det.models.project import ProjectManager
from det.testing.base import TestSeverity, TestSuiteReport, TestResult
from det.testing.definitions import TestDefinition, TestType
from det.testing.evaluator import TestEvaluator
from det.testing.quarantine import QuarantineHandler
from det.testing.runner import TestRunner
from det.monitoring.base import PipelineRunRecord, TestAuditRecord, QuarantineRecord
from det.monitoring.file_sink import FileTelemetrySink
from det.monitoring.duckdb_sink import DuckDBTelemetrySink
from det.monitoring.database_sink import DatabaseTelemetrySink
from det.gui.routes.common import read_json_body, send_json, send_error_json
from det.gui.routes.pipeline_routes import PipelineRouteHandler
from det.gui.routes.monitoring_routes import MonitoringRouteHandler
from det.gui.routes.catalog_routes import CatalogRouteHandler
from det.gui.routes.docs_routes import DocsRouteHandler
from det.gui.server import GUIServer, start_gui_server


class MockHTTPHandler:
    """Mock HTTP handler for inspecting route handler outputs."""

    def __init__(self, body_data: dict | None = None, raw_body: bytes = b"", headers: dict | None = None):
        self.headers = headers or {}
        if body_data is not None:
            raw = json.dumps(body_data).encode("utf-8")
            self.rfile = io.BytesIO(raw)
            self.headers["Content-Length"] = str(len(raw))
        else:
            self.rfile = io.BytesIO(raw_body)
            if "Content-Length" not in self.headers:
                self.headers["Content-Length"] = str(len(raw_body))
        self.wfile = io.BytesIO()
        self.status_code = 200
        self.response_headers = {}

    def send_response(self, code: int):
        self.status_code = code

    def send_header(self, k: str, v: str):
        self.response_headers[k] = v

    def end_headers(self):
        pass

    def get_json_response(self) -> dict:
        self.wfile.seek(0)
        content = self.wfile.read()
        return json.loads(content.decode("utf-8")) if content else {}


@pytest.fixture
def test_workspace(tmp_path: Path) -> Workspace:
    return Workspace.init(tmp_path / "ws")


# =========================================================================
# 1. Pipeline Routes Edge Cases
# =========================================================================

def test_pipeline_routes_run_and_test_errors(test_workspace: Workspace):
    handler = PipelineRouteHandler(test_workspace)

    # Pipeline already running conflict
    test_workspace._active_runs.add("default")
    mock_h = MockHTTPHandler()
    assert handler._handle_run_pipeline(mock_h, {"project": "default"}) is True
    assert mock_h.status_code == 409
    test_workspace._active_runs.clear()

    # Workspace run exception
    with patch.object(test_workspace, "run", side_effect=Exception("Database lock")):
        mock_h = MockHTTPHandler()
        assert handler._handle_run_pipeline(mock_h, {"project": "default"}) is True
        assert "Database lock" in mock_h.get_json_response().get("error", "")

    # Workspace test exception
    with patch.object(test_workspace, "test", side_effect=Exception("Assertion crash")):
        mock_h = MockHTTPHandler()
        assert handler._handle_test_pipeline(mock_h, {"project": "default"}) is True
        assert "Assertion crash" in mock_h.get_json_response().get("error", "")

    # Workspace docs generate exception
    with patch.object(test_workspace, "generate_docs", side_effect=Exception("Docs generator error")):
        mock_h = MockHTTPHandler()
        assert handler._handle_generate_docs(mock_h, {"project": "default"}) is True
        assert "Docs generator error" in mock_h.get_json_response().get("error", "")

    # Compile pipeline exception
    with patch.object(test_workspace.projects, "build_dag", side_effect=Exception("DAG cycle")):
        mock_h = MockHTTPHandler()
        assert handler._handle_compile_pipeline(mock_h, {"project": "default"}) is True
        assert "DAG cycle" in mock_h.get_json_response().get("error", "")


def test_pipeline_routes_model_save_and_delete_edge_cases(test_workspace: Workspace):
    handler = PipelineRouteHandler(test_workspace)

    # Missing model name
    mock_h = MockHTTPHandler()
    assert handler._handle_save_model(mock_h, {"name": ""}) is True
    assert "Model name is required" in mock_h.get_json_response().get("error", "")

    # Invalid identifier
    mock_h = MockHTTPHandler()
    assert handler._handle_save_model(mock_h, {"name": "123-bad!"}) is True
    assert mock_h.status_code == 400

    # Save model in custom folder with complex format
    mock_h = MockHTTPHandler()
    body = {
        "name": "staging_orders",
        "folder": "staging",
        "clean_sql": "SELECT 1 AS id",
        "materialized": "table",
        "description": "Staging orders with 'quotes'",
        "unique_key": "id",
        "destinations": "local_dest",
    }
    assert handler._handle_save_model(mock_h, body) is True
    assert mock_h.get_json_response().get("status") == "ok"

    # Delete model: missing name
    mock_h = MockHTTPHandler()
    assert handler._handle_delete_model(mock_h, {"name": ""}) is True
    assert "Model name is required" in mock_h.get_json_response().get("error", "")

    # Delete model: not found
    mock_h = MockHTTPHandler()
    assert handler._handle_delete_model(mock_h, {"name": "ghost_model"}) is True
    assert mock_h.status_code == 404

    # Delete model: successfully delete existing
    mock_h = MockHTTPHandler()
    assert handler._handle_delete_model(mock_h, {"name": "staging_orders"}) is True
    assert mock_h.get_json_response().get("status") == "ok"


def test_pipeline_routes_create_and_delete_pipeline(test_workspace: Workspace):
    handler = PipelineRouteHandler(test_workspace)

    # Create: empty name
    mock_h = MockHTTPHandler()
    assert handler._handle_create_pipeline(mock_h, {"name": ""}) is True
    assert "Pipeline name is required" in mock_h.get_json_response().get("error", "")

    # Create: custom folder
    mock_h = MockHTTPHandler()
    assert handler._handle_create_pipeline(mock_h, {"name": "analytics", "folder": "CustomGroup"}) is True
    assert mock_h.get_json_response().get("status") == "ok"

    # Delete: empty name
    mock_h = MockHTTPHandler()
    assert handler._handle_delete_pipeline(mock_h, {"name": ""}) is True
    assert "Pipeline name is required" in mock_h.get_json_response().get("error", "")

    # Delete: non-existent pipeline
    mock_h = MockHTTPHandler()
    assert handler._handle_delete_pipeline(mock_h, {"name": "ghost_pipeline"}) is True
    assert mock_h.status_code == 404

    # Delete: existing pipeline
    mock_h = MockHTTPHandler()
    assert handler._handle_delete_pipeline(mock_h, {"name": "analytics"}) is True
    assert mock_h.get_json_response().get("status") == "ok"


def test_pipeline_routes_schema_and_assertion_branches(test_workspace: Workspace):
    handler = PipelineRouteHandler(test_workspace)

    # Save schema: missing model name
    mock_h = MockHTTPHandler()
    assert handler._handle_save_model_schema(mock_h, {"model": ""}) is True
    assert "Model name is required" in mock_h.get_json_response().get("error", "")

    # Save schema: invalid YAML syntax
    mock_h = MockHTTPHandler()
    assert handler._handle_save_model_schema(mock_h, {"model": "m1", "raw_yaml": ": bad: [yaml"}) is True
    assert mock_h.status_code == 400

    # Save schema: raw_yaml root is a list
    mock_h = MockHTTPHandler()
    assert handler._handle_save_model_schema(mock_h, {"model": "m1", "raw_yaml": "- item1\n- item2"}) is True
    assert mock_h.status_code == 400

    # Save schema: raw_yaml with root mapping having name
    mock_h = MockHTTPHandler()
    raw = "name: m1\ndescription: Directly defined model"
    assert handler._handle_save_model_schema(mock_h, {"model": "m1", "raw_yaml": raw}) is True
    assert mock_h.get_json_response().get("status") == "ok"

    # Save schema: column description removal
    mock_h = MockHTTPHandler()
    body = {
        "model": "m1",
        "description": "Updated model desc",
        "columns": [
            {"name": "col_a", "description": "Column A desc"},
            {"name": "col_b", "description": ""},
        ],
    }
    assert handler._handle_save_model_schema(mock_h, body) is True
    assert mock_h.get_json_response().get("status") == "ok"

    # Save assertion: missing model
    mock_h = MockHTTPHandler()
    assert handler._handle_save_model_assertion(mock_h, {"model": ""}) is True
    assert "Model name is required" in mock_h.get_json_response().get("error", "")

    # Save assertions: all variations (not_null warn, unique warn, accepted_values warn, expression warn)
    for t_type, extra in [
        ("not_null", {"severity": "warn"}),
        ("unique", {"severity": "warn"}),
        ("accepted_values", {"accepted_values": "A, B, C", "severity": "warn"}),
        ("accepted_values", {"accepted_values": ["X", "Y"], "severity": "error"}),
        ("expression", {"expression": "col_a > 0", "severity": "warn"}),
    ]:
        mock_h = MockHTTPHandler()
        payload = {"model": "m1", "column": "col_a", "type": t_type, **extra}
        assert handler._handle_save_model_assertion(mock_h, payload) is True
        assert mock_h.get_json_response().get("status") == "ok"

    # Save assertion: model-level assertion (empty column) with old_test_name replacement
    mock_h = MockHTTPHandler()
    payload = {
        "model": "m1",
        "column": "",
        "type": "expression",
        "expression": "col_a != col_b",
        "severity": "warn",
        "old_test_name": "m1__expression",
    }
    assert handler._handle_save_model_assertion(mock_h, payload) is True
    assert mock_h.get_json_response().get("status") == "ok"

    # Delete assertion: missing names
    mock_h = MockHTTPHandler()
    assert handler._handle_delete_model_assertion(mock_h, {"model": "", "test_name": ""}) is True
    assert "Model name and test name are required" in mock_h.get_json_response().get("error", "")

    # Delete assertion: model not found in schema
    mock_h = MockHTTPHandler()
    assert handler._handle_delete_model_assertion(mock_h, {"model": "ghost_model", "test_name": "t1"}) is True
    assert "not found in schema.yml" in mock_h.get_json_response().get("error", "")

    # Delete assertion: column assertion deleted successfully
    mock_h = MockHTTPHandler()
    del_payload = {"model": "m1", "column": "col_a", "test_name": "m1_col_a_not_null", "type": "not_null"}
    assert handler._handle_delete_model_assertion(mock_h, del_payload) is True
    assert mock_h.get_json_response().get("status") == "ok"

    # Delete assertion: fallback search across columns
    mock_h = MockHTTPHandler()
    del_fallback = {"model": "m1", "column": "", "test_name": "m1_col_a_unique", "type": "unique"}
    assert handler._handle_delete_model_assertion(mock_h, del_fallback) is True
    assert mock_h.get_json_response().get("status") == "ok"


def test_test_matches_logic(test_workspace: Workspace):
    handler = PipelineRouteHandler(test_workspace)
    # String tests
    assert handler._test_matches("not_null", "orders_id_not_null", "not_null", "id", "orders") is True
    assert handler._test_matches("unique", "unique", "unique", "id", "orders") is True
    assert handler._test_matches("custom_rule", "orders_id_custom_rule", "custom_rule", "id", "orders") is True

    # Dict tests
    assert handler._test_matches({"not_null": {"severity": "warn"}}, "test", "not_null", "id", "orders") is True
    assert handler._test_matches({"name": "custom_unique", "unique": None}, "custom_unique", "unique", "id", "orders") is True
    assert handler._test_matches({"accepted_values": {"values": [1, 2]}}, "orders_id_accepted_values", "accepted_values", "id", "orders") is True
    assert handler._test_matches({"expression": "amount > 0"}, "other", "not_null", "id", "orders") is False


# =========================================================================
# 2. Monitoring & Catalog Routes Edge Cases
# =========================================================================

def test_monitoring_routes_edge_cases(test_workspace: Workspace):
    handler = MonitoringRouteHandler(test_workspace)

    # Unknown path returns False
    mock_h = MockHTTPHandler()
    assert handler.handle_post(mock_h, "/api/monitoring/unknown", {}) is False

    # Switch sink failure
    mock_h = MockHTTPHandler()
    with patch.object(test_workspace.monitoring, "switch_sink", side_effect=ValueError("Invalid sink type")):
        assert handler.handle_post(mock_h, "/api/monitoring/config", {"sink": "invalid"}) is True
        assert "Invalid sink type" in mock_h.get_json_response().get("error", "")

    # Quarantine resolve: missing record_id
    mock_h = MockHTTPHandler()
    assert handler.handle_post(mock_h, "/api/monitoring/quarantine/resolve", {}) is True
    assert "record_id is required" in mock_h.get_json_response().get("error", "")

    # Quarantine resolve: record not found
    mock_h = MockHTTPHandler()
    assert handler.handle_post(mock_h, "/api/monitoring/quarantine/resolve", {"record_id": "non_existent"}) is True
    assert mock_h.get_json_response().get("status") in ("ok", "not_found")

    # Quarantine purge
    mock_h = MockHTTPHandler()
    assert handler.handle_post(mock_h, "/api/monitoring/quarantine/purge", {"record_ids": ["q1", "q2"]}) is True
    assert "purged_count" in mock_h.get_json_response()


def test_catalog_routes_edge_cases(test_workspace: Workspace):
    handler = CatalogRouteHandler(test_workspace)

    # Save connection: missing name or type
    mock_h = MockHTTPHandler()
    assert handler._handle_save_connection(mock_h, {"name": ""}) is True
    assert "required" in mock_h.get_json_response().get("error", "")

    # Save connection: invalid name identifier
    mock_h = MockHTTPHandler()
    assert handler._handle_save_connection(mock_h, {"name": "123 bad!", "type": "duckdb"}) is True
    assert mock_h.status_code == 400

    # Delete connection: missing name
    mock_h = MockHTTPHandler()
    assert handler._handle_delete_connection(mock_h, {"name": ""}) is True
    assert "required" in mock_h.get_json_response().get("error", "")

    # Delete connection: not found
    mock_h = MockHTTPHandler()
    assert handler._handle_delete_connection(mock_h, {"name": "ghost_conn"}) is True
    assert mock_h.status_code == 404

    # Test connection: ad-hoc connection probe (tier=database)
    mock_h = MockHTTPHandler()
    body = {"tier": "database", "type": "sqlite", "options": {"path": ":memory:"}}
    assert handler._handle_test_connection(mock_h, body) is True
    assert "healthy" in mock_h.get_json_response()

    # Query: empty query string
    mock_h = MockHTTPHandler()
    assert handler._handle_query(mock_h, {"query": "   "}) is True
    assert "Query string cannot be empty" in mock_h.get_json_response().get("error", "")


# =========================================================================
# 3. Docs Routes Edge Cases
# =========================================================================

def test_docs_routes_edge_cases(test_workspace: Workspace):
    handler = DocsRouteHandler(test_workspace)

    # Docs generate error
    mock_h = MockHTTPHandler()
    with patch.object(test_workspace, "generate_docs", side_effect=Exception("Pandas missing")):
        assert handler.handle_post(mock_h, "/api/docs/generate", {"project": "default"}) is True
        assert "Pandas missing" in mock_h.get_json_response().get("error", "")

    # Docs delete error
    mock_h = MockHTTPHandler()
    with patch.object(test_workspace, "delete_docs", side_effect=Exception("Permission denied")):
        assert handler.handle_post(mock_h, "/api/docs/delete", {"project": "default"}) is True
        assert "Permission denied" in mock_h.get_json_response().get("error", "")

    # Docs update column description error
    mock_h = MockHTTPHandler()
    with patch.object(handler, "_update_column_description", side_effect=Exception("Disk full")):
        assert handler.handle_post(mock_h, "/api/docs/column/description", {"project": "default"}) is True
        assert "Disk full" in mock_h.get_json_response().get("error", "")

    # _get_docs_payload handles unexpected exception gracefully
    with patch.object(test_workspace.projects, "build_dag", side_effect=RuntimeError("Corrupted DAG")):
        payload = handler._get_docs_payload("default")
        assert "error" in payload
        assert "Corrupted DAG" in payload["error"]


# =========================================================================
# 4. GUI Server & Common Route Helpers
# =========================================================================

def test_gui_server_start_stop_and_common_helpers(test_workspace: Workspace):
    # Test read_json_body with invalid Content-Length
    mock_h = MockHTTPHandler(raw_body=b"data", headers={"Content-Length": "not_an_int"})
    assert read_json_body(mock_h) == {}

    # Test read_json_body with invalid JSON
    mock_h2 = MockHTTPHandler(raw_body=b"invalid-json{", headers={"Content-Length": "13"})
    assert read_json_body(mock_h2) == {}

    # Test send_error_json
    mock_h3 = MockHTTPHandler()
    send_error_json(mock_h3, "Custom error", status_code=418)
    assert mock_h3.status_code == 418
    assert mock_h3.get_json_response().get("error") == "Custom error"

    # Test GUIServer start (non-blocking) and stop
    server = GUIServer(test_workspace)
    server.start(port=0, blocking=False)
    assert server._server is not None
    server.stop()
    assert server._server is None

    # Test start_gui_server helper
    server2 = start_gui_server(test_workspace, port=0, blocking=False)
    assert server2._server is not None
    server2.stop()


# =========================================================================
# 5. Workspace Lifecycle Edge Cases
# =========================================================================

def test_workspace_lifecycle_edge_cases(tmp_path: Path):
    # Open non-existent workspace path raises FileNotFoundError
    with pytest.raises(FileNotFoundError, match="does not exist"):
        Workspace.open(tmp_path / "does_not_exist")

    ws = Workspace.init(tmp_path / "lifecycle_ws")

    # Check pipeline state
    assert ws.is_pipeline_running("default") is False
    assert ws.get_running_pipelines() == []

    # Delete docs
    assert ws.delete_docs() is False  # nothing to delete yet

    # Delete pipeline and ensure default re-scaffolding
    assert ws.delete_pipeline("default") is True
    # Pipelines dir should re-create default models
    assert (ws.root / "pipelines" / "default" / "models").exists()

    # Schema file with invalid YAML in _load_explicit_tests
    models_dir = ws.root / "pipelines" / "default" / "models"
    (models_dir / "schema.yml").write_text(": bad [yaml syntax", encoding="utf-8")
    tests = ws._load_explicit_tests("default")
    assert isinstance(tests, dict)

    ws.close()


# =========================================================================
# 6. Testing Engine & Quarantine Edge Cases
# =========================================================================

def test_testing_engine_and_quarantine_edge_cases(tmp_path: Path):
    con = test_con = duckdb.connect()
    evaluator = TestEvaluator()
    quarantine = QuarantineHandler()
    runner = TestRunner(evaluator=evaluator)

    # Quarantine counts and rows on non-existent table
    assert quarantine.get_quarantined_count(con, "ghost_table") == 0
    cols, rows = quarantine.get_quarantined_rows(con, "ghost_table")
    assert cols == []
    assert rows == []

    # TestEvaluator._count_total_rows on non-existent table
    assert evaluator._count_total_rows(con, "ghost_table") == 0

    # TestEvaluator error result handling on invalid SQL
    bad_test = TestDefinition(
        name="bad_test",
        model_name="orders",
        test_type=TestType.EXPRESSION,
        parameters={"expression": "SYNTAX ERROR !!!"},
    )
    res = evaluator.evaluate_test(con, bad_test)
    assert res.passed is False
    assert res.error_message is not None

    # Custom test type without custom_query raises ValueError
    custom_def = TestDefinition(name="custom_t", model_name="orders", test_type=TestType.CUSTOM_SQL)
    with pytest.raises(ValueError, match="must have 'custom_query' defined"):
        custom_def.get_failing_rows_query()

    custom_def.custom_query = "SELECT * FROM orders WHERE false"
    assert custom_def.get_failing_rows_query() == "SELECT * FROM orders WHERE false"

    # TestSuiteReport errored tally
    rep = TestSuiteReport()
    rep.add_result(TestResult("t1", "m1", None, TestSeverity.ERROR, False, 1))
    assert rep.errored == 1

    # TestRunner normalization
    assert runner._normalize_test_item("m1", "col", 12345) is None
    assert runner._normalize_test_item("m1", "col", "not_a_valid_test_type") is None

    # Parse schema with model-level tests and column-level tests
    schema_dict = {
        "models": [
            {
                # missing name is skipped
                "columns": [],
            },
            {
                "name": "customers",
                "columns": [{"name": "id", "tests": ["not_null"]}],
                "tests": [{"expression": "id > 0"}],
            },
        ]
    }
    parsed = runner.parse_schema_tests(schema_dict)
    assert len(parsed) == 2
    con.close()


# =========================================================================
# 7. Monitoring Sinks Edge Cases
# =========================================================================

def test_file_sink_edge_cases(tmp_path: Path):
    sink = FileTelemetrySink(tmp_path / "telemetry")

    # When files don't exist
    assert sink.get_runs() == []
    assert sink.get_test_audits() == []
    assert sink.get_quarantine_records() == []
    assert sink.purge_quarantine_records(["q1"]) == 0
    assert sink.resolve_quarantine_record("q1") is False

    # Record and filter with project, model, status, run_id
    run = PipelineRunRecord(
        run_id="r1",
        project="p1",
        status="SUCCESS",
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
        duration_ms=100.0,
        models_executed=1,
        rows_affected=10,
    )
    sink.record_run(run)
    assert len(sink.get_runs(project="p1", limit=10)) == 1
    assert len(sink.get_runs(project="p_other")) == 0

    audit = TestAuditRecord(
        audit_id="a1", run_id="r1", project="p1", model_name="m1", test_name="t1",
        test_type="not_null", severity="error", passed=False, failures_count=1,
        action_taken="LOG", details="Passed details", executed_at="2026-01-01T00:00:00Z",
    )
    sink.record_test_audits([audit])
    sink.record_test_audits([])  # empty batch
    assert len(sink.get_test_audits(run_id="r1")) == 1
    assert len(sink.get_test_audits(run_id="other_run")) == 0
    assert len(sink.get_test_audits(project="other_proj")) == 0

    q_rec = QuarantineRecord(
        record_id="q1", run_id="r1", project="p1", model_name="m1",
        test_name="t1", quarantined_at="2026-01-01T00:00:00Z",
        raw_payload={"val": -1}, status="OPEN",
    )
    sink.record_quarantine_rows([q_rec])
    sink.record_quarantine_rows([])  # empty batch
    assert len(sink.get_quarantine_records(model="m1", status="OPEN")) == 1
    assert len(sink.get_quarantine_records(model="m_other")) == 0
    assert len(sink.get_quarantine_records(status="RESOLVED")) == 0

    # Resolve and purge
    assert sink.resolve_quarantine_record("q1", notes="Verified") is True
    assert sink.purge_quarantine_records(["q1"]) == 1


def test_duckdb_and_database_sinks_parse_json(tmp_path: Path):
    duck_sink = DuckDBTelemetrySink(tmp_path / "duck.db")
    db_sink = DatabaseTelemetrySink("sqlite:///" + str(tmp_path / "db.sqlite"))

    # Test _parse_json_list / _parse_json on DuckDB and Database sinks
    assert duck_sink._parse_json_list(None) == []
    assert duck_sink._parse_json_list([{"a": 1}]) == [{"a": 1}]
    assert duck_sink._parse_json_list("not valid json") == []
    assert duck_sink._parse_json_list('{"not": "a list"}') == []

    assert db_sink._parse_json(None) == []
    assert db_sink._parse_json([{"a": 1}]) == [{"a": 1}]
    assert db_sink._parse_json("not valid json") == []
    assert db_sink._parse_json('{"not": "a list"}') == []

    # Empty batches
    duck_sink.record_test_audits([])
    duck_sink.record_quarantine_rows([])
    db_sink.record_test_audits([])
    db_sink.record_quarantine_rows([])


# =========================================================================
# 8. Models, Projects, DAG & Parser Edge Cases
# =========================================================================

def test_models_dag_and_project_edge_cases(tmp_path: Path):
    # DAG select_models raises KeyError on missing model
    dag = ModelDAG()
    with pytest.raises(KeyError, match="Selected model 'ghost' not found"):
        dag.select_models("ghost")

    # ProjectManager folder resolution and cleanup
    proj_root = tmp_path / "projects_test"
    mgr = ProjectManager(proj_root)
    assert mgr._get_known_connection_names() == set()

    # Create nested project
    nested_models = proj_root / "projects" / "groupA" / "proj1" / "models"
    nested_models.mkdir(parents=True, exist_ok=True)
    assert mgr.get_project_folder("proj1") == "groupA"

    # Delete project cleans up parent folder if empty
    assert mgr.delete_project("proj1") is True
    assert not (proj_root / "projects" / "groupA").exists()

    # DestinationSpec.from_any with invalid type raises TypeError
    with pytest.raises(TypeError, match="Cannot convert"):
        DestinationSpec.from_any(12345)

    # ModelConfig.from_dict with empty destinations defaults to local
    cfg = ModelConfig.from_dict({"destinations": []})
    assert len(cfg.destinations) == 1
    assert cfg.destinations[0].target == "local"

    # ModelParser source with single argument {{ source('raw_conn') }}
    parser = ModelParser()
    sql = "SELECT * FROM {{ source('raw_conn') }}"
    compiled = parser.compile_sql(sql, "test_model")
    assert compiled == "SELECT * FROM raw_conn"

    # ModelParser safe eval value fallback
    assert parser._safe_eval_value("custom_unquoted_string") == "custom_unquoted_string"


def test_dispatcher_deep_scenarios():
    con = duckdb.connect()
    dispatcher = QueryDispatcher()

    # execute_to_arrow on valid query
    tbl = dispatcher.execute_to_arrow(con, "SELECT 1 AS num, 'text' AS txt")
    assert tbl is not None
    assert tbl.num_rows == 1

    # execute_to_arrow when pyarrow is not available or error occurs
    mock_con = MagicMock()
    mock_con.sql.side_effect = Exception("Arrow driver missing")
    with patch.object(dispatcher, "_is_pyarrow_available", return_value=False):
        with pytest.raises(RuntimeError, match="PyArrow is required for Arrow streaming"):
            dispatcher.execute_to_arrow(mock_con, "SELECT 1")

    # format_catalog_error checks
    assert "Syntax Error" in dispatcher.format_catalog_error(duckdb.ParserException("Parser Error: syntax error"))
    assert "Binder Error" in dispatcher.format_catalog_error(duckdb.BinderException("Binder Error: column not found"))
    assert "Catalog Error" in dispatcher.format_catalog_error(duckdb.CatalogException("Catalog Error: table missing"))
    assert "Database Error" in dispatcher.format_catalog_error(Exception("Generic issue"))

    # _extract_column_names with cursor.description is None
    mock_cursor = MagicMock()
    mock_cursor.description = None
    assert dispatcher._extract_column_names(mock_cursor) == []

    con.close()


def test_mounter_cloud_extension_and_secret_fallback():
    mounter = CatalogMounter()
    mock_con = MagicMock(spec=duckdb.DuckDBPyConnection)
    mock_con.load_extension.side_effect = Exception("Extension unavailable in environment")

    # Item for azure, s3, delta
    for conn_type, expected_ext in [("azure", "azure"), ("s3", "aws"), ("delta", "delta")]:
        class MockCloudItem:
            tier = "entity"
            def __init__(self, ctype):
                self.name = f"{ctype}_item"
                self.type = ctype
            def get_mount_sql(self): return f"CREATE VIEW {self.name} AS SELECT 1"
            def get_secret_sql(self, resolver): return "CREATE SECRET (TYPE DUMMY)"

        item = MockCloudItem(conn_type)
        mounter.mount_item(mock_con, item)
        mock_con.load_extension.assert_called_with(expected_ext)

    # Secret execution error fallback
    mock_con.execute.side_effect = [Exception("Secret error"), None]
    mounter.mount_item(mock_con, item)
    assert mock_con.execute.call_count >= 2


def test_file_sink_deep_scenarios(tmp_path: Path):
    sink = FileTelemetrySink(tmp_path / "telemetry_deep")

    # Write blank lines to files to trigger line.strip() branches
    sink.runs_file.write_text("\n\n   \n", encoding="utf-8")
    assert sink.get_runs() == []

    sink.tests_file.write_text("\n\n", encoding="utf-8")
    assert sink.get_test_audits() == []

    sink.quarantine_file.write_text("\n\n", encoding="utf-8")
    assert sink.get_quarantine_records() == []

    # Exceed limit to test break
    run = PipelineRunRecord("r1", "p1", "SUCCESS", "2026-01-01", "2026-01-01", 10.0, 1, 1)
    run2 = PipelineRunRecord("r2", "p1", "SUCCESS", "2026-01-01", "2026-01-01", 10.0, 1, 1)
    sink.record_run(run)
    sink.record_run(run2)
    assert len(sink.get_runs(limit=1)) == 1

    # Quarantine with project filter
    q1 = QuarantineRecord("q1", "r1", "p1", "m1", "t1", "2026-01-01", {}, "OPEN")
    q2 = QuarantineRecord("q2", "r1", "p2", "m1", "t1", "2026-01-01", {}, "OPEN")
    sink.record_quarantine_rows([q1, q2])
    assert len(sink.get_quarantine_records(project="p1", limit=1)) == 1

