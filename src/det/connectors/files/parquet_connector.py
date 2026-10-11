"""Apache Parquet connector supporting single files, directories, Hive partitions, and remote endpoints."""

from __future__ import annotations

import io
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


class ParquetConnector(BaseConnector):
    id = "parquet"
    name = "Parquet"
    group = ConnectorGroup.FILES
    description = "Apache Parquet columnar files, folder datasets, and Hive-partitioned directories."

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
            description="Storage location protocol for Parquet data files.",
        ),
        ConfigField(
            name="base_path",
            label="Base Directory or URL",
            type="folder",
            placeholder="/data/warehouse or https://storage.example.com/data",
            description="Base folder path or root URL containing Parquet files or datasets.",
        ),
        ConfigField(
            name="host",
            label="Host",
            type="string",
            placeholder="ftp.example.com",
            description="Hostname or IP address for FTP/SFTP connections.",
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
            placeholder="storage_user",
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
                {"label": "Nested Subfolders (Recursive / Hive)", "value": "recursive"},
            ],
            description="Choose whether to read a single file, folder, or scan nested partitions.",
        ),
        ConfigField(
            name="path",
            label="File or Folder Path",
            type="string",
            required=True,
            placeholder="events.parquet or datasets/sales",
            description="Path to .parquet file, directory, or remote URL.",
        ),
        ConfigField(
            name="file_pattern",
            label="File Filter Pattern",
            type="string",
            default="*.parquet",
            placeholder="*.parquet",
            description="Glob filter pattern for matching files in folders.",
            advanced=True,
        ),
        ConfigField(
            name="hive_partitioning",
            label="Hive Partitioning",
            type="boolean",
            default=True,
            description="Automatically parse Hive partitions (e.g., year=2024/month=10/data.parquet) into schema columns.",
            advanced=False,
        ),
        ConfigField(
            name="columns",
            label="Columns Projection",
            type="string",
            placeholder="id, name, amount",
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
            default_message="Parquet connector ready.",
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
            default_pattern="*.parquet",
            options=options,
            connector_id=self.id,
        )

    def _get_target_paths(
        self,
        source_config: dict[str, Any],
        table_options: dict[str, Any],
    ) -> list[Path]:
        files = resolve_local_file_paths(source_config, table_options, default_pattern="*.parquet")
        if not files:
            raise SchemaInferenceError("No matching Parquet files found for specified path.", connector_id=self.id)
        if not files[0].exists():
            raise SchemaInferenceError(f"Parquet path does not exist: {files[0]}", connector_id=self.id)
        return files

    def _read_polars_df(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
        n_rows: int | None = None,
    ) -> pl.DataFrame:
        proto = resolve_protocol(source_config, table_options)
        hive = bool(table_options.get("hive_partitioning", True))
        cols_raw = str(table_options.get("columns") or "").strip()
        selected_cols = [c.strip() for c in cols_raw.split(",") if c.strip()] if cols_raw else None

        if proto == "local":
            files = self._get_target_paths(source_config, table_options)
            file_paths = [str(f) for f in files]
            try:
                if len(file_paths) == 1:
                    lf = pl.scan_parquet(file_paths[0], hive_partitioning=hive)
                else:
                    lf = pl.scan_parquet(file_paths, hive_partitioning=hive)

                if selected_cols:
                    avail = lf.collect_schema().names()
                    valid_cols = [c for c in selected_cols if c in avail]
                    if valid_cols:
                        lf = lf.select(valid_cols)

                if n_rows is not None:
                    lf = lf.head(n_rows)

                return lf.collect()
            except Exception as exc:
                raise SchemaInferenceError(f"Failed to read Parquet data: {exc}", connector_id=self.id) from exc
        else:
            raw_bytes = fetch_remote_bytes(source_config, credentials, table_options, connector_id=self.id)
            try:
                df = pl.read_parquet(io.BytesIO(raw_bytes), n_rows=n_rows)
                if selected_cols:
                    valid_cols = [c for c in selected_cols if c in df.columns]
                    if valid_cols:
                        df = df.select(valid_cols)
                return df
            except Exception as exc:
                raise SchemaInferenceError(f"Failed to parse Parquet from remote bytes: {exc}", connector_id=self.id) from exc

    def infer_schema(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
    ) -> SchemaResult:
        self.validate_table_options(table_options)
        proto = resolve_protocol(source_config, table_options)
        hive = bool(table_options.get("hive_partitioning", True))
        cols_raw = str(table_options.get("columns") or "").strip()
        selected_cols = [c.strip() for c in cols_raw.split(",") if c.strip()] if cols_raw else None

        try:
            if proto == "local":
                files = self._get_target_paths(source_config, table_options)
                file_paths = [str(f) for f in files]
                lf = pl.scan_parquet(file_paths[0] if len(file_paths) == 1 else file_paths, hive_partitioning=hive)
                if selected_cols:
                    avail = lf.collect_schema().names()
                    valid_cols = [c for c in selected_cols if c in avail]
                    if valid_cols:
                        lf = lf.select(valid_cols)

                schema = lf.collect_schema()
                sample_df = lf.head(100).collect()

                columns: list[ColumnMetadata] = []
                for name, dtype in schema.items():
                    nullable = sample_df[name].null_count() > 0 if name in sample_df.columns else True
                    columns.append(map_polars_dtype_to_metadata(name, dtype, is_nullable=nullable))

                try:
                    total_rows = lf.select(pl.len()).collect().item()
                except Exception:
                    total_rows = len(sample_df)

                return SchemaResult(
                    columns=columns,
                    row_count_estimate=total_rows,
                    sample_size=len(sample_df),
                )
            else:
                df = self._read_polars_df(source_config, credentials, table_options, n_rows=1000)
                columns = [
                    map_polars_dtype_to_metadata(name, dtype, is_nullable=df[name].null_count() > 0)
                    for name, dtype in zip(df.columns, df.dtypes)
                ]
                return SchemaResult(
                    columns=columns,
                    row_count_estimate=len(df),
                    sample_size=len(df),
                )
        except Exception as exc:
            if isinstance(exc, (SchemaInferenceError, PreviewError)):
                raise
            raise SchemaInferenceError(f"Parquet schema inference failed: {exc}", connector_id=self.id) from exc

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
            raise PreviewError(f"Parquet preview failed: {exc}", connector_id=self.id) from exc

        rows = format_preview_rows(df)
        return PreviewResult(columns=df.columns, rows=rows, total_rows=len(rows))
