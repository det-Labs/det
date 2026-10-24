"""Tests for WorkspaceConfig loading, saving, and engine mapping."""

from pathlib import Path
from det.config import WorkspaceConfig


def test_workspace_config_defaults() -> None:
    """Verify default config parameters."""
    cfg = WorkspaceConfig()
    assert cfg.threads is None
    assert cfg.memory_limit is None
    assert cfg.default_project == "default"
    assert cfg.extensions == []

    engine_cfg = cfg.to_engine_config()
    assert engine_cfg.threads is None
    assert engine_cfg.memory_limit is None


def test_workspace_config_save_and_load(tmp_path: Path) -> None:
    """Verify saving to YAML and loading back cleanly."""
    cfg_file = tmp_path / ".det" / "config.yaml"
    orig = WorkspaceConfig(
        threads=4,
        memory_limit="2GB",
        extensions=["autocomplete", "fts"],
        default_project="ecommerce",
    )
    orig.save(cfg_file)
    assert cfg_file.exists()

    loaded = WorkspaceConfig.load(cfg_file)
    assert loaded.threads == 4
    assert loaded.memory_limit == "2GB"
    assert loaded.extensions == ["autocomplete", "fts"]
    assert loaded.default_project == "ecommerce"

