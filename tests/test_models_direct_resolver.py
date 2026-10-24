"""Tests for direct catalog connection resolution in raw SQL queries."""

from det.models.direct_resolver import DirectConnectionResolver


def test_resolver_detects_connection_in_from_and_join() -> None:
    """Verify detecting connections referenced in FROM and JOIN clauses."""
    resolver = DirectConnectionResolver()
    sql = """
    SELECT *
    FROM sales_csv
    JOIN prod_pg.public.customers ON sales_csv.cust_id = customers.id
    WHERE status = 'active'
    """
    known_connections = {"sales_csv", "prod_pg", "unrelated_db"}
    detected = resolver.resolve_connections(sql, known_connections=known_connections)
    assert detected == {"sales_csv", "prod_pg"}


def test_resolver_ignores_ctes_and_known_models() -> None:
    """Verify resolver excludes CTE aliases and other model names from connections."""
    resolver = DirectConnectionResolver()
    sql = """
    WITH regional_sales AS (
        SELECT * FROM raw_feed
    )
    SELECT *
    FROM regional_sales
    JOIN stg_orders ON 1=1
    JOIN crm_source ON 1=1
    """
    known_connections = {"regional_sales", "raw_feed", "crm_source"}
    known_models = {"stg_orders"}

    detected = resolver.resolve_connections(
        sql,
        known_connections=known_connections,
        known_models=known_models,
    )
    # regional_sales is a CTE, so it should be excluded even though it's in known_connections
    assert "regional_sales" not in detected
    assert "stg_orders" not in detected
    assert "raw_feed" in detected
    assert "crm_source" in detected

