# SQL ETL Pipeline Authoring

`det` pipelines are declared in human-readable YAML files. Each pipeline consists of metadata, an optional catalog binding, and an ordered series of SQL transformation steps.

---

## 📄 Pipeline Specification Format

```yaml
version: 1
id: 550e8400-e29b-41d4-a716-446655440000
name: mart_customer_rfm_loyalty
folder: Analytics_Marts
catalog: sample_warehouse.yaml
description: Computes Recency, Frequency, and Monetary (RFM) customer loyalty tiers.

steps:
  - id: step-1
    name: customer_order_aggregates
    sql: |
      SELECT 
          customer_id,
          MAX(order_date) as last_order_date,
          COUNT(order_id) as total_orders,
          SUM(net_amount) as total_spend
      FROM raw_orders
      WHERE order_status != 'CANCELLED'
      GROUP BY customer_id
    destinations: []

  - id: step-2
    name: compute_rfm_scores
    sql: |
      SELECT 
          c.customer_id,
          c.first_name,
          c.email,
          agg.last_order_date,
          agg.total_orders,
          agg.total_spend,
          CASE 
              WHEN agg.total_spend > 1000 THEN 'Platinum'
              WHEN agg.total_spend > 500  THEN 'Gold'
              WHEN agg.total_spend > 100  THEN 'Silver'
              ELSE 'Bronze'
          END as loyalty_tier
      FROM raw_customers c
      JOIN customer_order_aggregates agg 
        ON c.customer_id = agg.customer_id
    destinations:
      - name: dw_rfm_segments_csv
        mode: overwrite
```

---

## 🔗 Step Interdependence & Dynamic Views

When step 1 executes, its output `DataFrame` is automatically registered into the DataFusion `SessionContext` under its step name (`customer_order_aggregates`).

Subsequent steps in the same pipeline can query previous step names just like any physical table, enabling clean, modular multi-stage DAG transformations without intermediate disk writes.

---

## 🎯 Destinations & Output Modes

Any step can declare one or more destinations referencing catalog connections:

```yaml
destinations:
  - name: dw_fct_orders_parquet
    mode: overwrite   # Options: overwrite, append
  - name: dw_daily_sales_delta
    mode: append
```

Supported destination formats include:
- **CSV**: Writes delimited text files with headers.
- **Parquet**: Writes columnar Parquet files with snappy/zstd compression.
- **Delta Lake**: Appends or overwrites ACID transaction log tables.

---

## 🔍 Pre-Flight Validation

Before executing in production, `det` validates:
1. SQL parsing and syntax conformance
2. Source table and intermediate view existence
3. Referenced column existence against catalog schemas
4. Output column mapping to destination schemas

