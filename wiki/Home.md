# Welcome to the `det` Wiki

**`det` (Data Engineering Tool)** is a fast, local-first SQL ETL workspace and multi-step pipeline orchestration engine built in Python and powered by **DuckDB 2.0** and **Apache Arrow**.

It gives data engineers, analytics engineers, and data teams a lightweight, developer-friendly orchestration workflow—combining declarative YAML pipeline models, a zero-install browser IDE, pre-flight SQL validation, row-level quarantine sinks, pluggable telemetry, and automated pipeline documentation.

---

## 🎯 The Three Core Directives

Everything in `det` is engineered around three foundational architectural pillars:

### 1. 🧩 Modularity
Every asset in `det` is cleanly decoupled and self-contained:
- **Data Catalog**: Connections (CSV, Parquet, JSON, NDJSON, Excel, Delta Lake, Apache Iceberg, AWS S3, Azure Blob / ADLS Gen2, Google Cloud Storage, Microsoft Fabric OneLake, PostgreSQL, MySQL, SQLite, MSSQL) are declared once and reused across all pipelines.
- **Topological DAG Pipelines**: Workflows are divided into independent, reproducible SQL transformation models. Intermediate stages can be inspected, tested, or routed to separate storage sinks.
- **Workspace Isolation**: Workspaces contain their own catalogs, extensions, models, and execution history without cross-project bleed.

### 2. ⚡ Performance
`det` leverages modern in-process vectorized analytics:
- **DuckDB 2.0 Engine**: Multi-threaded, vectorized SQL execution engine running analytical queries at bare-metal speeds directly on CPU cores.
- **Apache Arrow Columnar Memory**: Zero-copy in-memory interoperability between query stages and storage formats.
- **Lazy Scanning & Pushdown**: Projection pushdown and predicate pushdown ensure only required columns and row slices are scanned from disk.

### 3. 🔌 Extensibility
The platform is designed to adapt to any modern or legacy data ecosystem:
- **Pluggable Connectors**: Python extensions allow mounting external databases, cloud object stores, and custom file formats directly into the DuckDB session.
- **Unified Multi-Cloud Lakehouse**: Native support for AWS S3, Azure Blob / ADLS Gen2, Google Cloud Storage, Microsoft Fabric OneLake, and Delta Lake read/write.
- **Unified SQL Dialect**: Standard SQL queries can effortlessly join local files, cloud tables, and database connections in a single pipeline.
- **Headless Orchestration & Rich GUI**: Run headless in CI/CD via CLI (`det run`, `det test`) or visually design and debug pipelines in the embedded Web IDE (`det gui`).

---

## 🚀 Quick Navigation: Core CLI Guides

| Guide | Description |
| :--- | :--- |
| [**Quickstart & Installation**](Quickstart-&-Installation) | Install `det-core` from PyPI, initialize a workspace, and run your first pipeline. |
| [**Core Directives & Architecture**](Core-Directives-&-Architecture) | Deep dive into engine architecture, in-memory execution, and storage sinks. |
| [**SQL ETL Pipeline Authoring**](SQL-ETL-Pipeline-Authoring) | Learn multi-stage DAG pipelines, data tests, row quarantine, and output destinations. |
| [**Cloud Lakehouse Connectors**](Cloud-Lakehouse-Connectors) | Configure AWS S3, Azure ADLS Gen2, GCS, OneLake, and Delta Lake reads and writes. |
| [**Custom Connectors Guide**](Custom-Connectors-Guide) | Build and mount custom source and destination connectors. |
| [**CLI & Web IDE Reference**](CLI-&-Web-IDE-Reference) | Command-line arguments, keyboard shortcuts, and headless operations. |

---

## 🖥️ Quick Navigation: Web IDE Visual Studio

| Guide | Description |
| :--- | :--- |
| [**Web IDE Overview & Getting Started**](Web-IDE-Overview-&-Getting-Started) | Launching `det gui`, layout architecture, demo mode, and shortcuts. |
| [**Pipelines & DAG Studio**](Web-IDE-Pipelines-&-DAG-Studio) | Visual DAG lineage, Dual-Mode SQL Editor, live model execution, and schema views. |
| [**Data Quality & Quarantine**](Web-IDE-Data-Quality-&-Quarantine) | Interactive assertion authoring, test execution badges, and non-blocking quarantine audit. |
| [**Catalog & Lakehouse Connections**](Web-IDE-Catalog-&-Lakehouse-Connections) | Visual multi-cloud storage setup, latency health probes, and SQL Scratchpad. |
| [**Monitoring & Living Documentation**](Web-IDE-Monitoring-&-Living-Documentation) | Execution telemetry, millisecond latency tables, and auto-generated data dictionaries. |

---

## 🔮 Roadmap: SQL Editor Autocompletion
A major upcoming enhancement is **in-editor SQL autocompletion** powered by a lightweight Language Server Protocol (LSP) and catalog introspection. This will provide intelligent schema hints, column auto-suggestions, and instant SQL syntax diagnostics right inside the Web IDE editor.

---

## 🌐 External Resources
- **PyPI Package**: [`pip install det-core`](https://pypi.org/project/det-core/)
- **Product Website**: [det-labs.github.io/det](https://det-labs.github.io/det/)
- **Main Codebase**: [det-Labs/det on GitHub](https://github.com/det-Labs/det)
- **Issue Tracker**: [GitHub Issues](https://github.com/det-Labs/det/issues)

---

| 🏠 Overview | Next Page ➡️ |
| :--- | ---: |
| [**Wiki Index**](Home) | [**Quickstart & Installation ➔**](Quickstart-&-Installation) |
