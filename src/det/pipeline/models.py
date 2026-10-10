"""det.pipeline.models - Pydantic data models for data engineering projects, categories, and pipelines."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).isoformat()


class BaseNode(BaseModel):
    """Base model for pipeline DAG nodes."""
    id: str = Field(..., description="Unique node identifier within the pipeline")
    name: str = Field(..., description="Display name for the node")
    type: str = Field(..., description="Type of the node (source, model, sink)")


class SourceNode(BaseNode):
    """Model for a source node."""
    type: Literal["source"] = "source"
    adapter: str = Field(..., description="Adapter type (postgres, file, etc.)")
    connection: str | None = Field(None, description="Connection URI or env var")
    query: str | None = Field(None, description="SQL query for extraction")
    path: str | None = Field(None, description="Path for file-based sources")
    format: str | None = Field(None, description="Format for file-based sources")
    partition_column: str | None = Field(None, description="Column to partition on")
    partitions: int | None = Field(None, description="Number of partitions")
    storage_options: dict[str, Any] | None = Field(None, description="Additional storage options")
    scan_strategy: str | None = Field(None, description="Scan strategy (e.g. lazy)")


class ModelNode(BaseNode):
    """Model for a transformation model node."""
    type: Literal["model"] = "model"
    language: Literal["sql", "python", "rust"] = Field(..., description="Language used for the model")
    path: str | None = Field(None, description="Path to the model definition file")
    materialized: str | None = Field("table", description="Materialization strategy (e.g., table, view)")


class SinkNode(BaseNode):
    """Model for a sink node."""
    type: Literal["sink"] = "sink"
    adapter: str = Field(..., description="Adapter type (lakehouse, postgres, etc.)")
    source_model: str = Field(..., description="The ID of the upstream node generating data for this sink")
    format: str | None = Field(None, description="Output format (iceberg, etc.)")
    catalog: str | None = Field(None, description="Catalog URI")
    table: str = Field(..., description="Target table name")
    connection: str | None = Field(None, description="Connection URI or env var")
    mode: str = Field("merge", description="Write mode (merge, append, overwrite, bulk_copy)")
    merge_keys: list[str] | None = Field(None, description="Keys to merge on")


PipelineNode = SourceNode | ModelNode | SinkNode


class PipelineEdge(BaseModel):
    """An edge representing data flow or dependency between two nodes."""
    from_node: str = Field(..., alias="from", description="Source node ID")
    to_node: str = Field(..., alias="to", description="Target node ID")

    model_config = {
        "populate_by_name": True
    }


class DataPipeline(BaseModel):
    """Metadata representing an ETL/data pipeline workflow (placeholder for pipeline builder)."""

    id: str = Field(..., description="Unique pipeline identifier")
    name: str = Field(..., description="Display name for the data pipeline")
    description: str | None = Field(None, description="Optional pipeline purpose description")
    tags: list[str] = Field(default_factory=list, description="Categorical tags for filtering")
    created_at: str = Field(default_factory=_utcnow_iso, description="Creation timestamp")
    updated_at: str = Field(default_factory=_utcnow_iso, description="Last update timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom pipeline metadata")

    # DAG components
    nodes: list[PipelineNode] = Field(default_factory=list, description="Nodes in the pipeline DAG")
    edges: list[PipelineEdge] = Field(default_factory=list, description="Edges in the pipeline DAG")


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
