"""Base data contracts, document models, and interfaces for the documentation portal."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import duckdb

from det.models.dag import ModelDAG
from det.models.definition import ModelDefinition
from det.testing.definitions import TestDefinition


@dataclass(frozen=True)
class ColumnDoc:
    """Documentation and test metadata for an individual table column."""

    name: str
    data_type: str = "VARCHAR"
    description: str = ""
    test_badges: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SourceDoc:
    """Detailed catalog source metadata (connector type, tier, file path)."""

    name: str
    connector_type: str = "csv"
    tier: str = "entity"
    path: str = ""
    description: str = ""


@dataclass(frozen=True)
class DestinationDoc:
    """Detailed export destination metadata (format, path, options)."""

    target: str = "csv"
    path: str = ""
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TestDoc:
    """Detailed test assertion specification and failure policy."""

    name: str
    column: str = ""
    test_type: str = ""
    severity: str = "error"
    action_on_failure: str = "Halts pipeline execution"
    details: str = ""


@dataclass
class ModelDoc:
    """Rich documentation record for a single model in a pipeline."""

    name: str
    project: str
    description: str
    materialization: str
    destinations: list[str]
    tags: list[str]
    columns: list[ColumnDoc]
    compiled_sql: str
    raw_sql: str
    upstream_models: list[str] = field(default_factory=list)
    upstream_sources: list[str] = field(default_factory=list)
    sources_detail: list[SourceDoc] = field(default_factory=list)
    destinations_detail: list[DestinationDoc] = field(default_factory=list)
    tests_detail: list[TestDoc] = field(default_factory=list)


@dataclass
class ProjectDoc:
    """Project-level documentation package including statistics and lineage."""

    project_name: str
    version: str
    description: str
    total_models: int
    total_sources: int
    total_tests: int
    models: list[ModelDoc]
    lineage_mermaid: str


class BaseDocsExtractor(ABC):
    """Interface for extracting column data types, schemas, and test badges."""

    @abstractmethod
    def extract_model_doc(
        self,
        con: duckdb.DuckDBPyConnection,
        model: ModelDefinition,
        tests: list[TestDefinition] | None = None,
        catalog: Any = None,
    ) -> ModelDoc:
        """Extract documentation data model for a single pipeline model."""
        pass


class BaseLineageGenerator(ABC):
    """Interface for transforming a ModelDAG into Mermaid flowchart markup."""

    @abstractmethod
    def generate_mermaid(self, dag: ModelDAG) -> str:
        """Generate interactive Mermaid diagram string from dependency graph."""
        pass


class BaseDocsGenerator(ABC):
    """Interface for emitting static HTML documentation portals."""

    @abstractmethod
    def generate_html(self, project_doc: ProjectDoc) -> str:
        """Compile a standalone, zero-dependency HTML documentation string."""
        pass

    @abstractmethod
    def write_docs(self, output_dir: Path, project_doc: ProjectDoc) -> Path:
        """Persist generated documentation files to disk."""
        pass


class BaseDocsServer(ABC):
    """Interface for running local documentation preview servers."""

    @abstractmethod
    def start_server(self, docs_dir: Path, port: int = 8080) -> None:
        """Launch local HTTP server serving generated documentation."""
        pass
