"""Execution and evaluation of data quality test assertions against DuckDB."""

import logging
import time
import duckdb

from det.testing.base import (
    BaseTestEvaluator,
    TestResult,
    TestSeverity,
)
from det.testing.definitions import TestDefinition

logger = logging.getLogger(__name__)


class TestEvaluator(BaseTestEvaluator):
    """Executes test assertion queries and handles failure policies (halt, warn, drop)."""

    __test__ = False

    def __init__(self, quarantine_handler: Any = None) -> None:
        from det.testing.quarantine import QuarantineHandler
        self._quarantine = quarantine_handler or QuarantineHandler()

    def evaluate_test(
        self, con: duckdb.DuckDBPyConnection, test_def: TestDefinition
    ) -> TestResult:
        """Run failing-rows query and return comprehensive TestResult."""
        start_time = time.perf_counter()
        failing_query = test_def.get_failing_rows_query()

        try:
            failing_count = self._count_failing_rows(con, failing_query)
            total_count = self._count_total_rows(con, test_def.model_name)
            passed_count = max(0, total_count - failing_count)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            if failing_count == 0:
                return self._build_passed_result(test_def, passed_count, total_count, elapsed_ms)

            return self._handle_test_failure(
                con, test_def, failing_query, failing_count, passed_count, total_count, elapsed_ms
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error("Error executing test '%s': %s", test_def.name, exc)
            return self._build_error_result(test_def, str(exc), elapsed_ms)

    def _count_total_rows(self, con: duckdb.DuckDBPyConnection, model_name: str) -> int:
        """Query total row count of target model table or view."""
        try:
            res = con.execute(f"SELECT COUNT(*) FROM {model_name}").fetchall()
            return int(res[0][0]) if res else 0
        except Exception:
            return 0

    def _count_failing_rows(
        self, con: duckdb.DuckDBPyConnection, failing_query: str
    ) -> int:
        """Execute count wrapper over the failing-rows query."""
        count_sql = f"SELECT COUNT(*) FROM ({failing_query})"
        res = con.execute(count_sql).fetchall()
        return int(res[0][0]) if res else 0

    def _build_passed_result(
        self, test_def: TestDefinition, passed_count: int, total_count: int, elapsed_ms: float
    ) -> TestResult:
        """Construct passed TestResult object."""
        return TestResult(
            test_name=test_def.name,
            model_name=test_def.model_name,
            column_name=test_def.column_name,
            severity=test_def.severity,
            passed=True,
            failing_rows_count=0,
            passed_rows_count=passed_count,
            total_rows_count=total_count,
            execution_time_ms=round(elapsed_ms, 2),
        )

    def _handle_test_failure(
        self,
        con: duckdb.DuckDBPyConnection,
        test_def: TestDefinition,
        failing_query: str,
        failing_count: int,
        passed_count: int,
        total_count: int,
        elapsed_ms: float,
    ) -> TestResult:
        """Handle failure according to policy: error (halt), warn (log count), or drop (filter rows)."""
        quarantine_table: str | None = None
        if test_def.severity == TestSeverity.DROP:
            try:
                con.execute(
                    f"CREATE OR REPLACE TABLE {test_def.model_name} AS "
                    f"SELECT * FROM {test_def.model_name} EXCEPT ALL ({failing_query})"
                )
                quarantine_table = f"Dropped {failing_count} rows"
            except Exception as e:
                logger.warning("Could not drop failing rows from '%s': %s", test_def.model_name, e)
                quarantine_table = f"Failed to drop: {e}"
        elif test_def.severity == TestSeverity.QUARANTINE:
            quarantine_table = self._quarantine.quarantine_records(
                con, test_def.model_name, test_def.name, failing_query
            )
        elif test_def.severity in (TestSeverity.WARN, TestSeverity.WARNING):
            quarantine_table = f"Warning: {failing_count} rows violated test"
        else:
            quarantine_table = f"Error: {failing_count} rows violated test"

        return TestResult(
            test_name=test_def.name,
            model_name=test_def.model_name,
            column_name=test_def.column_name,
            severity=test_def.severity,
            passed=False,
            failing_rows_count=failing_count,
            passed_rows_count=passed_count,
            total_rows_count=total_count,
            quarantined_table=quarantine_table,
            execution_time_ms=round(elapsed_ms, 2),
        )

    def _build_error_result(
        self, test_def: TestDefinition, err_msg: str, elapsed_ms: float
    ) -> TestResult:
        """Construct TestResult representing an execution exception."""
        return TestResult(
            test_name=test_def.name,
            model_name=test_def.model_name,
            column_name=test_def.column_name,
            severity=test_def.severity,
            passed=False,
            failing_rows_count=0,
            execution_time_ms=round(elapsed_ms, 2),
            error_message=err_msg,
        )
