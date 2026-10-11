"""Extensible Markup Language (XML) connector supporting files, folders, and remote endpoints."""

from __future__ import annotations

import xml.etree.ElementTree as ET
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
from det.connectors.errors import DiscoveryError, PreviewError, SchemaInferenceError
from det.connectors.files.file_utils import (
    discover_files_endpoint,
    fetch_remote_bytes,
    format_preview_rows,
    map_polars_dtype_to_metadata,
    resolve_local_file_paths,
    resolve_protocol,
    test_connection_endpoint,
)


class XMLConnector(BaseConnector):
    id = "xml"
    name = "XML"
    group = ConnectorGroup.FILES
    description = "Extensible Markup Language (.xml) data records, XML folders, and remote endpoints."

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
            description="Storage location protocol for XML files.",
        ),
        ConfigField(
            name="base_path",
            label="Base Directory or URL",
            type="folder",
            placeholder="/data/xml_feeds or https://feeds.example.com",
            description="Root folder or base URL containing XML files.",
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
            placeholder="xml_user",
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
            description="Read a single XML file, all files in a folder, or scan recursively.",
        ),
        ConfigField(
            name="path",
            label="File or Folder Path",
            type="string",
            required=True,
            placeholder="records.xml or xml_dir",
            description="Path to XML file, directory, or remote URL.",
        ),
        ConfigField(
            name="row_tag",
            label="Row Element Tag (optional)",
            type="string",
            placeholder="item, record, or book (leave empty to use root children)",
            description="XML tag name identifying each row / record element.",
            advanced=False,
        ),
        ConfigField(
            name="file_pattern",
            label="File Filter Pattern",
            type="string",
            default="*.xml",
            placeholder="*.xml",
            description="Glob filter pattern for matching XML files.",
            advanced=True,
        ),
        ConfigField(
            name="columns",
            label="Columns Projection",
            type="string",
            placeholder="id, title, price",
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
            default_message="XML connector ready.",
        )

    def discover_objects(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> list[DiscoveredObject]:
        opts = options or {}
        path_opt = str(opts.get("path") or "").strip()
        proto = resolve_protocol(source_config, opts)

        # If pointing to an XML file, discover candidate row tags
        if path_opt and proto == "local":
            files = resolve_local_file_paths(source_config, opts, default_pattern="*.xml")
            if files and files[0].is_file():
                try:
                    tree = ET.parse(str(files[0]))
                    root = tree.getroot()
                    unique_tags = {elem.tag for elem in list(root)}
                    return [
                        DiscoveredObject(
                            id=tag,
                            name=tag,
                            type="tag",
                            path=str(files[0]),
                            metadata={"row_tag": tag},
                        )
                        for tag in sorted(unique_tags)
                    ]
                except Exception as exc:
                    raise DiscoveryError(f"Failed to inspect XML tags in {files[0]}: {exc}", connector_id=self.id) from exc

        return discover_files_endpoint(
            source_config=source_config,
            credentials=credentials,
            default_pattern="*.xml",
            options=options,
            connector_id=self.id,
        )

    def _parse_xml_root(self, root: ET.Element, row_tag: str, n_rows: int | None = None) -> list[dict[str, Any]]:
        elements = root.findall(f".//{row_tag}") if row_tag else list(root)
        records: list[dict[str, Any]] = []
        for elem in elements:
            record: dict[str, Any] = {**elem.attrib}
            for child in elem:
                record[child.tag] = child.text
            # If element has no children but has text and attribs
            if not len(elem) and elem.text and elem.text.strip():
                record["_value"] = elem.text.strip()

            records.append(record)
            if n_rows is not None and len(records) >= n_rows:
                break
        return records

    def _read_polars_df(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
        n_rows: int | None = None,
    ) -> pl.DataFrame:
        proto = resolve_protocol(source_config, table_options)
        row_tag = str(table_options.get("row_tag") or "").strip()
        cols_raw = str(table_options.get("columns") or "").strip()
        selected_cols = [c.strip() for c in cols_raw.split(",") if c.strip()] if cols_raw else None

        if proto == "local":
            files = resolve_local_file_paths(source_config, table_options, default_pattern="*.xml")
            if not files:
                raise SchemaInferenceError("No matching XML files found for path.", connector_id=self.id)
            if not files[0].exists():
                raise SchemaInferenceError(f"XML file does not exist: {files[0]}", connector_id=self.id)

            all_records: list[dict[str, Any]] = []
            for f in files:
                try:
                    tree = ET.parse(str(f))
                    root = tree.getroot()
                    file_records = self._parse_xml_root(root, row_tag, n_rows)
                    all_records.extend(file_records)
                    if n_rows is not None and len(all_records) >= n_rows:
                        break
                except Exception as exc:
                    raise SchemaInferenceError(f"Failed to parse XML file {f.name}: {exc}", connector_id=self.id) from exc

            df = pl.DataFrame(all_records) if all_records else pl.DataFrame()
        else:
            raw_bytes = fetch_remote_bytes(source_config, credentials, table_options, connector_id=self.id)
            try:
                root = ET.fromstring(raw_bytes)
                records = self._parse_xml_root(root, row_tag, n_rows)
                df = pl.DataFrame(records) if records else pl.DataFrame()
            except Exception as exc:
                raise SchemaInferenceError(f"Failed to parse XML from remote bytes: {exc}", connector_id=self.id) from exc

        if selected_cols and len(df) > 0:
            valid_cols = [c for c in selected_cols if c in df.columns]
            if valid_cols:
                df = df.select(valid_cols)

        if n_rows is not None and len(df) > 0:
            df = df.head(n_rows)

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
            raise SchemaInferenceError(f"XML schema inference failed: {exc}", connector_id=self.id) from exc

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
            raise PreviewError(f"XML preview failed: {exc}", connector_id=self.id) from exc

        rows = format_preview_rows(df)
        return PreviewResult(columns=df.columns, rows=rows, total_rows=len(rows))
