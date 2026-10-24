"""Test runner coordinating assertion suites and schema tests across models."""

import logging
from typing import Any
import duckdb

from det.models.definition import ModelDefinition
from det.testing.base import (
    BaseTestRunner,
    TestSuiteReport,
    TestType,
)
from det.testing.definitions import TestDefinition
from det.testing.evaluator import TestEvaluator

logger = logging.getLogger(__name__)


class TestRunner(BaseTestRunner):
    """Executes test assertion suites across models, schemas, and projects."""

    __test__ = False

    def __init__(self, evaluator: TestEvaluator | None = None) -> None:
        self._evaluator = evaluator or TestEvaluator()

    def run_tests(
        self, con: duckdb.DuckDBPyConnection, tests: list[TestDefinition]
    ) -> TestSuiteReport:
        """Execute a collection of tests and compile report metrics."""
        report = TestSuiteReport()
        for test in tests:
            result = self._evaluator.evaluate_test(con, test)
            report.add_result(result)
        return report

    def run_model_tests(
        self,
        con: duckdb.DuckDBPyConnection,
        model: ModelDefinition,
        explicit_tests: list[TestDefinition] | None = None,
    ) -> TestSuiteReport:
        """Run all auto-inferred and explicit tests for a specific model."""
        inferred = TestDefinition.infer_from_model(model)
        all_tests = list(inferred) + list(explicit_tests or [])
        return self.run_tests(con, all_tests)

    def parse_schema_tests(
        self, schema_dict: dict[str, Any]
    ) -> list[TestDefinition]:
        """Parse tests declared within models schema dictionary."""
        tests: list[TestDefinition] = []
        for model_data in schema_dict.get("models", []):
            model_name = model_data.get("name")
            if not model_name:
                continue
            tests.extend(self._parse_column_tests(model_name, model_data.get("columns", [])))
            tests.extend(self._parse_model_level_tests(model_name, model_data.get("tests", [])))
        return tests

    def _parse_column_tests(
        self, model_name: str, columns: list[dict[str, Any]]
    ) -> list[TestDefinition]:
        """Extract column-level tests from schema definition."""
        parsed: list[TestDefinition] = []
        for col_data in columns:
            col_name = col_data.get("name")
            for t_item in col_data.get("tests", []):
                t_def = self._normalize_test_item(model_name, col_name, t_item)
                if t_def:
                    parsed.append(t_def)
        return parsed

    def _parse_model_level_tests(
        self, model_name: str, tests_list: list[Any]
    ) -> list[TestDefinition]:
        """Extract model-level tests from schema definition."""
        parsed: list[TestDefinition] = []
        for t_item in tests_list:
            t_def = self._normalize_test_item(model_name, None, t_item)
            if t_def:
                parsed.append(t_def)
        return parsed

    def _normalize_test_item(
        self, model_name: str, col_name: str | None, item: Any
    ) -> TestDefinition | None:
        """Convert string or dictionary test description into a TestDefinition."""
        if isinstance(item, str):
            try:
                tt = TestType(item)
                return TestDefinition(
                    name=f"{model_name}_{col_name or 'tbl'}_{tt.value}",
                    model_name=model_name,
                    test_type=tt,
                    column_name=col_name,
                )
            except ValueError:
                return None
        if isinstance(item, dict):
            first_key = next(iter(item.keys()))
            if len(item) == 1 and first_key in [t.value for t in TestType]:
                val = item[first_key]
                item_data = dict(val) if isinstance(val, dict) else {"expression": val}
                item_data["type"] = first_key
            else:
                item_data = dict(item)
            if col_name and "column" not in item_data:
                item_data["column"] = col_name
            return TestDefinition.from_dict(model_name, item_data)
        return None
