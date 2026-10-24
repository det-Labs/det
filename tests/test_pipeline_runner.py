"""Tests for PipelineRunner executing models and publishing to destinations."""

from det.engine.facade import EngineFacade
from det.models.base import DestinationSpec, MaterializationType, WriteMode
from det.models.dag import ModelDAG
from det.models.definition import ModelConfig, ModelDefinition
from det.runner import PipelineRunner


def test_pipeline_runner_executes_models_in_order() -> None:
    """Verify runner executes staging before marts and captures telemetry."""
    engine = EngineFacade()
    runner = PipelineRunner(engine=engine)

    dag = ModelDAG()
    dag.add_model(
        ModelDefinition(
            name="stg_users",
            compiled_sql="SELECT 1 AS user_id, 'Alice' AS name",
            config=ModelConfig(materialized=MaterializationType.TABLE),
        )
    )
    dag.add_model(
        ModelDefinition(
            name="fct_users",
            compiled_sql="SELECT user_id, UPPER(name) AS upper_name FROM stg_users",
            refs=["stg_users"],
            config=ModelConfig(materialized=MaterializationType.TABLE),
        )
    )

    report = runner.run_dag(dag)
    assert report.is_successful is True
    assert report.total_models == 2
    assert report.succeeded == 2
    assert report.failed == 0

    # Verify rows exist in DuckDB session
    res = engine.execute("SELECT * FROM fct_users").rows
    assert res == [(1, "ALICE")]
    engine.close()


def test_pipeline_runner_publishes_to_destinations() -> None:
    """Verify runner materializes locally and publishes to secondary destinations."""
    engine = EngineFacade()
    runner = PipelineRunner(engine=engine)

    dag = ModelDAG()
    dag.add_model(
        ModelDefinition(
            name="orders_mart",
            compiled_sql="SELECT 101 AS order_id, 250.0 AS amount",
            config=ModelConfig(
                materialized=MaterializationType.TABLE,
                destinations=[
                    DestinationSpec(target="local"),
                    DestinationSpec(target="sink_table", mode=WriteMode.REPLACE),
                ],
            ),
        )
    )

    report = runner.run_dag(dag)
    assert report.is_successful is True

    # Verify both local and secondary sink were written
    local_rows = engine.execute("SELECT * FROM orders_mart").rows
    sink_rows = engine.execute("SELECT * FROM sink_table").rows
    assert local_rows == [(101, 250.0)]
    assert sink_rows == [(101, 250.0)]
    engine.close()


def test_pipeline_runner_halts_on_model_failure() -> None:
    """Verify pipeline halts immediately if a model encounters an execution error."""
    engine = EngineFacade()
    runner = PipelineRunner(engine=engine)

    dag = ModelDAG()
    dag.add_model(
        ModelDefinition(
            name="broken_model",
            compiled_sql="SELECT * FROM table_that_does_not_exist_xyz",
            config=ModelConfig(materialized=MaterializationType.TABLE),
        )
    )

    report = runner.run_dag(dag)
    assert report.is_successful is False
    assert report.failed == 1
    assert "Catalog Error" in (report.results[0].error_message or "") or "does not exist" in (report.results[0].error_message or "")
    engine.close()

