"""Tests for Pipeline & DAG REST endpoints in Web IDE."""

import json
from pathlib import Path
import socket
from typing import Any
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
    models_dir = base_dir / "projects" / "default" / "models"
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
