"""Tests for connection health check and latency probing."""

from pathlib import Path
import duckdb
from det.catalog.base import ConnectionTestStatus, ConnectionTier
from det.catalog.definitions import ConnectionDefinition
from det.catalog.tester import ConnectionTester


def test_probe_valid_entity_connection(tmp_path: Path) -> None:
    """Verify testing a valid entity file returns SUCCESS with latency."""
    csv_file = tmp_path / "sample.csv"
    csv_file.write_text("id,val\n1,alpha\n2,beta\n", encoding="utf-8")

    conn_def = ConnectionDefinition(
        name="test_csv",
        type="csv",
        tier=ConnectionTier.ENTITY,
        options={"path": str(csv_file).replace("\\", "/")},
    )

    con = duckdb.connect()
    tester = ConnectionTester()
    result = tester.test_connection(con, conn_def)

    assert result.is_healthy
    assert result.status == ConnectionTestStatus.SUCCESS
    assert result.latency_ms >= 0.0
    assert result.error_message is None
    con.close()


def test_probe_invalid_connection_returns_failure() -> None:
    """Verify testing an invalid/missing path returns FAILED with error message."""
    conn_def = ConnectionDefinition(
        name="broken_csv",
        type="csv",
        tier=ConnectionTier.ENTITY,
        options={"path": "non_existent_folder_xyz/file.csv"},
    )

    con = duckdb.connect()
    tester = ConnectionTester()
    result = tester.test_connection(con, conn_def)

    assert not result.is_healthy
    assert result.status == ConnectionTestStatus.FAILED
    assert result.error_message is not None
    assert "No files found" in result.error_message or "Cannot open" in result.error_message
    con.close()

