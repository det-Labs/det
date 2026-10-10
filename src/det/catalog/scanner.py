"""det.catalog.scanner - Schema auto-scanner for files and directory datasets."""

from __future__ import annotations

from pathlib import Path

# Python 3.15 lazy imports: modules are deferred until attribute access
import polars as pl
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from det.catalog.models import ColumnMetadata, ScanResult


def _normalize_polars_type(pl_type: pl.DataType) -> str:
    """Normalize a Polars DataType to a standard logical type string.

    Args:
        pl_type: The raw Polars datatype.

    Returns:
        str: Clean logical type string (e.g. 'int64', 'string', 'datetime').
    """
    name = str(pl_type).lower()
    if "string" in name or "utf8" in name:
        return "string"
    if "int64" in name:
        return "int64"
    if "int32" in name:
        return "int32"
    if "int16" in name:
        return "int16"
    if "int8" in name:
        return "int8"
    if "uint" in name:
        return "uint64"
    if "float64" in name:
        return "float64"
    if "float32" in name:
        return "float32"
    if "bool" in name:
        return "boolean"
    if "datetime" in name:
        return "datetime"
    if "date" in name:
        return "date"
    if "decimal" in name:
        return "decimal"
    if "list" in name:
        return "list"
    if "struct" in name:
        return "struct"
    return str(pl_type)


def scan_location(location: str | Path, format_hint: str | None = None) -> ScanResult:
    """Scan a file or directory path and infer schema, format, and row count.

    Args:
        location: Path to a file or directory.
        format_hint: Optional manual format indicator (e.g. 'parquet', 'csv').

    Returns:
        ScanResult: Object containing inferred columns, row count, and sample records.

    Raises:
        FileNotFoundError: If the specified location does not exist.
        ValueError: If the location is not a file/dir or file format is unsupported.
    """
    path = Path(location).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Location does not exist: {location}")

    if path.is_file():
        return _scan_file(path, format_hint)
    elif path.is_dir():
        return _scan_directory(path, format_hint)
    else:
        raise ValueError(f"Path is neither a regular file nor a directory: {location}")


def _scan_file(path: Path, format_hint: str | None = None) -> ScanResult:
    """Inspect and extract schema from a single file."""
    ext = path.suffix.lower().lstrip(".")
    detected_format = (format_hint or ext).lower()

    if detected_format in ("parquet", "pq"):
        try:
            pq_file = pq.ParquetFile(str(path))
            schema = pq_file.schema_arrow
            row_count = pq_file.metadata.num_rows

            columns = [
                ColumnMetadata(
                    name=field.name,
                    type=str(field.type),
                    nullable=field.nullable,
                )
                for field in schema
            ]

            # Sample preview of up to 5 rows
            sample_df = pl.read_parquet(str(path), n_rows=5)
            sample_data = sample_df.to_dicts()

            return ScanResult(
                location=str(path),
                format="parquet",
                columns=columns,
                row_count=row_count,
                sample_preview=sample_data,
            )
        except (OSError, RuntimeError):
            # Fallback to Polars lazy scan
            df = pl.scan_parquet(str(path)).collect().head(5)
            columns = [
                ColumnMetadata(name=col, type=_normalize_polars_type(df.schema[col]))
                for col in df.columns
            ]
            return ScanResult(
                location=str(path),
                format="parquet",
                columns=columns,
                sample_preview=df.to_dicts(),
            )

    elif detected_format in ("csv", "tsv", "txt"):
        separator = "\t" if detected_format == "tsv" or ext == "tsv" else ","
        df = pl.read_csv(str(path), separator=separator, n_rows=100, ignore_errors=True)
        columns = [
            ColumnMetadata(name=col, type=_normalize_polars_type(df.schema[col]))
            for col in df.columns
        ]

        # Calculate exact row count safely
        try:
            total_rows = (
                pl.scan_csv(str(path), separator=separator)
                .select(pl.len())
                .collect()
                .item()
            )
        except (pl.exceptions.PolarsError, OSError):
            total_rows = len(df)

        return ScanResult(
            location=str(path),
            format="csv" if separator == "," else "tsv",
            columns=columns,
            row_count=total_rows,
            sample_preview=df.head(5).to_dicts(),
        )

    elif detected_format in ("json", "ndjson", "jsonl"):
        try:
            df = pl.read_ndjson(str(path), n_rows=100)
            columns = [
                ColumnMetadata(name=col, type=_normalize_polars_type(df.schema[col]))
                for col in df.columns
            ]
            return ScanResult(
                location=str(path),
                format="ndjson",
                columns=columns,
                row_count=len(df),
                sample_preview=df.head(5).to_dicts(),
            )
        except (pl.exceptions.PolarsError, ValueError):
            # Fallback to standard JSON
            df = pl.read_json(str(path))
            columns = [
                ColumnMetadata(name=col, type=_normalize_polars_type(df.schema[col]))
                for col in df.columns
            ]
            return ScanResult(
                location=str(path),
                format="json",
                columns=columns,
                row_count=len(df),
                sample_preview=df.head(5).to_dicts(),
            )

    elif detected_format in ("xlsx", "xls"):
        df = pl.read_excel(str(path), read_options={"n_rows": 100})
        columns = [
            ColumnMetadata(name=col, type=_normalize_polars_type(df.schema[col]))
            for col in df.columns
        ]
        return ScanResult(
            location=str(path),
            format="excel",
            columns=columns,
            row_count=len(df),
            sample_preview=df.head(5).to_dicts(),
        )

    else:
        raise ValueError(f"Unsupported file format: .{ext} for file '{path.name}'")


def _scan_directory(dir_path: Path, format_hint: str | None = None) -> ScanResult:
    """Inspect and extract schema from a directory dataset."""
    parquet_files = list(dir_path.rglob("*.parquet")) + list(dir_path.rglob("*.pq"))
    if parquet_files or format_hint == "parquet":
        source = [str(f) for f in parquet_files] if parquet_files else str(dir_path)
        dataset = ds.dataset(source, format="parquet")
        schema = dataset.schema
        columns = [
            ColumnMetadata(
                name=field.name,
                type=str(field.type),
                nullable=field.nullable,
            )
            for field in schema
        ]
        sample_data: list[dict] = []
        try:
            parquet_glob = f"{dir_path.as_posix()}/**/*.parquet"
            sample_df = pl.scan_parquet(parquet_glob).collect().head(5)
            sample_data = sample_df.to_dicts()
        except (pl.exceptions.PolarsError, OSError, RuntimeError, ValueError):
            if parquet_files:
                sample_data = pl.read_parquet(str(parquet_files[0]), n_rows=5).to_dicts()

        return ScanResult(
            location=str(dir_path),
            format="parquet (directory)",
            columns=columns,
            sample_preview=sample_data,
        )

    csv_files = list(dir_path.rglob("*.csv"))
    if csv_files or format_hint == "csv":
        sample_file = csv_files[0] if csv_files else None
        if sample_file:
            df = pl.read_csv(str(sample_file), n_rows=100)
            columns = [
                ColumnMetadata(name=col, type=_normalize_polars_type(df.schema[col]))
                for col in df.columns
            ]
            return ScanResult(
                location=str(dir_path),
                format="csv (directory)",
                columns=columns,
                sample_preview=df.head(5).to_dicts(),
            )

    json_files = (
        list(dir_path.rglob("*.ndjson"))
        + list(dir_path.rglob("*.jsonl"))
        + list(dir_path.rglob("*.json"))
    )
    if json_files or format_hint in ("json", "ndjson", "jsonl"):
        sample_file = json_files[0] if json_files else None
        if sample_file:
            try:
                df = pl.read_ndjson(str(sample_file), n_rows=100)
                fmt = "ndjson (directory)"
            except (pl.exceptions.PolarsError, OSError, ValueError):
                df = pl.read_json(str(sample_file))
                fmt = "json (directory)"

            columns = [
                ColumnMetadata(name=col, type=_normalize_polars_type(df.schema[col]))
                for col in df.columns
            ]
            return ScanResult(
                location=str(dir_path),
                format=fmt,
                columns=columns,
                sample_preview=df.head(5).to_dicts(),
            )

    raise ValueError(f"Could not automatically detect dataset files inside directory: '{dir_path}'")
