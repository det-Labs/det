"""det.catalog.config - Manages catalog preferences and default YAML paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Local configuration directory for project-level settings
CONFIG_DIR = Path(".det")
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_CATALOG_FILENAME = "catalog.yaml"


def get_default_catalog_path() -> Path:
    """Retrieve the configured default catalog path from local configuration.

    If no configuration file exists or reading fails, safely defaults to
    './catalog.yaml' in the current working directory.

    Returns:
        Path: Absolute resolved path to the default catalog YAML file.
    """
    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("default_catalog_path"):
                    return Path(data["default_catalog_path"]).resolve()
        except (json.JSONDecodeError, OSError):
            return Path(DEFAULT_CATALOG_FILENAME).resolve()

    return Path(DEFAULT_CATALOG_FILENAME).resolve()


def set_default_catalog_path(path: str | Path) -> Path:
    """Persist the default catalog path into the local configuration file.

    Args:
        path: Path string or Path object pointing to the catalog YAML file.

    Returns:
        Path: Absolute resolved path that was persisted.

    Raises:
        OSError: If creating directories or writing the configuration fails.
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

    data["default_catalog_path"] = str(resolved_path)

    # Ensure default is also in known catalogs
    known = data.get("known_catalogs", [])
    if not isinstance(known, list):
        known = []
    path_str = str(resolved_path)
    if path_str not in known:
        known.append(path_str)
    data["known_catalogs"] = known

    # Write configuration safely
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return resolved_path


def get_known_catalogs() -> list[Path]:
    """Retrieve all known catalog YAML paths.

    Includes the default catalog, any registered catalogs from local config,
    and any existing 'catalog.yaml' in the project root.

    Returns:
        list[Path]: List of resolved Path objects for all known catalogs.
    """
    catalogs: list[Path] = []
    default_cat = get_default_catalog_path()
    if default_cat.is_file():
        catalogs.append(default_cat)

    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    raw_list = data.get("known_catalogs", [])
                    if isinstance(raw_list, list):
                        for p in raw_list:
                            resolved = Path(p).resolve()
                            if resolved.is_file() and resolved not in catalogs:
                                catalogs.append(resolved)
        except (json.JSONDecodeError, OSError):
            pass

    # If no existing file found yet, ensure default_cat is listed
    if not catalogs:
        catalogs.append(default_cat)

    # Deduplicate while preserving order
    result: list[Path] = []
    for c in catalogs:
        if c not in result:
            result.append(c)
    return result


def add_known_catalog(path: str | Path) -> Path:
    """Register a catalog path in the known catalogs configuration list."""
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

    known = data.get("known_catalogs", [])
    if not isinstance(known, list):
        known = []

    path_str = str(resolved_path)
    if path_str not in known:
        known.append(path_str)

    data["known_catalogs"] = known
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return resolved_path


def remove_known_catalog(path: str | Path) -> bool:
    """Remove a catalog from the known catalogs configuration list."""
    resolved_path = Path(path).resolve()
    if not CONFIG_FILE.is_file():
        return False

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False

        known = data.get("known_catalogs", [])
        if isinstance(known, list) and str(resolved_path) in known:
            known.remove(str(resolved_path))
            data["known_catalogs"] = known
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
    except (json.JSONDecodeError, OSError):
        pass
    return False
