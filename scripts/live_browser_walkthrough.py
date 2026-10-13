"""Live Headed Browser Walkthrough for Windows Snipping Tool Video Recording.

Storyline:
1. Catalog: Add Parquet source ('lakehouse_orders') with description.
2. Auto schema discovery: Show Schema tab (DataFusion / Arrow types).
3. Data Preview: Show Preview tab (tabular rows).
4. Add CSV source ('raw_customers') with description & preview.
5. ETL: Create new pipeline ('sales_performance_analysis'), add description.
6. Step 1: Pure ANSI SQL joining Parquet + CSV directly (zero Jinja). Add notes.
7. Step 2: Add step ('regional_summary'), aggregate query, destination, add notes.
8. Validation: Click Validate, show validation banner.
9. Execution: Click Save / Run (twice), show sub-second execution telemetry.
10. Monitoring: View execution runs table and stage latency breakdown.
11. Back to ETL: Generate HTML docs.
12. Documentation: Inspect living HTML documentation portal with lineage DAG.
"""

import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
UI_PATH = (Path(__file__).parent.parent / "src" / "det" / "ui" / "index.html").resolve()

def run_live_walkthrough():
    print("\n" + "=" * 70)
    print("🎬 DET LIVE HEADED BROWSER DEMO WALKTHROUGH")
    print("=" * 70)
    print("1. Set up your Windows Snipping Tool Screen Recorder (Win + Shift + R).")
    print("2. Edge will open maximized in 5 seconds.")
    print("3. Hit RECORD as soon as Edge opens!")
    print("=" * 70)

    for i in range(7, 0, -1):
        print(f"   Starting in {i}...", flush=True)
        time.sleep(1.0)

    print("\n🚀 Launching Microsoft Edge now!\n", flush=True)

    import tempfile
    import shutil
    profile_dir = tempfile.mkdtemp(prefix="det_edge_demo_")

    with sync_playwright() as p:
        browser = None
        context = None
        is_cdp = False
        try:
            print("Trying to connect to running Edge on port 9222 via CDP...", flush=True)
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
            is_cdp = True
            print("🎉 Successfully connected to your visible Edge window!", flush=True)
        except Exception as e:
            print("Port 9222 not running, launching persistent Edge context...", flush=True)
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                executable_path=EDGE_EXE,
                headless=False,
                viewport=None,
                no_viewport=True,
                args=[
                    "--start-maximized",
                    "--new-window",
                    "--no-default-browser-check",
                    "--disable-extensions",
                ]
            )
            page = context.pages[0] if context.pages else context.new_page()

        page.on("dialog", lambda d: d.accept())
        page.goto(UI_PATH.as_uri())
        time.sleep(2.5)

        # =============================================================
        # 1. CATALOG: Add Parquet Source with Description
        # =============================================================
        print("▶ [0:00 - 0:08] 1. Catalog: Adding Parquet Source...", flush=True)
        folder = page.locator(".folder-row").first
        if folder.count() > 0:
            folder.hover()
            time.sleep(0.6)

        add_btn = page.locator("button.tree-action[data-action='add-connection']").first
        if add_btn.count() > 0:
            add_btn.click(force=True)
            time.sleep(1.0)

            # Name
            name_in = page.locator("#editor-form input[name='name']")
            if name_in.count() > 0:
                name_in.fill("lakehouse_orders")
            time.sleep(0.5)

            # Connector: Parquet
            conn_sel = page.locator("#editor-form select[name='connector']")
            if conn_sel.count() > 0:
                try:
                    conn_sel.select_option(label="Parquet")
                except Exception:
                    page.evaluate("() => { const s = document.querySelector('#editor-form select[name=\"connector\"]'); if (s) { for (let opt of s.options) { if (opt.text.toLowerCase().includes('parquet')) { s.value = opt.value; s.dispatchEvent(new Event('change')); break; } } } }")
            time.sleep(0.5)

            # Description
            desc_in = page.locator("#editor-form textarea[name='description']")
            if desc_in.count() > 0:
                desc_in.fill("Partitioned Parquet sales orders lakehouse from S3 object storage")
            time.sleep(1.0)

            # Close dialog (to showcase existing connections in demo mode)
            page.locator("#dialog-cancel").click(force=True)
            page.evaluate("() => { const d = document.querySelector('#editor-dialog'); if (d && d.open) d.close(); }")
            time.sleep(0.8)

        # =============================================================
        # 2. AUTO SCHEMA DISCOVERY FOR PARQUET
        # =============================================================
        print("▶ [0:08 - 0:16] 2. Auto Schema Discovery for Parquet...", flush=True)
        # Select raw_orders (Parquet source)
        order_conn = page.locator(".connection-select", has_text="raw_orders")
        if order_conn.count() > 0:
            order_conn.first.click(force=True)
        else:
            page.locator(".connection-select").first.click(force=True)
        time.sleep(1.2)

        # Click Schema tab to showcase auto-discovered types
        schema_tab = page.locator(".detail-tab", has_text="Schema")
        if schema_tab.count() > 0:
            schema_tab.click(force=True)
            time.sleep(2.5)

        # =============================================================
        # 3. PREVIEW ROWS
        # =============================================================
        print("▶ [0:16 - 0:24] 3. Tabular Data Preview...", flush=True)
        preview_tab = page.locator(".detail-tab", has_text="Preview")
        if preview_tab.count() > 0:
            preview_tab.click(force=True)
            time.sleep(2.5)

        # =============================================================
        # 4. ADD CSV SOURCE & PREVIEW ROWS
        # =============================================================
        print("▶ [0:24 - 0:31] 4. CSV Source & Preview Rows...", flush=True)
        cust_conn = page.locator(".connection-select", has_text="raw_customers")
        if cust_conn.count() > 0:
            cust_conn.first.click(force=True)
            time.sleep(1.0)
            preview_tab = page.locator(".detail-tab", has_text="Preview")
            if preview_tab.count() > 0:
                preview_tab.click(force=True)
                time.sleep(2.2)

        # =============================================================
        # 5. MOVE TO ETL • CREATE NEW PIPELINE • ADD DESCRIPTION
        # =============================================================
        print("▶ [0:31 - 0:42] 5. ETL: Create Pipeline & Join Parquet + CSV...", flush=True)
        page.locator("button.module-tab[data-module='ETL']").click(force=True)
        time.sleep(1.2)

        # Set pipeline name and description in current view
        page.locator("#etl-pipeline-name-input").fill("sales_performance_analysis")
        time.sleep(0.5)

        # Open Pipeline Overview accordion and fill description
        page.evaluate("() => { const acc = document.querySelector('#etl-overview-details'); if (acc) acc.open = true; }")
        time.sleep(0.5)
        page.locator("#etl-pipeline-description").fill(
            "End-to-end customer sales pipeline: joins Parquet lakehouse orders with CSV demographics, computes regional KPIs, and publishes curated summaries."
        )
        time.sleep(1.2)

        # Step 1: Name and SQL Query joining both files directly
        page.locator("#etl-step-name-input").fill("joined_orders_customers")
        time.sleep(0.5)

        multi_source_sql = (
            "-- Step 1: Direct JOIN of Parquet Lakehouse + CSV Demographics\n"
            "-- Pure ANSI SQL • Zero Jinja • Evaluated by Apache DataFusion\n"
            "SELECT \n"
            "    o.order_id, \n"
            "    o.customer_id, \n"
            "    c.first_name || ' ' || c.last_name AS customer_name,\n"
            "    c.city,\n"
            "    c.region,\n"
            "    o.net_amount,\n"
            "    o.order_date\n"
            "FROM raw_orders o                  -- Parquet lakehouse\n"
            "JOIN raw_customers c               -- CSV customer master\n"
            "  ON o.customer_id = c.customer_id\n"
            "WHERE o.order_status = 'Completed';"
        )
        sql_box = page.locator("#etl-sql-textarea")
        sql_box.fill(multi_source_sql)
        page.evaluate("() => { const el = document.querySelector('#etl-sql-textarea'); if (el) el.dispatchEvent(new Event('input')); }")
        time.sleep(2.5)

        # =============================================================
        # 6. ADD NOTES FOR STEP 1 & STEP 2 WITH DESTINATION
        # =============================================================
        print("▶ [0:42 - 0:52] 6. Step Notes, Step 2 Aggregates & Destination...", flush=True)
        # Open Notes for Step 1
        page.locator("#etl-tab-notes").click(force=True)
        time.sleep(0.8)
        page.locator("#etl-step-desc-input").fill(
            "Join raw Parquet orders with CSV customer demographics into an in-engine virtual view."
        )
        time.sleep(1.5)

        # Add Step 2
        page.locator("#etl-add-step-button").click(force=True)
        time.sleep(1.0)
        page.locator("#etl-step-name-input").fill("regional_sales_summary")
        time.sleep(0.5)

        # Step 2 SQL
        agg_sql = (
            "-- Step 2: Regional aggregations referencing prior step\n"
            "SELECT \n"
            "    region,\n"
            "    COUNT(order_id) AS total_orders,\n"
            "    ROUND(SUM(net_amount), 2) AS regional_revenue,\n"
            "    ROUND(AVG(net_amount), 2) AS avg_order_value\n"
            "FROM joined_orders_customers\n"
            "GROUP BY region\n"
            "ORDER BY regional_revenue DESC;"
        )
        sql_box.fill(agg_sql)
        page.evaluate("() => { const el = document.querySelector('#etl-sql-textarea'); if (el) el.dispatchEvent(new Event('input')); }")
        time.sleep(1.5)

        # Step 2 Destinations: add destination chip
        page.evaluate("""() => {
            if (window.activePipeline && window.activePipeline.steps && window.activePipeline.steps[1]) {
                window.activePipeline.steps[1].destinations = ['dw_rfm_segments_csv', 'curated_lakehouse_parquet'];
                window.activePipeline.steps[1].keep_temporary = false;
                if (typeof renderDestinations === 'function') renderDestinations();
            }
        }""")
        time.sleep(1.2)

        # Step 2 Notes
        page.evaluate("() => { const n = document.querySelector('#notes-editor-container'); if (n && n.hidden) { const btn = document.querySelector('#etl-tab-notes'); if (btn) btn.click(); } }")
        time.sleep(0.5)
        notes_in = page.locator("#etl-step-desc-input")
        if notes_in.count() > 0 and notes_in.is_visible():
            notes_in.fill(
                "Aggregate lifetime metrics by region and publish directly to curated Parquet and CSV destinations."
            )
        time.sleep(1.5)

        # =============================================================
        # 7. VALIDATE PIPELINE • SHOW VALIDATION RESULT
        # =============================================================
        print("▶ [0:52 - 1:02] 7. Validate Pipeline & In-Engine Run...", flush=True)
        val_btn = page.locator("#etl-validate-button")
        val_btn.click(force=True)
        time.sleep(2.0)

        # =============================================================
        # 8. RUN TWICE • SHOW REAL-TIME TELEMETRY
        # =============================================================
        print("▶ [1:02 - 1:12] 8. Run Twice & Telemetry...", flush=True)
        run_btn = page.locator("#etl-run-button")
        run_btn.click(force=True)
        time.sleep(2.5)

        # Second run
        print("   Running a second time...", flush=True)
        run_btn.click(force=True)
        time.sleep(2.5)

        # =============================================================
        # 9. MONITORING: DETAILED RUN RESULTS & LATENCIES
        # =============================================================
        print("▶ [1:12 - 1:20] 9. Monitoring: Detailed Latencies...", flush=True)
        page.locator("button.module-tab[data-module='Monitoring']").click(force=True)
        time.sleep(1.5)

        first_run = page.locator("#monitoring-runs-tbody tr[data-run-id]").first
        if first_run.count() > 0:
            first_run.click(force=True)
            time.sleep(2.5)

        # =============================================================
        # 10. BACK TO ETL • GENERATE HTML DOCS
        # =============================================================
        print("▶ [1:20 - 1:28] 10. Generate HTML Documentation...", flush=True)
        page.locator("button.module-tab[data-module='ETL']").click(force=True)
        time.sleep(1.2)

        docs_btn = page.locator("#etl-docs-button")
        if docs_btn.count() > 0:
            docs_btn.click(force=True)
            time.sleep(2.0)

        # =============================================================
        # 11. DOCUMENTATION: INSPECT LIVING HTML DOC & LINEAGE DAG
        # =============================================================
        print("▶ [1:28 - 1:36] 11. Documentation Viewer & Lineage DAG...", flush=True)
        page.locator("button.module-tab[data-module='Documentation']").click(force=True)
        time.sleep(1.5)

        doc_item = page.locator("#docs-tree [data-doc-path]").first
        if doc_item.count() > 0:
            doc_item.click(force=True)
            time.sleep(3.5)

        print("\n" + "=" * 70)
        print("🎉 COMPLETE! Walkthrough finished smoothly.")
        print("   Pausing 5 seconds so you can click STOP on Snipping Tool!")
        print("=" * 70 + "\n")
        time.sleep(5.0)

        context.close()

    try:
        shutil.rmtree(profile_dir, ignore_errors=True)
    except Exception:
        pass

if __name__ == "__main__":
    run_live_walkthrough()
