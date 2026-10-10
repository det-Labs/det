"""det.pipeline.store - Concurrency-safe, atomic YAML persistence for pipeline projects."""

from __future__ import annotations

from pathlib import Path

from filelock import FileLock
from ruamel.yaml import YAML

from det.pipeline.models import PipelineCategory, PipelineStoreFile, Project


def _get_yaml_handler() -> YAML:
    """Return a configured ruamel.yaml instance with clean indentation."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.default_flow_style = False
    return yaml


def load_pipeline_store(path: str | Path) -> PipelineStoreFile:
    """Load a PipelineStoreFile from YAML, creating a default starter project if not found."""
    file_path = Path(path).resolve()
    lock_path = file_path.with_name(f"{file_path.name}.lock")

    if not file_path.exists():
        # Initialize default store with a starter project & category
        default_project = Project(
            name="default_project",
            description="Default Data Engineering project",
            categories=[
                PipelineCategory(name="default", description="Default pipeline category", pipelines=[])
            ],
        )
        store = PipelineStoreFile(version=1, projects=[default_project])
        save_pipeline_store(file_path, store)
        return store

    yaml = _get_yaml_handler()
    with FileLock(str(lock_path), timeout=10), open(file_path, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    if not data:
        return PipelineStoreFile(version=1, projects=[])

    return PipelineStoreFile.model_validate(data)


def save_pipeline_store(path: str | Path, store: PipelineStoreFile) -> None:
    """Atomically save the PipelineStoreFile to disk under a file lock."""
    file_path = Path(path).resolve()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = file_path.with_name(f"{file_path.name}.lock")
    temp_path = file_path.with_name(f"{file_path.name}.tmp")

    yaml = _get_yaml_handler()
    data = store.model_dump(exclude_none=True)

    with FileLock(str(lock_path), timeout=10):
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f)
            temp_path.replace(file_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass


def get_pipeline_yaml_str(path: str | Path) -> str:
    """Return raw YAML content as string under file lock."""
    file_path = Path(path).resolve()
    if not file_path.exists():
        return ""
    lock_path = file_path.with_name(f"{file_path.name}.lock")
    with FileLock(str(lock_path), timeout=10), open(file_path, "r", encoding="utf-8") as f:
        return f.read()

