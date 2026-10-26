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
det gui [--port 8080] [--open]
```

### `det demo`
Scaffolds an instant demo workspace populated with realistic e-commerce datasets and Medallion pipelines:

```bash
det demo [demo_dir]
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

## 🖥️ Deep-Dive Web IDE Visual Studio Guides

For comprehensive step-by-step guides on using each visual module in the Web IDE, consult the dedicated studio documentation:

* [**Web IDE Overview & Getting Started**](Web-IDE-Overview-&-Getting-Started): Launching, demo walkthrough, layout, and keyboard shortcuts.
* [**Web IDE: Pipelines & DAG Studio**](Web-IDE-Pipelines-&-DAG-Studio): Interactive DAG canvas, Dual-Mode SQL editor, and live model execution.
* [**Web IDE: Data Quality & Quarantine**](Web-IDE-Data-Quality-&-Quarantine): Visual assertion authoring, test badges, and non-blocking quarantine audits.
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
