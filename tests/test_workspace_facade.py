"""Tests for Workspace facade coordinating Engine, Catalog, Projects, and Runner."""

from pathlib import Path
from det.catalog.base import ConnectionTier
from det.catalog.definitions import ConnectionDefinition
from det.workspace import Workspace


def test_workspace_init_and_scaffold(tmp_path: Path) -> None:
    """Verify Workspace.init scaffolds standard folder structure (catalog, pipelines, data, extensions, .det)."""
    ws = Workspace.init(tmp_path)
    assert (tmp_path / ".det" / "config.yaml").exists()
    assert (tmp_path / "catalog" / "connections.yaml").exists()
    assert (tmp_path / "pipelines" / "default" / "det_project.yaml").exists()
    assert (tmp_path / "pipelines" / "default" / "models" / "staging").exists()
    assert (tmp_path / "pipelines" / "default" / "models" / "marts").exists()
    assert (tmp_path / "data").exists()
    assert (tmp_path / "extensions").exists()
    assert not (tmp_path / "projects").exists()
    ws.engine.close()


def _setup_feed_connection_and_model(ws: Workspace, tmp_path: Path) -> None:
    csv_file = tmp_path / "raw.csv"
    csv_file.write_text("id,val\n1,alpha\n2,beta\n", encoding="utf-8")
    ws.catalog.add_connection(
        ConnectionDefinition(
            name="raw_feed",
            type="csv",
            tier=ConnectionTier.ENTITY,
            options={"path": str(csv_file).replace("\\", "/")},
        )
    )
    ws.mount_catalog()
    model_sql = "{{ config(materialized='table', unique_key='id') }}\nSELECT id, UPPER(val) AS val FROM raw_feed"
    model_file = tmp_path / "pipelines" / "default" / "models" / "staging" / "stg_feed.sql"
    model_file.write_text(model_sql, encoding="utf-8")


def test_workspace_end_to_end_flow(tmp_path: Path) -> None:
    """Verify complete lifecycle: catalog connection -> model run -> test -> docs."""
    ws = Workspace.init(tmp_path)
    _setup_feed_connection_and_model(ws, tmp_path)

    run_report = ws.run()
    assert run_report.is_successful is True
    assert run_report.succeeded == 1
    assert len(ws.engine.execute("SELECT * FROM stg_feed").rows) == 2

    test_report = ws.test()
    assert test_report.is_successful is True
    assert test_report.passed == 2

    docs_file = ws.generate_docs()
    assert docs_file.exists()
    assert "stg_feed" in docs_file.read_text(encoding="utf-8")

    cat_results = ws.test_catalog()
    assert "raw_feed" in cat_results and cat_results["raw_feed"].is_healthy is True
    ws.engine.close()

