"""Tests for det command-line interface automation."""

from pathlib import Path
import pytest
from det.cli import main


def test_cli_init_command(tmp_path: Path) -> None:
    """Verify 'det init <path>' scaffolds the workspace."""
    target_dir = tmp_path / "cli_ws"
    exit_code = main(["init", str(target_dir)])
    assert exit_code == 0
    assert (target_dir / ".det" / "config.yaml").exists()
    assert (target_dir / "catalog" / "connections.yaml").exists()


def test_cli_run_test_and_docs_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify running init, run, test, and docs commands via CLI."""
    target_dir = tmp_path / "active_ws"
    # 1. Init
    assert main(["init", str(target_dir)]) == 0

    # Change working directory to initialized workspace
    monkeypatch.chdir(target_dir)

    # Create simple model
    model_file = target_dir / "pipelines" / "default" / "models" / "staging" / "sample.sql"
    model_file.write_text("{{ config(materialized='table', unique_key='x') }}\nSELECT 1 AS x\n", encoding="utf-8")

    # 2. Run
    assert main(["run"]) == 0

    # 3. Test
    assert main(["test"]) == 0

    # 4. Docs generate
    assert main(["docs", "generate"]) == 0
    assert (target_dir / "pipelines" / "default" / "docs" / "index.html").exists()

    # 5. Catalog list and test
    assert main(["catalog"]) == 0
    assert main(["catalog", "list"]) == 0
    assert main(["catalog", "test"]) == 0

    # Add a mock catalog connection
    import yaml
    cat_file = target_dir / "catalog" / "connections.yaml"
    cat_file.write_text(yaml.dump({
        "connections": {
            "test_sample": {
                "type": "duckdb",
                "tier": "entity",
                "options": {"query": "SELECT 1 AS id"}
            }
        }
    }), encoding="utf-8")

    assert main(["catalog", "list"]) == 0
    assert main(["catalog", "test"]) == 0
    assert main(["catalog", "test", "test_sample"]) == 0
    assert main(["catalog", "test", "missing_conn"]) == 1

