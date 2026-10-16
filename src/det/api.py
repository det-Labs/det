"""Public Python functions used by the GUI and Python callers."""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from det import __version__
from det.catalog import CatalogStore, resolve_connection_options
from det.connectors import connector_metadata, scan_builtin
from det.engine import create_session_context, run_sql
from det.monitoring import MonitoringStore
from det.pipeline import PipelineStore
from det.runner import PipelineRunner
from det.workspace import validate_workspace

MODULES = ("Catalog", "ETL", "Monitoring", "Documentation", "Help")
THEMES = ("light", "dark")


@dataclass
class UiState:
    workspace: str
    module: str = "Catalog"
    theme: str = "dark"


_ui_state: UiState | None = None
_catalog_store: CatalogStore | None = None
_pipeline_store: PipelineStore | None = None
_monitoring_store: MonitoringStore | None = None


def configure_ui(workspace: str | Path) -> dict[str, str]:
    """Set the workspace backing the GUI and return the current UI state."""
    global _catalog_store, _monitoring_store, _pipeline_store, _ui_state
    resolved_workspace = validate_workspace(workspace)
    _ui_state = UiState(workspace=str(resolved_workspace))
    _catalog_store = CatalogStore(resolved_workspace)
    _pipeline_store = PipelineStore(resolved_workspace)
    _monitoring_store = MonitoringStore(resolved_workspace)
    return get_ui_state()


configure_api = configure_ui


def get_ui_state() -> dict[str, str]:
    """Return the application identity and current shell preferences."""
    if _ui_state is None:
        raise RuntimeError("Configure a workspace before requesting UI state.")
    return {
        "app_name": "det",
        "app_description": "SQL ETL workspace",
        "version": __version__,
        **asdict(_ui_state),
    }


def update_ui_state(*, module: str | None = None, theme: str | None = None) -> dict[str, str]:
    """Update a valid module/theme selection and return the resulting state."""
    if _ui_state is None:
        raise RuntimeError("Configure a workspace before updating UI state.")
    if module is not None:
        if module not in MODULES:
            raise ValueError(f"Unknown module: {module}")
        _ui_state.module = module
    if theme is not None:
        if theme not in THEMES:
            raise ValueError(f"Unknown theme: {theme}")
        _ui_state.theme = theme
    return get_ui_state()


def get_catalog_store() -> CatalogStore:
    """Return the workspace catalog store configured for this process."""
    if _catalog_store is None:
        raise RuntimeError("Configure a workspace before using the catalog.")
    return _catalog_store


def get_connector_metadata() -> list[dict[str, Any]]:
    """Return built-in and installed extension connector definitions."""
    return connector_metadata()


def infer_connection_schema(connection_id: str) -> dict[str, Any]:
    """Infer a source schema with DataFusion and persist it to the active catalog."""
    store = get_catalog_store()
    connection = store.get_connection(connection_id)
    if not connection["is_source"]:
        raise ValueError("Schema inference is available only for source connections.")
    workspace = get_ui_state()["workspace"]
    catalog_doc = store.read()["catalog"]
    options = resolve_connection_options(connection, catalog_doc)
    context = create_session_context()
    dataframe = scan_builtin(
        context,
        connection["connector"],
        options,
        workspace,
    )
    inferred = [
        {
            "name": field.name,
            "data_type": str(field.type),
            "nullable": field.nullable,
        }
        for field in dataframe.schema()
    ]
    saved = store.save_connection_columns(connection_id, inferred)
    return {"connection": saved, "columns": saved["columns"]}


def preview_connection(connection_id: str) -> dict[str, Any]:
    """Return at most 50 rows from a source connection without a full scan."""
    store = get_catalog_store()
    connection = store.get_connection(connection_id)
    if not connection["is_source"]:
        raise ValueError("Data preview is available only for source connections.")
    workspace = get_ui_state()["workspace"]
    catalog_doc = store.read()["catalog"]
    options = resolve_connection_options(connection, catalog_doc)
    context = create_session_context()
    dataframe = scan_builtin(
        context,
        connection["connector"],
        options,
        workspace,
        saved_columns=connection["columns"] or None,
    )
    view_name = f"det_preview_{connection_id.replace('-', '_')}"
    context.register_view(view_name, dataframe)
    preview = run_sql(context, f"SELECT * FROM {view_name} LIMIT 50")
    batches = preview.collect()
    import pyarrow as pa

    rows = pa.Table.from_batches(batches, schema=preview.schema()).to_pylist() if batches else []
    return {
        "columns": connection["columns"] or [
            {
                "name": field.name,
                "data_type": str(field.type),
                "nullable": field.nullable,
                "description": "",
            }
            for field in preview.schema()
        ],
        "rows": rows,
        "row_limit": 50,
    }


def preview_adhoc_connection(
    connector: str,
    options: dict[str, Any],
    columns: list[dict[str, Any]] | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Scan and preview up to limit rows directly from connection parameters without registration."""
    import time

    start_time = time.perf_counter()
    workspace = get_ui_state()["workspace"]
    context = create_session_context()
    try:
        from det.connectors import connector_definitions
        for c_def in connector_definitions():
            if connector in (c_def.key, c_def.guid):
                connector = c_def.guid
                break

        dataframe = scan_builtin(
            context,
            connector,
            options,
            workspace,
            saved_columns=columns or None,
        )
        view_name = f"det_adhoc_{uuid4().hex[:8]}"
        context.register_view(view_name, dataframe)
        preview = run_sql(context, f"SELECT * FROM {view_name} LIMIT {limit}")
        batches = preview.collect()
        import pyarrow as pa

        rows = pa.Table.from_batches(batches, schema=preview.schema()).to_pylist() if batches else []
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
        inferred_columns = [
            {
                "name": field.name,
                "data_type": str(field.type),
                "nullable": field.nullable,
                "description": "",
            }
            for field in preview.schema()
        ]
        return {
            "success": True,
            "columns": columns or inferred_columns,
            "inferred_columns": inferred_columns,
            "rows": rows,
            "row_count": len(rows),
            "row_limit": limit,
            "elapsed_ms": elapsed_ms,
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 1),
        }


def test_database_connection(
    connector: str,
    options: dict[str, Any],
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Test connectivity to a database without fetching tables."""
    import time

    start_time = time.perf_counter()
    workspace = get_ui_state()["workspace"]
    try:
        from det.connectors import build_postgres_uri, connector_definitions, resolve_env_vars

        if profile_id:
            store = get_catalog_store()
            profile = store.get_profile(profile_id)
            connector = profile["connector"]
            options = {**profile["options"], **options}

        connector_key = connector
        for c_def in connector_definitions():
            if connector in (c_def.key, c_def.guid):
                connector_key = c_def.key
                break

        resolved_options = resolve_env_vars(options, workspace)

        if connector_key == "postgresql":
            import adbc_driver_postgresql.dbapi as pg_dbapi

            uri = build_postgres_uri(resolved_options)
            with pg_dbapi.connect(uri) as conn, conn.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
                return {
                    "success": True,
                    "message": "Connected successfully!",
                    "elapsed_ms": elapsed_ms,
                }

        return {
            "success": False,
            "error": f"Connector '{connector_key}' does not support connection testing.",
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
        return {
            "success": False,
            "error": str(exc),
            "elapsed_ms": elapsed_ms,
        }


def discover_database_tables(
    connector: str,
    options: dict[str, Any],
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Discover available schemas and tables from a database connection."""
    import time

    start_time = time.perf_counter()
    workspace = get_ui_state()["workspace"]
    try:
        from det.connectors import build_postgres_uri, connector_definitions, resolve_env_vars

        if profile_id:
            store = get_catalog_store()
            profile = store.get_profile(profile_id)
            connector = profile["connector"]
            options = {**profile["options"], **options}

        connector_key = connector
        for c_def in connector_definitions():
            if connector in (c_def.key, c_def.guid):
                connector_key = c_def.key
                break

        resolved_options = resolve_env_vars(options, workspace)

        if connector_key == "postgresql":
            import adbc_driver_postgresql.dbapi as pg_dbapi

            uri = build_postgres_uri(resolved_options)
            with pg_dbapi.connect(uri) as conn, conn.cursor() as cursor:
                cursor.execute(
                    "SELECT table_schema, table_name "
                    "FROM information_schema.tables "
                    "WHERE table_schema NOT IN ('information_schema', 'pg_catalog') "
                    "ORDER BY table_schema, table_name;"
                )
                table = cursor.fetch_arrow_table()
                rows = table.to_pylist() if table else []
                tables = [
                    {"schema": r["table_schema"], "name": r["table_name"]}
                    for r in rows
                ]
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
                return {
                    "success": True,
                    "tables": tables,
                    "count": len(tables),
                    "elapsed_ms": elapsed_ms,
                }

        return {
            "success": False,
            "error": f"Connector '{connector_key}' does not support table discovery.",
            "tables": [],
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
        return {
            "success": False,
            "error": str(exc),
            "tables": [],
            "elapsed_ms": elapsed_ms,
        }


def get_pipeline_store() -> PipelineStore:
    """Return the workspace pipeline store configured for this process."""
    if _pipeline_store is None:
        raise RuntimeError("Configure a workspace before using pipelines.")
    return _pipeline_store


def get_monitoring_store() -> MonitoringStore:
    """Return the workspace monitoring store configured for this process."""
    if _monitoring_store is None:
        raise RuntimeError("Configure a workspace before using monitoring.")
    return _monitoring_store


def list_pipeline_folders() -> list[str]:
    """Return all folders in the pipeline store."""
    return get_pipeline_store().list_folders()


def list_pipelines(folder: str | None = None) -> list[dict[str, Any]]:
    """Return pipeline metadata, optionally filtered by folder."""
    return get_pipeline_store().list_pipelines(folder)


def get_pipeline(identifier: str) -> dict[str, Any]:
    """Return pipeline definition by identifier or folder/name."""
    return get_pipeline_store().get_pipeline(identifier)


def save_pipeline(data: dict[str, Any]) -> dict[str, Any]:
    """Save or update a pipeline."""
    return get_pipeline_store().save_pipeline(data)


def delete_pipeline(identifier: str) -> bool:
    """Delete a pipeline by identifier."""
    return get_pipeline_store().delete_pipeline(identifier)


def run_pipeline(identifier_or_data: str | dict[str, Any]) -> dict[str, Any]:
    """Execute a pipeline using DataFusion and record monitoring telemetry."""
    workspace = get_ui_state()["workspace"]
    runner = PipelineRunner(workspace)
    return runner.run(identifier_or_data)


def list_pipeline_runs(
    *,
    pipeline_id: str | None = None,
    pipeline_name: str | None = None,
    folder: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List execution runs from the monitoring store."""
    return get_monitoring_store().list_runs(
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_name,
        folder=folder,
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


def get_pipeline_run(run_id: str) -> dict[str, Any]:
    """Get detailed telemetry for a specific pipeline execution run."""
    return get_monitoring_store().get_run(run_id)


def get_monitoring_summary() -> dict[str, Any]:
    """Get high-level workspace health and run metrics."""
    return get_monitoring_store().workspace_summary()


def validate_pipeline(identifier_or_data: str | dict[str, Any]) -> dict[str, Any]:
    """Pre-flight validate an entire pipeline without data execution."""
    from det.validator import PipelineValidator

    workspace = get_ui_state()["workspace"]
    return PipelineValidator(workspace).validate_pipeline(identifier_or_data)


def validate_step_sql(
    sql: str,
    *,
    catalog_file: str = "default.yaml",
    prior_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate SQL query against catalog and prior steps and infer schema."""
    from det.validator import PipelineValidator

    workspace = get_ui_state()["workspace"]
    return PipelineValidator(workspace).validate_step_sql(
        sql,
        catalog_file=catalog_file,
        prior_steps=prior_steps,
    )


def generate_pipeline_docs(
    identifier_or_data: str | dict[str, Any],
    doc_format: str = "html",
) -> str:
    """Generate single-file documentation with lineage diagrams in HTML or Markdown."""
    from det.docs import PipelineDocsGenerator

    workspace = get_ui_state()["workspace"]
    return PipelineDocsGenerator(workspace).generate(identifier_or_data, doc_format=doc_format)


def save_pipeline_docs(
    identifier_or_data: str | dict[str, Any],
    doc_format: str = "html",
) -> dict[str, Any]:
    """Generate and save documentation directly into workspace's documentation/<folder>/<name>.<ext>."""
    from det.docs import PipelineDocsGenerator

    workspace = get_ui_state()["workspace"]
    return PipelineDocsGenerator(workspace).save(identifier_or_data, doc_format=doc_format)


def list_pipeline_docs() -> dict[str, Any]:
    """List all generated documentation files grouped by folders."""
    from det.docs import PipelineDocsGenerator

    workspace = get_ui_state()["workspace"]
    return PipelineDocsGenerator(workspace).list_docs()


def get_pipeline_doc(rel_path: str) -> dict[str, Any]:
    """Retrieve content and metadata of a documentation file."""
    from det.docs import PipelineDocsGenerator

    workspace = get_ui_state()["workspace"]
    return PipelineDocsGenerator(workspace).get_doc(rel_path)


def delete_pipeline_doc(rel_path: str) -> dict[str, Any]:
    """Delete a documentation file from disk."""
    from det.docs import PipelineDocsGenerator

    workspace = get_ui_state()["workspace"]
    return PipelineDocsGenerator(workspace).delete_doc(rel_path)


def regenerate_pipeline_doc(rel_path: str, doc_format: str | None = None) -> dict[str, Any]:
    """Regenerate a documentation file from its pipeline."""
    from det.docs import PipelineDocsGenerator

    workspace = get_ui_state()["workspace"]
    return PipelineDocsGenerator(workspace).regenerate_doc(rel_path, doc_format=doc_format)


def verify_pipeline_doc_sync(rel_path: str) -> dict[str, Any]:
    """Check if a documentation file is out of sync with its pipeline or catalog."""
    from det.docs import PipelineDocsGenerator

    workspace = get_ui_state()["workspace"]
    return PipelineDocsGenerator(workspace).verify_staleness(rel_path)


def install_sample_data(
    workspace: str | Path | None = None,
    *,
    select_catalog: bool = True,
    overwrite_existing: bool = True,
) -> dict[str, Any]:
    """Recreate sample warehouse source data, catalog, and pipelines in the workspace."""
    from det.sample_data import install_sample_data as _install

    ws = workspace or get_ui_state()["workspace"]
    result = _install(ws, select_catalog=select_catalog, overwrite_existing=overwrite_existing)
    if select_catalog and _catalog_store is not None:
        try:
            _catalog_store.select("sample_warehouse.yaml")
        except Exception:
            pass
    return result


