"""Connection definition model conforming to the engine Mountable protocol."""

from dataclasses import dataclass, field
from typing import Any

from det.catalog.base import ConnectionTier


@dataclass
class ConnectionDefinition:
    """Represents a declarative data source connection configuration."""

    name: str
    type: str
    tier: ConnectionTier
    options: dict[str, Any] = field(default_factory=dict)
    credentials: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    folder: str = ""

    def __post_init__(self) -> None:
        """Validate connection identifier safety."""
        from det.validation import validate_identifier
        validate_identifier(self.name, "Connection name")

    @property
    def tier_value(self) -> str:
        """String representation of the tier."""
        return self.tier.value

    def get_mount_sql(self) -> str:
        """Generate the DuckDB SQL statement to mount this connection."""
        if self.tier == ConnectionTier.ENTITY:
            return self._build_entity_sql()
        return self._build_database_sql()

    def _build_entity_sql(self) -> str:
        """Construct CREATE OR REPLACE VIEW statement for entity connections."""
        custom_query = self.options.get("query")
        if custom_query:
            return f"CREATE OR REPLACE VIEW {self.name} AS {custom_query}"

        source_path = self.options.get("path") or self.options.get("url", "")
        escaped_path = source_path.replace("'", "''")
        read_expr = self._determine_read_expression(escaped_path)
        return f"CREATE OR REPLACE VIEW {self.name} AS SELECT * FROM {read_expr}"

    def _determine_read_expression(self, path: str) -> str:
        """Determine appropriate DuckDB read function based on type and path."""
        conn_type = self.type.lower()
        if conn_type in ("csv",) or path.endswith((".csv", ".tsv")):
            return f"read_csv_auto('{path}')"
        if conn_type in ("json",) or path.endswith((".json", ".ndjson")):
            return f"read_json_auto('{path}')"
        return f"read_parquet('{path}')"

    def _build_database_sql(self) -> str:
        """Construct ATTACH statement for database connections."""
        conn_type = self.type.upper()
        conn_str = self._resolve_database_connection_string()
        escaped_str = conn_str.replace("'", "''")

        if self.type.lower() in ("duckdb", ""):
            return f"ATTACH '{escaped_str}' AS {self.name}"
        return f"ATTACH '{escaped_str}' AS {self.name} (TYPE {conn_type})"

    def _resolve_database_connection_string(self) -> str:
        """Extract or compose database connection string."""
        explicit_str = (
            self.credentials.get("connection_string")
            or self.options.get("connection_string")
            or self.options.get("path")
        )
        if explicit_str:
            return str(explicit_str)

        parts: list[str] = []
        for key in ("host", "port", "dbname", "database", "user", "password"):
            val = self.credentials.get(key)
            if val is not None:
                parts.append(f"{key}={val}")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert definition to dictionary representation for YAML export."""
        res = {
            "type": self.type,
            "tier": self.tier.value,
            "options": self.options,
            "credentials": self.credentials,
            "description": self.description,
        }
        if self.folder:
            res["folder"] = self.folder
        return res

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "ConnectionDefinition":
        """Instantiate connection definition from a parsed dictionary."""
        raw_tier = data.get("tier", ConnectionTier.ENTITY.value)
        tier = ConnectionTier(raw_tier)
        return cls(
            name=name,
            type=str(data.get("type", "csv")),
            tier=tier,
            options=dict(data.get("options", {})),
            credentials=dict(data.get("credentials", {})),
            description=str(data.get("description", "")),
            folder=str(data.get("folder", "")),
        )

