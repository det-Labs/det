"""det.catalog.config - Manages catalog preferences and default YAML paths."""

from __future__ import annotations

import json
from pathlib import Path

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

    data: dict[str, str] = {}
    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
        except (json.JSONDecodeError, OSError):
            data = {}

    data["default_catalog_path"] = str(resolved_path)

    # Write configuration safely
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return resolved_path
