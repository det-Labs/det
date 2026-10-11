"""Strict connector interface, declarative field contract, and capability models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from det.catalog.models import ColumnMetadata
from det.connectors.errors import (
    ConnectorValidationError,
)


class ConnectorGroup(str, Enum):
    FILES = "Files"
    DATABASES = "Databases"
    APIS = "APIs"
    OTHERS = "Others"


class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    SELECT = "select"
    PASSWORD = "password"
    TEXTAREA = "textarea"
    FILE = "file"
    FOLDER = "folder"


class ConfigField(BaseModel):
    """Declarative UI and configuration field definition."""

    model_config = ConfigDict(extra="ignore")

    name: str
    label: str
    type: str = "string"
    required: bool = False
    default: Any = None
    placeholder: str = ""
    description: str = ""
    secret: bool = False
    options: list[dict[str, Any]] = Field(default_factory=list)
    advanced: bool = False


class DiscoveredObject(BaseModel):
    """Discovered object such as a file, table, sheet, or endpoint."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    type: str = "table"
    path: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectionTestResult(BaseModel):
    """Result of connection test."""

    model_config = ConfigDict(extra="ignore")

    success: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class SchemaResult(BaseModel):
    """Inferred schema and row count statistics."""

    model_config = ConfigDict(extra="ignore")

    columns: list[ColumnMetadata]
    row_count_estimate: int | None = None
    sample_size: int = 0


class PreviewResult(BaseModel):
    """Sample data preview for UI data grid."""

    model_config = ConfigDict(extra="ignore")

    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int | None = None
    truncated: bool = False


def _normalize_call_options(options: dict[str, Any] | None = None, *args: Any, **kwargs: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if isinstance(options, dict):
        merged.update(options)
    for arg in args:
        if isinstance(arg, dict):
            merged.update(arg)
    for k, v in kwargs.items():
        if isinstance(v, dict):
            merged.update(v)
        elif k != "limit":
            merged[k] = v
    return merged


class BaseConnector(ABC):
    """Abstract base contract for all data connectors. Every table keeps its configuration in itself."""

    id: str
    name: str
    group: ConnectorGroup | str = ConnectorGroup.OTHERS
    description: str = ""
    fields: list[ConfigField] = []
    source_fields: list[ConfigField] = []
    table_fields: list[ConfigField] = []

    def get_fields(self) -> list[ConfigField]:
        if self.fields:
            return self.fields
        if self.table_fields:
            return self.table_fields
        return self.source_fields

    def get_secret_field_names(self, scope: str = "all") -> set[str]:
        return {f.name for f in self.get_fields() if f.secret or f.type == "password"}

    def validate_options(self, options: dict[str, Any]) -> None:
        for field in self.get_fields():
            if field.required:
                val = options.get(field.name)
                if val is None or (isinstance(val, str) and not val.strip()):
                    raise ConnectorValidationError(
                        f"Field '{field.label}' ({field.name}) is required for {self.name} table configuration.",
                        connector_id=self.id,
                    )

    def validate_source_config(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any] | None = None,
    ) -> None:
        self.validate_options({**source_config, **(credentials or {})})

    def validate_table_options(self, table_options: dict[str, Any]) -> None:
        self.validate_options(table_options)

    @abstractmethod
    def test_connection(
        self,
        options: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> ConnectionTestResult:
        """Test reachability and authentication for the connector options."""

    @abstractmethod
    def discover_objects(
        self,
        options: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> list[DiscoveredObject]:
        """Discover available files, sheets, or tables."""

    @abstractmethod
    def infer_schema(
        self,
        options: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> SchemaResult:
        """Inspect or infer schema column metadata."""

    @abstractmethod
    def preview(
        self,
        options: dict[str, Any],
        *args: Any,
        limit: int = 50,
        **kwargs: Any,
    ) -> PreviewResult:
        """Read sample data for display."""

    def spec(self) -> dict[str, Any]:
        """Serialize connector specification for generic UI form renderer."""
        group_val = self.group.value if isinstance(self.group, ConnectorGroup) else str(self.group)
        fields_json = [f.model_dump(mode="json") for f in self.get_fields()]
        return {
            "id": self.id,
            "name": self.name,
            "group": group_val,
            "description": self.description,
            "fields": fields_json,
            "table_fields": fields_json,
            "source_fields": [],
        }

