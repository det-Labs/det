"""Base classes, field schemas, and connector contracts for extensibility."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import duckdb

from det.catalog.base import ConnectionTier


class FieldType(str, Enum):
    """Input types supported by the dynamic form generator in CLI and Web IDE."""

    TEXT = "text"
    PASSWORD = "password"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"


@dataclass(frozen=True)
class ConnectorField:
    """Declarative specification for a single connector configuration parameter."""

    name: str
    label: str
    field_type: FieldType
    required: bool = True
    default: Any = None
    placeholder: str = ""
    description: str = ""
    choices: list[str] = field(default_factory=list)
    is_secret: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert field schema to dictionary for dynamic UI rendering."""
        return {
            "name": self.name,
            "label": self.label,
            "type": self.field_type.value,
            "required": self.required,
            "default": self.default,
            "placeholder": self.placeholder,
            "description": self.description,
            "choices": list(self.choices),
            "is_secret": self.is_secret,
        }


class BaseConnector(ABC):
    """Abstract base class for all pluggable data source connectors."""

    key: str
    label: str
    description: str
    tier: ConnectionTier

    @classmethod
    @abstractmethod
    def get_fields(cls) -> list[ConnectorField]:
        """Return the declarative field schema used to build dynamic UI forms."""
        pass

    @abstractmethod
    def get_read_sql(self, options: dict[str, Any]) -> str:
        """Return the DuckDB read expression (e.g. read_parquet(...))."""
        pass

    @abstractmethod
    def get_attach_sql(
        self, options: dict[str, Any], credentials: dict[str, Any]
    ) -> str | None:
        """Return the ATTACH command if tier == DATABASE, else None."""
        pass

    @abstractmethod
    def test_connection(
        self,
        con: duckdb.DuckDBPyConnection,
        options: dict[str, Any],
        credentials: dict[str, Any],
    ) -> bool:
        """Execute a diagnostic probe against the target data source."""
        pass

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        """Return full connector metadata and UI field definitions."""
        return {
            "key": cls.key,
            "label": cls.label,
            "description": cls.description,
            "tier": cls.tier.value,
            "fields": [f.to_dict() for f in cls.get_fields()],
        }

