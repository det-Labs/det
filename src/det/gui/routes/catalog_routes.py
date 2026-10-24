"""Catalog and connection configuration REST endpoints for the Web IDE."""

from http.server import BaseHTTPRequestHandler
import logging
import time
from typing import Any

from det.catalog.base import ConnectionTier
from det.catalog.definitions import ConnectionDefinition
from det.extensions.registry import global_registry
from det.gui.base import BaseRouteHandler
from det.gui.routes.common import send_error_json, send_json
from det.workspace import Workspace

logger = logging.getLogger(__name__)


class CatalogRouteHandler(BaseRouteHandler):
    """Handles REST routes for data source connectors, catalog CRUD, and live queries."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def handle_get(self, handler: BaseHTTPRequestHandler, path: str) -> bool:
        """Process GET requests for catalog schemas and connections."""
        if path == "/api/catalog/connectors":
            send_json(handler, global_registry.list_schemas())
            return True
        if path == "/api/catalog/connections":
            conns = [
                {"name": c.name, "folder": c.folder, **c.to_dict()}
                for c in self._workspace.catalog.list_connections()
            ]
            send_json(handler, conns)
            return True
        return False

    def handle_post(
        self, handler: BaseHTTPRequestHandler, path: str, body: dict[str, Any]
    ) -> bool:
        """Process POST requests for catalog mutation, testing, and queries."""
        if path == "/api/catalog/connections":
            return self._handle_save_connection(handler, body)
        if path == "/api/catalog/connections/delete":
            return self._handle_delete_connection(handler, body)
        if path == "/api/catalog/test":
            return self._handle_test_connection(handler, body)
        if path == "/api/catalog/query":
            return self._handle_query(handler, body)
        return False

    def _handle_save_connection(
        self, handler: BaseHTTPRequestHandler, body: dict[str, Any]
    ) -> bool:
        """Create or update a connection definition and mount it into session."""
        name = str(body.get("name", "")).strip()
        conn_type = str(body.get("type", "")).strip()
        if not name or not conn_type:
            send_error_json(handler, "Connection 'name' and 'type' are required.")
            return True

        from det.validation import validate_identifier
        try:
            name = validate_identifier(name, "Connection name")
        except ValueError as ve:
            send_error_json(handler, str(ve))
            return True

        tier_str = body.get("tier", ConnectionTier.ENTITY.value)
        tier = ConnectionTier.DATABASE if tier_str == "database" else ConnectionTier.ENTITY
        conn_def = ConnectionDefinition(
            name=name,
            type=conn_type,
            tier=tier,
            options=body.get("options", {}),
            credentials=body.get("credentials", {}),
            description=body.get("description", ""),
            folder=body.get("folder", ""),
        )

        self._workspace.catalog.add_connection(conn_def, persist=True)
        self._workspace.mount_catalog()
        send_json(handler, {"status": "ok", "message": f"Connection '{name}' saved & mounted."})
        return True

    def _handle_delete_connection(
        self, handler: BaseHTTPRequestHandler, body: dict[str, Any]
    ) -> bool:
        """Remove a connection definition from catalog and disk."""
        name = str(body.get("name", "")).strip()
        if not name:
            send_error_json(handler, "Connection name is required for deletion.")
            return True

        deleted = self._workspace.catalog.delete_connection(name, persist=True)
        if deleted:
            send_json(handler, {"status": "ok", "message": f"Connection '{name}' deleted."})
        else:
            send_error_json(handler, f"Connection '{name}' not found.", status_code=404)
        return True

    def _handle_test_connection(
        self, handler: BaseHTTPRequestHandler, body: dict[str, Any]
    ) -> bool:
        """Execute a connection health check probe and latency benchmark."""
        name = body.get("name")
        if name and name in self._workspace.catalog._connections:
            conn_def = self._workspace.catalog.get_connection(name)
        else:
            tier_str = body.get("tier", ConnectionTier.ENTITY.value)
            tier = ConnectionTier.DATABASE if tier_str == "database" else ConnectionTier.ENTITY
            conn_def = ConnectionDefinition(
                name=name or "temp_probe",
                type=str(body.get("type", "duckdb")),
                tier=tier,
                options=body.get("options", {}),
                credentials=body.get("credentials", {}),
            )

        conn_name = name or "temp_probe"
        result = self._workspace.catalog._tester.test_connection(
            self._workspace.engine.session, conn_def
        )
        send_json(handler, {
            "name": conn_name,
            "healthy": result.is_healthy,
            "latency_ms": result.latency_ms,
            "error_message": result.error_message,
        })
        return True

    def _handle_query(
        self, handler: BaseHTTPRequestHandler, body: dict[str, Any]
    ) -> bool:
        """Execute ad-hoc SQL query against active DuckDB engine session."""
        sql = str(body.get("query", "")).strip()
        if not sql:
            send_error_json(handler, "Query string cannot be empty.")
            return True

        start_time = time.perf_counter()
        try:
            rel = self._workspace.engine.session.sql(sql)
            columns = list(rel.columns) if hasattr(rel, "columns") and rel.columns else []
            rows = rel.limit(100).fetchall() if columns else []
            duration = round((time.perf_counter() - start_time) * 1000, 2)
            serialized_rows = [self._serialize_row(r) for r in rows]

            send_json(handler, {
                "columns": columns,
                "rows": serialized_rows,
                "row_count": len(serialized_rows),
                "duration_ms": duration,
            })
        except Exception as exc:
            logger.exception("Scratchpad query failed: %s", exc)
            send_error_json(handler, f"Query error: {exc}")
        return True

    def _serialize_row(self, row: tuple[Any, ...]) -> list[Any]:
        """Convert row values to JSON-serializable primitives."""
        return [
            str(val) if val is not None and not isinstance(val, (int, float, bool, str)) else val
            for val in row
        ]
