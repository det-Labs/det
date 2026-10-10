"""det.catalog.models - Pydantic data models for Catalog items, schemas, and files."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ColumnMetadata(BaseModel):
    """Metadata for a single dataset column."""

    name: str = Field(..., description="Column identifier / name")
    type: str = Field(..., description="Logical or native data type (e.g. string, int64, float64)")
    nullable: bool = Field(True, description="Whether the column accepts null values")
    description: str = Field("", description="Human-readable column description")


class DatasetMetadata(BaseModel):
    """Metadata describing a table or file registered in the catalog."""

    id: str = Field(..., description="Unique dataset identifier (e.g. namespace.table_name)")
    name: str = Field(..., description="Dataset or table name")
    namespace: str = Field("default", description="Namespace / schema grouping")
    format: str = Field("parquet", description="Data format (parquet, csv, json, excel, directory)")
    location: str = Field(..., description="Absolute or relative file / folder path")
    description: str = Field("", description="Detailed description of the dataset")
    row_count: int | None = Field(None, description="Exact or estimated total row count")
    columns: list[ColumnMetadata] = Field(default_factory=list, description="Dataset column definitions")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")
    last_scanned: str | None = Field(None, description="ISO timestamp of when schema was last scanned")


class CatalogFile(BaseModel):
    """The root representation serialized to catalog.yaml."""

    catalog_version: int = Field(1, description="Catalog specification version")
    catalog_name: str = Field("det_catalog", description="Logical name of this catalog")
    datasets: list[DatasetMetadata] = Field(default_factory=list, description="List of registered datasets")


class ScanResult(BaseModel):
    """Result of auto-scanning a file or folder location."""

    location: str
    format: str
    columns: list[ColumnMetadata]
    row_count: int | None = None
    sample_preview: list[dict[str, Any]] | None = None
