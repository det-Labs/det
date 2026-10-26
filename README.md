# det (Data Engineering Tool)

[![PyPI Version](https://img.shields.io/pypi/v/det-core.svg?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/det-core/)
[![CI](https://github.com/det-Labs/det/actions/workflows/ci.yml/badge.svg)](https://github.com/det-Labs/det/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.14+](https://img.shields.io/badge/Python-3.14+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Engine: DuckDB 2.0](https://img.shields.io/badge/Engine-DuckDB%202.0-FFF000.svg?logo=duckdb&logoColor=black)](https://duckdb.org/)
[![In-Memory: Apache Arrow](https://img.shields.io/badge/In--Memory-Apache%20Arrow-E14434.svg)](https://arrow.apache.org/)
[![Architecture: Local--First](https://img.shields.io/badge/Architecture-Local--First-green.svg)](#)

> **det** is a lightweight, local-first SQL ETL orchestration framework and data transformation workspace powered by **DuckDB 2.0**.

`det` offers data engineers the familiar ergonomics of declarative SQL modeling—automatic dependency resolution, `{{ ref() }}` and `{{ source() }}` lineage, schema testing, and execution monitoring—combined with an embedded vectorized analytical engine and a built-in zero-dependency Web IDE.

---

## 📁 Workspace Architecture

Every `det` workspace follows a clean, standardized 4-directory structure:

```
my_workspace/
├── catalog/              # Single connections.yaml defining data sources with absolute paths
│   └── connections.yaml
├── pipelines/            # Pipeline definitions and SQL models
│   └── retail_medallion/
│       ├── det_project.yaml
│       └── models/
│           ├── bronze/
│           ├── silver/
│           ├── gold/
│           └── schema.yml
├── data/                 # Local data storage (Parquet, Delta, CSV, DuckDB)
├── extensions/           # Optional custom storage connectors and plugins
└── .det/                 # Internal runtime state, telemetry databases, and session caches
```

> [!IMPORTANT]
> To eliminate path resolution errors across different execution contexts and working directories, `catalog/connections.yaml` strictly uses absolute paths for all local data file locations, and `connections.yaml` is the single source of truth loaded from `catalog/`.

---

## 🚀 Key Highlights & Capabilities

- ⚡ **Embedded Vectorized Execution (DuckDB 2.0 & Arrow):**
  - High-throughput analytical SQL execution directly in-process.
  - Zero cloud serialization overhead, SIMD parallelism, and multi-threaded query execution for local and on-premises workloads.
- 🔌 **Unified Multi-Tier Catalog:**
  - **Relational Databases:** PostgreSQL, MySQL, SQLite, Microsoft SQL Server / Fabric SQL endpoints.
  - **Open Lakehouse Formats:** Delta Lake (vectorized `delta_scan` reads and ACID `deltalake` writes in append and overwrite modes), Apache Iceberg, Microsoft Fabric OneLake (`abfss://`).
  - **Multi-Cloud Object Storage & Flat Files:** AWS S3, Google Cloud Storage (GCS), Azure Blob / ADLS Gen2, Cloudflare R2, MinIO, Parquet, CSV, JSON, and Excel (`.xlsx`).
- 🧩 **Declarative SQL Modeling & DAG Resolution:**
  - `{{ ref('model_name') }}`: Declare model lineage and automatically generate topological execution DAGs.
  - `{{ source('connection', 'target') }}`: Read directly from any catalog connection using vectorized scanners.
  - `{{ env_var('VAR_NAME', 'default_value') }}`: Substitute environment tokens at compilation time.
- 🛡️ **Resilient Data Quality & Policy Enforcement:**
  - Declarative assertions: `not_null`, `unique`, `accepted_values`, `expression`, `relationships`, `row_count`, and `custom_sql`.
  - **Three Clean Enforcement Policies:**
    - `error`: Immediately halts pipeline execution upon validation failure.
    - `warning` (`warn`): Completes pipeline processing normally and logs total violating row counts in telemetry without bloating log storage.
    - `drop`: Drops violating rows in-flight (`EXCEPT ALL`) and processes remaining compliant rows uninterrupted.
- 📊 **Granular Monitoring & Pluggable Telemetry:**
  - Track individual model execution stages: status, start timestamps, millisecond durations, rows processed, and error diagnostics.
  - **Inclusive Priority Window:** Recent runs are prioritized up to the query limit (default 20) with a 30-day temporal window, guaranteeing infrequent pipelines remain visible.
  - Swappable storage sinks: Local DuckDB (`.det/telemetry.duckdb`), append-only flat-file JSONL (`.det/telemetry/`), or external database audit tables.
  - Full CLI management: `det monitor runs`, `det monitor run <id>`, `det monitor audits`, `det monitor status`, and `det monitor clean`.
- 📚 **Self-Contained Interactive Documentation:**
  - Automatic column and schema introspection with live documentation editing.
  - Interactive Mermaid DAG lineage diagrams.
  - Static self-contained HTML portal export via `det docs generate` and `det docs export`.
- 💻 **Dual Interface:**
  - Unified headless CLI and Python SDK for automation and CI/CD.
  - Built-in, zero-dependency browser Web IDE (`det gui`).

---

## 🛠️ CLI Quickstart

### 1. Initialize a Workspace
```bash
mkdir my_workspace && cd my_workspace
det init
```

### 2. Verify Catalog Connections
```bash
# List connections declared in catalog/connections.yaml
det catalog list

# Test network, authentication, and read latency
det catalog test

# Preview top records or inspect full connection metadata
det catalog display [connection_name] --limit 10
det catalog details [connection_name]
```

### 3. Compile & Execute Pipeline Models
```bash
# Compile and validate DAG dependencies
det compile [pipeline_name]

# Execute models in dependency order
det run [pipeline_name] --threads 4
```

### 4. Run Data Quality Assertions
```bash
# Evaluate quality assertions against error/warning/drop policies
det test [pipeline_name]
```

### 5. Inspect Execution Monitoring & Telemetry
```bash
# List recent pipeline executions (inclusive priority over 30 days)
det monitor runs [pipeline_name]

# Inspect a specific run with stage durations and error diagnostics
det monitor run <run_id>

# Review test audit results
det monitor audits [pipeline_name]

# Check telemetry sink status and disk usage
det monitor status

# Clean old telemetry records
det monitor clean --days 60 --yes
```

### 6. Generate and Export Living Documentation
```bash
# Generate self-contained HTML documentation
det docs generate [pipeline_name]

# Open documentation in browser or serve locally
det docs open [pipeline_name] --serve

# Export documentation bundle to a custom target
det docs export [pipeline_name] --output /absolute/path/to/docs.html
```

### 7. Manage Pipelines
```bash
# List all discovered pipelines
det pipeline list

# Inspect models in a pipeline
det pipeline models [pipeline_name]

# Generate documentation for a pipeline
det pipeline docs [pipeline_name]
```

### 8. Launch the Local Web IDE
```bash
# Launch server and automatically open browser at http://127.0.0.1:8080
det gui
```
Open [http://127.0.0.1:8080](http://127.0.0.1:8080) to explore the visual DAG canvas, models, documentation portal, and execution telemetry.

---

## 🐍 Python SDK Example

```python
from pathlib import Path
from det import Workspace

# Open active workspace (enforces absolute path resolution)
ws = Workspace(Path("/absolute/path/to/my_workspace"))

# Test catalog connections
health = ws.test_catalog()
print("Catalog Health:", health)

# Compile topological pipeline DAG
dag = ws.compile("retail_medallion")
print("Topological order:", [m.name for m in dag.models])

# Execute pipeline models
report = ws.run("retail_medallion")
print(f"Executed {report.total_models} models in {report.duration_ms:.1f}ms")

# Run data quality tests with enforcement policies (error, warning, drop)
test_suite = ws.test("retail_medallion")
print(f"Passed: {test_suite.passed}, Warned: {test_suite.warned}, Dropped: {test_suite.dropped}, Errored: {test_suite.errored}")

# Query monitoring telemetry
recent_runs = ws.monitor_runs("retail_medallion", limit=10, days=30)
for r in recent_runs:
    print(f"Run {r.run_id}: status={r.status}, duration={r.duration_ms:.1f}ms")

# Generate interactive HTML documentation
docs_path = ws.generate_docs("retail_medallion")
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
- 📦 **Pluggable Extension Ecosystem:** Dynamic third-party connector packaging and community plugins for `extensions/`.
- ⚡ **Streaming Ingestion Adapters:** Incremental real-time micro-batch processing with DuckDB append-only appenders.

---

## 🧪 Running Tests

`det` includes an automated test suite covering catalog mounting, DAG parsing, topological execution, quality policies, documentation generation, and telemetry sinks:

```bash
pytest
```
*Automated unit and integration test suite.*

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
