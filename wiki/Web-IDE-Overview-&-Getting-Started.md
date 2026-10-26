# Web IDE Overview & Getting Started

`det` includes a built-in, local-first browser Web IDE designed for analytics engineers and data teams who want visual DAG design, interactive SQL authoring, and real-time data introspection without leaving their local workstation.

---

## ⚡ Zero-Install, Zero-Cloud Local Studio

Unlike cloud orchestrators that require complex Kubernetes clusters or SaaS accounts, the `det` Web IDE:
* Runs 100% locally on your machine powered by an embedded Python HTTP server and in-process **DuckDB 2.0**.
* Requires zero cloud configuration, zero external browser CDNs, and zero telemetry tracking.
* Works seamlessly across air-gapped corporate environments and local laptop workflows.

![det Web IDE Studio](images/02_pipeline_dag.png)

---

## 🚀 Launching the Web IDE

To start the Web IDE from your terminal inside any `det` project directory:

```bash
det gui
```

By default, the server binds to `http://127.0.0.1:8080`.

### CLI Launch Flags

| Flag | Shorthand | Description | Default |
| :--- | :--- | :--- | :--- |
| `--port <int>` | `-p` | TCP port to host the Web IDE server | `8080` |
| `--open` | `-o` | Automatically launch default browser on startup | `False` |

```bash
# Launch on custom port and open browser automatically
det gui --port 9000 --open
```

---

## 🧭 Interface Layout & Architecture

The Web IDE features an intuitive 4-tier interface:

```
+-------------------------------------------------------------------------------+
| ⚡ det v0.3.3   [Catalog]  [Pipelines]  [Monitoring]  [Docs]    [Theme] ● Ready |
+-----------------------+-------------------------------------------------------+
|  PRIMARY EXPLORER     |  MAIN WORKSPACE STAGE                                 |
|                       |                                                       |
|  📁 sample_pipelines  |  ⚡ Command Ribbon: [+ Model] [Compile] [Test] [Run]  |
|    retail_medallion   |                                                       |
|    export_analytics   |  ┌─────────────────────────────────────────────────┐  |
|                       |  │ Interactive DAG Canvas (Pan & Zoom Lineage)     │  |
|  📁 Models            |  └─────────────────────────────────────────────────┘  |
|    bronze_customers   |                                                       |
|    silver_orders      |  ┌─────────────────────────────────────────────────┐  |
|    gold_metrics       |  │ SQL Model Editor (Clean SQL vs Compiled SQL)    │  |
|                       |  └─────────────────────────────────────────────────┘  |
|                       |                                                       |
|                       |  ┌─────────────────────────────────────────────────┐  |
|                       |  │ Column Schemas & Test Assertions Table          │  |
|                       |  └─────────────────────────────────────────────────┘  |
+-----------------------+-------------------------------------------------------+
```

1. **Top Navigation Bar**: Switch between the 4 core developer modules (**Catalog**, **Pipelines**, **Monitoring**, **Docs**), toggle themes, and monitor connection status.
2. **Primary Explorer Sidebar**: Search and organize pipelines, models, folders, and catalog data sources. Can be collapsed with one click to expand workspace real estate.
3. **Command Ribbon**: Instant action buttons to add models, compile Jinja macros, execute test assertions, generate docs, or run entire pipelines.
4. **Collapsible Stage Cards**: The central stage arranges the **Dependency Graph**, **SQL Editor**, and **Schema & Assertions** into clean collapsible cards with independent maximize/minimize controls.

---

## 🎓 Interactive Guided Tour & Demo Mode

If you are exploring `det` for the first time, you can launch an instant demo environment with realistic e-commerce datasets and pre-configured Medallion pipelines:

```bash
# Scaffold and run demo workspace in one command
det demo my_demo_workspace
cd my_demo_workspace
det gui --open
```

Inside the Web IDE, click the **Demo Mode** button in the header bar at any time to launch a 60-second guided interactive walkthrough highlighting key platform capabilities.

---

## ⌨️ Essential Keyboard Shortcuts

* `Ctrl + Enter` (or `Cmd + Enter`): Execute the current SQL model or Scratchpad query.
* `ArrowLeft` / `ArrowRight`: Navigate between active tabs or views.
* `Escape`: Dismiss modals and drawers.

---

| ⬅️ Previous Page | 🏠 Overview | Next Page ➡️ |
| :--- | :---: | ---: |
| [**← CLI & Web IDE Reference**](CLI-&-Web-IDE-Reference) | [**Wiki Index**](Home) | [**Web IDE: Pipelines & DAG Studio ➔**](Web-IDE-Pipelines-&-DAG-Studio) |
