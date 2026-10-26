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

   This creates the standardized 4-directory layout:
   - `catalog/`: Contains `connections.yaml` for data source declarations using absolute file paths.
   - `pipelines/`: SQL pipeline models organized in pipeline directories with `det_project.yaml` and `models/`.
   - `data/`: Storage for local data files (Parquet, CSV, Delta, DuckDB).
   - `extensions/`: Built-in and custom storage engine connectors.
   - `.det/`: Local runtime state, telemetry databases, and session caches.

3. **Verify Catalog Connections**:

   ```bash
   det catalog list
   det catalog test
   ```

4. **Launch the interactive Web IDE**:

   ```bash
   det gui
   ```

   The local IDE will automatically launch in your default web browser at `http://127.0.0.1:8080`.

---

## 🏃 Compiling & Running Pipelines via CLI

Compile DAG dependencies without scanning data:

```bash
det compile retail_medallion
```

Run a pipeline with multi-threaded execution:

```bash
det run retail_medallion --threads 4
```

Run with variable substitution:

```bash
det run retail_medallion --vars '{"environment": "prod"}'
```

---

## 🧪 Testing Data Quality

Execute data quality assertions against configured enforcement policies (`error`, `warning`, `drop`):

```bash
det test retail_medallion
```

---

## 📊 Monitoring Execution History

Inspect run telemetry and stage durations:

```bash
det monitor runs retail_medallion
det monitor audits retail_medallion
```

---

## 📚 Generating Living Documentation

Generate a standalone interactive HTML documentation portal complete with SVG/Mermaid DAG lineage:

```bash
det docs generate retail_medallion
det docs open retail_medallion --serve
```

---

| ⬅️ Previous Page | 🏠 Overview | Next Page ➡️ |
| :--- | :---: | ---: |
| [**← Home Overview**](Home) | [**Wiki Index**](Home) | [**Core Directives & Architecture ➔**](Core-Directives-&-Architecture) |
