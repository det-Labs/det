# Contributing to det

Thank you for your interest in contributing to **det** (Data Engineering Tool)! We welcome contributions from data engineers, software developers, technical writers, and open-source enthusiasts.

This document outlines the workflow, coding standards, and guidelines for contributing to `det`.

---

## Core Directives

All contributions, design proposals, and pull requests are evaluated against four architectural tenets:

1. **🧩 Modularity & Clean Design:** Keep modules cleanly separated. Engine sessions, catalog store, topological runner, documentation generator, telemetry sinks, and Web IDE interfaces must remain decoupled and independently testable.
2. **⚡ Vectorized Performance:** Leverage embedded DuckDB 2.0 and Apache Arrow columnar capabilities. Maintain sub-second iteration speed and avoid unnecessary serialization or blocking operations.
3. **🔌 Extensibility:** Prefer plugin-friendly interfaces (`BaseConnector`, `BaseTelemetrySink`) and declarative YAML/SQL schemas that empower engineers to extend functionality seamlessly.
4. **📐 Codebase Discipline:** Follow strict file limits ($\le 250$ lines per file, $\le 40$ lines per function) and native zero-dependency DOM/CSS practices in the Web IDE.

---

## Code of Conduct

All contributors and participants are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please report any unacceptable behavior to [saurabhr2@gmail.com](mailto:saurabhr2@gmail.com).

---

## Ways to Contribute

There are many ways to contribute to `det`:

1. **Build Custom Connectors:** Implement new data source/sink connectors (e.g. Snowflake, BigQuery, ClickHouse, REST APIs) using our `BaseConnector` plugin architecture in `src/det/catalog/base.py`.
2. **Pluggable Telemetry Sinks:** Add support for additional telemetry and logging providers (e.g. OpenTelemetry, CloudWatch, Datadog) using `BaseTelemetrySink`.
3. **Web IDE & SQL Editor Autocompletion:** Contribute to the upcoming smart SQL autocompletion, context-aware `{{ ref() }}` / `{{ source() }}` suggestions, and in-browser Language Server Protocol (LSP).
4. **Improve Documentation:** Fix typos, add tutorials, expand docstrings, or write real-world ETL pipeline examples.
5. **Report Bugs & Propose Features:** Submit reproducible bug reports or ideas using our GitHub Issue templates.

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
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install `det` in editable mode with development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Run the automated test suite:**
   ```bash
   pytest
   ```
   All 108 unit and integration tests should pass cleanly without errors or file system mutations.

---

## Authoring Custom Connectors

`det` is built from the ground up to be easily extensible. Every connector implements the `BaseConnector` abstract interface located in `src/det/catalog/base.py`:

```python
from det.catalog.base import BaseConnector, ConnectionTier, ConnectorParameter

class CustomLakeConnector(BaseConnector):
    """Custom connector for specialized lakehouse storage."""

    type_name = "custom_lake"
    tier = ConnectionTier.LAKEHOUSE
    description = "Vectorized scanner for custom lakehouse storage format."
    parameters = [
        ConnectorParameter("table_uri", "string", "Target URI", is_required=True),
    ]

    def get_read_sql(self, options: dict) -> str:
        """Generate SQL fragment for vectorized scanning."""
        uri = options.get("table_uri", "")
        return f"read_parquet('{uri}')"
```

---

## Pull Request Guidelines

1. **Keep Pull Requests Focused:** Aim for single, cohesive features or fixes.
2. **Add Tests:** Ensure every bug fix or new feature includes corresponding unit tests in `tests/`.
3. **Verify Constraints:**
   - Run `pytest` to verify all tests pass.
   - Maintain file length $\le 250$ lines and function length $\le 40$ lines.
4. **Maintain Documentation Integrity:** Update docstrings, user guides, or README sections relevant to your changes.

---

## License & Attribution

By contributing to `det`, you agree that your contributions will be licensed under its [MIT License](LICENSE).
