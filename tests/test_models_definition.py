"""Tests for model definitions, configurations, and destination specs."""

from det.models.base import DestinationSpec, MaterializationType, WriteMode
from det.models.definition import ModelConfig, ModelDefinition


def test_destination_spec_parsing() -> None:
    """Verify parsing string and dictionary representations into DestinationSpec."""
    spec_str = DestinationSpec.from_any("local")
    assert spec_str.target == "local"
    assert spec_str.mode == WriteMode.REPLACE

    spec_dict = DestinationSpec.from_any({
        "target": "prod_pg.public.events",
        "mode": "append",
        "connection": "prod_pg",
    })
    assert spec_dict.target == "prod_pg.public.events"
    assert spec_dict.mode == WriteMode.APPEND
    assert spec_dict.connection == "prod_pg"


def test_model_config_defaults_and_parsing() -> None:
    """Verify ModelConfig instantiation from dictionary with destinations."""
    config = ModelConfig.from_dict({
        "materialized": "table",
        "unique_key": "user_id",
        "destinations": [
            "local",
            {"target": "s3_archive", "mode": "append"}
        ],
        "tags": ["daily", "core"],
    })
    assert config.materialized == MaterializationType.TABLE
    assert config.unique_key == "user_id"
    assert len(config.destinations) == 2
    assert config.destinations[1].mode == WriteMode.APPEND
    assert config.tags == ["daily", "core"]


def test_model_definition_materialize_sql() -> None:
    """Verify generating CREATE TABLE or VIEW SQL based on materialization."""
    view_model = ModelDefinition(
        name="stg_orders",
        compiled_sql="SELECT * FROM raw_orders",
        config=ModelConfig(materialized=MaterializationType.VIEW),
    )
    assert view_model.get_materialize_sql() == "CREATE OR REPLACE VIEW stg_orders AS SELECT * FROM raw_orders"

    table_model = ModelDefinition(
        name="fct_orders",
        compiled_sql="SELECT * FROM stg_orders",
        config=ModelConfig(materialized=MaterializationType.TABLE),
    )
    assert table_model.get_materialize_sql() == "CREATE OR REPLACE TABLE fct_orders AS SELECT * FROM stg_orders"


def test_model_all_dependencies_union() -> None:
    """Verify all_dependencies combines refs, sources, and direct connections."""
    model = ModelDefinition(
        name="sales_report",
        refs=["stg_users", "stg_orders"],
        sources=["crm_db"],
        direct_connections=["sales_csv"],
    )
    assert model.all_dependencies == {"stg_users", "stg_orders", "crm_db", "sales_csv"}

