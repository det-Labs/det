# CLI & Web IDE Reference

Comprehensive reference for the `det` command-line interface and the local Web IDE.

---

## 💻 CLI Commands Summary Matrix

| Command | Action / Subcommands | Primary Purpose |
| :--- | :--- | :--- |
| `det init` | `[path]` | Scaffolds a new workspace with standard 4-folder structure |
| `det activate` | `<path>` | Sets the active workspace path for current terminal session |
| `det status` | *(none)* | Displays active workspace path, scoped folders, and health |
| `det demo` | `[path] [--remote] [--open] [--port N]` | Generates a complete ready-to-run retail medallion demo |
| `det compile` | `[pipeline_name]` | Compiles models, resolves `{{ ref() }}`, and validates DAG |
| `det run` | `[pipeline_name] [--threads N] [--vars '...']` | Executes pipeline models in topological dependency order |
| `det test` | `[pipeline_name] [--vars '...']` | Evaluates assertions against policies (`error`, `warning`, `drop`) |
| `det pipeline` | `list`, `compile`, `test`, `run`, `delete`, `models`, `docs` | Pipeline inspection, targeted execution, and lifecycle management |
| `det catalog` | `list`, `test`, `display`, `details`, `delete` | Data connection management, latency probes, and live data preview |
| `det monitor` | `runs`, `run`, `audits`, `status`, `clean` | Execution telemetry, stage duration profiling, and audit logs |
| `det docs` | `generate`, `open`, `export`, `delete` | Interactive data dictionary & lineage HTML documentation |
| `det gui` | `[--host H] [--port P] [--no-browser]` | Launches local zero-dependency Web IDE with auto-browser launch |

---

## 📁 1. Workspace Session & Environment

### `det init`
Scaffolds a clean workspace with the standardized 4-folder layout (`catalog/`, `pipelines/`, `data/`, `extensions/`, and internal `.det/`).

```bash
# Initialize current directory
det init

# Initialize a specific directory
det init /path/to/my_workspace
```

### `det activate`
Sets the active workspace directory in the local user session (`~/.det_session/session.json`). All subsequent `det` commands will automatically use this directory until changed.

```bash
det activate /path/to/my_workspace
```

### `det status`
Displays the currently resolved active workspace, session source (`CWD`, `DET_ACTIVE_DIR`, or session file), and folder verification status.

```bash
det status
```

### `det demo`
Scaffolds a fully populated sample workspace containing retail medallion pipelines (bronze, silver, gold models), sample CSV/Parquet data, and schema assertions.

```bash
# Scaffold local demo in current directory
det demo

# Scaffold demo and immediately launch & open Web IDE in browser
det demo --open

# Download remote online datasets via HTTPS instead of synthetic files
det demo --remote --open --port 8080
```

---

## ⚡ 2. Pipeline Execution & Compilation

### `det compile`
Parses YAML configurations and SQL models, validates syntax, resolves `{{ ref('model') }}` and `{{ source('conn', 'table') }}` macros, and constructs the topological execution DAG without scanning data.

```bash
# Compile default / all pipelines
det compile

# Compile a specific named pipeline
det compile retail_medallion
```

### `det run`
Executes pipeline models in topological dependency order using multi-threaded DuckDB.

```bash
# Run default pipeline
det run

# Run a specific pipeline with 4 execution threads
det run retail_medallion --threads 4

# Run with custom runtime variable substitution
det run retail_medallion --vars '{"environment": "production", "batch_date": "2026-10-26"}'
```

### `det test`
Executes data quality assertions configured across pipeline models. Violations are handled according to model policies:
- `error`: Halts pipeline execution immediately.
- `warning`: Logs total violating row counts to monitoring telemetry and continues execution.
- `drop`: Drops violating rows in-flight (`EXCEPT ALL`) and processes remaining compliant rows.

```bash
# Run tests for a pipeline
det test retail_medallion

# Run tests with runtime variable substitution
det test retail_medallion --vars '{"cutoff_year": 2024}'
```

---

## 🧩 3. Pipeline Lifecycle Management (`det pipeline`)

Inspect, manage, and execute individual pipelines:

```bash
# 1. List all available pipelines in the workspace
det pipeline list
det pipeline list --filter retail

# 2. Compile a single pipeline
det pipeline compile retail_medallion

# 3. Test a single pipeline
det pipeline test retail_medallion

# 4. Run a pipeline with verbose output or model selector
det pipeline run retail_medallion --verbose
det pipeline run retail_medallion --select "+silver_orders"

# 5. List all models contained in a pipeline
det pipeline models retail_medallion

# 6. Generate HTML documentation for a pipeline
det pipeline docs retail_medallion

# 7. Delete a pipeline and its model files
det pipeline delete old_pipeline --yes
```

> [!NOTE]
> Pipelines are scaffolded via the **Web IDE** visual interface or by creating a directory under `pipelines/<name>/` with a `det_project.yaml` and `models/` folder.

---

## 🔌 4. Data Catalog & Connections (`det catalog`)

Manage data source definitions declared in `catalog/connections.yaml`:

```bash
# 1. List all registered catalog connections
det catalog list
det catalog list --folder raw_files
det catalog list --filter delta

# 2. Test live connection health and network/read latency
det catalog test
det catalog test s3_lakehouse

# 3. Preview top rows from a catalog connection (interactive preview)
det catalog display customer_raw --limit 10

# 4. Inspect full metadata, mount SQL, and credentials configuration
det catalog details customer_raw

# 5. Delete an individual catalog connection from catalog/connections.yaml
det catalog delete legacy_db --yes
```

---

## 📊 5. Execution Monitoring & Telemetry (`det monitor`)

Query persistent execution metrics, duration breakdowns, and data quality audits:

```bash
# 1. List recent pipeline execution runs (inclusive priority up to 20 runs over 30 days)
det monitor runs
det monitor runs retail_medallion --limit 50 --days 60
det monitor runs --failed

# 2. Show detailed breakdown of a single pipeline run (stage durations, models, errors)
det monitor run run-20261026-140000-abc12345

# 3. List data quality test execution audit logs
det monitor audits
det monitor audits retail_medallion --failed
det monitor audits --run run-20261026-140000-abc12345

# 4. Show active monitoring sink configuration, database path, and record counts
det monitor status

# 5. Purge historical telemetry runs and test audits older than N days
det monitor clean --days 90 --yes
det monitor clean --days 30 --pipeline retail_medallion --yes
```

---

## 📚 6. Living Documentation (`det docs`)

Generate, inspect, and export interactive standalone data dictionaries and SVG lineage DAGs:

```bash
# 1. Generate or regenerate static HTML documentation for a pipeline
det docs generate retail_medallion

# 2. Open documentation in default browser or start a dedicated HTTP server
det docs open retail_medallion
det docs open retail_medallion --serve --port 8081

# 3. Export single-file self-contained HTML documentation bundle
det docs export retail_medallion --output /path/to/exported_docs.html

# 4. Delete generated documentation build artifacts
det docs delete retail_medallion
```

---

## 🖥️ 7. Web IDE Studio (`det gui`)

Launches the embedded, zero-dependency browser Web IDE with real-time DAG studio, interactive SQL editor, and live monitoring:

```bash
# Launch GUI and automatically open default browser at http://127.0.0.1:8080
det gui

# Bind to a custom port or interface
det gui --port 9090 --host 0.0.0.0

# Launch server without auto-opening browser
det gui --no-browser
```

---

## 🖥️ Deep-Dive Web IDE Visual Studio Guides

For comprehensive step-by-step guides on using each visual module in the Web IDE, consult the dedicated studio documentation:

* [**Web IDE Overview & Getting Started**](Web-IDE-Overview-&-Getting-Started): Launching, demo walkthrough, layout, and keyboard shortcuts.
* [**Web IDE: Pipelines & DAG Studio**](Web-IDE-Pipelines-&-DAG-Studio): Interactive DAG canvas, Dual-Mode SQL editor, and live model execution.
* [**Web IDE: Data Quality & Policies**](Web-IDE-Data-Quality-&-Policies): Visual assertion authoring, test badges, and enforcement policies (`error`, `warning`, `drop`).
* [**Web IDE: Catalog & Lakehouse Connections**](Web-IDE-Catalog-&-Lakehouse-Connections): Multi-cloud storage setup, latency health probes, and SQL Scratchpad.
* [**Web IDE: Monitoring & Living Documentation**](Web-IDE-Monitoring-&-Living-Documentation): Millisecond stage latency dashboards and auto-generated data dictionaries.

---

### Keyboard Shortcuts
- `Ctrl + Enter` (or `Cmd + Enter`): Run active SQL query or pipeline
- `ArrowLeft` / `ArrowRight`: Navigate between active tabs or views
- `Escape`: Close modals and inspection drawers

---

| ⬅️ Previous Page | 🏠 Overview | Next Page ➡️ |
| :--- | :---: | ---: |
| [**← Custom Connectors Guide**](Custom-Connectors-Guide) | [**Wiki Index**](Home) | [**Web IDE Overview & Getting Started ➔**](Web-IDE-Overview-&-Getting-Started) |
