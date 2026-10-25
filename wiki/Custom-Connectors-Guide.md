# Custom Connectors Guide

`det` is designed to be fully extensible. You can integrate any internal database, cloud service, API, or proprietary file format by registering custom extensions.

---

## 🛠️ Connector Architecture

A connector consists of two primary parts:
1. **Connector Definition**: Metadata (name, label, options fields, description, supported capabilities).
2. **Mount / Scan / Sink Handler**: Python function that receives the DuckDB session and connection options to register a view or write data.

---

## 📝 Example: Authoring a Custom SQLite Connector

Below is a concise implementation of a custom SQLite connector:

```python
import sqlite3
from typing import Any
import duckdb

from det.extensions.base import BaseExtension, ExtensionDefinition

class SQLiteExtension(BaseExtension):
    def definition(self) -> ExtensionDefinition:
        return ExtensionDefinition(
            name="sqlite_custom",
            label="Custom SQLite Connector",
            description="Mounts local SQLite databases into DuckDB session",
            fields=["db_path", "table_name"],
        )

    def mount(self, con: duckdb.DuckDBPyConnection, options: dict[str, Any], view_name: str) -> None:
        db_path = options["db_path"]
        table_name = options["table_name"]
        con.execute(f"ATTACH '{db_path}' AS sqlite_db (TYPE SQLITE)")
        con.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM sqlite_db.{table_name}")
```

---

## 📦 Packaging Connectors

Custom connectors can be maintained:
1. Inside your workspace's `extensions/` directory (automatically loaded by `det`).
2. Packaged as a standalone Python library exposing an `entry_point` in `pyproject.toml`:

```toml
[project.entry-points."det.extensions"]
my_connector = "my_package.connector:MyExtension"
```

---

| ⬅️ Previous Page | 🏠 Overview | Next Page ➡️ |
| :--- | :---: | ---: |
| [**← Cloud Lakehouse Connectors**](Cloud-Lakehouse-Connectors) | [**Wiki Index**](Home) | [**CLI & Web IDE Reference ➔**](CLI-&-Web-IDE-Reference) |
