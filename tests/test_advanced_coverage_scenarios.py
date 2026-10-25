"""Advanced test suite targeting real-world assertions, quarantine exports, schema mutations, and docs."""

import json
from pathlib import Path
import socket
from typing import Any
import urllib.error
import urllib.request
import duckdb
import pytest

from det.gui.server import GUIServer
from det.testing.base import TestSeverity, TestType
from det.testing.definitions import TestDefinition
from det.testing.evaluator import TestEvaluator
from det.testing.quarantine import QuarantineHandler
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


def _setup_pipeline_workspace(tmp_path: Path) -> tuple[GUIServer, str, Workspace]:
    """Scaffold a workspace with test models and schema.yml for assertion testing."""
    ws = Workspace.init(tmp_path)
    models_dir = tmp_path / "projects" / "orders_pipeline" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    model_file = models_dir / "stg_orders.sql"
    model_file.write_text("{{ config(materialized='table') }}\nSELECT 1 AS order_id, 100.0 AS amount, 'COMPLETED' AS status;\n", encoding="utf-8")

    schema_file = models_dir / "schema.yml"
    schema_file.write_text("""
version: 2
models:
  - name: stg_orders
    description: Staging orders table
    columns:
      - name: order_id
        description: Primary key
        tests:
          - unique
          - not_null
""", encoding="utf-8")

    port = find_free_port()
    server = GUIServer(ws)
    server.start(port=port, blocking=False)
    base_url = f"http://127.0.0.1:{port}"
    return server, base_url, ws


def test_pipeline_test_and_docs_endpoints(tmp_path: Path) -> None:
    """Verify POST /api/pipelines/test and POST /api/pipelines/docs endpoints."""
    server, base_url, ws = _setup_pipeline_workspace(tmp_path)
    try:
        # Run pipeline first so table exists for assertions
        _post_json(f"{base_url}/api/pipelines/run", {"project": "orders_pipeline"})

        # 1. Run pipeline assertion test suite
        test_res = _post_json(
            f"{base_url}/api/pipelines/test",
            {"project": "orders_pipeline"},
        )
        assert test_res["status"] == "ok"
        assert test_res["passed"] >= 2
        assert test_res["failed"] == 0

        # 2. Trigger docs generation from pipeline route
        docs_res = _post_json(
            f"{base_url}/api/pipelines/docs",
            {"project": "orders_pipeline"},
        )
        assert docs_res["status"] == "ok"
    finally:
        server.stop()


def test_model_schema_and_column_description_mutation(tmp_path: Path) -> None:
    """Verify editing model schema and column descriptions via REST APIs."""
    server, base_url, ws = _setup_pipeline_workspace(tmp_path)
    try:
        # 1. Save model schema updates (description, unique_key, tags)
        schema_res = _post_json(
            f"{base_url}/api/pipelines/model/schema",
            {
                "project": "orders_pipeline",
                "model": "stg_orders",
                "description": "Updated staging orders table with audit trail",
                "unique_key": "order_id",
                "tags": ["finance", "staging"],
            },
        )
        assert schema_res["status"] == "ok"

        # Read back schema.yml
        schema_file = tmp_path / "projects" / "orders_pipeline" / "models" / "schema.yml"
        content = schema_file.read_text(encoding="utf-8")
        assert "Updated staging orders table with audit trail" in content

        # 2. Update individual column description
        col_res = _post_json(
            f"{base_url}/api/docs/column/description",
            {
                "project": "orders_pipeline",
                "model": "stg_orders",
                "column": "amount",
                "description": "Gross revenue in USD",
            },
        )
        assert col_res["status"] == "ok"

        updated_content = schema_file.read_text(encoding="utf-8")
        assert "Gross revenue in USD" in updated_content

        # 3. Delete docs endpoint
        del_docs_res = _post_json(
            f"{base_url}/api/docs/delete",
            {"project": "orders_pipeline"},
        )
        assert del_docs_res["status"] == "ok"
    finally:
        server.stop()


def test_quarantine_handler_export_and_isolation(tmp_path: Path) -> None:
    """Verify QuarantineHandler isolates failing rows into quarantine tables."""
    con = duckdb.connect()
    quarantine = QuarantineHandler()
    evaluator = TestEvaluator(quarantine_handler=quarantine)

    con.execute("""
        CREATE TABLE dirty_transactions AS
        SELECT 1 AS tx_id, 50.0 AS amount
        UNION ALL
        SELECT 2, -10.0 -- Failing row
        UNION ALL
        SELECT 3, -99.9; -- Failing row
    """)

    test_def = TestDefinition(
        name="assert_positive_transaction",
        model_name="dirty_transactions",
        column_name="amount",
        test_type=TestType.EXPRESSION,
        severity=TestSeverity.QUARANTINE,
        parameters={"expression": "amount > 0"},
    )

    result = evaluator.evaluate_test(con, test_def)
    assert result.passed is False
    assert result.failing_rows_count == 2
    assert result.quarantined_table is not None

    # Verify quarantined rows table was created in DuckDB
    quarantine_rows = con.execute(f"SELECT * FROM {result.quarantined_table}").fetchall()
    assert len(quarantine_rows) == 2
    amounts = [float(r[1]) for r in quarantine_rows]
    assert -10.0 in amounts
    assert -99.9 in amounts
