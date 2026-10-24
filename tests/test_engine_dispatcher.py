"""Tests for query dispatcher and error formatting."""

import duckdb
import pytest
from det.engine.dispatcher import QueryDispatcher


def test_dispatcher_executes_select_query() -> None:
    """Verify executing a valid query returns QueryResult with columns and rows."""
    con = duckdb.connect()
    dispatcher = QueryDispatcher()
    res = dispatcher.execute_query(con, "SELECT 42 AS answer, 'det' AS project")
    assert res.columns == ["answer", "project"]
    assert res.rows == [(42, "det")]
    assert res.row_count == 1
    con.close()


def test_dispatcher_executes_empty_result_query() -> None:
    """Verify executing a query that produces zero rows."""
    con = duckdb.connect()
    dispatcher = QueryDispatcher()
    res = dispatcher.execute_query(con, "SELECT 1 AS x WHERE 1 = 0")
    assert res.columns == ["x"]
    assert res.rows == []
    assert res.row_count == 0
    con.close()


def test_dispatcher_formats_catalog_error_on_missing_table() -> None:
    """Verify user-friendly error formatting when a table is missing."""
    con = duckdb.connect()
    dispatcher = QueryDispatcher()
    with pytest.raises(RuntimeError, match="Catalog Error:"):
        dispatcher.execute_query(con, "SELECT * FROM missing_table_123")
    con.close()


def test_dispatcher_formats_syntax_error() -> None:
    """Verify syntax error formatting on malformed SQL."""
    con = duckdb.connect()
    dispatcher = QueryDispatcher()
    with pytest.raises(RuntimeError, match="Syntax Error:"):
        dispatcher.execute_query(con, "SELECT SELECT FROM")
    con.close()

