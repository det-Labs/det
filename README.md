# det (Data Engineering Tool)

[![PyPI Version](https://img.shields.io/pypi/v/det-core.svg?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/det-core/)
[![CI](https://github.com/det-Labs/det/actions/workflows/ci.yml/badge.svg)](https://github.com/det-Labs/det/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.14+](https://img.shields.io/badge/Python-3.14+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Engine: DuckDB 2.0](https://img.shields.io/badge/Engine-DuckDB%202.0-FFF000.svg?logo=duckdb&logoColor=black)](https://duckdb.org/)
[![In-Memory: Apache Arrow](https://img.shields.io/badge/In--Memory-Apache%20Arrow-E14434.svg)](https://arrow.apache.org/)
[![Architecture: Local--First](https://img.shields.io/badge/Architecture-Local--First-green.svg)](#)

> **det** is a lightweight, local-first SQL ETL orchestration framework and data transformation workspace powered by **DuckDB 2.0**.

`det` offers data engineers the familiar ergonomics of declarative SQL modeling—automatic dependency resolution, `{{ ref() }}` and `{{ source() }}` lineage, and schema testing—combined with an embedded vectorized analytical engine and a built-in zero-dependency Web IDE.

---

## 🚀 Key Highlights & Capabilities

- ⚡ **Embedded Vectorized Execution (DuckDB 2.0 & Arrow):**
  - High-throughput analytical SQL execution directly in-process.
  - Zero cloud serialization overhead, SIMD parallelism, and multi-threaded query execution for local and on-premises workloads.
- 🔌 **Unified Multi-Tier Catalog:**
  - **Relational Databases:** PostgreSQL, MySQL, SQLite, Microsoft SQL Server / Fabric SQL endpoints.
  - **Open Lakehouse Formats:** Delta Lake (read-only source scanner with time-travel snapshot querying), Apache Iceberg, Microsoft Fabric OneLake (`abfss://`).
  - **Object Storage & Flat Files:** AWS S3, Cloudflare R2, Parquet, CSV, JSON, and Excel (`.xlsx`).
- 🧩 **Declarative SQL Modeling & DAG Resolution:**
  - `{{ ref('model_name') }}`: Declare model lineage and automatically generate topological execution DAGs.
  - `{{ source('connection', 'target') }}`: Read directly from any catalog connection using vectorized scanners.
  - `{{ env_var('VAR_NAME', 'default_value') }}`: Substitute environment tokens at compilation time.
- 🛡️ **Resilient Data Quality & Row Quarantine:**
  - Declarative assertions: `not_null`, `unique`, `accepted_values`, `expression`, `relationships` (referential integrity), `row_count`, and `custom_sql`.
  - Non-blocking row quarantine: Isolate violating data rows into persistent quarantine sinks for audit and remediation without crashing downstream pipeline runs.
- 📊 **Granular Monitoring & Pluggable Telemetry:**
  - Track individual model execution stages: status, start timestamps, millisecond durations, rows processed, and error diagnostics.
  - Swappable storage sinks: Local DuckDB (`.det/telemetry.duckdb`), append-only flat-file JSONL (`.det/telemetry/`), or external database audit tables.
  - One-click run export to JSON for external log ingestion and auditing.
  - Built-in performance guard capping log queries to keep UI navigation responsive.
- 📚 **Self-Contained Interactive Documentation:**
  - Automatic column and schema introspection with live documentation editing.
  - Interactive Mermaid DAG lineage diagrams.
  - Static self-contained HTML portal export via `det docs generate`.
- 💻 **Dual Interface:**
  - Full headless CLI and Python SDK for headless automation and CI/CD.
  - Built-in, zero-dependency browser Web IDE (`det gui`).

---

## 🛠️ CLI Quickstart

### 1. Initialize a Workspace
```bash
det init my_pipeline
cd my_pipeline
```

### 2. Verify Catalog Connections
```bash
det catalog list
det catalog test
```

### 3. Execute Pipeline Models
```bash
det run
```

### 4. Run Data Quality Assertions
```bash
det test
```

### 5. Generate and Serve Documentation
```bash
det docs generate
```

### 6. Launch the Local Web IDE
```bash
det gui --port 8080
```
Open [http://localhost:8080](http://localhost:8080) to explore the visual DAG canvas, models, documentation portal, and execution telemetry.

---

## 🐍 Python SDK Example

```python
from pathlib import Path
from det import Workspace

# Open active workspace
ws = Workspace(Path("."))

# Test catalog connections
health = ws.test_catalog()
print("Catalog Health:", health)

# Execute topological pipeline DAG
report = ws.run()
print(f"Executed {report.total_models} models in {report.duration_ms:.1f}ms")

# Run data quality tests with automatic quarantine routing
test_suite = ws.test()
print(f"Passed: {test_suite.passed_count}, Failed: {test_suite.failed_count}")

# Generate interactive HTML documentation
docs_path = ws.generate_docs()
print("Documentation portal generated at:", docs_path)
```

---

## 🔮 Roadmap & Upcoming Features

We are actively developing the following enhancements:

- ✍️ **Intelligent SQL Editor Autocompletion & Language Server (LSP):**
  - **Context-Aware `{{ ref() }}` Completion:** Instant autocomplete suggestions for all model names defined across active pipelines.
  - **Catalog Source Suggestion:** Live autocompletion for `{{ source('connection', 'table') }}` referencing catalog items and mounted views.
  - **Column-Level Suggestions:** Schema-aware column autocompletion introspected from upstream models and catalog connections.
  - **In-Browser Syntax Validation:** Real-time SQL syntax highlighting, linting, and error hints within the Web IDE.
- 📦 **Pluggable Extension Ecosystem:** Dynamic third-party connector packaging and community plugins.
- ⚡ **Streaming Ingestion Adapters:** Incremental real-time micro-batch processing with DuckDB append-only appenders.

---

## 🧪 Running Tests

`det` includes a comprehensive automated test suite covering catalog mounting, DAG parsing, topological execution, quarantine routing, documentation extraction, and telemetry sinks:

```bash
pytest
```
*108 passing unit and integration tests.*

---

## 📦 Building Distribution Packages

```bash
python -m build
python -m twine check dist/*
```

---

## 📄 License & Attribution

Maintained by **Saurabh Rai** ([saurabhr2@gmail.com](mailto:saurabhr2@gmail.com)) and **[det-Labs](https://github.com/det-Labs)**.

Licensed under the **[MIT License](LICENSE)**.
