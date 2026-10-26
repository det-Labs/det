"""Base protocols, enums, and outcome models for data quality and quarantine testing."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import duckdb


class TestType(str, Enum):
    """Supported data quality assertion types."""

    __test__ = False

    NOT_NULL = "not_null"
    UNIQUE = "unique"
    ACCEPTED_VALUES = "accepted_values"
    EXPRESSION = "expression"
    CUSTOM_SQL = "custom_sql"


class TestSeverity(str, Enum):
    """Enforcement severity for test failures."""

    __test__ = False

    WARN = "warn"
    WARNING = "warning"
    ERROR = "error"
    DROP = "drop"
    QUARANTINE = "quarantine"  # alias to drop for backward compatibility


@dataclass(frozen=True)
class TestResult:
    """Individual assertion execution result."""

    __test__ = False

    test_name: str
    model_name: str
    column_name: str | None
    severity: TestSeverity
    passed: bool
    failing_rows_count: int
    passed_rows_count: int = 0
    total_rows_count: int = 0
    quarantined_table: str | None = None
    execution_time_ms: float = 0.0
    error_message: str | None = None


@dataclass
class TestSuiteReport:
    """Aggregate summary of test suite execution across models."""

    __test__ = False
    total_tests: int = 0
    passed: int = 0
    warned: int = 0
    errored: int = 0
    dropped: int = 0
    quarantined: int = 0
    results: list[TestResult] = field(default_factory=list)

    @property
    def is_successful(self) -> bool:
        """Return True if no error-severity tests failed."""
        return self.errored == 0

    def add_result(self, result: TestResult) -> None:
        """Incorporate a single test result into aggregate metrics."""
        self.total_tests += 1
        self.results.append(result)
        if result.passed:
            self.passed += 1
        elif result.severity in (TestSeverity.WARN, TestSeverity.WARNING):
            self.warned += 1
        elif result.severity in (TestSeverity.DROP, TestSeverity.QUARANTINE):
            self.dropped += 1
            self.quarantined += 1
        else:
            self.errored += 1


class BaseTestEvaluator(ABC):
    """Interface for evaluating test assertions against DuckDB."""

    @abstractmethod
    def evaluate_test(
        self, con: duckdb.DuckDBPyConnection, test_def: Any
    ) -> TestResult:
        """Run assertion query and compute result."""
        pass


class BaseQuarantineHandler(ABC):
    """Interface for routing failing rows into quarantine sinks."""

    @abstractmethod
    def quarantine_records(
        self,
        con: duckdb.DuckDBPyConnection,
        model_name: str,
        test_name: str,
        failing_query: str,
    ) -> str:
        """Extract violating rows into _quarantine_<model> table."""
        pass


class BaseTestRunner(ABC):
    """Interface for orchestrating test execution across models."""

    @abstractmethod
    def run_tests(
        self, con: duckdb.DuckDBPyConnection, tests: list[Any]
    ) -> TestSuiteReport:
        """Execute test batch and return summary report."""
        pass
