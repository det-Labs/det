"""Tests for data quality assertions: not_null, unique, accepted_values, expression, and custom SQL."""

import duckdb
import pytest

from det.models.definition import ModelConfig, ModelDefinition
from det.testing.base import TestSeverity, TestType
from det.testing.definitions import TestDefinition
from det.testing.evaluator import TestEvaluator


@pytest.fixture
def test_db() -> duckdb.DuckDBPyConnection:
    """Provide in-memory DuckDB connection with sample customer data."""
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE sample_users AS SELECT * FROM (VALUES
            (1, 'alice@corp.com', 25, 'active'),
            (2, 'bob@corp.com', 30, 'pending'),
            (3, NULL, -5, 'invalid_status'),
            (4, 'duplicate@corp.com', 40, 'active'),
            (5, 'duplicate@corp.com', 45, 'active')
        ) AS t(id, email, age, status)
    """)
    yield con
    con.close()


def test_not_null_assertion(test_db: duckdb.DuckDBPyConnection) -> None:
    """Verify not_null detects rows with NULL values."""
    evaluator = TestEvaluator()
    # id has no nulls
    test_pass = TestDefinition(name="id_not_null", model_name="sample_users", test_type=TestType.NOT_NULL, column_name="id")
    res_pass = evaluator.evaluate_test(test_db, test_pass)
    assert res_pass.passed is True
    assert res_pass.failing_rows_count == 0
    assert res_pass.passed_rows_count == 5
    assert res_pass.total_rows_count == 5

    # email has 1 null
    test_fail = TestDefinition(name="email_not_null", model_name="sample_users", test_type=TestType.NOT_NULL, column_name="email")
    res_fail = evaluator.evaluate_test(test_db, test_fail)
    assert res_fail.passed is False
    assert res_fail.failing_rows_count == 1
    assert res_fail.passed_rows_count == 4
    assert res_fail.total_rows_count == 5


def test_unique_assertion(test_db: duckdb.DuckDBPyConnection) -> None:
    """Verify unique detects duplicate values."""
    evaluator = TestEvaluator()
    # id is unique
    test_pass = TestDefinition(name="id_unique", model_name="sample_users", test_type=TestType.UNIQUE, column_name="id")
    res_pass = evaluator.evaluate_test(test_db, test_pass)
    assert res_pass.passed is True

    # email has duplicates (alice, bob, null, duplicate, duplicate) -> 2 rows share duplicate email
    test_fail = TestDefinition(name="email_unique", model_name="sample_users", test_type=TestType.UNIQUE, column_name="email")
    res_fail = evaluator.evaluate_test(test_db, test_fail)
    assert res_fail.passed is False
    assert res_fail.failing_rows_count == 2


def test_accepted_values_assertion(test_db: duckdb.DuckDBPyConnection) -> None:
    """Verify accepted_values checks allowed whitelist."""
    evaluator = TestEvaluator()
    test_def = TestDefinition(
        name="status_valid",
        model_name="sample_users",
        test_type=TestType.ACCEPTED_VALUES,
        column_name="status",
        parameters={"values": ["active", "pending"]},
    )
    res = evaluator.evaluate_test(test_db, test_def)
    assert res.passed is False
    # row 3 has 'invalid_status'
    assert res.failing_rows_count == 1


def test_expression_assertion(test_db: duckdb.DuckDBPyConnection) -> None:
    """Verify boolean expression assertion."""
    evaluator = TestEvaluator()
    test_def = TestDefinition(
        name="age_positive",
        model_name="sample_users",
        test_type=TestType.EXPRESSION,
        parameters={"expression": "age >= 0"},
    )
    res = evaluator.evaluate_test(test_db, test_def)
    assert res.passed is False
    # row 3 has age -5
    assert res.failing_rows_count == 1


def test_auto_inference_from_unique_key() -> None:
    """Verify TestDefinition.infer_from_model generates not_null and unique on unique_key."""
    model = ModelDefinition(
        name="orders",
        config=ModelConfig(unique_key="order_id"),
    )
    inferred = TestDefinition.infer_from_model(model)
    assert len(inferred) == 2
    types = {t.test_type for t in inferred}
    cols = {t.column_name for t in inferred}
    assert types == {TestType.NOT_NULL, TestType.UNIQUE}
    assert cols == {"order_id"}

