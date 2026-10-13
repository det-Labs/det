# CLI & Web IDE Reference

Comprehensive reference for the `det` command-line interface and the local Web IDE.

---

## 💻 CLI Commands

### `det gui`
Launches the interactive Web IDE server and automatically opens your web browser:

```bash
det gui [--port 8000] [--host 127.0.0.1] [--no-browser]
```

### `det run`
Executes one or all pipelines headlessly:

```bash
det run <pipeline_path_or_name> [--catalog custom.yaml] [--verbose]
```

Examples:
```bash
det run Sample_Warehouse_Pipelines/fct_orders
det run Sample_Warehouse_Pipelines/mart_customer_rfm_loyalty --verbose
```

### `det validate`
Performs static pre-flight validation on a pipeline's SQL queries, schemas, and dependencies:

```bash
det validate <pipeline_path_or_name>
```

### `det sample-data`
Installs the complete NovaMart Global sample warehouse into the current directory:

```bash
det sample-data [--force]
```

### `det doc`
Generates interactive HTML or Markdown documentation from a pipeline definition:

```bash
det doc <pipeline_path_or_name> [--format html|markdown]
```

### `det inspect`
Inspects a catalog connection, lists columns, data types, and row count:

```bash
det inspect <connection_name> [--rows 10]
```

---

## 🖥️ Web IDE Interface & Keyboard Shortcuts

The `det` Web IDE offers four unified modules:

1. **Catalog Module**:
   - Manage source and destination connection metadata
   - Live sample preview with pagination and data types
   - Schema derivation and type overrides
2. **ETL Module**:
   - Visual Mermaid DAG graph reflecting transformation flow
   - Multi-step SQL editor with syntax highlighting
   - Inline schema validation and destination routing
   - One-click pipeline execution with real-time step timers
3. **Monitoring Module**:
   - Comprehensive telemetry history for every run
   - Status indicators (SUCCESS, FAILED, RUNNING)
   - Step-by-step latency analysis and processed row counts
4. **Documentation Module**:
   - Auto-generated living documentation for every pipeline
   - Embedded SVG/Mermaid DAGs
   - Markdown and HTML export

### Global Keyboard Shortcuts
- `Ctrl + Enter` (or `Cmd + Enter`): Run active pipeline or step
- `Ctrl + S` (or `Cmd + S`): Save pipeline definition
- `Escape`: Close modals and inspection drawers
