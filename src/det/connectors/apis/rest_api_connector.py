"""HTTP REST API JSON connector supporting authentication, pagination, dynamic JSON path extraction, and schema inference."""

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


def extract_json_path(data: Any, path: str | None) -> list[dict[str, Any]]:
    """Extract array of records from nested JSON data using a dot-separated path."""
    if not path or not path.strip():
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            # If dict has a single list value, extract it
            list_vals = [v for v in data.values() if isinstance(v, list)]
            if len(list_vals) == 1:
                return [x for x in list_vals[0] if isinstance(x, dict)]
            return [data]
        return []

    cur = data
    parts = [p.strip() for p in path.strip().split(".") if p.strip()]
    for p in parts:
        if isinstance(cur, dict):
            cur = cur.get(p)
        elif isinstance(cur, list) and p.isdigit():
            idx = int(p)
            cur = cur[idx] if idx < len(cur) else None
        else:
            return []

    if isinstance(cur, list):
        return [x for x in cur if isinstance(x, dict)]
    if isinstance(cur, dict):
        return [cur]
    return []


def infer_json_type(values: list[Any]) -> str:
    """Infer column type from observed values in JSON records."""
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


class RestApiConnector(BaseConnector):
    """Connector for HTTP/HTTPS REST APIs returning JSON payloads."""

    id = "rest_api"
    name = "REST API"
    group = ConnectorGroup.APIS
    description = "HTTP REST API JSON endpoint connector (with authentication, pagination, and JSON path extraction)"

    source_fields = [
        ConfigField(
            name="base_url",
            label="Base URL",
            type=FieldType.STRING,
            required=True,
            placeholder="https://api.example.com/v1",
            description="Root API endpoint URL.",
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
            description="Authentication mechanism required by the API.",
        ),
        ConfigField(
            name="auth_token",
            label="Auth Token / API Key",
            type=FieldType.PASSWORD,
            secret=True,
            placeholder="eyJhbGciOiJIUzI1NiIs...",
            description="Bearer token or API key header value.",
        ),
        ConfigField(
            name="api_key_header",
            label="API Key Header Name",
            type=FieldType.STRING,
            default="X-API-Key",
            advanced=True,
            placeholder="X-API-Key or Authorization",
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
            placeholder='{"Accept": "application/json", "X-Custom-Client": "det-core"}',
            description="Optional extra HTTP headers in JSON format.",
        ),
        ConfigField(
            name="timeout",
            label="Request Timeout (seconds)",
            type=FieldType.INTEGER,
            default=15,
            advanced=True,
            description="HTTP request timeout in seconds.",
        ),
    ]

    table_fields = [
        ConfigField(
            name="endpoint",
            label="Endpoint Path",
            type=FieldType.STRING,
            required=True,
            placeholder="/users, /orders, /products",
            description="API path appended to Base URL.",
        ),
        ConfigField(
            name="data_path",
            label="JSON Data Path (optional)",
            type=FieldType.STRING,
            placeholder="data.items, results, records",
            description="Dot-separated path to the JSON records list (leave empty if response root is a list).",
        ),
        ConfigField(
            name="query_params",
            label="Query Parameters (JSON, optional)",
            type=FieldType.TEXTAREA,
            advanced=True,
            placeholder='{"status": "active", "sort": "desc"}',
            description="URL query parameters as JSON key-value pairs.",
        ),
        ConfigField(
            name="pagination_type",
            label="Pagination Type",
            type=FieldType.SELECT,
            default="none",
            options=[
                {"label": "None (Single Request)", "value": "none"},
                {"label": "Page-based (?page=1&limit=50)", "value": "page"},
                {"label": "Offset-based (?offset=0&limit=50)", "value": "offset"},
            ],
            advanced=True,
            description="Pagination protocol supported by the endpoint.",
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

        base_url = str(s_cfg.get("base_url") or t_opts.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            raise ConnectorValidationError("REST API Base URL is required.")

        endpoint = str(t_opts.get("endpoint") or "").strip()
        if endpoint and not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        full_url = f"{base_url}{endpoint}"

        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "det-core/1.0 (REST Connector)",
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
            header_name = s_cfg.get("api_key_header") or "X-API-Key"
            headers[header_name] = token
        elif auth_type == "basic" and (username or password):
            basic_auth = (username, password)

        # Query params
        params: dict[str, Any] = {}
        q_params = t_opts.get("query_params")
        if isinstance(q_params, str) and q_params.strip():
            try:
                parsed = json.loads(q_params)
                if isinstance(parsed, dict):
                    params.update(parsed)
            except Exception:
                pass
        elif isinstance(q_params, dict):
            params.update(q_params)

        timeout = int(s_cfg.get("timeout") or 15)

        return {
            "base_url": base_url,
            "full_url": full_url,
            "headers": headers,
            "params": params,
            "basic_auth": basic_auth,
            "timeout": timeout,
            "data_path": t_opts.get("data_path"),
            "pagination_type": t_opts.get("pagination_type", "none"),
            "page_size": int(t_opts.get("page_size", 50)),
        }

    def _fetch_records(
        self,
        req_cfg: dict[str, Any],
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        url = req_cfg["full_url"]
        headers = req_cfg["headers"]
        base_params = dict(req_cfg["params"])
        timeout = req_cfg["timeout"]
        auth = req_cfg["basic_auth"]
        data_path = req_cfg["data_path"]
        pagination_type = req_cfg["pagination_type"]
        page_size = req_cfg["page_size"]

        all_records: list[dict[str, Any]] = []

        with httpx.Client(timeout=timeout, auth=auth, headers=headers) as client:
            if pagination_type == "page":
                page = 1
                while True:
                    cur_params = dict(base_params)
                    cur_params["page"] = page
                    cur_params["limit"] = page_size
                    resp = client.get(url, params=cur_params)
                    resp.raise_for_status()
                    payload = resp.json()
                    page_records = extract_json_path(payload, data_path)
                    if not page_records:
                        break
                    all_records.extend(page_records)
                    if limit and len(all_records) >= limit:
                        all_records = all_records[:limit]
                        break
                    if len(page_records) < page_size:
                        break
                    page += 1
            elif pagination_type == "offset":
                offset = 0
                while True:
                    cur_params = dict(base_params)
                    cur_params["offset"] = offset
                    cur_params["limit"] = page_size
                    resp = client.get(url, params=cur_params)
                    resp.raise_for_status()
                    payload = resp.json()
                    page_records = extract_json_path(payload, data_path)
                    if not page_records:
                        break
                    all_records.extend(page_records)
                    if limit and len(all_records) >= limit:
                        all_records = all_records[:limit]
                        break
                    if len(page_records) < page_size:
                        break
                    offset += page_size
            else:
                resp = client.get(url, params=base_params)
                resp.raise_for_status()
                payload = resp.json()
                all_records = extract_json_path(payload, data_path)
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
            test_url = req_cfg["base_url"]
            timeout = req_cfg["timeout"]
            headers = req_cfg["headers"]
            auth = req_cfg["basic_auth"]

            start_t = time.perf_counter()
            with httpx.Client(timeout=timeout, auth=auth, headers=headers) as client:
                resp = client.get(test_url)
            elapsed_ms = (time.perf_counter() - start_t) * 1000

            if resp.status_code < 400:
                return ConnectionTestResult(
                    success=True,
                    message=f"Connected successfully to REST API endpoint ({resp.status_code} OK in {elapsed_ms:.1f}ms).",
                    details={"status_code": resp.status_code, "latency_ms": elapsed_ms, "url": test_url},
                )
            elif resp.status_code in (401, 403):
                return ConnectionTestResult(
                    success=False,
                    message=f"Authentication failed ({resp.status_code} Unauthorized / Forbidden). Check API token or credentials.",
                    details={"status_code": resp.status_code, "url": test_url},
                )
            else:
                return ConnectionTestResult(
                    success=False,
                    message=f"REST API server returned HTTP {resp.status_code}.",
                    details={"status_code": resp.status_code, "url": test_url},
                )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"REST API connection failed: {e}",
            )

    def discover_objects(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[DiscoveredObject]:
        """Discover available endpoints from root API JSON or OpenAPI definition if available."""
        try:
            req_cfg = self._build_request_config(source_config, credentials, options)
            base_url = req_cfg["base_url"]
            headers = req_cfg["headers"]
            auth = req_cfg["basic_auth"]
            timeout = req_cfg["timeout"]

            discovered: list[DiscoveredObject] = []
            with httpx.Client(timeout=timeout, auth=auth, headers=headers) as client:
                # 1. Try openapi.json or swagger.json
                for doc_path in ("/openapi.json", "/swagger.json", "/api/openapi.json"):
                    try:
                        doc_resp = client.get(f"{base_url}{doc_path}")
                        if doc_resp.status_code == 200:
                            doc_data = doc_resp.json()
                            paths = doc_data.get("paths", {})
                            for p in paths.keys():
                                discovered.append(
                                    DiscoveredObject(
                                        id=p,
                                        name=p,
                                        type="endpoint",
                                        path=p,
                                        metadata={"method": "GET"},
                                    )
                                )
                            if discovered:
                                return discovered
                    except Exception:
                        pass

                # 2. Try root endpoint JSON dictionary of endpoints
                try:
                    root_resp = client.get(base_url)
                    if root_resp.status_code == 200:
                        payload = root_resp.json()
                        if isinstance(payload, dict):
                            for k, v in payload.items():
                                if isinstance(v, str) and (v.startswith("/") or v.startswith("http")):
                                    ep = v if v.startswith("/") else ("/" + v.split("/", 3)[-1] if "/" in v else f"/{k}")
                                    discovered.append(
                                        DiscoveredObject(
                                            id=k,
                                            name=f"/{k}",
                                            type="endpoint",
                                            path=ep,
                                        )
                                    )
                except Exception:
                    pass

            return discovered
        except Exception as e:
            raise DiscoveryError(f"Failed to discover REST API endpoints: {e}") from e

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
            raise SchemaInferenceError(f"Failed to infer REST API schema: {e}") from e

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
            raise PreviewError(f"Failed to preview REST API endpoint: {e}") from e

    def read_polars(
        self,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> pl.DataFrame:
        """Scan REST API endpoint records into a Polars DataFrame."""
        req_cfg = self._build_request_config(source_config, credentials, table_options)
        records = self._fetch_records(req_cfg, limit=limit)
        if not records:
            return pl.DataFrame()
        return pl.DataFrame(records)

