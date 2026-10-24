"""Tests for ExtensionRegistry and connector schema generation."""

from typing import Any
import duckdb
import pytest

from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType
from det.extensions.registry import ExtensionRegistry


class CustomMockConnector(BaseConnector):
    """Test connector for registry validation."""

    key = "custom_test"
    label = "Custom Test Source"
    description = "Test description"
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls) -> list[ConnectorField]:
        return [
            ConnectorField(
                name="api_token",
                label="API Token",
                field_type=FieldType.PASSWORD,
                is_secret=True,
            )
        ]

    def get_read_sql(self, options: dict[str, Any]) -> str:
        return "read_parquet('custom://data')"

    def get_attach_sql(
        self, options: dict[str, Any], credentials: dict[str, Any]
    ) -> str | None:
        return None

    def test_connection(
        self,
        con: duckdb.DuckDBPyConnection,
        options: dict[str, Any],
        credentials: dict[str, Any],
    ) -> bool:
        return True


def test_registry_registration_and_lookup() -> None:
    """Verify registering a connector and looking it up by key."""
    registry = ExtensionRegistry()
    registry.register(CustomMockConnector)

    retrieved = registry.get("custom_test")
    assert retrieved is CustomMockConnector
    # Case-insensitive lookup
    assert registry.get("CUSTOM_TEST") is CustomMockConnector
    assert "custom_test" in registry.list_keys()


def test_registry_rejects_invalid_subclass() -> None:
    """Verify registry raises TypeError if class does not inherit BaseConnector."""
    registry = ExtensionRegistry()

    class NotAConnector:
        key = "bad"

    with pytest.raises(TypeError, match="must inherit from BaseConnector"):
        registry.register(NotAConnector)  # type: ignore


def test_registry_emits_dynamic_schemas_for_ui() -> None:
    """Verify list_schemas generates complete declarative metadata for dynamic forms."""
    registry = ExtensionRegistry()
    registry.register(CustomMockConnector)

    schemas = registry.list_schemas()
    assert len(schemas) == 1
    schema = schemas[0]
    assert schema["key"] == "custom_test"
    assert schema["label"] == "Custom Test Source"
    assert schema["tier"] == "entity"
    assert len(schema["fields"]) == 1

    field_meta = schema["fields"][0]
    assert field_meta["name"] == "api_token"
    assert field_meta["type"] == "password"
    assert field_meta["is_secret"] is True

