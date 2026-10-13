# 🚀 Official LinkedIn Announcement Post

*Copy and paste the text below directly into your LinkedIn post. You can attach either the 96s official demo video (`det_official_demo.mp4`), the PDF carousel (`det_linkedin_carousel.pdf`), or the 3D announcement visual (`det_3d_announcement_visual.jpg`).*

---

What if you could build complete, production-grade ETL pipelines in Pure SQL… without Jinja templates, without a database server, and without heavy cloud bills?

Today, I’m excited to launch **det (Data Engineering Tool)** — a fast, local-first SQL ETL workspace and multi-step pipeline engine powered by **Apache DataFusion** and **Apache Arrow**. ⚡

📦 PyPI: `pip install det-core`
⭐ GitHub: https://github.com/det-Labs/det
🌐 Interactive Web IDE (Zero-Install): https://det-labs.github.io/det/demo.html

---

### 💡 Why we built det:

Data teams love SQL. But modern tools made it needlessly complex:
• dbt forces you into Jinja macro spaghetti just to chain models together.
• You have to pay heavy cloud database taxes (Snowflake / BigQuery compute) just to run simple staging transformations.
• Joining raw files across different formats requires separate ingestion tooling before you can even write a query.
• Models are locked into writing to only one target table per file.

**det changes this paradigm completely:**

### 1. 🧩 Pure ANSI SQL — No Jinja, No Template Fatigue
Write standard SQL. Every intermediate pipeline step automatically registers as an in-engine virtual view for subsequent steps. No `{{ ref(...) }}`, no macro debugging, and no mental overhead.

### 2. 📁 Multi-Source Extraction in a Single Query
Unlike dbt (which expects all data to already live in one warehouse), `det` queries and joins across heterogeneous formats directly on your filesystem:
👉 Parquet • Delta Lake (ACID) • Multi-sheet Excel (.xlsx) • CSV • JSON • NDJSON • XML.
You can literally join an Excel quota sheet with a Delta Lake orders table in one standard `JOIN`.

### 3. ⚡ Zero Database Backend Needed (In-Engine Vectorized Compute)
`det` doesn’t require spinning up Postgres, DuckDB server, or cloud data warehouses. It embeds **Apache DataFusion** (an industrial-grade vectorized query engine written in Rust) and executes multi-threaded queries on **Apache Arrow** columnar memory at bare-metal CPU speeds.

### 4. 🎯 Load to Multiple Destinations Simultaneously
dbt and SQLMesh tie one model to one output table. In `det`, a single pipeline step can publish directly to multiple destinations:
• Parquet Lakehouse (snappy/zstd)
• Delta Lake ACID Table (append/overwrite)
• Clean CSV exports for business stakeholders

### 5. 🖥️ Zero-Install Visual Web IDE (`det gui`)
Prefer visual workflows? Run `det gui` to launch our built-in browser interface featuring:
• Interactive visual Mermaid DAG topology maps
• Real-time SQL editor with pre-flight schema validation
• Data catalog previews with instant tabular data inspection
• Sub-second step duration telemetry and execution monitoring
• One-click living HTML/Markdown documentation generation

---

### 🚀 Get started in 30 seconds:

```bash
pip install det-core
det sample-data    # Unpacks the full NovaMart Global sample warehouse
det gui            # Launches the visual IDE in your browser
```

Or test drive the full Web IDE right now without installing anything:
👉 **Live Browser Showcase:** https://det-labs.github.io/det/demo.html

We’ve published complete architecture deep-dives, custom connector tutorials, and CLI guides on our new **GitHub Wiki**: https://github.com/det-Labs/det/wiki

I’d love to hear your thoughts, feedback, and what custom connectors you'd like to see next! If you find it helpful, dropping a ⭐ on GitHub means the world to our team.

---

#DataEngineering #ApacheDataFusion #ApacheArrow #SQL #dbt #SQLMesh #Python #ETL #OpenSource #AnalyticsEngineering #DataWarehouse #LocalFirst
