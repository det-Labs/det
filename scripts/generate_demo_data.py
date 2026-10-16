"""Generate demo-data.js for standalone static GitHub Pages demonstration."""

from dataclasses import asdict
import json
from pathlib import Path
import tempfile

import det
from det.catalog import CatalogStore
from det.connectors import connector_definitions
from det.docs import PipelineDocsGenerator
from det.pipeline import PipelineStore
from det.sample_data import install_sample_data


def generate_demo_data() -> None:
    temp_dir = Path(tempfile.mkdtemp())
    det.Workspace(temp_dir)
    install_sample_data(temp_dir)

    cat_store = CatalogStore(temp_dir)
    pipe_store = PipelineStore(temp_dir)

    # 1. State
    state = {
        "app_name": "det",
        "app_description": "SQL ETL workspace",
        "version": "0.2.2",
        "workspace": "NovaMart_Global_Warehouse",
        "module": "Catalog",
        "theme": "light",
    }

    # 2. Connectors
    from det.connectors import connector_metadata
    connectors = connector_metadata()

    # 3. Catalogs list & active catalog
    catalogs_list = ["sample_warehouse.yaml", "default.yaml"]
    cat_store.select("sample_warehouse.yaml")
    catalog_data = cat_store.read()

    # 4. Pipelines
    pipeline_list = pipe_store.list_pipelines()
    pipeline_details = {}
    for p in pipeline_list:
        p_key = f"{p['folder']}/{p['name']}"
        pipeline_details[p_key] = pipe_store.get_pipeline(p_key)

    # 5. Monitoring runs (synthetic production runs)
    monitoring_runs = [
        {
            "id": "run-001",
            "run_id": "run-001",
            "pipeline_name": "mart_customer_rfm_loyalty",
            "pipeline_name_at_run": "mart_customer_rfm_loyalty",
            "folder_at_run": "Sample_Warehouse_Pipelines",
            "status": "SUCCESS",
            "started_at": "2026-10-13T09:15:00Z",
            "finished_at": "2026-10-13T09:15:00.042Z",
            "total_duration_seconds": 0.042,
            "steps": [
                {"step_name": "compute_rfm_scores", "status": "SUCCESS", "duration_ms": 22.4, "rows_processed": 500},
                {"step_name": "segment_loyalty_tiers", "status": "SUCCESS", "duration_ms": 19.6, "rows_processed": 500},
            ],
            "rows_processed": 500,
        },
        {
            "id": "run-002",
            "run_id": "run-002",
            "pipeline_name": "mart_store_performance_vs_targets",
            "pipeline_name_at_run": "mart_store_performance_vs_targets",
            "folder_at_run": "Sample_Warehouse_Pipelines",
            "status": "SUCCESS",
            "started_at": "2026-10-13T09:12:00Z",
            "finished_at": "2026-10-13T09:12:00.038Z",
            "total_duration_seconds": 0.038,
            "steps": [
                {"step_name": "aggregate_actuals", "status": "SUCCESS", "duration_ms": 18.2, "rows_processed": 250},
                {"step_name": "compute_attainment_pct", "status": "SUCCESS", "duration_ms": 19.8, "rows_processed": 50},
            ],
            "rows_processed": 50,
        },
        {
            "id": "run-003",
            "run_id": "run-003",
            "pipeline_name": "fct_orders",
            "pipeline_name_at_run": "fct_orders",
            "folder_at_run": "Sample_Warehouse_Pipelines",
            "status": "SUCCESS",
            "started_at": "2026-10-13T09:10:00Z",
            "finished_at": "2026-10-13T09:10:00.029Z",
            "total_duration_seconds": 0.029,
            "steps": [
                {"step_name": "dedup_and_clean", "status": "SUCCESS", "duration_ms": 15.1, "rows_processed": 1000},
                {"step_name": "enrich_order_amounts", "status": "SUCCESS", "duration_ms": 13.9, "rows_processed": 1000},
            ],
            "rows_processed": 1000,
        },
        {
            "id": "run-004",
            "run_id": "run-004",
            "pipeline_name": "dim_customers",
            "pipeline_name_at_run": "dim_customers",
            "folder_at_run": "Sample_Warehouse_Pipelines",
            "status": "SUCCESS",
            "started_at": "2026-10-13T09:05:00Z",
            "finished_at": "2026-10-13T09:05:00.018Z",
            "total_duration_seconds": 0.018,
            "steps": [
                {"step_name": "normalize_customer_profiles", "status": "SUCCESS", "duration_ms": 18.0, "rows_processed": 100},
            ],
            "rows_processed": 100,
        },
    ]

    monitoring_summary = {
        "health_status": "Healthy",
        "total_runs": 14,
        "success_count": 14,
        "failure_count": 0,
        "success_rate": 100.0,
        "average_duration_seconds": 0.028,
        "last_run_status": "SUCCESS",
        "last_run_time": "2026-10-13T09:15:00Z",
    }

    def make_preview(col_tuples, row_dicts):
        return {
            "columns": [
                {"name": c[0], "data_type": c[1], "nullable": True, "description": ""}
                for c in col_tuples
            ],
            "rows": row_dicts,
            "row_limit": 50,
            "total_rows_sampled": len(row_dicts),
        }

    # 6. Sample preview table data for connections matching api.py contract
    previews = {
        "raw_customers": make_preview(
            [("customer_id", "Utf8"), ("first_name", "Utf8"), ("last_name", "Utf8"), ("email", "Utf8"), ("city", "Utf8"), ("state", "Utf8"), ("loyalty_status", "Utf8"), ("credit_balance", "Float64")],
            [
                {"customer_id": "C001", "first_name": "Emma", "last_name": "Watson", "email": "emma.w@example.com", "city": "Seattle", "state": "WA", "loyalty_status": "Gold", "credit_balance": 150.0},
                {"customer_id": "C002", "first_name": "Liam", "last_name": "Smith", "email": "liam.s@example.com", "city": "Portland", "state": "OR", "loyalty_status": "Silver", "credit_balance": 25.5},
                {"customer_id": "C003", "first_name": "Olivia", "last_name": "Garcia", "email": "olivia.g@example.com", "city": "Austin", "state": "TX", "loyalty_status": "Platinum", "credit_balance": 480.0},
                {"customer_id": "C004", "first_name": "Noah", "last_name": "Martin", "email": "noah.m@example.com", "city": "Denver", "state": "CO", "loyalty_status": "Bronze", "credit_balance": 0.0},
                {"customer_id": "C005", "first_name": "Sophia", "last_name": "Muller", "email": "sophia.m@example.com", "city": "Chicago", "state": "IL", "loyalty_status": "Gold", "credit_balance": 75.0},
            ]
        ),
        "raw_stores": make_preview(
            [("store_id", "Utf8"), ("store_type", "Utf8"), ("name", "Utf8"), ("city", "Utf8"), ("state", "Utf8"), ("region", "Utf8"), ("sqft", "Int64"), ("opened_year", "Int64")],
            [
                {"store_id": "STR_001", "store_type": "Flagship", "name": "NovaMart Downtown Seattle", "city": "Seattle", "state": "WA", "region": "Northwest", "sqft": 45000, "opened_year": 2018},
                {"store_id": "STR_002", "store_type": "Outlet", "name": "NovaMart Portland Hillsboro", "city": "Portland", "state": "OR", "region": "Northwest", "sqft": 28000, "opened_year": 2020},
                {"store_id": "STR_003", "store_type": "Flagship", "name": "NovaMart Austin Domain", "city": "Austin", "state": "TX", "region": "Southwest", "sqft": 52000, "opened_year": 2019},
            ]
        ),
        "raw_orders": make_preview(
            [("order_id", "Utf8"), ("customer_id", "Utf8"), ("product_id", "Utf8"), ("store_id", "Utf8"), ("order_date", "Utf8"), ("currency", "Utf8"), ("quantity", "Int64"), ("unit_price", "Float64"), ("payment_method", "Utf8")],
            [
                {"order_id": "ORD-2026-001", "customer_id": "C001", "product_id": "PRD-01", "store_id": "STR_001", "order_date": "2026-01-04", "currency": "USD", "quantity": 1, "unit_price": 199.99, "payment_method": "Credit Card"},
                {"order_id": "ORD-2026-002", "customer_id": "C003", "product_id": "PRD-02", "store_id": "STR_003", "order_date": "2026-01-05", "currency": "USD", "quantity": 2, "unit_price": 349.50, "payment_method": "Apple Pay"},
                {"order_id": "ORD-2026-003", "customer_id": "C002", "product_id": "PRD-03", "store_id": "STR_001", "order_date": "2026-01-08", "currency": "USD", "quantity": 1, "unit_price": 49.99, "payment_method": "Debit Card"},
            ]
        ),
        "raw_products": make_preview(
            [("product_id", "Utf8"), ("product_name", "Utf8"), ("category", "Utf8"), ("sub_category", "Utf8"), ("cost_price_usd", "Float64"), ("retail_price_usd", "Float64"), ("sku", "Utf8"), ("is_active", "Boolean")],
            [
                {"product_id": "PRD-01", "product_name": "Quantum Wireless Headphones", "category": "Electronics", "sub_category": "Audio", "cost_price_usd": 85.0, "retail_price_usd": 199.99, "sku": "SKU-QWH-01", "is_active": True},
                {"product_id": "PRD-02", "product_name": "Ergonomic Mesh Chair", "category": "Furniture", "sub_category": "Office", "cost_price_usd": 140.0, "retail_price_usd": 349.50, "sku": "SKU-EMC-02", "is_active": True},
                {"product_id": "PRD-03", "product_name": "Cold Brew Coffee Maker", "category": "Appliances", "sub_category": "Kitchen", "cost_price_usd": 18.5, "retail_price_usd": 49.99, "sku": "SKU-CBC-03", "is_active": True},
            ]
        ),
        "raw_exchange_rates": make_preview(
            [("currency_code", "Utf8"), ("currency_name", "Utf8"), ("rate_to_usd", "Float64"), ("effective_date", "Utf8")],
            [
                {"currency_code": "USD", "currency_name": "US Dollar", "rate_to_usd": 1.000, "effective_date": "2026-01-01"},
                {"currency_code": "EUR", "currency_name": "Euro", "rate_to_usd": 1.085, "effective_date": "2026-01-01"},
                {"currency_code": "GBP", "currency_name": "British Pound", "rate_to_usd": 1.272, "effective_date": "2026-01-01"},
            ]
        ),
        "raw_store_targets": make_preview(
            [("store_id", "Utf8"), ("monthly_target_usd", "Float64"), ("quarterly_target_usd", "Float64"), ("region", "Utf8")],
            [
                {"store_id": "STR_001", "monthly_target_usd": 150000.0, "quarterly_target_usd": 450000.0, "region": "Northwest"},
                {"store_id": "STR_002", "monthly_target_usd": 90000.0, "quarterly_target_usd": 270000.0, "region": "Northwest"},
                {"store_id": "STR_003", "monthly_target_usd": 180000.0, "quarterly_target_usd": 540000.0, "region": "Southwest"},
            ]
        ),
        "raw_returns": make_preview(
            [("return_id", "Utf8"), ("order_id", "Utf8"), ("product_id", "Utf8"), ("customer_id", "Utf8"), ("return_reason", "Utf8"), ("refund_amount_usd", "Float64")],
            [
                {"return_id": "RET-001", "order_id": "ORD-2026-001", "product_id": "PRD-01", "customer_id": "C001", "return_reason": "Defective item", "refund_amount_usd": 199.99},
            ]
        ),
        "raw_clickstream": make_preview(
            [("event_id", "Utf8"), ("customer_id", "Utf8"), ("session_id", "Utf8"), ("event_type", "Utf8"), ("device_type", "Utf8")],
            [
                {"event_id": "EVT-1001", "customer_id": "C001", "session_id": "SES-9821", "event_type": "view_product", "device_type": "mobile_ios"},
                {"event_id": "EVT-1002", "customer_id": "C001", "session_id": "SES-9821", "event_type": "add_to_cart", "device_type": "mobile_ios"},
            ]
        ),
        "raw_supplier_shipments": make_preview(
            [("shipment_id", "Utf8"), ("product_id", "Utf8"), ("supplier_name", "Utf8"), ("quantity_received", "Int64"), ("delivery_status", "Utf8"), ("total_cost_usd", "Float64")],
            [
                {"shipment_id": "SHP-501", "product_id": "PRD-01", "supplier_name": "AcousticTech Shenzen", "quantity_received": 500, "delivery_status": "Delivered", "total_cost_usd": 42500.0},
            ]
        ),
    }

    # 7. Documentation list and pre-rendered HTML content
    gen = PipelineDocsGenerator(temp_dir)
    docs_items = []
    docs_contents = {}

    for p in pipeline_list:
        p_name = p["name"]
        p_folder = p["folder"]
        rel_path = f"{p_folder}/{p_name}.html"
        try:
            html_content = gen.generate(f"{p_folder}/{p_name}", doc_format="html")
        except Exception:
            html_content = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{p_name}</title><style>body{{font-family:sans-serif;padding:2rem;background:#0f172a;color:#f8fafc;}}</style></head><body><h1>Pipeline: {p_name}</h1><p>Folder: {p_folder}</p><p>SQL ETL Pipeline documentation generated by det.</p></body></html>"""

        docs_contents[rel_path] = html_content
        docs_contents[p_name] = html_content
        docs_items.append({
            "path": rel_path,
            "folder": p_folder,
            "name": p_name,
            "format": "html",
            "pipeline_name": p_name,
            "bytes": len(html_content.encode("utf-8")),
            "content": html_content,
        })

    docs = {
        "folders": ["Sample_Warehouse_Pipelines"],
        "items": docs_items,
    }

    demo_bundle = {
        "state": state,
        "connectors": connectors,
        "catalogs": catalogs_list,
        "active_catalog_name": "sample_warehouse.yaml",
        "catalog": catalog_data,
        "pipelines": pipeline_list,
        "pipeline_details": pipeline_details,
        "monitoring_runs": monitoring_runs,
        "monitoring_summary": monitoring_summary,
        "previews": previews,
        "docs": docs,
        "docs_contents": docs_contents,
    }

    out_file = Path(__file__).parent.parent / "src" / "det" / "ui" / "demo-data.js"
    json_str = json.dumps(demo_bundle, indent=2)
    js_content = f"// Pre-built NovaMart Global sample warehouse data for static demonstration\nwindow.DET_DEMO_DATA = {json_str};\n"
    out_file.write_text(js_content, encoding="utf-8")
    print(f"Generated demo-data.js ({len(js_content)} bytes) at {out_file}")


if __name__ == "__main__":
    generate_demo_data()

