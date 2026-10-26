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
|  - Pre-flight DAG Compiler       - Quality Policy Engine     - Testing Runner     |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                                  DuckDB 2.0 Engine                                |
|  - Vectorized Multi-Threaded Execution    - Query Optimizer & Filter Pushdown     |
|  - In-Process Analytical SQL Processing   - Dynamic Extension Framework           |
|  - Temporary Cloud Secrets (S3/Azure/GCS) - Native Delta Lake & Parquet Scanners  |
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
|  CSV | Parquet | JSON | Excel | Delta Lake (Read/Write) | Iceberg | SQLite | PG | |
|  AWS S3 | Azure ADLS Gen2 | Google Cloud Storage | Microsoft Fabric OneLake       |
+-----------------------------------------------------------------------------------+
```

---

## 1. 🧩 Modularity

### Workspace Independence
A workspace is a structured directory on disk following a clean 4-folder layout:
- `catalog/`: Contains `connections.yaml` (the single configuration file defining connections, credentials, and schemas). Strictly uses absolute paths for all local file targets to ensure path stability across environments.
- `pipelines/`: Modular pipeline specifications and SQL models grouped into pipeline directories (e.g. `pipelines/<pipeline_name>/models/*.sql`).
- `data/`: Dedicated local data storage (Parquet, Delta, CSV, DuckDB).
- `extensions/`: Built-in and user-authored storage connector extensions.
- `.det/`: Internal runtime state, telemetry databases (`telemetry.duckdb` / JSONL), compiled artifacts, and session caches.

### Decoupled Data Contracts
Catalog connections specify strict schemas (column names, types, nullability, descriptions). Pipelines reference connection names rather than hardcoded connection strings, allowing environments (Dev, Staging, Prod) to swap catalogs effortlessly.

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
- `csv`, `parquet`, `json`, `ndjson`, `excel` (`openpyxl`)
- `delta_lake` (ACID transaction logs - high-throughput `delta_scan` reads and `write_deltalake` ACID exports in `append` and `replace` modes)
- `azure` (Azure Blob Storage / ADLS Gen2 `abfss://` with Service Principal and Connection String auth)
- `gcs` (Google Cloud Storage `gs://` with HMAC and Bearer Token secrets)
- `s3` (AWS S3, MinIO, Cloudflare R2 with access keys and session tokens)
- `onelake` (Microsoft Fabric OneLake lakehouse tables and direct ABFSS URIs)
- `iceberg`, `postgres`, `mysql`, `sqlite`, `mssql`

### Interoperable Multi-Source SQL
Because connectors register views into DuckDB's session, a single SQL query can join an Excel spreadsheet with a Delta Lake table and write to Parquet, Delta Lake, or PostgreSQL in a single pipeline.

---

| ⬅️ Previous Page | 🏠 Overview | Next Page ➡️ |
| :--- | :---: | ---: |
| [**← Quickstart & Installation**](Quickstart-&-Installation) | [**Wiki Index**](Home) | [**SQL ETL Pipeline Authoring ➔**](SQL-ETL-Pipeline-Authoring) |
