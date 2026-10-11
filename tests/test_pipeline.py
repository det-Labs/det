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
    cat = service.create_category(
        "finance", "daily_reconciliation", description="Daily ledger checks"
    )
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
    res = client.post(
        "/api/pipelines/projects", json={"name": "crm_sync", "description": "CRM data pipelines"}
    )
    assert res.status_code == 201
    assert res.json()["name"] == "crm_sync"

    # 3. Update Project
    res = client.put(
        "/api/pipelines/projects/crm_sync",
        json={"new_name": "crm_hubspot", "description": "HubSpot sync"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "crm_hubspot"

    # 4. Create Category
    res = client.post(
        "/api/pipelines/projects/crm_hubspot/categories",
        json={"name": "contacts", "description": "Contacts sync"},
    )
    assert res.status_code == 201
    assert res.json()["name"] == "contacts"

    # 5. Update Category
    res = client.put(
        "/api/pipelines/projects/crm_hubspot/categories/contacts",
        json={"new_name": "deals", "description": "Deals sync"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "deals"

    # 6. Delete Category
    res = client.delete("/api/pipelines/projects/crm_hubspot/categories/deals")
    assert res.status_code == 204

    # 7. Delete Project
    res = client.delete("/api/pipelines/projects/crm_hubspot")
    assert res.status_code == 204


def test_multi_file_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test configuration helpers for managing known pipeline files."""
    import det.pipeline.config as pipe_cfg

    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(pipe_cfg, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(pipe_cfg, "CONFIG_DIR", tmp_path)

    p1 = tmp_path / "pipelines1.yaml"
    p2 = tmp_path / "pipelines2.yaml"
    p1.touch()
    p2.touch()

    pipe_cfg.set_default_pipeline_path(p1)
    assert pipe_cfg.get_default_pipeline_path().resolve() == p1.resolve()

    pipe_cfg.add_known_pipeline_file(p2)
    known = pipe_cfg.get_known_pipeline_files()
    assert p1.resolve() in known
    assert p2.resolve() in known

    assert pipe_cfg.remove_known_pipeline_file(p2) is True
    assert p2.resolve() not in pipe_cfg.get_known_pipeline_files()


def test_pipeline_service_multi_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test PipelineService multi-file creation, switching, and scoped CRUD."""
    import det.pipeline.config as pipe_cfg

    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(pipe_cfg, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(pipe_cfg, "CONFIG_DIR", tmp_path)

    f1 = tmp_path / "etl_alpha.yaml"
    f2 = tmp_path / "etl_beta.yaml"

    service = PipelineService(f1)
    service.create_pipeline_file(f1, set_as_default=True)
    service.create_pipeline_file(f2)
    assert service.active_path == f2.resolve()

    service.switch_file(f1)
    assert service.active_path == f1.resolve()

    service.create_project("alpha_proj", description="Project in alpha file")

    # Create project scoped to f2
    service.create_project("beta_proj", description="Project in beta file", file_path=f2)

    # Verify project isolation
    alpha_projs = service.list_projects(file_path=f1)
    beta_projs = service.list_projects(file_path=f2)
    assert any(p.name == "alpha_proj" for p in alpha_projs)
    assert not any(p.name == "beta_proj" for p in alpha_projs)
    assert any(p.name == "beta_proj" for p in beta_projs)

    # Full tree verification
    full_tree = service.get_full_tree()
    assert len(full_tree) >= 2
    f2_entry = next(item for item in full_tree if Path(item["path"]).resolve() == f2.resolve())
    assert f2_entry["total_projects"] >= 1

    # Switch file
    service.switch_file(f2)
    assert service.active_path == f2.resolve()

    # Export yaml
    yaml_text = service.export_yaml(f2)
    assert "beta_proj" in yaml_text


def test_pipeline_file_api_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test REST API endpoints for multi-file pipeline operations."""
    import det.pipeline.config as pipe_cfg

    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(pipe_cfg, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(pipe_cfg, "CONFIG_DIR", tmp_path)

    f1 = tmp_path / "api_p1.yaml"
    f2 = tmp_path / "api_p2.yaml"

    service = PipelineService(f1)
    set_pipeline_service(service)
    client = TestClient(app)

    # 1. Create pipeline file
    res = client.post("/api/pipelines/file/create", json={"path": str(f1), "set_as_default": True})
    assert res.status_code == 200
    assert res.json()["active_path"] == str(f1.resolve())

    # 2. Open another pipeline file
    res = client.post("/api/pipelines/file/open", json={"path": str(f2), "set_as_default": False})
    assert res.status_code == 200
    assert res.json()["active_path"] == str(f2.resolve())

    # 3. Create project in f1 via query parameter
    res = client.post(
        f"/api/pipelines/projects?file_path={f1}",
        json={"name": "scoped_p1", "description": "in p1"},
    )
    assert res.status_code == 201

    # 4. Get tree with file_path
    res = client.get(f"/api/pipelines/tree?file_path={f1}")
    assert res.status_code == 200
    data = res.json()
    assert "pipeline_files" in data
    assert any(p["name"] == "scoped_p1" for p in data["projects"])

    # 5. Get yaml
    res = client.get(f"/api/pipelines/yaml?path={f1}")
    assert res.status_code == 200
    assert "scoped_p1" in res.text

    # 6. Switch back to f1
    res = client.post("/api/pipelines/file/switch", json={"path": str(f1), "set_as_default": False})
    assert res.status_code == 200
    assert res.json()["active_path"] == str(f1.resolve())

    # 7. Set default
    res = client.post("/api/pipelines/file/set-default", json={"path": str(f2)})
    assert res.status_code == 200

    # 8. Remove file
    res = client.post("/api/pipelines/file/remove", json={"path": str(f2)})
    assert res.status_code == 200


def test_pipeline_file_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Test CLI commands for pipeline file management."""
    from typer.testing import CliRunner

    import det.pipeline.config as pipe_cfg
    from det.cli import app

    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr(pipe_cfg, "CONFIG_FILE", cfg_file)
    monkeypatch.setattr(pipe_cfg, "CONFIG_DIR", tmp_path)

    runner = CliRunner()
    file_a = tmp_path / "cli_a.yaml"
    file_b = tmp_path / "cli_b.yaml"

    # Create file via CLI
    res = runner.invoke(app, ["pipeline", "file", "create", str(file_a), "--default"])
    assert res.exit_code == 0
    assert "Created pipeline file" in res.stdout

    # Open file via CLI
    res = runner.invoke(app, ["pipeline", "file", "open", str(file_b)])
    assert res.exit_code == 0
    assert "Opened pipeline file" in res.stdout

    # List files via pipeline command
    res = runner.invoke(app, ["pipeline", "file", "list"])
    assert res.exit_code == 0
    assert "cli_a.yaml" in res.stdout
    assert "cli_b.yaml" in res.stdout

    # List files via etl alias
    res = runner.invoke(app, ["etl", "file", "list"])
    assert res.exit_code == 0
    assert "cli_a.yaml" in res.stdout

    # Set default via pipeline command
    res = runner.invoke(app, ["pipeline", "set-default", str(file_b)])
    assert res.exit_code == 0
    assert "Default pipeline path updated" in res.stdout
