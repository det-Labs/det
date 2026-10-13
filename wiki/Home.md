# Welcome to the `det` Wiki

**`det` (Data Engineering Tool)** is a fast, local-first SQL ETL workspace and multi-step pipeline orchestration engine built in Python and powered by **Apache DataFusion** and **Apache Arrow**.

It gives data engineers, analytics engineers, and data teams a lightweight, developer-friendly alternative to heavy data orchestrators—combining declarative YAML pipeline models, a zero-install browser IDE, pre-flight SQL validation, telemetry monitoring, and automated pipeline documentation.

---

## 🎯 The Three Core Directives

Everything in `det` is engineered around three foundational architectural pillars:

### 1. 🧩 Modularity
Every asset in `det` is cleanly decoupled and self-contained:
- **Data Catalog**: Connections (CSV, Parquet, JSON, NDJSON, XML, Excel, Delta Lake) are declared once and reused everywhere.
- **DAG Pipelines**: Workflows are divided into independent, reproducible SQL transformation steps. Intermediate stages can be inspected, tested, or routed to separate sinks.
- **Workspace Isolation**: Workspaces contain their own catalogs, pipelines, environments, and execution history without cross-project bleed.

### 2. ⚡ Performance
`det` eliminates python serialization bottlenecks and heavy JVM clusters:
- **Apache DataFusion Engine**: Multi-threaded, vectorized Rust execution engine running queries at bare-metal speeds directly on CPU cores.
- **Apache Arrow Columnar Memory**: Zero-copy in-memory interoperability between query stages and storage formats.
- **Lazy Scanning & Projection Pushdown**: Only the columns and row slices required by your SQL transformations are scanned from disk.

### 3. 🔌 Extensibility
The platform is designed to adapt to any modern or legacy data ecosystem:
- **Pluggable Connectors**: Simple Python API allows registering custom storage engines, internal proprietary databases, REST APIs, and file formats.
- **Unified SQL Dialect**: Use standard SQL across heterogeneous sources—join an Excel workbook with a Delta Lake table and output to Parquet in a single pipeline.
- **Headless Orchestration & Rich GUI**: Run headless in CI/CD via CLI (`det run`) or visually design and debug pipelines in the embedded Web IDE (`det gui`).

---

## 🚀 Quick Navigation

| Guide | Description |
| :--- | :--- |
| **[[Quickstart & Installation\|Quickstart-&-Installation]]** | Install `det-core` from PyPI, initialize a workspace, and run your first pipeline. |
| **[[Core Directives & Architecture\|Core-Directives-&-Architecture]]** | Deep dive into engine architecture, in-memory execution, and storage isolation. |
| **[[SQL ETL Pipeline Authoring\|SQL-ETL-Pipeline-Authoring]]** | Learn multi-stage DAG pipelines, CTEs, DataFusion SQL features, and output sinks. |
| **[[Custom Connectors Guide\|Custom-Connectors-Guide]]** | Build and package custom source and destination connectors. |
| **[[CLI & Web IDE Reference\|CLI-&-Web-IDE-Reference]]** | Command-line arguments, keyboard shortcuts, and GUI capabilities. |

---

## 🌐 Live Interactive Resources
- **Online Showcase**: Try the [Interactive Web IDE](https://det-labs.github.io/det/demo.html) right in your browser.
- **PyPI Package**: [`pip install det-core`](https://pypi.org/project/det-core/)
- **Main Codebase**: [det-Labs/det on GitHub](https://github.com/det-Labs/det)
