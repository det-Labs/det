# <span style="color:#f45b00;">det</span> — Data Engineering Toolkit
### by <span style="color:#f45b00;">det</span> <span style="color:#5d5d5f;">Labs</span>

> **A modular, Python-first data engineering framework built by <span style="color:#f45b00;">det</span> Labs for modern analytical workflows.**

[![CI](https://img.shields.io/badge/CI-passing-22c55e.svg)](https://github.com/saurabhr2/det/actions)
[![Python](https://img.shields.io/badge/python->=3.15-3776ab.svg)](https://www.python.org/downloads/release/python-3150/)
[![License](https://img.shields.io/badge/license-Apache--2.0-22c55e.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-f45b00.svg)](https://github.com/saurabhr2/det/releases)
[![det Labs](https://img.shields.io/badge/org-det%20Labs-f45b00.svg)](https://github.com/saurabhr2/det)

---

## Current Status: Version 0.1.0 (Catalog MVP Released)

**<span style="color:#f45b00;">det</span>** (developed by **det Labs**) has completed its **Version 0.1.0** milestone with the release of the **Catalog Module (`det.catalog`)**:
- Concurrency-safe, atomic YAML metadata persistence with file locks.
- Automated schema discovery for Parquet, CSV, TSV, JSON, NDJSON, Excel, and directory datasets using Polars and PyArrow.
- Leverages Python 3.15 stable native `lazy import` syntax for instantaneous engine load times.
- Full Python programmatic Command API (`CatalogService`).
- Interactive Local Browser Web GUI with vertical category explorer, draggable resizer, quick circular action buttons, Discover Schema modal, inline column description editing, and a 3-way theme switcher (Light / Dark / Auto System).
- Typer CLI (`det catalog ...` and `det-gui`).

---

## Architectural Vision & Module Roadmap

`det` is built from the ground up by det Labs to be modular, extensible, and Python-native:

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interfaces                         │
│         CLI (`det`)   │   Web GUI (`det-gui`)   │   API     │
└──────────────┬──────────────────┬──────────────────┬────────┘
               │                  │                  │
┌──────────────▼──────────────────▼──────────────────▼────────┐
│                 det Core Modules (det Labs)                 │
│                                                             │
│  [ Released v0.1 ]                                          │
│  ├── det.catalog     Metadata, schemas, YAML store & GUI    │
│                                                             │
│  [ Planned Roadmap ]                                        │
│  ├── det.engine      Execution abstraction (DuckDB, Polars) │
│  ├── det.pipeline    DAG orchestration & SQL/Python models  │
│  ├── det.quality     Schema contracts, profiling & tests    │
│  ├── det.lineage     Table & column-level dependency graphs │
│  └── det.connectors  Ingestion & sync (Iceberg, Delta, S3)  │
└─────────────────────────────────────────────────────────────┘
```

### Module Roadmap

| Module | Purpose | Status |
| :--- | :--- | :--- |
| **`det.catalog`** | Dataset discovery, typed schema inference, categories/namespaces, and visual catalog manager | **Released in v0.1.0** |
| **`det.engine`** | Unified query execution interface abstracting Polars, DuckDB, and Arrow in-memory compute | *Planned (v0.2)* |
| **`det.pipeline`** | Pipeline DAG execution, dbt-style transforms in SQL & Python, incremental materialization | *Planned (v0.3)* |
| **`det.quality`** | Data validation checks, statistical profiling, anomaly detection, and schema contracts | *Planned (v0.4)* |
| **`det.lineage`** | Column-level and dataset-level upstream/downstream lineage graphs | *Planned (v0.5)* |
| **`det.connectors`**| Multi-source extractors and destination sinks (S3, GCS, PostgreSQL, Snowflake, Iceberg, Delta) | *Planned (v0.6)* |

---

## Quickstart

### Prerequisites
- **Python**: `>= 3.15` (Stable released October 9, 2026)

### Installation

```bash
# Clone the repository
git clone https://github.com/saurabhr2/det.git
cd det

# Create virtual environment with Python 3.15
py -3.15 -m venv .venv
.venv\Scripts\activate       # On Windows
# source .venv/bin/activate  # On Linux/macOS

# Install in editable mode with development tools
pip install -e ".[dev]"

# Verify test suite
pytest
```

### 1. Launch the Catalog Web GUI
Experience the interactive visual catalog manager directly in your local browser:

```bash
det-gui
```
Navigate to `http://127.0.0.1:8501`:
- Group datasets into categories / namespaces.
- Point to local files or folders and click **Discover Schema** to auto-infer columns and types.
- Drag the sidebar border to resize the explorer bar manually (double-click to reset).
- Switch themes between **Light**, **Dark**, or **Auto (System Default)**.
- Edit column descriptions inline by clicking on them.
- Switch between different YAML catalog files or create brand new catalogs.

### 2. Using the CLI

```bash
# View system & version info
det version
det info

# Scan a dataset to inspect its inferred schema without registering
det catalog scan sample_data/orders.parquet

# List all registered tables in active catalog
det catalog list

# Set a catalog file as the persistent default
det catalog set-default catalogs/main.yaml
```

### 3. Programmatic Python API

```python
from det.catalog import CatalogService, DatasetMetadata

# Connect to catalog
service = CatalogService("catalogs/main.yaml")

# Discover schema from a Parquet or CSV file
scan = service.scan_path("data/customers.parquet")

# Register into catalog
service.register_dataset(DatasetMetadata(
    id="crm.customers",
    name="customers",
    namespace="crm",
    format="parquet",
    location="data/customers.parquet",
    description="Customer master records",
    columns=scan.columns,
    row_count=scan.row_count,
))

# Retrieve and inspect
dataset = service.get_dataset("crm.customers")
print(f"Table {dataset.name} has {len(dataset.columns)} columns and {dataset.row_count} rows.")
```

---

## Testing & Quality

All code adheres to strict standards:
- PEP 257 docstrings on all public functions, classes, and methods.
- Explicit type annotations.
- Python 3.15 `lazy import` integration.
- Fast, automated pytest test suite:

```bash
pytest -v
ruff check .
```

---

## License

Distributed under the **Apache License 2.0**. Copyright (c) 2026 det Labs. See [`LICENSE`](LICENSE) for details.
