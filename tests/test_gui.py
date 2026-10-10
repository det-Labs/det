"""Unit tests for det.gui FastAPI server endpoints."""

from pathlib import Path

import polars as pl
import pytest
from fastapi.testclient import TestClient

from det.catalog.service import CatalogService
from det.gui.server import app, set_service


@pytest.fixture
def gui_client(tmp_path: Path):
    """Fixture providing a FastAPI TestClient wired to a temporary catalog."""
    catalog_path = tmp_path / "gui_test_catalog.yaml"
    service = CatalogService(catalog_path)
    set_service(service)

    # Create dummy parquet file to test scan endpoint
    data_file = tmp_path / "metrics.parquet"
    df = pl.DataFrame({"metric": ["cpu", "memory"], "val": [45.2, 88.0]})
    df.write_parquet(data_file)

    client = TestClient(app)
    return {
        "client": client,
        "service": service,
        "catalog_path": catalog_path,
        "data_file": data_file,
        "tmp_path": tmp_path,
    }


def test_gui_catalog_status(gui_client):
    client = gui_client["client"]
    res = client.get("/api/catalog/status")
    assert res.status_code == 200
    data = res.json()
    assert "active_path" in data
    assert data["dataset_count"] == 0


def test_gui_scan_and_crud(gui_client):
    client = gui_client["client"]
    data_file = gui_client["data_file"]

    # 1. Test scan endpoint
    scan_res = client.post("/api/scan", json={"location": str(data_file)})
    assert scan_res.status_code == 200
    scan_data = scan_res.json()
    assert scan_data["format"] == "parquet"
    assert len(scan_data["columns"]) == 2

    # 2. Register new dataset via POST /api/datasets
    payload = {
        "id": "telemetry.metrics",
        "name": "metrics",
        "namespace": "telemetry",
        "format": "parquet",
        "location": str(data_file),
        "description": "Server health metrics",
        "columns": scan_data["columns"],
        "tags": ["monitoring"],
    }
    create_res = client.post("/api/datasets", json=payload)
    assert create_res.status_code == 201

    # 3. List datasets
    list_res = client.get("/api/datasets")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # 4. Get dataset
    get_res = client.get("/api/datasets/telemetry.metrics")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "metrics"

    # 5. Delete dataset
    del_res = client.delete("/api/datasets/telemetry.metrics")
    assert del_res.status_code == 204

    # Verify deleted
    list_after = client.get("/api/datasets")
    assert len(list_after.json()) == 0


def test_gui_switch_catalog(gui_client):
    client = gui_client["client"]
    new_path = gui_client["tmp_path"] / "switched_catalog.yaml"

    res = client.post(
        "/api/catalog/switch",
        json={"path": str(new_path), "set_as_default": False},
    )
    assert res.status_code == 200
    assert res.json()["active_path"] == str(new_path.resolve())


def test_gui_create_catalog(gui_client):
    client = gui_client["client"]
    new_path = gui_client["tmp_path"] / "created_catalog.yaml"

    res = client.post(
        "/api/catalog/create",
        json={"path": str(new_path), "name": "API Catalog", "set_as_default": False},
    )
    assert res.status_code == 200
    assert res.json()["active_path"] == str(new_path.resolve())
    assert res.json()["dataset_count"] == 0

    # Repeat without overwrite should fail with 409 Conflict
    dup_res = client.post(
        "/api/catalog/create",
        json={"path": str(new_path), "name": "API Catalog", "overwrite": False},
    )
    assert dup_res.status_code == 409


def test_gui_namespace_endpoints(gui_client):
    client = gui_client["client"]

    # 1. Create namespace
    create_res = client.post("/api/namespaces", json={"name": "ecommerce"})
    assert create_res.status_code == 201
    assert create_res.json()["name"] == "ecommerce"

    # 2. List namespaces
    list_res = client.get("/api/namespaces")
    assert list_res.status_code == 200
    names = [n["name"] for n in list_res.json()]
    assert "ecommerce" in names

    # 3. Rename namespace
    rename_res = client.put("/api/namespaces/ecommerce", json={"new_name": "shop"})
    assert rename_res.status_code == 200
    assert rename_res.json()["new_name"] == "shop"

    # 4. Delete namespace
    del_res = client.delete("/api/namespaces/shop?reassign_to=default")
    assert del_res.status_code == 200


def test_gui_tree_and_multi_catalog(gui_client):
    client = gui_client["client"]
    tmp_path = gui_client["tmp_path"]

    # 1. Test get tree
    tree_res = client.get("/api/tree")
    assert tree_res.status_code == 200
    catalogs = tree_res.json()["catalogs"]
    assert len(catalogs) >= 1
    assert "namespaces" in catalogs[0]

    # 2. Open another catalog
    cat2_path = tmp_path / "extra_cat.yaml"
    open_res = client.post("/api/catalog/open", json={"path": str(cat2_path), "set_as_default": False})
    assert open_res.status_code == 200
    open_catalogs = open_res.json()["catalogs"]
    paths = [c["path"] for c in open_catalogs]
    assert str(cat2_path.resolve()) in paths

    # 3. Set default catalog
    def_res = client.post("/api/catalog/set-default", json={"path": str(cat2_path)})
    assert def_res.status_code == 200

    # 4. Remove extra catalog from explorer
    rem_res = client.post("/api/catalog/remove", json={"path": str(cat2_path)})
    assert rem_res.status_code == 200


def test_gui_pipeline_endpoints(tmp_path: Path):
    """Test pipeline CRUD and tree endpoints on FastAPI server."""
    from det.gui.server import set_pipeline_service
    from det.pipeline import PipelineService

    pipe_path = tmp_path / "gui_pipelines.yaml"
    pipe_svc = PipelineService(file_path=pipe_path)
    set_pipeline_service(pipe_svc)

    client = TestClient(app)

    # 1. Tree
    tree_res = client.get("/api/pipelines/tree")
    assert tree_res.status_code == 200
    assert "projects" in tree_res.json()

    # 2. Create project
    proj_res = client.post(
        "/api/pipelines/projects",
        json={"name": "ecommerce_etl", "description": "Ecommerce data workflows"},
    )
    assert proj_res.status_code == 201
    assert proj_res.json()["name"] == "ecommerce_etl"

    # 3. Create category
    cat_res = client.post(
        "/api/pipelines/projects/ecommerce_etl/categories",
        json={"name": "orders_stage", "description": "Order processing category"},
    )
    assert cat_res.status_code == 201
    assert cat_res.json()["name"] == "orders_stage"

    # 4. Update category
    cat_up = client.put(
        "/api/pipelines/projects/ecommerce_etl/categories/orders_stage",
        json={"new_name": "orders_clean", "description": "Cleaned orders"},
    )
    assert cat_up.status_code == 200
    assert cat_up.json()["name"] == "orders_clean"

    # 5. Delete category
    cat_del = client.delete("/api/pipelines/projects/ecommerce_etl/categories/orders_clean")
    assert cat_del.status_code == 204

    # 6. Delete project
    proj_del = client.delete("/api/pipelines/projects/ecommerce_etl")
    assert proj_del.status_code == 204


