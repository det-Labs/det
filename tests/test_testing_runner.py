"""Tests for TestRunner orchestrating test suites and parsing schema definitions."""

import duckdb
from det.models.definition import ModelConfig, ModelDefinition
from det.testing.base import TestSeverity, TestType
from det.testing.definitions import TestDefinition
from det.testing.runner import TestRunner


def test_runner_executes_suite_and_aggregates_metrics() -> None:
    """Verify TestRunner aggregates passed, warned, errored, and quarantined counts."""
    con = duckdb.connect()
    con.execute("CREATE TABLE metrics_demo AS SELECT 1 AS id, 'valid' AS status")

    tests = [
        # Passed test
        TestDefinition(name="id_not_null", model_name="metrics_demo", test_type=TestType.NOT_NULL, column_name="id"),
        # Warn test (failing)
        TestDefinition(
            name="status_warn",
            model_name="metrics_demo",
            test_type=TestType.ACCEPTED_VALUES,
            column_name="status",
            severity=TestSeverity.WARN,
            parameters={"values": ["other"]},
        ),
        # Quarantine test (failing)
        TestDefinition(
            name="status_quarantine",
            model_name="metrics_demo",
            test_type=TestType.ACCEPTED_VALUES,
            column_name="status",
            severity=TestSeverity.QUARANTINE,
            parameters={"values": ["other"]},
        ),
    ]

    runner = TestRunner()
    report = runner.run_tests(con, tests)

    assert report.total_tests == 3
    assert report.passed == 1
    assert report.warned == 1
    assert report.quarantined == 1
    assert report.errored == 0
    assert report.is_successful is True  # Warn and quarantine do not block success
    con.close()


def test_runner_parses_schema_dictionary() -> None:
    """Verify parsing schema YAML definitions with column and model-level tests."""
    schema_dict = {
        "models": [
            {
                "name": "customers",
                "columns": [
                    {"name": "id", "tests": ["not_null", "unique"]},
                    {
                        "name": "email",
                        "tests": [
                            {
                                "type": "expression",
                                "expression": "email LIKE '%@%'",
                                "severity": "quarantine",
                            }
                        ],
                    },
                ],
            }
        ]
    }

    runner = TestRunner()
    parsed = runner.parse_schema_tests(schema_dict)

    assert len(parsed) == 3
    names = {t.name for t in parsed}
    assert "customers_id_not_null" in names
    assert "customers_id_unique" in names
    email_test = next(t for t in parsed if t.column_name == "email")
    assert email_test.severity == TestSeverity.QUARANTINE


def test_runner_combines_inferred_and_explicit_tests() -> None:
    """Verify run_model_tests runs both unique_key auto-inferred and explicit tests."""
    con = duckdb.connect()
    con.execute("CREATE TABLE products AS SELECT 101 AS product_id, 'Gadget' AS name")

    model = ModelDefinition(
        name="products",
        config=ModelConfig(unique_key="product_id"),
    )
    explicit_test = TestDefinition(
        name="name_not_null",
        model_name="products",
        test_type=TestType.NOT_NULL,
        column_name="name",
    )

    runner = TestRunner()
    report = runner.run_model_tests(con, model, explicit_tests=[explicit_test])

    # product_id_not_null (inferred) + product_id_unique (inferred) + name_not_null (explicit) = 3
    assert report.total_tests == 3
    assert report.passed == 3
    con.close()

