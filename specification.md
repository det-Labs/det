# TECHNICAL ARCHITECTURE & ENGINEERING SPECIFICATION (v3.0 - ENTERPRISE)
**System Identifier:** Polaris-DAG Engine  
**Core Runtime:** Rust Native (`polars`, `arrow2`, `tokio`, `rayon`)  
**High-Level Interface:** Python 3.10+ Native Package (`polaris-dag`) & Rust CLI  
**Execution Paradigm:** Out-of-Core, In-Memory Zero-Copy Streaming DAG

---

## 1. System Vision & Foundational Tenets

Polaris-DAG is a unified data processing framework that unifies **Extraction, Transformation (Modeling), Quality Testing, and Loading/Reverse-ETL** into a single DAG execution lifecycle.

### Core Principles
1. **Zero External Warehouse Overhead:** Computation runs locally or on compute nodes via Polars, avoiding cloud data warehouse provisioning costs and JVM bloat.
2. **Unified Lifecycle DAG:** Extraction, intermediate modeling, testing, and sinks operate within a single execution graph.
3. **Rust Speed with Python Usability:** The execution core, memory scheduler, and I/O run entirely in Rust. Python users interact with a native Python API (`import polaris`) and can author models using Python Polars without paying serialization penalties.
4. **Resilient Zero-Copy Boundaries:** Data interchange between Rust, C drivers, and Python uses the **Apache Arrow C Data Interface** in-process, with an optional **POSIX Shared Memory (`/dev/shm`)** mode for out-of-process isolation.

---

## 2. In-Memory & IPC Interchange Architecture

To achieve low-latency data handoffs while remaining accessible to Python developers, Polaris implements a two-tier execution runtime:

```
[ Tier 1: In-Process Native C-ABI Bridge (Default) ]
 Rust Engine Core (Polars) <── PyO3 FFI / Arrow C Data Interface ──> In-Process Python Runtime
                             (Zero-Copy Pointer Handshake)

[ Tier 2: Isolated Out-of-Process Worker Bridge (Fault-Tolerant) ]
 Rust Engine Core ─────────► POSIX Shared Memory (/dev/shm) ◄──────── Python Worker Process
 (Parent Process)            (Arrow IPC Ring Buffers)                (Child Process)
```

### 2.1 Tier 1: In-Process Zero-Copy C Data Interface
For standard, trusted models, Python executes within the process space using a PyO3 bridge.
- **Pointer Handshake:** DataFrames are converted directly between Polars Rust and Python Polars by exporting and importing the `FFI_ArrowArray` and `FFI_ArrowSchema` pointers.
- **Zero Allocation:** Neither columns nor records are copied or serialized; only memory addresses and ownership flags are exchanged.
- **Reference Protection:** Rust implements custom destructors wrapped in Python Capsule objects (`PyCapsule`), ensuring memory allocations remain pinned until Python releases the references.

### 2.2 Tier 2: Isolated POSIX Shared Memory Ring Buffer
For untrusted third-party Python code, C-extensions, or models with unpredictable memory profiles:
- Rust allocates a circular ring buffer inside `/dev/shm` (or memory-mapped shared files on Windows).
- Data batches are published as uncompressed **Arrow IPC Streams**.
- Python worker subprocesses map the shared file into memory, run user logic via Python Polars, and write the output back to the ring buffer.
- If a Python model crashes or encounters a segmentation fault, the main Rust engine intercepts the failure, logs the error, and fails the node cleanly without crashing the pipeline.

---

## 3. Resource Governance: Memory & CPU Scheduling

### 3.1 Three-Zone Memory Governor
To prevent Out-Of-Memory (`OOMKilled`) panics during memory-intensive operations, the engine tracks allocations using `jemalloc` hooks against host RAM:

```
0% ──────────── 70% ───────────────────── 85% ───────────────────── 100%
     GREEN ZONE           YELLOW ZONE                 RED ZONE
 [In-Memory Compute]   [Spill-to-Disk / Streaming]   [Pipeline Throttled / Paused]
```

- **Green Zone (< 70% RAM Used):** Fully in-memory operations using `LazyFrame::collect()`.
- **Yellow Zone (70% - 85% RAM Used):** Engine shifts execution plans to streaming mode (`LazyFrame::sink_parquet()` or `collect_streaming()`). New node starts are queued until memory recedes.
- **Red Zone (> 85% RAM Used):** The execution scheduler freezes upstream node tasks, unloads cached intermediate buffers to temporary local Arrow IPC files, and pauses extraction streams.

### 3.2 Dynamic Rayon Thread Budgeting
To prevent thread contention between concurrent DAG nodes:
- The system checks available logical CPU cores ($N_{cores}$).
- Independent DAG nodes do not contest all cores simultaneously.
- A **Thread Pool Governor** divides worker allocations dynamically:
  $$\text{Threads Per Node} = \max\left(1, \left\lfloor \frac{N_{cores}}{\text{Active Concurrent Nodes}} \right\rfloor\right)$$
- If a single critical-path node is running, it scales up to use all available cores.

---

## 4. Dual Transformation Paradigms: SQL vs. Expression Chains

Analysts and engineers can choose their modeling language on a per-model basis.

### 4.1 ANSI SQL Models (`models/*.sql`)
- Evaluated via `polars::sql::SQLContext`.
- Supports Jinja parameterization for dependency management:
  - `{{ ref('model_or_source_name') }}`
  - `{{ config(materialized='table') }}`
- Dependencies are automatically registered as lazy table references in the SQL context.

```sql
-- models/marts/fct_daily_revenue.sql
{{ config(materialized='table') }}

WITH orders AS (
    SELECT * FROM {{ ref('src_postgres_orders') }}
    WHERE status = 'COMPLETED'
),
rates AS (
    SELECT * FROM {{ ref('src_s3_currency_rates') }}
)
SELECT 
    o.order_date,
    o.currency,
    SUM(o.amount * r.exchange_rate) AS total_revenue_usd,
    COUNT(o.order_id) AS transaction_count
FROM orders o
JOIN rates r ON o.currency = r.currency AND o.order_date = r.date
GROUP BY o.order_date, o.currency
```

### 4.2 Polars Expression Chain Models (`models/*.py` or `models/*.rs`)
- Designed for pipelines requiring complex logic: windowing, list/struct unnesting, machine learning scoring, or custom array manipulations.

```python
# models/marts/fct_user_retention.py
import polars as pl
from polaris import ModelContext

def model(ctx: ModelContext) -> pl.LazyFrame:
    orders_lf: pl.LazyFrame = ctx.ref("src_postgres_orders")
    
    return (
        orders_lf
        .filter(pl.col("status") == "COMPLETED")
        .sort(["user_id", "order_date"])
        .with_columns([
            pl.col("order_date").diff().over("user_id").dt.total_days().alias("days_since_last_order"),
            pl.col("order_id").cum_count().over("user_id").alias("order_sequence_number")
        ])
    )
```

---

## 5. Unified Pluggable Adapters (Sources & Sinks)

Static seed files are replaced with a uniform Adapter Architecture. Sources and Sinks exist as declarative nodes within the project configuration.

### 5.1 Source Declarations (`sources/sources.yml`)
Data can be read directly from files, cloud object stores, or databases without manual file uploads:

```yaml
version: 1
sources:
  - name: src_postgres_orders
    adapter: postgres
    connection: env(DB_URI_POSTGRES)
    query: |
      SELECT order_id, user_id, amount, currency, status, order_date 
      FROM core_orders
    partition_column: order_id
    partitions: 8  # Parallel chunked reads via ConnectorX directly to Arrow

  - name: src_s3_currency_rates
    adapter: file
    path: "s3://lakehouse-raw/finance/rates/*.parquet"
    storage_options:
      aws_region: "us-east-1"
    format: parquet
    scan_strategy: lazy  # Projection & filter pushdown supported
```

### 5.2 Multi-Sink Declarations (`sinks/sinks.yml`)
Models can fan out to multiple destinations (data lakes and operational databases) in a single run:

```yaml
version: 1
sinks:
  - name: export_lakehouse_iceberg
    source_model: fct_daily_revenue
    adapter: lakehouse
    format: iceberg
    catalog: env(ICEBERG_CATALOG_URI)
    table: finance.fct_daily_revenue
    mode: merge
    merge_keys: [order_date, currency]

  - name: sync_operational_cache
    source_model: fct_daily_revenue
    adapter: postgres
    connection: env(APP_DB_URI)
    table: cached_daily_revenue
    mode: bulk_copy  # Streams Arrow directly via Postgres binary COPY protocol
```

---

## 6. Automated Testing & Quality Gates

Data validation assertions execute in memory against Arrow buffers before downstream sinks run.

### 6.1 Declarative Schema Tests (`models/schema.yml`)
```yaml
version: 1
models:
  - name: fct_daily_revenue
    columns:
      - name: order_date
        tests:
          - not_null
      - name: total_revenue_usd
        tests:
          - not_null
          - range:
              min: 0.0
              severity: error
```

### 6.2 Test Execution Model
Tests compile into Polars boolean filter plans:
```rust
// Internally executed test evaluation
let violations_df = lazy_frame
    .select([
        col("order_date").is_null().sum().alias("null_order_date"),
        col("total_revenue_usd").is_null().sum().alias("null_revenue"),
        (col("total_revenue_usd").lt(lit(0.0))).sum().alias("negative_revenue_violations"),
    ])
    .collect()?;
```
- **Error Failure:** Any test failure marked with `severity: error` triggers a pipeline rollback: downstream Sinks for that branch are canceled immediately.
- **Warning Thresholds:** Soft assertions (`severity: warn`) emit structured alert logs to the console and UI without stopping the pipeline.

---

## 7. Triple-Modality Documentation Generator

The documentation engine inspects SQL/Python ASTs, markdown descriptions, column data types, and DAG topologies, exporting documentation in three formats:

1. **Self-Contained Single HTML (`single-html`):**
   - Bundles all HTML, CSS, JavaScript, and project metadata into one standalone `.html` file.
   - Includes an interactive node graph visualizer (lineage explorer) and offline search index.
   - Operates with zero web server dependencies (can be opened directly from local disk).
2. **Static SPA Site (`site`):**
   - Builds a static web application (`docs/dist/`) designed for hosting on S3, GitHub Pages, or internal portals.
   - Supports search indexing, column-level lineage tracking, and live schema previews.
3. **Markdown Documentation Tree (`markdown`):**
   - Outputs a standard directory structure of `.md` files matching the project layout.
   - Injects embedded **Mermaid.js** lineage diagrams for rendering directly on GitHub and GitLab:
     ```mermaid
     graph LR
       src_pg[src_postgres_orders] --> fct_rev[fct_daily_revenue]
       src_s3[src_s3_currency_rates] --> fct_rev
       fct_rev --> sink_iceberg[export_lakehouse_iceberg]
       fct_rev --> sink_pg[sync_operational_cache]
     ```

---

## 8. Frontend UI & IDE Integration Contract (JSON-RPC 2.0)

The engine provides a JSON-RPC 2.0 interface over WebSockets / IPC for client integrations, visual frontends, and IDE extensions.

### 8.1 DAG Structure Query
**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "dag:inspect",
  "id": 101
}
```
**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 101,
  "result": {
    "nodes": [
      {
        "id": "src_orders",
        "type": "source",
        "adapter": "postgres",
        "name": "src_postgres_orders"
      },
      {
        "id": "model_revenue",
        "type": "model",
        "language": "sql",
        "name": "fct_daily_revenue"
      },
      {
        "id": "sink_iceberg",
        "type": "sink",
        "adapter": "lakehouse",
        "name": "export_lakehouse_iceberg"
      }
    ],
    "edges": [
      { "from": "src_orders", "to": "model_revenue" },
      { "from": "model_revenue", "to": "sink_iceberg" }
    ]
  }
}
```

### 8.2 Real-Time Execution Metric Stream
**Event:**
```json
{
  "jsonrpc": "2.0",
  "method": "pipeline:telemetry",
  "params": {
    "node_id": "model_revenue",
    "state": "running",
    "rows_processed": 2500000,
    "memory_used_bytes": 481296384,
    "memory_zone": "green",
    "threads_active": 8,
    "current_operator": "hash_join"
  }
}
```

### 8.3 Documentation Generation Trigger
**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "docs:build",
  "params": {
    "format": "single-html",
    "output_path": "./dist/polaris_docs.html"
  },
  "id": 102
}
```
**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 102,
  "result": {
    "status": "success",
    "output_file": "./dist/polaris_docs.html",
    "size_bytes": 2145890
  }
}
```

### Implementation Sequence & Next Steps

Phase 1: Foundations & Memory Governance
  ├── Implement Petgraph DAG compiler with cycle detection
  ├── Configure Jemalloc hooks and the 3-Zone Memory Governor
  └── Build Rayon Thread Governor with isolated node sub-pools

Phase 2: Adapter Engine & Ingestion
  ├── Implement SourceAdapter and SinkAdapter traits
  ├── Build ConnectorX streaming wrapper using Arrow C FFI
  └── Implement Tokio-PG binary COPY bulk loader

Phase 3: Transformation Engine & Tests
  ├── Wire Polars SQLContext with Jinja template expansion
  ├── Build isolated Python worker runner using POSIX shared memory
  └── Implement assertion compiler for generic/singular tests

Phase 4: Multi-Format Docs & UI Bridge
  ├── Build Single-HTML, Static SPA, and Markdown doc generators
  ├── Stand up JSON-RPC 2.0 bidirectional server (stdio / WS)
  └── Wire telemetry events and graph structures into visual ui