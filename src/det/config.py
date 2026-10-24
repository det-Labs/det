"""Workspace configuration and engine settings loader for .det/config.yaml."""

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any
import yaml

from det.engine.base import EngineConfig

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceConfig:
    """Settings controlling workspace engine execution, memory, and extensions."""

    database: str = ".det/det.duckdb"
    threads: int | None = None
    memory_limit: str | None = None
    extensions: list[str] = field(default_factory=list)
    default_project: str = "default"

    def to_engine_config(self, workspace_root: Path | None = None) -> EngineConfig:
        """Convert workspace config into EngineConfig for DuckDBSessionManager."""
        db_path = self.database
        if workspace_root is not None and db_path != ":memory:":
            db_path = str((workspace_root / db_path).resolve())
        return EngineConfig(
            database=db_path,
            threads=self.threads,
            memory_limit=self.memory_limit,
            extensions=list(self.extensions),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation for YAML export."""
        return {
            "engine": {
                "database": self.database,
                "threads": self.threads,
                "memory_limit": self.memory_limit,
                "extensions": self.extensions,
            },
            "workspace": {
                "default_project": self.default_project,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkspaceConfig":
        """Instantiate WorkspaceConfig from parsed YAML dictionary."""
        engine_data = data.get("engine", {})
        ws_data = data.get("workspace", {})
        return cls(
            database=engine_data.get("database", ".det/det.duckdb"),
            threads=engine_data.get("threads"),
            memory_limit=engine_data.get("memory_limit"),
            extensions=list(engine_data.get("extensions", [])),
            default_project=ws_data.get("default_project", "default"),
        )

    @classmethod
    def load(cls, file_path: Path) -> "WorkspaceConfig":
        """Load configuration from .det/config.yaml, falling back to defaults if missing."""
        if not file_path.exists():
            return cls()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                return cls.from_dict(content if isinstance(content, dict) else {})
        except Exception as exc:
            logger.warning("Could not parse config from '%s': %s", file_path, exc)
            return cls()

    def save(self, file_path: Path) -> None:
        """Atomically persist configuration dictionary to target YAML file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, sort_keys=False)
