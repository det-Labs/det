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
