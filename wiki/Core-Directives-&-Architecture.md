# Core Directives & Architecture

`det` is designed to provide high-performance, modular, and developer-friendly SQL analytics and ETL execution without unnecessary infrastructure complexity. It strictly enforces three architectural directives: **Modularity**, **Performance**, and **Extensibility**.

```
+-----------------------------------------------------------------------------------+
|                                 det Web IDE & CLI                                 |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                        det Workspace & Orchestration Engine                       |
|  - Multi-tier Catalog (YAML)     - DAG Pipeline Resolver     - Telemetry Sinks    |
|  - Pre-flight SQL Validator      - Row Quarantine Engine     - Testing Runner     |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                                  DuckDB 2.0 Engine                                |
|  - Vectorized Multi-Threaded Execution    - Query Optimizer & Filter Pushdown     |
|  - In-Process Analytical SQL Processing   - Dynamic Extension Framework           |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                              Apache Arrow In-Memory Model                         |
|  - Zero-Copy RecordBatches                - Columnar In-Memory Interchange        |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                            Heterogeneous Storage Sinks Layer                      |
|  CSV | Parquet | JSON | XML | Excel | Delta Lake | Iceberg | SQLite | PG | MySQL    |
+-----------------------------------------------------------------------------------+
```

---

## 1. 🧩 Modularity

### Workspace Independence
A workspace is a structured directory on disk containing:
- `catalog/`: YAML files defining connections, secrets references, and column schemas.
- `projects/`: Modular pipeline model specifications grouped into domain projects.
- `extensions/`: Built-in and user-authored storage connector extensions.
- `.det/`: Telemetry databases (`telemetry.duckdb`), quarantine files, and run logs.

### Decoupled Data Contracts
Catalog connections specify strict schemas (column names, types, nullability, descriptions). Pipelines reference connection names rather than hardcoded file paths or connection strings, allowing environments (Dev, Staging, Prod) to swap catalogs effortlessly.

---

## 2. ⚡ Performance

### DuckDB 2.0 Vectorized Execution
`det` embeds DuckDB 2.0—a fast vectorized SQL analytical engine:
- **Vectorized SIMD processing**: Vector operations process thousands of rows per CPU instruction.
- **Multi-threaded execution**: Joins, aggregations, and window functions run concurrently across all available CPU cores.
- **Pushdown optimization**: Filter predicates (`WHERE amount > 100`) and column projections (`SELECT id, name`) are pushed directly down to the file and database scanners.

### Zero-Copy Arrow Tables
All internal intermediate query steps transfer data using Apache Arrow columnar memory without serializing to Python objects.

---

## 3. 🔌 Extensibility

### Universal Connector Extensions
Any storage technology can be integrated into `det` by registering a connector definition and a scan/sink implementation. Built-in connectors include:
- `csv`, `parquet`, `json`, `ndjson`, `xml`, `excel` (`openpyxl`)
- `delta_lake` (ACID transaction logs - read-only source scanner)
- `iceberg`, `postgres`, `mysql`, `sqlite`, `s3` (`httpfs`)

### Interoperable Multi-Source SQL
Because connectors register views into DuckDB's session, a single SQL query can join an Excel spreadsheet with a Delta Lake table and write to Parquet or PostgreSQL in a single pipeline.

---

| ⬅️ Previous Page | 🏠 Overview | Next Page ➡️ |
| :--- | :---: | ---: |
| [**← Quickstart & Installation**](Quickstart-&-Installation) | [**Wiki Index**](Home) | [**SQL ETL Pipeline Authoring ➔**](SQL-ETL-Pipeline-Authoring) |
