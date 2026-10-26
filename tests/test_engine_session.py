"""Tests for DuckDB session manager and engine configurations."""

from unittest.mock import MagicMock
import pytest
from det.engine.base import EngineConfig
from det.engine.session import DuckDBSessionManager, load_or_install_extension


def test_session_manager_initializes_default_connection() -> None:
    """Verify that default session connects to an in-memory DuckDB database."""
    manager = DuckDBSessionManager()
    con = manager.get_connection()
    assert con is not None
    res = con.execute("SELECT 1 AS num").fetchall()
    assert res == [(1,)]
    manager.close_connection()


def test_session_manager_reuses_connection_instance() -> None:
    """Verify singleton behavior: repeated get_connection calls return identical instance."""
    manager = DuckDBSessionManager()
    con1 = manager.get_connection()
    con2 = manager.get_connection()
    assert con1 is con2
    manager.close_connection()


def test_session_manager_custom_config() -> None:
    """Verify engine configuration options such as threads and memory limit."""
    config = EngineConfig(threads=2, memory_limit="500MB")
    manager = DuckDBSessionManager(config)
    con = manager.get_connection()
    assert con is not None
    manager.close_connection()


def test_session_manager_close_clears_connection() -> None:
    """Verify closing connection resets the reference cleanly."""
    manager = DuckDBSessionManager()
    con1 = manager.get_connection()
    manager.close_connection()
    con2 = manager.get_connection()
    assert con1 is not con2
    manager.close_connection()


def test_load_or_install_extension_fallback() -> None:
    """Verify fallback install attempt when initial load_extension fails."""
    mock_con = MagicMock()
    mock_con.load_extension.side_effect = [Exception("Extension not found"), None]
    
    success = load_or_install_extension(mock_con, "httpfs")
    assert success is True
    mock_con.install_extension.assert_called_once_with("httpfs")
    assert mock_con.load_extension.call_count == 2


def test_load_or_install_extension_failure_graceful() -> None:
    """Verify graceful handling when both install and load fail."""
    mock_con = MagicMock()
    mock_con.load_extension.side_effect = Exception("Extension unavailable")
    mock_con.install_extension.side_effect = Exception("Network offline")

    success = load_or_install_extension(mock_con, "nonexistent_ext")
    assert success is False

