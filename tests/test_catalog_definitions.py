"""Tests for connection definitions and SQL generation."""

from det.catalog.base import ConnectionTier
from det.catalog.definitions import ConnectionDefinition
from det.engine.base import Mountable


def test_entity_csv_mount_sql() -> None:
    """Verify entity connection generates correct read_csv_auto SQL."""
    conn = ConnectionDefinition(
        name="sales_raw",
        type="csv",
        tier=ConnectionTier.ENTITY,
        options={"path": "data/sales.csv"},
    )
    expected = "CREATE OR REPLACE VIEW sales_raw AS SELECT * FROM read_csv_auto('data/sales.csv')"
    assert conn.get_mount_sql() == expected


def test_entity_custom_query_mount_sql() -> None:
    """Verify custom query takes precedence over path in entity connections."""
    conn = ConnectionDefinition(
        name="active_users",
        type="parquet",
        tier=ConnectionTier.ENTITY,
        options={"query": "SELECT * FROM read_parquet('data/*.parquet') WHERE active = true"},
    )
    expected = "CREATE OR REPLACE VIEW active_users AS SELECT * FROM read_parquet('data/*.parquet') WHERE active = true"
    assert conn.get_mount_sql() == expected


def test_database_sqlite_mount_sql() -> None:
    """Verify database connection generates correct ATTACH SQL with TYPE clause."""
    conn = ConnectionDefinition(
        name="legacy_db",
        type="sqlite",
        tier=ConnectionTier.DATABASE,
        options={"path": "legacy.db"},
    )
    expected = "ATTACH 'legacy.db' AS legacy_db (TYPE SQLITE)"
    assert conn.get_mount_sql() == expected


def test_database_postgres_mount_sql() -> None:
    """Verify database connection generates host/port/user connection string."""
    conn = ConnectionDefinition(
        name="prod_pg",
        type="postgres",
        tier=ConnectionTier.DATABASE,
        credentials={"host": "10.0.0.1", "port": 5432, "dbname": "app", "user": "det"},
    )
    assert conn.get_mount_sql() == "ATTACH 'host=10.0.0.1 port=5432 dbname=app user=det' AS prod_pg (TYPE POSTGRES)"


def test_connection_satisfies_engine_mountable_protocol() -> None:
    """Verify ConnectionDefinition implements the engine's Mountable protocol."""
    conn = ConnectionDefinition(
        name="test_item",
        type="csv",
        tier=ConnectionTier.ENTITY,
        options={"path": "test.csv"},
    )
    assert isinstance(conn, Mountable)


def test_dict_serialization_symmetry() -> None:
    """Verify to_dict and from_dict roundtrip preserve all fields."""
    orig = ConnectionDefinition(
        name="inventory",
        type="parquet",
        tier=ConnectionTier.ENTITY,
        options={"path": "s3://bucket/inv.parquet"},
        credentials={"key": "secret"},
        description="Daily inventory snapshot",
    )
    data = orig.to_dict()
    restored = ConnectionDefinition.from_dict("inventory", data)
    assert restored.name == orig.name
    assert restored.type == orig.type
    assert restored.tier == orig.tier
    assert restored.options == orig.options
    assert restored.credentials == orig.credentials
    assert restored.description == orig.description

