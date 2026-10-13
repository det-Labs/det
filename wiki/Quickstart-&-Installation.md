# Quickstart & Installation

Get started with `det` in under 60 seconds.

---

## 📦 Requirements

- **Python**: `>= 3.14` (built for modern Python with prerelease support)
- **OS**: Linux (Ubuntu, Debian, Fedora, Arch), macOS (Intel & Apple Silicon), Windows (10/11, Server)
- **Rust/Cargo**: Not required (wheels are pre-compiled with Apache DataFusion binaries)

---

## 🛠️ Installation

Install `det-core` directly from PyPI:

```bash
pip install det-core
```

For development or full format support (including Excel `.xlsx` and Delta Lake):

```bash
pip install "det-core[dev]"
```

Verify your installation:

```bash
det --version
```

---

## 🚀 Initialize Your First Workspace

1. **Create and navigate to your project directory**:

   ```bash
   mkdir my_warehouse && cd my_warehouse
   ```

2. **Install the complete NovaMart Global sample warehouse**:

   ```bash
   det sample-data
   ```

   This unpacks:
   - 14 Catalog connections across CSV, Parquet, JSON, NDJSON, XML, Excel, and Delta Lake
   - 10 Production multi-stage ETL pipelines
   - Source dataset files under `source_data/`

3. **Launch the interactive Web IDE**:

   ```bash
   det gui
   ```

   The local IDE will automatically launch in your default web browser at `http://127.0.0.1:8000`.

---

## 🏃 Running Pipelines via CLI

Run a single pipeline by name or folder/name:

```bash
det run Sample_Warehouse_Pipelines/fct_orders
```

Run with verbose execution output and step breakdown:

```bash
det run Sample_Warehouse_Pipelines/mart_customer_rfm_loyalty --verbose
```

---

## 🧪 Validating Pipelines Headless

Verify SQL syntax, column references, and dependency topologies before running:

```bash
det validate Sample_Warehouse_Pipelines/stg_customers_cleaned
```

---

## 📚 Generating Pipeline Documentation

Generate standalone, interactive HTML documentation complete with Mermaid DAG diagrams and data contracts:

```bash
det doc Sample_Warehouse_Pipelines/mart_customer_rfm_loyalty --format html
```

