"""Safe, locked, atomic YAML catalog persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from filelock import FileLock
from ruamel.yaml import YAML

from det.catalog.models import CatalogFile


def load_catalog(path: str | Path) -> CatalogFile:
    file_path = Path(path).expanduser().resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"Catalog file does not exist: {file_path}")
    try:
        with (
            FileLock(str(file_path) + ".lock", timeout=10),
            file_path.open("r", encoding="utf-8") as stream,
        ):
            data: Any = YAML(typ="safe").load(stream)
    except OSError as exc:
        raise OSError(f"Cannot read catalog file: {file_path}") from exc
    if data is None:
        raise ValueError(f"Catalog file is empty: {file_path}")
    if not isinstance(data, dict):
        raise TypeError(f"Catalog root must be a YAML mapping: {file_path}")
    return CatalogFile.model_validate(data)


def read_catalog_yaml(path: str | Path) -> str:
    file_path = Path(path).expanduser().resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"Catalog file does not exist: {file_path}")
    try:
        with (
            FileLock(str(file_path) + ".lock", timeout=10),
            file_path.open("r", encoding="utf-8") as stream,
        ):
            return stream.read()
    except OSError as exc:
        raise OSError(f"Cannot read catalog file: {file_path}") from exc


def create_catalog(path: str | Path, name: str, overwrite: bool = False) -> CatalogFile:
    file_path = Path(path).expanduser().resolve()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(str(file_path) + ".lock")
    with FileLock(str(lock_path), timeout=10):
        if not overwrite and file_path.exists():
            raise FileExistsError(f"Catalog file already exists: {file_path}")
        cat = CatalogFile(catalog_name=name)
        write_catalog_unlocked(file_path, cat)
    return cat


def save_catalog(path: str | Path, catalog: CatalogFile) -> None:
    file_path = Path(path).expanduser().resolve()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(file_path) + ".lock", timeout=10):
        if not file_path.is_file():
            raise FileNotFoundError(f"Catalog file does not exist: {file_path}")
        write_catalog_unlocked(file_path, catalog)


def write_catalog_unlocked(file_path: Path, catalog: CatalogFile) -> None:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    payload = catalog.model_dump(mode="json", exclude_none=True)
    with file_path.open("w", encoding="utf-8") as stream:
        yaml.dump(payload, stream)


get_catalog_yaml_str = read_catalog_yaml
