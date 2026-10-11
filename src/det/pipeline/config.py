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
        except json.JSONDecodeError, OSError:
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
        except json.JSONDecodeError, OSError:
            data = {}

    data["default_pipeline_path"] = str(resolved_path)

    # Ensure default is also in known pipelines
    known = data.get("known_pipelines", [])
    if not isinstance(known, list):
        known = []
    path_str = str(resolved_path)
    if path_str not in known:
        known.append(path_str)
    data["known_pipelines"] = known

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return resolved_path


def get_known_pipeline_files() -> list[Path]:
    """Retrieve all known pipeline YAML paths.

    Includes the default pipeline file, any registered pipelines from local config,
    and any existing 'pipelines.yaml' in the project root.

    Returns:
        list[Path]: List of resolved Path objects for all known pipeline files.
    """
    pipelines: list[Path] = []
    default_pipe = get_default_pipeline_path()
    if default_pipe.is_file():
        pipelines.append(default_pipe)

    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    raw_list = data.get("known_pipelines", [])
                    if isinstance(raw_list, list):
                        for p in raw_list:
                            resolved = Path(p).resolve()
                            if resolved.is_file() and resolved not in pipelines:
                                pipelines.append(resolved)
        except json.JSONDecodeError, OSError:
            pass

    # If no existing file found yet, ensure default_pipe is listed
    if not pipelines:
        pipelines.append(default_pipe)

    # Deduplicate while preserving order
    result: list[Path] = []
    for p in pipelines:
        if p not in result:
            result.append(p)
    return result


def add_known_pipeline_file(path: str | Path) -> Path:
    """Register a pipeline YAML path in the known pipelines configuration list."""
    resolved_path = Path(path).resolve()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {}
    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except json.JSONDecodeError, OSError:
            data = {}

    known = data.get("known_pipelines", [])
    if not isinstance(known, list):
        known = []

    path_str = str(resolved_path)
    if path_str not in known:
        known.append(path_str)

    data["known_pipelines"] = known
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return resolved_path


def remove_known_pipeline_file(path: str | Path) -> bool:
    """Remove a pipeline file from the known pipelines configuration list."""
    resolved_path = Path(path).resolve()
    if not CONFIG_FILE.is_file():
        return False

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False

        known = data.get("known_pipelines", [])
        if isinstance(known, list) and str(resolved_path) in known:
            known.remove(str(resolved_path))
            data["known_pipelines"] = known
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
    except json.JSONDecodeError, OSError:
        pass
    return False
