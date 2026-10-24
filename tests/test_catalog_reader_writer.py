"""Tests for catalog YAML reader and atomic writer."""

from pathlib import Path
import pytest
from det.catalog.base import ConnectionTier
from det.catalog.definitions import ConnectionDefinition
from det.catalog.reader import CatalogReader
from det.catalog.writer import CatalogWriter


def test_reader_handles_non_existent_file(tmp_path: Path) -> None:
    """Verify reader returns empty dictionary for non-existent file."""
    reader = CatalogReader()
    missing_file = tmp_path / "does_not_exist.yaml"
    result = reader.read_yaml(missing_file)
    assert result == {}


def test_writer_and_reader_roundtrip(tmp_path: Path) -> None:
    """Verify writing definitions atomically to YAML and reading them back."""
    yaml_file = tmp_path / "connections.yaml"
    writer = CatalogWriter()
    reader = CatalogReader()

    definitions = {
        "raw_events": ConnectionDefinition(
            name="raw_events",
            type="json",
            tier=ConnectionTier.ENTITY,
            options={"path": "events/*.json"},
            description="Raw event stream",
        ),
        "warehouse": ConnectionDefinition(
            name="warehouse",
            type="sqlite",
            tier=ConnectionTier.DATABASE,
            options={"path": "wh.db"},
        ),
    }

    writer.write_yaml(yaml_file, definitions)
    assert yaml_file.exists()

    loaded = reader.read_yaml(yaml_file)
    assert len(loaded) == 2
    assert "raw_events" in loaded
    assert "warehouse" in loaded
    assert loaded["raw_events"].tier == ConnectionTier.ENTITY
    assert loaded["warehouse"].tier == ConnectionTier.DATABASE


def test_reader_resolves_environment_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify secret resolution during catalog read."""
    monkeypatch.setenv("PG_HOST", "db.internal.corp")
    yaml_file = tmp_path / "connections.yaml"
    yaml_file.write_text(
        """
connections:
  pg_db:
    type: postgres
    tier: database
    credentials:
      host: "${PG_HOST}"
      port: 5432
""",
        encoding="utf-8",
    )

    reader = CatalogReader()
    loaded = reader.read_yaml(yaml_file, resolve_secrets=True)
    assert loaded["pg_db"].credentials["host"] == "db.internal.corp"

