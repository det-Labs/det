"""Microsoft SQL Server database connector supporting connection management, schema/table discovery, schema inference, and Polars preview."""

from __future__ import annotations

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


def map_sqlserver_type_to_standard(sql_type: str | None) -> str:
    """Map SQL Server INFORMATION_SCHEMA data_type to standard catalog data type."""
    if not sql_type:
        return "String"
    t = sql_type.strip().lower()
    if any(k in t for k in ("int", "bigint", "smallint", "tinyint")):
        return "Int64"
    if any(k in t for k in ("decimal", "numeric", "float", "real", "money")):
        return "Float64"
    if "bit" in t:
        return "Boolean"
    if any(k in t for k in ("datetime", "date", "time")):
        return "DateTime"
    if any(k in t for k in ("binary", "varbinary", "image")):
        return "Binary"
    if "json" in t:
        return "JSON"
    if "uniqueidentifier" in t:
        return "String"
    if any(k in t for k in ("char", "varchar", "nchar", "nvarchar", "text", "ntext", "xml")):
        return "String"
    return "String"


class SQLServerConnector(BaseConnector):
    """High-performance Microsoft SQL Server database connector."""

    id = "sqlserver"
    name = "SQL Server"
    group = ConnectorGroup.DATABASES
    description = "Microsoft SQL Server database (high-performance pymssql driver)"

    source_fields = [
        ConfigField(
            name="host",
            label="Host",
            type=FieldType.STRING,
            required=True,
            default="localhost",
            placeholder="localhost or mssql.example.com",
            description="SQL Server hostname or IP address.",
        ),
        ConfigField(
            name="port",
            label="Port",
            type=FieldType.INTEGER,
            required=True,
            default=1433,
            placeholder="1433",
            description="SQL Server port (default: 1433).",
        ),
        ConfigField(
            name="database",
            label="Database Name",
            type=FieldType.STRING,
            required=True,
            placeholder="e.g. SalesDB, master",
            description="Target database name on the SQL Server instance.",
        ),
        ConfigField(
            name="username",
            label="Username",
            type=FieldType.STRING,
            required=True,
            placeholder="sa",
            description="Database login user.",
        ),
        ConfigField(
            name="password",
            label="Password",
            type=FieldType.PASSWORD,
            secret=True,
            placeholder="••••••••",
            description="Database login password (stored in .det/connections.yaml).",
        ),
        ConfigField(
            name="connect_timeout",
            label="Connect Timeout (seconds)",
            type=FieldType.INTEGER,
            default=10,
            advanced=True,
            description="Timeout in seconds for connection attempt.",
        ),
    ]

    table_fields = [
        ConfigField(
            name="schema",
            label="Schema Name",
            type=FieldType.STRING,
            default="dbo",
            placeholder="dbo",
            description="SQL Server schema name (default: dbo).",
        ),
        ConfigField(
            name="table_name",
            label="Table or View Name",
            type=FieldType.STRING,
            required=True,
            placeholder="e.g. Orders, Customers",
            description="Name of the table or view in the specified schema.",
        ),
        ConfigField(
            name="query",
            label="Custom SQL Query (optional)",
            type=FieldType.TEXTAREA,
            advanced=True,
            placeholder="SELECT OrderID, Total FROM Orders WHERE Status = 'Active'",
            description="Optional custom SELECT query. If specified, overrides Table Name.",
        ),
        ConfigField(
            name="columns",
            label="Column Projection (optional)",
            type=FieldType.STRING,
            advanced=True,
            placeholder="OrderID, CustomerName, Amount",
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
        port = int(s_cfg.get("port") or t_opts.get("port") or 1433)
        database = s_cfg.get("database") or t_opts.get("database") or ""
        username = s_cfg.get("username") or creds.get("username") or t_opts.get("username") or "sa"
        password = creds.get("password") or s_cfg.get("password") or t_opts.get("password") or ""
        connect_timeout = int(s_cfg.get("connect_timeout") or t_opts.get("connect_timeout") or 10)

        if not database:
            raise ConnectorValidationError("SQL Server database name is required.")

        return {
            "server": str(host).strip(),
            "port": str(port),
            "database": str(database).strip(),
            "user": str(username).strip(),
            "password": str(password),
            "login_timeout": connect_timeout,
            "timeout": connect_timeout,
        }

    def _connect(self, params: dict[str, Any]) -> Any:
        try:
            import pymssql
            return pymssql.connect(**params)
        except ImportError as e:
            raise ConnectorValidationError(
                "pymssql library is required to connect to SQL Server."
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
                cur = conn.cursor()
                cur.execute("SELECT 1;")
                cur.execute("""
                    SELECT count(*)
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW');
                """)
                row = cur.fetchone()
                table_count = row[0] if row else 0
            finally:
                conn.close()

            return ConnectionTestResult(
                success=True,
                message=f"Connected successfully to SQL Server database '{params['database']}' ({table_count} tables/views found).",
                details={
                    "database": params["database"],
                    "server": params["server"],
                    "port": params["port"],
                    "table_count": table_count,
                },
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"SQL Server connection failed: {e}",
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
                cur = conn.cursor()
                cur.execute("""
                    SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
                    FROM INFORMATION_SCHEMA.TABLES
                    ORDER BY TABLE_SCHEMA, TABLE_NAME;
                """)
                rows = cur.fetchall()
            finally:
                conn.close()

            discovered: list[DiscoveredObject] = []
            for schema, tbl_name, tbl_type in rows:
                full_id = f"{schema}.{tbl_name}"
                display_name = tbl_name if schema.lower() == "dbo" else full_id
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
            raise DiscoveryError(f"Failed to discover SQL Server objects: {e}") from e

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
            schema_name = str(t_opts.get("schema") or "dbo").strip()
            table_name = str(t_opts.get("table_name") or t_opts.get("table") or "").strip()
            custom_query = str(t_opts.get("query") or "").strip()

            if not table_name and not custom_query:
                raise ConnectorValidationError(
                    "Either Table Name or Custom Query must be specified for SQL Server."
                )

            conn = self._connect(params)
            try:
                cur = conn.cursor()
                columns_meta: list[ColumnMetadata] = []
                row_count_estimate: int | None = None

                if custom_query:
                    # Introspect custom query
                    cur.execute(f"SELECT TOP 0 * FROM ({custom_query}) AS _det_subquery;")
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
                    # Introspect table from INFORMATION_SCHEMA.COLUMNS
                    cur.execute("""
                        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                        ORDER BY ORDINAL_POSITION;
                    """, (schema_name, table_name))
                    rows = cur.fetchall()

                    if not rows:
                        cur.execute(f"SELECT TOP 0 * FROM [{schema_name}].[{table_name}];")
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
                                    type=map_sqlserver_type_to_standard(raw_type),
                                    nullable=(is_null.upper() == "YES"),
                                )
                            )

                    try:
                        cur.execute(f"SELECT count_big(*) FROM [{schema_name}].[{table_name}];")
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
            raise SchemaInferenceError(f"Failed to infer SQL Server schema: {e}") from e

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
            schema_name = str(t_opts.get("schema") or "dbo").strip()
            table_name = str(t_opts.get("table_name") or t_opts.get("table") or "").strip()
            custom_query = str(t_opts.get("query") or "").strip()
            projection = str(t_opts.get("columns") or "").strip()

            if not table_name and not custom_query:
                raise ConnectorValidationError(
                    "Either Table Name or Custom Query must be specified for SQL Server."
                )

            conn = self._connect(params)
            try:
                cur = conn.cursor()
                if custom_query:
                    sql = f"SELECT TOP {int(limit)} * FROM ({custom_query}) AS _det_prev;"
                    count_sql = f"SELECT count(*) FROM ({custom_query}) AS _det_cnt;"
                else:
                    proj = projection if projection else "*"
                    sql = f"SELECT TOP {int(limit)} {proj} FROM [{schema_name}].[{table_name}];"
                    count_sql = f"SELECT count_big(*) FROM [{schema_name}].[{table_name}];"

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
            raise PreviewError(f"Failed to preview SQL Server table: {e}") from e

    def read_polars(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> pl.DataFrame:
        """Scan SQL Server table directly into a Polars DataFrame."""
        params = self._build_connection_params(source_config, credentials, table_options)
        t_opts = table_options or {}
        schema_name = str(t_opts.get("schema") or "dbo").strip()
        table_name = str(t_opts.get("table_name") or t_opts.get("table") or "").strip()
        custom_query = str(t_opts.get("query") or "").strip()
        projection = str(t_opts.get("columns") or "").strip()

        if custom_query:
            query = custom_query
        else:
            proj = projection if projection else "*"
            query = f"SELECT {proj} FROM [{schema_name}].[{table_name}]"

        if limit is not None:
            query = f"SELECT TOP {int(limit)} * FROM ({query}) AS _det_polars"

        conn = self._connect(params)
        try:
            return pl.read_database(query=query, connection=conn)
        finally:
            conn.close()

