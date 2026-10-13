"""det.pipeline - YAML data pipeline definitions, steps, and folder storage."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _canonical_guid(value: Any) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"det:pipeline:{value}"))


class PipelineStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=2000)
    sql: str = Field(min_length=1)
    destinations: list[str] = Field(default_factory=list)
    keep_temporary: bool = True

    @field_validator("id", mode="before")
    @classmethod
    def canonicalize_id(cls, value: Any) -> str:
        return _canonical_guid(value) if value is not None else str(uuid.uuid4())

    @field_validator("name")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        clean = value.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", clean):
            raise ValueError(
                f"Step name '{clean}' must start with a letter and contain only letters, numbers, and underscores."
            )
        return clean


class Pipeline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(min_length=1, max_length=64)
    folder: str = Field(default="default", min_length=1, max_length=64)
    catalog: str = Field(default="default.yaml")
    description: str = Field(default="", max_length=5000)
    steps: list[PipelineStep] = Field(default_factory=list)
    relative_path: str | None = None

    @field_validator("id", mode="before")
    @classmethod
    def canonicalize_id(cls, value: Any) -> str:
        return _canonical_guid(value) if value is not None else str(uuid.uuid4())

    @field_validator("name", "folder")
    @classmethod
    def validate_name(cls, value: str) -> str:
        clean = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", clean):
            raise ValueError(
                f"Name '{clean}' must contain only letters, numbers, hyphens, and underscores."
            )
        return clean

    @model_validator(mode="after")
    def validate_unique_step_names(self) -> Pipeline:
        names = [step.name.lower() for step in self.steps]
        if len(names) != len(set(names)):
            raise ValueError("Pipeline step names must be unique within the pipeline.")
        return self


class PipelineStore:
    """Manages pipeline YAML files organized in folders inside pipelines/."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.directory = self.workspace / "pipelines"
        self._lock = threading.RLock()
        self.directory.mkdir(parents=True, exist_ok=True)

    def list_folders(self) -> list[str]:
        """List distinct folder names under pipelines/."""
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            folders = set()
            for path in self.directory.iterdir():
                if path.is_dir() and not path.name.startswith((".", "_")):
                    folders.add(path.name)
            # Default folder always exists if empty
            if not folders:
                folders.add("default")
            return sorted(folders)

    def list_pipelines(self, folder: str | None = None) -> list[dict[str, Any]]:
        """List all pipeline metadata summaries, optionally filtered by folder."""
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            results: list[dict[str, Any]] = []

            # Scan nested subdirectories
            for folder_dir in self.directory.iterdir():
                if folder_dir.is_dir() and not folder_dir.name.startswith((".", "_")):
                    if folder and folder_dir.name != folder:
                        continue
                    for pipeline_file in folder_dir.glob("*.yaml"):
                        pipeline = self._safe_load_pipeline(pipeline_file)
                        if pipeline:
                            results.append(pipeline)

            # Scan top-level flat yaml files
            if folder is None or folder == "default":
                for pipeline_file in self.directory.glob("*.yaml"):
                    pipeline = self._safe_load_pipeline(pipeline_file)
                    if pipeline and (not folder or pipeline.get("folder") == folder):
                        results.append(pipeline)

            return sorted(results, key=lambda p: (p.get("folder", ""), p.get("name", "")))

    def _safe_load_pipeline(self, path: Path) -> dict[str, Any] | None:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            pipeline = Pipeline.model_validate(raw)
            data = pipeline.model_dump(mode="json")
            data["relative_path"] = str(path.relative_to(self.directory))
            return data
        except Exception:
            return None

    def get_pipeline(self, identifier: str) -> dict[str, Any]:
        """Get a pipeline by GUID, 'folder/name', or 'name'."""
        with self._lock:
            # 1. Check direct path: folder/name
            if "/" in identifier or "\\" in identifier:
                folder, name = re.split(r"[/\\]", identifier, maxsplit=1)
                clean_name = name[:-5] if name.endswith(".yaml") else name
                target_path = self.directory / folder / f"{clean_name}.yaml"
                if target_path.is_file():
                    loaded = self._safe_load_pipeline(target_path)
                    if loaded:
                        return loaded

            # 2. Search all pipelines for matching id or name
            all_pipelines = self.list_pipelines()
            for p in all_pipelines:
                if p["id"] == identifier or p["name"] == identifier:
                    return p
            raise FileNotFoundError(f"Pipeline not found: {identifier}")

    def save_pipeline(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate and atomically save a pipeline to its folder, moving files if folder or name changed."""
        with self._lock:
            pipeline = Pipeline.model_validate(data)
            folder_dir = self.directory / pipeline.folder
            folder_dir.mkdir(parents=True, exist_ok=True)

            target_path = folder_dir / f"{pipeline.name}.yaml"

            # Check if an existing pipeline is being moved or renamed
            old_path_to_clean: Path | None = None
            old_log_to_move: tuple[Path, Path] | None = None
            try:
                existing = self.get_pipeline(pipeline.id)
                old_rel = existing.get("relative_path")
                if old_rel:
                    old_file = self.directory / old_rel
                    if old_file.resolve() != target_path.resolve() and old_file.is_file():
                        old_path_to_clean = old_file

                old_folder = existing.get("folder")
                if old_folder and old_folder != pipeline.folder:
                    old_log_path = self.workspace / "logs" / "pipelines" / old_folder / f"{pipeline.id}.json"
                    new_log_dir = self.workspace / "logs" / "pipelines" / pipeline.folder
                    new_log_path = new_log_dir / f"{pipeline.id}.json"
                    if old_log_path.is_file():
                        old_log_to_move = (old_log_path, new_log_path)
            except FileNotFoundError:
                pass

            serialized = yaml.safe_dump(
                pipeline.model_dump(mode="json"),
                allow_unicode=True,
                sort_keys=False,
            )

            temporary_name: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    dir=folder_dir,
                    prefix=f".{target_path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as stream:
                    temporary_name = stream.name
                    stream.write(serialized)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_name, target_path)

                # Clean up old file if pipeline was moved or renamed
                if old_path_to_clean and old_path_to_clean.is_file():
                    old_path_to_clean.unlink()

                # Move mirrored logs to new folder if folder changed
                if old_log_to_move:
                    src_log, dst_log = old_log_to_move
                    dst_log.parent.mkdir(parents=True, exist_ok=True)
                    if src_log.is_file() and not dst_log.exists():
                        shutil.move(str(src_log), str(dst_log))

            finally:
                if temporary_name and os.path.exists(temporary_name):
                    os.unlink(temporary_name)

            return self.get_pipeline(pipeline.id)

    def delete_pipeline(self, identifier: str) -> bool:
        """Delete a pipeline file by id or folder/name."""
        with self._lock:
            pipeline = self.get_pipeline(identifier)
            rel_path = pipeline.get("relative_path")
            if rel_path:
                target_path = self.directory / rel_path
                if target_path.is_file():
                    target_path.unlink()
                    return True
            return False

    def create_folder(self, folder_name: str) -> str:
        """Create a new folder under pipelines/."""
        clean = folder_name.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", clean):
            raise ValueError(f"Invalid folder name: {clean}")
        with self._lock:
            path = self.directory / clean
            path.mkdir(parents=True, exist_ok=True)
            return clean

    def rename_folder(self, old_name: str, new_name: str) -> str:
        """Rename an existing pipeline folder."""
        clean_new = new_name.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", clean_new):
            raise ValueError(f"Invalid folder name: {clean_new}")
        with self._lock:
            old_dir = self.directory / old_name
            new_dir = self.directory / clean_new
            if not old_dir.is_dir():
                raise FileNotFoundError(f"Folder does not exist: {old_name}")
            if new_dir.exists() and new_dir != old_dir:
                raise FileExistsError(f"Target folder already exists: {clean_new}")
            old_dir.rename(new_dir)

            # Update the 'folder' field inside all child pipeline YAMLs
            for child in new_dir.glob("*.yaml"):
                p_data = self._safe_load_pipeline(child)
                if p_data:
                    p_data["folder"] = clean_new
                    self.save_pipeline(p_data)

            # Mirror folder rename in logs/pipelines if it exists
            old_log_dir = self.workspace / "logs" / "pipelines" / old_name
            new_log_dir = self.workspace / "logs" / "pipelines" / clean_new
            if old_log_dir.is_dir() and not new_log_dir.exists():
                old_log_dir.rename(new_log_dir)

            return clean_new

    def delete_folder(self, folder_name: str) -> bool:
        """Delete an empty pipeline folder."""
        with self._lock:
            folder_dir = self.directory / folder_name
            if not folder_dir.is_dir():
                raise FileNotFoundError(f"Folder does not exist: {folder_name}")
            if any(folder_dir.glob("*.yaml")):
                raise ValueError("Cannot delete folder containing pipelines. Move or delete them first.")
            folder_dir.rmdir()

            # Mirror folder cleanup in logs/pipelines if empty
            log_folder_dir = self.workspace / "logs" / "pipelines" / folder_name
            if log_folder_dir.is_dir() and not any(log_folder_dir.glob("*.json")):
                log_folder_dir.rmdir()

            return True
