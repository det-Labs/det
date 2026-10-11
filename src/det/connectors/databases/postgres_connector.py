"""PostgreSQL database connector supporting connection management, schema/table discovery, schema inference, and Polars preview."""

from __future__ import annotations

import urllib.parse
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


def map_postgres_type_to_standard(pg_type: str | None) -> str:
    """Map PostgreSQL information_schema data_type to standard catalog data type."""
    if not pg_type:
        return "String"
    t = pg_type.strip().lower()
    if any(k in t for k in ("int", "serial")):
        return "Int64"
    if any(k in t for k in ("numeric", "decimal", "real", "double", "float")):
        return "Float64"
    if "bool" in t:
        return "Boolean"
    if any(k in t for k in ("timestamp", "date", "time")):
        return "DateTime"
    if any(k in t for k in ("bytea", "blob", "binary")):
        return "Binary"
    if "json" in t:
        return "JSON"
    if "uuid" in t:
        return "String"
    return "String"


class PostgresConnector(BaseConnector):
    """High-performance PostgreSQL relational database connector."""

    id = "postgres"
    name = "PostgreSQL"
    group = ConnectorGroup.DATABASES
    description = "PostgreSQL relational database (high-performance Arrow/Polars driver)"

    source_fields = [
        ConfigField(
            name="host",
            label="Host",
            type=FieldType.STRING,
            required=True,
            default="localhost",
            placeholder="localhost or db.example.com",
            description="PostgreSQL server hostname or IP address.",
        ),
        ConfigField(
            name="port",
            label="Port",
            type=FieldType.INTEGER,
            required=True,
            default=5432,
            placeholder="5432",
            description="Database port (default: 5432).",
        ),
        ConfigField(
            name="database",
            label="Database Name",
            type=FieldType.STRING,
            required=True,
            placeholder="e.g. analytics_db, production",
            description="Name of the target database.",
        ),
        ConfigField(
            name="username",
            label="Username",
            type=FieldType.STRING,
            required=True,
            placeholder="postgres",
            description="Database user login.",
        ),
        ConfigField(
            name="password",
            label="Password",
            type=FieldType.PASSWORD,
            secret=True,
            placeholder="••••••••",
            description="Database user password (securely stored in .det/connections.yaml).",
        ),
        ConfigField(
            name="sslmode",
            label="SSL Mode",
            type=FieldType.SELECT,
            default="prefer",
            options=[
                {"label": "Disable (No SSL)", "value": "disable"},
                {"label": "Allow (Try non-SSL then SSL)", "value": "allow"},
                {"label": "Prefer (Try SSL then non-SSL)", "value": "prefer"},
                {"label": "Require (SSL required)", "value": "require"},
                {"label": "Verify CA", "value": "verify-ca"},
                {"label": "Verify Full", "value": "verify-full"},
            ],
            advanced=True,
            description="Security and SSL encryption mode.",
        ),
        ConfigField(
            name="connect_timeout",
            label="Connect Timeout (seconds)",
            type=FieldType.INTEGER,
            default=10,
            advanced=True,
            description="Maximum seconds to wait for connection response.",
        ),
    ]

    table_fields = [
        ConfigField(
            name="schema",
            label="Schema Name",
            type=FieldType.STRING,
            default="public",
            placeholder="public",
            description="PostgreSQL schema name (default: public).",
        ),
        ConfigField(
            name="table_name",
            label="Table or View Name",
            type=FieldType.STRING,
            required=True,
            placeholder="e.g. orders, users, active_subscriptions_view",
            description="Name of the table or view in the specified schema.",
        ),
        ConfigField(
            name="query",
            label="Custom SQL Query (optional)",
            type=FieldType.TEXTAREA,
            advanced=True,
            placeholder="SELECT id, name, total FROM orders WHERE status = 'COMPLETED'",
            description="Optional custom SELECT statement. If specified, overrides Table Name.",
        ),
        ConfigField(
            name="columns",
            label="Column Projection (optional)",
            type=FieldType.STRING,
            advanced=True,
            placeholder="id, customer_name, amount",
            description="Comma-separated column names to include in preview and scans.",
        ),
    ]

    def _build_connection_params(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        s_cfg = dict(source_config or {})
        creds = dict(credentials or {})
        t_opts = dict(table_options or {})

        host = s_cfg.get("host") or t_opts.get("host") or "localhost"
        port = int(s_cfg.get("port") or t_opts.get("port") or 5432)
        database = s_cfg.get("database") or t_opts.get("database") or ""
        username = s_cfg.get("username") or creds.get("username") or t_opts.get("username") or "postgres"
        password = creds.get("password") or s_cfg.get("password") or t_opts.get("password") or ""
        sslmode = s_cfg.get("sslmode") or t_opts.get("sslmode") or "prefer"
        connect_timeout = int(s_cfg.get("connect_timeout") or t_opts.get("connect_timeout") or 10)

        if not database:
            raise ConnectorValidationError("PostgreSQL database name is required.")

        return {
            "host": str(host).strip(),
            "port": port,
            "database": str(database).strip(),
            "user": str(username).strip(),
            "password": str(password),
            "sslmode": str(sslmode).strip(),
            "connect_timeout": connect_timeout,
        }

    def _get_connection_uri(self, params: dict[str, Any]) -> str:
        """Construct PostgreSQL connection URI."""
        user = urllib.parse.quote_plus(params["user"])
        pwd = urllib.parse.quote_plus(params["password"])
        host = params["host"]
        port = params["port"]
        db = urllib.parse.quote_plus(params["database"])
        ssl = params["sslmode"]
        timeout = params["connect_timeout"]
        return f"postgresql://{user}:{pwd}@{host}:{port}/{db}?sslmode={ssl}&connect_timeout={timeout}"

    def _connect(self, params: dict[str, Any]) -> Any:
        try:
            import psycopg2
            return psycopg2.connect(**params)
        except ImportError as e:
            raise ConnectorValidationError(
                "psycopg2 library is required to connect to PostgreSQL."
            ) from e

    def test_connection(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ConnectionTestResult:
        try:
            params = self._build_connection_params(source_config, credentials, table_options)
            conn = self._connect(params)
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    cur.execute("""
                        SELECT count(*)
                        FROM information_schema.tables
                        WHERE table_schema NOT IN ('pg_catalog', 'information_schema');
                    """)
                    row = cur.fetchone()
                    table_count = row[0] if row else 0
            finally:
                conn.close()

            return ConnectionTestResult(
                success=True,
                message=f"Connected successfully to PostgreSQL database '{params['database']}' ({table_count} tables/views found).",
                details={
                    "database": params["database"],
                    "host": params["host"],
                    "port": params["port"],
                    "table_count": table_count,
                },
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"PostgreSQL connection failed: {e}",
            )

    def discover_objects(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[DiscoveredObject]:
        try:
            params = self._build_connection_params(source_config, credentials, options)
            conn = self._connect(params)
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT table_schema, table_name, table_type
                        FROM information_schema.tables
                        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                        ORDER BY table_schema, table_name;
                    """)
                    rows = cur.fetchall()
            finally:
                conn.close()

            discovered: list[DiscoveredObject] = []
            for schema, tbl_name, tbl_type in rows:
                full_id = f"{schema}.{tbl_name}"
                display_name = tbl_name if schema == "public" else full_id
                obj_type = "view" if "view" in tbl_type.lower() else "table"
                discovered.append(
                    DiscoveredObject(
                        id=full_id,
                        name=display_name,
                        type=obj_type,
                        path=full_id,
                        metadata={"schema": schema, "table": tbl_name, "type": tbl_type},
                    )
                )
            return discovered
        except Exception as e:
            raise DiscoveryError(f"Failed to discover PostgreSQL objects: {e}") from e

    def infer_schema(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SchemaResult:
        try:
            params = self._build_connection_params(source_config, credentials, table_options)
            t_opts = table_options or {}
            schema_name = str(t_opts.get("schema") or "public").strip()
            table_name = str(t_opts.get("table_name") or t_opts.get("table") or "").strip()
            custom_query = str(t_opts.get("query") or "").strip()

            if not table_name and not custom_query:
                raise ConnectorValidationError(
                    "Either Table Name or Custom Query must be specified for PostgreSQL."
                )

            conn = self._connect(params)
            try:
                with conn.cursor() as cur:
                    columns_meta: list[ColumnMetadata] = []
                    row_count_estimate: int | None = None

                    if custom_query:
                        # Introspect custom query
                        cur.execute(f"SELECT * FROM ({custom_query}) AS _det_subquery LIMIT 0;")
                        for desc in cur.description:
                            columns_meta.append(
                                ColumnMetadata(
                                    name=desc[0],
                                    type="String",
                                    nullable=True,
                                )
                            )
                        try:
                            cur.execute(f"SELECT count(*) FROM ({custom_query}) AS _det_cnt;")
                            cnt_row = cur.fetchone()
                            row_count_estimate = cnt_row[0] if cnt_row else None
                        except Exception:
                            row_count_estimate = None
                    else:
                        # Introspect table from information_schema.columns
                        cur.execute("""
                            SELECT column_name, data_type, is_nullable
                            FROM information_schema.columns
                            WHERE table_schema = %s AND table_name = %s
                            ORDER BY ordinal_position;
                        """, (schema_name, table_name))
                        rows = cur.fetchall()

                        if not rows:
                            # Attempt direct query fallback
                            cur.execute(f'SELECT * FROM "{schema_name}"."{table_name}" LIMIT 0;')
                            for desc in cur.description:
                                columns_meta.append(
                                    ColumnMetadata(
                                        name=desc[0],
                                        type="String",
                                        nullable=True,
                                    )
                                )
                        else:
                            for col_name, raw_type, is_null in rows:
                                columns_meta.append(
                                    ColumnMetadata(
                                        name=col_name,
                                        type=map_postgres_type_to_standard(raw_type),
                                        nullable=(is_null.upper() == "YES"),
                                    )
                                )

                        try:
                            cur.execute(f'SELECT count(*) FROM "{schema_name}"."{table_name}";')
                            cnt_row = cur.fetchone()
                            row_count_estimate = cnt_row[0] if cnt_row else None
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
            raise SchemaInferenceError(f"Failed to infer PostgreSQL schema: {e}") from e

    def preview(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> PreviewResult:
        try:
            params = self._build_connection_params(source_config, credentials, table_options)
            t_opts = table_options or {}
            schema_name = str(t_opts.get("schema") or "public").strip()
            table_name = str(t_opts.get("table_name") or t_opts.get("table") or "").strip()
            custom_query = str(t_opts.get("query") or "").strip()
            projection = str(t_opts.get("columns") or "").strip()

            if not table_name and not custom_query:
                raise ConnectorValidationError(
                    "Either Table Name or Custom Query must be specified for PostgreSQL."
                )

            conn = self._connect(params)
            try:
                with conn.cursor() as cur:
                    if custom_query:
                        sql = f"SELECT * FROM ({custom_query}) AS _det_preview LIMIT {int(limit)};"
                        count_sql = f"SELECT count(*) FROM ({custom_query}) AS _det_cnt;"
                    else:
                        proj = projection if projection else "*"
                        sql = f'SELECT {proj} FROM "{schema_name}"."{table_name}" LIMIT {int(limit)};'
                        count_sql = f'SELECT count(*) FROM "{schema_name}"."{table_name}";'

                    cur.execute(sql)
                    col_names = [d[0] for d in cur.description]
                    raw_rows = cur.fetchall()

                    try:
                        cur.execute(count_sql)
                        row = cur.fetchone()
                        total_rows = row[0] if row else len(raw_rows)
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
                        row_dict[col] = f"<binary {len(val)} bytes>"
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
            raise PreviewError(f"Failed to preview PostgreSQL table: {e}") from e

    def read_polars(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> pl.DataFrame:
        """Scan PostgreSQL table or query directly into a Polars DataFrame."""
        params = self._build_connection_params(source_config, credentials, table_options)
        t_opts = table_options or {}
        schema_name = str(t_opts.get("schema") or "public").strip()
        table_name = str(t_opts.get("table_name") or t_opts.get("table") or "").strip()
        custom_query = str(t_opts.get("query") or "").strip()
        projection = str(t_opts.get("columns") or "").strip()

        if custom_query:
            query = custom_query
        else:
            proj = projection if projection else "*"
            query = f'SELECT {proj} FROM "{schema_name}"."{table_name}"'

        if limit is not None:
            query = f"SELECT * FROM ({query}) AS _det_polars LIMIT {int(limit)}"

        conn = self._connect(params)
        try:
            return pl.read_database(query=query, connection=conn)
        finally:
            conn.close()
