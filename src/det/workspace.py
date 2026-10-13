"""Workspace initialization and validation."""

from pathlib import Path
from uuid import uuid4


WORKSPACE_DIRECTORIES = (
    "extensions",
    "extensions/connectors",
    "extensions/ui",
    "catalog",
    "pipelines",
    "documentation",
    "logs",
)

DEFAULT_CATALOG = """\
version: 1
id: {catalog_id}
name: Default catalog
folders:
  - id: {folder_id}
    name: Default
    connections: []
"""


def initialize_workspace(location: str | Path) -> Path:
    """Create the standard workspace layout and starter catalog."""
    workspace = Path(location).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    for relative_path in WORKSPACE_DIRECTORIES:
        (workspace / relative_path).mkdir(parents=True, exist_ok=True)

    catalog_path = workspace / "catalog" / "default.yaml"
    if not catalog_path.exists():
        catalog_path.write_text(
            DEFAULT_CATALOG.format(catalog_id=uuid4(), folder_id=uuid4()),
            encoding="utf-8",
        )

    return workspace


def validate_workspace(location: str | Path) -> Path:
    """Return the resolved workspace path or explain how to initialize it."""
    workspace = Path(location).expanduser().resolve()
    missing = [
        relative_path
        for relative_path in WORKSPACE_DIRECTORIES
        if not (workspace / relative_path).is_dir()
    ]
    if not (workspace / "catalog" / "default.yaml").is_file():
        missing.append("catalog/default.yaml")
    if missing:
        missing_items = ", ".join(missing)
        raise ValueError(
            f"{workspace} is not an initialized det workspace "
            f"(missing: {missing_items}). Run 'det init {workspace}'."
        )
    return workspace


class Workspace:
    """High-level Python SDK interface for interacting with a det workspace."""

    def __init__(self, location: str | Path = ".") -> None:
        self.root = initialize_workspace(location)

    def run_pipeline(self, pipeline_name: str) -> dict:
        from det.api import configure_api, run_pipeline
        configure_api(self.root)
        return run_pipeline(pipeline_name)

    def validate_pipeline(self, pipeline_name: str) -> dict:
        from det.api import configure_api, validate_pipeline
        configure_api(self.root)
        return validate_pipeline(pipeline_name)
