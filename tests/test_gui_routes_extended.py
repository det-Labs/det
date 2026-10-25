"""Extended REST API tests for Web IDE routes (Pipelines, Catalog, Monitoring, Docs)."""

import json
from pathlib import Path
import socket
from typing import Any
import urllib.error
import urllib.request
import pytest

from det.gui.server import GUIServer
from det.workspace import Workspace


def find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Helper to perform HTTP POST with JSON body and return response."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode("utf-8"))


def _get_json(url: str) -> dict[str, Any] | list[Any]:
    """Helper to perform HTTP GET and return JSON response."""
    with urllib.request.urlopen(url) as res:
        return json.loads(res.read().decode("utf-8"))


def _setup_test_server(tmp_path: Path) -> tuple[GUIServer, str, Workspace]:
    """Scaffold a workspace with test models and launch a lightweight server."""
    ws = Workspace.init(tmp_path)

    # Scaffold a sample pipeline
    models_dir = tmp_path / "projects" / "core_pipeline" / "models"
    stg = models_dir / "staging" / "raw_events.sql"
    stg.parent.mkdir(parents=True, exist_ok=True)
    stg.write_text("{{ config(materialized='view') }}\nSELECT 1 AS event_id, 'click' AS event_name;\n", encoding="utf-8")

    mart = models_dir / "marts" / "fct_events.sql"
    mart.parent.mkdir(parents=True, exist_ok=True)
    mart.write_text("{{ config(materialized='table') }}\nSELECT event_id, upper(event_name) AS action FROM {{ ref('raw_events') }};\n", encoding="utf-8")

    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    base_url = f"http://127.0.0.1:{port}"
    return server, base_url, ws


def test_pipeline_routes_model_run_save_compile(tmp_path: Path) -> None:
    """Verify running single models, saving model SQL, and compiling Jinja SQL."""
    server, base_url, ws = _setup_test_server(tmp_path)
    try:
        # 1. Compile model DAG
        compile_res = _post_json(
            f"{base_url}/api/pipelines/compile",
            {"project": "core_pipeline"},
        )
        assert compile_res["status"] == "ok"
        assert compile_res["models_count"] == 2
        assert compile_res["has_cycles"] is False

        # 2. Run single model using select parameter
        run_res = _post_json(
            f"{base_url}/api/pipelines/run",
            {"project": "core_pipeline", "select": "raw_events"},
        )
        assert run_res["status"] == "ok"
        assert run_res["total_models"] == 1
        assert run_res["results"][0]["model_name"] == "raw_events"

        # 3. Save modified model SQL
        new_sql = "{{ config(materialized='view') }}\nSELECT 2 AS event_id, 'purchase' AS event_name;\n"
        save_res = _post_json(
            f"{base_url}/api/pipelines/model/save",
            {"project": "core_pipeline", "name": "raw_events", "folder": "staging", "sql": new_sql},
        )
        assert save_res["status"] == "ok"

        # Read back saved file
        saved_file = tmp_path / "projects" / "core_pipeline" / "models" / "staging" / "raw_events.sql"
        assert "purchase" in saved_file.read_text(encoding="utf-8")

        # 4. Error case: Missing model name in save
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _post_json(
                f"{base_url}/api/pipelines/model/save",
                {"project": "core_pipeline", "name": "", "sql": "SELECT 1"},
            )
        assert exc_info.value.code == 400
    finally:
        server.stop()


def test_pipeline_create_delete_model_and_pipeline(tmp_path: Path) -> None:
    """Verify creating a new pipeline, deleting a model, and deleting a pipeline."""
    server, base_url, ws = _setup_test_server(tmp_path)
    try:
        # 1. Create a new pipeline
        create_res = _post_json(
            f"{base_url}/api/pipelines/create",
            {"name": "finance_pipeline", "folder": "Core Pipelines"},
        )
        assert create_res["status"] == "ok"
        assert (tmp_path / "projects" / "finance_pipeline" / "models").exists()

        # 2. Delete a single model
        del_model_res = _post_json(
            f"{base_url}/api/pipelines/model/delete",
            {"project": "core_pipeline", "name": "raw_events"},
        )
        assert del_model_res["status"] == "ok"
        assert not (tmp_path / "projects" / "core_pipeline" / "models" / "staging" / "raw_events.sql").exists()

        # 3. Delete pipeline
        del_res = _post_json(
            f"{base_url}/api/pipelines/delete",
            {"name": "finance_pipeline"},
        )
        assert del_res["status"] == "ok"
        assert not (tmp_path / "projects" / "finance_pipeline").exists()
    finally:
        server.stop()


def test_catalog_routes_save_test_and_query(tmp_path: Path) -> None:
    """Verify Catalog connection creation, testing, deletion, and scratchpad queries."""
    server, base_url, ws = _setup_test_server(tmp_path)
    try:
        # 1. Save valid connection
        save_res = _post_json(
            f"{base_url}/api/catalog/connections",
            {
                "name": "mock_csv_source",
                "type": "csv",
                "tier": "entity",
                "options": {"query": "SELECT 100 AS user_id, 'active' AS status"},
                "description": "Mock source",
            },
        )
        assert save_res["status"] == "ok"

        # 2. List connections
        conns = _get_json(f"{base_url}/api/catalog/connections")
        assert any(c["name"] == "mock_csv_source" for c in conns)

        # 3. Execute scratchpad query
        query_res = _post_json(
            f"{base_url}/api/catalog/query",
            {"query": "SELECT * FROM mock_csv_source WHERE user_id = 100;"},
        )
        assert query_res["row_count"] == 1
        assert query_res["rows"][0][0] == 100

        # Query syntax error
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _post_json(
                f"{base_url}/api/catalog/query",
                {"query": "SELECT * FROM non_existent_table_12345;"},
            )
        assert exc_info.value.code == 400

        # 4. Invalid connection identifier validation
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _post_json(
                f"{base_url}/api/catalog/connections",
                {"name": "invalid-identifier with spaces", "type": "csv"},
            )
        assert exc_info.value.code == 400

        # 5. Delete connection
        del_res = _post_json(
            f"{base_url}/api/catalog/connections/delete",
            {"name": "mock_csv_source"},
        )
        assert del_res["status"] == "ok"

        # Delete 404
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _post_json(
                f"{base_url}/api/catalog/connections/delete",
                {"name": "already_deleted_source"},
            )
        assert exc_info.value.code == 404
    finally:
        server.stop()


def test_monitoring_routes_runs_and_quarantine(tmp_path: Path) -> None:
    """Verify monitoring endpoints for execution runs and quarantine record management."""
    server, base_url, ws = _setup_test_server(tmp_path)
    try:
        # Run pipeline to generate run telemetry
        _post_json(f"{base_url}/api/pipelines/run", {"project": "core_pipeline"})

        # 1. Fetch runs
        data = _get_json(f"{base_url}/api/monitoring/runs?project=core_pipeline")
        runs = data.get("runs", [])
        assert len(runs) >= 1
        assert runs[0]["project"] == "core_pipeline"
        assert runs[0]["status"] == "SUCCESS"

        # 2. Fetch test audits
        audits = _get_json(f"{base_url}/api/monitoring/audits?project=core_pipeline")
        assert "audits" in audits

        # 3. Fetch quarantine records
        q_data = _get_json(f"{base_url}/api/monitoring/quarantine?project=core_pipeline")
        assert "records" in q_data
    finally:
        server.stop()


def test_docs_routes_generation(tmp_path: Path) -> None:
    """Verify documentation generation and dictionary extraction endpoints."""
    server, base_url, ws = _setup_test_server(tmp_path)
    try:
        # Run pipeline first so models exist in catalog
        _post_json(f"{base_url}/api/pipelines/run", {"project": "core_pipeline"})

        # 1. Generate docs
        gen_res = _post_json(
            f"{base_url}/api/docs/generate",
            {"project": "core_pipeline"},
        )
        assert gen_res["status"] == "ok"
        assert Path(gen_res["path"]).exists()

        # 2. Regenerate docs
        regen_res = _post_json(
            f"{base_url}/api/docs/regenerate",
            {"project": "core_pipeline"},
        )
        assert regen_res["status"] == "ok"

        # 3. Query pipeline docs content dictionary
        doc_meta = _get_json(f"{base_url}/api/docs/content?project=core_pipeline")
        assert doc_meta["project_name"] == "core_pipeline"
        assert any(m["name"] == "fct_events" for m in doc_meta["models"])

        # 4. View generated HTML docs
        with urllib.request.urlopen(f"{base_url}/api/docs/view?project=core_pipeline") as res:
            html = res.read().decode("utf-8")
            assert "<html" in html.lower()
            assert "core_pipeline" in html
    finally:
        server.stop()
