// =============================================================================
// det - Help & Documentation Portal Topics (Microsoft Learn Architecture)
// =============================================================================

window.HELP_CATEGORIES = [
  {
    id: "overview",
    title: "Overview & Architecture",
    topics: [
      {
        id: "intro",
        title: "Introduction to det",
        readTime: "3 min read",
        summary: "Understand det's local-first, headless-by-design architecture, embedded Apache DataFusion engine, and core data engineering principles.",
        content: `
          <p class="lead"><strong>det</strong> is a modern, local-first, headless-by-design data engineering toolkit and orchestration engine. It combines declarative SQL pipelines and YAML catalogs with the blazing performance of the Apache DataFusion execution engine.</p>

          <div class="help-callout is-note">
            <div class="help-callout-header">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              <span>NOTE</span>
            </div>
            <p>det is designed to be <strong>zero-dependency for cloud databases</strong>: you do not need Snowflake, BigQuery, Postgres, or Spark running to transform data. All compute executes locally using Apache Arrow in-memory columnar buffers.</p>
          </div>

          <h2>Core Directives</h2>
          <p>Every architectural and engineering decision in <strong>det</strong> is anchored on three foundational directives:</p>
          <ul>
            <li><strong>🧩 Modularity:</strong> Every component is cleanly decoupled and interchangeable. Catalogs (<code>catalog/*.yaml</code>), pipeline DAG steps (<code>pipelines/*/*.yaml</code>), storage connectors (<code>BaseConnector</code>), DataFusion query compute, and the Web IDE operate as composable building blocks following clean Medallion design (Bronze &rarr; Silver &rarr; Gold).</li>
            <li><strong>⚡ Performance:</strong> Built on Apache DataFusion (vectorized Rust query engine) and Apache Arrow in-memory columnar buffers. Multi-threaded SIMD parallelism executes transformations in sub-second latency with zero intermediate serialization overhead and zero cloud egress costs.</li>
            <li><strong>🔌 Extensibility:</strong> An open plugin framework enables developers to author and register custom data sources and sinks by subclassing <code>BaseConnector</code>. Pipeline automation is first-class via CLI (<code>det run</code>), Python SDK (<code>det.Workspace</code>), or REST endpoints.</li>
          </ul>

          <h2>Core Design Principles</h2>
          <ul>
            <li><strong>Headless First:</strong> Every feature can be driven via the command line (<code>det run</code>), Python SDK (<code>det.Workspace</code>), or REST API. The Web IDE is a companion, not a prerequisite.</li>
            <li><strong>Local-First &amp; Zero Cloud Lock-In:</strong> Your source data, catalogs, pipeline definitions, and logs live directly in your filesystem. Zero cloud egress costs, zero mandatory SaaS telemetry.</li>
            <li><strong>Git-Versionable by Default:</strong> Catalogs and pipelines are stored in standard YAML and SQL. Branch, commit, review, and merge your entire data stack just like application code.</li>
            <li><strong>Blazing Apache DataFusion Compute:</strong> Multi-threaded, vectorized SQL execution powered by Apache Arrow. Queries process gigabytes of data in seconds across multiple CPU cores.</li>
          </ul>

          <h2>The 4 Pillars of a det Workspace</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Pillar</th>
                  <th>Location</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Catalogs</strong></td>
                  <td><code>catalog/*.yaml</code></td>
                  <td>Declare source datasets and destination targets (CSV, Parquet, Delta Lake, JSON, Excel, XML, Databases) with typed schemas.</td>
                </tr>
                <tr>
                  <td><strong>Pipelines (ETL)</strong></td>
                  <td><code>pipelines/*.yaml</code></td>
                  <td>Multi-stage SQL transformation DAGs with intermediate virtual table registration and configurable write modes (overwrite/append).</td>
                </tr>
                <tr>
                  <td><strong>Monitoring</strong></td>
                  <td><code>logs/pipelines/</code></td>
                  <td>Immutable execution logs with execution duration, row counts, stage timings, and full error tracebacks.</td>
                </tr>
                <tr>
                  <td><strong>Documentation</strong></td>
                  <td><code>documentation/</code></td>
                  <td>Auto-generated Markdown and standalone HTML data dictionaries with embedded Mermaid DAG lineage diagrams.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="help-callout is-tip">
            <div class="help-callout-header">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
              <span>TIP · QUICK JUMP</span>
            </div>
            <p>New to det? Jump to the <strong><a data-help-jump="sample-warehouse-overview">Sample Warehouse Overview</a></strong> or follow the <strong><a data-help-jump="quickstart">Quickstart Tour</a></strong> to unpack the <strong>NovaMart Global</strong> sample warehouse with a single click!</p>
          </div>
        `
      },
      {
        id: "architecture",
        title: "Architecture & Execution Model",
        readTime: "4 min read",
        summary: "Explore det's decoupled layer architecture, vectorized compute engine, and the lifecycle of a pipeline run.",
        content: `
          <p>det is engineered around a clean, decoupled architecture where presentation, orchestration, compute, and I/O connectors operate independently.</p>

          <h2>Layered Architecture</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Layer</th>
                  <th>Components</th>
                  <th>Role</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Presentation</strong></td>
                  <td>CLI (<code>det</code>), Python SDK, REST API, Web IDE</td>
                  <td>Exposes declarative pipeline trigger, validation, and monitoring interfaces.</td>
                </tr>
                <tr>
                  <td><strong>Orchestration</strong></td>
                  <td><code>det.pipeline.PipelineRunner</code>, <code>det.catalog.CatalogStore</code></td>
                  <td>Validates YAML schemas, resolves stage dependencies, and orchestrates multi-stage workflows.</td>
                </tr>
                <tr>
                  <td><strong>Compute Engine</strong></td>
                  <td><code>det.engine.DataFusionEngine</code></td>
                  <td>Vectorized query execution, Arrow RecordBatch manipulation, SQL planning, and parallel projection.</td>
                </tr>
                <tr>
                  <td><strong>I/O Connectors</strong></td>
                  <td>CSV, Parquet, Delta Lake, JSON, NDJSON, Excel, XML, SQLite, DuckDB, Postgres, MySQL</td>
                  <td>Streams datasets from disk or network into Arrow tables and writes transformed RecordBatches to disk.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Lifecycle of a Pipeline Execution</h2>
          <ol>
            <li><strong>Discovery &amp; Validation:</strong> The pipeline definition (YAML) is parsed and validated against stage dependency constraints.</li>
            <li><strong>Catalog Resolution:</strong> All source connections referenced in SQL stages are resolved against the active Catalog (e.g. <code>catalog/default.yaml</code>).</li>
            <li><strong>Context Registration:</strong> Tables are registered into an isolated in-memory Apache DataFusion <code>SessionContext</code> as virtual Arrow table providers.</li>
            <li><strong>Vectorized Execution:</strong> The SQL query for each stage is executed. DataFusion generates an optimized logical plan, physical plan, and executes it in parallel across available CPU cores.</li>
            <li><strong>Destination Writing:</strong> The resulting Arrow RecordBatches are written to the stage destination target in either <code>overwrite</code> or <code>append</code> mode.</li>
            <li><strong>Intermediate Views:</strong> Stages flagged without a permanent destination are registered as intermediate views available to downstream stages in the same pipeline run.</li>
            <li><strong>Observability Emission:</strong> Comprehensive run metrics (rows written, duration, status, memory, and any errors) are serialized to <code>logs/pipelines/{pipeline_name}.json</code>.</li>
          </ol>

          <div class="help-callout is-important">
            <div class="help-callout-header">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              <span>IMPORTANT · ISOLATION</span>
            </div>
            <p>Every pipeline run executes in its own isolated <code>SessionContext</code>. Temporary views registered during one pipeline cannot leak into or conflict with other pipelines running concurrently.</p>
          </div>
        `
      }
    ]
  },
  {
    id: "sample-warehouse",
    title: "Sample Warehouse",
    topics: [
      {
        id: "sample-warehouse-overview",
        title: "Purpose & Overview",
        readTime: "4 min read",
        summary: "Understand the purpose of the NovaMart Global sample warehouse, why it is provided, and what it demonstrates.",
        content: `
          <p class="lead">The <strong>NovaMart Global</strong> sample warehouse is a comprehensive, production-grade reference data platform bundled directly into det. It allows you to explore, evaluate, and test all det features immediately—without needing to configure cloud connections, fetch raw datasets, or write boilerplate schemas.</p>

          <!-- Interactive Hero Card -->
          <div class="help-sample-card">
            <div class="help-sample-card-text">
              <h4>NovaMart Omnichannel Warehouse</h4>
              <p>Unpack 14 pre-configured connections across 8 distinct file formats and 10 production SQL pipelines directly into your active workspace.</p>
              <div class="help-sample-card-badges">
                <span class="help-sample-card-badge">14 Connections</span>
                <span class="help-sample-card-badge">8 Formats</span>
                <span class="help-sample-card-badge">10 SQL Pipelines</span>
                <span class="help-sample-card-badge">Instant Unpack</span>
              </div>
            </div>
            <button class="primary-button compact-btn help-install-sample-btn help-install-sample-action-btn" type="button">
              <svg viewBox="0 0 24 24" aria-hidden="true" style="width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
              <span>Load Sample Warehouse</span>
            </button>
          </div>

          <h2>Why det Provides a Sample Warehouse</h2>
          <p>Real-world data engineering rarely deals with pristine, single-format CSVs. Enterprise environments encompass complex polyglot data landscapes: nested documents, columnar storage, ACID transactional logs, legacy spreadsheets, and semi-structured feeds. The NovaMart warehouse was designed to simulate these exact production conditions:</p>
          <ul>
            <li><strong>Zero-Friction Evaluation:</strong> Get a fully functioning, end-to-end data platform running locally within seconds. No API keys, cloud credentials, or database provisioning required.</li>
            <li><strong>Reference Architecture:</strong> Demonstrates industry best practices for folder organization, catalog structuring, multi-stage DAGs, and medallion architecture (Bronze / Silver / Gold).</li>
            <li><strong>Format Diversity:</strong> Exercises 8 heterogeneous file formats (CSV, XML, JSON, NDJSON, Excel, Parquet, Delta Lake) interacting seamlessly within the same query engine.</li>
            <li><strong>Cross-Format Vectorized Joins:</strong> Proves Apache DataFusion's ability to join an ACID Delta Lake table with a multi-sheet Excel spreadsheet and a columnar Parquet file in a single unified SQL query.</li>
          </ul>

          <h2>NovaMart Global Domain Overview</h2>
          <p>NovaMart is a multinational omnichannel retail enterprise operating 55 physical stores across North America alongside a high-traffic e-commerce portal. The sample warehouse models its core transactional and operational domains:</p>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Domain</th>
                  <th>Source Format</th>
                  <th>Storage Location</th>
                  <th>Business Function</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Customers</strong></td>
                  <td><span class="help-type-tag">CSV</span></td>
                  <td><code>source_data/customers/customers.csv</code></td>
                  <td>Customer master data: loyalty tiers, email addresses, credit balances, and account join dates.</td>
                </tr>
                <tr>
                  <td><strong>Stores</strong></td>
                  <td><span class="help-type-tag">XML</span></td>
                  <td><code>source_data/stores/store_catalog.xml</code></td>
                  <td>Hierarchical retail locations, physical format types, square footage, manager names, GPS coordinates.</td>
                </tr>
                <tr>
                  <td><strong>Orders</strong></td>
                  <td><span class="help-type-tag">Partitioned CSV</span></td>
                  <td><code>source_data/orders/2026_Q1/</code> &amp; <code>2026_Q2/</code></td>
                  <td>Omnichannel sales transactions partitioned by fiscal quarter with unit prices, quantities, and discounts.</td>
                </tr>
                <tr>
                  <td><strong>Products</strong></td>
                  <td><span class="help-type-tag">JSON</span></td>
                  <td><code>source_data/products/products.json</code></td>
                  <td>Catalog items with nested category hierarchies, wholesale costs, MSRP, and supplier metadata.</td>
                </tr>
                <tr>
                  <td><strong>Finance</strong></td>
                  <td><span class="help-type-tag">Excel (.xlsx)</span></td>
                  <td><code>source_data/finance/financial_reference.xlsx</code></td>
                  <td>Multi-sheet workbook containing live currency exchange rates and quarterly store revenue quotas.</td>
                </tr>
                <tr>
                  <td><strong>Web Clickstream</strong></td>
                  <td><span class="help-type-tag">NDJSON</span></td>
                  <td><code>source_data/web_analytics/clickstream_events.ndjson</code></td>
                  <td>High-throughput user event streaming logs: page views, add-to-cart actions, session IDs, and device telemetry.</td>
                </tr>
                <tr>
                  <td><strong>Returns</strong></td>
                  <td><span class="help-type-tag">Parquet</span></td>
                  <td><code>source_data/returns/order_returns.parquet</code></td>
                  <td>Columnar return logs compressed with Snappy, tracking refund amounts, item conditions, and return reasons.</td>
                </tr>
                <tr>
                  <td><strong>Supplier Inventory</strong></td>
                  <td><span class="help-type-tag">Delta Lake</span></td>
                  <td><code>source_data/inventory/supplier_shipments/</code></td>
                  <td>ACID-compliant storage tracking supplier shipments, lot numbers, fulfillment lead times, and stock levels.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="help-callout is-tip">
            <div class="help-callout-header">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
              <span>NEXT STEP</span>
            </div>
            <p>Ready to unpack and explore? Continue to the <a data-help-jump="quickstart">How to Use &amp; Quickstart Tour</a> to install the sample data and run your first analytical pipeline.</p>
          </div>
        `
      },
      {
        id: "quickstart",
        title: "How to Use & Quickstart Tour",
        readTime: "5 min read",
        summary: "Step-by-step instructions on loading the sample warehouse, exploring catalogs, and running pipelines.",
        content: `
          <p class="lead">Follow this quick 4-step walkthrough to unpack the NovaMart sample warehouse, inspect connections in the Catalog viewer, and execute pre-configured multi-stage pipelines.</p>

          <!-- Interactive Action Card -->
          <div class="help-sample-card">
            <div class="help-sample-card-text">
              <h4>Load Sample Data into Current Workspace</h4>
              <p>Generates the complete <code>catalog/sample_warehouse.yaml</code>, unpacks all 8 datasets into <code>source_data/</code>, and creates 10 multi-stage pipelines under <code>pipelines/Sample_Warehouse_Pipelines/</code>.</p>
            </div>
            <button class="primary-button compact-btn help-install-sample-btn help-install-sample-action-btn" type="button">
              <svg viewBox="0 0 24 24" aria-hidden="true" style="width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
              <span>Load Sample Warehouse</span>
            </button>
          </div>

          <h2>Step 1: Install the Sample Warehouse</h2>
          <p>You can install the sample warehouse using any of the following methods:</p>
          <ul>
            <li><strong>From the Web UI:</strong> Click the <strong>Load Sample Warehouse</strong> button above.</li>
            <li><strong>From the Command Line:</strong> Run the CLI command in your workspace root:
              <div class="help-code-wrap">
                <div class="help-code-header"><span>BASH</span><button class="help-code-copy-btn">Copy</button></div>
                <pre><code>det sample-data</code></pre>
              </div>
            </li>
            <li><strong>From Python:</strong> Invoke the sample data installer programmatically:
              <div class="help-code-wrap">
                <div class="help-code-header"><span>PYTHON</span><button class="help-code-copy-btn">Copy</button></div>
                <pre><code>import det

det.sample_data.install(workspace_dir=".")</code></pre>
              </div>
            </li>
          </ul>

          <h2>Step 2: Explore Connections in the Catalog Tab</h2>
          <ol>
            <li>Switch to the <strong>Catalog</strong> tab in the primary navigation header.</li>
            <li>Select <code>sample_warehouse.yaml</code> from the catalog selector dropdown.</li>
            <li>In the catalog sidebar, click on any connection folder under <code>Sample_Warehouse_Connections</code> (such as <code>customers_raw</code>, <code>financial_ref_fx</code>, or <code>supplier_inventory_delta</code>).</li>
            <li>Review the inferred schema types, file paths, format options (such as sheet names or delimiter settings), and click <strong>Test Connection</strong> to verify immediate data accessibility.</li>
          </ol>

          <h2>Step 3: Inspect Pipelines in the ETL Tab</h2>
          <ol>
            <li>Switch to the <strong>ETL</strong> tab in the navigation header.</li>
            <li>In the left explorer tree, expand <code>Sample_Warehouse_Pipelines</code> to browse all 10 pre-configured pipelines.</li>
            <li>Click on <code>mart_customer_rfm_loyalty</code> or <code>mart_store_performance_vs_targets</code>.</li>
            <li>The visual DAG viewer renders the pipeline topology, showing source connections, intermediate SQL stages, and destination outputs connected by directed flow arrows.</li>
            <li>Click any stage node to review its vectorized SQL transformation in the code editor.</li>
          </ol>

          <h2>Step 4: Execute Pipelines &amp; Inspect Outputs</h2>
          <p>Run a pipeline interactively by clicking the <strong>Run pipeline</strong> button in the ETL toolbar, or execute it headlessly from your shell:</p>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>BASH</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code># 1. Clean raw staging models
det run stg_customers_cleaned
det run stg_orders_combined

# 2. Build enriched facts & dimensions
det run fct_orders

# 3. Compute business data marts
det run mart_customer_rfm_loyalty
det run mart_store_performance_vs_targets</code></pre>
          </div>

          <div class="help-callout is-tip">
            <div class="help-callout-header">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
              <span>TIP · IDEMPOTENT EXECUTION</span>
            </div>
            <p>All 10 sample pipelines configure <code>write_mode: overwrite</code> by default. You can safely run pipelines repeatedly without creating duplicate rows or corrupting output files!</p>
          </div>
        `
      },
      {
        id: "sample-warehouse-datasets",
        title: "Included Datasets & Schemas",
        readTime: "6 min read",
        summary: "Comprehensive specification of the 8 file formats, schema definitions, and relational entities in NovaMart.",
        content: `
          <p class="lead">The NovaMart Global sample warehouse unpacks 8 distinct raw datasets into the <code>source_data/</code> folder. Each dataset is purposefully chosen to highlight det's native handling of specific file formats, compression algorithms, and structural layouts.</p>

          <h2>Dataset Catalog &amp; Technical Specifications</h2>

          <h3>1. Customers Master (Delimited CSV)</h3>
          <p><strong>Path:</strong> <code>source_data/customers/customers.csv</code> (100 records)</p>
          <p>Demonstrates automatic schema inference, header resolution, and CSV parsing.</p>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead><tr><th>Field</th><th>Type</th><th>Description</th></tr></thead>
              <tbody>
                <tr><td><code>customer_id</code></td><td><span class="help-type-tag">string</span></td><td>Unique customer identifier (e.g. <code>"CUST-00101"</code>).</td></tr>
                <tr><td><code>first_name</code>, <code>last_name</code></td><td><span class="help-type-tag">string</span></td><td>Customer legal name.</td></tr>
                <tr><td><code>email</code></td><td><span class="help-type-tag">string</span></td><td>Contact email address.</td></tr>
                <tr><td><code>loyalty_tier</code></td><td><span class="help-type-tag">string</span></td><td>Membership tier: <code>"Bronze"</code>, <code>"Silver"</code>, <code>"Gold"</code>, <code>"Platinum"</code>.</td></tr>
                <tr><td><code>account_created</code></td><td><span class="help-type-tag">string / date</span></td><td>Account registration timestamp.</td></tr>
                <tr><td><code>credit_balance</code></td><td><span class="help-type-tag">float64</span></td><td>Current account credit or loyalty wallet balance.</td></tr>
              </tbody>
            </table>
          </div>

          <h3>2. Store Locations (Semi-Structured XML)</h3>
          <p><strong>Path:</strong> <code>source_data/stores/store_catalog.xml</code> (55 stores)</p>
          <p>Demonstrates parsing hierarchical XML structures into relational records using det's XML connector with XPath row evaluation.</p>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead><tr><th>Field</th><th>Type</th><th>Description</th></tr></thead>
              <tbody>
                <tr><td><code>store_id</code></td><td><span class="help-type-tag">string</span></td><td>Store code (e.g. <code>"STR-001"</code>).</td></tr>
                <tr><td><code>store_name</code></td><td><span class="help-type-tag">string</span></td><td>Location designation (e.g. <code>"Downtown Metro Flagship"</code>).</td></tr>
                <tr><td><code>store_format</code></td><td><span class="help-type-tag">string</span></td><td>Format classification: <code>"Flagship"</code>, <code>"Express"</code>, <code>"Supercenter"</code>.</td></tr>
                <tr><td><code>city</code>, <code>state</code>, <code>country</code></td><td><span class="help-type-tag">string</span></td><td>Physical location coordinates.</td></tr>
                <tr><td><code>square_footage</code></td><td><span class="help-type-tag">int64</span></td><td>Retail floor area.</td></tr>
                <tr><td><code>manager_name</code></td><td><span class="help-type-tag">string</span></td><td>Store general manager.</td></tr>
              </tbody>
            </table>
          </div>

          <h3>3. Sales Orders (Quarterly Partitioned CSV)</h3>
          <p><strong>Path:</strong> <code>source_data/orders/2026_Q1/*.csv</code> &amp; <code>2026_Q2/*.csv</code> (500 orders)</p>
          <p>Demonstrates multi-file union ingestion and directory partition traversal.</p>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead><tr><th>Field</th><th>Type</th><th>Description</th></tr></thead>
              <tbody>
                <tr><td><code>order_id</code></td><td><span class="help-type-tag">string</span></td><td>Transaction order ID (e.g. <code>"ORD-90210"</code>).</td></tr>
                <tr><td><code>customer_id</code></td><td><span class="help-type-tag">string</span></td><td>Purchasing customer foreign key.</td></tr>
                <tr><td><code>store_id</code></td><td><span class="help-type-tag">string</span></td><td>Fulfilling store or fulfillment center.</td></tr>
                <tr><td><code>order_date</code></td><td><span class="help-type-tag">string / date</span></td><td>Order timestamp.</td></tr>
                <tr><td><code>product_id</code></td><td><span class="help-type-tag">string</span></td><td>Line item product code.</td></tr>
                <tr><td><code>quantity</code></td><td><span class="help-type-tag">int64</span></td><td>Number of units purchased.</td></tr>
                <tr><td><code>unit_price</code></td><td><span class="help-type-tag">float64</span></td><td>Unit transaction price before discounts.</td></tr>
                <tr><td><code>discount_pct</code></td><td><span class="help-type-tag">float64</span></td><td>Applied promotional discount percentage.</td></tr>
              </tbody>
            </table>
          </div>

          <h3>4. Product Catalog (Nested JSON)</h3>
          <p><strong>Path:</strong> <code>source_data/products/products.json</code> (64 items)</p>
          <p>Demonstrates querying nested JSON structures and extracting child object properties in DataFusion SQL.</p>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead><tr><th>Field</th><th>Type</th><th>Description</th></tr></thead>
              <tbody>
                <tr><td><code>product_id</code></td><td><span class="help-type-tag">string</span></td><td>Stock Keeping Unit (SKU).</td></tr>
                <tr><td><code>product_name</code></td><td><span class="help-type-tag">string</span></td><td>Product marketing title.</td></tr>
                <tr><td><code>category</code></td><td><span class="help-type-tag">string</span></td><td>Category: <code>"Electronics"</code>, <code>"Apparel"</code>, <code>"Home"</code>, <code>"Grocery"</code>.</td></tr>
                <tr><td><code>wholesale_cost</code></td><td><span class="help-type-tag">float64</span></td><td>Unit procurement cost.</td></tr>
                <tr><td><code>retail_price</code></td><td><span class="help-type-tag">float64</span></td><td>Manufacturer Suggested Retail Price (MSRP).</td></tr>
              </tbody>
            </table>
          </div>

          <h3>5. Financial Reference (Multi-Sheet Excel)</h3>
          <p><strong>Path:</strong> <code>source_data/finance/financial_reference.xlsx</code></p>
          <p>Demonstrates querying specific sheets from multi-worksheet Excel workbooks (<code>sheet: "FX_Rates"</code> and <code>sheet: "Quarterly_Targets"</code>).</p>

          <h3>6. Web Clickstream (Streaming NDJSON)</h3>
          <p><strong>Path:</strong> <code>source_data/web_analytics/clickstream_events.ndjson</code> (400 events)</p>
          <p>Demonstrates newline-delimited JSON ingestion for real-time telemetry, session metrics, and funnel analytics.</p>

          <h3>7. Order Returns (Columnar Parquet)</h3>
          <p><strong>Path:</strong> <code>source_data/returns/order_returns.parquet</code> (60 returns)</p>
          <p>Demonstrates reading binary columnar Parquet datasets with Snappy compression, projection pushdown, and metadata statistics.</p>

          <h3>8. Supplier Shipments (Delta Lake Table)</h3>
          <p><strong>Path:</strong> <code>source_data/inventory/supplier_shipments/</code> (120 records)</p>
          <p>Demonstrates querying native ACID Delta Lake tables, including reading <code>_delta_log/</code> transaction journals and snapshot parsing.</p>
        `
      },
      {
        id: "sample-warehouse-pipelines",
        title: "Pre-configured Pipelines & DAGs",
        readTime: "6 min read",
        summary: "Tour the 10 production SQL pipelines demonstrating staging models, intermediate facts/dimensions, and analytical data marts.",
        content: `
          <p class="lead">The NovaMart sample warehouse ships with 10 production-grade SQL pipelines organized according to the industry-standard <strong>Medallion Architecture</strong>: Bronze (Staging), Silver (Enriched Dimensions &amp; Facts), and Gold (Analytical Marts).</p>

          <h2>Pipeline Architecture Overview</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Tier / Layer</th>
                  <th>Pipeline Name</th>
                  <th>Inputs</th>
                  <th>Output Target</th>
                  <th>Transformation Logic</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td rowspan="4"><strong>Bronze (Staging)</strong></td>
                  <td><code>stg_customers_cleaned</code></td>
                  <td><code>customers_raw</code> (CSV)</td>
                  <td>Parquet</td>
                  <td>Standardizes casing, strips whitespace, validates email formats, casts registration dates.</td>
                </tr>
                <tr>
                  <td><code>stg_stores_parsed</code></td>
                  <td><code>stores_xml</code> (XML)</td>
                  <td>Parquet</td>
                  <td>Extracts attributes from XML hierarchy, validates GPS latitude/longitude, standardizes format types.</td>
                </tr>
                <tr>
                  <td><code>stg_orders_combined</code></td>
                  <td><code>orders_partitioned</code> (CSV)</td>
                  <td>Parquet</td>
                  <td>Unions quarterly partitioned files, calculates gross line total, cleans order date keys.</td>
                </tr>
                <tr>
                  <td><code>stg_products_flattened</code></td>
                  <td><code>products_json</code> (JSON)</td>
                  <td>Parquet</td>
                  <td>Flattens nested JSON hierarchy, computes base profit margin per unit.</td>
                </tr>
                <tr>
                  <td rowspan="3"><strong>Silver (Facts &amp; Dims)</strong></td>
                  <td><code>fct_orders</code></td>
                  <td><code>stg_orders_combined</code>, <code>stg_customers_cleaned</code></td>
                  <td>Parquet</td>
                  <td>Enriches transactions with customer demographic attributes and loyalty status.</td>
                </tr>
                <tr>
                  <td><code>dim_products</code></td>
                  <td><code>stg_products_flattened</code></td>
                  <td>Parquet</td>
                  <td>Creates conformable product dimension with margin categorization.</td>
                </tr>
                <tr>
                  <td><code>dim_stores</code></td>
                  <td><code>stg_stores_parsed</code></td>
                  <td>Parquet</td>
                  <td>Creates retail location dimension enriched with physical store format sizing.</td>
                </tr>
                <tr>
                  <td rowspan="3"><strong>Gold (Marts)</strong></td>
                  <td><code>mart_customer_rfm_loyalty</code></td>
                  <td><code>fct_orders</code>, <code>stg_customers_cleaned</code></td>
                  <td>Parquet / Mart</td>
                  <td>Calculates Recency, Frequency, Monetary (RFM) segmentation scores and lifetime customer value.</td>
                </tr>
                <tr>
                  <td><code>mart_store_performance_vs_targets</code></td>
                  <td><code>fct_orders</code>, <code>financial_ref_targets</code> (Excel)</td>
                  <td>Parquet / Mart</td>
                  <td>Joins realized store sales against Excel quarterly quotas to compute quota attainment percentage.</td>
                </tr>
                <tr>
                  <td><code>mart_returns_financial_impact</code></td>
                  <td><code>fct_orders</code>, <code>returns_parquet</code> (Parquet)</td>
                  <td>Parquet / Mart</td>
                  <td>Correlates order returns with product categories to compute net refund loss and identify defect rates.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Example: Cross-Format Polyglot Join in Pure SQL</h2>
          <p>Below is an excerpt from <code>mart_store_performance_vs_targets.sql</code> showing how det executes a vectorized join between Parquet order transactions and an Excel spreadsheet without intermediate format conversion:</p>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>SQL (DataFusion)</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>-- Joins Silver Parquet transactions against Excel financial quotas
WITH store_actuals AS (
  SELECT
    store_id,
    SUM(quantity * unit_price * (1 - discount_pct)) AS realized_revenue,
    COUNT(DISTINCT order_id) AS total_orders
  FROM fct_orders
  GROUP BY store_id
)
SELECT
  s.store_id,
  s.store_name,
  s.city,
  a.realized_revenue,
  t.target_q1_revenue AS target_revenue,
  ROUND((a.realized_revenue / t.target_q1_revenue) * 100, 2) AS quota_attainment_pct
FROM dim_stores s
JOIN store_actuals a ON s.store_id = a.store_id
JOIN financial_ref_targets t ON s.store_id = t.store_id
ORDER BY quota_attainment_pct DESC;</code></pre>
          </div>

          <h2>Extending and Customizing the Sample Pipelines</h2>
          <p>You can clone or modify any sample pipeline in your workspace. Simply navigate to <code>pipelines/Sample_Warehouse_Pipelines/&lt;pipeline_name&gt;/</code> to edit the <code>pipeline.yaml</code> configuration or SQL stage scripts. Use them as production-ready templates for your own real-world data pipelines!</p>
        `
      }
    ]
  },
  {
    id: "catalogs",
    title: "Catalogs & Connectors",
    topics: [
      {
        id: "catalog-spec",
        title: "Catalog YAML Specification",
        readTime: "4 min read",
        summary: "Learn the schema structure of catalog YAML files, connection definitions, direction modes, and folder organization.",
        content: `
          <p>A <strong>Catalog</strong> is a declarative YAML document that defines all data sources, intermediate datasets, and destination targets available to your pipelines. Catalogs live in the <code>catalog/</code> directory of your workspace.</p>

          <h2>Root Schema Structure</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Type</th>
                  <th>Required</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">version</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>Catalog specification schema version (currently <code>"1"</code>).</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">name</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>Human-readable catalog name (e.g. <code>"NovaMart Enterprise Warehouse"</code>).</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">folders</code></td>
                  <td><span class="help-type-tag">array</span></td>
                  <td><span class="help-opt-tag">Optional</span></td>
                  <td>List of organizational folders (<code>id</code>, <code>name</code>).</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">connections</code></td>
                  <td><span class="help-type-tag">array</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>List of connection objects defining datasets and external systems.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Connection Properties</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Property</th>
                  <th>Type</th>
                  <th>Required</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">id</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>Unique slug identifier used in SQL <code>FROM</code> clauses and pipeline stages.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">name</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>Display name in the Web UI.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">folder_id</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-opt-tag">Optional</span></td>
                  <td>Folder ID for grouping in the Catalog Explorer.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">connector_type</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>Connector engine: <code>csv</code>, <code>parquet</code>, <code>delta</code>, <code>json</code>, <code>ndjson</code>, <code>excel</code>, <code>xml</code>, <code>sqlite</code>, <code>duckdb</code>, <code>postgres</code>, <code>mysql</code>.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">direction</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td><code>source</code> (read-only), <code>destination</code> (write target), or <code>both</code>.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">path_or_url</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>Relative path from workspace root, file glob, or database connection URI.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">options</code></td>
                  <td><span class="help-type-tag">object</span></td>
                  <td><span class="help-opt-tag">Optional</span></td>
                  <td>Connector-specific settings (delimiters, sheet names, XML tags, compression).</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Complete Catalog YAML Example</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>YAML</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>version: "1"
name: "Retail Catalog"
folders:
  - id: raw_data
    name: "Raw Source Data"
  - id: warehouse
    name: "Transformed Marts"

connections:
  - id: raw_customers
    name: "Raw Customers CSV"
    folder_id: raw_data
    connector_type: csv
    direction: source
    path_or_url: source_data/customers/customers.csv
    options:
      delimiter: ","
      has_header: true

  - id: mart_dim_customers
    name: "Dimension Customers Parquet"
    folder_id: warehouse
    connector_type: parquet
    direction: destination
    path_or_url: warehouse/marts/dim_customers.parquet
    options:
      compression: snappy</code></pre>
          </div>
        `
      },
      {
        id: "connectors",
        title: "Supported Connectors & Options",
        readTime: "6 min read",
        summary: "Comprehensive reference matrix of all 11 supported file and database connectors, options, and sample configurations.",
        content: `
          <p>det provides built-in connectors for the most popular data engineering file formats and relational engines. Connectors seamlessly translate disk formats into Apache Arrow columnar streams.</p>

          <h2>Connector Matrix</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Connector</th>
                  <th>Type Code</th>
                  <th>Supported Directions</th>
                  <th>Key Options</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>CSV / TSV</strong></td>
                  <td><code>csv</code></td>
                  <td>Source, Destination, Both</td>
                  <td><code>delimiter</code>, <code>has_header</code>, <code>quote_char</code>, <code>encoding</code></td>
                </tr>
                <tr>
                  <td><strong>Apache Parquet</strong></td>
                  <td><code>parquet</code></td>
                  <td>Source, Destination, Both</td>
                  <td><code>compression</code> (<code>snappy</code>, <code>zstd</code>, <code>gzip</code>)</td>
                </tr>
                <tr>
                  <td><strong>Delta Lake</strong></td>
                  <td><code>delta</code></td>
                  <td>Source, Destination, Both</td>
                  <td><code>version</code>, <code>storage_options</code></td>
                </tr>
                <tr>
                  <td><strong>JSON Array</strong></td>
                  <td><code>json</code></td>
                  <td>Source, Destination, Both</td>
                  <td><code>multiline</code></td>
                </tr>
                <tr>
                  <td><strong>NDJSON (JSON Lines)</strong></td>
                  <td><code>ndjson</code></td>
                  <td>Source, Destination, Both</td>
                  <td><code>compression</code></td>
                </tr>
                <tr>
                  <td><strong>Microsoft Excel</strong></td>
                  <td><code>excel</code></td>
                  <td>Source, Destination</td>
                  <td><code>sheet_name</code>, <code>header_row</code></td>
                </tr>
                <tr>
                  <td><strong>XML</strong></td>
                  <td><code>xml</code></td>
                  <td>Source</td>
                  <td><code>root_tag</code>, <code>row_tag</code></td>
                </tr>
                <tr>
                  <td><strong>DuckDB</strong></td>
                  <td><code>duckdb</code></td>
                  <td>Source, Destination, Both</td>
                  <td><code>table_name</code>, <code>schema</code></td>
                </tr>
                <tr>
                  <td><strong>SQLite</strong></td>
                  <td><code>sqlite</code></td>
                  <td>Source, Destination, Both</td>
                  <td><code>table_name</code></td>
                </tr>
                <tr>
                  <td><strong>PostgreSQL</strong></td>
                  <td><code>postgres</code></td>
                  <td>Source, Destination, Both</td>
                  <td><code>table_name</code>, <code>schema</code></td>
                </tr>
                <tr>
                  <td><strong>MySQL</strong></td>
                  <td><code>mysql</code></td>
                  <td>Source, Destination, Both</td>
                  <td><code>table_name</code></td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Connector Configuration Details</h2>

          <h3>1. CSV / TSV Connector</h3>
          <p>Supports single files or wildcard multi-file partitions (e.g. <code>source_data/orders/*/*.csv</code>).</p>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>YAML</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>connector_type: csv
path_or_url: source_data/orders/*/*.csv
options:
  delimiter: ","        # Defaults to comma
  has_header: true      # Defaults to true
  quote_char: "\""      # Quote delimiter</code></pre>
          </div>

          <h3>2. Apache Parquet Connector</h3>
          <p>Snappy-compressed columnar format with predicate pushdown and column projection.</p>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>YAML</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>connector_type: parquet
path_or_url: warehouse/marts/dim_customers.parquet
options:
  compression: snappy   # 'snappy', 'zstd', or 'uncompressed'</code></pre>
          </div>

          <h3>3. Delta Lake Connector</h3>
          <p>Read from ACID transaction logs in Delta Lake folders. Automatically tracks the latest commit snapshot.</p>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>YAML</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>connector_type: delta
path_or_url: source_data/inventory/supplier_shipments</code></pre>
          </div>

          <h3>4. Microsoft Excel (.xlsx) Connector</h3>
          <p>Extract specific sheets from Excel workbooks into tabular Arrow formats.</p>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>YAML</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>connector_type: excel
path_or_url: source_data/finance/financial_reference.xlsx
options:
  sheet_name: Exchange_Rates
  header_row: 0</code></pre>
          </div>

          <h3>5. XML Connector</h3>
          <p>Flattens hierarchical XML documents using root and row tag identifiers.</p>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>YAML</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>connector_type: xml
path_or_url: source_data/stores/store_catalog.xml
options:
  root_tag: store_network
  row_tag: store</code></pre>
          </div>
        `
      }
    ]
  },
  {
    id: "pipelines",
    title: "Pipelines & SQL Engine",
    topics: [
      {
        id: "pipeline-spec",
        title: "Pipeline Definition & Stages",
        readTime: "4 min read",
        summary: "Master the structure of pipeline YAML files, stage sequencing, virtual view registration, and multi-stage dependencies.",
        content: `
          <p>A <strong>Pipeline</strong> defines a directed acyclic graph (DAG) of SQL transformations. Pipelines live under the <code>pipelines/</code> directory of your workspace (e.g. <code>pipelines/Sample_Warehouse_Pipelines/fct_orders.yaml</code>).</p>

          <h2>Pipeline YAML Schema</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Type</th>
                  <th>Required</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">name</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>Unique pipeline identifier matching the file slug.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">description</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-opt-tag">Optional</span></td>
                  <td>Business summary explaining the pipeline's purpose.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">stages</code></td>
                  <td><span class="help-type-tag">array</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>Ordered list of execution stages.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Stage Definition Properties</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Stage Property</th>
                  <th>Type</th>
                  <th>Required</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">name</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>Unique stage label within this pipeline.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">destination</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>Catalog connection ID where output is written, OR intermediate stage name for in-memory virtual views.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">write_mode</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-opt-tag">Optional</span></td>
                  <td><code>overwrite</code> (truncate/replace) or <code>append</code> (insert rows). Defaults to <code>overwrite</code>.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">sql</code></td>
                  <td><span class="help-type-tag">string</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>Apache DataFusion compliant SQL query. Can reference any catalog connection ID or prior intermediate stage names.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Multi-Stage Pipeline Example</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>YAML</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>name: fct_orders
description: "Normalize orders and enrich with currency exchange rates"

stages:
  - name: stage_extract_clean
    destination: stage_extract_clean    # In-memory virtual view!
    sql: |
      SELECT 
        order_id,
        customer_id,
        store_id,
        currency,
        order_amount,
        CAST(order_date AS DATE) AS order_date
      FROM raw_orders
      WHERE order_status != 'CANCELLED'

  - name: stage_enrich_fx
    destination: dest_fct_orders       # Permanent catalog connection ID!
    write_mode: overwrite
    sql: |
      SELECT 
        o.order_id,
        o.customer_id,
        o.store_id,
        o.order_date,
        o.order_amount AS original_amount,
        o.order_amount * COALESCE(fx.rate_to_usd, 1.0) AS amount_usd
      FROM stage_extract_clean o
      LEFT JOIN ref_exchange_rates fx
        ON o.currency = fx.currency_code</code></pre>
          </div>
        `
      },
      {
        id: "sql-engine",
        title: "Apache DataFusion SQL Engine",
        readTime: "5 min read",
        summary: "Discover the full range of supported SQL features: joins, window functions, CTEs, aggregations, casting, and date math.",
        content: `
          <p>det embeds <strong>Apache DataFusion</strong>, a state-of-the-art vectorized SQL query engine written in Rust. DataFusion uses <strong>Apache Arrow</strong> as its in-memory columnar representation for high throughput and low latency.</p>

          <h2>Supported SQL Dialect Features</h2>
          <ul>
            <li><strong>Joins:</strong> <code>INNER JOIN</code>, <code>LEFT JOIN</code>, <code>RIGHT JOIN</code>, <code>FULL OUTER JOIN</code>, and <code>CROSS JOIN</code>.</li>
            <li><strong>Common Table Expressions (CTEs):</strong> Recursive and multi-stage <code>WITH cte1 AS (...), cte2 AS (...)</code>.</li>
            <li><strong>Window Functions:</strong> <code>ROW_NUMBER()</code>, <code>RANK()</code>, <code>DENSE_RANK()</code>, <code>LAG()</code>, <code>LEAD()</code>, <code>SUM() OVER(...)</code>, <code>AVG() OVER(...)</code> with <code>PARTITION BY</code> and <code>ORDER BY</code>.</li>
            <li><strong>Aggregations:</strong> <code>GROUP BY</code>, <code>HAVING</code>, <code>COUNT(DISTINCT ...)</code>, <code>SUM</code>, <code>AVG</code>, <code>MIN</code>, <code>MAX</code>.</li>
            <li><strong>Conditionals:</strong> <code>CASE WHEN ... THEN ... ELSE ... END</code>, <code>COALESCE</code>, <code>NULLIF</code>.</li>
            <li><strong>Type Casting:</strong> <code>CAST(column AS DOUBLE)</code>, <code>CAST(column AS VARCHAR)</code>, <code>CAST(column AS DATE)</code>, <code>CAST(column AS TIMESTAMP)</code>.</li>
            <li><strong>String Functions:</strong> <code>CONCAT</code>, <code>UPPER</code>, <code>LOWER</code>, <code>SUBSTR</code>, <code>TRIM</code>, <code>REPLACE</code>.</li>
            <li><strong>Date &amp; Time:</strong> <code>DATE_TRUNC</code>, <code>CURRENT_DATE</code>, <code>CURRENT_TIMESTAMP</code>, <code>DATE_PART</code>.</li>
          </ul>

          <h2>Real-World Complex SQL Example (NovaMart RFM Mart)</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>SQL</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>WITH customer_metrics AS (
  SELECT
    c.customer_id,
    c.full_name,
    c.loyalty_tier,
    COUNT(o.order_id) AS total_orders,
    SUM(o.net_sales_amount) AS total_spend_usd,
    MAX(o.order_date) AS last_order_date
  FROM dim_customers c
  INNER JOIN fct_orders o 
    ON c.customer_id = o.customer_id
  GROUP BY c.customer_id, c.full_name, c.loyalty_tier
),
rfm_scores AS (
  SELECT
    customer_id,
    full_name,
    loyalty_tier,
    total_orders,
    total_spend_usd,
    NTILE(5) OVER (ORDER BY total_spend_usd DESC) AS monetary_score,
    NTILE(5) OVER (ORDER BY total_orders DESC) AS frequency_score
  FROM customer_metrics
)
SELECT 
  customer_id,
  full_name,
  loyalty_tier,
  total_spend_usd,
  CASE 
    WHEN monetary_score &gt;= 4 AND frequency_score &gt;= 4 THEN 'Champions'
    WHEN monetary_score &gt;= 3 THEN 'High Potential'
    ELSE 'Standard'
  END AS customer_rfm_segment
FROM rfm_scores;</code></pre>
          </div>
        `
      },
      {
        id: "write-modes",
        title: "Write Modes & Idempotent Builds",
        readTime: "3 min read",
        summary: "Understand the mechanics of overwrite vs append and how to construct reproducible data pipelines.",
        content: `
          <p>Every pipeline stage in det can specify a <code>write_mode</code> that determines how results are committed to the destination target.</p>

          <h2>Write Mode Comparison</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Write Mode</th>
                  <th>Target Behavior</th>
                  <th>Idempotent?</th>
                  <th>Typical Use Case</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">overwrite</code></td>
                  <td>Atomically truncates or replaces the destination file or table with the newly computed RecordBatches.</td>
                  <td><span class="help-req-tag" style="background:#10b981;color:#fff;">Yes</span></td>
                  <td>Staging tables, dimension lookups, aggregated data marts, daily snapshots.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">append</code></td>
                  <td>Inserts newly computed rows to the existing destination target without truncating existing rows.</td>
                  <td><span class="help-opt-tag">No</span></td>
                  <td>Immutable append-only event logs, telemetry streams, audit tracking.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="help-callout is-tip">
            <div class="help-callout-header">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
              <span>BEST PRACTICE · REPRODUCIBLE BUILDS</span>
            </div>
            <p>In modern analytics engineering, <strong>prefer <code>overwrite</code> for data marts and dimensional models</strong>. When a pipeline is idempotent, running it 1 time or 100 times produces identical results, eliminating data duplication bugs during pipeline re-runs or CI testing.</p>
          </div>
        `
      }
    ]
  },
  {
    id: "cli",
    title: "CLI Reference",
    topics: [
      {
        id: "cli-overview",
        title: "CLI Overview & Global Options",
        readTime: "3 min read",
        summary: "Complete guide to the det command line interface, global options, workspace paths, and exit codes.",
        content: `
          <p>The <code>det</code> CLI provides complete headless orchestration. Everything you can do in the Web IDE can be performed via the CLI in CI/CD pipelines, Docker containers, or cron jobs.</p>

          <h2>Synopsis</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>BASH</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>det [GLOBAL_OPTIONS] COMMAND [ARGS]...</code></pre>
          </div>

          <h2>Global Options</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Option</th>
                  <th>Short</th>
                  <th>Type</th>
                  <th>Default</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">--workspace</code></td>
                  <td><code>-w</code></td>
                  <td><span class="help-type-tag">PATH</span></td>
                  <td>Current working directory (<code>.</code>)</td>
                  <td>Path to workspace root containing <code>catalog/</code> and <code>pipelines/</code>.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">--verbose</code></td>
                  <td><code>-v</code></td>
                  <td><span class="help-type-tag">FLAG</span></td>
                  <td><code>False</code></td>
                  <td>Enable detailed debug logging and exception tracebacks.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">--version</code></td>
                  <td><code>-V</code></td>
                  <td><span class="help-type-tag">FLAG</span></td>
                  <td>-</td>
                  <td>Print current det version and exit.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">--help</code></td>
                  <td><code>-h</code></td>
                  <td><span class="help-type-tag">FLAG</span></td>
                  <td>-</td>
                  <td>Show help message and command list.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Available CLI Commands</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Command</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>det init</code></td>
                  <td>Initialize a new local data engineering workspace with default directory scaffolding.</td>
                </tr>
                <tr>
                  <td><code>det run</code></td>
                  <td>Execute a SQL pipeline by name or path.</td>
                </tr>
                <tr>
                  <td><code>det sample-data</code></td>
                  <td>Unpack the NovaMart Global sample warehouse into the current workspace.</td>
                </tr>
                <tr>
                  <td><code>det catalog</code></td>
                  <td>List, inspect, and validate YAML catalogs and connections.</td>
                </tr>
                <tr>
                  <td><code>det pipeline</code></td>
                  <td>List, validate, and inspect pipeline definitions.</td>
                </tr>
                <tr>
                  <td><code>det gui</code> / <code>det ui</code></td>
                  <td>Launch the local Web IDE and REST server.</td>
                </tr>
              </tbody>
            </table>
          </div>
        `
      },
      {
        id: "cli-init",
        title: "det init Command",
        readTime: "3 min read",
        summary: "Bootstrap a new local workspace with standard directory layout and default catalog template.",
        content: `
          <p>Use <code>det init</code> to bootstrap a new local data engineering workspace.</p>

          <h2>Synopsis</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>BASH</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>det init [DIRECTORY] [OPTIONS]</code></pre>
          </div>

          <h2>Parameters</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Parameter</th>
                  <th>Type</th>
                  <th>Required</th>
                  <th>Default</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">DIRECTORY</code></td>
                  <td><span class="help-type-tag">PATH</span></td>
                  <td><span class="help-opt-tag">Optional</span></td>
                  <td><code>.</code> (Current dir)</td>
                  <td>Target folder where the workspace will be created.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">--force</code></td>
                  <td><span class="help-type-tag">FLAG</span></td>
                  <td><span class="help-opt-tag">Optional</span></td>
                  <td><code>False</code></td>
                  <td>Reinitialize workspace even if catalog or pipeline folders already exist.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Scaffolded Directory Structure</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>TEXT</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>my-workspace/
├── catalog/
│   └── default.yaml         # Initial empty catalog template
├── pipelines/               # Pipeline definitions directory
├── logs/                    # Local run logs
└── documentation/           # Generated data dictionaries</code></pre>
          </div>
        `
      },
      {
        id: "cli-run",
        title: "det run Command",
        readTime: "4 min read",
        summary: "Execute data pipelines headlessly with stage filtering, catalog overrides, dry-run mode, and CI/CD exit codes.",
        content: `
          <p>The <code>det run</code> command executes a data pipeline end-to-end.</p>

          <h2>Synopsis</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>BASH</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>det run &lt;PIPELINE&gt; [OPTIONS]</code></pre>
          </div>

          <h2>Parameters</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Parameter</th>
                  <th>Type</th>
                  <th>Required</th>
                  <th>Default</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">&lt;PIPELINE&gt;</code></td>
                  <td><span class="help-type-tag">STRING</span></td>
                  <td><span class="help-req-tag">Required</span></td>
                  <td>-</td>
                  <td>Pipeline name (e.g. <code>fct_orders</code>) or path to YAML file.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">--catalog</code> / <code>-c</code></td>
                  <td><span class="help-type-tag">PATH</span></td>
                  <td><span class="help-opt-tag">Optional</span></td>
                  <td>Active catalog</td>
                  <td>Catalog file used to resolve source and destination connections.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">--stage</code> / <code>-s</code></td>
                  <td><span class="help-type-tag">STRING</span></td>
                  <td><span class="help-opt-tag">Optional</span></td>
                  <td>All stages</td>
                  <td>Execute only a specific named stage within the pipeline.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">--dry-run</code></td>
                  <td><span class="help-type-tag">FLAG</span></td>
                  <td><span class="help-opt-tag">Optional</span></td>
                  <td><code>False</code></td>
                  <td>Validate schemas, SQL, and connections without writing data to destination targets.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Exit Codes (for CI/CD)</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Exit Code</th>
                  <th>Meaning</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>0</code></td>
                  <td><strong>SUCCESS:</strong> All pipeline stages executed and committed successfully.</td>
                </tr>
                <tr>
                  <td><code>1</code></td>
                  <td><strong>PIPELINE FAILURE:</strong> A SQL query error or destination I/O failure occurred.</td>
                </tr>
                <tr>
                  <td><code>2</code></td>
                  <td><strong>CONFIG ERROR:</strong> Specified pipeline file, catalog, or source connection was not found.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Example: GitHub Actions Workflow</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>YAML</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>name: Nightly Warehouse Build
on:
  schedule:
    - cron: '0 2 * * *'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install det-core
      - name: Run Staging and Mart Pipelines
        run: |
          det run stg_customers_cleaned
          det run fct_orders
          det run mart_customer_rfm_loyalty</code></pre>
          </div>
        `
      },
      {
        id: "cli-sample-data",
        title: "det sample-data Command",
        readTime: "3 min read",
        summary: "Unpack the NovaMart Global sample warehouse into the current workspace.",
        content: `
          <p>The <code>det sample-data</code> command (alias: <code>det samples</code>) unpacks the bundled NovaMart Global sample dataset into your workspace.</p>

          <h2>Synopsis</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>BASH</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>det sample-data [OPTIONS]</code></pre>
          </div>

          <h2>Options</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Option</th>
                  <th>Type</th>
                  <th>Default</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">--overwrite</code></td>
                  <td><span class="help-type-tag">FLAG</span></td>
                  <td><code>True</code></td>
                  <td>Overwrite existing sample warehouse files if they already exist in the workspace.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">--select-catalog</code></td>
                  <td><span class="help-type-tag">FLAG</span></td>
                  <td><code>True</code></td>
                  <td>Automatically set <code>sample_warehouse.yaml</code> as the active catalog in the GUI.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Output Summary</h2>
          <ul>
            <li>Creates <code>source_data/</code> containing CSV, XML, JSON, NDJSON, Excel, Parquet, and Delta Lake files.</li>
            <li>Creates <code>catalog/sample_warehouse.yaml</code> containing 14 connections under <code>Sample_Warehouse_Connections</code>.</li>
            <li>Creates <code>pipelines/Sample_Warehouse_Pipelines/</code> with 10 production SQL pipelines.</li>
          </ul>
        `
      },
      {
        id: "cli-catalog-pipeline",
        title: "det catalog & det pipeline Commands",
        readTime: "4 min read",
        summary: "Commands to list, validate, and inspect YAML catalogs and pipeline DAGs.",
        content: `
          <p>The <code>det catalog</code> and <code>det pipeline</code> commands provide inspection and validation utilities.</p>

          <h2>det catalog Subcommands</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Command</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>det catalog list</code></td>
                  <td>List all YAML catalog files found in <code>catalog/</code>.</td>
                </tr>
                <tr>
                  <td><code>det catalog show [CATALOG]</code></td>
                  <td>Display all folders, connection IDs, and target paths for a catalog.</td>
                </tr>
                <tr>
                  <td><code>det catalog validate [CATALOG]</code></td>
                  <td>Validate catalog YAML schema and verify that source file paths exist on disk.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>det pipeline Subcommands</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Command</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>det pipeline list</code></td>
                  <td>List all pipeline YAML files across folders in <code>pipelines/</code>.</td>
                </tr>
                <tr>
                  <td><code>det pipeline validate &lt;PIPELINE&gt;</code></td>
                  <td>Validate pipeline YAML syntax, stage dependencies, and SQL syntax without executing.</td>
                </tr>
              </tbody>
            </table>
          </div>
        `
      },
      {
        id: "cli-gui",
        title: "det gui Command",
        readTime: "3 min read",
        summary: "Launch the local Web IDE and REST API server.",
        content: `
          <p>The <code>det gui</code> command (alias: <code>det ui</code>) starts the local web interface and headless REST API server.</p>

          <h2>Synopsis</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>BASH</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>det gui [OPTIONS]</code></pre>
          </div>

          <h2>Options</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Option</th>
                  <th>Short</th>
                  <th>Default</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">--port</code></td>
                  <td><code>-p</code></td>
                  <td><code>8000</code></td>
                  <td>TCP port to bind the HTTP server to.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">--host</code></td>
                  <td><code>-h</code></td>
                  <td><code>127.0.0.1</code></td>
                  <td>Binding network interface (use <code>0.0.0.0</code> for containerized deployments).</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">--no-browser</code></td>
                  <td>-</td>
                  <td><code>False</code></td>
                  <td>Do not open default web browser automatically upon server startup.</td>
                </tr>
              </tbody>
            </table>
          </div>
        `
      }
    ]
  },
  {
    id: "python",
    title: "Python SDK Reference",
    topics: [
      {
        id: "python-overview",
        title: "Python SDK Overview & Architecture",
        readTime: "3 min read",
        summary: "Integrate det into Python scripts, Jupyter notebooks, Airflow DAGs, and Prefect flows.",
        content: `
          <p>The <code>det</code> Python package exposes a complete programmatic API. Every capability in the CLI and GUI is available as standard Python classes and functions.</p>

          <h2>Core Python Modules</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Module</th>
                  <th>Key Classes / Functions</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>det.Workspace</code></td>
                  <td><code>Workspace</code></td>
                  <td>High-level workspace interface for pipeline execution, catalog loading, and discovery.</td>
                </tr>
                <tr>
                  <td><code>det.catalog</code></td>
                  <td><code>Catalog</code>, <code>Connection</code></td>
                  <td>Programmatic catalog and connection manipulation.</td>
                </tr>
                <tr>
                  <td><code>det.pipeline</code></td>
                  <td><code>Pipeline</code>, <code>PipelineRunner</code>, <code>ExecutionResult</code></td>
                  <td>Pipeline parsing, stage graph resolution, and execution runner.</td>
                </tr>
                <tr>
                  <td><code>det.sample_data</code></td>
                  <td><code>install_sample_data</code></td>
                  <td>Programmatically unpack sample warehouse files.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Minimal Python Example</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>PYTHON</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>from det import Workspace

# Open workspace in current directory
ws = Workspace(".")

# List available pipelines
pipelines = ws.list_pipelines()
print("Found pipelines:", pipelines)

# Execute pipeline
result = ws.run_pipeline("fct_orders")
if result.status == "SUCCESS":
    print(f"Pipeline succeeded in {result.duration_seconds:.2f}s! Rows: {result.rows_written}")
else:
    print(f"Pipeline failed: {result.errors}")</code></pre>
          </div>
        `
      },
      {
        id: "python-workspace",
        title: "det.Workspace API Reference",
        readTime: "5 min read",
        summary: "Detailed reference for the det.Workspace class, methods, parameters, return types, and exceptions.",
        content: `
          <p>The <code>det.Workspace</code> class is the primary entry point for programmatic data engineering in det.</p>

          <h2>Constructor</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>PYTHON</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>ws = Workspace(path: str | Path | None = None)</code></pre>
          </div>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Parameter</th>
                  <th>Type</th>
                  <th>Required</th>
                  <th>Default</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">path</code></td>
                  <td><span class="help-type-tag">str | Path | None</span></td>
                  <td><span class="help-opt-tag">Optional</span></td>
                  <td><code>None</code> (Current dir)</td>
                  <td>Path to workspace root directory.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Methods</h2>

          <h3><code>run_pipeline(...)</code></h3>
          <p>Executes a pipeline by name or YAML file path.</p>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>PYTHON</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>result = ws.run_pipeline(
    name_or_path: str | Path,
    catalog: str | Path | None = None,
    stage: str | None = None,
    dry_run: bool = False
) -&gt; ExecutionResult</code></pre>
          </div>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Parameter</th>
                  <th>Type</th>
                  <th>Default</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">name_or_path</code></td>
                  <td><span class="help-type-tag">str | Path</span></td>
                  <td>-</td>
                  <td>Name or relative path of pipeline to run.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">catalog</code></td>
                  <td><span class="help-type-tag">str | Path | None</span></td>
                  <td><code>None</code></td>
                  <td>Catalog filename to use (defaults to active catalog).</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">stage</code></td>
                  <td><span class="help-type-tag">str | None</span></td>
                  <td><code>None</code></td>
                  <td>Specific stage name to run in isolation.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">dry_run</code></td>
                  <td><span class="help-type-tag">bool</span></td>
                  <td><code>False</code></td>
                  <td>Validate schemas and queries without committing data.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h3><code>ExecutionResult</code> Dataclass</h3>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Type</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">status</code></td>
                  <td><span class="help-type-tag">str</span></td>
                  <td><code>"SUCCESS"</code> or <code>"FAILED"</code>.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">duration_seconds</code></td>
                  <td><span class="help-type-tag">float</span></td>
                  <td>Total execution time in seconds.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">rows_written</code></td>
                  <td><span class="help-type-tag">int</span></td>
                  <td>Total rows written across all destination stages.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">stages_completed</code></td>
                  <td><span class="help-type-tag">list[str]</span></td>
                  <td>Names of stages that completed successfully.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">errors</code></td>
                  <td><span class="help-type-tag">list[str]</span></td>
                  <td>Error messages if execution failed.</td>
                </tr>
              </tbody>
            </table>
          </div>
        `
      },
      {
        id: "python-sample-data",
        title: "det.sample_data API Reference",
        readTime: "3 min read",
        summary: "Programmatically install the NovaMart sample warehouse in automated testing suites or bootstrap scripts.",
        content: `
          <p>The <code>det.sample_data</code> module enables programmatic installation of sample data into any workspace directory.</p>

          <h2>Function: <code>install_sample_data</code></h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>PYTHON</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>from det.sample_data import install_sample_data

result = install_sample_data(
    workspace_dir: str | Path | None = None,
    *,
    select_catalog: bool = True,
    overwrite_existing: bool = True
) -&gt; dict[str, Any]</code></pre>
          </div>

          <h2>Parameters</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Parameter</th>
                  <th>Type</th>
                  <th>Default</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code class="help-param-name">workspace_dir</code></td>
                  <td><span class="help-type-tag">str | Path | None</span></td>
                  <td><code>None</code></td>
                  <td>Target workspace directory (defaults to current active workspace).</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">select_catalog</code></td>
                  <td><span class="help-type-tag">bool</span></td>
                  <td><code>True</code></td>
                  <td>If True, switches the GUI active catalog to <code>sample_warehouse.yaml</code>.</td>
                </tr>
                <tr>
                  <td><code class="help-param-name">overwrite_existing</code></td>
                  <td><span class="help-type-tag">bool</span></td>
                  <td><code>True</code></td>
                  <td>If True, replaces existing sample files if already present.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>Return Value Dictionary</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>PYTHON</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>{
    "status": "SUCCESS",
    "catalog": "sample_warehouse.yaml",
    "active_catalog": "sample_warehouse.yaml",
    "source_data_dir": ".../source_data",
    "pipelines_copied": 10,
    "catalog_file": ".../catalog/sample_warehouse.yaml"
}</code></pre>
          </div>
        `
      }
    ]
  },
  {
    id: "observability",
    title: "Observability & Documentation",
    topics: [
      {
        id: "monitoring",
        title: "Pipeline Health & Execution Logs",
        readTime: "4 min read",
        summary: "Understand how execution metrics are logged, how to filter runs in the Monitoring tab, and how to debug failures.",
        content: `
          <p>det features built-in observability without needing third-party logging daemons. Every pipeline execution records immutable metrics to <code>logs/pipelines/{pipeline_name}.json</code>.</p>

          <h2>Log File JSON Structure</h2>
          <div class="help-code-wrap">
            <div class="help-code-header"><span>JSON</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>{
  "pipeline": "fct_orders",
  "run_id": "run_20261013_083000",
  "status": "SUCCESS",
  "start_time": "2026-10-13T08:30:00.123456Z",
  "end_time": "2026-10-13T08:30:00.456789Z",
  "duration_seconds": 0.333,
  "rows_written": 500,
  "stages": [
    {
      "name": "stage_extract_clean",
      "status": "SUCCESS",
      "duration_seconds": 0.120,
      "rows_written": 500
    },
    {
      "name": "stage_enrich_fx",
      "status": "SUCCESS",
      "duration_seconds": 0.213,
      "rows_written": 500
    }
  ]
}</code></pre>
          </div>

          <h2>Monitoring Features in the Web IDE</h2>
          <ul>
            <li><strong>Status Filter Pills:</strong> Quickly filter runs by <strong>All</strong>, <strong>Success</strong>, or <strong>Failed</strong>.</li>
            <li><strong>Inferred Results:</strong> View stage duration breakdowns and output row metrics at a glance.</li>
            <li><strong>Actual Log Entries:</strong> Trace execution events in chronological sequence.</li>
            <li><strong>Raw JSON Log:</strong> One-click button to copy the complete raw execution log payload.</li>
          </ul>
        `
      },
      {
        id: "documentation",
        title: "Automated Documentation & Lineage",
        readTime: "4 min read",
        summary: "Generate self-documenting data dictionaries, pipeline schemas, and interactive Mermaid DAG lineage diagrams.",
        content: `
          <p>det automatically generates documentation directly from your catalog metadata and SQL queries, keeping your team's data dictionary in perfect sync with code.</p>

          <h2>Documentation Formats</h2>
          <ul>
            <li><strong>Interactive HTML:</strong> Standalone HTML document with interactive tables, column search, and rendered Mermaid lineage graphs.</li>
            <li><strong>Markdown (.md):</strong> Clean GitHub-flavored Markdown for version control repositories or documentation static site generators (MkDocs, Docusaurus).</li>
          </ul>

          <h2>Stale Documentation Detection</h2>
          <p>det calculates cryptographic hashes of your pipeline definitions and compares them with generated documentation. If a pipeline definition is edited after docs were generated, a <strong>Stale Documentation Warning Banner</strong> appears with a 1-click <strong>Regenerate now</strong> button.</p>

          <div class="help-callout is-tip">
            <div class="help-callout-header">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
              <span>TIP · LINEAGE VISUALIZATION</span>
            </div>
            <p>Every generated document contains a visual Mermaid DAG diagram illustrating upstream sources, intermediate stages, and downstream destination targets.</p>
          </div>
        `
      }
    ]
  },
  {
    id: "extensibility",
    title: "Extensibility & Custom Connectors",
    topics: [
      {
        id: "extensibility-overview",
        title: "Extensibility Architecture & Plugin System",
        readTime: "4 min read",
        summary: "Understand det's pluggable architecture, standard Python entry point discovery, and the decoupled contract between data sources, Apache DataFusion, and the Web UI.",
        content: `
          <p class="lead"><strong>det</strong> was designed from day one with an open, non-monolithic architecture. All built-in connectors (CSV, Parquet, Delta Lake, Iceberg, JSON, Excel, XML) use the exact same extension contract that third-party plugins use.</p>

          <div class="help-callout is-note">
            <div class="help-callout-header">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              <span>NOTE · ZERO CORE MODIFICATIONS</span>
            </div>
            <p>You never need to fork or patch <code>det-core</code> to connect to new proprietary databases, internal REST APIs, cloud object stores, or SaaS applications. Build your connector as a standalone Python package, register it via entry points, and install it with <code>pip</code>.</p>
          </div>

          <h2>How Extensibility Works in det</h2>
          <p>The extension lifecycle spans three integrated layers:</p>
          <ol>
            <li><strong>UI Metadata Contract:</strong> Connectors define their own configuration fields (file paths, authentication tokens, query options, compression algorithms). The Web UI automatically renders dynamic forms in the <em>Add Connection</em> dialog without writing any HTML or JavaScript.</li>
            <li><strong>Catalog Serialization:</strong> Connection settings are saved transparently as typed YAML in <code>catalog/*.yaml</code> files, enabling full Git versioning.</li>
            <li><strong>Engine Execution Contract:</strong> At pipeline runtime, the connector's <code>read()</code> method is invoked with the DataFusion <code>SessionContext</code> and user options. The connector loads the data into an in-memory Apache Arrow Table or Dataset and returns a lazy DataFusion <code>DataFrame</code> ready for multi-threaded SQL querying.</li>
          </ol>

          <h2>Plugin Discovery via Python Entry Points</h2>
          <p>det discovers custom connectors using standard Python package metadata entry points under the group <code>det.connectors</code>. When det starts or when the UI queries available connectors, it calls:</p>

          <div class="help-code-wrap">
            <div class="help-code-header"><span>PYTHON</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>from importlib.metadata import entry_points

# det automatically scans this group on startup:
for ep in entry_points(group="det.connectors"):
    connector_def = ep.load()
    # Registered into the global connector registry</code></pre>
          </div>

          <p>Any Python package in your virtual environment that advertises a <code>det.connectors</code> entry point is automatically loaded, validated for UUID and key uniqueness, and made available across the CLI, Python SDK, and Web IDE.</p>

          <h2>Extension Capabilities Summary</h2>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Extension Point</th>
                  <th>Contract Mechanism</th>
                  <th>Primary Use Case</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Custom Connectors</strong></td>
                  <td><code>ConnectorDefinition</code> + <code>det.connectors</code> entry point</td>
                  <td>Add support for databases (PostgreSQL, SQLite, MySQL, DuckDB), APIs, or warehouse formats.</td>
                </tr>
                <tr>
                  <td><strong>DataFusion UDFs</strong></td>
                  <td><code>SessionContext.register_udf()</code></td>
                  <td>Expose custom Python scalar and aggregate functions directly inside SQL pipeline stages.</td>
                </tr>
                <tr>
                  <td><strong>Lifecycle Hooks</strong></td>
                  <td>Python SDK &amp; <code>det.runner.execute_pipeline</code></td>
                  <td>Run pre-flight checks, send Slack/Teams webhook notifications, or log custom metrics.</td>
                </tr>
                <tr>
                  <td><strong>Custom Exporters</strong></td>
                  <td>Arrow write sinks &amp; Destination stages</td>
                  <td>Push final transformed data to cloud data lakes, message queues, or reporting tables.</td>
                </tr>
              </tbody>
            </table>
          </div>
        `
      },
      {
        id: "connector-specification",
        title: "Connector Specification & API Contract",
        readTime: "6 min read",
        summary: "Detailed reference specification for ConnectorDefinition, ConnectorField types, sections, validation rules, and the ConnectorReader protocol.",
        content: `
          <p>All connectors in det must adhere to the data structures defined in <code>det.connectors</code>. This specification guarantees complete interoperability between the Web IDE forms, the catalog storage layer, and the Apache DataFusion execution engine.</p>

          <h2>1. <code>ConnectorDefinition</code> Dataclass</h2>
          <p>The top-level object exported by your connector plugin:</p>

          <div class="help-code-wrap">
            <div class="help-code-header"><span>PYTHON</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>from dataclasses import dataclass
from typing import Protocol, Any
from det.connectors import ConnectorDefinition, ConnectorField

@dataclass(frozen=True)
class ConnectorDefinition:
    key: str                          # Lowercase alphanumeric slug: a-z, 0-9, _, -
    guid: str                         # Canonical UUID string (RFC 4122)
    label: str                        # Human-readable label rendered in UI (e.g. "PostgreSQL")
    description: str                  # Short summary shown in connection list & tooltips
    fields: tuple[ConnectorField, ...] # Configuration fields rendered in the dialog
    read: ConnectorReader | None = None # Optional callable scanning data into DataFusion</code></pre>
          </div>

          <h3>Validation Rules</h3>
          <ul>
            <li><code>key</code>: Must consist exclusively of lowercase letters, digits, underscores, or hyphens (e.g. <code>"sqlite"</code>, <code>"azure_blob"</code>, <code>"shopify_api"</code>).</li>
            <li><code>guid</code>: Must be a valid UUID. Best practice: use deterministic UUIDv5 with a fixed namespace, or a randomly generated UUIDv4:
              <br><code>guid = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://myorg.com/connectors/sqlite"))</code>
            </li>
          </ul>

          <h2>2. <code>ConnectorField</code> Dataclass</h2>
          <p>Defines individual form inputs rendered in the Web UI modal and saved in catalog YAML:</p>

          <div class="help-code-wrap">
            <div class="help-code-header"><span>PYTHON</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>from dataclasses import dataclass
from typing import Literal, Any

@dataclass(frozen=True)
class ConnectorField:
    name: str                              # Technical key stored in connection.options dict
    label: str                             # Label displayed above the input field
    section: Literal["connection", "read", "write"] # Grouping section in the UI form
    kind: Literal["text", "number", "boolean", "select", "list", "textarea"] # Input widget type
    description: str = ""                  # Helpful description or tooltip displayed under the field
    default: Any = None                    # Default value populated in new connections
    choices: tuple[str, ...] = ()          # Permitted values for "select" kind dropdowns
    required: bool = False                 # Whether user must supply a value
    placeholder: str = ""                  # Ghost text shown in empty text inputs</code></pre>
          </div>

          <h3>Field Sections Breakdown</h3>
          <div class="help-table-wrap">
            <table class="help-table">
              <thead>
                <tr>
                  <th>Section</th>
                  <th>Purpose</th>
                  <th>Typical Fields</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>"connection"</code></td>
                  <td>Shared across both source reading and destination writing.</td>
                  <td>File paths, hosts, ports, database names, auth tokens, SSL flags.</td>
                </tr>
                <tr>
                  <td><code>"read"</code></td>
                  <td>Configured when this connection is used as a source table.</td>
                  <td>SQL query, table name, delimiter, schema inference rows, batch size.</td>
                </tr>
                <tr>
                  <td><code>"write"</code></td>
                  <td>Configured when this connection is used as a target destination.</td>
                  <td>Write mode (overwrite/append), output pattern, compression, partition columns.</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h2>3. <code>ConnectorReader</code> Protocol</h2>
          <p>The callable invoked by det when executing a pipeline or previewing a source in the Catalog UI:</p>

          <div class="help-code-wrap">
            <div class="help-code-header"><span>PYTHON</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>from pathlib import Path
from typing import Any, Protocol
from datafusion import DataFrame, SessionContext

class ConnectorReader(Protocol):
    def __call__(
        self,
        context: SessionContext,
        options: dict[str, Any],
        workspace: Path,
    ) -> DataFrame:
        """
        Args:
            context: The DataFusion SessionContext for the active execution.
            options: Dictionary of saved options from the catalog YAML for this connection.
            workspace: The absolute filesystem Path to the root of the active workspace.

        Returns:
            A lazy DataFusion DataFrame representing the loaded table.
        """
        ...</code></pre>
          </div>
        `
      },
      {
        id: "building-custom-connector",
        title: "Step-by-Step: Building a Custom Connector",
        readTime: "8 min read",
        summary: "End-to-end tutorial: create a custom SQLite database connector, write the reader method, and register it via pyproject.toml.",
        content: `
          <p>Let's build a real, fully functional custom connector from scratch that allows det pipelines to query tables from a local <strong>SQLite database</strong>.</p>

          <h2>Step 1: Project Structure</h2>
          <p>Create a standalone Python project or add this to your internal data engineering library:</p>

          <div class="help-code-wrap">
            <div class="help-code-header"><span>DIRECTORY STRUCTURE</span></div>
            <pre><code>det-sqlite-connector/
├── pyproject.toml
└── det_sqlite/
    ├── __init__.py
    └── connector.py</code></pre>
          </div>

          <h2>Step 2: Implement <code>connector.py</code></h2>
          <p>Define the connector metadata, fields, and reader implementation:</p>

          <div class="help-code-wrap">
            <div class="help-code-header"><span>PYTHON · det_sqlite/connector.py</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>import sqlite3
import uuid
from pathlib import Path
from typing import Any
import pyarrow as pa
from datafusion import DataFrame, SessionContext
from det.connectors import ConnectorDefinition, ConnectorField

def read_sqlite(
    context: SessionContext,
    options: dict[str, Any],
    workspace: Path,
) -> DataFrame:
    # 1. Resolve database path (supports relative paths to workspace)
    raw_path = options.get("database_path", "").strip()
    if not raw_path:
        raise ValueError("SQLite connector requires a 'database_path' option.")
    
    db_path = Path(raw_path).expanduser()
    if not db_path.is_absolute():
        db_path = workspace / db_path
        
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database file not found at: {db_path}")

    # 2. Extract user query or table name
    table_name = options.get("table_name", "").strip()
    custom_sql = options.get("custom_sql", "").strip()
    query = custom_sql if custom_sql else f"SELECT * FROM {table_name}"
    
    if not query:
        raise ValueError("Specify either 'table_name' or 'custom_sql' for SQLite scan.")

    # 3. Query SQLite and convert rows to Apache Arrow Table
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        # Build column-oriented dictionary for PyArrow
        data_by_col = {col: [row[i] for row in rows] for i, col in enumerate(columns)}
        arrow_table = pa.Table.from_pydict(data_by_col)
    finally:
        conn.close()

    # 4. Register with DataFusion and return lazy DataFrame
    return context.from_arrow(arrow_table)

# Define the Connector Definition
SQLITE_CONNECTOR = ConnectorDefinition(
    key="sqlite",
    guid=str(uuid.uuid5(uuid.NAMESPACE_URL, "https://det.dev/connectors/sqlite")),
    label="SQLite Database",
    description="Query relational tables and custom views from local SQLite database files.",
    fields=(
        ConnectorField(
            name="database_path",
            label="Database File Path",
            section="connection",
            kind="text",
            description="Relative to workspace root or absolute path to .sqlite / .db file.",
            required=True,
            placeholder="data/app.db",
        ),
        ConnectorField(
            name="table_name",
            label="Table or View Name",
            section="read",
            kind="text",
            description="Name of the SQLite table to scan.",
            placeholder="users",
        ),
        ConnectorField(
            name="custom_sql",
            label="Custom SQL Query (Optional)",
            section="read",
            kind="textarea",
            description="Override table scan with a customized SELECT query.",
            placeholder="SELECT id, name, created_at FROM users WHERE active = 1",
        ),
    ),
    read=read_sqlite,
)</code></pre>
          </div>

          <h2>Step 3: Register via <code>pyproject.toml</code></h2>
          <p>Declare your connector under the <code>det.connectors</code> entry point table:</p>

          <div class="help-code-wrap">
            <div class="help-code-header"><span>TOML · pyproject.toml</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "det-sqlite-connector"
version = "0.1.0"
description = "SQLite data connector for det"
dependencies = [
    "pyarrow>=14.0.0",
    "datafusion>=35.0.0",
]

# The critical entry point hook recognized by det:
[project.entry-points."det.connectors"]
sqlite = "det_sqlite.connector:SQLITE_CONNECTOR"</code></pre>
          </div>

          <h2>Step 4: Install &amp; Verify</h2>
          <p>Install the package into your Python environment:</p>

          <div class="help-code-wrap">
            <div class="help-code-header"><span>BASH</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code># Install in editable mode for local development:
pip install -e .

# Launch det GUI or run pipelines:
det gui</code></pre>
          </div>

          <p>Now open the Web GUI and navigate to the <strong>Catalog</strong> tab. Click <strong>+ Add connection</strong>. In the <em>Connector</em> dropdown, you will see <strong>SQLite Database</strong> listed alongside the built-in file formats! Fill in the database path, and your SQLite table is immediately available for pipelines, join queries, and automated documentation.</p>
        `
      },
      {
        id: "extending-engine-runners",
        title: "DataFusion UDFs & Custom Execution Hooks",
        readTime: "5 min read",
        summary: "Extend the SQL engine with custom Python User-Defined Functions (UDFs), custom destination writers, and programmatic execution hooks.",
        content: `
          <p>Beyond custom file and database connectors, det exposes hooks for registering Python functions directly into Apache DataFusion and executing pipelines programmatically in custom workflows.</p>

          <h2>Registering Custom DataFusion UDFs</h2>
          <p>You can define custom vectorized Python functions and register them into DataFusion's SQL catalog. These functions become immediately queryable across all pipeline stages.</p>

          <div class="help-code-wrap">
            <div class="help-code-header"><span>PYTHON</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>import pyarrow.compute as pc
from datafusion import SessionContext, udf
from det.engine import create_session_context

# 1. Define a vectorized scalar function operating on PyArrow Arrays:
def hash_email(email_array):
    # Vectorized SHA-256 or MD5 hash
    return pc.sha256(email_array)

# 2. Wrap as a DataFusion UDF:
email_hasher = udf(
    hash_email,
    input_types=[pa.utf8()],
    return_type=pa.utf8(),
    volatility="immutable",
    name="mask_email"
)

# 3. Register into the SessionContext:
context = create_session_context()
context.register_udf(email_hasher)

# Now queryable directly in SQL:
# SELECT id, mask_email(email) AS masked_email FROM customers;</code></pre>
          </div>

          <h2>Programmatic Pipeline Execution Hooks</h2>
          <p>You can execute, validate, and monitor pipelines programmatically from external scripts, Airflow operators, Prefect tasks, or CI/CD pipelines:</p>

          <div class="help-code-wrap">
            <div class="help-code-header"><span>PYTHON</span><button class="help-code-copy-btn">Copy</button></div>
            <pre><code>from det.api import configure_api, run_pipeline, validate_pipeline

# Initialize workspace context
configure_api("/path/to/my_workspace")

# 1. Pre-flight logical plan validation
val_result = validate_pipeline("finance/revenue_summary")
if not val_result.get("valid"):
    print("Validation failed:", val_result.get("error"))

# 2. Run pipeline with full disk logging
run_result = run_pipeline("finance/revenue_summary")
print(f"Run ID: {run_result['run_id']}")
print(f"Status: {run_result['status']}")
print(f"Duration: {run_result['duration_ms']} ms")
print(f"Total Rows: {run_result['total_rows']}")</code></pre>
          </div>

          <h2>Custom Write Handlers &amp; Post-Run Hooks</h2>
          <p>Because pipeline outputs are written to disk and cataloged under <code>logs/pipelines/&lt;pipeline_id&gt;/</code> as JSON log files, you can attach event handlers or filesystem watchers to automatically:</p>
          <ul>
            <li>Trigger webhook notifications on pipeline failures.</li>
            <li>Replicate Parquet / Delta Lake partitions to AWS S3, Google Cloud Storage, or Azure Blob.</li>
            <li>Send telemetry to Datadog, Prometheus, or Grafana using the structured run metrics.</li>
          </ul>
        `
      }
    ]
  },
  {
    id: "troubleshooting",
    title: "FAQ & Troubleshooting",
    topics: [
      {
        id: "faq",
        title: "Frequently Asked Questions (FAQ)",
        readTime: "5 min read",
        summary: "Answers to common questions about det, comparisons with dbt and DuckDB, cloud deployment, and performance.",
        content: `
          <h2>General Questions</h2>

          <h3>How does det compare to dbt?</h3>
          <p><strong>dbt</strong> requires an external cloud data warehouse (Snowflake, BigQuery, Databricks, Redshift, Postgres) to execute queries. <strong>det</strong> embeds its own vectorized engine (Apache DataFusion). You can run complete ETL pipelines from scratch without spinning up or paying for any cloud database.</p>

          <h3>How does det compare to DuckDB?</h3>
          <p>DuckDB is an embedded database engine. det is a <strong>complete data engineering orchestration system</strong> (catalogs, pipelines, multi-stage DAGs, monitoring logs, automated lineage documentation, and Web IDE) that leverages Apache DataFusion and Arrow for its compute engine.</p>

          <h3>Can det run completely headless in CI/CD?</h3>
          <p>Yes! Every pipeline can be executed via <code>det run &lt;pipeline_name&gt;</code> with standard UNIX exit codes (<code>0</code> for success, non-zero for failure). You never need to launch the browser UI in production environments.</p>

          <h3>Is an internet connection required?</h3>
          <p>No. det is 100% local-first. All compute, catalogs, pipelines, documentation, and web assets run on your local machine with zero external cloud dependencies.</p>

          <h3>Can I version control my entire warehouse with Git?</h3>
          <p>Absolutely. Catalogs (<code>catalog/*.yaml</code>), pipelines (<code>pipelines/*.yaml</code>), and generated documentation (<code>documentation/*.md</code>) are plain text files designed to be committed to Git repositories.</p>
        `
      },
      {
        id: "troubleshooting-guide",
        title: "Troubleshooting & Common Errors",
        readTime: "4 min read",
        summary: "Diagnostic guide for resolving SQL parsing issues, schema mismatches, and missing source paths.",
        content: `
          <p>When an error occurs during pipeline execution, det provides descriptive error messages and stack traces in the <strong>Monitoring</strong> tab and terminal output.</p>

          <h2>Common Error Codes &amp; Solutions</h2>

          <h3>1. <code>SourceFileNotFound</code></h3>
          <p><strong>Cause:</strong> A connection in your catalog points to a relative path that does not exist in your workspace.</p>
          <p><strong>Solution:</strong> Check the <code>path_or_url</code> property in your catalog YAML. Relative paths are resolved relative to the workspace root directory.</p>

          <h3>2. <code>SQLSyntaxError</code> or <code>TableNotFound</code></h3>
          <p><strong>Cause:</strong> The SQL query references a table or connection ID that is not defined in the catalog, or an intermediate stage was misspelled.</p>
          <p><strong>Solution:</strong> Verify that table names in your <code>FROM</code> and <code>JOIN</code> clauses match connection IDs in your catalog YAML or preceding stage names within the same pipeline.</p>

          <h3>3. <code>SchemaMismatchError</code> during Append</h3>
          <p><strong>Cause:</strong> A pipeline stage with <code>write_mode: append</code> attempted to write columns whose data types or count differ from the existing destination file.</p>
          <p><strong>Solution:</strong> Either align the stage SQL query using explicit <code>CAST(column AS ...)</code> expressions, or change <code>write_mode</code> to <code>overwrite</code>.</p>

          <div class="help-callout is-tip">
            <div class="help-callout-header">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              <span>TIP · DRY RUN VALIDATION</span>
            </div>
            <p>Before executing in production, use dry-run mode to validate queries and schemas without writing data: <code>det run my_pipeline --dry-run</code>.</p>
          </div>
        `
      }
    ]
  }
];
