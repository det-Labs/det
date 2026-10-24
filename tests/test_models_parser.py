"""Tests for SQL model parser extracting configs, refs, and macro replacements."""

from det.models.base import MaterializationType
from det.models.parser import ModelParser


def test_parser_extracts_config_block() -> None:
    """Verify parsing {{ config(...) }} blocks with multiple options."""
    parser = ModelParser()
    raw_sql = """
    {{ config(materialized='table', unique_key='id', tags=['finance']) }}
    SELECT id, name FROM raw_users
    """
    config, clean_sql = parser.parse_config(raw_sql)
    assert config.materialized == MaterializationType.TABLE
    assert config.unique_key == "id"
    assert config.tags == ["finance"]
    assert "SELECT id, name FROM raw_users" in clean_sql
    assert "config" not in clean_sql


def test_parser_extracts_refs_and_sources() -> None:
    """Verify extracting model dependencies and source references."""
    parser = ModelParser()
    sql = """
    SELECT *
    FROM {{ ref('stg_customers') }}
    JOIN {{ source('crm_pg', 'contacts') }} ON 1=1
    JOIN {{ ref('ecommerce', 'stg_orders') }} ON 1=1
    """
    refs = parser.parse_refs(sql)
    sources = parser.parse_sources(sql)
    assert "stg_customers" in refs
    assert "stg_orders" in refs
    assert "crm_pg" in sources


def test_parser_compiles_macros() -> None:
    """Verify compiling {{ this }} and {{ ref(...) }} into standard SQL identifiers."""
    parser = ModelParser()
    sql = "SELECT id FROM {{ ref('stg_items') }} WHERE created_at < (SELECT MAX(created_at) FROM {{ this }})"
    compiled = parser.compile_sql(sql, model_name="fct_items")
    assert compiled == "SELECT id FROM stg_items WHERE created_at < (SELECT MAX(created_at) FROM fct_items)"


def test_parser_full_model_text() -> None:
    """Verify end-to-end parse_text produces complete ModelDefinition."""
    parser = ModelParser()
    sql = """
    {{ config(materialized='table') }}
    SELECT * FROM {{ ref('stg_users') }}
    """
    model = parser.parse_text("active_users", sql, project="analytics")
    assert model.name == "active_users"
    assert model.project == "analytics"
    assert model.config.materialized == MaterializationType.TABLE
    assert model.refs == ["stg_users"]
    assert model.compiled_sql == "SELECT * FROM stg_users"


def test_parser_extracts_header_docblock() -> None:
    """Verify extracting multi-line markdown docblock explaining the entire query."""
    parser = ModelParser()
    sql = """
    /*
    # Customer LTV Mart
    This query computes 12-month trailing LTV.
    - Excludes refunded transactions
    - Aggregates by customer tier
    */
    {{ config(materialized='table') }}
    SELECT customer_id, SUM(amount) FROM sales GROUP BY 1
    """
    model = parser.parse_text("customer_ltv", sql)
    assert "# Customer LTV Mart" in model.description
    assert "- Excludes refunded transactions" in model.description
    assert "/*" not in model.compiled_sql
    assert model.compiled_sql == "SELECT customer_id, SUM(amount) FROM sales GROUP BY 1"


def test_parser_extracts_multiline_config_description() -> None:
    """Verify extracting triple-quoted multi-line description from config."""
    parser = ModelParser()
    sql = '''
    {{ config(
        materialized='view',
        description="""
        Comprehensive multi-line explanation of the query:
        Step 1: Ingest
        Step 2: Cleanse
        """
    ) }}
    SELECT 1 AS num
    '''
    model = parser.parse_text("demo_model", sql)
    assert "Comprehensive multi-line explanation" in model.description
    assert "Step 1: Ingest" in model.description


