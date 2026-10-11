"""CSV Connector supporting local files/directories, HTTP, FTP, and SFTP."""

from __future__ import annotations

import ftplib
import io
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
    DiscoveryError,
    PreviewError,
    SchemaInferenceError,
)


class CSVConnector(BaseConnector):
    id = "csv"
    name = "CSV"
    group = ConnectorGroup.FILES
    description = (
        "Delimited text files (CSV, TSV, custom delimiters) from local disks, nested folders, HTTP, FTP, or SFTP."
    )

    source_fields = [
        ConfigField(
            name="protocol",
            label="Location Protocol",
            type="select",
            default="local",
            options=[
                {"label": "Local filesystem", "value": "local"},
                {"label": "HTTP / HTTPS", "value": "http"},
                {"label": "FTP Server", "value": "ftp"},
                {"label": "SFTP Server", "value": "sftp"},
            ],
            description="Protocol / location type for the shared connection source.",
        ),
        ConfigField(
            name="base_path",
            label="Base Path or URL",
            type="string",
            placeholder="D:/Data or https://example.com/data",
            description="Root directory or base URL prefix for files.",
        ),
        ConfigField(
            name="host",
            label="Host",
            type="string",
            placeholder="ftp.example.com",
            description="Server hostname for FTP / SFTP connections.",
            advanced=True,
        ),
        ConfigField(
            name="port",
            label="Port",
            type="integer",
            placeholder="21 for FTP, 22 for SFTP",
            description="Connection port for FTP / SFTP.",
            advanced=True,
        ),
        ConfigField(
            name="username",
            label="Username",
            type="string",
            placeholder="username",
            description="Username for FTP / SFTP / HTTP authentication.",
            advanced=True,
        ),
        ConfigField(
            name="password",
            label="Password / Secret",
            type="password",
            secret=True,
            placeholder="••••••••",
            description="Password, auth token, or secret key.",
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
            description="Choose whether to read a single file, multiple files in a folder, or scan nested folders.",
        ),
        ConfigField(
            name="path",
            label="File or Folder Path",
            type="string",
            required=True,
            placeholder="data/sales.csv or sales_archive",
            description="Local file path, directory path, or remote path.",
        ),
        ConfigField(
            name="file_pattern",
            label="Filename Filter / Wildcard",
            type="string",
            default="*.csv",
            placeholder="*.csv or sales_*.csv",
            description="Glob filter pattern when scanning a directory.",
            advanced=False,
        ),
        ConfigField(
            name="delimiter",
            label="Delimiter",
            type="select",
            default=",",
            options=[
                {"label": "Comma (,)", "value": ","},
                {"label": "Semicolon (;)", "value": ";"},
                {"label": "Tab (\\t)", "value": "\t"},
                {"label": "Pipe (|)", "value": "|"},
            ],
            description="Character separating field values.",
        ),
        ConfigField(
            name="has_header",
            label="First Row as Header",
            type="boolean",
            default=True,
            description="Whether the first row contains column headers.",
        ),
        ConfigField(
            name="encoding",
            label="Encoding",
            type="select",
            default="utf-8",
            options=[
                {"label": "UTF-8", "value": "utf-8"},
                {"label": "UTF-8 with BOM", "value": "utf-8-sig"},
                {"label": "Latin-1 / ISO-8859-1", "value": "latin-1"},
                {"label": "Windows-1252 (CP1252)", "value": "cp1252"},
                {"label": "ASCII", "value": "ascii"},
            ],
            description="Text encoding of the CSV files.",
            advanced=True,
        ),
        ConfigField(
            name="skip_rows",
            label="Skip Leading Rows",
            type="integer",
            default=0,
            placeholder="0",
            description="Number of initial rows to skip before headers and data.",
            advanced=True,
        ),
        ConfigField(
            name="comment_prefix",
            label="Comment Prefix",
            type="string",
            default="",
            placeholder="#",
            description="Lines starting with this character/string are ignored.",
            advanced=True,
        ),
    ]

    fields = source_fields + table_fields


    def _normalize(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for arg in args:
            if isinstance(arg, dict):
                merged.update(arg)
        for k, v in kwargs.items():
            if isinstance(v, dict):
                merged.update(v)
            elif k != "limit":
                merged[k] = v
        return merged


    def _resolve_protocol(self, source_config: dict[str, Any], table_options: dict[str, Any]) -> str:
        proto = str(source_config.get("protocol") or "local").lower()
        path = str(table_options.get("path") or "").strip()
        if path.startswith(("http://", "https://")):
            return "http"
        if path.startswith("ftp://"):
            return "ftp"
        if path.startswith("sftp://"):
            return "sftp"
        return proto

    def _resolve_local_paths(
        self,
        source_config: dict[str, Any],
        table_options: dict[str, Any],
    ) -> list[Path]:
        raw_path = str(table_options.get("path") or "").strip()
        base_path = str(source_config.get("base_path") or "").strip()
        target = Path(raw_path)
        if not target.is_absolute() and base_path:
            target = Path(base_path) / target

        target = target.expanduser().resolve()
        mode = str(table_options.get("file_selection") or "auto").lower()
        recursive = bool(table_options.get("recursive", False)) or (mode == "recursive")
        pattern = str(table_options.get("file_pattern") or "*.csv").strip() or "*.csv"

        if mode == "single" and target.is_file():
            return [target]
        if target.is_file() and mode in {"auto", "single"}:
            return [target]
        if target.is_dir():
            files = list(target.rglob(pattern) if recursive else target.glob(pattern))
            return [f for f in sorted(files) if f.is_file()]

        # Check if raw_path is a glob itself
        if any(c in raw_path for c in ["*", "?", "["]):
            parent = target.parent
            if parent.is_dir():
                files = list(parent.rglob(target.name) if recursive else parent.glob(target.name))
                return [f for f in sorted(files) if f.is_file()]

        return [target]

    def _fetch_remote_bytes(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
        max_bytes: int | None = None,
    ) -> bytes:
        proto = self._resolve_protocol(source_config, table_options)
        path = str(table_options.get("path") or "").strip()
        base = str(source_config.get("base_path") or "").strip()

        if proto in {"http", "https"}:
            url = path if path.startswith(("http://", "https://")) else f"{base.rstrip('/')}/{path.lstrip('/')}"
            headers: dict[str, str] = {}
            username = source_config.get("username")
            password = credentials.get("password")
            auth = (username, password) if username and password else None
            if max_bytes:
                headers["Range"] = f"bytes=0-{max_bytes - 1}"
            try:
                with httpx.Client(follow_redirects=True, timeout=15) as client:
                    resp = client.get(url, headers=headers, auth=auth)
                    resp.raise_for_status()
                    return resp.content
            except Exception as exc:
                raise PreviewError(f"Failed to fetch CSV over HTTP from {url}: {exc}", connector_id=self.id) from exc

        if proto == "ftp":
            host = source_config.get("host") or urlparse(base).hostname or "localhost"
            port = int(source_config.get("port") or 21)
            user = source_config.get("username") or "anonymous"
            passwd = credentials.get("password") or ""
            try:
                ftp = ftplib.FTP()
                ftp.connect(host, port, timeout=10)
                ftp.login(user, passwd)
                buffer = io.BytesIO()
                remote_path = path if not base else f"{base.rstrip('/')}/{path.lstrip('/')}"
                ftp.retrbinary(f"RETR {remote_path}", buffer.write, blocksize=8192)
                ftp.quit()
                return buffer.getvalue()
            except Exception as exc:
                raise PreviewError(f"Failed to fetch CSV over FTP: {exc}", connector_id=self.id) from exc

        if proto == "sftp":
            try:
                import paramiko  # type: ignore
            except ImportError as exc:
                raise PreviewError("SFTP requires paramiko package ('pip install paramiko').", connector_id=self.id) from exc
            host = source_config.get("host") or urlparse(base).hostname or "localhost"
            port = int(source_config.get("port") or 22)
            user = source_config.get("username") or ""
            passwd = credentials.get("password") or ""
            try:
                transport = paramiko.Transport((host, port))
                transport.connect(username=user, password=passwd)
                sftp = paramiko.SFTPClient.from_transport(transport)
                buffer = io.BytesIO()
                remote_path = path if not base else f"{base.rstrip('/')}/{path.lstrip('/')}"
                sftp.getfo(remote_path, buffer)
                sftp.close()
                transport.close()
                return buffer.getvalue()
            except Exception as exc:
                raise PreviewError(f"Failed to fetch CSV over SFTP: {exc}", connector_id=self.id) from exc

        raise PreviewError(f"Unsupported protocol: {proto}", connector_id=self.id)

    def test_connection(
        self,
        options: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> ConnectionTestResult:
        merged = self._normalize(options, *args, **kwargs)
        base = str(merged.get("base_path") or merged.get("path") or "").strip()
        proto = str(merged.get("protocol") or "local").lower()
        if base.startswith(("http://", "https://")):
            proto = "http"
        elif base.startswith("ftp://"):
            proto = "ftp"
        elif base.startswith("sftp://"):
            proto = "sftp"

        if proto == "local":
            if not base:
                return ConnectionTestResult(success=True, message="Local filesystem is accessible.")
            target = Path(base).expanduser().resolve()
            if not target.exists():
                return ConnectionTestResult(
                    success=False,
                    message=f"Local path does not exist: {target}",
                    details={"path": str(target)},
                )
            return ConnectionTestResult(
                success=True,
                message=f"Local path exists and is accessible: {target}",
                details={"path": str(target), "is_dir": target.is_dir()},
            )

        if proto in {"http", "https"}:
            if not base:
                return ConnectionTestResult(success=True, message="HTTP connector ready.")
            username = merged.get("username")
            password = merged.get("password")
            auth = (username, password) if username and password else None
            try:
                with httpx.Client(follow_redirects=True, timeout=10) as client:
                    resp = client.head(base, auth=auth)
                    if resp.status_code >= 400:
                        resp = client.get(base, headers={"Range": "bytes=0-10"}, auth=auth)

                    return ConnectionTestResult(
                        success=resp.is_success,
                        message=f"HTTP endpoint reached with status {resp.status_code}.",
                        details={"status_code": resp.status_code, "url": str(resp.url)},
                    )
            except Exception as exc:
                return ConnectionTestResult(
                    success=False,
                    message=f"Cannot reach HTTP endpoint: {exc}",
                    details={"error": str(exc)},
                )

        if proto == "ftp":
            host = merged.get("host") or urlparse(base).hostname or ""
            port = int(merged.get("port") or 21)
            user = merged.get("username") or "anonymous"
            passwd = merged.get("password") or ""
            if not host:
                return ConnectionTestResult(success=False, message="FTP Host is required.")
            try:
                ftp = ftplib.FTP()
                ftp.connect(host, port, timeout=10)
                ftp.login(user, passwd)
                ftp.quit()
                return ConnectionTestResult(success=True, message=f"Connected to FTP server {host}:{port}.")
            except Exception as exc:
                return ConnectionTestResult(success=False, message=f"FTP connection failed: {exc}")

        if proto == "sftp":
            try:
                import paramiko  # type: ignore
            except ImportError:
                return ConnectionTestResult(
                    success=False,
                    message="SFTP requires the paramiko package ('pip install paramiko').",
                )
            host = merged.get("host") or urlparse(base).hostname or ""
            port = int(merged.get("port") or 22)
            user = merged.get("username") or ""
            passwd = merged.get("password") or ""
            if not host:
                return ConnectionTestResult(success=False, message="SFTP Host is required.")
            try:
                transport = paramiko.Transport((host, port))
                transport.connect(username=user, password=passwd)
                transport.close()
                return ConnectionTestResult(success=True, message=f"Connected to SFTP server {host}:{port}.")
            except Exception as exc:
                return ConnectionTestResult(success=False, message=f"SFTP connection failed: {exc}")


        return ConnectionTestResult(success=False, message=f"Unsupported protocol: {proto}")

    def discover_objects(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> list[DiscoveredObject]:
        proto = str(source_config.get("protocol") or "local").lower()
        base = str(source_config.get("base_path") or "").strip()
        opts = options or {}
        pattern = str(opts.get("file_pattern") or "*.csv").strip() or "*.csv"
        recursive = bool(opts.get("recursive", False))

        if proto == "local":
            target = Path(base if base else ".").expanduser().resolve()
            if not target.exists():
                raise DiscoveryError(f"Directory does not exist: {target}", connector_id=self.id)
            if target.is_file():
                return [
                    DiscoveredObject(
                        id=target.name,
                        name=target.name,
                        type="file",
                        path=str(target),
                        metadata={"size": target.stat().st_size},
                    )
                ]
            files = list(target.rglob(pattern) if recursive else target.glob(pattern))
            results: list[DiscoveredObject] = []
            for f in sorted(files):
                if f.is_file():
                    rel = str(f.relative_to(target)).replace("\\", "/")
                    results.append(
                        DiscoveredObject(
                            id=rel,
                            name=f.name,
                            type="file",
                            path=str(f),
                            metadata={"size": f.stat().st_size, "relative_path": rel},
                        )
                    )
            return results

        if proto == "ftp":
            host = source_config.get("host") or urlparse(base).hostname or ""
            port = int(source_config.get("port") or 21)
            user = source_config.get("username") or "anonymous"
            passwd = credentials.get("password") or ""
            try:
                ftp = ftplib.FTP()
                ftp.connect(host, port, timeout=10)
                ftp.login(user, passwd)
                remote_dir = urlparse(base).path if base.startswith("ftp://") else base
                if remote_dir:
                    try:
                        ftp.cwd(remote_dir)
                    except Exception:
                        pass
                file_list = ftp.nlst()
                ftp.quit()
                regex = re.compile(pattern.replace(".", r"\.").replace("*", ".*"))
                return [
                    DiscoveredObject(id=name, name=name, type="file", path=name)
                    for name in sorted(file_list)
                    if regex.match(name)
                ]
            except Exception as exc:
                raise DiscoveryError(f"FTP discovery error: {exc}", connector_id=self.id) from exc

        if proto == "sftp":
            try:
                import paramiko  # type: ignore
            except ImportError:
                return []
            host = source_config.get("host") or urlparse(base).hostname or ""
            port = int(source_config.get("port") or 22)
            user = source_config.get("username") or ""
            passwd = credentials.get("password") or ""
            try:
                transport = paramiko.Transport((host, port))
                transport.connect(username=user, password=passwd)
                sftp = paramiko.SFTPClient.from_transport(transport)
                remote_dir = base if base else "."
                file_list = sftp.listdir(remote_dir)
                sftp.close()
                transport.close()
                regex = re.compile(pattern.replace(".", r"\.").replace("*", ".*"))
                return [
                    DiscoveredObject(
                        id=name,
                        name=name,
                        type="file",
                        path=f"{remote_dir.rstrip('/')}/{name}" if remote_dir != "." else name,
                    )
                    for name in sorted(file_list)
                    if regex.match(name)
                ]
            except Exception as exc:
                raise DiscoveryError(f"SFTP discovery error: {exc}", connector_id=self.id) from exc

        return []

    def _read_polars_df(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
        n_rows: int | None = None,
    ) -> pl.DataFrame:
        proto = self._resolve_protocol(source_config, table_options)
        delimiter = str(table_options.get("delimiter") or ",")
        has_header = bool(table_options.get("has_header", True))
        skip_rows = int(table_options.get("skip_rows") or 0)
        encoding = str(table_options.get("encoding") or "utf-8").lower()
        quote_char = str(table_options.get("quote_char") or '"')
        comment_prefix = table_options.get("comment_prefix") or None

        read_kwargs: dict[str, Any] = {
            "separator": delimiter,
            "has_header": has_header,
            "skip_rows": skip_rows,
            "encoding": "utf8-lossy" if "utf" in encoding else encoding,
            "quote_char": quote_char if quote_char else None,
            "comment_prefix": comment_prefix,
            "infer_schema_length": 10000,
        }
        if n_rows is not None:
            read_kwargs["n_rows"] = n_rows

        if proto == "local":
            files = self._resolve_local_paths(source_config, table_options)
            if not files:
                raise SchemaInferenceError("No matching CSV files found for path.", connector_id=self.id)
            first_file = files[0]
            if not first_file.is_file():
                raise SchemaInferenceError(f"CSV file does not exist: {first_file}", connector_id=self.id)
            try:
                if len(files) == 1:
                    return pl.read_csv(str(first_file), **read_kwargs)
                else:
                    # Multiple matching files
                    return pl.read_csv([str(f) for f in files], **read_kwargs)
            except Exception as exc:
                raise SchemaInferenceError(f"Failed to parse CSV file(s): {exc}", connector_id=self.id) from exc
        else:
            raw_data = self._fetch_remote_bytes(source_config, credentials, table_options)
            try:
                return pl.read_csv(io.BytesIO(raw_data), **read_kwargs)
            except Exception as exc:
                raise SchemaInferenceError(f"Failed to parse CSV from remote bytes: {exc}", connector_id=self.id) from exc

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
            raise SchemaInferenceError(f"Schema inference failed: {exc}", connector_id=self.id) from exc

        columns: list[ColumnMetadata] = []
        for name, dtype in zip(df.columns, df.dtypes):
            type_str = self._map_dtype(dtype)
            nullable = df[name].null_count() > 0 or len(df) == 0
            columns.append(ColumnMetadata(name=str(name), type=type_str, nullable=nullable))

        total_rows: int | None = None
        proto = self._resolve_protocol(source_config, table_options)
        if proto == "local":
            try:
                files = self._resolve_local_paths(source_config, table_options)
                if len(files) == 1 and files[0].is_file():
                    # Quick approximate or exact count
                    lazy_df = pl.scan_csv(
                        str(files[0]),
                        separator=str(table_options.get("delimiter") or ","),
                        has_header=bool(table_options.get("has_header", True)),
                        skip_rows=int(table_options.get("skip_rows") or 0),
                    )
                    total_rows = lazy_df.select(pl.len()).collect().item()
            except Exception:
                total_rows = len(df)

        return SchemaResult(
            columns=columns,
            row_count_estimate=total_rows if total_rows is not None else len(df),
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
            if isinstance(exc, (PreviewError, SchemaInferenceError)):
                raise
            raise PreviewError(f"Preview failed: {exc}", connector_id=self.id) from exc

        rows: list[dict[str, Any]] = []
        for row_dict in df.to_dicts():
            cleaned_row = {
                k: (str(v) if v is not None and not isinstance(v, (int, float, bool, str)) else v)
                for k, v in row_dict.items()
            }
            rows.append(cleaned_row)

        return PreviewResult(
            columns=df.columns,
            rows=rows,
            total_rows=len(rows),
            truncated=len(rows) >= limit,
        )

    @staticmethod
    def _map_dtype(dtype: pl.DataType) -> str:
        if dtype.is_integer():
            return "Int64"
        if dtype.is_float():
            return "Float64"
        if dtype == pl.Boolean or dtype.is_(pl.Boolean):
            return "Boolean"
        if dtype == pl.Date or dtype.is_(pl.Date):
            return "Date"
        if dtype.is_temporal():
            return "Datetime"
        return "String"
