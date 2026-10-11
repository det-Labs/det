"""SQLite database connector supporting connections, table/view discovery, schema inference, and data preview."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import polars as pl

from det.catalog.models import ColumnMetadata
from det.connectors.contract import (
    BaseConnector,
    ConfigField,
    ConnectionTestResult,
    ConnectorGroup,
    DiscoveredObject,
    FieldType,
    PreviewResult,
    SchemaResult,
)
from det.connectors.errors import (
    ConnectorValidationError,
    DiscoveryError,
    PreviewError,
    SchemaInferenceError,
)


def map_sqlite_type_to_standard(sqlite_type: str | None) -> str:
    """Map SQLite declared column type to standard catalog data type."""
    if not sqlite_type:
        return "String"
    t = sqlite_type.strip().upper()
    if any(k in t for k in ("INT", "SERIAL")):
        return "Int64"
    if any(k in t for k in ("REAL", "FLOAT", "DOUBL", "DECIMAL", "NUMERIC")):
        return "Float64"
    if "BOOL" in t:
        return "Boolean"
    if any(k in t for k in ("DATE", "TIME")):
        return "DateTime"
    if any(k in t for k in ("BLOB", "BINARY")):
        return "Binary"
    if "JSON" in t:
        return "JSON"
    return "String"


class SQLiteConnector(BaseConnector):
    """Connector for SQLite embedded databases (.db, .sqlite, .sqlite3)."""

    id = "sqlite"
    name = "SQLite"
    group = ConnectorGroup.DATABASES
    description = "Embedded relational database (SQLite .db, .sqlite, .sqlite3 files)"

    source_fields = [
        ConfigField(
            name="database_path",
            label="Database File Path",
            type=FieldType.STRING,
            required=True,
            placeholder="D:/data/app.db or :memory:",
            description="Path to SQLite database file on local filesystem or :memory:.",
        ),
        ConfigField(
            name="read_only",
            label="Read-Only Mode",
            type=FieldType.BOOLEAN,
            default=True,
            advanced=True,
            description="Open SQLite database in read-only mode to prevent accidental changes.",
        ),
        ConfigField(
            name="timeout",
            label="Busy Timeout (seconds)",
            type=FieldType.INTEGER,
            default=5,
            advanced=True,
            description="Timeout in seconds when database is locked by another process.",
        ),
    ]

    table_fields = [
        ConfigField(
            name="table_name",
            label="Table or View Name",
            type=FieldType.STRING,
            required=True,
            placeholder="e.g. customers, orders_view",
            description="Name of the table or view in the SQLite database.",
        ),
        ConfigField(
            name="query",
            label="Custom SQL Query (optional)",
            type=FieldType.TEXTAREA,
            advanced=True,
            placeholder="SELECT id, name FROM users WHERE active = 1",
            description="Optional custom SELECT statement. If specified, overrides Table Name.",
        ),
        ConfigField(
            name="columns",
            label="Column Projection (optional)",
            type=FieldType.STRING,
            advanced=True,
            placeholder="col1, col2, col3",
            description="Comma-separated column names to include in preview and scans.",
        ),
    ]

    def _resolve_db_path(
        self,
        source_config: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
    ) -> str:
        s_cfg = source_config or {}
        t_opts = table_options or {}
        path_str = (
            s_cfg.get("database_path")
            or s_cfg.get("path")
            or t_opts.get("database_path")
            or t_opts.get("path")
            or ""
        )
        path_str = str(path_str).strip()
        if not path_str:
            raise ConnectorValidationError(
                "SQLite database path is required in connection or table options."
            )
        if path_str == ":memory:":
            return ":memory:"
        p = Path(path_str).expanduser()
        return str(p.resolve())

    def _open_connection(
        self,
        db_path: str,
        read_only: bool = True,
        timeout: int = 5,
    ) -> sqlite3.Connection:
        if db_path != ":memory:":
            if not os.path.exists(db_path):
                raise ConnectorValidationError(
                    f"SQLite database file not found: '{db_path}'"
                )
            if read_only:
                try:
                    posix_path = Path(db_path).resolve().as_posix()
                    # SQLite URI mode for read-only
                    uri = f"file:///{posix_path}?mode=ro" if posix_path.startswith("/") or ":" in posix_path else f"file:{posix_path}?mode=ro"
                    return sqlite3.connect(uri, uri=True, timeout=timeout)
                except Exception:
                    # Fallback if URI mode fails
                    pass
        return sqlite3.connect(db_path, timeout=timeout)

    def test_connection(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ConnectionTestResult:
        try:
            db_path = self._resolve_db_path(source_config, table_options)
            timeout = int((source_config or {}).get("timeout", 5))
            conn = self._open_connection(db_path, read_only=True, timeout=timeout)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1;")
                cursor.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%';"
                )
                table_count = cursor.fetchone()[0]
            finally:
                conn.close()

            if db_path == ":memory:":
                size_str = "in-memory"
            else:
                size_bytes = os.path.getsize(db_path)
                size_str = f"{size_bytes / 1024:.1f} KB"

            return ConnectionTestResult(
                success=True,
                message=f"Connected successfully to SQLite database ({size_str}, {table_count} tables/views found).",
                details={"table_count": table_count, "database_path": db_path},
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"SQLite connection failed: {e}",
            )

    def discover_objects(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[DiscoveredObject]:
        try:
            db_path = self._resolve_db_path(source_config, options)
            timeout = int((source_config or {}).get("timeout", 5))
            conn = self._open_connection(db_path, read_only=True, timeout=timeout)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT type, name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name;"
                )
                rows = cursor.fetchall()
            finally:
                conn.close()

            results: list[DiscoveredObject] = []
            for obj_type, name in rows:
                results.append(
                    DiscoveredObject(
                        id=name,
                        name=name,
                        type=obj_type,
                        path=name,
                        metadata={"type": obj_type, "database_path": db_path},
                    )
                )
            return results
        except Exception as e:
            raise DiscoveryError(f"Failed to discover SQLite objects: {e}") from e

    def infer_schema(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SchemaResult:
        try:
            db_path = self._resolve_db_path(source_config, table_options)
            t_opts = table_options or {}
            table_name = str(t_opts.get("table_name") or t_opts.get("table") or "").strip()
            custom_query = str(t_opts.get("query") or "").strip()

            if not table_name and not custom_query:
                raise ConnectorValidationError(
                    "Either Table Name or Custom Query must be specified for SQLite."
                )

            timeout = int((source_config or {}).get("timeout", 5))
            conn = self._open_connection(db_path, read_only=True, timeout=timeout)
            try:
                cursor = conn.cursor()
                columns_meta: list[ColumnMetadata] = []
                row_count_estimate: int | None = None

                if custom_query:
                    # Query execution for custom query schema
                    cursor.execute(f"SELECT * FROM ({custom_query}) LIMIT 0;")
                    for col_desc in cursor.description:
                        col_name = col_desc[0]
                        columns_meta.append(
                            ColumnMetadata(
                                name=col_name,
                                type="String",
                                nullable=True,
                            )
                        )
                    # Row count estimate
                    try:
                        cursor.execute(f"SELECT count(*) FROM ({custom_query});")
                        row_count_estimate = cursor.fetchone()[0]
                    except Exception:
                        row_count_estimate = None
                else:
                    # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
                    cursor.execute(f'PRAGMA table_info("{table_name}");')
                    pragma_rows = cursor.fetchall()
                    if not pragma_rows:
                        # Could be a view or table not found
                        cursor.execute(f'SELECT * FROM "{table_name}" LIMIT 0;')
                        for col_desc in cursor.description:
                            columns_meta.append(
                                ColumnMetadata(
                                    name=col_desc[0],
                                    type="String",
                                    nullable=True,
                                )
                            )
                    else:
                        for row in pragma_rows:
                            col_name = row[1]
                            raw_type = row[2]
                            not_null = bool(row[3])
                            is_pk = bool(row[5])
                            columns_meta.append(
                                ColumnMetadata(
                                    name=col_name,
                                    type=map_sqlite_type_to_standard(raw_type),
                                    nullable=not not_null and not is_pk,
                                    description="Primary Key" if is_pk else "",
                                )
                            )

                    try:
                        cursor.execute(f'SELECT count(*) FROM "{table_name}";')
                        row_count_estimate = cursor.fetchone()[0]
                    except Exception:
                        row_count_estimate = None
            finally:
                conn.close()

            return SchemaResult(
                columns=columns_meta,
                row_count_estimate=row_count_estimate,
                sample_size=min(row_count_estimate or 0, 50),
            )
        except Exception as e:
            raise SchemaInferenceError(f"Failed to infer SQLite schema: {e}") from e

    def preview(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> PreviewResult:
        try:
            db_path = self._resolve_db_path(source_config, table_options)
            t_opts = table_options or {}
            table_name = str(t_opts.get("table_name") or t_opts.get("table") or "").strip()
            custom_query = str(t_opts.get("query") or "").strip()
            projection = str(t_opts.get("columns") or "").strip()

            if not table_name and not custom_query:
                raise ConnectorValidationError(
                    "Either Table Name or Custom Query must be specified for SQLite."
                )

            timeout = int((source_config or {}).get("timeout", 5))
            conn = self._open_connection(db_path, read_only=True, timeout=timeout)
            try:
                cursor = conn.cursor()
                if custom_query:
                    sql = f"SELECT * FROM ({custom_query}) LIMIT {int(limit)};"
                    count_sql = f"SELECT count(*) FROM ({custom_query});"
                else:
                    proj = projection if projection else "*"
                    sql = f'SELECT {proj} FROM "{table_name}" LIMIT {int(limit)};'
                    count_sql = f'SELECT count(*) FROM "{table_name}";'

                cursor.execute(sql)
                col_names = [d[0] for d in cursor.description]
                raw_rows = cursor.fetchall()

                try:
                    cursor.execute(count_sql)
                    total_rows = cursor.fetchone()[0]
                except Exception:
                    total_rows = len(raw_rows)
            finally:
                conn.close()

            formatted_rows: list[dict[str, Any]] = []
            for row in raw_rows:
                row_dict: dict[str, Any] = {}
                for idx, col in enumerate(col_names):
                    val = row[idx]
                    if isinstance(val, (bytes, bytearray)):
                        row_dict[col] = f"<blob {len(val)} bytes>"
                    elif val is None:
                        row_dict[col] = None
                    else:
                        row_dict[col] = str(val) if not isinstance(val, (int, float, bool)) else val
                formatted_rows.append(row_dict)

            return PreviewResult(
                columns=col_names,
                rows=formatted_rows,
                total_rows=total_rows,
                truncated=len(formatted_rows) < total_rows,
            )
        except Exception as e:
            raise PreviewError(f"Failed to preview SQLite table: {e}") from e

    def read_polars(
        self,
        source_config: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> pl.DataFrame:
        """Scan SQLite table directly into a Polars DataFrame."""
        db_path = self._resolve_db_path(source_config, table_options)
        t_opts = table_options or {}
        table_name = str(t_opts.get("table_name") or t_opts.get("table") or "").strip()
        custom_query = str(t_opts.get("query") or "").strip()
        projection = str(t_opts.get("columns") or "").strip()

        if custom_query:
            query = custom_query
        else:
            proj = projection if projection else "*"
            query = f'SELECT {proj} FROM "{table_name}"'

        if limit is not None:
            query = f"SELECT * FROM ({query}) LIMIT {int(limit)}"

        timeout = int((source_config or {}).get("timeout", 5))
        conn = self._open_connection(db_path, read_only=True, timeout=timeout)
        try:
            return pl.read_database(query=query, connection=conn)
        finally:
            conn.close()
