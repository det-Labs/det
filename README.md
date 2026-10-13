# det

[![PyPI Version](https://img.shields.io/pypi/v/det-core.svg?color=blue&logo=pypi&logoColor=white)](https://pypi.org/project/det-core/)
[![CI](https://github.com/det-Labs/det/actions/workflows/ci.yml/badge.svg)](https://github.com/det-Labs/det/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.14+](https://img.shields.io/badge/Python-3.14+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Engine: Apache DataFusion](https://img.shields.io/badge/Engine-Apache%20DataFusion-orange.svg)](https://datafusion.apache.org/)
[![Memory: Apache Arrow](https://img.shields.io/badge/In--Memory-Apache%20Arrow-E14434.svg)](https://arrow.apache.org/)
[![Build: Local-First](https://img.shields.io/badge/Architecture-Local--First-green.svg)](#)

> **det** stands for **Data Engineering Tool** — a fast, local-first SQL ETL workspace and pipeline orchestration engine powered by Apache DataFusion.

`det` is a modern data engineering toolkit that combines declarative SQL pipelines and YAML catalogs with the performance of the embedded **Apache DataFusion** vectorized execution engine. 

Designed as a lightweight, zero-cloud-lock-in alternative to **dbt**, **Spark**, and heavyweight cloud orchestrators, `det` lets you ingest, transform, validate, and document complex multi-stage data pipelines directly on your filesystem.

---

## Core Directives

The architecture of `det` is anchored on three non-negotiable core directives:

- 🧩 **Modularity:** 
  Every component is decoupled and interchangeable. Data catalogs (`catalog/*.yaml`), pipeline DAG steps (`pipelines/*/*.yaml`), storage connectors (`BaseConnector`), DataFusion query execution, documentation generators, and the Web IDE operate as independent, composable building blocks following clean Medallion design (Bronze &rarr; Silver &rarr; Gold).

- ⚡ **Performance:** 
  Built from the ground up on **Apache DataFusion** (Rust vectorized query engine) and **Apache Arrow** columnar memory. Pipeline stages run in-memory with multi-threaded SIMD parallelism, sub-second step execution, and zero cloud serialization overhead or network egress latency.

- 🔌 **Extensibility:** 
  A first-class plugin architecture enables anyone to bring custom storage systems, databases (PostgreSQL, ClickHouse, DuckDB), cloud object stores (S3, GCS, Azure Blob), or REST APIs by subclassing `BaseConnector`. Drive pipelines headlessly via CLI, programmatically via Python SDK, or visually via the built-in browser IDE.

---

## Key Highlights

- ⚡ **Blazing Vectorized Compute:** Powered by Apache DataFusion and Apache Arrow. Executes multi-threaded, SIMD-accelerated SQL transformations in-memory with sub-second latency across CPU cores.
- 📁 **Polyglot Format Unification:** Query and join across heterogeneous formats—**Parquet, Delta Lake (ACID), CSV, JSON, NDJSON, multi-sheet Excel (.xlsx), XML, and Apache Iceberg**—in pure ANSI SQL.
- 🔒 **Zero Cloud Lock-In & Zero Egress:** Transform gigabytes of data locally without provisioning Snowflake, BigQuery, Postgres, or cloud database clusters.
- 🌿 **Git-Versionable by Default:** Workspace catalogs, data connections, and pipeline steps are defined in clean YAML and SQL files. Branch, commit, review, and merge your data stack like application code.
- 🖥️ **Headless First & Dual Mode:** 
  - **Headless:** Drive pipelines headlessly via CLI (`det run`) or Python SDK (`det.Workspace`) in CI/CD environments.
  - **Interactive Web IDE:** Launch the built-in browser UI (`det gui`) for visual DAG inspection, SQL editing, live previews, and telemetry monitoring.
- 📊 **Automated Documentation & Lineage:** Export static, standalone HTML and Markdown documentation portals complete with visual Mermaid DAG topology maps and column schemas.
- 🏪 **Bundled Sample Warehouse:** Instantly unpack **NovaMart Global**—a production-grade omnichannel enterprise warehouse with 14 connections, 8 file formats, and 10 multi-stage SQL pipelines.

---

## Feature Comparison

| Feature | `det` | `dbt-core` | `DuckDB` CLI | `PySpark` |
|---|---|---|---|---|
| **Execution Engine** | Embedded **Apache DataFusion** (Rust vectorized) | Remote Cloud DW (Snowflake/BigQuery/Postgres) | Embedded DuckDB | JVM / Distributed Cluster |
| **Compute Location** | **100% Local / Zero Egress** | Cloud Database required | 100% Local | Local or Cluster |
| **Setup Time** | **30 seconds** (`pip install det-core`) | High (profiles.yml, credentials, DB costs) | Fast (`pip install duckdb`) | High (Java, JVM, Hadoop, RAM tuning) |
| **Multi-Format SQL Joins** | **Parquet, Delta Lake, Excel, JSON, XML, CSV** in pure SQL | Dependent on target database capabilities | Parquet, CSV, JSON | Parquet, Delta, CSV, JSON |
| **Interactive Web IDE** | **Built-in** (`det gui`) with DAG canvas & SQL runner | Cloud SaaS paid add-on / third-party | CLI only | Spark UI (monitoring only) |
| **Automated Lineage & Docs** | **Built-in HTML/Markdown** with Mermaid DAGs | Yes (`dbt docs generate`) | Manual | Complex integration |
| **Declarative YAML Pipelines** | **Built-in** multi-step DAG orchestrator | SQL files + YAML schema | Ad-hoc SQL scripts | Python/Scala code |
| **License** | **MIT License** | Apache 2.0 | MIT | Apache 2.0 |

---

## Quick Start

### Installation

Install via PyPI:

```bash
pip install det-core
```

Or install in editable mode from source:

```bash
git clone https://github.com/det-labs/det.git
cd det
pip install -e .
```

### 30-Second Walkthrough

#### 1. Initialize a Workspace
Create a standard workspace directory structure:
```bash
det init my_workspace
cd my_workspace
```

#### 2. Load the NovaMart Sample Warehouse
Unpack realistic omnichannel datasets, catalog connections, and 10 production SQL pipelines:
```bash
det sample-data
```

#### 3. Execute Pipelines Headlessly
Run staging models, dimensional facts, and business data marts:
```bash
# Clean staging models
det run stg_customers_cleaned
det run stg_orders_normalized

# Build customer dimensions and facts
det run dim_customers
det run fct_orders

# Compute business intelligence mart
det run mart_customer_rfm_loyalty
```

#### 4. Launch the Interactive Web IDE
Serve the visual workspace interface locally:
```bash
det gui --port 8765
```
Open your browser to `http://127.0.0.1:8765` to visually explore catalogs, run SQL pipelines, inspect DAG topologies, and monitor execution metrics.

---

## Architecture Overview

`det` organizes data transformations into clean, reproducible layers following the industry-standard **Medallion Architecture**:

```
[ Raw Sources ]
CSV • XML • JSON • NDJSON • Excel • Parquet • Delta Lake
         │
         ▼  (Bronze: Staging Layer)
  stg_customers_cleaned  •  stg_stores_catalog  •  stg_orders_normalized
         │
         ▼  (Silver: Intermediate Layer)
  dim_customers  •  dim_stores  •  fct_orders
         │
         ▼  (Gold: Analytical Marts)
  mart_customer_rfm_loyalty  •  mart_store_performance_vs_targets
         │
         ▼  (Published Destinations)
  Parquet Lakehouse  •  Delta Lake ACID  •  CSV Reports
```

### Example: Multi-Format Vectorized SQL Join

`det` lets you join completely different file formats in a single SQL query without intermediate conversion:

```sql
-- Joining Silver Parquet transactions against an Excel financial quota sheet
WITH store_actuals AS (
  SELECT
    store_id,
    SUM(quantity * unit_price * (1.0 - discount_pct)) AS realized_revenue,
    COUNT(DISTINCT order_id) AS total_orders
  FROM fct_orders
  GROUP BY store_id
)
SELECT
  s.store_id,
  s.store_name,
  s.city,
  a.realized_revenue,
  t.target_q1_revenue AS target_revenue,
  ROUND((a.realized_revenue / t.target_q1_revenue) * 100, 2) AS quota_attainment_pct
FROM dim_stores s
JOIN store_actuals a ON s.store_id = a.store_id
JOIN financial_ref_targets t ON s.store_id = t.store_id
ORDER BY quota_attainment_pct DESC;
```

---

## Workspace Structure

An initialized `det` workspace has a predictable, Git-friendly folder hierarchy:

```
my_workspace/
├── catalog/
│   └── default.yaml          # Declarative data sources & destinations
├── pipelines/
│   └── my_pipeline/
│       └── pipeline.yaml     # Multi-step SQL DAG definition
├── documentation/            # Generated HTML/Markdown lineage docs
├── extensions/
│   ├── connectors/           # Custom Python connector plugins
│   └── ui/                   # Custom UI extensions
├── logs/
│   └── pipelines/            # Execution run logs and metrics
└── source_data/              # Local data storage (optional)
```

---

## Command Line Interface (CLI)

| Command | Syntax | Description |
|---|---|---|
| **Init** | `det init [FOLDER]` | Scaffolds workspace layout and creates `default.yaml`. |
| **Sample Data** | `det sample-data` | Unpacks NovaMart Global datasets, catalog, and pipelines. |
| **Run** | `det run <pipeline_key>` | Executes a pipeline headlessly with live progress logs. |
| **Catalog** | `det catalog list` | Lists all registered catalogs and connection folders. |
| **Pipeline** | `det pipeline list` | Displays all configured pipelines, stages, and status. |
| **Docs** | `det docs <pipeline_key>` | Generates automated HTML and Markdown documentation. |
| **GUI** | `det gui [--port 8765]` | Starts the local web server and opens the browser UI. |

---

## Python SDK

Integrate `det` directly into your Python automation, test suites, or Jupyter notebooks:

```python
import det
from pathlib import Path

# Initialize workspace
workspace = det.Workspace("./my_workspace")

# Install sample data
det.sample_data.install(workspace.root)

# Execute pipeline programmatically
result = workspace.run_pipeline("Sample_Warehouse_Pipelines/mart_customer_rfm_loyalty")

print(f"Status: {result['status']}")
print(f"Execution Time: {result['duration_ms']:.2f} ms")
print(f"Rows Processed: {result['rows_processed']}")
```

---

## Extensibility & Custom Connectors

`det` includes a plugin architecture based on the `BaseConnector` specification. Build and register custom storage backends (e.g. SQLite, PostgreSQL, REST APIs) in just a few lines of Python:

```python
from det.connectors import BaseConnector, ConnectorRegistry

class SQLiteConnector(BaseConnector):
    guid = "my-custom-sqlite-connector"
    name = "SQLite Database"
    is_readable = True
    is_writable = True

    def scan(self, options, context, workspace):
        import sqlite3, pyarrow as pa
        conn = sqlite3.connect(options["path"])
        # Ingest into Arrow RecordBatch and register view
        ...
        return dataframe

# Register connector
ConnectorRegistry.register(SQLiteConnector())
```

---

## Community & Contributing

We welcome contributions of all kinds! Whether you want to add a new connector, improve the DataFusion engine, enhance documentation, or report issues:

- 📖 **Contributor Guide:** Check out [CONTRIBUTING.md](CONTRIBUTING.md) for local setup, development guidelines, and our custom connector authoring tutorial.
- 🔌 **Community Connector Wishlist:** We are actively looking for contributors to help build and test connectors for:
  - Databases: **PostgreSQL**, **ClickHouse**, **MySQL**, **DuckDB**, **Snowflake**, **BigQuery**
  - Cloud Storage: **AWS S3**, **Google Cloud Storage (GCS)**, **Azure Blob Storage**
  - Streams & APIs: **Kafka / Redpanda**, **REST / Webhooks**
- 💬 **Join the Discussion:** Have questions or pipeline architecture ideas? Join our [GitHub Discussions](https://github.com/det-Labs/det/discussions).
- 📜 **Code of Conduct:** Review our [Code of Conduct](CODE_OF_CONDUCT.md).
- 🛡️ **Security:** For security vulnerability reporting, please see [SECURITY.md](SECURITY.md).

---

## Running Tests

Run the test suite:

```bash
python -m unittest discover -s tests
```

---

## Authors & License

Maintained by **Saurabh Rai** ([saurabhr2@gmail.com](mailto:saurabhr2@gmail.com)) and **[det-Labs](https://github.com/det-Labs)**.

This project is licensed under the **[MIT License](LICENSE)**. Anyone is free to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software, subject to including the copyright notice and attribution to the authors in all copies or substantial portions of the Software.

---

## Discovery & Search Tags

`ETL` • `det` • `dbt alternative` • `SQL` • `data engineering` • `data pipeline` • `apache datafusion` • `apache arrow` • `parquet` • `delta lake` • `duckdb alternative` • `data orchestration` • `analytics engineering` • `medallion architecture` • `local-first` • `data warehouse`
