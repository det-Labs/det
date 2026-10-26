# SQL ETL Pipeline Authoring

`det` pipelines are declared in human-readable YAML files. Each pipeline consists of metadata, an optional catalog binding, and an ordered series of SQL transformation models.

---

## 📄 Pipeline Specification Format

```yaml
version: 1
id: 550e8400-e29b-41d4-a716-446655440000
name: mart_customer_rfm_loyalty
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
      - name: dw_rfm_segments_delta
        mode: overwrite
```

---

## 🔗 Step Interdependence & In-Memory Views

When step 1 executes, its output view is automatically registered into the DuckDB session under its step name (`customer_order_aggregates`).

Subsequent steps in the same pipeline can query previous step names directly, enabling clean, modular multi-stage DAG transformations without writing intermediate files to disk.

---

## 🎯 Destinations & Output Modes

Any step can declare one or more destinations referencing catalog connections:

```yaml
destinations:
  - name: dw_fct_orders_parquet
    mode: overwrite   # Options: overwrite, append
  - name: dw_orders_delta
    mode: append      # Fully supported for Delta Lake and Parquet
  - name: dw_monthly_report_excel
    mode: overwrite
```

Supported destination formats include:
- **Delta Lake**: Full ACID write destination support via streaming Arrow RecordBatches into `_delta_log` and Parquet files in both `overwrite` (replace) and `append` modes.
- **Parquet**: Writes columnar Parquet files with compression.
- **CSV**: Writes delimited text files with headers.
- **JSON**: Writes structured JSON or NDJSON documents.
- **Excel**: Exports formatted `.xlsx` workbooks.
- **Relational Databases**: Mounts and writes to PostgreSQL, MySQL, and SQLite.
- **Cloud Lakehouses**: Direct writes to remote cloud endpoints (`s3://`, `abfss://`, `gs://`).

---

## 🛡️ Data Quality Audits & Row Quarantine

`det` includes native row-level quarantine capabilities:
- **Pre-flight & Post-flight Audits**: Validate `not_null`, `unique`, `accepted_values`, `expression`, and custom SQL rules.
- **Row-Level Quarantine**: Route violating rows to `_quarantine_<model>` sinks while allowing conforming rows to proceed downstream, preventing entire pipeline crashes due to isolated dirty records.

---

| ⬅️ Previous Page | 🏠 Overview | Next Page ➡️ |
| :--- | :---: | ---: |
| [**← Core Directives & Architecture**](Core-Directives-&-Architecture) | [**Wiki Index**](Home) | [**Cloud Lakehouse Connectors ➔**](Cloud-Lakehouse-Connectors) |
