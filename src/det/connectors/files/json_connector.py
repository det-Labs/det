"""JSON Connector supporting JSON Lines (NDJSON), JSON Arrays, directories, and remote endpoints."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import polars as pl

from det.connectors.contract import (
    BaseConnector,
    ConfigField,
    ConnectionTestResult,
    ConnectorGroup,
    DiscoveredObject,
    PreviewResult,
    SchemaResult,
)
from det.connectors.errors import PreviewError, SchemaInferenceError
from det.connectors.files.file_utils import (
    discover_files_endpoint,
    fetch_remote_bytes,
    format_preview_rows,
    map_polars_dtype_to_metadata,
    resolve_local_file_paths,
    resolve_protocol,
    test_connection_endpoint,
)


class JSONConnector(BaseConnector):
    id = "json"
    name = "JSON"
    group = ConnectorGroup.FILES
    description = "JavaScript Object Notation files (NDJSON / JSON Lines and JSON array documents)."

    source_fields = [
        ConfigField(
            name="protocol",
            label="Protocol / Storage Type",
            type="select",
            default="local",
            options=[
                {"label": "Local Filesystem", "value": "local"},
                {"label": "Remote HTTP / HTTPS", "value": "http"},
                {"label": "Remote FTP Server", "value": "ftp"},
                {"label": "Remote SFTP Server (SSH)", "value": "sftp"},
            ],
            description="Storage location protocol for JSON files.",
        ),
        ConfigField(
            name="base_path",
            label="Base Directory or URL",
            type="folder",
            placeholder="/data/events or https://api.example.com/data",
            description="Root folder or base URL containing JSON files.",
        ),
        ConfigField(
            name="host",
            label="Host",
            type="string",
            placeholder="ftp.example.com",
            description="Hostname or IP for remote connections.",
            advanced=True,
        ),
        ConfigField(
            name="port",
            label="Port",
            type="integer",
            placeholder="21 or 22",
            description="Port number for FTP (21) or SFTP (22).",
            advanced=True,
        ),
        ConfigField(
            name="username",
            label="Username",
            type="string",
            placeholder="json_user",
            description="Authentication username.",
            advanced=True,
        ),
        ConfigField(
            name="password",
            label="Password / Token",
            type="password",
            secret=True,
            description="Password or secret token for remote storage access.",
            advanced=True,
        ),
    ]

    table_fields = [
        ConfigField(
            name="file_selection",
            label="File Selection Mode",
            type="select",
            default="auto",
            options=[
                {"label": "Auto-detect (File or Folder)", "value": "auto"},
                {"label": "Single File", "value": "single"},
                {"label": "Multiple Files in Folder", "value": "folder"},
                {"label": "Nested Subfolders (Recursive)", "value": "recursive"},
            ],
            description="Choose whether to read a single file, a folder of JSON files, or scan recursively.",
        ),
        ConfigField(
            name="path",
            label="File or Folder Path",
            type="string",
            required=True,
            placeholder="records.ndjson or events_dir",
            description="Path to JSON file, directory, or remote URL.",
        ),
        ConfigField(
            name="json_format",
            label="JSON Structure",
            type="select",
            default="auto",
            options=[
                {"label": "Auto-detect (inspect file content/extension)", "value": "auto"},
                {"label": "JSON Lines / NDJSON (one JSON object per line)", "value": "lines"},
                {"label": "Standard JSON Array ([{...}, {...}])", "value": "array"},
            ],
            description="Structure format of the JSON data.",
        ),
        ConfigField(
            name="file_pattern",
            label="File Filter Pattern",
            type="string",
            default="*.json*",
            placeholder="*.json*",
            description="Glob pattern when reading folders (e.g. *.ndjson or *.json).",
            advanced=True,
        ),
        ConfigField(
            name="columns",
            label="Columns Projection",
            type="string",
            placeholder="id, name, event_type",
            description="Optional comma-separated list of column names to project.",
            advanced=True,
        ),
    ]

    def test_connection(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> ConnectionTestResult:
        return test_connection_endpoint(
            source_config=source_config,
            credentials=credentials,
            connector_id=self.id,
            default_message="JSON connector ready.",
        )

    def discover_objects(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> list[DiscoveredObject]:
        return discover_files_endpoint(
            source_config=source_config,
            credentials=credentials,
            default_pattern="*.json*",
            options=options,
            connector_id=self.id,
        )

    def _determine_format(self, first_path_or_bytes: Path | bytes, requested_format: str) -> str:
        req = requested_format.lower()
        if req in {"lines", "ndjson"}:
            return "lines"
        if req in {"array", "standard"}:
            return "array"

        # Auto-detect: check extension or first non-whitespace character
        if isinstance(first_path_or_bytes, Path):
            ext = first_path_or_bytes.suffix.lower()
            if ext in {".ndjson", ".jsonl"}:
                return "lines"
            try:
                with first_path_or_bytes.open("r", encoding="utf-8") as stream:
                    for line in stream:
                        line_stripped = line.strip()
                        if line_stripped:
                            if line_stripped.startswith("["):
                                return "array"
                            if line_stripped.startswith("{"):
                                return "lines"
            except Exception:
                pass
        elif isinstance(first_path_or_bytes, (bytes, bytearray)):
            stripped = first_path_or_bytes.strip()
            if stripped.startswith(b"["):
                return "array"
            if stripped.startswith(b"{"):
                return "lines"

        return "array"

    def _read_polars_df(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
        n_rows: int | None = None,
    ) -> pl.DataFrame:
        proto = resolve_protocol(source_config, table_options)
        req_fmt = str(table_options.get("json_format") or "auto").lower()
        cols_raw = str(table_options.get("columns") or "").strip()
        selected_cols = [c.strip() for c in cols_raw.split(",") if c.strip()] if cols_raw else None

        if proto == "local":
            files = resolve_local_file_paths(source_config, table_options, default_pattern="*.json*")
            if not files:
                raise SchemaInferenceError("No matching JSON files found for path.", connector_id=self.id)
            if not files[0].exists():
                raise SchemaInferenceError(f"JSON file does not exist: {files[0]}", connector_id=self.id)

            fmt = self._determine_format(files[0], req_fmt)

            try:
                if fmt == "lines":
                    if len(files) == 1:
                        df = pl.read_ndjson(str(files[0]), n_rows=n_rows)
                    else:
                        df = pl.read_ndjson([str(f) for f in files], n_rows=n_rows)
                else:
                    # Array or multi-file standard JSON
                    all_records: list[dict[str, Any]] = []
                    for f in files:
                        with f.open("r", encoding="utf-8") as stream:
                            content = json.load(stream)
                        if isinstance(content, dict):
                            all_records.append(content)
                        elif isinstance(content, list):
                            all_records.extend(content)
                        if n_rows is not None and len(all_records) >= n_rows:
                            break
                    if not all_records:
                        df = pl.DataFrame()
                    else:
                        df = pl.DataFrame(all_records)
                        if n_rows is not None:
                            df = df.head(n_rows)
            except Exception as exc:
                # If first format failed, try alternate fallback
                try:
                    if fmt == "array":
                        df = pl.read_ndjson([str(f) for f in files], n_rows=n_rows)
                    else:
                        with files[0].open("r", encoding="utf-8") as stream:
                            raw = json.load(stream)
                        df = pl.DataFrame(raw if isinstance(raw, list) else [raw])
                        if n_rows is not None:
                            df = df.head(n_rows)
                except Exception:
                    raise SchemaInferenceError(f"Failed to parse JSON file(s): {exc}", connector_id=self.id) from exc
        else:
            raw_bytes = fetch_remote_bytes(source_config, credentials, table_options, connector_id=self.id)
            fmt = self._determine_format(raw_bytes, req_fmt)
            try:
                if fmt == "lines":
                    df = pl.read_ndjson(io.BytesIO(raw_bytes), n_rows=n_rows)
                else:
                    try:
                        df = pl.read_json(io.BytesIO(raw_bytes))
                        if n_rows is not None:
                            df = df.head(n_rows)
                    except Exception:
                        df = pl.read_ndjson(io.BytesIO(raw_bytes), n_rows=n_rows)
            except Exception as exc:
                raise SchemaInferenceError(f"Failed to parse JSON from remote bytes: {exc}", connector_id=self.id) from exc

        if selected_cols:
            valid_cols = [c for c in selected_cols if c in df.columns]
            if valid_cols:
                df = df.select(valid_cols)

        return df

    def infer_schema(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
    ) -> SchemaResult:
        self.validate_table_options(table_options)
        try:
            df = self._read_polars_df(source_config, credentials, table_options, n_rows=1000)
        except Exception as exc:
            if isinstance(exc, (SchemaInferenceError, PreviewError)):
                raise
            raise SchemaInferenceError(f"JSON schema inference failed: {exc}", connector_id=self.id) from exc

        columns = [
            map_polars_dtype_to_metadata(name, dtype, is_nullable=df[name].null_count() > 0 or len(df) == 0)
            for name, dtype in zip(df.columns, df.dtypes)
        ]
        return SchemaResult(
            columns=columns,
            row_count_estimate=len(df),
            sample_size=len(df),
        )

    def preview(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
        limit: int = 50,
    ) -> PreviewResult:
        self.validate_table_options(table_options)
        try:
            df = self._read_polars_df(source_config, credentials, table_options, n_rows=limit)
        except Exception as exc:
            if isinstance(exc, PreviewError):
                raise
            raise PreviewError(f"JSON preview failed: {exc}", connector_id=self.id) from exc

        rows = format_preview_rows(df)
        return PreviewResult(columns=df.columns, rows=rows, total_rows=len(rows))
