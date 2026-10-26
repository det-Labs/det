"""Tests for single folder hierarchy, session activation, and scoped folder rules."""

import os
from pathlib import Path
import pytest
import yaml

from det.catalog.manager import CatalogManager
from det.cli import main
from det.session import (
    get_stored_environment,
    resolve_active_root,
    set_active_environment,
)
from det.workspace import Workspace


def test_init_only_creates_official_folders_no_projects(tmp_path: Path) -> None:
    """Verify init only scaffolds catalog, pipelines, data, extensions, .det (no projects)."""
    env_dir = tmp_path / "env_a"
    assert main(["init", str(env_dir)]) == 0

    assert (env_dir / "catalog" / "connections.yaml").exists()
    assert (env_dir / "pipelines" / "default" / "models" / "staging").exists()
    assert (env_dir / "pipelines" / "default" / "models" / "marts").exists()
    assert (env_dir / "data").exists()
    assert (env_dir / "extensions").exists()
    assert (env_dir / ".det" / "config.yaml").exists()
    assert (env_dir / ".det" / "bin" / "activate.ps1").exists()
    assert (env_dir / ".det" / "bin" / "activate.bat").exists()
    assert (env_dir / ".det" / "bin" / "activate").exists()

    # Must NOT create projects folder
    assert not (env_dir / "projects").exists()


def test_init_idempotency_does_not_recreate_existing(tmp_path: Path) -> None:
    """Verify running init on existing folders preserves user files and does not recreate."""
    env_dir = tmp_path / "env_idempotent"
    env_dir.mkdir(parents=True)
    (env_dir / "catalog").mkdir()
    (env_dir / "pipelines").mkdir()
    (env_dir / "data").mkdir()
    (env_dir / "extensions").mkdir()

    # Pre-populate custom file
    custom_cat = env_dir / "catalog" / "connections.yaml"
    custom_cat.write_text("connections:\n  my_feed:\n    type: duckdb\n", encoding="utf-8")

    custom_model = env_dir / "pipelines" / "my_custom.sql"
    custom_model.write_text("SELECT 42 AS num", encoding="utf-8")

    custom_data = env_dir / "data" / "input.csv"
    custom_data.write_text("a,b\n1,2\n", encoding="utf-8")

    # Re-run init
    assert main(["init", str(env_dir)]) == 0

    # Ensure files were preserved, not overwritten
    assert "my_feed" in custom_cat.read_text(encoding="utf-8")
    assert "SELECT 42" in custom_model.read_text(encoding="utf-8")
    assert "1,2" in custom_data.read_text(encoding="utf-8")


def test_session_remembers_active_environment_from_outside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify init stores location so commands from an outside directory target that environment."""
    outside_dir = tmp_path / "outside_work"
    outside_dir.mkdir()
    env_dir = tmp_path / "my_remote_env"

    monkeypatch.chdir(outside_dir)

    # Initialize remote location while standing in outside_dir
    assert main(["init", str(env_dir)]) == 0

    # Verify session recorded the active environment
    stored = get_stored_environment()
    assert stored is not None
    assert stored.resolve() == env_dir.resolve()

    # Verify resolve_active_root picks up env_dir even when cwd is outside_dir
    active_root = resolve_active_root()
    assert active_root.resolve() == env_dir.resolve()

    # Verify status command reflects this
    assert main(["status"]) == 0


def test_extra_folders_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify extra folders in the root are ignored and outside the scope of det."""
    env_dir = tmp_path / "scoped_env"
    assert main(["init", str(env_dir)]) == 0
    monkeypatch.chdir(env_dir)

    # Create extra folders
    (env_dir / "node_modules").mkdir()
    (env_dir / "node_modules" / "some_pkg").mkdir()
    (env_dir / "build").mkdir()
    (env_dir / "temp_cache").mkdir()

    # Create a pipeline model in pipelines/
    model_file = env_dir / "pipelines" / "default" / "models" / "staging" / "test_model.sql"
    model_file.write_text("{{ config(materialized='table') }}\nSELECT 100 AS result\n", encoding="utf-8")

    # Run pipeline
    assert main(["run"]) == 0

    # Workspace projects should only contain pipelines, ignoring node_modules, build, etc.
    ws = Workspace.open(env_dir)
    try:
        discovered = ws.projects.discover_projects()
        assert "default" in discovered
        assert "node_modules" not in discovered
        assert "build" not in discovered
        assert "temp_cache" not in discovered
    finally:
        ws.close()


def test_catalog_strictly_connections_yaml(tmp_path: Path) -> None:
    """Verify only connections.yaml in catalog/ is loaded, and all other yaml files are ignored."""
    cat_dir = tmp_path / "catalog"
    cat_dir.mkdir(parents=True)

    # Canonical file
    (cat_dir / "connections.yaml").write_text(
        yaml.dump({
            "connections": {
                "valid_feed": {
                    "type": "duckdb",
                    "tier": "entity",
                    "options": {"query": "SELECT 1"}
                }
            }
        }),
        encoding="utf-8"
    )

    # Other non-canonical yaml files that must be ignored
    (cat_dir / "other.yaml").write_text(
        yaml.dump({
            "connections": {
                "ignored_feed": {
                    "type": "duckdb",
                    "tier": "entity",
                    "options": {"query": "SELECT 2"}
                }
            }
        }),
        encoding="utf-8"
    )
    (cat_dir / "backup.yml").write_text(
        yaml.dump({
            "connections": {
                "backup_feed": {
                    "type": "duckdb",
                    "tier": "entity",
                    "options": {"query": "SELECT 3"}
                }
            }
        }),
        encoding="utf-8"
    )

    mgr = CatalogManager(cat_dir)
    conns = mgr.list_connections()
    names = [c.name for c in conns]

    assert "valid_feed" in names
    assert "ignored_feed" not in names
    assert "backup_feed" not in names


def test_catalog_five_core_functions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify all 5 catalog functions: list, test, display, details, delete."""
    env_dir = tmp_path / "catalog_env"
    assert main(["init", str(env_dir)]) == 0
    monkeypatch.chdir(env_dir)

    # 1. Setup sample connections with folders
    cat_file = env_dir / "catalog" / "connections.yaml"
    cat_file.write_text(
        yaml.dump({
            "connections": {
                "sales_data": {
                    "type": "duckdb",
                    "tier": "entity",
                    "folder": "Ecommerce",
                    "description": "Sales transactions",
                    "options": {"query": "SELECT i AS id, 'item_' || i AS item, (i * 10.5) AS amount FROM generate_series(1, 25) t(i)"},
                    "credentials": {"api_key": "secret_token_123"}
                },
                "users_data": {
                    "type": "duckdb",
                    "tier": "entity",
                    "folder": "Core",
                    "description": "User profiles",
                    "options": {"query": "SELECT 1 AS uid, 'Alice' AS uname"},
                }
            }
        }),
        encoding="utf-8"
    )

    # 1. list (all / under one folder)
    assert main(["catalog", "list"]) == 0
    assert main(["catalog", "list", "--folder", "Ecommerce"]) == 0
    assert main(["catalog", "list", "--folder", "NonExistent"]) == 0

    # 2. test (all / single / under one folder)
    assert main(["catalog", "test"]) == 0
    assert main(["catalog", "test", "sales_data"]) == 0
    assert main(["catalog", "test", "--folder", "Core"]) == 0
    assert main(["catalog", "test", "non_existent_feed"]) == 1

    # 3. display (top 10 rows)
    assert main(["catalog", "display", "sales_data"]) == 0
    assert main(["catalog", "display", "sales_data", "--limit", "5"]) == 0
    assert main(["catalog", "display", "non_existent_feed"]) == 1

    # 4. details (connection name, type, and all other properties)
    assert main(["catalog", "details", "sales_data"]) == 0
    assert main(["catalog", "details", "non_existent_feed"]) == 1

    # 5. delete (deletes individual connection)
    assert main(["catalog", "delete", "users_data", "--yes"]) == 0
    assert main(["catalog", "delete", "non_existent_feed", "--yes"]) == 1

    # Confirm users_data was removed from connections.yaml
    conns_after = yaml.safe_load(cat_file.read_text(encoding="utf-8"))["connections"]
    assert "users_data" not in conns_after
    assert "sales_data" in conns_after


def test_connections_yaml_strictly_enforces_absolute_paths(tmp_path: Path) -> None:
    """Verify relative local paths in connections.yaml are strictly rejected."""
    cat_dir = tmp_path / "catalog"
    cat_dir.mkdir(parents=True)
    cat_file = cat_dir / "connections.yaml"

    # Relative path should raise ValueError
    cat_file.write_text(
        yaml.dump({
            "connections": {
                "rel_feed": {
                    "type": "csv",
                    "tier": "entity",
                    "options": {"path": "data/relative_path.csv"}
                }
            }
        }),
        encoding="utf-8"
    )

    with pytest.raises(ValueError, match="must always be full absolute paths"):
        CatalogManager(cat_dir)

    # Absolute path should pass
    abs_path = (tmp_path / "data" / "absolute_path.csv").resolve().as_posix()
    cat_file.write_text(
        yaml.dump({
            "connections": {
                "abs_feed": {
                    "type": "csv",
                    "tier": "entity",
                    "options": {"path": abs_path}
                }
            }
        }),
        encoding="utf-8"
    )

    mgr = CatalogManager(cat_dir)
    assert mgr.get_connection("abs_feed") is not None


def test_demo_connections_all_have_absolute_paths(tmp_path: Path) -> None:
    """Verify det demo generates only full absolute paths in catalog/connections.yaml."""
    from det.demo import setup_demo_workspace
    setup_demo_workspace(tmp_path)

    cat_file = tmp_path / "catalog" / "connections.yaml"
    assert cat_file.exists()
    data = yaml.safe_load(cat_file.read_text(encoding="utf-8"))

    from det.catalog.reader import is_absolute_path
    for name, conn in data["connections"].items():
        path = conn["options"].get("path")
        assert path is not None, f"Connection {name} missing path"
        assert is_absolute_path(path), f"Connection {name} path '{path}' is not absolute!"


def test_pipeline_module_six_core_functions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify all 6 pipeline module commands and filtering."""
    env_dir = tmp_path / "pipe_test_env"
    assert main(["init", str(env_dir)]) == 0
    monkeypatch.chdir(env_dir)

    # Setup pipeline A
    p_a_models = env_dir / "pipelines" / "pipeline_alpha" / "models"
    (p_a_models / "staging").mkdir(parents=True, exist_ok=True)
    (p_a_models / "staging" / "stg_orders.sql").write_text(
        "{{ config(materialized='table') }}\nSELECT 1 AS id, 'PENDING' AS status\n",
        encoding="utf-8"
    )

    # Setup pipeline B in group folder
    p_b_models = env_dir / "pipelines" / "analytics" / "pipeline_beta" / "models"
    (p_b_models / "marts").mkdir(parents=True, exist_ok=True)
    (p_b_models / "marts" / "fct_metrics.sql").write_text(
        "{{ config(materialized='table') }}\nSELECT 100 AS metric_val\n",
        encoding="utf-8"
    )

    # 1. Listing pipelines (all / folder / filter by name: contains)
    assert main(["pipeline", "list"]) == 0
    assert main(["pipeline", "list", "--folder", "analytics"]) == 0
    assert main(["pipeline", "list", "--filter", "alpha"]) == 0
    assert main(["pipeline", "list", "--filter", "non_existent"]) == 0

    # 2. Compile: single pipeline so name is required
    assert main(["pipeline", "compile", "pipeline_alpha"]) == 0
    assert main(["compile", "pipeline_beta"]) == 0
    assert main(["pipeline", "compile", "missing_pipeline"]) == 1

    # 3. Test: Single pipeline
    assert main(["pipeline", "test", "pipeline_alpha"]) == 0
    assert main(["test", "pipeline_beta"]) == 0

    # 4. Run: Single pipeline
    assert main(["pipeline", "run", "pipeline_alpha"]) == 0
    assert main(["run", "pipeline_beta"]) == 0

    # 6. Listing of models in a given pipeline
    assert main(["pipeline", "models", "pipeline_alpha"]) == 0
    assert main(["pipeline", "models", "missing_pipeline"]) == 1

    # 5. Delete: single pipeline
    assert main(["pipeline", "delete", "pipeline_alpha", "--yes"]) == 0
    assert main(["pipeline", "delete", "missing_pipeline", "--yes"]) == 1

    # Confirm pipeline_alpha is gone
    assert not (env_dir / "pipelines" / "pipeline_alpha").exists()
    assert (env_dir / "pipelines" / "analytics" / "pipeline_beta").exists()




