"""Tests for catalog mounter and virtual view binder."""

import duckdb
import pytest
from det.engine.base import Mountable
from det.engine.mounter import CatalogMounter


class MockMountItem:
    """Mock implementation of Mountable protocol for testing."""

    def __init__(self, name: str, tier: str, mount_sql: str) -> None:
        self._name = name
        self._tier = tier
        self._mount_sql = mount_sql

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> str:
        return self._tier

    def get_mount_sql(self) -> str:
        return self._mount_sql


def test_bind_entity_view_and_query_by_name() -> None:
    """Verify that an entity bound as a view can be queried directly by connection name."""
    con = duckdb.connect()
    mounter = CatalogMounter()

    mounter.bind_entity_view(con, "customers_csv", "SELECT 101 AS id, 'Alice' AS name")
    res = con.execute("SELECT * FROM customers_csv").fetchall()
    assert res == [(101, "Alice")]
    con.close()


def test_mount_database_attach() -> None:
    """Verify attaching an in-memory database catalog."""
    con = duckdb.connect()
    mounter = CatalogMounter()

    mounter.mount_database(con, "aux_db", ":memory:")
    databases = [row[0] for row in con.execute("SHOW DATABASES").fetchall()]
    assert "aux_db" in databases
    con.close()


def test_mount_all_isolates_failures() -> None:
    """Verify that failures on one connection do not prevent mounting valid ones."""
    con = duckdb.connect()
    mounter = CatalogMounter()

    items: list[Mountable] = [
        MockMountItem("valid_view", "entity", "CREATE OR REPLACE VIEW valid_view AS SELECT 1 AS num"),
        MockMountItem("invalid_view", "entity", "CREATE OR REPLACE VIEW invalid_view AS SELECT * FROM does_not_exist_xyz"),
        MockMountItem("another_valid", "entity", "CREATE OR REPLACE VIEW another_valid AS SELECT 2 AS num"),
    ]

    report = mounter.mount_all(con, items)
    assert not report.is_successful
    assert "valid_view" in report.mounted
    assert "another_valid" in report.mounted
    assert "invalid_view" in report.failed

    # Check query on valid ones works
    res = con.execute("SELECT num FROM valid_view").fetchall()
    assert res == [(1,)]
    con.close()


def test_validate_identifier_rejects_sql_injection() -> None:
    """Verify that invalid SQL identifiers are rejected."""
    mounter = CatalogMounter()
    con = duckdb.connect()
    with pytest.raises(ValueError, match="Invalid SQL identifier"):
        mounter.bind_entity_view(con, "bad-name; DROP TABLE foo;", "SELECT 1")
    con.close()

