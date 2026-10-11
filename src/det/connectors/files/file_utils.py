"""Shared utilities for file-based connectors (local, remote HTTP, FTP, SFTP)."""

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
from det.connectors.contract import ConnectionTestResult, DiscoveredObject
from det.connectors.errors import DiscoveryError, PreviewError, SchemaInferenceError


def resolve_protocol(source_config: dict[str, Any], table_options: dict[str, Any]) -> str:
    """Determine protocol (local, http, https, ftp, sftp) from source or table config."""
    path = str(table_options.get("path") or "").strip()
    base = str(source_config.get("base_path") or "").strip()
    proto = str(source_config.get("protocol") or "").strip().lower()

    if path.startswith(("http://", "https://", "ftp://", "sftp://")):
        return urlparse(path).scheme.lower()
    if base.startswith(("http://", "https://", "ftp://", "sftp://")):
        return urlparse(base).scheme.lower()
    if proto in {"http", "https", "ftp", "sftp", "local"}:
        return proto
    return "local"


def resolve_local_file_paths(
    source_config: dict[str, Any],
    table_options: dict[str, Any],
    default_pattern: str,
) -> list[Path]:
    """Resolve file paths on local filesystem supporting single file, folder, and recursive modes."""
    raw_path = str(table_options.get("path") or "").strip()
    base = str(source_config.get("base_path") or "").strip()

    if not raw_path and not base:
        return []

    target = Path(raw_path)
    if not target.is_absolute() and base:
        target = Path(base) / target
    target = target.expanduser().resolve()

    mode = str(table_options.get("file_selection") or "auto").lower()
    pattern = str(table_options.get("file_pattern") or default_pattern).strip() or default_pattern
    recursive = bool(table_options.get("recursive", False)) or (mode == "recursive")

    if mode == "single":
        return [target]

    if target.is_file():
        if mode in {"auto", "single"}:
            return [target]
        return [target]

    if target.is_dir():
        if recursive or mode == "recursive":
            files = list(target.rglob(pattern))
        else:
            files = list(target.glob(pattern))
        return [f for f in sorted(files) if f.is_file()]

    # If target doesn't exist, return it so caller can raise specific FileNotFoundError
    return [target]


def fetch_remote_bytes(
    source_config: dict[str, Any],
    credentials: dict[str, Any],
    table_options: dict[str, Any],
    connector_id: str,
    max_bytes: int | None = None,
) -> bytes:
    """Fetch raw bytes from HTTP, HTTPS, FTP, or SFTP endpoints."""
    proto = resolve_protocol(source_config, table_options)
    path = str(table_options.get("path") or "").strip()
    base = str(source_config.get("base_path") or "").strip()

    if proto in {"http", "https"}:
        url = path if path.startswith(("http://", "https://")) else f"{base.rstrip('/')}/{path.lstrip('/')}"
        headers: dict[str, str] = {}
        username = source_config.get("username")
        password = credentials.get("password")
        token = credentials.get("token") or source_config.get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        auth = (username, password) if (username and password and not token) else None

        if max_bytes:
            headers["Range"] = f"bytes=0-{max_bytes - 1}"
        try:
            with httpx.Client(follow_redirects=True, timeout=20) as client:
                resp = client.get(url, headers=headers, auth=auth)
                resp.raise_for_status()
                return resp.content
        except Exception as exc:
            raise PreviewError(f"Failed to fetch remote data over HTTP from {url}: {exc}", connector_id=connector_id) from exc

    if proto == "ftp":
        host = source_config.get("host") or urlparse(base).hostname or "localhost"
        port = int(source_config.get("port") or 21)
        user = source_config.get("username") or "anonymous"
        passwd = credentials.get("password") or ""
        try:
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=15)
            ftp.login(user, passwd)
            buffer = io.BytesIO()
            remote_path = path if not base else f"{base.rstrip('/')}/{path.lstrip('/')}"
            ftp.retrbinary(f"RETR {remote_path}", buffer.write, blocksize=8192)
            ftp.quit()
            return buffer.getvalue()
        except Exception as exc:
            raise PreviewError(f"Failed to fetch remote data over FTP: {exc}", connector_id=connector_id) from exc

    if proto == "sftp":
        try:
            import paramiko  # type: ignore
        except ImportError as exc:
            raise PreviewError("SFTP requires the paramiko package ('pip install paramiko').", connector_id=connector_id) from exc

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
            raise PreviewError(f"Failed to fetch remote data over SFTP: {exc}", connector_id=connector_id) from exc

    raise SchemaInferenceError(f"Unsupported remote protocol '{proto}'.", connector_id=connector_id)


def test_connection_endpoint(
    source_config: dict[str, Any],
    credentials: dict[str, Any],
    connector_id: str,
    default_message: str = "Connector ready.",
) -> ConnectionTestResult:
    """Test connectivity for local directories, HTTP, FTP, or SFTP."""
    merged = {**source_config, **credentials}
    proto = str(merged.get("protocol") or "local").lower()
    base = str(merged.get("base_path") or "").strip()

    if proto == "local":
        if not base:
            return ConnectionTestResult(success=True, message=default_message)
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
        token = merged.get("token")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        auth = (username, password) if (username and password and not token) else None
        try:
            with httpx.Client(follow_redirects=True, timeout=10) as client:
                resp = client.head(base, headers=headers, auth=auth)
                if resp.status_code >= 400:
                    resp = client.get(base, headers={**headers, "Range": "bytes=0-10"}, auth=auth)

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


def discover_files_endpoint(
    source_config: dict[str, Any],
    credentials: dict[str, Any],
    default_pattern: str,
    options: dict[str, Any] | None,
    connector_id: str,
) -> list[DiscoveredObject]:
    """Discover files across local filesystem, FTP, or SFTP."""
    proto = str(source_config.get("protocol") or "local").lower()
    base = str(source_config.get("base_path") or "").strip()
    opts = options or {}
    pattern = str(opts.get("file_pattern") or default_pattern).strip() or default_pattern
    recursive = bool(opts.get("recursive", False))

    if proto == "local":
        target = Path(base if base else ".").expanduser().resolve()
        if not target.exists():
            raise DiscoveryError(f"Directory does not exist: {target}", connector_id=connector_id)
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
            raise DiscoveryError(f"FTP discovery error: {exc}", connector_id=connector_id) from exc

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
            raise DiscoveryError(f"SFTP discovery error: {exc}", connector_id=connector_id) from exc

    return []


def map_polars_dtype_to_metadata(name: str, dtype: pl.DataType, is_nullable: bool = True) -> ColumnMetadata:
    """Map Polars DataType to standard ColumnMetadata representation."""
    type_str = str(dtype)
    return ColumnMetadata(name=str(name), type=type_str, nullable=is_nullable)


def format_preview_rows(df: pl.DataFrame) -> list[dict[str, Any]]:
    """Convert Polars DataFrame rows into JSON-safe dictionaries."""
    rows: list[dict[str, Any]] = []
    for row_dict in df.to_dicts():
        clean_row: dict[str, Any] = {}
        for k, v in row_dict.items():
            if v is None or isinstance(v, (int, float, bool, str)):
                clean_row[k] = v
            else:
                clean_row[k] = str(v)
        rows.append(clean_row)
    return rows

