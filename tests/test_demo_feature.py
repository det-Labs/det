"""Tests for Demo / Sample Workspace Generation and Tour Endpoints."""

import json
from pathlib import Path
import socket
from typing import Any
import urllib.request

from det.cli import build_parser, handle_demo
from det.demo import (
    generate_demo_connections,
    generate_demo_datasets,
    generate_demo_pipelines,
    setup_demo_workspace,
)
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


def test_demo_generator_functions(tmp_path: Path) -> None:
    """Verify dataset, connection, and pipeline generation directly."""
    # 1. Generate datasets
    datasets = generate_demo_datasets(tmp_path)
    assert datasets["customers"].exists()
    assert datasets["sales_orders"].exists()
    assert datasets["web_events"].exists()
    assert datasets["inventory"].exists()

    # 2. Generate connections
    conn_file = generate_demo_connections(tmp_path)
    assert conn_file.exists()
    content = conn_file.read_text(encoding="utf-8")
    assert "customers_data" in content
    assert "sales_orders_data" in content

    # 3. Generate pipelines
    projects = generate_demo_pipelines(tmp_path)
    assert "retail_medallion" in projects
    assert "export_analytics" in projects

    # Check that SQL models exist
    bronze_cust = tmp_path / "pipelines" / "sample_pipelines" / "retail_medallion" / "models" / "bronze" / "bronze_customers.sql"
    assert bronze_cust.exists()
    assert "customers_data" in bronze_cust.read_text(encoding="utf-8")


def test_setup_demo_workspace_and_execution(tmp_path: Path) -> None:
    """Verify full demo workspace setup and end-to-end DAG execution."""
    res = setup_demo_workspace(tmp_path)
    assert res["status"] == "ok"
    assert len(res["pipelines"]) == 2
    assert "retail_medallion" in res["pipelines"]
    assert "export_analytics" in res["pipelines"]

    ws = Workspace.open(tmp_path)
    try:
        # Run retail_medallion pipeline (15 models across Bronze, Silver, Gold)
        rep = ws.run(project="retail_medallion")
        assert rep.is_successful
        assert rep.total_models == 15
        assert rep.succeeded == 15

        # Test retail_medallion assertions (default + custom expressions)
        test_rep = ws.test(project="retail_medallion")
        assert test_rep.is_successful
        assert test_rep.passed >= 25
        assert test_rep.errored == 0

        # Run export_analytics pipeline (7 models with Parquet, CSV, Excel destinations)
        rep_exp = ws.run(project="export_analytics")
        assert rep_exp.is_successful
        assert rep_exp.total_models == 7
        assert rep_exp.succeeded == 7

        # Test export_analytics assertions
        test_exp_rep = ws.test(project="export_analytics")
        assert test_exp_rep.is_successful
        assert test_exp_rep.passed >= 15
        assert test_exp_rep.errored == 0

        # Verify export files exist and are populated
        export_dir = tmp_path / "data" / "exports"
        assert (export_dir / "sales_summary.parquet").exists()
        assert (export_dir / "finance_reconciliation.csv").exists()
        assert (export_dir / "inventory_audit.xlsx").exists()
        assert (export_dir / "executive_flash.parquet").exists()
        assert (export_dir / "executive_flash.csv").exists()
        assert (export_dir / "executive_flash.xlsx").exists()
        assert (export_dir / "weekly_marketing_kpis.parquet").exists()
        assert (export_dir / "weekly_marketing_kpis.csv").exists()

        assert (export_dir / "finance_reconciliation.csv").stat().st_size > 0
        assert (export_dir / "inventory_audit.xlsx").stat().st_size > 0
    finally:
        ws.close()


def test_demo_cli_command(tmp_path: Path, capsys: Any) -> None:
    """Verify det demo CLI parser and handler."""
    parser = build_parser()
    args = parser.parse_args(["demo", str(tmp_path)])
    code = handle_demo(args)
    assert code == 0
    captured = capsys.readouterr()
    assert "Scaffolding det demo workspace" in captured.out
    assert (tmp_path / "data" / "customers.parquet").exists()
    assert (tmp_path / "pipelines" / "sample_pipelines" / "retail_medallion").exists()


def test_demo_http_routes(tmp_path: Path) -> None:
    """Verify /api/demo/setup and /api/demo/status endpoints on GUIServer."""
    ws = Workspace.init(tmp_path)
    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    base_url = f"http://127.0.0.1:{port}"

    try:
        # 1. GET /api/demo/status before setup
        with urllib.request.urlopen(f"{base_url}/api/demo/status") as res:
            status_data = json.loads(res.read().decode("utf-8"))
            assert status_data["status"] == "ok"
            assert status_data["has_demo"] is False

        # 2. POST /api/demo/setup
        setup_resp = _post_json(f"{base_url}/api/demo/setup", {})
        assert setup_resp["status"] == "ok"
        assert len(setup_resp["details"]["pipelines"]) == 2

        # 3. GET /api/demo/status after setup
        with urllib.request.urlopen(f"{base_url}/api/demo/status") as res:
            status_data2 = json.loads(res.read().decode("utf-8"))
            assert status_data2["has_demo"] is True

        # 4. Verify pipelines are now listed in /api/pipelines
        with urllib.request.urlopen(f"{base_url}/api/pipelines") as res:
            pipes = json.loads(res.read().decode("utf-8"))
            pipe_names = [p["name"] for p in pipes]
            assert "retail_medallion" in pipe_names
            assert "export_analytics" in pipe_names
            med_pipe = next(p for p in pipes if p["name"] == "retail_medallion")
            assert med_pipe["folder"] == "sample_pipelines"
    finally:
        server.stop()
        ws.close()

