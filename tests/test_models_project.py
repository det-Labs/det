"""Tests for multi-project workspace discovery and DAG compilation."""

from pathlib import Path
from det.catalog.base import ConnectionTier
from det.catalog.definitions import ConnectionDefinition
from det.catalog.manager import CatalogManager
from det.models.project import ProjectManager


def test_discover_multi_project_directories(tmp_path: Path) -> None:
    """Verify scanning projects/ discovers all active projects."""
    (tmp_path / "projects" / "finance" / "models").mkdir(parents=True)
    (tmp_path / "projects" / "marketing" / "models").mkdir(parents=True)
    (tmp_path / "projects" / "_hidden" / "models").mkdir(parents=True)

    pm = ProjectManager(tmp_path)
    projects = pm.discover_projects()
    assert projects == ["finance", "marketing"]


def test_discover_fallback_single_project(tmp_path: Path) -> None:
    """Verify fallback to root models/ when projects/ directory is absent."""
    (tmp_path / "models").mkdir(parents=True)
    pm = ProjectManager(tmp_path)
    assert pm.discover_projects() == ["default"]


def _setup_catalog_and_models(tmp_path: Path) -> CatalogManager:
    catalog_mgr = CatalogManager(tmp_path / "catalog" / "connections.yaml")
    catalog_mgr.add_connection(
        ConnectionDefinition(
            name="pos_sales",
            type="csv",
            tier=ConnectionTier.ENTITY,
            options={"path": "pos.csv"},
        )
    )
    models_dir = tmp_path / "projects" / "retail" / "models"
    models_dir.mkdir(parents=True)
    stg_sql = "{{ config(materialized='table') }}\nSELECT * FROM pos_sales"
    (models_dir / "stg_sales.sql").write_text(stg_sql, encoding="utf-8")
    mart_sql = "{{ config(materialized='table') }}\nSELECT * FROM {{ ref('stg_sales') }}"
    (models_dir / "fct_sales.sql").write_text(mart_sql, encoding="utf-8")
    return catalog_mgr


def test_project_manager_loads_models_and_auto_resolves_connections(tmp_path: Path) -> None:
    """Verify ProjectManager parses models and cross-references CatalogManager connections."""
    catalog_mgr = _setup_catalog_and_models(tmp_path)
    pm = ProjectManager(tmp_path, catalog_manager=catalog_mgr)
    dag = pm.build_dag("retail")

    stg_model = dag.get_model("stg_sales")
    assert stg_model is not None
    assert "pos_sales" in stg_model.direct_connections

    order = dag.get_execution_order()
    assert order == ["stg_sales", "fct_sales"]

