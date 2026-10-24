"""Tests for EngineFacade unifying session, mounter, dispatcher, and secrets."""

import pytest
from det.engine.base import EngineConfig
from det.engine.facade import EngineFacade
from tests.test_engine_mounter import MockMountItem


def test_facade_end_to_end_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify complete lifecycle: secrets, mount view, execute query, and close."""
    monkeypatch.setenv("APP_ENV", "testing")
    engine = EngineFacade(EngineConfig())

    # Secret resolution
    assert engine.resolve_secret("Env: ${APP_ENV}") == "Env: testing"
    assert engine.mask_secret("password123") == "******"

    # Mount entity view
    engine.mount_entity("my_source", "SELECT 99 AS code, 'OK' AS status")

    # Direct query by connection name
    result = engine.execute("SELECT * FROM my_source")
    assert result.columns == ["code", "status"]
    assert result.rows == [(99, "OK")]

    # Mount batch
    report = engine.mount_all([
        MockMountItem("batch_view", "entity", "CREATE OR REPLACE VIEW batch_view AS SELECT 1 AS id")
    ])
    assert report.is_successful
    assert "batch_view" in report.mounted

    # Verify batch view queryable
    batch_res = engine.execute("SELECT id FROM batch_view")
    assert batch_res.rows == [(1,)]

    # Clean termination
    engine.close()

