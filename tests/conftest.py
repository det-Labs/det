from pathlib import Path

import pytest

import det.catalog.config as config_mod


@pytest.fixture(autouse=True)
def isolate_test_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolate project configuration file to tmp_path during test runs."""
    test_dir = tmp_path / ".det"
    test_file = test_dir / "config.json"
    monkeypatch.setattr(config_mod, "CONFIG_DIR", test_dir)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", test_file)

