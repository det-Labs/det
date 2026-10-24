"""Base protocols, enums, and data specifications for models and DAG orchestration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class MaterializationType(str, Enum):
    """Supported SQL materialization strategies in DuckDB."""

    VIEW = "view"
    TABLE = "table"
    INCREMENTAL = "incremental"
    EPHEMERAL = "ephemeral"


class WriteMode(str, Enum):
    """Write behavior when publishing to a destination."""

    REPLACE = "replace"
    APPEND = "append"
    MERGE = "merge"


@dataclass(frozen=True)
class DestinationSpec:
    """Specification of an egress destination target for model output."""

    target: str = "local"
    mode: WriteMode = WriteMode.REPLACE
    connection: str | None = None
    path: str | None = None
    format: str | None = None

    @classmethod
    def from_any(cls, value: Any) -> "DestinationSpec":
        """Instantiate DestinationSpec from string or dictionary representation."""
        if isinstance(value, str):
            return cls(target=value, mode=WriteMode.REPLACE)
        if isinstance(value, dict):
            raw_mode = value.get("mode", WriteMode.REPLACE.value)
            mode = WriteMode(raw_mode) if isinstance(raw_mode, str) else raw_mode
            return cls(
                target=str(value.get("target", "local")),
                mode=mode,
                connection=value.get("connection"),
                path=value.get("path"),
                format=value.get("format"),
            )
        raise TypeError(f"Cannot convert {type(value)} to DestinationSpec.")


@dataclass(frozen=True)
class DAGStage:
    """Represents a set of independent models that can execute concurrently."""

    stage_index: int
    models: list[str]


class BaseModelParser(ABC):
    """Interface for parsing model files and extracting dependencies."""

    @abstractmethod
    def parse_file(self, file_path: Path, project: str) -> Any:
        """Parse SQL file into a model definition."""
        pass


class BaseDirectResolver(ABC):
    """Interface for detecting direct catalog connections within SQL queries."""

    @abstractmethod
    def resolve_connections(
        self, sql: str, known_connections: set[str], known_models: set[str]
    ) -> set[str]:
        """Detect connection table identifiers in SQL."""
        pass


class BaseDAG(ABC):
    """Interface for dependency graph and topological stage resolution."""

    @abstractmethod
    def get_execution_order(self) -> list[str]:
        """Return flat topological execution order."""
        pass

    @abstractmethod
    def get_execution_stages(self) -> list[DAGStage]:
        """Return parallelizable execution tiers."""
        pass


class BaseProjectManager(ABC):
    """Interface for multi-project discovery and lifecycle management."""

    @abstractmethod
    def discover_projects(self) -> list[str]:
        """Return list of discovered project identifiers in workspace."""
        pass

