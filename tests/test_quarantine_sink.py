"""Tests for quarantine sink routing, failure tagging, and inspection."""

import duckdb
import pytest

from det.testing.base import TestSeverity, TestType
from det.testing.definitions import TestDefinition
from det.testing.evaluator import TestEvaluator
from det.testing.quarantine import QuarantineHandler


@pytest.fixture
def clean_db() -> duckdb.DuckDBPyConnection:
    """Create in-memory database with customer orders containing dirty data."""
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE raw_orders AS SELECT * FROM (VALUES
            (101, 'US', 150.0),
            (102, 'US', -20.0),
            (103, 'XX', 99.0)
        ) AS t(order_id, country_code, amount)
    """)
    yield con
    con.close()


def test_quarantine_sink_creates_table_and_inserts_violating_rows(
    clean_db: duckdb.DuckDBPyConnection,
) -> None:
    """Verify failing rows are routed to _quarantine_raw_orders with metadata tags."""
    handler = QuarantineHandler()
    evaluator = TestEvaluator(quarantine_handler=handler)

    test_def = TestDefinition(
        name="positive_amount",
        model_name="raw_orders",
        test_type=TestType.EXPRESSION,
        severity=TestSeverity.QUARANTINE,
        parameters={"expression": "amount > 0"},
    )

    res = evaluator.evaluate_test(clean_db, test_def)
    assert res.passed is False
    assert res.severity == TestSeverity.QUARANTINE
    assert res.failing_rows_count == 1
    assert res.quarantined_table == "_quarantine_raw_orders"

    # Check quarantine table contents
    quarantine_count = handler.get_quarantined_count(clean_db, "raw_orders")
    assert quarantine_count == 1

    cols, rows = handler.get_quarantined_rows(clean_db, "raw_orders")
    assert "quarantined_at" in cols
    assert "failure_reason" in cols
    # Row 102 had amount -20.0
    failed_row = rows[0]
    reason_idx = cols.index("failure_reason")
    assert failed_row[reason_idx] == "positive_amount"


def test_multiple_quarantine_tests_append_to_same_sink(
    clean_db: duckdb.DuckDBPyConnection,
) -> None:
    """Verify multiple failing tests route to the same model quarantine table."""
    handler = QuarantineHandler()
    evaluator = TestEvaluator(quarantine_handler=handler)

    # Test 1: amount > 0 (1 failing row: 102)
    t1 = TestDefinition(
        name="positive_amount",
        model_name="raw_orders",
        test_type=TestType.EXPRESSION,
        severity=TestSeverity.QUARANTINE,
        parameters={"expression": "amount > 0"},
    )
    evaluator.evaluate_test(clean_db, t1)

    # Test 2: valid country (1 failing row: 103)
    t2 = TestDefinition(
        name="valid_country",
        model_name="raw_orders",
        test_type=TestType.ACCEPTED_VALUES,
        column_name="country_code",
        severity=TestSeverity.QUARANTINE,
        parameters={"values": ["US", "CA"]},
    )
    evaluator.evaluate_test(clean_db, t2)

    total_quarantined = handler.get_quarantined_count(clean_db, "raw_orders")
    assert total_quarantined == 2

    _, rows = handler.get_quarantined_rows(clean_db, "raw_orders")
    assert len(rows) == 2

