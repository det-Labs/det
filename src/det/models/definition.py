"""Data models for model configurations and declarative SQL definitions."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from det.models.base import DestinationSpec, MaterializationType


@dataclass
class ModelConfig:
    """Model execution and materialization settings."""

    materialized: MaterializationType = MaterializationType.VIEW
    destinations: list[DestinationSpec] = field(
        default_factory=lambda: [DestinationSpec(target="local")]
    )
    unique_key: str | None = None
    tags: list[str] = field(default_factory=list)
    schema: str | None = None
    enabled: bool = True
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelConfig":
        """Instantiate ModelConfig from parsed dictionary."""
        raw_mat = data.get("materialized", MaterializationType.VIEW.value)
        materialized = (
            MaterializationType(raw_mat)
            if isinstance(raw_mat, str)
            else raw_mat
        )

        raw_destinations = data.get("destinations", ["local"])
        destinations = [DestinationSpec.from_any(d) for d in raw_destinations]
        if not destinations:
            destinations = [DestinationSpec(target="local")]

        return cls(
            materialized=materialized,
            destinations=destinations,
            unique_key=data.get("unique_key"),
            tags=list(data.get("tags", [])),
            schema=data.get("schema"),
            enabled=bool(data.get("enabled", True)),
            description=str(data.get("description", "")).strip(),
        )


@dataclass
class ModelDefinition:
    """Represents a parsed SQL model within a project."""

    name: str
    project: str = "default"
    raw_sql: str = ""
    compiled_sql: str = ""
    config: ModelConfig = field(default_factory=ModelConfig)
    description: str = ""
    refs: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    direct_connections: list[str] = field(default_factory=list)
    file_path: Path | None = None

    def __post_init__(self) -> None:
        """Validate model identifier safety."""
        from det.validation import validate_identifier
        validate_identifier(self.name, "Model name")

    @property
    def all_dependencies(self) -> set[str]:
        """Union of all explicit and auto-detected upstream dependencies."""
        return set(self.refs).union(self.sources).union(self.direct_connections)

    def get_materialize_sql(self, override_name: str | None = None) -> str:
        """Construct DDL statement (CREATE VIEW/TABLE) for local DuckDB execution."""
        target_name = override_name or self.name
        strategy = self.config.materialized

        if strategy in (MaterializationType.TABLE, MaterializationType.INCREMENTAL):
            return f"CREATE OR REPLACE TABLE {target_name} AS {self.compiled_sql}"
        return f"CREATE OR REPLACE VIEW {target_name} AS {self.compiled_sql}"

