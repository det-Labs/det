# Quickstart & Installation

Get started with `det` in under 60 seconds.

---

## 📦 Requirements

- **Python**: `>= 3.14` (built for modern Python environments)
- **OS**: Linux, macOS (Intel & Apple Silicon), Windows (10/11, Server)
- **C/C++ Compiler**: Not required (DuckDB and PyArrow binaries are pre-compiled wheels)

---

## 🛠️ Installation

Install `det-core` directly from PyPI:

```bash
pip install det-core
```

For development or test harness tools:

```bash
pip install "det-core[dev]"
```

Verify your installation:

```bash
det --version
```

---

## 🚀 Initialize Your Workspace

1. **Create and navigate to your project directory**:

   ```bash
   mkdir my_warehouse && cd my_warehouse
   ```

2. **Scaffold a clean workspace structure**:

   ```bash
   det init
   ```

   This creates:
   - `catalog/`: Connector YAML declarations for raw and curated data sources.
   - `projects/`: SQL pipeline models organized in domain folders with `det_project.yaml`.
   - `extensions/`: Built-in and custom storage engine connectors.
   - `.det/`: Local runtime state, telemetry databases, and session caches.

3. **Launch the interactive Web IDE**:

   ```bash
   det gui
   ```

   The local IDE will automatically launch in your default web browser at `http://127.0.0.1:8080`.

---

## 🏃 Running Pipelines via CLI

Run a single pipeline by name or project folder:

```bash
det run my_project/fct_orders
```

Run with verbose execution output and step breakdown:

```bash
det run my_project/fct_orders --verbose
```

---

## 🧪 Validating & Testing Pipelines Headless

Verify SQL syntax, column references, and dependency topologies before running:

```bash
det validate my_project/fct_orders
```

Execute data quality audits and tests (e.g. `not_null`, `unique`, `accepted_values`, `row_condition`):

```bash
det test my_project/fct_orders
```

---

## 📚 Generating Pipeline Documentation

Generate standalone documentation complete with SVG/Mermaid DAG lineage and schema contracts:

```bash
det doc my_project/fct_orders
```

---

| ⬅️ Previous Page | 🏠 Overview | Next Page ➡️ |
| :--- | :---: | ---: |
| [**← Home Overview**](Home) | [**Wiki Index**](Home) | [**Core Directives & Architecture ➔**](Core-Directives-&-Architecture) |
