"""Tests for DocsExtractor introspecting DuckDB schemas and matching test assertions."""

import duckdb
from det.docs.extractor import DocsExtractor
from det.models.definition import ModelConfig, ModelDefinition
from det.testing.base import TestSeverity, TestType
from det.testing.definitions import TestDefinition


def _build_sample_model_and_tests():
    model = ModelDefinition(
        name="customers",
        project="core",
        description="Core customer master table",
        compiled_sql="SELECT * FROM raw_customers",
        config=ModelConfig(materialized="table", tags=["core"]),
    )
    tests = [
        TestDefinition(name="id_not_null", model_name="customers", test_type=TestType.NOT_NULL, column_name="id"),
        TestDefinition(name="id_unique", model_name="customers", test_type=TestType.UNIQUE, column_name="id"),
        TestDefinition(
            name="balance_positive",
            model_name="customers",
            test_type=TestType.EXPRESSION,
            column_name="balance",
            severity=TestSeverity.QUARANTINE,
        ),
    ]
    return model, tests


def test_docs_extractor_introspects_columns_and_badges() -> None:
    """Verify DocsExtractor reads column types from DuckDB and attaches test badges."""
    con = duckdb.connect()
    con.execute("CREATE TABLE customers AS SELECT 1 AS id, 'alice' AS name, 100.5 AS balance")
    model, tests = _build_sample_model_and_tests()

    extractor = DocsExtractor()
    model_doc = extractor.extract_model_doc(con, model, tests)

    assert model_doc.name == "customers"
    assert model_doc.description == "Core customer master table"
    assert len(model_doc.columns) == 3

    id_col = next(c for c in model_doc.columns if c.name == "id")
    assert id_col.data_type == "INTEGER"
    assert "NOT_NULL" in id_col.test_badges
    assert "UNIQUE" in id_col.test_badges

    bal_col = next(c for c in model_doc.columns if c.name == "balance")
    assert "DECIMAL" in bal_col.data_type or "DOUBLE" in bal_col.data_type
    assert any("QUARANTINE" in b for b in bal_col.test_badges)
    con.close()


def test_docs_extractor_handles_unmaterialized_model() -> None:
    """Verify extractor returns empty columns when model table does not yet exist."""
    con = duckdb.connect()
    model = ModelDefinition(name="unbuilt_model", project="demo")
    extractor = DocsExtractor()
    model_doc = extractor.extract_model_doc(con, model)
    assert model_doc.columns == []
    con.close()
