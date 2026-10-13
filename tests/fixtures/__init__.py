"""Test workspace fixtures helper."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from det.api import configure_ui
from det.workspace import initialize_workspace

FIXTURES_DIR = Path(__file__).parent.resolve()


def setup_test_workspace() -> tuple[str, Path]:
    """Create a temporary initialized workspace populated with test catalog and pipelines."""
    temp_dir = tempfile.mkdtemp()
    workspace = Path(temp_dir)
    initialize_workspace(workspace)

    cat_src = FIXTURES_DIR / "catalog" / "default.yaml"
    if cat_src.is_file():
        shutil.copy2(cat_src, workspace / "catalog" / "default.yaml")

    pipe_src = FIXTURES_DIR / "pipelines"
    if pipe_src.is_dir():
        for subfolder in pipe_src.iterdir():
            if subfolder.is_dir():
                dst = workspace / "pipelines" / subfolder.name
                dst.mkdir(parents=True, exist_ok=True)
                for f in subfolder.glob("*.yaml"):
                    shutil.copy2(f, dst / f.name)

    configure_ui(workspace)
    return temp_dir, workspace
