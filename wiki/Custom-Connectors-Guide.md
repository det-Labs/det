# Custom Connectors Guide

`det` is designed to be fully extensible. You can integrate any internal database, cloud service, API, or proprietary file format by registering custom connectors.

---

## 🛠️ Connector Architecture

A connector consists of two primary parts:
1. **Connector Definition**: Metadata (name, label, options fields, description, supported roles).
2. **Scan / Sink Handler**: Python function that receives the DataFusion `SessionContext` and connection options to register a view or write data.

---

## 📝 Example: Authoring a Custom SQLite Connector

Below is a complete implementation of a custom SQLite connector:

```python
import sqlite3
from typing import Any
import pyarrow as pa
from datafusion import SessionContext, DataFrame

from det.connectors import ConnectorDefinition, ConnectorField, register_connector

def scan_sqlite(
    ctx: SessionContext, 
    view_name: str, 
    options: dict[str, Any], 
    saved_columns: list[dict[str, Any]] | None
) -> DataFrame:
    db_path = options["db_path"]
    table_name = options["table_name"]
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]
    conn.close()
    
    # Convert to Arrow Table
    pydict = {col: [row[i] for row in rows] for i, col in enumerate(col_names)}
    table = pa.Table.from_pydict(pydict)
    
    # Register view in DataFusion
    ctx.register_record_batches(view_name, [table.to_batches()])
    return ctx.table(view_name)

# Register connector definition
register_connector(
    ConnectorDefinition(
        id="sqlite-custom-guid",
        label="SQLite Database",
        description="Local relational SQLite database connector.",
        is_source=True,
        is_destination=False,
        fields=[
            ConnectorField(name="db_path", label="Database File Path", field_type="text", required=True),
            ConnectorField(name="table_name", label="Source Table Name", field_type="text", required=True),
        ],
        scanner=scan_sqlite,
    )
)
```

---

## 📦 Packaging Connectors

Custom connectors can be maintained:
1. Inside your workspace's `plugins/` directory
2. Packaged as a standalone Python library (e.g. `det-connector-snowflake`, `det-connector-bigquery`) exposing an `entry_point` in `pyproject.toml`:

```toml
[project.entry-points."det.connectors"]
snowflake = "det_snowflake.connector:register"
```

