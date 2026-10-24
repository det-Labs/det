"""Tests for dependency graph topological ordering, cycles, and staged parallelism."""

import pytest
from det.models.dag import ModelDAG
from det.models.definition import ModelDefinition


def test_topological_execution_order() -> None:
    """Verify execution order respects dependencies (staging before marts)."""
    dag = ModelDAG()
    stg_users = ModelDefinition(name="stg_users", refs=[])
    stg_orders = ModelDefinition(name="stg_orders", refs=[])
    fct_sales = ModelDefinition(name="fct_sales", refs=["stg_users", "stg_orders"])
    daily_mart = ModelDefinition(name="daily_mart", refs=["fct_sales"])

    dag.add_model(daily_mart)
    dag.add_model(fct_sales)
    dag.add_model(stg_users)
    dag.add_model(stg_orders)

    order = dag.get_execution_order()
    assert order.index("stg_users") < order.index("fct_sales")
    assert order.index("stg_orders") < order.index("fct_sales")
    assert order.index("fct_sales") < order.index("daily_mart")


def test_staged_parallel_execution_tiers() -> None:
    """Verify models are grouped into non-dependent parallel stages."""
    dag = ModelDAG()
    dag.add_model(ModelDefinition(name="stg_a", refs=[]))
    dag.add_model(ModelDefinition(name="stg_b", refs=[]))
    dag.add_model(ModelDefinition(name="intm_ab", refs=["stg_a", "stg_b"]))
    dag.add_model(ModelDefinition(name="gold_mart", refs=["intm_ab"]))

    stages = dag.get_execution_stages()
    assert len(stages) == 3
    # Stage 0: root models with no model dependencies
    assert stages[0].models == ["stg_a", "stg_b"]
    # Stage 1: depends on Stage 0
    assert stages[1].models == ["intm_ab"]
    # Stage 2: depends on Stage 1
    assert stages[2].models == ["gold_mart"]


def test_cycle_detection_raises_runtime_error() -> None:
    """Verify circular dependencies are caught and reported with diagnostic path."""
    dag = ModelDAG()
    dag.add_model(ModelDefinition(name="model_a", refs=["model_b"]))
    dag.add_model(ModelDefinition(name="model_b", refs=["model_c"]))
    dag.add_model(ModelDefinition(name="model_c", refs=["model_a"]))

    with pytest.raises(RuntimeError, match="Circular dependency detected"):
        dag.get_execution_order()


def test_model_selection_upstream_and_downstream() -> None:
    """Verify +model, model+, and +model+ selector traversal."""
    dag = ModelDAG()
    dag.add_model(ModelDefinition(name="raw", refs=[]))
    dag.add_model(ModelDefinition(name="stg", refs=["raw"]))
    dag.add_model(ModelDefinition(name="mart", refs=["stg"]))
    dag.add_model(ModelDefinition(name="report", refs=["mart"]))

    # +mart selects mart and all upstream ancestors
    upstream = dag.select_models("+mart")
    assert upstream == {"mart", "stg", "raw"}

    # stg+ selects stg and all downstream descendants
    downstream = dag.select_models("stg+")
    assert downstream == {"stg", "mart", "report"}

    # exact
    exact = dag.select_models("stg")
    assert exact == {"stg"}

