"""Tests for Web IDE HTTP server, REST endpoints, and UI extensibility."""

import json
from pathlib import Path
import socket
import urllib.request
import pytest

from det.gui.base import UIModule, UITheme
from det.gui.routes.ui_routes import UIRouteHandler
from det.gui.server import GUIServer
from det.workspace import Workspace


def find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post_json(url: str, data: dict) -> dict:
    """Helper to issue a JSON POST request and return parsed response."""
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode("utf-8"))


def _verify_server_static_and_status(base_url: str) -> None:
    """Helper to verify static files and status endpoint."""
    with urllib.request.urlopen(f"{base_url}/") as res:
        assert res.status == 200 and "det" in res.read().decode("utf-8")
    with urllib.request.urlopen(f"{base_url}/style.css") as res:
        assert res.status == 200 and "text/css" in res.headers.get("Content-Type", "")
    with urllib.request.urlopen(f"{base_url}/api/status") as res:
        assert json.loads(res.read().decode("utf-8"))["status"] == "ready"


def _verify_explorer_and_manifest(base_url: str) -> None:
    """Helper to verify explorer and manifest API responses."""
    with urllib.request.urlopen(f"{base_url}/api/explorer") as res:
        explorer = json.loads(res.read().decode("utf-8"))
        assert len(explorer["projects"]) >= 1
        assert any(m["name"] == "sample" for m in explorer["projects"][0]["models"])
    with urllib.request.urlopen(f"{base_url}/api/ui/manifest") as res:
        manifest = json.loads(res.read().decode("utf-8"))
        module_ids = [m["id"] for m in manifest["modules"]]
        for mod in ["catalog", "pipelines", "monitoring", "docs"]:
            assert mod in module_ids


def test_gui_server_lifecycle_and_endpoints(tmp_path: Path) -> None:
    """Verify GUIServer starts, serves assets & endpoints, and stops cleanly."""
    ws = Workspace.init(tmp_path)
    model_file = tmp_path / "projects" / "default" / "models" / "staging" / "sample.sql"
    model_file.write_text("{{ config(materialized='table') }}\nSELECT 100 AS id, 'alpha' AS tag\n", encoding="utf-8")
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    try:
        base_url = f"http://127.0.0.1:{port}"
        _verify_server_static_and_status(base_url)
        _verify_explorer_and_manifest(base_url)
    finally:
        server.stop()
        ws.close()


def test_ui_extensibility_registration() -> None:
    """Verify extensions can register custom UI modules and color themes."""
    ui_handler = UIRouteHandler()
    custom_mod = UIModule(id="lineage_3d", title="3D Lineage", icon="cube", order=25, description="3D graph")
    ui_handler.register_module(custom_mod)
    custom_theme = UITheme(id="cyberpunk", name="Cyberpunk Neon", css_variables={"--bg": "#0f051d"})
    ui_handler.register_theme(custom_theme)

    manifest_mods = [m.id for m in ui_handler._modules]
    assert "lineage_3d" in manifest_mods
    assert manifest_mods.index("lineage_3d") == 2
    assert "cyberpunk" in [t.id for t in ui_handler._themes]


def test_gui_cors_preflight(tmp_path: Path) -> None:
    """Verify CORS preflight OPTIONS request returns 200 with headers."""
    ws = Workspace.init(tmp_path)
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/status", method="OPTIONS")
        with urllib.request.urlopen(req) as res:
            assert res.status == 200
            assert res.headers.get("Access-Control-Allow-Origin") == "*"
    finally:
        server.stop()
        ws.close()


def test_gui_catalog_endpoints(tmp_path: Path) -> None:
    """Verify catalog connectors, connections CRUD, testing, and query endpoints."""
    ws = Workspace.init(tmp_path)
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    base_url = f"http://127.0.0.1:{port}"
    try:
        with urllib.request.urlopen(f"{base_url}/api/catalog/connectors") as res:
            assert res.status == 200
        add_res = _post_json(f"{base_url}/api/catalog/connections", {
            "name": "mem_db", "type": "duckdb", "tier": "database", "options": {"path": ":memory:"}
        })
        assert add_res["status"] == "ok"
        test_res = _post_json(f"{base_url}/api/catalog/test", {"name": "mem_db"})
        assert test_res["healthy"] is True
        query_res = _post_json(f"{base_url}/api/catalog/query", {"query": "SELECT 42 AS answer, 'det' AS app"})
        assert query_res["columns"] == ["answer", "app"] and query_res["rows"] == [[42, "det"]]
        del_res = _post_json(f"{base_url}/api/catalog/connections/delete", {"name": "mem_db"})
        assert del_res["status"] == "ok"
    finally:
        server.stop()
        ws.close()
