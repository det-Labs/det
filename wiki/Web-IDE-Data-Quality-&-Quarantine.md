# Web IDE: Data Quality & Quarantine

Data quality is a first-class citizen in `det`. The Web IDE provides visual controls to author assertion contracts, run automated tests across pipeline stages, and audit quarantined records in real time.

---

## 🛡️ Defining Visual Quality Assertions

Quality checks can be defined at both the column level and the model level directly within the Web IDE or via standard `schema.yml` contracts.

![Data Quality Assertions](images/04_assertions.png)

### Built-in Column Assertions

| Assertion | Description | Example Rule |
| :--- | :--- | :--- |
| `not_null` | Asserts column contains zero `NULL` or missing values. | `customer_id` must not be null |
| `unique` | Asserts every value in the column or compound key is unique. | `order_id` uniqueness check |
| `accepted_values` | Validates values belong to a defined whitelist. | `status IN ('PENDING', 'COMPLETED', 'CANCELLED')` |
| `expression` | Arbitrary SQL boolean condition evaluated per row. | `net_amount >= 0.0` or `discount_pct <= 1.0` |

---

## 🧪 Interactive Test Execution

Clicking the **Test** button in the pipeline ribbon executes all assertions defined across the DAG:
* **Real-Time Badge Updates**: DAG nodes turn green (`✓ 13 pass`) or red upon completion.
* **Detailed Assertions Table**: Displays assertion name, target column, test type, severity level (`error` vs `warn`), rows passed, rows failing, and execution latency.
* **In-Memory Speed**: Powered by vectorized DuckDB scans, hundreds of assertions execute in single-digit milliseconds.

---

## 🚫 Non-Blocking Row Quarantine

Traditional ETL tools abort the entire data pipeline when a data quality validation fails. In enterprise workflows, a single invalid record should not stop millions of valid transactions from reaching downstream analytics.

`det` solves this with **Non-Blocking Row Quarantine**:

```
Raw Input Data ──────► [Quality Validation] ───┬──► Compliant Rows ──► Silver / Gold Tables
                                               │
                                               └──► Violating Rows ──► Quarantine Sink (.parquet / .db)
```

### Configuring Quarantine in YAML

In your model's `schema.yml`, simply specify `quarantine: true` on any assertion:

```yaml
version: 2
models:
  - name: silver_orders
    columns:
      - name: net_amount
        tests:
          - expression: "net_amount >= 0.0"
            severity: error
            quarantine: true
            quarantine_table: orders_negative_amount_quarantine
```

When `silver_orders` executes:
1. Valid rows with `net_amount >= 0.0` pass directly into the clean silver table.
2. Violating rows (`net_amount < 0.0`) are automatically segregated and written to the quarantine sink along with error metadata.
3. Upstream and downstream models proceed uninterrupted.

---

## 🔍 Auditing Quarantined Rows

In the Web IDE **Monitoring** tab, open the **Quarantine Explorer** to:
* View a live count of total quarantined records.
* Inspect quarantined rows in a tabular data grid.
* Review exact validation violation rules and timestamps.
* Export quarantined datasets for root-cause analysis with source data providers.

---

| ⬅️ Previous Page | 🏠 Overview | Next Page ➡️ |
| :--- | :---: | ---: |
| [**← Web IDE: Pipelines & DAG Studio**](Web-IDE-Pipelines-&-DAG-Studio) | [**Wiki Index**](Home) | [**Web IDE: Catalog & Lakehouse Connections ➔**](Web-IDE-Catalog-&-Lakehouse-Connections) |
