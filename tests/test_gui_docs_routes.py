"""Tests for Docs API endpoints, schema introspection, and static docs generation."""

import json
from pathlib import Path
import socket
import urllib.request

from det.gui.server import GUIServer
from det.workspace import Workspace


def find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _setup_test_workspace(tmp_path: Path) -> Workspace:
    """Create test workspace with sample models, configs, and tests."""
    ws = Workspace.init(tmp_path)
    model_dir = tmp_path / "projects" / "default" / "models" / "staging"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_file = model_dir / "stg_customers.sql"
    model_file.write_text(
        "{{ config(materialized='table', unique_key='id', description='Customer records') }}\n"
        "SELECT 1 AS id, 'Alice' AS name, '2026-01-01' AS signup_date\n",
        encoding="utf-8",
    )
    return ws


def test_docs_content_api_endpoint(tmp_path: Path) -> None:
    """Verify /api/docs/content introspects columns, types, and test badges."""
    ws = _setup_test_workspace(tmp_path)
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    try:
        url = f"http://127.0.0.1:{port}/api/docs/content?project=default"
        with urllib.request.urlopen(url) as res:
            assert res.status == 200
            data = json.loads(res.read().decode("utf-8"))
            assert data["project_name"] == "default"
            assert data["total_models"] == 1
            assert len(data["models"]) == 1
            m = data["models"][0]
            assert m["name"] == "stg_customers"
            assert m["materialization"] == "table"
            col_names = [c["name"] for c in m["columns"]]
            assert "id" in col_names
            assert "name" in col_names
            # Verify unique test badge on unique_key id
            id_col = next(c for c in m["columns"] if c["name"] == "id")
            assert "UNIQUE" in id_col["test_badges"]
    finally:
        server.stop()
        ws.close()


def test_docs_generate_api_endpoint(tmp_path: Path) -> None:
    """Verify /api/docs/generate triggers static HTML compilation."""
    ws = _setup_test_workspace(tmp_path)
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    try:
        url = f"http://127.0.0.1:{port}/api/docs/generate"
        payload = json.dumps({"project": "default"}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req) as res:
            assert res.status == 200
            data = json.loads(res.read().decode("utf-8"))
            assert data["status"] == "ok"
            out_path = Path(data["path"])
            assert out_path.exists()
            assert "index.html" in str(out_path)
    finally:
        server.stop()
        ws.close()


def test_docs_delete_api_endpoint(tmp_path: Path) -> None:
    """Verify /api/docs/delete removes static HTML compilation on disk."""
    ws = _setup_test_workspace(tmp_path)
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    try:
        # First generate
        ws.generate_docs(project="default")
        gen_dir = ws.root / "projects" / "default" / "docs" if (ws.root / "projects").exists() else ws.root / "docs"
        assert gen_dir.exists()

        # Call delete endpoint
        url = f"http://127.0.0.1:{port}/api/docs/delete"
        payload = json.dumps({"project": "default"}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req) as res:
            assert res.status == 200
            data = json.loads(res.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data["deleted"] is True
            assert not gen_dir.exists()
    finally:
        server.stop()
        ws.close()


def test_docs_regenerate_and_view_api_endpoints(tmp_path: Path) -> None:
    """Verify regenerating docs, viewing HTML docs, and metadata status flag."""
    ws = _setup_test_workspace(tmp_path)
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    try:
        content_url = f"http://127.0.0.1:{port}/api/docs/content?project=default"
        # 1. Initially has_generated_docs is False
        with urllib.request.urlopen(content_url) as res:
            data = json.loads(res.read().decode("utf-8"))
            assert data["has_generated_docs"] is False

        # 2. View endpoint before generation returns 404
        view_url = f"http://127.0.0.1:{port}/api/docs/view?project=default"
        try:
            urllib.request.urlopen(view_url)
            assert False, "Should have returned 404"
        except urllib.error.HTTPError as err:
            assert err.code == 404

        # 3. Call /api/docs/regenerate
        regen_url = f"http://127.0.0.1:{port}/api/docs/regenerate"
        payload = json.dumps({"project": "default"}).encode("utf-8")
        req = urllib.request.Request(
            regen_url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req) as res:
            assert res.status == 200
            data = json.loads(res.read().decode("utf-8"))
            assert data["status"] == "ok"
            assert data.get("regenerated") is True

        # 4. Now has_generated_docs is True
        with urllib.request.urlopen(content_url) as res:
            data = json.loads(res.read().decode("utf-8"))
            assert data["has_generated_docs"] is True
            assert data["generated_docs_path"] is not None

        # 5. View endpoint returns HTML content
        with urllib.request.urlopen(view_url) as res:
            assert res.status == 200
            assert "text/html" in res.headers.get("Content-Type", "")
            body = res.read().decode("utf-8")
            assert "<!DOCTYPE html>" in body or "Data Dictionary" in body or "html" in body
    finally:
        server.stop()
        ws.close()


