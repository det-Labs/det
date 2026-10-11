"""Pydantic models for catalog YAML data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ColumnMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    type: str
    nullable: bool = True
    description: str = ""


class ConnectionMetadata(BaseModel):
    """Named reusable connection stored in connections.yaml (without credentials in catalog)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    connector: str
    config: dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class SourceMetadata(ConnectionMetadata):
    """Backwards compatibility alias for ConnectionMetadata."""


class DatasetMetadata(BaseModel):
    """Table metadata stored in a catalog, regardless of its connector."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    namespace: str = "default"
    format: str = "unknown"
    connector: str = ""
    location: str = ""
    connection_id: str | None = None
    source_id: str | None = None
    source_table: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    row_count: int | None = None
    columns: list[ColumnMetadata] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    last_scanned: str | None = None

    @model_validator(mode="after")
    def sync_format_and_connector(self) -> DatasetMetadata:
        if not self.connector and self.format and self.format != "unknown":
            self.connector = self.format
        elif (not self.format or self.format == "unknown") and self.connector:
            self.format = self.connector
        if not self.connection_id and self.source_id:
            self.connection_id = self.source_id
        elif not self.source_id and self.connection_id:
            self.source_id = self.connection_id
        return self


class CatalogFile(BaseModel):
    """Versioned on-disk representation of one catalog."""

    model_config = ConfigDict(extra="ignore")

    catalog_version: int = 1
    catalog_name: str = "Catalog"
    namespaces: list[str] = Field(default_factory=lambda: ["default"])
    connections: list[ConnectionMetadata] = Field(default_factory=list)
    sources: list[SourceMetadata] = Field(default_factory=list)
    datasets: list[DatasetMetadata] = Field(default_factory=list)

    @field_validator("catalog_name")
    @classmethod
    def validate_catalog_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Catalog name cannot be empty.")
        return value

    @model_validator(mode="after")
    def ensure_default_category(self) -> CatalogFile:
        self.namespaces = list(dict.fromkeys(["default", *self.namespaces]))
        for dataset in self.datasets:
            if dataset.namespace not in self.namespaces:
                self.namespaces.append(dataset.namespace)
        if not self.connections and self.sources:
            self.connections = [ConnectionMetadata(**s.model_dump()) for s in self.sources]
        elif not self.sources and self.connections:
            self.sources = [SourceMetadata(**c.model_dump()) for c in self.connections]
        return self

    def category_tree(self) -> list[dict[str, Any]]:
        """Return categories with their table metadata in catalog order."""
        tree: list[dict[str, Any]] = []
        for name in self.namespaces:
            tables = [
                {**dataset.model_dump(mode="json"), "columns_count": len(dataset.columns)}
                for dataset in self.datasets
                if dataset.namespace == name
            ]
            tree.append(
                {
                    "name": name,
                    "count": len(tables),
                    "tables": tables,
                }
            )
        return tree


class CatalogState(BaseModel):
    """Current open catalog, if any, and the single-catalog explorer tree."""

    active_path: str | None
    default_path: str | None
    is_default: bool
    catalog_name: str | None
    categories: list[dict[str, Any]]
    connections: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    dataset_count: int = 0




class ScanResult(BaseModel):
    """Result of auto-scanning a file or folder location."""

    location: str
    format: str
    columns: list[ColumnMetadata]
    row_count: int | None = None
    sample_preview: list[dict[str, Any]] | None = None
