"""GraphQL API connector supporting custom queries, variables, Relay/cursor & offset pagination, and schema introspection."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx
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

ISO_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$")


def get_nested_value(data: Any, path: str | None) -> Any:
    """Traverse nested dictionary / list using dot-separated notation."""
    if not path or not path.strip() or data is None:
        return None
    cur = data
    parts = [p.strip() for p in path.strip().split(".") if p.strip()]
    for p in parts:
        if isinstance(cur, dict):
            cur = cur.get(p)
        elif isinstance(cur, list) and p.isdigit():
            idx = int(p)
            cur = cur[idx] if idx < len(cur) else None
        else:
            return None
    return cur


def extract_graphql_records(data: Any, path: str | None = None) -> list[dict[str, Any]]:
    """Extract list of records from GraphQL JSON response.
    
    If path is provided, navigates directly to path.
    If path is omitted, auto-detects the first list of dicts in data['data'] (or data).
    Automatically unpacks Relay-style edge connections ([{node: {...}}]).
    """
    if data is None:
        return []

    # If response is wrapped in standard GraphQL {"data": ...}
    root = data.get("data", data) if isinstance(data, dict) else data

    target: Any = None
    if path and path.strip():
        # Clean path: if path starts with "data.", strip it if root is already data
        clean_path = path.strip()
        if clean_path.startswith("data.") and isinstance(data, dict) and "data" in data:
            clean_path = clean_path[5:]
        target = get_nested_value(root, clean_path)
        if target is None and isinstance(data, dict):
            target = get_nested_value(data, path)
    else:
        # Auto-detect: search for the first list of dicts
        def find_first_list(node: Any) -> list[Any] | None:
            if isinstance(node, list) and (not node or any(isinstance(x, dict) for x in node)):
                return node
            if isinstance(node, dict):
                for val in node.values():
                    found = find_first_list(val)
                    if found is not None:
                        return found
            return None

        target = find_first_list(root)
        if target is None and isinstance(root, dict):
            # If root is a single dictionary record (e.g. { "user": { ... } })
            dict_vals = [v for v in root.values() if isinstance(v, dict)]
            if len(dict_vals) == 1:
                return [dict_vals[0]]
            return [root]

    if isinstance(target, list):
        records: list[dict[str, Any]] = []
        for item in target:
            if isinstance(item, dict):
                # Unpack Relay edge pattern: {"cursor": "...", "node": {...}}
                if "node" in item and isinstance(item["node"], dict) and len(item) <= 3:
                    node_copy = dict(item["node"])
                    if "cursor" in item and "_cursor" not in node_copy and "cursor" not in node_copy:
                        node_copy["_cursor"] = item["cursor"]
                    records.append(node_copy)
                else:
                    records.append(item)
        return records

    if isinstance(target, dict):
        return [target]

    return []


def infer_json_type(values: list[Any]) -> str:
    """Infer column type from observed values in GraphQL JSON records."""
    non_nulls = [v for v in values if v is not None]
    if not non_nulls:
        return "String"

    first = non_nulls[0]
    if isinstance(first, bool):
        return "Boolean"
    if isinstance(first, int):
        if all(isinstance(v, int) for v in non_nulls):
            return "Int64"
        if all(isinstance(v, (int, float)) for v in non_nulls):
            return "Float64"
    if isinstance(first, float):
        if all(isinstance(v, (int, float)) for v in non_nulls):
            return "Float64"
    if isinstance(first, (dict, list)):
        return "JSON"
    if isinstance(first, str):
        if all(isinstance(v, str) and ISO_DATE_REGEX.match(v) for v in non_nulls):
            return "DateTime"
        return "String"
    return "String"


class GraphQLConnector(BaseConnector):
    """Connector for GraphQL endpoints supporting queries, variables, and schema introspection."""

    id = "graphql"
    name = "GraphQL"
    group = ConnectorGroup.APIS
    description = "GraphQL endpoint connector (with custom queries, variables, Relay/cursor & offset pagination, and schema introspection)"

    source_fields = [
        ConfigField(
            name="endpoint_url",
            label="Endpoint URL",
            type=FieldType.STRING,
            required=True,
            placeholder="https://api.example.com/graphql",
            description="GraphQL endpoint HTTP/HTTPS URL.",
        ),
        ConfigField(
            name="auth_type",
            label="Authentication Type",
            type=FieldType.SELECT,
            default="none",
            options=[
                {"label": "None (Public API)", "value": "none"},
                {"label": "Bearer Token", "value": "bearer"},
                {"label": "API Key Header", "value": "api_key"},
                {"label": "Basic Auth", "value": "basic"},
            ],
            description="Authentication mechanism required by the GraphQL endpoint.",
        ),
        ConfigField(
            name="auth_token",
            label="Auth Token / API Key",
            type=FieldType.PASSWORD,
            secret=True,
            placeholder="Bearer token or API key...",
            description="Bearer token or API key header value.",
        ),
        ConfigField(
            name="api_key_header",
            label="API Key Header Name",
            type=FieldType.STRING,
            default="Authorization",
            advanced=True,
            placeholder="Authorization or X-API-Key",
            description="HTTP header name when using API Key authentication.",
        ),
        ConfigField(
            name="username",
            label="Username (Basic Auth)",
            type=FieldType.STRING,
            advanced=True,
            placeholder="api_user",
            description="Username for Basic Authentication.",
        ),
        ConfigField(
            name="password",
            label="Password (Basic Auth)",
            type=FieldType.PASSWORD,
            secret=True,
            advanced=True,
            placeholder="••••••••",
            description="Password for Basic Authentication.",
        ),
        ConfigField(
            name="custom_headers",
            label="Custom Headers (JSON)",
            type=FieldType.TEXTAREA,
            advanced=True,
            placeholder='{"X-Custom-Client": "det-core"}',
            description="Optional extra HTTP headers in JSON format.",
        ),
        ConfigField(
            name="timeout",
            label="Request Timeout (seconds)",
            type=FieldType.INTEGER,
            default=20,
            advanced=True,
            description="HTTP request timeout in seconds.",
        ),
    ]

    table_fields = [
        ConfigField(
            name="query",
            label="GraphQL Query",
            type=FieldType.TEXTAREA,
            required=True,
            placeholder="query GetItems($limit: Int) {\n  items(limit: $limit) {\n    id\n    name\n  }\n}",
            description="GraphQL query document string.",
        ),
        ConfigField(
            name="variables",
            label="Query Variables (JSON, optional)",
            type=FieldType.TEXTAREA,
            advanced=True,
            placeholder='{"limit": 50}',
            description="GraphQL query variables as a JSON object.",
        ),
        ConfigField(
            name="operation_name",
            label="Operation Name (optional)",
            type=FieldType.STRING,
            advanced=True,
            placeholder="GetItems",
            description="Operation name if the GraphQL document defines multiple operations.",
        ),
        ConfigField(
            name="data_path",
            label="Data Path (optional)",
            type=FieldType.STRING,
            placeholder="data.items or repository.issues.nodes",
            description="Dot-separated path to target records. Auto-detected if omitted.",
        ),
        ConfigField(
            name="pagination_type",
            label="Pagination Type",
            type=FieldType.SELECT,
            default="none",
            options=[
                {"label": "None (Single Query)", "value": "none"},
                {"label": "Relay / Cursor (pageInfo.endCursor)", "value": "cursor"},
                {"label": "Offset / Page ($offset or $page)", "value": "offset"},
            ],
            advanced=True,
            description="Pagination protocol supported by the GraphQL query.",
        ),
        ConfigField(
            name="cursor_variable",
            label="Cursor Variable Name",
            type=FieldType.STRING,
            default="after",
            advanced=True,
            placeholder="after",
            description="GraphQL variable name for cursor (e.g. after).",
        ),
        ConfigField(
            name="cursor_path",
            label="Cursor Path in Response",
            type=FieldType.STRING,
            default="pageInfo.endCursor",
            advanced=True,
            placeholder="pageInfo.endCursor",
            description="Dot-separated path to the next page cursor in response JSON.",
        ),
        ConfigField(
            name="has_next_page_path",
            label="Has Next Page Path",
            type=FieldType.STRING,
            default="pageInfo.hasNextPage",
            advanced=True,
            placeholder="pageInfo.hasNextPage",
            description="Dot-separated path to hasNextPage boolean in response JSON.",
        ),
        ConfigField(
            name="limit_variable",
            label="Page Size / Limit Variable Name",
            type=FieldType.STRING,
            default="first",
            advanced=True,
            placeholder="first or limit",
            description="GraphQL variable name for page size (e.g. first or limit).",
        ),
        ConfigField(
            name="page_size",
            label="Page Size",
            type=FieldType.INTEGER,
            default=50,
            advanced=True,
            description="Number of records requested per page.",
        ),
    ]

    def _build_request_config(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        s_cfg = dict(source_config or {})
        creds = dict(credentials or {})
        t_opts = dict(table_options or {})

        endpoint_url = str(s_cfg.get("endpoint_url") or t_opts.get("endpoint_url") or "").strip()
        if not endpoint_url:
            raise ConnectorValidationError("GraphQL Endpoint URL is required.")

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "det-core/1.0 (GraphQL Connector)",
        }

        # Custom headers
        cust_headers = s_cfg.get("custom_headers")
        if isinstance(cust_headers, str) and cust_headers.strip():
            try:
                parsed = json.loads(cust_headers)
                if isinstance(parsed, dict):
                    headers.update({str(k): str(v) for k, v in parsed.items()})
            except Exception:
                pass
        elif isinstance(cust_headers, dict):
            headers.update({str(k): str(v) for k, v in cust_headers.items()})

        # Authentication
        auth_type = s_cfg.get("auth_type", "none").lower()
        token = creds.get("auth_token") or s_cfg.get("auth_token") or ""
        username = s_cfg.get("username") or creds.get("username") or ""
        password = creds.get("password") or s_cfg.get("password") or ""
        basic_auth = None

        if auth_type == "bearer" and token:
            headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key" and token:
            header_name = s_cfg.get("api_key_header") or "Authorization"
            headers[header_name] = token
        elif auth_type == "basic" and (username or password):
            basic_auth = (username, password)

        # Variables
        variables: dict[str, Any] = {}
        vars_raw = t_opts.get("variables")
        if isinstance(vars_raw, str) and vars_raw.strip():
            try:
                parsed_vars = json.loads(vars_raw)
                if isinstance(parsed_vars, dict):
                    variables = parsed_vars
            except Exception:
                pass
        elif isinstance(vars_raw, dict):
            variables = dict(vars_raw)

        timeout = int(s_cfg.get("timeout") or 20)

        query = t_opts.get("query")
        if query:
            query = str(query).strip()

        return {
            "endpoint_url": endpoint_url,
            "headers": headers,
            "basic_auth": basic_auth,
            "timeout": timeout,
            "query": query,
            "variables": variables,
            "operation_name": t_opts.get("operation_name"),
            "data_path": t_opts.get("data_path"),
            "pagination_type": t_opts.get("pagination_type", "none"),
            "cursor_variable": t_opts.get("cursor_variable", "after"),
            "cursor_path": t_opts.get("cursor_path", "pageInfo.endCursor"),
            "has_next_page_path": t_opts.get("has_next_page_path", "pageInfo.hasNextPage"),
            "limit_variable": t_opts.get("limit_variable", "first"),
            "page_size": int(t_opts.get("page_size", 50)),
        }

    def _execute_query(
        self,
        client: httpx.Client,
        endpoint_url: str,
        query: str,
        variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
    ) -> dict[str, Any]:
        """Execute a single GraphQL query and return parsed JSON payload."""
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        if operation_name:
            payload["operationName"] = operation_name

        resp = client.post(endpoint_url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict):
            errors = data.get("errors")
            if errors and not data.get("data"):
                first_msg = errors[0].get("message") if isinstance(errors, list) and errors else str(errors)
                raise ValueError(f"GraphQL server error: {first_msg}")

        return data

    def _fetch_records(
        self,
        req_cfg: dict[str, Any],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        query = req_cfg.get("query")
        if not query:
            raise ConnectorValidationError("GraphQL query document is required.")

        endpoint_url = req_cfg["endpoint_url"]
        headers = req_cfg["headers"]
        timeout = req_cfg["timeout"]
        auth = req_cfg["basic_auth"]
        base_variables = dict(req_cfg["variables"])
        operation_name = req_cfg.get("operation_name")
        data_path = req_cfg.get("data_path")
        pagination_type = req_cfg.get("pagination_type", "none")
        cursor_var = req_cfg.get("cursor_variable", "after")
        cursor_path = req_cfg.get("cursor_path", "pageInfo.endCursor")
        has_next_page_path = req_cfg.get("has_next_page_path", "pageInfo.hasNextPage")
        limit_var = req_cfg.get("limit_variable", "first")
        page_size = req_cfg.get("page_size", 50)

        all_records: list[dict[str, Any]] = []

        with httpx.Client(timeout=timeout, auth=auth, headers=headers) as client:
            if pagination_type == "cursor":
                cur_cursor: str | None = None
                while True:
                    cur_vars = dict(base_variables)
                    if limit_var:
                        cur_vars[limit_var] = page_size
                    if cur_cursor:
                        cur_vars[cursor_var] = cur_cursor

                    data = self._execute_query(client, endpoint_url, query, cur_vars, operation_name)
                    records = extract_graphql_records(data, data_path)
                    if not records:
                        break
                    all_records.extend(records)
                    if limit and len(all_records) >= limit:
                        all_records = all_records[:limit]
                        break

                    # Check next page cursor
                    has_next = get_nested_value(data, has_next_page_path)
                    if has_next is None and data_path:
                        # Try relative to parent container
                        parent_path = ".".join(data_path.split(".")[:-1])
                        has_next = get_nested_value(data, f"{parent_path}.{has_next_page_path}".strip("."))

                    next_cursor = get_nested_value(data, cursor_path)
                    if next_cursor is None and data_path:
                        parent_path = ".".join(data_path.split(".")[:-1])
                        next_cursor = get_nested_value(data, f"{parent_path}.{cursor_path}".strip("."))

                    if has_next is False or not next_cursor or next_cursor == cur_cursor:
                        break
                    cur_cursor = str(next_cursor)
            elif pagination_type == "offset":
                offset = 0
                while True:
                    cur_vars = dict(base_variables)
                    cur_vars["offset"] = offset
                    if limit_var:
                        cur_vars[limit_var] = page_size
                    data = self._execute_query(client, endpoint_url, query, cur_vars, operation_name)
                    records = extract_graphql_records(data, data_path)
                    if not records:
                        break
                    all_records.extend(records)
                    if limit and len(all_records) >= limit:
                        all_records = all_records[:limit]
                        break
                    if len(records) < page_size:
                        break
                    offset += page_size
            else:
                cur_vars = dict(base_variables)
                if limit and limit_var and limit_var not in cur_vars:
                    cur_vars[limit_var] = limit
                data = self._execute_query(client, endpoint_url, query, cur_vars, operation_name)
                all_records = extract_graphql_records(data, data_path)
                if limit and len(all_records) > limit:
                    all_records = all_records[:limit]

        return all_records

    def test_connection(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> ConnectionTestResult:
        try:
            req_cfg = self._build_request_config(source_config, credentials, table_options)
            url = req_cfg["endpoint_url"]
            timeout = req_cfg["timeout"]
            headers = req_cfg["headers"]
            auth = req_cfg["basic_auth"]

            start_t = time.perf_counter()
            with httpx.Client(timeout=timeout, auth=auth, headers=headers) as client:
                # Test query using typename or schema query type
                test_payload = {"query": "{ __typename }"}
                resp = client.post(url, json=test_payload)
            elapsed_ms = (time.perf_counter() - start_t) * 1000

            if resp.status_code == 200:
                body = resp.json()
                if isinstance(body, dict) and body.get("errors") and not body.get("data"):
                    err_msg = body["errors"][0].get("message", "Unknown GraphQL error")
                    return ConnectionTestResult(
                        success=False,
                        message=f"GraphQL endpoint responded with error: {err_msg}",
                        details={"status_code": resp.status_code, "latency_ms": elapsed_ms, "url": url},
                    )
                return ConnectionTestResult(
                    success=True,
                    message=f"Connected successfully to GraphQL endpoint (200 OK in {elapsed_ms:.1f}ms).",
                    details={"status_code": resp.status_code, "latency_ms": elapsed_ms, "url": url},
                )
            elif resp.status_code in (401, 403):
                return ConnectionTestResult(
                    success=False,
                    message=f"Authentication failed ({resp.status_code} Unauthorized / Forbidden). Check API token or credentials.",
                    details={"status_code": resp.status_code, "url": url},
                )
            else:
                return ConnectionTestResult(
                    success=False,
                    message=f"GraphQL server returned HTTP {resp.status_code}.",
                    details={"status_code": resp.status_code, "url": url},
                )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"GraphQL connection failed: {e}",
            )

    def discover_objects(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[DiscoveredObject]:
        """Discover queryable root fields using GraphQL introspection query."""
        try:
            req_cfg = self._build_request_config(source_config, credentials, options)
            url = req_cfg["endpoint_url"]
            headers = req_cfg["headers"]
            auth = req_cfg["basic_auth"]
            timeout = req_cfg["timeout"]

            introspection_query = """
            query DetIntrospectSchema {
              __schema {
                queryType {
                  name
                  fields {
                    name
                    description
                    args {
                      name
                      type {
                        name
                        kind
                      }
                    }
                  }
                }
              }
            }
            """
            discovered: list[DiscoveredObject] = []
            with httpx.Client(timeout=timeout, auth=auth, headers=headers) as client:
                resp = client.post(url, json={"query": introspection_query})
                if resp.status_code == 200:
                    payload = resp.json()
                    fields = (
                        payload.get("data", {})
                        .get("__schema", {})
                        .get("queryType", {})
                        .get("fields", [])
                    )
                    for f in fields:
                        field_name = f.get("name")
                        if not field_name:
                            continue
                        arg_names = [a.get("name") for a in f.get("args", []) if a.get("name")]
                        discovered.append(
                            DiscoveredObject(
                                id=field_name,
                                name=field_name,
                                type="query_field",
                                path=field_name,
                                metadata={
                                    "description": f.get("description") or "",
                                    "arguments": arg_names,
                                },
                            )
                        )
            return discovered
        except Exception as e:
            raise DiscoveryError(f"Failed to discover GraphQL schema fields: {e}") from e

    def infer_schema(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SchemaResult:
        try:
            req_cfg = self._build_request_config(source_config, credentials, table_options)
            records = self._fetch_records(req_cfg, limit=50)

            if not records:
                return SchemaResult(columns=[], row_count_estimate=0, sample_size=0)

            all_keys: list[str] = []
            for r in records:
                for k in r.keys():
                    if k not in all_keys:
                        all_keys.append(k)

            columns_meta: list[ColumnMetadata] = []
            for k in all_keys:
                vals = [r.get(k) for r in records]
                col_type = infer_json_type(vals)
                nullable = any(v is None for v in vals) or len(vals) < len(records)
                columns_meta.append(
                    ColumnMetadata(
                        name=k,
                        type=col_type,
                        nullable=nullable,
                    )
                )

            return SchemaResult(
                columns=columns_meta,
                row_count_estimate=len(records),
                sample_size=len(records),
            )
        except Exception as e:
            raise SchemaInferenceError(f"Failed to infer GraphQL query schema: {e}") from e

    def preview(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> PreviewResult:
        try:
            req_cfg = self._build_request_config(source_config, credentials, table_options)
            records = self._fetch_records(req_cfg, limit=limit)

            if not records:
                return PreviewResult(columns=[], rows=[], total_rows=0, truncated=False)

            all_keys: list[str] = []
            for r in records:
                for k in r.keys():
                    if k not in all_keys:
                        all_keys.append(k)

            formatted_rows: list[dict[str, Any]] = []
            for r in records:
                row_dict: dict[str, Any] = {}
                for k in all_keys:
                    v = r.get(k)
                    if isinstance(v, (dict, list)):
                        row_dict[k] = json.dumps(v, ensure_ascii=False)
                    else:
                        row_dict[k] = v
                formatted_rows.append(row_dict)

            return PreviewResult(
                columns=all_keys,
                rows=formatted_rows,
                total_rows=len(formatted_rows),
                truncated=False,
            )
        except Exception as e:
            raise PreviewError(f"Failed to preview GraphQL query: {e}") from e

    def read_polars(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> pl.DataFrame:
        """Execute GraphQL query and return records as a Polars DataFrame."""
        req_cfg = self._build_request_config(source_config, credentials, table_options)
        records = self._fetch_records(req_cfg, limit=limit)
        if not records:
            return pl.DataFrame()
        return pl.DataFrame(records)

