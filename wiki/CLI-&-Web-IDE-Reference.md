# CLI & Web IDE Reference

Comprehensive reference for the `det` command-line interface and the local Web IDE.

---

## 💻 CLI Commands

### `det init`
Scaffolds a clean workspace with standard folders (`catalog/`, `projects/`, `extensions/`, `.det/`):

```bash
det init [workspace_name]
```

### `det gui`
Launches the interactive zero-CDN Web IDE and opens your web browser:

```bash
det gui [--port 8080] [--host 127.0.0.1] [--no-browser]
```

### `det run`
Executes one or all pipelines headlessly with topological DAG resolution:

```bash
det run <pipeline_or_project> [--verbose]
```

### `det test`
Executes data quality audits and tests configured on pipeline models:

```bash
det test <pipeline_or_project>
```

### `det validate`
Performs static pre-flight validation on SQL queries, column schemas, and DAG dependencies:

```bash
det validate <pipeline_or_project>
```

### `det doc`
Generates interactive documentation with SVG/Mermaid DAG diagrams and column contracts:

```bash
det doc <pipeline_or_project>
```

### `det inspect`
Inspects a catalog connection, schema, and displays a sample row preview:

```bash
det inspect <connection_name> [--rows 10]
```

---

## 🖥️ Web IDE Interface & Modules

The `det` Web IDE offers a clean, dual-pane architecture:

1. **Explorer Bar**:
   - Filter and search projects and pipeline models
   - Persistent bottom settings access for common **Storage Sinks Configuration**
2. **Secondary Collapsible Panel**:
   - **Execution Telemetry**: Run history, stage durations, and row metrics
   - **Quarantine Explorer**: Inspection of quarantined rows and validation failure details
   - **Data Quality Audits**: Pass/fail status across `not_null`, `unique`, and conditional rules
3. **DAG Lineage Visualizer**:
   - Interactive SVG/Mermaid graph reflecting transformation flow and upstream dependencies
4. **Interactive SQL Editor**:
   - Fast in-browser SQL authoring with real-time execution
   - *Roadmap*: Native in-editor autocompletion and Language Server Protocol (LSP) diagnostics

### Keyboard Shortcuts
- `Ctrl + Enter` (or `Cmd + Enter`): Run active SQL query or pipeline
- `Escape`: Close modals and inspection drawers

---

| ⬅️ Previous Page | 🏠 Overview | Next Page ➡️ |
| :--- | :---: | ---: |
| [**← Custom Connectors Guide**](Custom-Connectors-Guide) | [**Wiki Index**](Home) | [**Back to Home ➔**](Home) |
