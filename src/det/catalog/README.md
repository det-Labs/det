# <span style="color:#f45b00;">det</span>.catalog
### by <span style="color:#f45b00;">det</span> <span style="color:#5d5d5f;">Labs</span>

> **The Catalog & Metadata Engine for the <span style="color:#f45b00;">det</span> Data Engineering Framework**

The `det.catalog` module provides a lightweight, local-first, concurrency-safe data catalog. It discovers dataset schemas automatically, organizes tables into categories (namespaces), persists metadata into human-readable YAML files, and exposes both a Python programmatic Command API, a CLI, and an interactive local browser GUI.

---

## Key Features

- **Automated Schema Discovery**: Inactive or deferred inspection for Parquet, CSV/TSV, JSON/NDJSON, Excel, and directory datasets with row counts and typed column schemas.
- **Python 3.15 Native Lazy Imports**: Utilizes Python 3.15's native `lazy import` syntax for instant startup and deferred loading of heavy analytical libraries (Polars and PyArrow).
- **Concurrency-Safe & Atomic Persistence**: Backed by `ruamel.yaml` and `filelock` with atomic file replacements, ensuring multiple processes or GUI sessions never corrupt catalog files.
- **Hierarchical Namespaces / Categories**: Organize tables into logical business domains (e.g., `bronze`, `silver`, `gold`, `finance`, `marketing`) with cascade reassignments on deletion.
- **Multiple Catalogs & Default Switching**: Create new catalog YAML files, switch between existing ones, and set default catalogs that load automatically across sessions.
- **Interactive Web GUI**: Single-page application served via FastAPI with an explorer sidebar, draggable resizer, circular action badges, schema modals, inline column description editing, and a 3-way theme switcher (Light / Dark / Auto System).

---

## Installation & Requirements

- **Python**: `>= 3.15` (Stable)
- **Dependencies**: `polars`, `pyarrow`, `pydantic`, `ruamel.yaml`, `filelock`, `fastapi`, `uvicorn`, `typer`

```bash
# Install det with catalog support in editable mode
pip install -e .

# Or with dev dependencies (pytest, ruff, httpx)
pip install -e ".[dev]"
```

---

## Programmatic Python API

The `CatalogService` is the core command service underpinning all catalog actions.

```python
from pathlib import Path
from det.catalog import CatalogService, DatasetMetadata

# 1. Initialize service with active catalog (or default from .det/config.json)
service = CatalogService("catalogs/main.yaml")

# 2. Discover schema automatically from a file or folder
scan_result = service.scan_path("data/orders.parquet")
print(f"Format: {scan_result.format}, Rows: {scan_result.row_count}")
for col in scan_result.columns:
    print(f" - {col.name}: {col.type} (nullable={col.nullable})")

# 3. Register a table into a category
dataset = DatasetMetadata(
    id="sales.orders",
    name="orders",
    namespace="sales",
    format="parquet",
    location="data/orders.parquet",
    description="Customer transactions and order records",
    columns=scan_result.columns,
    row_count=scan_result.row_count,
    tags=["raw", "ecommerce"]
)
service.register_dataset(dataset)

# 4. List, filter, or retrieve datasets
all_tables = service.list_datasets()
sales_tables = service.list_datasets(namespace="sales")
customer_tables = service.list_datasets(search="customer")
order_table = service.get_dataset("sales.orders")

# 5. Manage Categories / Namespaces
service.create_namespace("finance")
service.rename_namespace("sales", "commercial")
service.delete_namespace("commercial", reassign_to="default")

# 6. Re-scan table to detect schema evolution
updated_dataset = service.rescan_dataset("default.orders")

# 7. Create or Switch active catalog
service.create_catalog("catalogs/analytics.yaml", name="Analytics Catalog", set_as_default=True)
service.switch_catalog("catalogs/main.yaml")
```

---

## CLI Usage

The `det` command-line tool provides direct access to catalog operations:

```bash
# View CLI version and environment information
det version
det info

# List all registered datasets in the active catalog
det catalog list

# Scan any local file or directory to inspect its inferred schema
det catalog scan sample_data/customers.csv

# Set a catalog file as your default preference
det catalog set-default catalogs/main.yaml

# Launch the interactive Web GUI
det-gui
# Or specify custom host/port:
det-gui --port 8501 --host 127.0.0.1
```

---

## Interactive Local Browser Web GUI

Launch the catalog visual interface:

```bash
det-gui
```

Open `http://127.0.0.1:8501` in your browser to access:
- **Vertical Explorer**: Left hierarchical category/namespace tree with table counts.
- **Draggable Resizer**: Click and drag the vertical divider between the explorer and content pane to adjust sidebar width (double-click to reset to 340px).
- **Table Row Actions**: Circular action badges on every table item:
  - Cyan `↻`: Instant schema re-scan.
  - Blue `✏`: Edit table metadata & schema.
  - Red `✕`: Delete table from catalog.
- **Category Row Actions**:
  - Green `+`: Register a new table directly into that category.
  - Blue `✏`: Rename category.
  - Red `✕`: Delete category (cascade-reassigns tables to `default`).
- **Discover Schema**: Auto-infers types and row counts from files or directories with manual adjustments and column descriptions.
- **Inline Column Description Editing**: Click any column description in the schema view to edit it immediately without opening forms.
- **Catalog Switcher & Creator**: Dedicated modals to switch to existing catalogs or create new catalog YAML files.
- **3-Way Theme Switcher**: Toggle between **Auto (System)**, **Light**, and **Dark** modes in the top navigation.
- **Raw YAML Viewer**: Inspect the live YAML representation and copy it to your clipboard.

---

## Catalog YAML Schema Specification

All catalog information is serialized in an explicit, git-friendly YAML structure:

```yaml
catalog_version: 1
catalog_name: det_catalog
namespaces:
  - default
  - sales
datasets:
  - id: sales.orders
    name: orders
    namespace: sales
    format: parquet
    location: data/orders.parquet
    description: Customer orders and transaction records
    row_count: 10450
    last_scanned: '2026-10-10T06:00:00Z'
    tags:
      - ecommerce
      - transactions
    columns:
      - name: order_id
        type: Int64
        nullable: false
        description: Primary key for order
      - name: customer_id
        type: String
        nullable: false
        description: Foreign key referencing customer
      - name: amount
        type: Float64
        nullable: true
        description: Total order charge in USD
```
