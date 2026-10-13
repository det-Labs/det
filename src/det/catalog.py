"""YAML catalog persistence and folder/connection operations."""

from __future__ import annotations

import os
import re
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


def _canonical_guid(value: Any) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"det:legacy-id:{value}"))


class CatalogConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(min_length=1, max_length=30)
    connector: str
    is_source: bool = True
    is_destination: bool = False
    description: str = Field(default="", max_length=2000)
    options: dict[str, Any] = Field(default_factory=dict)
    columns: list["CatalogColumn"] = Field(default_factory=list)

    @field_validator("id", mode="before")
    @classmethod
    def canonicalize_id(cls, value: Any) -> str:
        return _canonical_guid(value) if value is not None else str(uuid.uuid4())

    @field_validator("connector")
    @classmethod
    def validate_connector_guid(cls, value: str) -> str:
        try:
            return str(uuid.UUID(value))
        except ValueError as error:
            raise ValueError("Connector type must be identified by a GUID.") from error

    @field_validator("name")
    @classmethod
    def validate_sql_identifier(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,29}", value):
            raise ValueError(
                "Connection names must start with a letter, be at most 30 characters, "
                "and contain only letters, numbers, and underscores."
            )
        return value

    @model_validator(mode="after")
    def require_a_role(self) -> "CatalogConnection":
        if not self.is_source and not self.is_destination:
            raise ValueError("A connection must be marked as a source, a destination, or both.")
        return self


class CatalogColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(min_length=1, max_length=255)
    data_type: str
    nullable: bool = True
    description: str = Field(default="", max_length=2000)

    @field_validator("id", mode="before")
    @classmethod
    def canonicalize_id(cls, value: Any) -> str:
        return _canonical_guid(value) if value is not None else str(uuid.uuid4())


CatalogConnection.model_rebuild()


class CatalogFolder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str = Field(min_length=1, max_length=120)
    connections: list[CatalogConnection] = Field(default_factory=list)

    @field_validator("id", mode="before")
    @classmethod
    def canonicalize_id(cls, value: Any) -> str:
        return _canonical_guid(value) if value is not None else str(uuid.uuid4())


class CatalogDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    name: str = Field(min_length=1, max_length=120)
    folders: list[CatalogFolder] = Field(default_factory=list)

    @field_validator("id", mode="before")
    @classmethod
    def canonicalize_id(cls, value: Any) -> str:
        return _canonical_guid(value) if value is not None else str(uuid.uuid4())


class CatalogStore:
    """Manage YAML catalog files inside one initialized workspace."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.directory = self.workspace / "catalog"
        self._lock = threading.RLock()
        self._active_filename = self._initial_filename()

    def _initial_filename(self) -> str:
        files = self.list_filenames()
        if "default.yaml" in files:
            return "default.yaml"
        if files:
            return files[0]
        self._write_file("default.yaml", self._new_document("Default catalog"))
        return "default.yaml"

    @staticmethod
    def _validate_filename(filename: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.ya?ml", filename):
            raise ValueError("Catalog file must be a simple .yaml or .yml filename.")
        return filename

    @staticmethod
    def _new_document(name: str) -> CatalogDocument:
        return CatalogDocument(
            name=name,
            folders=[
                CatalogFolder(
                    name="Default",
                )
            ],
        )

    def list_filenames(self) -> list[str]:
        self.directory.mkdir(parents=True, exist_ok=True)
        return sorted(
            path.name
            for path in self.directory.iterdir()
            if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
        )

    def describe_catalogs(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active": self._active_filename,
                "items": self.list_filenames(),
            }

    def select(self, filename: str) -> dict[str, Any]:
        with self._lock:
            filename = self._validate_filename(filename)
            if filename not in self.list_filenames():
                raise FileNotFoundError(f"Catalog does not exist: {filename}")
            self._active_filename = filename
            return self.read()

    def create_catalog(self, name: str) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("Catalog name cannot be empty.")
        stem = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-_").lower() or "catalog"
        with self._lock:
            for existing_filename in self.list_filenames():
                self._active_filename = existing_filename
                existing = self.read()["catalog"]
                if existing["name"].casefold() == name.casefold():
                    return self.read()
            filename = f"{stem}.yaml"
            suffix = 2
            while filename in self.list_filenames():
                filename = f"{stem}-{suffix}.yaml"
                suffix += 1
            self._write_file(filename, self._new_document(name))
            self._active_filename = filename
            return self.read()

    def read(self) -> dict[str, Any]:
        with self._lock:
            filename = self._validate_filename(self._active_filename)
            path = self.directory / filename
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8"))
                if raw is None:
                    raw = {}
                if not isinstance(raw, dict):
                    raise ValueError(f"Catalog root must be a YAML mapping: {filename}")
                needs_migration = False
                if "folders" not in raw or not raw["folders"]:
                    raw["folders"] = [{
                        "id": str(uuid.uuid4()),
                        "name": "Default",
                        "connections": [],
                    }]
                    needs_migration = True
                if "connections" in raw:
                    raw["folders"][0].setdefault("connections", []).extend(raw.pop("connections"))
                    needs_migration = True
                if "id" not in raw:
                    raw["id"] = str(uuid.uuid4())
                    needs_migration = True
                for folder in raw["folders"]:
                    for connection in folder.get("connections", []):
                        if "direction" in connection:
                            direction = connection.pop("direction")
                            connection.setdefault("is_source", direction in {"source", "both"})
                            connection.setdefault("is_destination", direction in {"destination", "both"})
                            needs_migration = True
                catalog = CatalogDocument.model_validate(raw)
            except (OSError, ValueError, yaml.YAMLError, ValidationError) as error:
                raise ValueError(f"Could not load catalog {filename}: {error}") from error
            self._validate_ids(catalog)
            if needs_migration:
                self._write_file(filename, catalog)
                path = self.directory / filename
            return {
                "filename": filename,
                "catalog": catalog.model_dump(mode="json"),
                "yaml": path.read_text(encoding="utf-8"),
            }

    def save_yaml(self, content: str) -> dict[str, Any]:
        try:
            raw = yaml.safe_load(content)
            if not isinstance(raw, dict):
                raise ValueError("Catalog YAML must contain a mapping.")
            if not raw.get("folders"):
                raise ValueError("A catalog must contain at least one folder.")
            catalog = CatalogDocument.model_validate(raw)
        except (yaml.YAMLError, ValidationError) as error:
            raise ValueError(f"Invalid catalog YAML: {error}") from error
        self._validate_ids(catalog)
        with self._lock:
            self._write_file(self._active_filename, catalog)
            return self.read()

    def rename_catalog(self, name: str) -> dict[str, Any]:
        with self._lock:
            current = self.read()["catalog"]
            current["name"] = name.strip()
            catalog = CatalogDocument.model_validate(current)
            self._write_file(self._active_filename, catalog)
            return self.read()

    def add_folder(self, name: str) -> dict[str, Any]:
        with self._lock:
            catalog = self._read_document()
            catalog.folders.append(CatalogFolder(name=self._validate_name(name, "Folder")))
            return self._save_document(catalog)

    def update_folder(self, folder_id: str, name: str) -> dict[str, Any]:
        with self._lock:
            catalog = self._read_document()
            folder = self._folder(catalog, folder_id)
            folder.name = self._validate_name(name, "Folder")
            return self._save_document(catalog)

    def delete_folder(self, folder_id: str) -> dict[str, Any]:
        with self._lock:
            catalog = self._read_document()
            folder = self._folder(catalog, folder_id)
            if len(catalog.folders) == 1:
                raise ValueError("A catalog must contain at least one folder.")
            if folder.connections:
                raise ValueError("Move or delete this folder's connections before deleting it.")
            catalog.folders.remove(folder)
            return self._save_document(catalog)

    def add_connection(self, folder_id: str, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            catalog = self._read_document()
            folder = self._folder(catalog, folder_id)
            connection_values = dict(values)
            requested_folder_id = connection_values.pop("folder_id", folder_id)
            if requested_folder_id != folder_id:
                raise ValueError("Connection folder does not match the requested folder.")
            connection = CatalogConnection.model_validate(connection_values)
            folder.connections.append(connection)
            return self._save_document(catalog)

    def update_connection(
        self,
        connection_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            catalog = self._read_document()
            connection = self._connection(catalog, connection_id)
            update_values = dict(values)
            target_folder_id = update_values.pop("folder_id", None)
            updated = CatalogConnection.model_validate({
                **connection.model_dump(),
                **update_values,
                "id": connection_id,
            })
            for folder in catalog.folders:
                for index, current in enumerate(folder.connections):
                    if current.id == connection_id:
                        folder.connections[index] = updated
                        break
            if target_folder_id is not None:
                target = self._folder(catalog, target_folder_id)
                if target.id != self._connection_folder(catalog, connection_id):
                    for folder in catalog.folders:
                        folder.connections = [
                            item for item in folder.connections if item.id != connection_id
                        ]
                    target.connections.append(updated)
            return self._save_document(catalog)

    def save_connection_columns(
        self,
        connection_id: str,
        columns: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._lock:
            catalog = self._read_document()
            connection = self._connection(catalog, connection_id)
            existing_by_name = {column.name: column for column in connection.columns}
            saved_columns: list[CatalogColumn] = []
            for column_data in columns:
                column = CatalogColumn.model_validate(column_data)
                existing = existing_by_name.get(column.name)
                if existing is not None:
                    column.id = existing.id
                    column.description = existing.description
                saved_columns.append(column)
            connection.columns = saved_columns
            self._save_document(catalog)
            return self.get_connection(connection_id)

    def delete_connection(self, connection_id: str) -> dict[str, Any]:
        with self._lock:
            catalog = self._read_document()
            self._connection(catalog, connection_id)
            for folder in catalog.folders:
                folder.connections = [
                    connection for connection in folder.connections
                    if connection.id != connection_id
                ]
            return self._save_document(catalog)

    def get_connection(self, connection_id: str) -> dict[str, Any]:
        catalog = self._read_document()
        for folder in catalog.folders:
            for connection in folder.connections:
                if connection.id == connection_id:
                    return {
                        **connection.model_dump(mode="json"),
                        "folder_id": folder.id,
                        "folder_name": folder.name,
                    }
        raise FileNotFoundError(f"Connection does not exist: {connection_id}")

    def _read_document(self) -> CatalogDocument:
        return CatalogDocument.model_validate(self.read()["catalog"])

    def _save_document(self, catalog: CatalogDocument) -> dict[str, Any]:
        if not catalog.folders:
            raise ValueError("A catalog must contain at least one folder.")
        self._validate_ids(catalog)
        self._write_file(self._active_filename, catalog)
        return self.read()

    def _write_file(self, filename: str, catalog: CatalogDocument) -> None:
        path = self.directory / self._validate_filename(filename)
        self.directory.mkdir(parents=True, exist_ok=True)
        serialized = yaml.safe_dump(
            catalog.model_dump(mode="json"),
            allow_unicode=True,
            sort_keys=False,
        )
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.directory,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary_name = stream.name
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
        finally:
            if temporary_name and os.path.exists(temporary_name):
                os.unlink(temporary_name)

    @staticmethod
    def _folder(catalog: CatalogDocument, folder_id: str) -> CatalogFolder:
        for folder in catalog.folders:
            if folder.id == folder_id:
                return folder
        raise FileNotFoundError(f"Folder does not exist: {folder_id}")

    @staticmethod
    def _connection(catalog: CatalogDocument, connection_id: str) -> CatalogConnection:
        for folder in catalog.folders:
            for connection in folder.connections:
                if connection.id == connection_id:
                    return connection
        raise FileNotFoundError(f"Connection does not exist: {connection_id}")

    @staticmethod
    def _connection_folder(catalog: CatalogDocument, connection_id: str) -> str:
        for folder in catalog.folders:
            if any(connection.id == connection_id for connection in folder.connections):
                return folder.id
        raise FileNotFoundError(f"Connection does not exist: {connection_id}")

    @staticmethod
    def _validate_ids(catalog: CatalogDocument) -> None:
        item_ids = [catalog.id]
        item_ids.extend(folder.id for folder in catalog.folders)
        item_ids.extend(
            item_id
            for folder in catalog.folders
            for connection in folder.connections
            for item_id in (
                connection.id,
                *(column.id for column in connection.columns),
            )
        )
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("GUIDs must be unique across catalog items.")

    @staticmethod
    def _validate_name(name: str, item_type: str) -> str:
        normalized = name.strip()
        if not normalized:
            raise ValueError(f"{item_type} name cannot be empty.")
        return normalized
