"""Tests for Pipeline & DAG REST endpoints in Web IDE."""

import json
from pathlib import Path
import socket
from typing import Any
import urllib.error
import urllib.request

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


def _create_sample_models(base_dir: Path) -> None:
    """Scaffold staging and marts models for testing DAG compilation."""
    models_dir = base_dir / "pipelines" / "default" / "models"
    stg = models_dir / "staging" / "stg_users.sql"
    stg.parent.mkdir(parents=True, exist_ok=True)
    stg.write_text("{{ config(materialized='view') }}\nSELECT 1 AS user_id\n", encoding="utf-8")

    marts = models_dir / "marts" / "fct_users.sql"
    marts.parent.mkdir(parents=True, exist_ok=True)
    marts.write_text("{{ config(materialized='table') }}\nSELECT * FROM {{ ref('stg_users') }}\n", encoding="utf-8")


def test_pipeline_routes_list_and_dag(tmp_path: Path) -> None:
    """Verify /api/pipelines and /api/pipelines/dag return valid topology."""
    ws = Workspace.init(tmp_path)
    _create_sample_models(tmp_path)
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    base_url = f"http://127.0.0.1:{port}"

    try:
        with urllib.request.urlopen(f"{base_url}/api/pipelines") as res:
            pipelines = json.loads(res.read().decode("utf-8"))
            default_p = next(p for p in pipelines if p["name"] == "default")
            assert default_p["models_count"] == 2

        with urllib.request.urlopen(f"{base_url}/api/pipelines/dag?project=default") as res:
            dag = json.loads(res.read().decode("utf-8"))
            assert "stg_users" in [n["id"] for n in dag["nodes"]]
            assert ("stg_users", "fct_users") in [(e["from"], e["to"]) for e in dag["edges"]]

        report = _post_json(f"{base_url}/api/pipelines/run", {"project": "default"})
        assert report["status"] == "ok" and report["total_models"] == 2 and "row_count" in report
    finally:
        server.stop()
        ws.close()


def test_pipeline_model_crud_and_create_pipeline(tmp_path: Path) -> None:
    """Verify saving new model, creating pipeline, and deleting model."""
    ws = Workspace.init(tmp_path)
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    base_url = f"http://127.0.0.1:{port}"

    try:
        resp = _post_json(f"{base_url}/api/pipelines/create", {"name": "marketing"})
        assert resp["status"] == "ok"

        save_payload = {
            "project": "marketing",
            "name": "stg_campaigns",
            "folder": "staging",
            "sql": "{{ config(materialized='view') }}\nSELECT 1 AS camp_id\n",
        }
        assert _post_json(f"{base_url}/api/pipelines/model/save", save_payload)["status"] == "ok"

        del_payload = {"project": "marketing", "name": "stg_campaigns"}
        assert _post_json(f"{base_url}/api/pipelines/model/delete", del_payload)["status"] == "ok"
    finally:
        server.stop()
        ws.close()


def test_pipeline_model_schema_dual_mode(tmp_path: Path) -> None:
    """Verify in-context schema inspection and saving via table and raw YAML."""
    ws = Workspace.init(tmp_path)
    _create_sample_models(tmp_path)
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. GET model schema
        with urllib.request.urlopen(f"{base_url}/api/pipelines/model/schema?project=default&model=stg_users") as res:
            data = json.loads(res.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["model"] == "stg_users"
            assert "raw_yaml" in data
            assert any(c["name"] == "user_id" for c in data["columns"])

        # 2. POST model schema via table (column descriptions)
        table_payload = {
            "project": "default",
            "model": "stg_users",
            "description": "Clean users staging view",
            "columns": [
                {"name": "user_id", "description": "Unique user ID identifier"},
            ],
        }
        res_post = _post_json(f"{base_url}/api/pipelines/model/schema", table_payload)
        assert res_post["status"] == "ok"
        assert res_post["description"] == "Clean users staging view"
        uid_col = next(c for c in res_post["columns"] if c["name"] == "user_id")
        assert uid_col["description"] == "Unique user ID identifier"

        # Verify schema.yml written to disk
        schema_file = tmp_path / "pipelines" / "default" / "models" / "schema.yml"
        assert schema_file.exists()
        assert "Unique user ID identifier" in schema_file.read_text(encoding="utf-8")

        # 3. POST model schema via raw YAML
        yaml_payload = {
            "project": "default",
            "model": "stg_users",
            "raw_yaml": """version: 2
models:
  - name: stg_users
    description: "Updated description via YAML"
    columns:
      - name: user_id
        description: "Primary key via YAML"
        tests:
          - unique
          - not_null
""",
        }
        res_yaml = _post_json(f"{base_url}/api/pipelines/model/schema", yaml_payload)
        assert res_yaml["status"] == "ok"
        assert res_yaml["description"] == "Updated description via YAML"
        uid_col_yaml = next(c for c in res_yaml["columns"] if c["name"] == "user_id")
        assert uid_col_yaml["description"] == "Primary key via YAML"

        # 4. Invalid YAML error handling
        bad_yaml_payload = {
            "project": "default",
            "model": "stg_users",
            "raw_yaml": "version: 2\nmodels: [broken yaml: {",
        }
        try:
            _post_json(f"{base_url}/api/pipelines/model/schema", bad_yaml_payload)
            assert False, "Should have raised HTTP error"
        except urllib.error.HTTPError as err:
            assert err.code == 400
            err_body = json.loads(err.read().decode("utf-8"))
            assert "Invalid YAML syntax" in err_body["error"]
    finally:
        server.stop()
        ws.close()


def test_pipeline_routes_create_and_delete_pipeline(tmp_path: Path) -> None:
    """Verify creating and deleting an entire pipeline project via API."""
    ws = Workspace.init(tmp_path)
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. Create new pipeline
        res_create = _post_json(f"{base_url}/api/pipelines/create", {"name": "finance_pipeline"})
        assert res_create["status"] == "ok"
        assert res_create["created"] == "finance_pipeline"
        assert (tmp_path / "pipelines" / "finance_pipeline" / "models").exists()

        # 2. Delete pipeline
        res_delete = _post_json(f"{base_url}/api/pipelines/delete", {"name": "finance_pipeline"})
        assert res_delete["status"] == "ok"
        assert res_delete["deleted"] == "finance_pipeline"
        assert not (tmp_path / "pipelines" / "finance_pipeline").exists()

        # 3. Deleting non-existent returns 404
        try:
            _post_json(f"{base_url}/api/pipelines/delete", {"name": "non_existent"})
            assert False, "Should have raised 404"
        except urllib.error.HTTPError as err:
            assert err.code == 404
    finally:
        server.stop()
        ws.close()


def test_pipeline_concurrency_guard(tmp_path: Path) -> None:
    """Verify same pipeline running concurrently is blocked, but different pipelines can run concurrently."""
    ws = Workspace.init(tmp_path)
    _create_sample_models(tmp_path)
    # Also scaffold a second pipeline
    p2_dir = tmp_path / "pipelines" / "p2" / "models"
    p2_dir.mkdir(parents=True, exist_ok=True)
    (p2_dir / "m2.sql").write_text("{{ config(materialized='table') }}\nSELECT 42 AS val\n", encoding="utf-8")

    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. Normal run succeeds
        rep = _post_json(f"{base_url}/api/pipelines/run", {"project": "default"})
        assert rep["status"] == "ok"

        # 2. Simulate active run for default
        ws._active_runs.add("default")
        try:
            # Running default again should return 409 Conflict
            _post_json(f"{base_url}/api/pipelines/run", {"project": "default"})
            assert False, "Should have failed with 409 Conflict"
        except urllib.error.HTTPError as err:
            assert err.code == 409
            body = json.loads(err.read().decode("utf-8"))
            assert "already running" in body["error"]

        # 3. But running a DIFFERENT pipeline (p2) while default is running succeeds!
        rep_p2 = _post_json(f"{base_url}/api/pipelines/run", {"project": "p2"})
        assert rep_p2["status"] == "ok"

        # 4. Check /api/pipelines/running endpoint
        with urllib.request.urlopen(f"{base_url}/api/pipelines/running") as res:
            data = json.loads(res.read().decode("utf-8"))
            assert "default" in data["running"]
    finally:
        ws._active_runs.discard("default")
        server.stop()
        ws.close()


def test_pipeline_model_assertion_crud(tmp_path: Path) -> None:
    """Verify adding, updating, and deleting model quality assertions via API."""
    ws = Workspace.init(tmp_path)
    _create_sample_models(tmp_path)

    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. Add new expression assertion to stg_users
        add_res = _post_json(f"{base_url}/api/pipelines/model/assertion/save", {
            "project": "default",
            "model": "stg_users",
            "column": "user_id",
            "type": "expression",
            "expression": "user_id > 0",
            "severity": "warn",
        })
        assert add_res["status"] == "ok"

        # 2. Verify assertion appears in schema API
        with urllib.request.urlopen(f"{base_url}/api/pipelines/model/schema?project=default&model=stg_users") as res:
            schema_data = json.loads(res.read().decode("utf-8"))
            col = next(c for c in schema_data["columns"] if c["name"] == "user_id")
            assert any("expression" in b.lower() for b in col["test_badges"])

        # 3. Delete the assertion
        del_res = _post_json(f"{base_url}/api/pipelines/model/assertion/delete", {
            "project": "default",
            "model": "stg_users",
            "column": "user_id",
            "test_name": "stg_users_user_id_expression",
            "type": "expression",
        })
        assert del_res["status"] == "ok"

        # 4. Verify assertion removed from schema API
        with urllib.request.urlopen(f"{base_url}/api/pipelines/model/schema?project=default&model=stg_users") as res:
            schema_data2 = json.loads(res.read().decode("utf-8"))
            col2 = next(c for c in schema_data2["columns"] if c["name"] == "user_id")
            assert not any("expression" in b.lower() for b in col2["test_badges"])
    finally:
        server.stop()
        ws.close()
