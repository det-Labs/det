"""det.catalog.store - Safe, atomic, and concurrency-locked YAML catalog persistence."""

from __future__ import annotations

from pathlib import Path

from filelock import FileLock
from ruamel.yaml import YAML

from det.catalog.models import CatalogFile


def _get_yaml_handler() -> YAML:
    """Return a configured ruamel.yaml instance with clean indentation."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.default_flow_style = False
    return yaml


def load_catalog(path: str | Path) -> CatalogFile:
    """Load a CatalogFile from a YAML file, creating a default one if it does not exist."""
    file_path = Path(path).resolve()
    lock_path = file_path.with_name(f"{file_path.name}.lock")

    if not file_path.exists():
        # Initialize an empty catalog file
        catalog = CatalogFile(catalog_version=1, catalog_name="det_catalog", datasets=[])
        save_catalog(file_path, catalog)
        return catalog

    yaml = _get_yaml_handler()
    with FileLock(str(lock_path), timeout=10), open(file_path, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    if not data:
        return CatalogFile(catalog_version=1, catalog_name="det_catalog", datasets=[])

    return CatalogFile.model_validate(data)


def save_catalog(path: str | Path, catalog: CatalogFile) -> None:
    """Persist a CatalogFile atomically to a YAML file under a concurrency file lock."""
    file_path = Path(path).resolve()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = file_path.with_name(f"{file_path.name}.lock")
    temp_path = file_path.with_name(f"{file_path.name}.tmp")

    yaml = _get_yaml_handler()
    data = catalog.model_dump(exclude_none=True)

    with FileLock(str(lock_path), timeout=10):
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f)
            # Atomic replacement on Windows and POSIX
            temp_path.replace(file_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass


def get_catalog_yaml_str(path: str | Path) -> str:
    """Return the raw YAML content as a string."""
    file_path = Path(path).resolve()
    if not file_path.exists():
        return ""
    lock_path = file_path.with_name(f"{file_path.name}.lock")
    with FileLock(str(lock_path), timeout=10), open(file_path, "r", encoding="utf-8") as f:
        return f.read()
