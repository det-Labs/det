"""Unit tests for det.pipeline module and Pipeline REST API."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from det.gui.server import app, set_pipeline_service
from det.pipeline import PipelineService


@pytest.fixture
def temp_pipeline_service(tmp_path: Path) -> PipelineService:
    """Fixture providing a PipelineService bound to an isolated temp YAML file."""
    yaml_path = tmp_path / "test_pipelines.yaml"
    return PipelineService(yaml_path)


def test_project_crud(temp_pipeline_service: PipelineService):
    """Test full Project lifecycle: create, list, edit, delete."""
    service = temp_pipeline_service

    # Initial load should have default starter project
    projects = service.list_projects()
    assert len(projects) == 1
    assert projects[0].name == "default_project"

    # Create project
    proj = service.create_project(name="marketing_etl", description="Marketing analytics")
    assert proj.name == "marketing_etl"
    assert proj.description == "Marketing analytics"
    assert len(proj.categories) == 1
    assert proj.categories[0].name == "default"

    # Duplicate name should raise ValueError
    with pytest.raises(ValueError, match="already exists"):
        service.create_project(name="marketing_etl")

    # List projects
    all_projs = service.list_projects()
    assert len(all_projs) == 2

    # Edit project
    updated = service.update_project(
        name="marketing_etl",
        new_name="growth_marketing",
        description="Updated growth analytics",
    )
    assert updated.name == "growth_marketing"
    assert updated.description == "Updated growth analytics"

    # Delete project
    assert service.delete_project("growth_marketing") is True
    assert service.get_project("growth_marketing") is None
    assert len(service.list_projects()) == 1


def test_category_crud(temp_pipeline_service: PipelineService):
    """Test Category lifecycle within a project: create, list, edit, delete."""
    service = temp_pipeline_service
    service.create_project("finance", description="Finance workflows")

    # Create category
    cat = service.create_category("finance", "daily_reconciliation", description="Daily ledger checks")
    assert cat.name == "daily_reconciliation"
    assert cat.description == "Daily ledger checks"

    # Duplicate category in same project should raise ValueError
    with pytest.raises(ValueError, match="already exists"):
        service.create_category("finance", "daily_reconciliation")

    # List categories
    cats = service.list_categories("finance")
    cat_names = [c.name for c in cats]
    assert "default" in cat_names
    assert "daily_reconciliation" in cat_names

    # Edit category
    edited = service.update_category(
        "finance",
        "daily_reconciliation",
        new_name="hourly_reconciliation",
        description="Hourly automated checks",
    )
    assert edited.name == "hourly_reconciliation"
    assert edited.description == "Hourly automated checks"

    # Delete category
    assert service.delete_category("finance", "hourly_reconciliation") is True
    assert service.get_category("finance", "hourly_reconciliation") is None


def test_tree_view(temp_pipeline_service: PipelineService):
    """Test tree hierarchy generation."""
    service = temp_pipeline_service
    tree = service.get_tree()
    assert "total_projects" in tree
    assert "projects" in tree
    assert tree["total_projects"] >= 1


def test_pipeline_api_endpoints(temp_pipeline_service: PipelineService):
    """Test FastAPI endpoints for pipeline management."""
    set_pipeline_service(temp_pipeline_service)
    client = TestClient(app)

    # 1. Get Tree
    res = client.get("/api/pipelines/tree")
    assert res.status_code == 200
    data = res.json()
    assert "total_projects" in data

    # 2. Create Project
    res = client.post("/api/pipelines/projects", json={"name": "crm_sync", "description": "CRM data pipelines"})
    assert res.status_code == 201
    assert res.json()["name"] == "crm_sync"

    # 3. Update Project
    res = client.put("/api/pipelines/projects/crm_sync", json={"new_name": "crm_hubspot", "description": "HubSpot sync"})
    assert res.status_code == 200
    assert res.json()["name"] == "crm_hubspot"

    # 4. Create Category
    res = client.post("/api/pipelines/projects/crm_hubspot/categories", json={"name": "contacts", "description": "Contacts sync"})
    assert res.status_code == 201
    assert res.json()["name"] == "contacts"

    # 5. Update Category
    res = client.put("/api/pipelines/projects/crm_hubspot/categories/contacts", json={"new_name": "deals", "description": "Deals sync"})
    assert res.status_code == 200
    assert res.json()["name"] == "deals"

    # 6. Delete Category
    res = client.delete("/api/pipelines/projects/crm_hubspot/categories/deals")
    assert res.status_code == 204

    # 7. Delete Project
    res = client.delete("/api/pipelines/projects/crm_hubspot")
    assert res.status_code == 204

