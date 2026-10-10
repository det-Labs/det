# det

A modular, Python-first data engineering framework.

## Overview

`det` combines a dbt-inspired workflow with native Python and SQL data processing (Polars, DuckDB), multi-source extraction, and multi-destination publishing, paired with CLI and visual tooling (GUI).

## Development Setup

```bash
# Create virtual environment (Python >= 3.14)
py -3.15 -m venv .venv
.venv\Scripts\activate

# Install in editable mode
pip install -e ".[dev]"

# Run tests
pytest
```

## License

Apache License 2.0.
