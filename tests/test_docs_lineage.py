"""Tests for LineageGenerator producing interactive Mermaid flowchart markup."""

from det.docs.lineage import LineageGenerator
from det.models.dag import ModelDAG
from det.models.definition import ModelDefinition


def test_lineage_generator_produces_valid_mermaid() -> None:
    """Verify LineageGenerator outputs flowchart LR with sources, models, and edges."""
    dag = ModelDAG()
    stg_users = ModelDefinition(name="stg_users", refs=[], direct_connections=["users_csv"])
    fct_sales = ModelDefinition(name="fct_sales", refs=["stg_users"])

    dag.add_model(stg_users)
    dag.add_model(fct_sales)

    gen = LineageGenerator()
    mermaid_code = gen.generate_mermaid(dag)

    assert "flowchart LR" in mermaid_code
    # External source node
    assert 'src_users_csv[("users_csv")]:::sourceNode' in mermaid_code
    # Internal model nodes
    assert 'mod_stg_users["stg_users"]:::modelNode' in mermaid_code
    assert 'mod_fct_sales["fct_sales"]:::modelNode' in mermaid_code
    # Directed edge
    assert "src_users_csv --> mod_stg_users" in mermaid_code
    assert "mod_stg_users --> mod_fct_sales" in mermaid_code

