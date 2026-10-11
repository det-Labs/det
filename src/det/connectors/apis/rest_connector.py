"""REST / HTTP API Connector."""

from __future__ import annotations

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
    PreviewResult,
    SchemaResult,
)
from det.connectors.errors import (
    SchemaInferenceError,
)


class RestApiConnector(BaseConnector):
    id = "rest"
    name = "REST API"
    group = ConnectorGroup.APIS
    description = "HTTP / REST API web endpoints returning JSON data."

    source_fields = [
        ConfigField(
            name="base_url",
            label="Base URL",
            type="string",
            required=True,
            placeholder="https://jsonplaceholder.typicode.com",
            description="Root API URL.",
        ),
        ConfigField(
            name="auth_type",
            label="Authentication Type",
            type="select",
            default="none",
            options=[
                {"label": "None (Public)", "value": "none"},
                {"label": "Bearer Token", "value": "bearer"},
                {"label": "Basic Authentication", "value": "basic"},
                {"label": "Custom Header / API Key", "value": "api_key"},
            ],
            description="Authentication mechanism.",
        ),
        ConfigField(
            name="username",
            label="Username",
            type="string",
            placeholder="username",
            description="Basic Auth username.",
            advanced=True,
        ),
        ConfigField(
            name="password",
            label="Password",
            type="password",
            secret=True,
            placeholder="••••••••",
            description="Basic Auth password.",
            advanced=True,
        ),
        ConfigField(
            name="api_key",
            label="API Key / Token",
            type="password",
            secret=True,
            placeholder="••••••••",
            description="Bearer token or API key.",
            advanced=True,
        ),
        ConfigField(
            name="header_name",
            label="Header Name",
            type="string",
            default="Authorization",
            placeholder="Authorization or x-api-key",
            description="HTTP header name for custom API key.",
            advanced=True,
        ),
    ]

    table_fields = [
        ConfigField(
            name="endpoint",
            label="Endpoint Path",
            type="string",
            required=True,
            placeholder="/posts or /objects",
            description="Endpoint path relative to Base URL.",
        ),
        ConfigField(
            name="method",
            label="HTTP Method",
            type="select",
            default="GET",
            options=[
                {"label": "GET", "value": "GET"},
                {"label": "POST", "value": "POST"},
            ],
            description="HTTP Request method.",
        ),
        ConfigField(
            name="json_path",
            label="JSON Response Property",
            type="string",
            placeholder="data or results (leave empty if response is root array)",
            description="Key in JSON response that contains the array of records.",
            advanced=True,
        ),
    ]

    def _build_request_params(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> tuple[dict[str, str], Any]:
        headers: dict[str, str] = {"Accept": "application/json"}
        auth_type = str(source_config.get("auth_type") or "none").lower()
        auth = None

        if auth_type == "bearer":
            token = str(credentials.get("api_key") or "").strip()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "basic":
            user = str(source_config.get("username") or "").strip()
            passwd = str(credentials.get("password") or "").strip()
            if user or passwd:
                auth = (user, passwd)
        elif auth_type == "api_key":
            hname = str(source_config.get("header_name") or "x-api-key").strip()
            key = str(credentials.get("api_key") or "").strip()
            if key:
                headers[hname] = key

        return headers, auth

    def test_connection(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> ConnectionTestResult:
        base_url = str(source_config.get("base_url") or "").strip()
        if not base_url:
            return ConnectionTestResult(success=False, message="Base URL is required.")
        headers, auth = self._build_request_params(source_config, credentials)
        try:
            with httpx.Client(follow_redirects=True, timeout=10) as client:
                resp = client.get(base_url, headers=headers, auth=auth)
                return ConnectionTestResult(
                    success=resp.is_success,
                    message=f"HTTP request returned status {resp.status_code}.",
                    details={"status_code": resp.status_code, "url": str(resp.url)},
                )
        except Exception as exc:
            return ConnectionTestResult(success=False, message=f"API request failed: {exc}")

    def discover_objects(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> list[DiscoveredObject]:
        return []

    def _fetch_records(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
    ) -> list[dict[str, Any]]:
        base_url = str(source_config.get("base_url") or "").strip().rstrip("/")
        endpoint = str(table_options.get("endpoint") or "").strip().lstrip("/")
        url = f"{base_url}/{endpoint}" if endpoint else base_url
        headers, auth = self._build_request_params(source_config, credentials)
        method = str(table_options.get("method") or "GET").upper()

        try:
            with httpx.Client(follow_redirects=True, timeout=15) as client:
                resp = client.request(method, url, headers=headers, auth=auth)
                resp.raise_for_status()
                payload = resp.json()

            json_path = str(table_options.get("json_path") or "").strip()
            if json_path and isinstance(payload, dict):
                payload = payload.get(json_path, [])

            if isinstance(payload, dict):
                payload = [payload]
            elif not isinstance(payload, list):
                raise ValueError("API response must be an array of objects or an object.")

            return [item for item in payload if isinstance(item, dict)]
        except Exception as exc:
            raise SchemaInferenceError(f"Failed to query API at {url}: {exc}", connector_id=self.id) from exc

    def infer_schema(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
    ) -> SchemaResult:
        self.validate_table_options(table_options)
        records = self._fetch_records(source_config, credentials, table_options)
        if not records:
            raise SchemaInferenceError("API returned no records.", connector_id=self.id)
        df = pl.DataFrame(records)
        columns = [
            ColumnMetadata(name=str(name), type=str(dtype), nullable=df[name].null_count() > 0)
            for name, dtype in zip(df.columns, df.dtypes)
        ]
        return SchemaResult(columns=columns, row_count_estimate=len(records), sample_size=len(records))

    def preview(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
        limit: int = 50,
    ) -> PreviewResult:
        self.validate_table_options(table_options)
        records = self._fetch_records(source_config, credentials, table_options)
        subset = records[:limit]
        if not subset:
            return PreviewResult(columns=[], rows=[], total_rows=0)
        df = pl.DataFrame(subset)
        rows: list[dict[str, Any]] = []
        for row_dict in df.to_dicts():
            rows.append({
                k: (str(v) if v is not None and not isinstance(v, (int, float, bool, str)) else v)
                for k, v in row_dict.items()
            })
        return PreviewResult(columns=df.columns, rows=rows, total_rows=len(records))
