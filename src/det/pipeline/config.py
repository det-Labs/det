"""det.pipeline.config - Configuration and default path resolution for pipelines YAML store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(".det")
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_PIPELINES_FILENAME = "pipelines.yaml"


def get_default_pipeline_path() -> Path:
    """Retrieve the configured default pipelines path from local configuration.

    If no configuration exists, defaults to 'pipelines.yaml' in current directory.

    Returns:
        Path: Absolute resolved path to the default pipelines YAML file.
    """
    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("default_pipeline_path"):
                    return Path(data["default_pipeline_path"]).resolve()
        except (json.JSONDecodeError, OSError):
            return Path(DEFAULT_PIPELINES_FILENAME).resolve()

    return Path(DEFAULT_PIPELINES_FILENAME).resolve()


def set_default_pipeline_path(path: str | Path) -> Path:
    """Persist the default pipelines YAML path into the local configuration file.

    Args:
        path: Path string or Path object pointing to the pipelines YAML file.

    Returns:
        Path: Absolute resolved path that was persisted.
    """
    resolved_path = Path(path).resolve()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {}
    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except (json.JSONDecodeError, OSError):
            data = {}

    data["default_pipeline_path"] = str(resolved_path)

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return resolved_path

