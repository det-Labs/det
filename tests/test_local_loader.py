"""Tests for dynamic loading of drop-in connector extensions."""

from pathlib import Path
from det.extensions.local_loader import LocalExtensionLoader
from det.extensions.registry import ExtensionRegistry


def test_load_drop_in_connector_from_directory(tmp_path: Path) -> None:
    """Verify scanning directory discovers and registers BaseConnector subclasses."""
    plugin_code = """
from det.catalog.base import ConnectionTier
from det.extensions.base import BaseConnector, ConnectorField, FieldType

class DropInConnector(BaseConnector):
    key = "drop_in"
    label = "Drop In Plugin"
    description = "Dynamically loaded"
    tier = ConnectionTier.ENTITY

    @classmethod
    def get_fields(cls):
        return [ConnectorField(name="target", label="Target", field_type=FieldType.TEXT)]

    def get_read_sql(self, options):
        return "SELECT 1"

    def get_attach_sql(self, options, credentials):
        return None

    def test_connection(self, con, options, credentials):
        return True
"""
    plugin_file = tmp_path / "custom_plugin.py"
    plugin_file.write_text(plugin_code, encoding="utf-8")

    registry = ExtensionRegistry()
    loader = LocalExtensionLoader()
    loaded_keys = loader.load_directory(tmp_path, registry)

    assert "drop_in" in loaded_keys
    connector = registry.get("drop_in")
    assert connector is not None
    assert connector.label == "Drop In Plugin"


def test_loader_ignores_corrupt_files_without_crashing(tmp_path: Path) -> None:
    """Verify loader skips invalid files gracefully and isolates failures."""
    corrupt_file = tmp_path / "broken.py"
    corrupt_file.write_text("def broken_syntax(;", encoding="utf-8")

    registry = ExtensionRegistry()
    loader = LocalExtensionLoader()
    loaded_keys = loader.load_directory(tmp_path, registry)

    assert loaded_keys == []
    assert len(registry.list_keys()) == 0

