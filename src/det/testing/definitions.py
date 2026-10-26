"""Declarative test definitions, automatic inference, and SQL assertion compilers."""

from dataclasses import dataclass, field
from typing import Any

from det.models.definition import ModelDefinition
from det.testing.base import TestSeverity, TestType


@dataclass
class TestDefinition:
    """Represents a data quality assertion defined on a model."""

    __test__ = False

    name: str
    model_name: str
    test_type: TestType
    column_name: str | None = None
    severity: TestSeverity = TestSeverity.ERROR
    parameters: dict[str, Any] = field(default_factory=dict)
    custom_query: str | None = None

    def get_failing_rows_query(self) -> str:
        """Compile and return SQL query that returns all rows violating this test."""
        if self.test_type == TestType.NOT_NULL:
            return self._build_not_null_query()
        if self.test_type == TestType.UNIQUE:
            return self._build_unique_query()
        if self.test_type == TestType.ACCEPTED_VALUES:
            return self._build_accepted_values_query()
        if self.test_type == TestType.EXPRESSION:
            return self._build_expression_query()
        return self._build_custom_sql_query()

    def _build_not_null_query(self) -> str:
        """Query rows where target column is NULL."""
        return f"SELECT * FROM {self.model_name} WHERE {self.column_name} IS NULL"

    def _build_unique_query(self) -> str:
        """Query rows that have duplicate values in target column."""
        subquery = (
            f"SELECT {self.column_name} FROM {self.model_name} "
            f"WHERE {self.column_name} IS NOT NULL "
            f"GROUP BY {self.column_name} HAVING COUNT(*) > 1"
        )
        return f"SELECT * FROM {self.model_name} WHERE {self.column_name} IN ({subquery})"

    def _build_accepted_values_query(self) -> str:
        """Query rows with values outside the accepted whitelist."""
        raw_values = self.parameters.get("values", [])
        escaped_values = [f"'{str(v).replace('\'', '\'\'')}'" for v in raw_values]
        values_clause = ", ".join(escaped_values) if escaped_values else "NULL"
        return (
            f"SELECT * FROM {self.model_name} "
            f"WHERE {self.column_name} NOT IN ({values_clause}) "
            f"OR {self.column_name} IS NULL"
        )

    def _build_expression_query(self) -> str:
        """Query rows violating custom boolean expression."""
        expr = self.parameters.get("expression") or self.custom_query or "TRUE"
        return f"SELECT * FROM {self.model_name} WHERE NOT ({expr}) OR ({expr}) IS NULL"

    def _build_custom_sql_query(self) -> str:
        """Return custom user-provided SQL query."""
        if not self.custom_query:
            raise ValueError(f"Custom SQL test '{self.name}' must have 'custom_query' defined.")
        return self.custom_query.strip()

    @classmethod
    def from_dict(cls, model_name: str, data: dict[str, Any]) -> "TestDefinition":
        """Instantiate a TestDefinition from parsed schema dictionary."""
        col = data.get("column") or data.get("column_name")
        raw_type = data.get("type") or data.get("test_type", "expression")
        test_type = TestType(raw_type)

        raw_sev = data.get("severity", TestSeverity.ERROR.value)
        if isinstance(raw_sev, str):
            sev_str = raw_sev.lower()
            if sev_str in ("warn", "warning"):
                severity = TestSeverity.WARN
            elif sev_str == "drop":
                severity = TestSeverity.DROP
            elif sev_str == "quarantine":
                severity = TestSeverity.QUARANTINE
            else:
                severity = TestSeverity.ERROR
        else:
            severity = raw_sev

        name = data.get("name") or f"{model_name}_{col or 'tbl'}_{test_type.value}"
        params = {k: v for k, v in data.items() if k not in ("name", "column", "column_name", "type", "test_type", "severity", "custom_query")}
        if "expression" in data:
            params["expression"] = data["expression"]
        if "values" in data:
            params["values"] = data["values"]

        return cls(
            name=name,
            model_name=model_name,
            test_type=test_type,
            column_name=col,
            severity=severity,
            parameters=params,
            custom_query=data.get("custom_query"),
        )

    @classmethod
    def infer_from_model(cls, model: ModelDefinition) -> list["TestDefinition"]:
        """Auto-generate baseline tests (not_null, unique) from unique_key config."""
        inferred: list[TestDefinition] = []
        key = model.config.unique_key
        if not key:
            return inferred

        inferred.append(
            cls(
                name=f"{model.name}_{key}_not_null",
                model_name=model.name,
                test_type=TestType.NOT_NULL,
                column_name=key,
                severity=TestSeverity.ERROR,
            )
        )
        inferred.append(
            cls(
                name=f"{model.name}_{key}_unique",
                model_name=model.name,
                test_type=TestType.UNIQUE,
                column_name=key,
                severity=TestSeverity.ERROR,
            )
        )
        return inferred
