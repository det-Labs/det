"""det.pipeline.models - Pydantic data models for data engineering projects, categories, and pipelines."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def _utcnow_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


class DataPipeline(BaseModel):
    """Metadata representing an ETL/data pipeline workflow (placeholder for pipeline builder)."""

    id: str = Field(..., description="Unique pipeline identifier")
    name: str = Field(..., description="Display name for the data pipeline")
    description: str | None = Field(None, description="Optional pipeline purpose description")
    tags: list[str] = Field(default_factory=list, description="Categorical tags for filtering")
    created_at: str = Field(default_factory=_utcnow_iso, description="Creation timestamp")
    updated_at: str = Field(default_factory=_utcnow_iso, description="Last update timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom pipeline metadata")


class PipelineCategory(BaseModel):
    """A logical category grouping multiple data pipelines within a project."""

    name: str = Field(..., description="Unique category name within the parent project")
    description: str | None = Field(None, description="Optional category description")
    pipelines: list[DataPipeline] = Field(default_factory=list, description="Data pipelines in category")


class Project(BaseModel):
    """A top-level data engineering project containing categories and pipelines."""

    name: str = Field(..., description="Unique project name")
    description: str | None = Field(None, description="Project description or business context")
    created_at: str = Field(default_factory=_utcnow_iso, description="Creation timestamp")
    updated_at: str = Field(default_factory=_utcnow_iso, description="Last update timestamp")
    categories: list[PipelineCategory] = Field(
        default_factory=list,
        description="Logical categories belonging to this project",
    )


class PipelineStoreFile(BaseModel):
    """Root YAML schema file containing data engineering projects and pipelines."""

    version: int = Field(1, description="Pipeline file format schema version")
    projects: list[Project] = Field(default_factory=list, description="List of configured projects")
