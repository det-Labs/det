"""High-scale realistic demo dataset and multi-pipeline generator for det.

Features:
- 4 Multi-Format Datasets (46,000+ records in Parquet, CSV, JSON)
- 4 Catalog Connections grouped under 'sample_connections'
- Pipeline 1: 'retail_medallion' (15 models across Bronze, Silver, Gold with full docs, multi-joins, CTEs, & mixed default/custom assertions)
- Pipeline 2: 'export_analytics' (7 models demonstrating CSV, Excel, and Parquet exports with full docs & window CTEs)
"""

import json
from pathlib import Path
import shutil
from typing import Any
import duckdb
import yaml


def generate_demo_datasets(workspace_root: Path, use_remote: bool = False) -> dict[str, Path]:
    """Generate realistic sample datasets (46,000+ records) in workspace data/ folder."""
    data_dir = workspace_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "exports").mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(":memory:")
    paths: dict[str, Path] = {}

    # 1. Customers Dataset (5,000 rows in Parquet)
    cust_path = data_dir / "customers.parquet"
    con.execute(f"""
        COPY (
            SELECT 
                (1000 + i) AS customer_id,
                'Cust_' || (1000 + i) AS first_name,
                'Family_' || ((i * 37) % 500) AS last_name,
                'user_' || (1000 + i) || '@' || (CASE (i % 5)
                    WHEN 0 THEN 'gmail.com'
                    WHEN 1 THEN 'enterprise.com'
                    WHEN 2 THEN 'techcorp.io'
                    WHEN 3 THEN 'yahoo.com'
                    ELSE 'domain.org' END) AS email,
                (CASE (i % 5)
                    WHEN 0 THEN 'VIP'
                    WHEN 1 THEN 'PLATINUM'
                    WHEN 2 THEN 'GOLD'
                    WHEN 3 THEN 'SILVER'
                    ELSE 'BRONZE' END) AS loyalty_tier,
                (CASE (i % 7)
                    WHEN 0 THEN 'US'
                    WHEN 1 THEN 'UK'
                    WHEN 2 THEN 'DE'
                    WHEN 3 THEN 'FR'
                    WHEN 4 THEN 'CA'
                    WHEN 5 THEN 'AU'
                    ELSE 'JP' END) AS country,
                DATE '2023-01-01' + (i % 730)::INTEGER AS signup_date
            FROM generate_series(1, 5000) t(i)
        ) TO '{cust_path.as_posix()}' (FORMAT PARQUET)
    """)
    paths["customers"] = cust_path

    # 2. Sales Orders Dataset (25,000 rows in CSV)
    sales_path = data_dir / "sales_orders.csv"
    con.execute(f"""
        COPY (
            SELECT 
                'ORD-' || LPAD(CAST(i AS VARCHAR), 6, '0') AS order_id,
                (1000 + (i % 5000) + 1) AS customer_id,
                ((i * 13) % 1000 + 1) AS product_id,
                ((i % 7) + 1) AS quantity,
                ROUND(10.0 + ((i * 17) % 490), 2) AS unit_price,
                ROUND((CASE WHEN (i % 4 = 0) THEN 0.15 WHEN (i % 7 = 0) THEN 0.25 ELSE 0.0 END), 2) AS discount_pct,
                ROUND((((i % 7) + 1) * (10.0 + ((i * 17) % 490))) * 0.08, 2) AS tax_amount,
                (CASE (i % 10)
                    WHEN 0 THEN 'CANCELLED'
                    WHEN 1 THEN 'PROCESSING'
                    ELSE 'COMPLETED' END) AS order_status,
                (CASE (i % 4)
                    WHEN 0 THEN 'CREDIT_CARD'
                    WHEN 1 THEN 'PAYPAL'
                    WHEN 2 THEN 'APPLE_PAY'
                    ELSE 'BANK_TRANSFER' END) AS payment_method,
                TIMESTAMP '2023-06-01 00:00:00' + INTERVAL (i * 35) MINUTE AS order_timestamp
            FROM generate_series(1, 25000) t(i)
        ) TO '{sales_path.as_posix()}' (HEADER, DELIMITER ',')
    """)
    paths["sales_orders"] = sales_path

    # 3. Web Events Clickstream Dataset (15,000 rows in JSON)
    events_path = data_dir / "web_events.json"
    con.execute(f"""
        COPY (
            SELECT 
                'EVT-' || LPAD(CAST(i AS VARCHAR), 6, '0') AS event_id,
                'SESS-' || LPAD(CAST(((i * 7) % 4000 + 1) AS VARCHAR), 5, '0') AS session_id,
                (CASE WHEN (i % 5 = 0) THEN NULL ELSE (1000 + (i % 5000) + 1) END) AS user_id,
                (CASE (i % 4)
                    WHEN 0 THEN 'PAGE_VIEW'
                    WHEN 1 THEN 'ADD_TO_CART'
                    WHEN 2 THEN 'SEARCH'
                    ELSE 'CHECKOUT' END) AS event_type,
                (CASE (i % 4)
                    WHEN 0 THEN '/products/' || ((i * 13) % 1000 + 1)
                    WHEN 1 THEN '/cart'
                    WHEN 2 THEN '/search?q=deals'
                    ELSE '/checkout/success' END) AS page_url,
                (CASE (i % 3)
                    WHEN 0 THEN 'DESKTOP'
                    WHEN 1 THEN 'MOBILE'
                    ELSE 'TABLET' END) AS device_type,
                ((i * 11) % 300 + 5) AS dwell_time_seconds,
                (CASE (i % 5)
                    WHEN 0 THEN 'google'
                    WHEN 1 THEN 'newsletter'
                    WHEN 2 THEN 'organic'
                    WHEN 3 THEN 'facebook'
                    ELSE 'direct' END) AS utm_source,
                TIMESTAMP '2023-06-01 00:00:00' + INTERVAL (i * 42) MINUTE AS event_timestamp
            FROM generate_series(1, 15000) t(i)
        ) TO '{events_path.as_posix()}' (FORMAT JSON)
    """)
    paths["web_events"] = events_path

    # 4. Inventory Catalog Dataset (1,200 rows in CSV)
    inv_path = data_dir / "inventory.csv"
    con.execute(f"""
        COPY (
            SELECT 
                i AS product_id,
                'SKU-' || LPAD(CAST(i AS VARCHAR), 5, '0') AS sku,
                'Item ' || i AS product_name,
                (CASE (i % 5)
                    WHEN 0 THEN 'ELECTRONICS'
                    WHEN 1 THEN 'HARDWARE'
                    WHEN 2 THEN 'APPAREL'
                    WHEN 3 THEN 'HOME_GARDEN'
                    ELSE 'AUTOMOTIVE' END) AS category,
                ROUND(5.0 + ((i * 7) % 150), 2) AS unit_cost,
                ((i * 23) % 450) AS stock_quantity,
                50 AS reorder_threshold
            FROM generate_series(1, 1200) t(i)
        ) TO '{inv_path.as_posix()}' (HEADER, DELIMITER ',')
    """)
    paths["inventory"] = inv_path

    con.close()
    return paths


def generate_demo_connections(workspace_root: Path) -> Path:
    """Create standard connections catalog for demo datasets grouped under sample_connections."""
    cat_dir = workspace_root / "catalog"
    cat_dir.mkdir(parents=True, exist_ok=True)
    conn_file = cat_dir / "connections.yaml"

    config = {
        "connections": {
            "customers_data": {
                "type": "parquet",
                "tier": "entity",
                "options": {"path": "data/customers.parquet"},
                "description": "Master customer entity containing 5,000 vectorized profile records with loyalty brackets, demographic attributes, and registration dates.",
                "folder": "sample_connections",
            },
            "sales_orders_data": {
                "type": "csv",
                "tier": "entity",
                "options": {
                    "path": "data/sales_orders.csv",
                    "header": True,
                    "delimiter": ",",
                },
                "description": "Core transaction ledger containing 25,000 multi-channel retail orders with item quantities, price points, discounts, and fulfillment tracking.",
                "folder": "sample_connections",
            },
            "web_events_data": {
                "type": "json",
                "tier": "entity",
                "options": {"path": "data/web_events.json", "format": "auto"},
                "description": "High-velocity clickstream event log capturing 15,000 page views, search intents, cart additions, and semi-structured UTM campaign telemetry.",
                "folder": "sample_connections",
            },
            "inventory_data": {
                "type": "csv",
                "tier": "entity",
                "options": {
                    "path": "data/inventory.csv",
                    "header": True,
                    "delimiter": ",",
                },
                "description": "Warehouse product catalog spanning 1,200 active SKUs carrying unit costs, physical on-hand stock, and safety reorder thresholds.",
                "folder": "sample_connections",
            },
        }
    }

    conn_file.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return conn_file


def generate_demo_pipelines(workspace_root: Path) -> list[str]:
    """Create realistic sample pipelines inside projects/sample_pipelines/."""
    projects_dir = workspace_root / "projects"
    sample_dir = projects_dir / "sample_pipelines"

    # Clean legacy demo folders if they exist
    for legacy_name in [
        "ecommerce_analytics",
        "customer_segmentation",
        "executive_overview",
        "inventory_compliance",
    ]:
        legacy_dir = projects_dir / legacy_name
        if legacy_dir.exists():
            shutil.rmtree(legacy_dir, ignore_errors=True)

    if sample_dir.exists():
        for old_item in sample_dir.iterdir():
            if old_item.is_dir():
                shutil.rmtree(old_item, ignore_errors=True)
    sample_dir.mkdir(parents=True, exist_ok=True)

    created_projects: list[str] = []

    # =========================================================================
    # PIPELINE 1: retail_medallion (15 Models across Bronze, Silver, Gold)
    # =========================================================================
    medallion_proj = sample_dir / "retail_medallion"
    medallion_proj.mkdir(parents=True, exist_ok=True)
    (medallion_proj / "det_project.yaml").write_text("""name: retail_medallion
version: 1.0.0
description: "Full-scale enterprise retail data lakehouse implementing Bronze (raw ingestion & type normalization), Silver (cleansed conformed dimensions & enriched transaction ledgers), and Gold (Customer 360, financial rollups, marketing attribution, cohort retention, and inventory replenishment) medallion architecture layers."
""", encoding="utf-8")

    m_models = medallion_proj / "models"
    (m_models / "bronze").mkdir(parents=True, exist_ok=True)
    (m_models / "silver").mkdir(parents=True, exist_ok=True)
    (m_models / "gold").mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------
    # Bronze Layer (4 Models, Views, Ingestion & Conformance, Default Tests)
    # -------------------------------------------------------------
    (m_models / "bronze" / "bronze_customers.sql").write_text("""{{ config(
    materialized='view',
    description='Raw customer records ingested with type normalization and ingestion timestamps'
) }}

SELECT 
    CAST(customer_id AS BIGINT) AS customer_id,
    TRIM(first_name) AS first_name,
    TRIM(last_name) AS last_name,
    LOWER(TRIM(email)) AS email,
    UPPER(TRIM(loyalty_tier)) AS loyalty_tier,
    UPPER(TRIM(country)) AS country,
    CAST(signup_date AS DATE) AS signup_date,
    CURRENT_TIMESTAMP AS _ingested_at
FROM customers_data
WHERE customer_id IS NOT NULL
""", encoding="utf-8")

    (m_models / "bronze" / "bronze_sales_orders.sql").write_text("""{{ config(
    materialized='view',
    description='Raw sales order lines ingested from source CSV with quantity and price normalization'
) }}

SELECT 
    CAST(order_id AS VARCHAR) AS order_id,
    CAST(customer_id AS BIGINT) AS customer_id,
    CAST(product_id AS BIGINT) AS product_id,
    CAST(quantity AS INTEGER) AS quantity,
    CAST(unit_price AS DOUBLE) AS unit_price,
    CAST(discount_pct AS DOUBLE) AS discount_pct,
    CAST(tax_amount AS DOUBLE) AS tax_amount,
    UPPER(TRIM(order_status)) AS order_status,
    UPPER(TRIM(payment_method)) AS payment_method,
    CAST(order_timestamp AS TIMESTAMP) AS order_timestamp,
    CURRENT_TIMESTAMP AS _ingested_at
FROM sales_orders_data
WHERE order_id IS NOT NULL
""", encoding="utf-8")

    (m_models / "bronze" / "bronze_web_events.sql").write_text("""{{ config(
    materialized='view',
    description='Raw clickstream web telemetry events ingested from JSON streams'
) }}

SELECT 
    CAST(event_id AS VARCHAR) AS event_id,
    CAST(session_id AS VARCHAR) AS session_id,
    CAST(user_id AS BIGINT) AS user_id,
    UPPER(TRIM(event_type)) AS event_type,
    CAST(page_url AS VARCHAR) AS page_url,
    UPPER(TRIM(device_type)) AS device_type,
    CAST(dwell_time_seconds AS INTEGER) AS dwell_time_seconds,
    LOWER(TRIM(utm_source)) AS utm_source,
    CAST(event_timestamp AS TIMESTAMP) AS event_timestamp,
    CURRENT_TIMESTAMP AS _ingested_at
FROM web_events_data
WHERE event_id IS NOT NULL
""", encoding="utf-8")

    (m_models / "bronze" / "bronze_inventory.sql").write_text("""{{ config(
    materialized='view',
    description='Raw warehouse SKU stock levels and replenishment metadata from CSV'
) }}

SELECT 
    CAST(product_id AS BIGINT) AS product_id,
    UPPER(TRIM(sku)) AS sku,
    TRIM(product_name) AS product_name,
    UPPER(TRIM(category)) AS category,
    CAST(unit_cost AS DOUBLE) AS unit_cost,
    CAST(stock_quantity AS INTEGER) AS stock_quantity,
    CAST(reorder_threshold AS INTEGER) AS reorder_threshold,
    CURRENT_TIMESTAMP AS _ingested_at
FROM inventory_data
WHERE product_id IS NOT NULL
""", encoding="utf-8")

    # -------------------------------------------------------------
    # Silver Layer (6 Models, Tables, Multi-Joins & CTEs, Default + Custom Tests)
    # -------------------------------------------------------------
    (m_models / "silver" / "silver_customers.sql").write_text("""{{ config(
    materialized='table',
    description='Conformed customer dimension with standardized attributes, email domains, and tier rankings'
) }}

SELECT 
    customer_id,
    first_name,
    last_name,
    CONCAT(first_name, ' ', last_name) AS full_name,
    email,
    SPLIT_PART(email, '@', 2) AS email_domain,
    loyalty_tier,
    CASE 
        WHEN loyalty_tier = 'VIP' THEN 5
        WHEN loyalty_tier = 'PLATINUM' THEN 4
        WHEN loyalty_tier = 'GOLD' THEN 3
        WHEN loyalty_tier = 'SILVER' THEN 2
        ELSE 1 
    END AS tier_rank,
    country,
    signup_date,
    DATE_DIFF('day', signup_date, DATE '2026-06-01') AS account_age_days
FROM {{ ref('bronze_customers') }}
""", encoding="utf-8")

    (m_models / "silver" / "silver_orders.sql").write_text("""{{ config(
    materialized='table',
    description='Enriched order transaction lines with gross, discount, tax, net revenue, and fulfillment SLA flags'
) }}

SELECT 
    order_id,
    customer_id,
    product_id,
    quantity,
    unit_price,
    discount_pct,
    ROUND(quantity * unit_price, 2) AS gross_revenue_usd,
    ROUND(quantity * unit_price * discount_pct, 2) AS discount_amount_usd,
    ROUND(tax_amount, 2) AS tax_amount_usd,
    ROUND((quantity * unit_price * (1.0 - discount_pct)) + tax_amount, 2) AS net_revenue_usd,
    order_status,
    payment_method,
    order_timestamp,
    CAST(order_timestamp AS DATE) AS order_date,
    CASE 
        WHEN order_status = 'COMPLETED' THEN 'FULFILLED'
        WHEN order_status = 'PROCESSING' THEN 'IN_TRANSIT'
        WHEN order_status = 'CANCELLED' THEN 'CANCELLED'
        ELSE 'PENDING'
    END AS fulfillment_status
FROM {{ ref('bronze_sales_orders') }}
""", encoding="utf-8")

    (m_models / "silver" / "silver_web_sessions.sql").write_text("""{{ config(
    materialized='table',
    description='Sessionized clickstream activity aggregating duration, bounce flags, and traffic sources'
) }}

SELECT 
    session_id,
    MAX(COALESCE(user_id, 0)) AS user_id,
    MAX(device_type) AS device_type,
    MAX(utm_source) AS utm_source,
    MIN(event_timestamp) AS session_start_at,
    MAX(event_timestamp) AS session_end_at,
    COUNT(event_id) AS total_events,
    SUM(dwell_time_seconds) AS session_duration_seconds,
    CASE WHEN COUNT(event_id) <= 1 THEN 1 ELSE 0 END AS is_bounce,
    CASE WHEN SUM(CASE WHEN event_type = 'CHECKOUT' THEN 1 ELSE 0 END) > 0 THEN 1 ELSE 0 END AS has_checkout
FROM {{ ref('bronze_web_events') }}
GROUP BY session_id
""", encoding="utf-8")

    (m_models / "silver" / "silver_order_items_enhanced.sql").write_text("""{{ config(
    materialized='table',
    description='Order items 3-way joined with warehouse catalog and customer dimension carrying product categories, margins, and loyalty tiers'
) }}

SELECT 
    o.order_id,
    o.customer_id,
    c.full_name AS customer_name,
    c.loyalty_tier,
    o.product_id,
    i.sku,
    i.product_name,
    i.category,
    o.quantity,
    o.unit_price,
    i.unit_cost,
    o.gross_revenue_usd,
    ROUND(o.quantity * i.unit_cost, 2) AS total_cost_usd,
    ROUND(o.gross_revenue_usd - (o.quantity * i.unit_cost), 2) AS gross_profit_usd,
    CASE 
        WHEN o.gross_revenue_usd > 0 
        THEN ROUND((o.gross_revenue_usd - (o.quantity * i.unit_cost)) / o.gross_revenue_usd, 4)
        ELSE 0.0 
    END AS profit_margin_pct,
    o.order_date
FROM {{ ref('silver_orders') }} o
JOIN {{ ref('bronze_inventory') }} i ON o.product_id = i.product_id
JOIN {{ ref('silver_customers') }} c ON o.customer_id = c.customer_id
""", encoding="utf-8")

    (m_models / "silver" / "silver_inventory_health.sql").write_text("""{{ config(
    materialized='table',
    description='Warehouse SKU valuation and stock status classification based on safety thresholds'
) }}

SELECT 
    product_id,
    sku,
    product_name,
    category,
    unit_cost,
    stock_quantity,
    reorder_threshold,
    ROUND(stock_quantity * unit_cost, 2) AS total_carrying_value_usd,
    CASE 
        WHEN stock_quantity = 0 THEN 'OUT_OF_STOCK'
        WHEN stock_quantity <= reorder_threshold THEN 'CRITICAL'
        WHEN stock_quantity > reorder_threshold * 4 THEN 'OVERSTOCKED'
        ELSE 'HEALTHY'
    END AS stock_status,
    CASE 
        WHEN stock_quantity <= reorder_threshold THEN 1 
        ELSE 0 
    END AS reorder_flag
FROM {{ ref('bronze_inventory') }}
""", encoding="utf-8")

    (m_models / "silver" / "silver_customer_orders.sql").write_text("""{{ config(
    materialized='table',
    description='Customer order bridge aggregating lifetime order volumes, total expenditure, tenure dates, and web engagement via multi-CTE joins'
) }}

WITH customer_orders AS (
    SELECT 
        customer_id,
        COUNT(order_id) AS total_lifetime_orders,
        COALESCE(ROUND(SUM(gross_revenue_usd), 2), 0.0) AS lifetime_gross_spend_usd,
        COALESCE(ROUND(SUM(net_revenue_usd), 2), 0.0) AS lifetime_net_spend_usd,
        COALESCE(ROUND(AVG(net_revenue_usd), 2), 0.0) AS avg_order_value_usd,
        MIN(order_date) AS first_order_date,
        MAX(order_date) AS most_recent_order_date
    FROM {{ ref('silver_orders') }}
    GROUP BY customer_id
),
customer_sessions AS (
    SELECT 
        user_id AS customer_id,
        COUNT(DISTINCT session_id) AS total_web_sessions,
        SUM(session_duration_seconds) AS total_engagement_seconds
    FROM {{ ref('silver_web_sessions') }}
    WHERE user_id > 0
    GROUP BY user_id
)
SELECT 
    c.customer_id,
    c.full_name,
    c.email,
    c.loyalty_tier,
    c.country,
    COALESCE(o.total_lifetime_orders, 0) AS total_lifetime_orders,
    COALESCE(o.lifetime_gross_spend_usd, 0.0) AS lifetime_gross_spend_usd,
    COALESCE(o.lifetime_net_spend_usd, 0.0) AS lifetime_net_spend_usd,
    COALESCE(o.avg_order_value_usd, 0.0) AS avg_order_value_usd,
    o.first_order_date,
    o.most_recent_order_date,
    COALESCE(s.total_web_sessions, 0) AS total_web_sessions,
    COALESCE(s.total_engagement_seconds, 0) AS total_engagement_seconds
FROM {{ ref('silver_customers') }} c
LEFT JOIN customer_orders o ON c.customer_id = o.customer_id
LEFT JOIN customer_sessions s ON c.customer_id = s.customer_id
""", encoding="utf-8")

    # -------------------------------------------------------------
    # Gold Layer (5 Models, Tables, Multi-CTE Chains & Analytical Marts)
    # -------------------------------------------------------------
    (m_models / "gold" / "gold_customer_360.sql").write_text("""{{ config(
    materialized='table',
    description='Unified Customer 360 analytical mart with RFM segmentation, LTV ranking, and churn risk scoring'
) }}

WITH rfm_calc AS (
    SELECT 
        customer_id,
        full_name,
        email,
        loyalty_tier,
        country,
        total_lifetime_orders,
        lifetime_net_spend_usd,
        avg_order_value_usd,
        first_order_date,
        most_recent_order_date,
        COALESCE(DATE_DIFF('day', most_recent_order_date, DATE '2026-06-01'), 999) AS recency_days
    FROM {{ ref('silver_customer_orders') }}
),
quantiles AS (
    SELECT 
        *,
        NTILE(5) OVER (ORDER BY recency_days ASC) AS r_score,
        NTILE(5) OVER (ORDER BY total_lifetime_orders DESC) AS f_score,
        NTILE(5) OVER (ORDER BY lifetime_net_spend_usd DESC) AS m_score
    FROM rfm_calc
)
SELECT 
    customer_id,
    full_name,
    email,
    loyalty_tier,
    country,
    total_lifetime_orders,
    lifetime_net_spend_usd,
    avg_order_value_usd,
    recency_days,
    r_score,
    f_score,
    m_score,
    CASE 
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'CHAMPIONS'
        WHEN f_score >= 4 AND m_score >= 3 THEN 'LOYAL_CUSTOMERS'
        WHEN r_score <= 2 AND f_score >= 3 THEN 'AT_RISK'
        WHEN r_score <= 2 AND f_score <= 2 THEN 'HIBERNATING'
        ELSE 'POTENTIAL_LOYALISTS'
    END AS rfm_segment,
    ROUND(1.0 - (r_score / 5.0), 2) AS churn_risk_score
FROM quantiles
""", encoding="utf-8")

    (m_models / "gold" / "gold_daily_financial_kpis.sql").write_text("""{{ config(
    materialized='table',
    description='Daily executive finance ledger tracking revenue throughput, rolling 7-day averages, DoD growth, and discount leakage'
) }}

WITH daily_rollup AS (
    SELECT 
        order_date,
        COUNT(DISTINCT order_id) AS total_orders,
        COUNT(DISTINCT customer_id) AS unique_purchasing_customers,
        ROUND(SUM(gross_revenue_usd), 2) AS total_gross_revenue_usd,
        ROUND(SUM(discount_amount_usd), 2) AS total_discounts_usd,
        ROUND(SUM(tax_amount_usd), 2) AS total_tax_usd,
        ROUND(SUM(net_revenue_usd), 2) AS total_net_revenue_usd,
        ROUND(AVG(net_revenue_usd), 2) AS avg_order_value_usd
    FROM {{ ref('silver_orders') }}
    GROUP BY order_date
),
windowed_kpis AS (
    SELECT 
        order_date,
        total_orders,
        unique_purchasing_customers,
        total_gross_revenue_usd,
        total_discounts_usd,
        total_tax_usd,
        total_net_revenue_usd,
        avg_order_value_usd,
        ROUND(AVG(total_net_revenue_usd) OVER (ORDER BY order_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS rolling_7d_net_revenue_usd,
        ROUND(AVG(total_orders) OVER (ORDER BY order_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1) AS rolling_7d_orders,
        LAG(total_net_revenue_usd, 1) OVER (ORDER BY order_date) AS prev_day_net_revenue_usd
    FROM daily_rollup
)
SELECT 
    order_date,
    total_orders,
    unique_purchasing_customers,
    total_gross_revenue_usd,
    total_discounts_usd,
    total_tax_usd,
    total_net_revenue_usd,
    avg_order_value_usd,
    rolling_7d_net_revenue_usd,
    rolling_7d_orders,
    COALESCE(prev_day_net_revenue_usd, total_net_revenue_usd) AS prev_day_net_revenue_usd,
    CASE 
        WHEN prev_day_net_revenue_usd IS NOT NULL AND prev_day_net_revenue_usd > 0
        THEN ROUND(((total_net_revenue_usd - prev_day_net_revenue_usd) / prev_day_net_revenue_usd) * 100.0, 2)
        ELSE 0.0 
    END AS day_over_day_growth_pct,
    CASE 
        WHEN total_gross_revenue_usd > 0 
        THEN ROUND(total_discounts_usd / total_gross_revenue_usd, 4)
        ELSE 0.0 
    END AS effective_discount_rate
FROM windowed_kpis
ORDER BY order_date DESC
""", encoding="utf-8")

    (m_models / "gold" / "gold_channel_attribution.sql").write_text("""{{ config(
    materialized='table',
    description='Multi-touch marketing acquisition funnel tracking conversion rates, bounces, and attributed revenues by campaign and device'
) }}

WITH campaign_traffic AS (
    SELECT 
        utm_source,
        device_type,
        COUNT(DISTINCT session_id) AS total_sessions,
        COUNT(DISTINCT user_id) FILTER (WHERE user_id > 0) AS identified_visitors,
        SUM(is_bounce) AS bounce_count,
        SUM(session_duration_seconds) AS total_dwell_seconds
    FROM {{ ref('silver_web_sessions') }}
    GROUP BY utm_source, device_type
),
order_conversions AS (
    SELECT 
        s.utm_source,
        s.device_type,
        COUNT(DISTINCT o.order_id) AS attributed_orders,
        ROUND(SUM(o.net_revenue_usd), 2) AS attributed_revenue_usd
    FROM {{ ref('silver_web_sessions') }} s
    JOIN {{ ref('silver_orders') }} o 
      ON s.user_id = o.customer_id 
     AND CAST(s.session_start_at AS DATE) = o.order_date
    GROUP BY s.utm_source, s.device_type
)
SELECT 
    t.utm_source,
    t.device_type,
    t.total_sessions,
    t.identified_visitors,
    t.bounce_count,
    ROUND(t.bounce_count::DOUBLE / NULLIF(t.total_sessions, 0), 4) AS bounce_rate,
    COALESCE(c.attributed_orders, 0) AS attributed_orders,
    COALESCE(c.attributed_revenue_usd, 0.0) AS attributed_revenue_usd,
    ROUND(COALESCE(c.attributed_orders, 0)::DOUBLE / NULLIF(t.total_sessions, 0), 4) AS conversion_rate,
    COALESCE(ROUND(COALESCE(c.attributed_revenue_usd, 0.0) / NULLIF(c.attributed_orders, 0), 2), 0.0) AS revenue_per_order_usd
FROM campaign_traffic t
LEFT JOIN order_conversions c 
  ON t.utm_source = c.utm_source AND t.device_type = c.device_type
ORDER BY attributed_revenue_usd DESC, total_sessions DESC
""", encoding="utf-8")

    (m_models / "gold" / "gold_inventory_replenishment.sql").write_text("""{{ config(
    materialized='table',
    description='Supply chain replenishment priority schedule calculating procurement quantities and capital needs'
) }}

WITH category_summary AS (
    SELECT 
        category,
        COUNT(*) AS total_skus,
        SUM(CASE WHEN stock_status = 'CRITICAL' THEN 1 ELSE 0 END) AS critical_sku_count,
        SUM(CASE WHEN stock_status = 'OUT_OF_STOCK' THEN 1 ELSE 0 END) AS out_of_stock_sku_count,
        ROUND(SUM(total_carrying_value_usd), 2) AS current_carrying_value_usd,
        ROUND(SUM(CASE 
            WHEN stock_status IN ('CRITICAL', 'OUT_OF_STOCK') 
            THEN unit_cost * (reorder_threshold * 2) 
            ELSE 0 
        END), 2) AS replenishment_capital_required_usd
    FROM {{ ref('silver_inventory_health') }}
    GROUP BY category
)
SELECT 
    category,
    total_skus,
    critical_sku_count,
    out_of_stock_sku_count,
    current_carrying_value_usd,
    replenishment_capital_required_usd
FROM category_summary
ORDER BY replenishment_capital_required_usd DESC
""", encoding="utf-8")

    (m_models / "gold" / "gold_monthly_cohort_retention.sql").write_text("""{{ config(
    materialized='table',
    description='Monthly customer cohort retention matrix tracking user activity decay and repeat spending across 4 CTE stages'
) }}

WITH customer_cohorts AS (
    SELECT 
        customer_id,
        STRFTIME(signup_date, '%Y-%m') AS cohort_month
    FROM {{ ref('silver_customers') }}
),
order_months AS (
    SELECT 
        customer_id,
        STRFTIME(order_date, '%Y-%m') AS activity_month,
        net_revenue_usd
    FROM {{ ref('silver_orders') }}
),
joined_cohorts AS (
    SELECT 
        c.cohort_month,
        o.activity_month,
        COUNT(DISTINCT c.customer_id) AS active_customers,
        ROUND(SUM(o.net_revenue_usd), 2) AS cohort_revenue_usd
    FROM customer_cohorts c
    JOIN order_months o ON c.customer_id = o.customer_id
    GROUP BY c.cohort_month, o.activity_month
),
cohort_base AS (
    SELECT 
        cohort_month,
        COUNT(DISTINCT customer_id) AS base_customers
    FROM customer_cohorts
    GROUP BY cohort_month
)
SELECT 
    j.cohort_month,
    j.activity_month,
    b.base_customers,
    j.active_customers,
    ROUND((j.active_customers::DOUBLE / b.base_customers) * 100.0, 2) AS retention_rate_pct,
    j.cohort_revenue_usd
FROM joined_cohorts j
JOIN cohort_base b ON j.cohort_month = b.cohort_month
ORDER BY j.cohort_month, j.activity_month
""", encoding="utf-8")

    # Complete schema.yml documentation with every column described & assertions configured
    (m_models / "schema.yml").write_text("""version: 2
models:
  # ==========================================
  # BRONZE LAYER (Default Tests Only)
  # ==========================================
  - name: bronze_customers
    description: "Raw customer ingestion view with type casting and audit metadata"
    columns:
      - name: customer_id
        description: "Primary customer integer identifier"
        tests:
          - unique
          - not_null
      - name: first_name
        description: "Customer given name trimmed of trailing whitespace"
      - name: last_name
        description: "Customer family name"
      - name: email
        description: "Normalized lowercase customer email address"
        tests:
          - not_null
      - name: loyalty_tier
        description: "Raw loyalty tier classification code"
        tests:
          - not_null
      - name: country
        description: "Customer residence ISO country abbreviation"
        tests:
          - not_null
      - name: signup_date
        description: "Account creation calendar date"
        tests:
          - not_null
      - name: _ingested_at
        description: "Timestamp when raw record was ingested by pipeline"

  - name: bronze_sales_orders
    description: "Raw retail sales order lines ledger ingested from source CSV"
    columns:
      - name: order_id
        description: "Unique sales order alphanumeric identifier"
        tests:
          - unique
          - not_null
      - name: customer_id
        description: "Foreign key referencing customer entity"
        tests:
          - not_null
      - name: product_id
        description: "Foreign key referencing product SKU in catalog"
        tests:
          - not_null
      - name: quantity
        description: "Units purchased in transaction"
        tests:
          - not_null
      - name: unit_price
        description: "Base catalogue unit price in USD"
        tests:
          - not_null
      - name: discount_pct
        description: "Promotional discount rate between 0.0 and 1.0"
        tests:
          - not_null
      - name: tax_amount
        description: "Calculated state and local sales tax amount"
        tests:
          - not_null
      - name: order_status
        description: "Fulfillment lifecycle state code"
        tests:
          - not_null
          - accepted_values:
              values: ['COMPLETED', 'PROCESSING', 'CANCELLED']
      - name: payment_method
        description: "Checkout tender type used for payment"
        tests:
          - not_null
      - name: order_timestamp
        description: "UTC point in time when transaction was captured"
        tests:
          - not_null
      - name: _ingested_at
        description: "Ingestion timestamp metadata"

  - name: bronze_web_events
    description: "Raw clickstream telemetry tracking online shopper interactions"
    columns:
      - name: event_id
        description: "Unique event identifier"
        tests:
          - unique
          - not_null
      - name: session_id
        description: "Browser cookie session grouping tag"
        tests:
          - not_null
      - name: user_id
        description: "Authenticated customer ID or null for guest"
      - name: event_type
        description: "Shopper interaction classification"
        tests:
          - not_null
          - accepted_values:
              values: ['PAGE_VIEW', 'ADD_TO_CART', 'SEARCH', 'CHECKOUT']
      - name: page_url
        description: "Relative web pathname visited"
        tests:
          - not_null
      - name: device_type
        description: "Hardware form factor of client"
        tests:
          - not_null
      - name: dwell_time_seconds
        description: "Seconds spent on target page before navigation"
        tests:
          - not_null
      - name: utm_source
        description: "Attribution campaign referral source"
        tests:
          - not_null
      - name: event_timestamp
        description: "Point in time event occurred"
        tests:
          - not_null
      - name: _ingested_at
        description: "Ingestion timestamp metadata"

  - name: bronze_inventory
    description: "Raw warehouse catalog carrying SKU specifications and stock levels"
    columns:
      - name: product_id
        description: "Unique product catalog integer identifier"
        tests:
          - unique
          - not_null
      - name: sku
        description: "Standardized warehouse stock keeping unit code"
        tests:
          - not_null
      - name: product_name
        description: "Commercial product display title"
        tests:
          - not_null
      - name: category
        description: "Department merchandise grouping"
        tests:
          - not_null
      - name: unit_cost
        description: "Procurement cost per unit in USD"
        tests:
          - not_null
      - name: stock_quantity
        description: "Current on-hand physical warehouse stock"
        tests:
          - not_null
      - name: reorder_threshold
        description: "Safety stock trigger boundary"
        tests:
          - not_null
      - name: _ingested_at
        description: "Ingestion timestamp metadata"

  # ==========================================
  # SILVER LAYER (Default + Custom Expression Tests)
  # ==========================================
  - name: silver_customers
    description: "Cleansed and standardized customer dimension with email domains and age"
    columns:
      - name: customer_id
        description: "Conformed customer unique identifier"
        tests:
          - unique
          - not_null
      - name: first_name
        description: "Given first name"
      - name: last_name
        description: "Family surname"
      - name: full_name
        description: "Concatenated full customer name"
        tests:
          - not_null
      - name: email
        description: "Primary contact email"
        tests:
          - not_null
      - name: email_domain
        description: "Extracted corporate or webmail domain"
        tests:
          - not_null
      - name: loyalty_tier
        description: "Standardized customer membership bracket"
        tests:
          - not_null
          - accepted_values:
              values: ['VIP', 'PLATINUM', 'GOLD', 'SILVER', 'BRONZE']
      - name: tier_rank
        description: "Numeric tier ranking from 1 (Bronze) to 5 (VIP)"
        tests:
          - not_null
          - expression: "tier_rank >= 1 AND tier_rank <= 5"
      - name: country
        description: "Geographic country of account origin"
        tests:
          - not_null
      - name: signup_date
        description: "Customer onboarding date"
        tests:
          - not_null
      - name: account_age_days
        description: "Account tenure measured in elapsed days"
        tests:
          - not_null
          - expression: "account_age_days >= 0"

  - name: silver_orders
    description: "Enriched order lines with calculated gross/net revenues and fulfillment SLAs"
    columns:
      - name: order_id
        description: "Order primary identifier"
        tests:
          - unique
          - not_null
      - name: customer_id
        description: "Customer key"
        tests:
          - not_null
      - name: product_id
        description: "Product catalog item key"
        tests:
          - not_null
      - name: quantity
        description: "Units purchased"
        tests:
          - not_null
          - expression: "quantity > 0"
      - name: unit_price
        description: "Item unit price"
        tests:
          - not_null
          - expression: "unit_price >= 0"
      - name: discount_pct
        description: "Discount factor"
        tests:
          - not_null
      - name: gross_revenue_usd
        description: "Pre-discount gross transaction value"
        tests:
          - not_null
          - expression: "gross_revenue_usd >= 0"
      - name: discount_amount_usd
        description: "Monetary discount deducted from gross revenue"
        tests:
          - not_null
          - expression: "discount_amount_usd >= 0"
      - name: tax_amount_usd
        description: "Applicable sales tax amount"
        tests:
          - not_null
          - expression: "tax_amount_usd >= 0"
      - name: net_revenue_usd
        description: "Post-discount invoice revenue including taxes"
        tests:
          - not_null
          - expression: "net_revenue_usd >= 0"
      - name: order_status
        description: "Transaction processing status"
        tests:
          - not_null
      - name: payment_method
        description: "Tender method"
        tests:
          - not_null
      - name: order_timestamp
        description: "Timestamp of sale"
        tests:
          - not_null
      - name: order_date
        description: "Calendar date of sale"
        tests:
          - not_null
      - name: fulfillment_status
        description: "Operational delivery lifecycle status"
        tests:
          - not_null
          - accepted_values:
              values: ['FULFILLED', 'IN_TRANSIT', 'CANCELLED', 'PENDING']

  - name: silver_web_sessions
    description: "Sessionized visitor clickstream behavior and engagement metrics"
    columns:
      - name: session_id
        description: "Unique web browsing session key"
        tests:
          - unique
          - not_null
      - name: user_id
        description: "User identifier or 0 for guest"
      - name: device_type
        description: "Hardware form factor"
        tests:
          - not_null
      - name: utm_source
        description: "Inbound campaign referral source"
        tests:
          - not_null
      - name: session_start_at
        description: "First event timestamp in session"
        tests:
          - not_null
      - name: session_end_at
        description: "Final event timestamp in session"
        tests:
          - not_null
      - name: total_events
        description: "Count of interactions in session"
        tests:
          - not_null
          - expression: "total_events > 0"
      - name: session_duration_seconds
        description: "Total elapsed dwell time in seconds"
        tests:
          - not_null
          - expression: "session_duration_seconds >= 0"
      - name: is_bounce
        description: "Flag indicating single-page bounce session (1=yes, 0=no)"
        tests:
          - not_null
          - accepted_values:
              values: [0, 1]
      - name: has_checkout
        description: "Flag indicating completed checkout interaction"
        tests:
          - not_null
          - accepted_values:
              values: [0, 1]

  - name: silver_order_items_enhanced
    description: "Order lines 3-way joined with inventory unit costs and customer dimensions for margin analytics"
    columns:
      - name: order_id
        description: "Order transaction key"
        tests:
          - not_null
      - name: customer_id
        description: "Purchasing customer key"
        tests:
          - not_null
      - name: customer_name
        description: "Full customer name from conformed dimension"
        tests:
          - not_null
      - name: loyalty_tier
        description: "Customer loyalty tier bracket"
        tests:
          - not_null
      - name: product_id
        description: "Catalog item key"
        tests:
          - not_null
      - name: sku
        description: "Stock keeping unit code"
        tests:
          - not_null
      - name: product_name
        description: "Catalog merchandise name"
        tests:
          - not_null
      - name: category
        description: "Product merchandise department"
        tests:
          - not_null
      - name: quantity
        description: "Purchased units"
        tests:
          - not_null
          - expression: "quantity > 0"
      - name: unit_price
        description: "Item selling price"
        tests:
          - not_null
          - expression: "unit_price >= 0"
      - name: unit_cost
        description: "Warehouse procurement unit cost"
        tests:
          - not_null
          - expression: "unit_cost >= 0"
      - name: gross_revenue_usd
        description: "Gross transaction amount"
        tests:
          - not_null
          - expression: "gross_revenue_usd >= 0"
      - name: total_cost_usd
        description: "Cost of goods sold (COGS)"
        tests:
          - not_null
          - expression: "total_cost_usd >= 0"
      - name: gross_profit_usd
        description: "Revenue minus unit procurement cost"
        tests:
          - not_null
      - name: profit_margin_pct
        description: "Profit margin ratio"
        tests:
          - not_null
          - expression: "profit_margin_pct <= 1.0"
      - name: order_date
        description: "Date transaction occurred"
        tests:
          - not_null

  - name: silver_inventory_health
    description: "Warehouse stock valuation and safety reorder status evaluation"
    columns:
      - name: product_id
        description: "Product inventory key"
        tests:
          - unique
          - not_null
      - name: sku
        description: "Warehouse SKU tag"
        tests:
          - not_null
      - name: product_name
        description: "Product title"
        tests:
          - not_null
      - name: category
        description: "Merchandise line"
        tests:
          - not_null
      - name: unit_cost
        description: "Per-unit cost basis"
        tests:
          - not_null
          - expression: "unit_cost >= 0"
      - name: stock_quantity
        description: "Available physical units"
        tests:
          - not_null
          - expression: "stock_quantity >= 0"
      - name: reorder_threshold
        description: "Trigger threshold for restocking"
        tests:
          - not_null
          - expression: "reorder_threshold >= 0"
      - name: total_carrying_value_usd
        description: "Total capital tied up in warehouse stock"
        tests:
          - not_null
          - expression: "total_carrying_value_usd >= 0"
      - name: stock_status
        description: "Stock sufficiency status"
        tests:
          - not_null
          - accepted_values:
              values: ['HEALTHY', 'CRITICAL', 'OUT_OF_STOCK', 'OVERSTOCKED']
      - name: reorder_flag
        description: "Binary restocking alert flag"
        tests:
          - not_null
          - accepted_values:
              values: [0, 1]

  - name: silver_customer_orders
    description: "Customer lifetime sales summary and multi-channel engagement bridge"
    columns:
      - name: customer_id
        description: "Customer unique key"
        tests:
          - unique
          - not_null
      - name: full_name
        description: "Customer display name"
        tests:
          - not_null
      - name: email
        description: "Primary email address"
        tests:
          - not_null
      - name: loyalty_tier
        description: "Membership bracket"
        tests:
          - not_null
      - name: country
        description: "Country code"
        tests:
          - not_null
      - name: total_lifetime_orders
        description: "Historical count of orders placed"
        tests:
          - not_null
          - expression: "total_lifetime_orders >= 0"
      - name: lifetime_gross_spend_usd
        description: "Gross lifetime billings"
        tests:
          - not_null
          - expression: "lifetime_gross_spend_usd >= 0"
      - name: lifetime_net_spend_usd
        description: "Cumulative net revenue generated by customer"
        tests:
          - not_null
          - expression: "lifetime_net_spend_usd >= 0"
      - name: avg_order_value_usd
        description: "Average customer spend per basket"
        tests:
          - not_null
          - expression: "avg_order_value_usd >= 0"
      - name: first_order_date
        description: "Initial purchase date"
      - name: most_recent_order_date
        description: "Latest transaction date"
      - name: total_web_sessions
        description: "Total recorded website browsing sessions"
        tests:
          - not_null
          - expression: "total_web_sessions >= 0"
      - name: total_engagement_seconds
        description: "Cumulative website dwell time in seconds"
        tests:
          - not_null
          - expression: "total_engagement_seconds >= 0"

  # ==========================================
  # GOLD LAYER (Advanced Analytical Marts & Strict Rules)
  # ==========================================
  - name: gold_customer_360
    description: "Consolidated Customer 360 mart with RFM segmentation and churn prediction"
    columns:
      - name: customer_id
        description: "Customer dimensional key"
        tests:
          - unique
          - not_null
      - name: full_name
        description: "Full customer name"
        tests:
          - not_null
      - name: email
        description: "Customer email"
        tests:
          - not_null
      - name: loyalty_tier
        description: "Loyalty program tier"
        tests:
          - not_null
      - name: country
        description: "ISO country code"
        tests:
          - not_null
      - name: total_lifetime_orders
        description: "Lifetime order count"
        tests:
          - not_null
          - expression: "total_lifetime_orders >= 0"
      - name: lifetime_net_spend_usd
        description: "Total net lifetime value"
        tests:
          - not_null
          - expression: "lifetime_net_spend_usd >= 0"
      - name: avg_order_value_usd
        description: "Average transaction size"
        tests:
          - not_null
          - expression: "avg_order_value_usd >= 0"
      - name: recency_days
        description: "Days elapsed since most recent transaction"
        tests:
          - not_null
          - expression: "recency_days >= 0"
      - name: r_score
        description: "Recency quantile rank (1 to 5)"
        tests:
          - not_null
          - expression: "r_score >= 1 AND r_score <= 5"
      - name: f_score
        description: "Frequency quantile rank (1 to 5)"
        tests:
          - not_null
          - expression: "f_score >= 1 AND f_score <= 5"
      - name: m_score
        description: "Monetary quantile rank (1 to 5)"
        tests:
          - not_null
          - expression: "m_score >= 1 AND m_score <= 5"
      - name: rfm_segment
        description: "Behavioral RFM cohort grouping"
        tests:
          - not_null
          - accepted_values:
              values: ['CHAMPIONS', 'LOYAL_CUSTOMERS', 'AT_RISK', 'HIBERNATING', 'POTENTIAL_LOYALISTS']
      - name: churn_risk_score
        description: "Algorithmic churn probability between 0.0 and 1.0"
        tests:
          - not_null
          - expression: "churn_risk_score >= 0.0 AND churn_risk_score <= 1.0"

  - name: gold_daily_financial_kpis
    description: "Executive daily ledger tracking top-line revenues, rolling 7-day metrics, and discount erosion"
    columns:
      - name: order_date
        description: "Calendar accounting date"
        tests:
          - unique
          - not_null
      - name: total_orders
        description: "Total orders fulfilled"
        tests:
          - not_null
          - expression: "total_orders >= 0"
      - name: unique_purchasing_customers
        description: "Count of unique buyers"
        tests:
          - not_null
          - expression: "unique_purchasing_customers >= 0"
      - name: total_gross_revenue_usd
        description: "Total invoice gross revenue"
        tests:
          - not_null
          - expression: "total_gross_revenue_usd >= 0"
      - name: total_discounts_usd
        description: "Total discounts absorbed"
        tests:
          - not_null
          - expression: "total_discounts_usd >= 0"
      - name: total_tax_usd
        description: "Total sales taxes collected"
        tests:
          - not_null
          - expression: "total_tax_usd >= 0"
      - name: total_net_revenue_usd
        description: "Total invoice net revenue"
        tests:
          - not_null
          - expression: "total_net_revenue_usd >= 0"
      - name: avg_order_value_usd
        description: "Average net ticket value"
        tests:
          - not_null
          - expression: "avg_order_value_usd >= 0"
      - name: rolling_7d_net_revenue_usd
        description: "7-day rolling window average net revenue"
        tests:
          - not_null
          - expression: "rolling_7d_net_revenue_usd >= 0"
      - name: rolling_7d_orders
        description: "7-day rolling window average order count"
        tests:
          - not_null
          - expression: "rolling_7d_orders >= 0"
      - name: prev_day_net_revenue_usd
        description: "Prior calendar day net revenue for velocity comparisons"
        tests:
          - not_null
          - expression: "prev_day_net_revenue_usd >= 0"
      - name: day_over_day_growth_pct
        description: "Day-over-day growth rate percentage"
        tests:
          - not_null
      - name: effective_discount_rate
        description: "Ratio of discounts given to gross revenue"
        tests:
          - not_null
          - expression: "effective_discount_rate >= 0.0 AND effective_discount_rate <= 1.0"

  - name: gold_channel_attribution
    description: "Marketing funnel attribution tracking conversion efficiency by channel"
    columns:
      - name: utm_source
        description: "Traffic acquisition source"
        tests:
          - not_null
      - name: device_type
        description: "Client device form factor"
        tests:
          - not_null
      - name: total_sessions
        description: "Total recorded visitor sessions"
        tests:
          - not_null
          - expression: "total_sessions > 0"
      - name: identified_visitors
        description: "Visitors logged into registered accounts"
        tests:
          - not_null
          - expression: "identified_visitors >= 0"
      - name: bounce_count
        description: "Sessions that bounced on entry page"
        tests:
          - not_null
          - expression: "bounce_count >= 0"
      - name: bounce_rate
        description: "Ratio of bounce sessions to total sessions"
        tests:
          - not_null
          - expression: "bounce_rate >= 0.0 AND bounce_rate <= 1.0"
      - name: attributed_orders
        description: "Transactions linked to referral source"
        tests:
          - not_null
          - expression: "attributed_orders >= 0"
      - name: attributed_revenue_usd
        description: "Net revenue attributed to marketing channel"
        tests:
          - not_null
          - expression: "attributed_revenue_usd >= 0"
      - name: conversion_rate
        description: "Percentage of sessions converting to purchases"
        tests:
          - not_null
          - expression: "conversion_rate >= 0.0 AND conversion_rate <= 1.0"
      - name: revenue_per_order_usd
        description: "Average net dollar yield per attributed order"
        tests:
          - not_null
          - expression: "revenue_per_order_usd >= 0"

  - name: gold_inventory_replenishment
    description: "Actionable replenishment order schedule and procurement capital allocation"
    columns:
      - name: category
        description: "Product category"
        tests:
          - unique
          - not_null
      - name: total_skus
        description: "Number of active catalogue items"
        tests:
          - not_null
          - expression: "total_skus > 0"
      - name: critical_sku_count
        description: "Count of items below safety stock"
        tests:
          - not_null
          - expression: "critical_sku_count >= 0"
      - name: out_of_stock_sku_count
        description: "Count of depleted inventory items"
        tests:
          - not_null
          - expression: "out_of_stock_sku_count >= 0"
      - name: current_carrying_value_usd
        description: "Current on-hand dollar valuation"
        tests:
          - not_null
          - expression: "current_carrying_value_usd >= 0"
      - name: replenishment_capital_required_usd
        description: "Estimated procurement capital needed"
        tests:
          - not_null
          - expression: "replenishment_capital_required_usd >= 0"

  - name: gold_monthly_cohort_retention
    description: "Customer cohort retention decay matrix across post-signup calendar months"
    columns:
      - name: cohort_month
        description: "Signup vintage month (YYYY-MM)"
        tests:
          - not_null
      - name: activity_month
        description: "Transaction activity month (YYYY-MM)"
        tests:
          - not_null
      - name: base_customers
        description: "Initial registered cohort size"
        tests:
          - not_null
          - expression: "base_customers > 0"
      - name: active_customers
        description: "Cohort members transacting in activity month"
        tests:
          - not_null
          - expression: "active_customers > 0"
      - name: retention_rate_pct
        description: "Cohort retention rate percentage"
        tests:
          - not_null
          - expression: "retention_rate_pct >= 0.0 AND retention_rate_pct <= 100.0"
      - name: cohort_revenue_usd
        description: "Net sales dollars generated by cohort in activity month"
        tests:
          - not_null
          - expression: "cohort_revenue_usd >= 0"
""", encoding="utf-8")
    created_projects.append("retail_medallion")

    # =========================================================================
    # PIPELINE 2: export_analytics (7 Models, Multi-Destination CSV/Excel/Parquet)
    # =========================================================================
    export_proj = sample_dir / "export_analytics"
    export_proj.mkdir(parents=True, exist_ok=True)
    (export_proj / "det_project.yaml").write_text("""name: export_analytics
version: 1.0.0
description: "Operational analytics and multi-destination data distribution pipeline exporting enriched analytical datasets to Parquet, CSV, and Excel (.xlsx) workbooks for downstream consumption across BI, finance, and plant operations."
""", encoding="utf-8")

    e_models = export_proj / "models"
    (e_models / "staging").mkdir(parents=True, exist_ok=True)
    (e_models / "marts").mkdir(parents=True, exist_ok=True)

    # Staging Models (2 Models, Views)
    (e_models / "staging" / "stg_export_sales.sql").write_text("""{{ config(
    materialized='view',
    description='Clean sales orders ready for export reconciliation'
) }}

SELECT 
    order_id,
    customer_id,
    product_id,
    quantity,
    unit_price,
    ROUND(quantity * unit_price, 2) AS gross_sales_usd,
    ROUND((quantity * unit_price * discount_pct), 2) AS discount_usd,
    ROUND(tax_amount, 2) AS tax_usd,
    ROUND((quantity * unit_price * (1.0 - discount_pct)) + tax_amount, 2) AS net_sales_usd,
    payment_method,
    order_status,
    CAST(order_timestamp AS DATE) AS order_date
FROM sales_orders_data
WHERE order_id IS NOT NULL
""", encoding="utf-8")

    (e_models / "staging" / "stg_export_inventory.sql").write_text("""{{ config(
    materialized='view',
    description='Clean warehouse stock ready for operations export'
) }}

SELECT 
    product_id,
    sku,
    product_name,
    category,
    unit_cost,
    stock_quantity,
    reorder_threshold,
    ROUND(stock_quantity * unit_cost, 2) AS carrying_value_usd,
    CASE WHEN stock_quantity <= reorder_threshold THEN 'REORDER_NOW' ELSE 'OK' END AS audit_status
FROM inventory_data
WHERE product_id IS NOT NULL
""", encoding="utf-8")

    # Export Marts (5 Models with Destinations)
    # 1. Parquet Export
    (e_models / "marts" / "rpt_sales_summary_parquet.sql").write_text("""{{ config(
    materialized='table',
    destinations=['data/exports/sales_summary.parquet'],
    description='High-efficiency Parquet lake export summarizing sales by payment method'
) }}

SELECT 
    payment_method,
    COUNT(order_id) AS total_orders,
    ROUND(SUM(gross_sales_usd), 2) AS total_gross_sales_usd,
    ROUND(SUM(net_sales_usd), 2) AS total_net_sales_usd,
    ROUND(AVG(net_sales_usd), 2) AS avg_ticket_usd
FROM {{ ref('stg_export_sales') }}
WHERE order_status = 'COMPLETED'
GROUP BY payment_method
""", encoding="utf-8")

    # 2. CSV Export
    (e_models / "marts" / "rpt_finance_reconciliation_csv.sql").write_text("""{{ config(
    materialized='table',
    destinations=['data/exports/finance_reconciliation.csv'],
    description='Standard CSV export for corporate ERP finance ledger reconciliation'
) }}

SELECT 
    order_date,
    COUNT(order_id) AS total_transactions,
    ROUND(SUM(gross_sales_usd), 2) AS gross_billed_usd,
    ROUND(SUM(discount_usd), 2) AS discounts_absorbed_usd,
    ROUND(SUM(tax_usd), 2) AS tax_collected_usd,
    ROUND(SUM(net_sales_usd), 2) AS net_receivables_usd
FROM {{ ref('stg_export_sales') }}
WHERE order_status = 'COMPLETED'
GROUP BY order_date
ORDER BY order_date DESC
""", encoding="utf-8")

    # 3. Excel Export (.xlsx)
    (e_models / "marts" / "rpt_inventory_audit_excel.sql").write_text("""{{ config(
    materialized='table',
    destinations=['data/exports/inventory_audit.xlsx'],
    description='Formatted Excel spreadsheet export for warehouse operations managers'
) }}

SELECT 
    category,
    COUNT(product_id) AS total_skus,
    SUM(stock_quantity) AS total_units_in_warehouse,
    ROUND(SUM(carrying_value_usd), 2) AS total_carrying_value_usd,
    SUM(CASE WHEN audit_status = 'REORDER_NOW' THEN 1 ELSE 0 END) AS items_requiring_reorder
FROM {{ ref('stg_export_inventory') }}
GROUP BY category
ORDER BY total_carrying_value_usd DESC
""", encoding="utf-8")

    # 4. Multi-Destination Export (Triple Destination: Parquet + CSV + Excel!)
    (e_models / "marts" / "rpt_executive_flash_multi.sql").write_text("""{{ config(
    materialized='table',
    destinations=[
        'data/exports/executive_flash.parquet',
        'data/exports/executive_flash.csv',
        'data/exports/executive_flash.xlsx'
    ],
    description='Executive flash report simultaneously published to Parquet, CSV, and Excel workbooks'
) }}

WITH sales_metrics AS (
    SELECT 
        COUNT(DISTINCT order_id) AS total_orders_fulfilled,
        COUNT(DISTINCT customer_id) AS active_customer_count,
        ROUND(SUM(gross_sales_usd), 2) AS total_gross_usd,
        ROUND(SUM(discount_usd), 2) AS total_discounts_usd,
        ROUND(SUM(net_sales_usd), 2) AS total_net_revenue_usd,
        ROUND(AVG(net_sales_usd), 2) AS average_order_value_usd
    FROM {{ ref('stg_export_sales') }}
    WHERE order_status = 'COMPLETED'
),
inventory_metrics AS (
    SELECT 
        COUNT(DISTINCT product_id) AS total_catalog_skus,
        SUM(stock_quantity) AS total_units_in_stock,
        ROUND(SUM(carrying_value_usd), 2) AS total_inventory_valuation_usd,
        SUM(CASE WHEN audit_status = 'REORDER_NOW' THEN 1 ELSE 0 END) AS skus_at_risk
    FROM {{ ref('stg_export_inventory') }}
)
SELECT 
    'Global Operations' AS sales_territory,
    s.total_orders_fulfilled,
    s.active_customer_count,
    s.total_gross_usd,
    s.total_discounts_usd,
    s.total_net_revenue_usd,
    s.average_order_value_usd,
    i.total_catalog_skus,
    i.total_units_in_stock,
    i.total_inventory_valuation_usd,
    i.skus_at_risk
FROM sales_metrics s
CROSS JOIN inventory_metrics i
""", encoding="utf-8")

    # 5. Dual Destination Export (Parquet + CSV)
    (e_models / "marts" / "rpt_weekly_marketing_kpis.sql").write_text("""{{ config(
    materialized='table',
    destinations=[
        'data/exports/weekly_marketing_kpis.parquet',
        'data/exports/weekly_marketing_kpis.csv'
    ],
    description='Weekly customer acquisition throughput published to Parquet and CSV'
) }}

WITH weekly_sales AS (
    SELECT 
        DATE_TRUNC('week', order_date) AS sales_week,
        COUNT(DISTINCT customer_id) AS unique_buyers,
        COUNT(order_id) AS order_volume,
        ROUND(SUM(net_sales_usd), 2) AS total_weekly_revenue_usd
    FROM {{ ref('stg_export_sales') }}
    WHERE order_status = 'COMPLETED'
    GROUP BY DATE_TRUNC('week', order_date)
),
windowed_weeks AS (
    SELECT 
        sales_week,
        unique_buyers,
        order_volume,
        total_weekly_revenue_usd,
        ROUND(total_weekly_revenue_usd / NULLIF(unique_buyers, 0), 2) AS avg_spend_per_customer,
        LAG(total_weekly_revenue_usd, 1) OVER (ORDER BY sales_week) AS prior_week_revenue_usd
    FROM weekly_sales
)
SELECT 
    sales_week,
    unique_buyers,
    order_volume,
    total_weekly_revenue_usd,
    avg_spend_per_customer,
    COALESCE(prior_week_revenue_usd, total_weekly_revenue_usd) AS prior_week_revenue_usd,
    CASE 
        WHEN prior_week_revenue_usd IS NOT NULL AND prior_week_revenue_usd > 0
        THEN ROUND(((total_weekly_revenue_usd - prior_week_revenue_usd) / prior_week_revenue_usd) * 100.0, 2)
        ELSE 0.0 
    END AS week_over_week_growth_pct
FROM windowed_weeks
ORDER BY sales_week DESC
""", encoding="utf-8")

    # Schema documentation for export_analytics
    (e_models / "schema.yml").write_text("""version: 2
models:
  - name: stg_export_sales
    description: "Normalized sales transactions for export reporting"
    columns:
      - name: order_id
        description: "Unique transaction identifier"
        tests:
          - unique
          - not_null
      - name: customer_id
        description: "Customer identifier"
        tests:
          - not_null
      - name: product_id
        description: "Product SKU identifier"
        tests:
          - not_null
      - name: quantity
        description: "Purchased quantity"
        tests:
          - not_null
          - expression: "quantity > 0"
      - name: unit_price
        description: "Unit price in USD"
        tests:
          - not_null
          - expression: "unit_price >= 0"
      - name: gross_sales_usd
        description: "Gross revenue before discounts"
        tests:
          - not_null
          - expression: "gross_sales_usd >= 0"
      - name: discount_usd
        description: "Total discounts applied"
        tests:
          - not_null
          - expression: "discount_usd >= 0"
      - name: tax_usd
        description: "Sales tax captured"
        tests:
          - not_null
          - expression: "tax_usd >= 0"
      - name: net_sales_usd
        description: "Net revenue after discounts including taxes"
        tests:
          - not_null
          - expression: "net_sales_usd >= 0"
      - name: payment_method
        description: "Payment channel"
        tests:
          - not_null
      - name: order_status
        description: "Lifecycle status code"
        tests:
          - not_null
      - name: order_date
        description: "Accounting calendar date"
        tests:
          - not_null

  - name: stg_export_inventory
    description: "Normalized warehouse inventory for export reporting"
    columns:
      - name: product_id
        description: "Primary product catalog key"
        tests:
          - unique
          - not_null
      - name: sku
        description: "Stock keeping unit code"
        tests:
          - not_null
      - name: product_name
        description: "Merchandise title"
        tests:
          - not_null
      - name: category
        description: "Merchandise department"
        tests:
          - not_null
      - name: unit_cost
        description: "Cost per unit in USD"
        tests:
          - not_null
          - expression: "unit_cost >= 0"
      - name: stock_quantity
        description: "On-hand unit quantity"
        tests:
          - not_null
          - expression: "stock_quantity >= 0"
      - name: reorder_threshold
        description: "Safety reorder threshold"
        tests:
          - not_null
          - expression: "reorder_threshold >= 0"
      - name: carrying_value_usd
        description: "Capital inventory valuation"
        tests:
          - not_null
          - expression: "carrying_value_usd >= 0"
      - name: audit_status
        description: "Replenishment urgency status code"
        tests:
          - not_null
          - accepted_values:
              values: ['REORDER_NOW', 'OK']

  - name: rpt_sales_summary_parquet
    description: "Parquet export of sales volume and ticket averages by payment method"
    columns:
      - name: payment_method
        description: "Payment channel"
        tests:
          - unique
          - not_null
      - name: total_orders
        description: "Number of completed orders"
        tests:
          - not_null
          - expression: "total_orders > 0"
      - name: total_gross_sales_usd
        description: "Total invoice gross billings"
        tests:
          - not_null
          - expression: "total_gross_sales_usd > 0"
      - name: total_net_sales_usd
        description: "Total invoice net revenue"
        tests:
          - not_null
          - expression: "total_net_sales_usd > 0"
      - name: avg_ticket_usd
        description: "Average revenue per order"
        tests:
          - not_null
          - expression: "avg_ticket_usd > 0"

  - name: rpt_finance_reconciliation_csv
    description: "CSV export for finance and ERP general ledger reconciliation"
    columns:
      - name: order_date
        description: "Transaction accounting date"
        tests:
          - unique
          - not_null
      - name: total_transactions
        description: "Completed transactions count"
        tests:
          - not_null
          - expression: "total_transactions > 0"
      - name: gross_billed_usd
        description: "Gross billings total"
        tests:
          - not_null
          - expression: "gross_billed_usd >= 0"
      - name: discounts_absorbed_usd
        description: "Discount absorption total"
        tests:
          - not_null
          - expression: "discounts_absorbed_usd >= 0"
      - name: tax_collected_usd
        description: "Sales taxes collected"
        tests:
          - not_null
          - expression: "tax_collected_usd >= 0"
      - name: net_receivables_usd
        description: "Net cash receivables"
        tests:
          - not_null
          - expression: "net_receivables_usd >= 0"

  - name: rpt_inventory_audit_excel
    description: "Excel workbook (.xlsx) export for warehouse logistics and plant managers"
    columns:
      - name: category
        description: "Merchandise category"
        tests:
          - unique
          - not_null
      - name: total_skus
        description: "Active SKU count"
        tests:
          - not_null
          - expression: "total_skus > 0"
      - name: total_units_in_warehouse
        description: "Physical unit count in stock"
        tests:
          - not_null
          - expression: "total_units_in_warehouse >= 0"
      - name: total_carrying_value_usd
        description: "Dollar valuation of inventory holdings"
        tests:
          - not_null
          - expression: "total_carrying_value_usd >= 0"
      - name: items_requiring_reorder
        description: "Count of SKUs at or below safety stock"
        tests:
          - not_null
          - expression: "items_requiring_reorder >= 0"

  - name: rpt_executive_flash_multi
    description: "Multi-destination export (Parquet, CSV, Excel) summarizing top-line executive flash KPIs"
    columns:
      - name: sales_territory
        description: "Geographic sales region scope"
        tests:
          - not_null
      - name: total_orders_fulfilled
        description: "Total fulfilled order count"
        tests:
          - not_null
          - expression: "total_orders_fulfilled >= 0"
      - name: active_customer_count
        description: "Active purchasing customers"
        tests:
          - not_null
          - expression: "active_customer_count >= 0"
      - name: total_gross_usd
        description: "Total gross billings"
        tests:
          - not_null
          - expression: "total_gross_usd >= 0"
      - name: total_discounts_usd
        description: "Total discounts absorbed"
        tests:
          - not_null
          - expression: "total_discounts_usd >= 0"
      - name: total_net_revenue_usd
        description: "Total company net revenue"
        tests:
          - not_null
          - expression: "total_net_revenue_usd >= 0"
      - name: average_order_value_usd
        description: "Average order ticket size"
        tests:
          - not_null
          - expression: "average_order_value_usd >= 0"
      - name: total_catalog_skus
        description: "Total active product SKUs in catalog"
        tests:
          - not_null
          - expression: "total_catalog_skus > 0"
      - name: total_units_in_stock
        description: "Warehouse stock units on hand"
        tests:
          - not_null
          - expression: "total_units_in_stock >= 0"
      - name: total_inventory_valuation_usd
        description: "Total inventory capital valuation"
        tests:
          - not_null
          - expression: "total_inventory_valuation_usd >= 0"
      - name: skus_at_risk
        description: "Number of SKUs at or below reorder threshold"
        tests:
          - not_null
          - expression: "skus_at_risk >= 0"

  - name: rpt_weekly_marketing_kpis
    description: "Dual destination export (Parquet and CSV) tracking weekly acquisition velocity and WoW growth"
    columns:
      - name: sales_week
        description: "Beginning timestamp of sales week"
        tests:
          - not_null
      - name: unique_buyers
        description: "Unique purchasing customers within week"
        tests:
          - not_null
          - expression: "unique_buyers > 0"
      - name: order_volume
        description: "Total weekly order transaction volume"
        tests:
          - not_null
          - expression: "order_volume > 0"
      - name: total_weekly_revenue_usd
        description: "Total revenue for the week"
        tests:
          - not_null
          - expression: "total_weekly_revenue_usd >= 0"
      - name: avg_spend_per_customer
        description: "Weekly average ticket yield per buyer"
        tests:
          - not_null
          - expression: "avg_spend_per_customer >= 0"
      - name: prior_week_revenue_usd
        description: "Preceding calendar week revenue"
        tests:
          - not_null
          - expression: "prior_week_revenue_usd >= 0"
      - name: week_over_week_growth_pct
        description: "Percentage growth in sales vs preceding week"
        tests:
          - not_null
""", encoding="utf-8")
    created_projects.append("export_analytics")

    return created_projects


def setup_demo_workspace(workspace_root: Path, use_remote: bool = False) -> dict[str, Any]:
    """Execute complete demo environment setup: datasets, connections, and sample pipelines."""
    data_paths = generate_demo_datasets(workspace_root, use_remote=use_remote)
    conn_path = generate_demo_connections(workspace_root)
    pipeline_names = generate_demo_pipelines(workspace_root)
    return {
        "status": "ok",
        "datasets": [str(p) for p in data_paths.values()],
        "connections": str(conn_path),
        "pipelines": pipeline_names,
    }
