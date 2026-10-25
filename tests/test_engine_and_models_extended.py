"""Extended tests for Engine Execution, Models Parser, DAG edge cases, and Data Quality."""

from pathlib import Path
import duckdb
import pytest

from det.catalog.base import ConnectionTier
from det.catalog.definitions import ConnectionDefinition
from det.engine.facade import EngineFacade
from det.models.base import DestinationSpec, MaterializationType, WriteMode
from det.models.dag import ModelDAG
from det.models.definition import ModelConfig, ModelDefinition
from det.models.parser import ModelParser
from det.runner import PipelineRunner
from det.testing.base import TestResult, TestSeverity, TestType
from det.testing.definitions import TestDefinition
from det.testing.evaluator import TestEvaluator
from det.testing.runner import TestRunner


def test_pipeline_runner_delta_append_mode(tmp_path: Path) -> None:
    """Verify PipelineRunner writes initial Delta table in REPLACE mode, then adds batch in APPEND mode."""
    con = duckdb.connect()
    delta_dir = tmp_path / "delta_append_test"
    runner = PipelineRunner(workspace_root=tmp_path)

    # 1. Batch 1: 2 rows in REPLACE mode
    con.execute("CREATE TABLE source_batch AS SELECT 1 AS id, 'Batch 1' AS label UNION ALL SELECT 2, 'Batch 1';")
    model_b1 = ModelDefinition(
        name="source_batch",
        compiled_sql="SELECT * FROM source_batch",
        config=ModelConfig(
            materialized=MaterializationType.TABLE,
            destinations=[
                DestinationSpec(target="delta_sink", path=str(delta_dir), format="delta", mode=WriteMode.REPLACE)
            ],
        ),
    )
    runner._publish_destinations(con, model_b1)

    # Verify 2 rows in Delta
    con.execute("LOAD delta;")
    rows_b1 = con.execute(f"SELECT * FROM delta_scan('{str(delta_dir).replace('\\', '/')}')").fetchall()
    assert len(rows_b1) == 2

    # 2. Batch 2: 3 more rows in APPEND mode
    con.execute("CREATE OR REPLACE TABLE source_batch AS SELECT 3 AS id, 'Batch 2' AS label UNION ALL SELECT 4, 'Batch 2' UNION ALL SELECT 5, 'Batch 2';")
    model_b2 = ModelDefinition(
        name="source_batch",
        compiled_sql="SELECT * FROM source_batch",
        config=ModelConfig(
            materialized=MaterializationType.TABLE,
            destinations=[
                DestinationSpec(target="delta_sink", path=str(delta_dir), format="delta", mode=WriteMode.APPEND)
            ],
        ),
    )
    runner._publish_destinations(con, model_b2)

    # Verify total 5 rows in Delta
    rows_total = con.execute(f"SELECT * FROM delta_scan('{str(delta_dir).replace('\\', '/')}') ORDER BY id").fetchall()
    assert len(rows_total) == 5
    assert rows_total[0][0] == 1
    assert rows_total[4][0] == 5


def test_pipeline_runner_excel_cloud_uri_guard() -> None:
    """Verify Excel export rejects cloud URIs since Excel requires a local filesystem."""
    con = duckdb.connect()
    runner = PipelineRunner()
    con.execute("CREATE TABLE mock_tbl AS SELECT 1 AS x;")

    model = ModelDefinition(
        name="mock_tbl",
        compiled_sql="SELECT 1 AS x",
        config=ModelConfig(
            materialized=MaterializationType.TABLE,
            destinations=[
                DestinationSpec(target="s3_excel", path="s3://my-bucket/out.xlsx")
            ],
        ),
    )
    with pytest.raises(ValueError, match="Direct Excel export to cloud URI.*is not supported"):
        runner._publish_destinations(con, model)


def test_parser_complex_ctes_window_functions_and_comments() -> None:
    """Verify JinjaParser and ASTParser handle complex multi-CTE queries, window functions, and comments."""
    sql = """
    -- This is a comment containing {{ ref('ignored_comment_ref') }}
    /* Multi-line comment
       referencing {{ ref('another_ignored_ref') }}
    */
    WITH active_orders AS (
        SELECT order_id, customer_id, amount,
               ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) as rn
        FROM {{ ref('stg_orders') }}
        WHERE status = 'COMPLETED'
    ),
    customer_aggregates AS (
        SELECT customer_id, SUM(amount) AS total_spent
        FROM active_orders
        GROUP BY customer_id
    )
    SELECT c.customer_id, c.email, a.total_spent
    FROM {{ ref('stg_customers') }} c
    JOIN customer_aggregates a ON c.customer_id = a.customer_id
    WHERE a.total_spent > 100
    """
    parser = ModelParser()
    extracted_refs = parser.parse_refs(sql)
    assert "stg_orders" in extracted_refs
    assert "stg_customers" in extracted_refs

    model = parser.parse_text("customer_spending", sql, project="analytics")
    assert model.name == "customer_spending"
    assert "stg_orders" in model.refs
    assert "stg_customers" in model.refs
    assert "customer_spending" in model.compiled_sql or "FROM stg_orders" in model.compiled_sql


def test_catalog_database_connection_string_resolution() -> None:
    """Verify ConnectionDefinition resolves credentials dict with host/port/dbname/user/password."""
    conn = ConnectionDefinition(
        name="dw_postgres",
        type="postgres",
        tier=ConnectionTier.DATABASE,
        credentials={
            "host": "postgres.corp",
            "port": 5432,
            "dbname": "finance_dw",
            "user": "etl_reader",
            "password": "strong_password",
        },
    )
    mount_sql = conn.get_mount_sql()
    assert "ATTACH 'host=postgres.corp port=5432 dbname=finance_dw user=etl_reader password=strong_password' AS dw_postgres (TYPE POSTGRES)" in mount_sql

    # Invalid identifier validation
    with pytest.raises(ValueError, match="cannot start with a number"):
        ConnectionDefinition(
            name="123_invalid-name!",
            type="postgres",
            tier=ConnectionTier.DATABASE,
        )


def test_assertion_evaluator_accepted_values_and_warn_severity() -> None:
    """Verify AssertionEvaluator checks accepted values and respects warn severity without crashing."""
    con = duckdb.connect()
    evaluator = TestEvaluator()

    con.execute("""
        CREATE TABLE sample_orders AS
        SELECT 1 AS id, 'DELIVERED' AS status
        UNION ALL
        SELECT 2, 'PENDING'
        UNION ALL
        SELECT 3, 'UNKNOWN_STATUS';
    """)

    # 1. Accepted values test failing on row 3
    test_accepted = TestDefinition(
        name="test_order_status_values",
        model_name="sample_orders",
        column_name="status",
        test_type=TestType.ACCEPTED_VALUES,
        severity=TestSeverity.WARN,
        parameters={"values": ["DELIVERED", "PENDING", "PROCESSING"]},
    )
    res = evaluator.evaluate_test(con, test_accepted)
    assert res.passed is False
    assert res.failing_rows_count == 1
    assert res.severity == TestSeverity.WARN

    # 2. Custom expression test passing
    test_expr = TestDefinition(
        name="test_order_id_positive",
        model_name="sample_orders",
        column_name="id",
        test_type=TestType.EXPRESSION,
        severity=TestSeverity.ERROR,
        parameters={"expression": "id > 0"},
    )
    res_expr = evaluator.evaluate_test(con, test_expr)
    assert res_expr.passed is True
    assert res_expr.failing_rows_count == 0
