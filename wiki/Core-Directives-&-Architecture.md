# Core Directives & Architecture

`det` was built from the ground up to address the bloat, complexity, and resource overhead of traditional data engineering tooling. It strictly enforces three architectural directives: **Modularity**, **Performance**, and **Extensibility**.

```
+-----------------------------------------------------------------------------------+
|                                     det Web IDE & CLI                             |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                           det Workspace & Orchestration Engine                     |
|  - Catalog Store (YAML)         - Pipeline Store (YAML)     - Monitoring Store    |
|  - Pre-flight SQL Validator     - Docs Generator            - Runner Dispatcher   |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                               Apache DataFusion Engine                            |
|  - Vectorized Multi-Threaded Execution    - Query Planner & Optimizer             |
|  - Filter & Projection Pushdown           - Standard SQL & Dialect Extensions    |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                              Apache Arrow In-Memory Model                         |
|  - Columnar RecordBatches                 - Zero-Copy Memory Transfers            |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                               Pluggable Storage Layer                             |
|  CSV | Parquet | JSON | NDJSON | XML | Excel (openpyxl/fastexcel) | Delta Lake   |
+-----------------------------------------------------------------------------------+
```

---

## 1. 🧩 Modularity

### Workspace Independence
A workspace is simply a directory on disk. It contains:
- `catalog/`: YAML files defining connections, secrets references, and column contracts.
- `pipelines/`: Modular YAML pipeline specifications grouped into business domain folders.
- `logs/`: Structured JSON telemetry logs for every execution run.
- `documentation/`: Static HTML and Markdown documentation generated automatically.

### Decoupled Data Contracts
Catalog connections specify strict schemas (column names, types, nullability, descriptions). Pipelines reference connection names rather than hardcoded file paths or connection strings, allowing environments (Dev, Staging, Prod) to swap catalogs effortlessly.

---

## 2. ⚡ Performance

### Apache DataFusion Execution
Rather than relying on pure Python interpreters or spinning up a multi-node Spark cluster for local workflows, `det` embeds Apache DataFusion—an industrial-grade SQL query engine written in Rust:
- **Vectorized SIMD processing**: Vector instructions process thousands of rows per CPU cycle.
- **Multi-threaded task scheduling**: Complex joins and aggregations execute concurrently across all available CPU cores.
- **Pushdown optimization**: Filter predicates (`WHERE amount > 100`) and column projections (`SELECT id, name`) are pushed directly down to the file reader, reading only matching bytes from disk.

### Zero-Copy Arrow Tables
All internal intermediate query steps transfer data using Apache Arrow `RecordBatch` streams without serializing to Python objects or dictionaries.

---

## 3. 🔌 Extensibility

### Universal Connector API
Any storage technology can be integrated into `det` by registering a connector definition and a scan/sink implementation. Built-in connectors include:
- `csv`: Delimited text files with lazy DataFusion scanning
- `parquet`: Columnar format with dictionary encoding and statistics
- `json` / `ndjson`: Semi-structured document streams
- `xml`: Structured XML parsed into relational Arrow batches
- `excel`: Multi-sheet Excel `.xlsx` workbooks
- `delta`: Delta Lake transaction log (`_delta_log`) and ACID time-travel tables

### Interoperable Multi-Source SQL
Because all connectors register views into DataFusion's `SessionContext`, a single SQL query can join an Excel spreadsheet with a Delta Lake table and output to Parquet:

```sql
SELECT 
    c.customer_id,
    c.first_name,
    t.monthly_target_usd,
    sum(o.net_amount) as total_spent
FROM raw_customers c
JOIN raw_store_targets t ON c.city = t.region
JOIN fct_orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.first_name, t.monthly_target_usd;
```
