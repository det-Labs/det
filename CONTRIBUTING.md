# Contributing to det

Thank you for your interest in contributing to **det** (Data Engineering Tool)! We welcome contributions from data engineers, software developers, technical writers, and open-source enthusiasts.

This document outlines the workflow, coding standards, and guidelines for contributing to `det`.

---

## Core Directives

All contributions, design proposals, and pull requests are evaluated against our three architectural tenets:

1. **🧩 Modularity:** Keep modules cleanly separated. Connectors, execution logic, catalog store, and UI layers must remain decoupled and testable in isolation.
2. **⚡ Performance:** Leverage Apache DataFusion and Apache Arrow vectorized columnar operations. Avoid unnecessary serialization, intermediate disk dumps, or single-threaded bottlenecks.
3. **🔌 Extensibility:** Prefer plugin-friendly interfaces (`BaseConnector`, `ConnectorRegistry`) and declarative YAML/SQL schemas that empower users to extend functionality without modifying engine internals.

---

## Code of Conduct

All contributors and participants are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please report any unacceptable behavior to [saurabhr2@gmail.com](mailto:saurabhr2@gmail.com).

---

## Ways to Contribute

There are many ways to contribute to `det`:

1. **Build Custom Connectors:** Implement new data source/sink connectors (e.g., PostgreSQL, MySQL, ClickHouse, Snowflake, S3, REST APIs) using our `BaseConnector` plugin architecture.
2. **Improve Documentation:** Fix typos, add tutorials, expand docstrings, or write real-world ETL pipeline examples.
3. **Report Bugs:** Submit reproducible bug reports using our [Bug Report Template](https://github.com/det-Labs/det/issues/new?template=bug_report.yml).
4. **Propose Features:** Share ideas or architectural proposals using our [Feature Request Template](https://github.com/det-Labs/det/issues/new?template=feature_request.yml).
5. **Optimize Engine Performance:** Enhance Apache DataFusion query planning, Arrow memory utilization, or caching mechanisms.

---

## Development Setup

### Prerequisites

- **Python 3.14+**
- **Git**
- A virtual environment tool (`venv`, `uv`, or `conda`)

### Step-by-Step Environment Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/det.git
   cd det
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install `det` in editable mode with development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify the installation by running the test suite:**
   ```bash
   python -m unittest discover -s tests
   ```
   All tests should pass cleanly without errors or file system mutations.

---

## Authoring Custom Connectors

`det` is built from the ground up to be easily extensible. Every connector implements the `BaseConnector` abstract interface located in `src/det/connectors.py`.

### The `BaseConnector` Specification

```python
from det.connectors import BaseConnector, ConnectorRegistry
import pyarrow as pa
from typing import Dict, Any

class CustomDBConnector(BaseConnector):
    """Connector for querying external database systems."""

    guid = "custom-db"
    name = "Custom Database Connector"
    description = "Reads tables from Custom DB into Apache Arrow RecordBatches."
    is_readable = True
    is_writable = False

    def scan(self, options: Dict[str, Any], context: Any, workspace: Any) -> pa.Table:
        """
        Executes query or scans data, returning a PyArrow Table or DataFusion DataFrame.
        """
        table_name = options.get("table")
        connection_url = options.get("url")
        
        # 1. Connect to data source
        # 2. Ingest into Apache Arrow format
        # arrow_table = ...
        
        # 3. Register table with DataFusion context
        context.register_record_batches(table_name, [arrow_table.to_batches()])
        return arrow_table

    def write(self, arrow_table: pa.Table, options: Dict[str, Any], workspace: Any) -> None:
        """Writes PyArrow Table to destination storage."""
        if not self.is_writable:
            raise NotImplementedError("This connector does not support write operations.")
```

### Registering Your Connector

Register your connector with the global `ConnectorRegistry`:

```python
ConnectorRegistry.register(CustomDBConnector())
```

Once registered, your connector can be referenced in any `catalog/*.yaml` file using the `type: custom-db` directive.

---

## Git Workflow & Pull Requests

### Branching Strategy

- Always create your feature or bug fix branch from `main`:
  ```bash
  git checkout main
  git pull origin main
  git checkout -b feat/my-new-connector
  ```

### Conventional Commit Messages

We enforce standard [Conventional Commits](https://www.conventionalcommits.org/) format:

- `feat:` A new feature or connector (e.g., `feat(connectors): add ClickHouse connector`)
- `fix:` A bug fix (e.g., `fix(engine): handle null values in Excel date parsing`)
- `docs:` Documentation only changes (e.g., `docs: update quickstart guide`)
- `test:` Adding or refactoring tests (e.g., `test: add unit test for Delta Lake partition scanner`)
- `refactor:` Code change that neither fixes a bug nor adds a feature
- `perf:` Performance improvements
- `chore:` Maintenance tasks, dependency updates, CI workflows

### Submitting a Pull Request

1. Push your branch to your GitHub fork:
   ```bash
   git push origin feat/my-new-connector
   ```
2. Open a Pull Request against `det-Labs/det` on branch `main`.
3. Complete the PR checklist provided in the [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md).
4. Ensure all CI automated tests pass.
5. Address any review feedback promptly.

---

## Coding Standards & Integrity

- **Python Standards:** Follow PEP 8 guidelines. Write clear, type-annotated code wherever possible.
- **Clean Architecture:** Keep core modules decoupled (`engine`, `connectors`, `catalog`, `pipeline`, `runner`, `docs`, `gui`).
- **Tests First:** Any new feature, connector, or bug fix must include corresponding unit tests in the `tests/` directory. Tests must execute cleanly in isolated temporary workspaces (`tempfile.mkdtemp()`) without writing files to the repository root.
- **Documentation:** When introducing new configuration keys or CLI commands, update the relevant docstrings, Help articles in `src/det/ui/index.html`, and `README.md`.

---

## Maintainers

Project Owner: **Saurabh Rai** ([saurabhr2@gmail.com](mailto:saurabhr2@gmail.com)) & **det-Labs**
