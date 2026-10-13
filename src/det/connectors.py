"""Built-in file connectors and the connector extension contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pyarrow as pa
from datafusion import DataFrame, SessionContext


@dataclass(frozen=True)
class ConnectorField:
    """A connector-owned field definition rendered by the shared UI."""

    name: str
    label: str
    section: Literal["connection", "read", "write"]
    kind: Literal["text", "number", "boolean", "select", "list", "textarea"]
    description: str = ""
    default: Any = None
    choices: tuple[str, ...] = ()
    required: bool = False
    placeholder: str = ""


class ConnectorReader(Protocol):
    def __call__(
        self,
        context: SessionContext,
        options: dict[str, Any],
        workspace: Path,
    ) -> DataFrame: ...


@dataclass(frozen=True)
class ConnectorDefinition:
    """Metadata and optional reader implementation contributed by a plugin."""

    key: str
    guid: str
    label: str
    description: str
    fields: tuple[ConnectorField, ...]
    read: ConnectorReader | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        try:
            canonical_guid = str(UUID(self.guid))
        except ValueError as error:
            raise ValueError(f"Connector {self.key!r} must have a GUID.") from error
        if not self.key or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in self.key):
            raise ValueError("Connector keys must use lowercase letters, digits, '_' or '-'.")
        object.__setattr__(self, "guid", canonical_guid)


CSV_CONNECTOR = ConnectorDefinition(
    key="csv",
    guid=str(uuid5(NAMESPACE_URL, "https://det.dev/connectors/csv")),
    label="CSV",
    description="Delimited text files scanned lazily by Apache DataFusion.",
    fields=(
        ConnectorField(
            "path", "File or folder path", "connection", "text",
            "Absolute path or workspace-relative path. A folder scans matching files.",
            required=True, placeholder="data/sales",
        ),
        ConnectorField(
            "file_pattern", "File name filter", "connection", "text",
            "Glob pattern applied inside a folder. Use ** for nested folders.",
            default="*.csv", placeholder="sales-*.csv",
        ),
        ConnectorField("include_subfolders", "Include nested folders", "connection", "boolean",
                       "Include matching files from nested folders.", True),
        ConnectorField("paths", "Additional file paths", "connection", "list",
                       "Optional list of additional files with the same schema."),
        ConnectorField(
            "exclude_patterns", "Exclude patterns", "connection", "list",
            "Optional glob patterns to omit from the selected files.",
        ),
        ConnectorField(
            "has_header", "First row contains column names", "read", "boolean",
            "Treat the first record in each file as column headers.", True,
        ),
        ConnectorField("delimiter", "Delimiter", "read", "text", "Single ASCII character.", ","),
        ConnectorField("quote", "Text qualifier", "read", "text", "Quote character for fields.", '"'),
        ConnectorField("escape", "Escape character", "read", "text", "Optional escape character."),
        ConnectorField("terminator", "Line terminator", "read", "text", "Optional record terminator."),
        ConnectorField("comment", "Comment character", "read", "text", "Ignore lines beginning with this character."),
        ConnectorField("newlines_in_values", "Allow newlines in values", "read", "boolean",
                       "Supports embedded newlines; may reduce parallel scan performance.", False),
        ConnectorField("schema_infer_max_records", "Schema inference rows", "read", "number",
                       "Maximum records used when DataFusion infers a schema.", 1000),
        ConnectorField("file_compression_type", "File compression", "read", "select",
                       "Compression of input files.", "", ("", "gzip", "bz2", "xz", "zstd")),
        ConnectorField("null_regex", "Null-value pattern", "read", "text",
                       "Optional regular expression for null values."),
        ConnectorField("truncated_rows", "Allow short rows", "read", "boolean",
                       "Fill missing fields in short records with nulls.", False),
        ConnectorField("output_path", "Output file or folder", "write", "text",
                       "Destination path for a pipeline stage.", placeholder="output/result.csv"),
        ConnectorField("with_header", "Write column headers", "write", "boolean",
                       "Include a header row in CSV output.", True),
        ConnectorField("output_file_pattern", "Output file name", "write", "text",
                       "Target name when a stage writes a single CSV file.", default="part-*.csv"),
        ConnectorField("partition_by", "Partition output by columns", "write", "list",
                       "Write separate partition folders for these columns."),
        ConnectorField("single_file_output", "Write one output file", "write", "boolean",
                       "Disable DataFusion's normal multi-file output for this write.", False),
        ConnectorField("sort_by", "Sort output by expressions", "write", "textarea",
                       "Optional comma-separated DataFusion sort expressions."),
        ConnectorField("insert_operation", "DataFusion insert operation", "write", "select",
                       "Provider insert behavior when supported by the destination.",
                       "", ("", "APPEND", "OVERWRITE", "REPLACE")),
        ConnectorField("write_mode", "If output exists", "write", "select",
                       "Whether a destination replaces existing data or adds output.", "overwrite",
                       ("overwrite", "append")),
    ),
    read=None,
)

PARQUET_CONNECTOR = ConnectorDefinition(
    key="parquet",
    guid=str(uuid5(NAMESPACE_URL, "https://det.dev/connectors/parquet")),
    label="Parquet",
    description="Columnar files scanned by Apache DataFusion with Parquet pruning.",
    fields=(
        ConnectorField(
            "path", "File or folder path", "connection", "text",
            "Absolute path or workspace-relative path. A folder scans matching files.",
            required=True, placeholder="data/events",
        ),
        ConnectorField("file_pattern", "File name filter", "connection", "text",
                       "Glob pattern applied inside a folder. Use ** for nested folders.",
                       default="*.parquet", placeholder="events-*.parquet"),
        ConnectorField("include_subfolders", "Include nested folders", "connection", "boolean",
                       "Include matching files from nested folders.", True),
        ConnectorField("paths", "Additional file paths", "connection", "list",
                       "Optional list of additional files with the same schema."),
        ConnectorField("exclude_patterns", "Exclude patterns", "connection", "list",
                       "Optional glob patterns to omit from the selected files."),
        ConnectorField("parquet_pruning", "Enable Parquet pruning", "read", "boolean",
                       "Use query predicates to skip irrelevant row groups.", True),
        ConnectorField("skip_metadata", "Skip embedded Arrow metadata", "read", "boolean",
                       "Avoid embedded metadata that can cause schema conflicts.", True),
        ConnectorField("partition_columns", "Hive partition columns", "read", "textarea",
                       "Optional comma-separated folder partition columns (column:type)."),
        ConnectorField("output_path", "Output file or folder", "write", "text",
                       "Destination path for a pipeline stage.", placeholder="output/result.parquet"),
        ConnectorField("output_file_pattern", "Output file name", "write", "text",
                       "Target name when a stage writes a single Parquet file.", default="part-*.parquet"),
        ConnectorField("partition_by", "Partition output by columns", "write", "list",
                       "Write separate partition folders for these columns."),
        ConnectorField("single_file_output", "Write one output file", "write", "boolean",
                       "Disable DataFusion's normal multi-file output for this write.", False),
        ConnectorField("sort_by", "Sort output by expressions", "write", "textarea",
                       "Optional comma-separated DataFusion sort expressions."),
        ConnectorField("insert_operation", "DataFusion insert operation", "write", "select",
                       "Provider insert behavior when supported by the destination.",
                       "", ("", "APPEND", "OVERWRITE", "REPLACE")),
        ConnectorField("write_mode", "If output exists", "write", "select",
                       "Whether a destination replaces existing data or adds output.", "overwrite",
                       ("overwrite", "append")),
        ConnectorField("compression", "Compression", "write", "select",
                       "Parquet compression codec.", "zstd",
                       ("uncompressed", "snappy", "gzip", "brotli", "lz4", "lz4_raw", "zstd")),
        ConnectorField("compression_level", "Compression level", "write", "number",
                       "Optional codec level; Zstandard supports levels 1-22."),
        ConnectorField("writer_version", "Writer version", "write", "select",
                       "Parquet writer format version.", "1.0", ("1.0", "2.0")),
        ConnectorField("data_pagesize_limit", "Data page size limit", "write", "number",
                       "Best-effort maximum data page size in bytes."),
        ConnectorField("write_batch_size", "Write batch size", "write", "number",
                       "Target write batch size in bytes."),
        ConnectorField("skip_arrow_metadata", "Skip Arrow schema metadata", "write", "boolean",
                       "Do not encode Arrow metadata in the Parquet file.", False),
        ConnectorField("dictionary_enabled", "Dictionary encoding", "write", "boolean",
                       "Enable dictionary encoding when writing.", True),
        ConnectorField("dictionary_page_size_limit", "Dictionary page size limit", "write", "number",
                       "Best-effort maximum dictionary page size in bytes."),
        ConnectorField("statistics_enabled", "Statistics", "write", "select",
                       "Write Parquet statistics.", "chunk", ("none", "chunk", "page")),
        ConnectorField("max_row_group_size", "Maximum row group size", "write", "number",
                       "Maximum rows in a row group; larger groups require more memory."),
        ConnectorField("created_by", "Created by", "write", "text",
                       "Value stored in Parquet file metadata."),
        ConnectorField("column_index_truncate_length", "Column index truncate length", "write", "number"),
        ConnectorField("statistics_truncate_length", "Statistics truncate length", "write", "number"),
        ConnectorField("data_page_row_count_limit", "Data page row count limit", "write", "number"),
        ConnectorField("bloom_filter_on_write", "Write Bloom filters", "write", "boolean", default=False),
        ConnectorField("bloom_filter_fpp", "Bloom filter false positive probability", "write", "number"),
        ConnectorField("bloom_filter_ndv", "Bloom filter distinct-value estimate", "write", "number"),
        ConnectorField("encoding", "Default encoding", "write", "select",
                       "Default encoding for output columns.", "plain",
                       ("plain", "plain_dictionary", "rle", "bit_packed", "delta_binary_packed",
                        "delta_length_byte_array", "delta_byte_array", "rle_dictionary",
                        "byte_stream_split")),
        ConnectorField("allow_single_file_parallelism", "Parallelize single-file output", "write", "boolean",
                       "Parallelize serialization when writing one file.", False),
        ConnectorField("maximum_parallel_row_group_writers", "Parallel row-group writers", "write", "number",
                       "More writers may improve throughput at additional memory cost."),
        ConnectorField("maximum_buffered_record_batches_per_stream", "Buffered batches per stream", "write", "number",
                       "Increase with parallel writers when memory permits."),
        ConnectorField("column_specific_options", "Per-column Parquet options (JSON)", "write", "textarea",
                       "Optional JSON object mapping column names to DataFusion ParquetColumnOptions."),
    ),
    read=None,
)

EXCEL_CONNECTOR = ConnectorDefinition(
    key="excel",
    guid=str(uuid5(NAMESPACE_URL, "https://det.dev/connectors/excel")),
    label="Excel",
    description="Excel spreadsheets (.xlsx, .xlsm, .xltx, .xltm) scanned via openpyxl and Apache DataFusion.",
    fields=(
        ConnectorField(
            "path", "File or folder path", "connection", "text",
            "Absolute path or workspace-relative path. A folder scans matching files.",
            required=True, placeholder="data/sheets",
        ),
        ConnectorField("file_pattern", "File name filter", "connection", "text",
                       "Glob pattern applied inside a folder. Use ** for nested folders.",
                       default="*.xlsx", placeholder="sales-*.xlsx"),
        ConnectorField("include_subfolders", "Include nested folders", "connection", "boolean",
                       "Include matching files from nested folders.", True),
        ConnectorField("paths", "Additional file paths", "connection", "list",
                       "Optional list of additional files with the same schema."),
        ConnectorField("exclude_patterns", "Exclude patterns", "connection", "list",
                       "Optional glob patterns to omit from the selected files."),
        ConnectorField("sheet_name", "Sheet name", "read", "text",
                       "Name of the sheet to read. Leave blank for the active or first sheet."),
        ConnectorField("has_header", "First row contains column names", "read", "boolean",
                       "Treat the first row of data as column headers.", True),
        ConnectorField("header_row", "Header row number", "read", "number",
                       "1-based row number containing column names.", 1),
        ConnectorField("data_start_row", "Data start row number", "read", "number",
                       "1-based row number where table data starts.", 2),
        ConnectorField("output_path", "Output file or folder", "write", "text",
                       "Destination path for an Excel export.", placeholder="output/result.xlsx"),
        ConnectorField("sheet_name_write", "Destination sheet name", "write", "text",
                       "Sheet name in the output Excel workbook.", default="Sheet1"),
        ConnectorField("write_mode", "If output exists", "write", "select",
                       "Whether a destination replaces existing data or adds output.", "overwrite",
                       ("overwrite", "append")),
    ),
    read=None,
)

JSON_CONNECTOR = ConnectorDefinition(
    key="json",
    guid=str(uuid5(NAMESPACE_URL, "https://det.dev/connectors/json")),
    label="JSON",
    description="Line-delimited (NDJSON/JSONL) or array JSON files scanned by Apache DataFusion.",
    fields=(
        ConnectorField(
            "path", "File or folder path", "connection", "text",
            "Absolute path or workspace-relative path. A folder scans matching files.",
            required=True, placeholder="data/events",
        ),
        ConnectorField("file_pattern", "File name filter", "connection", "text",
                       "Glob pattern applied inside a folder. Use ** for nested folders.",
                       default="*.json", placeholder="events-*.json"),
        ConnectorField("include_subfolders", "Include nested folders", "connection", "boolean",
                       "Include matching files from nested folders.", True),
        ConnectorField("paths", "Additional file paths", "connection", "list",
                       "Optional list of additional files with the same schema."),
        ConnectorField("exclude_patterns", "Exclude patterns", "connection", "list",
                       "Optional glob patterns to omit from the selected files."),
        ConnectorField("json_format", "JSON format", "read", "select",
                       "Format of the JSON file: auto-detect, line-delimited (NDJSON/JSONL), or JSON array.",
                       "auto", ("auto", "lines", "array")),
        ConnectorField("schema_infer_max_records", "Schema inference rows", "read", "number",
                       "Maximum records used when DataFusion infers a schema.", 1000),
        ConnectorField("file_compression_type", "File compression", "read", "select",
                       "Compression of input files.", "", ("", "gzip", "bz2", "xz", "zstd")),
        ConnectorField("output_path", "Output file or folder", "write", "text",
                       "Destination path for JSON output.", placeholder="output/result.json"),
        ConnectorField("output_format", "Output format", "write", "select",
                       "Output JSON format.", "lines", ("lines", "array")),
        ConnectorField("write_mode", "If output exists", "write", "select",
                       "Whether a destination replaces existing data or adds output.", "overwrite",
                       ("overwrite", "append")),
    ),
    read=None,
)

XML_CONNECTOR = ConnectorDefinition(
    key="xml",
    guid=str(uuid5(NAMESPACE_URL, "https://det.dev/connectors/xml")),
    label="XML",
    description="XML data files scanned into Apache DataFusion.",
    fields=(
        ConnectorField(
            "path", "File or folder path", "connection", "text",
            "Absolute path or workspace-relative path. A folder scans matching files.",
            required=True, placeholder="data/feed.xml",
        ),
        ConnectorField("file_pattern", "File name filter", "connection", "text",
                       "Glob pattern applied inside a folder. Use ** for nested folders.",
                       default="*.xml", placeholder="feed-*.xml"),
        ConnectorField("include_subfolders", "Include nested folders", "connection", "boolean",
                       "Include matching files from nested folders.", True),
        ConnectorField("paths", "Additional file paths", "connection", "list",
                       "Optional list of additional files with the same schema."),
        ConnectorField("exclude_patterns", "Exclude patterns", "connection", "list",
                       "Optional glob patterns to omit from the selected files."),
        ConnectorField("row_tag", "Row element tag", "read", "text",
                       "XML element tag representing each row. Leave blank to auto-detect child elements.",
                       placeholder="record"),
        ConnectorField("flatten_attributes", "Include XML attributes", "read", "boolean",
                       "Include XML element attributes as row columns.", True),
        ConnectorField("output_path", "Output file or folder", "write", "text",
                       "Destination path for XML output.", placeholder="output/result.xml"),
        ConnectorField("root_tag", "Root element tag", "write", "text",
                       "Root XML element tag for output.", default="records"),
        ConnectorField("row_tag_write", "Row element tag", "write", "text",
                       "Row XML element tag for output.", default="record"),
        ConnectorField("write_mode", "If output exists", "write", "select",
                       "Whether a destination replaces existing data or adds output.", "overwrite",
                       ("overwrite", "append")),
    ),
    read=None,
)

DELTA_CONNECTOR = ConnectorDefinition(
    key="delta",
    guid=str(uuid5(NAMESPACE_URL, "https://det.dev/connectors/delta")),
    label="Delta Lake",
    description="Delta Lake ACID table format scanned lazily by Apache DataFusion.",
    fields=(
        ConnectorField(
            "path", "Delta table folder path", "connection", "text",
            "Absolute or workspace-relative path to the Delta table root directory.",
            required=True, placeholder="data/delta_orders",
        ),
        ConnectorField(
            "version", "Snapshot version", "read", "number",
            "Optional specific version number for time-travel queries.",
        ),
        ConnectorField(
            "datetime", "As-of timestamp", "read", "text",
            "Optional ISO-8601 timestamp for time-travel queries (e.g. 2026-10-12T00:00:00Z).",
            placeholder="2026-10-12T00:00:00Z",
        ),
        ConnectorField(
            "output_path", "Output folder path", "write", "text",
            "Destination folder path for Delta Lake table output.", placeholder="output/delta_result",
        ),
        ConnectorField(
            "mode", "Write mode", "write", "select",
            "Delta Lake write mode.", "overwrite", ("overwrite", "append", "error", "ignore"),
        ),
        ConnectorField(
            "partition_by", "Partition columns", "write", "list",
            "Optional list of partition columns for Delta output.",
        ),
    ),
    read=None,
)

ICEBERG_CONNECTOR = ConnectorDefinition(
    key="iceberg",
    guid=str(uuid5(NAMESPACE_URL, "https://det.dev/connectors/iceberg")),
    label="Apache Iceberg",
    description="Apache Iceberg open table format scanned into Apache DataFusion.",
    fields=(
        ConnectorField(
            "path", "Iceberg table folder path", "connection", "text",
            "Absolute or workspace-relative path to the Iceberg table root directory.",
            required=True, placeholder="data/iceberg_orders",
        ),
        ConnectorField(
            "snapshot_id", "Snapshot ID", "read", "number",
            "Optional specific snapshot ID for time-travel queries.",
        ),
        ConnectorField(
            "as_of_timestamp", "As-of timestamp (ms)", "read", "number",
            "Optional snapshot timestamp in milliseconds for time-travel queries.",
        ),
        ConnectorField(
            "output_path", "Output folder path", "write", "text",
            "Destination folder path for Iceberg table output.", placeholder="output/iceberg_result",
        ),
        ConnectorField(
            "write_mode", "If output exists", "write", "select",
            "Whether to replace existing data or append.", "overwrite", ("overwrite", "append"),
        ),
    ),
    read=None,
)


def connector_definitions() -> list[ConnectorDefinition]:
    """Return core connectors followed by installed extension connectors."""
    definitions = [
        CSV_CONNECTOR,
        PARQUET_CONNECTOR,
        EXCEL_CONNECTOR,
        JSON_CONNECTOR,
        XML_CONNECTOR,
        DELTA_CONNECTOR,
        ICEBERG_CONNECTOR,
    ]
    known_ids = {item.guid for item in definitions}
    known_keys = {item.key for item in definitions}
    for entry_point in entry_points(group="det.connectors"):
        loaded = entry_point.load()
        definition = loaded() if callable(loaded) and not isinstance(loaded, ConnectorDefinition) else loaded
        if not isinstance(definition, ConnectorDefinition):
            raise TypeError(
                f"Connector extension {entry_point.name!r} must provide a ConnectorDefinition."
            )
        if definition.guid in known_ids:
            raise ValueError(f"Duplicate connector GUID: {definition.guid}")
        if definition.key in known_keys:
            raise ValueError(f"Duplicate connector key: {definition.key}")
        known_ids.add(definition.guid)
        known_keys.add(definition.key)
        definitions.append(definition)
    return definitions


def connector_metadata() -> list[dict[str, Any]]:
    """Serialize connector definitions for the generic connection editor."""
    return [
        {
            "id": connector.guid,
            "key": connector.key,
            "label": connector.label,
            "description": connector.description,
            "fields": [asdict(field) for field in connector.fields],
        }
        for connector in connector_definitions()
    ]


def _matched_paths(options: dict[str, Any], workspace: Path) -> list[Path]:
    candidates: list[Path] = []
    raw_paths = [options.get("path", "")]
    extra_paths = options.get("paths") or []
    if isinstance(extra_paths, str):
        extra_paths = [line.strip() for line in extra_paths.splitlines() if line.strip()]
    raw_paths.extend(extra_paths)
    raw_paths = [value.strip() for value in raw_paths if isinstance(value, str) and value.strip()]
    if not raw_paths:
        raise ValueError("A file or folder path is required.")
    for raw_path in raw_paths:
        base = Path(raw_path).expanduser()
        if not base.is_absolute():
            base = workspace / base
        base = base.resolve()
        if base.is_file():
            candidates.append(base)
        elif base.is_dir():
            pattern = options.get("file_pattern") or "*"
            if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
                raise ValueError("File name filters must stay within the selected folder.")
            if options.get("include_subfolders", True) and not pattern.startswith("**/"):
                pattern = f"**/{pattern}"
            candidates.extend(
                path.resolve() for path in base.glob(pattern) if path.is_file()
            )
        else:
            raise FileNotFoundError(f"Configured file or folder does not exist: {base}")
    excluded = options.get("exclude_patterns") or []
    if isinstance(excluded, str):
        excluded = [line.strip() for line in excluded.splitlines() if line.strip()]
    if excluded:
        candidates = [
            path for path in candidates
            if not any(path.match(pattern) for pattern in excluded)
        ]
    candidates = sorted(set(candidates))
    if not candidates:
        raise FileNotFoundError("No files match the configured paths and file-name filter.")
    return candidates


def _arrow_type_from_string(type_name: str) -> pa.DataType:
    """Safely map type names or aliases to PyArrow DataType."""
    try:
        return pa.type_for_alias(type_name)
    except (ValueError, KeyError):
        pass
    type_lower = type_name.lower().strip()
    mapping = {
        "int": pa.int64(),
        "integer": pa.int64(),
        "bigint": pa.int64(),
        "int64": pa.int64(),
        "int32": pa.int32(),
        "smallint": pa.int16(),
        "tinyint": pa.int8(),
        "float": pa.float32(),
        "float32": pa.float32(),
        "double": pa.float64(),
        "float64": pa.float64(),
        "str": pa.string(),
        "string": pa.string(),
        "text": pa.string(),
        "varchar": pa.string(),
        "bool": pa.bool_(),
        "boolean": pa.bool_(),
        "date": pa.date32(),
        "date32": pa.date32(),
        "timestamp": pa.timestamp("us"),
        "datetime": pa.timestamp("us"),
    }
    return mapping.get(type_lower, pa.string())


def _build_arrow_schema(saved_columns: list[dict[str, Any]] | None) -> pa.Schema | None:
    """Build a PyArrow schema from saved catalog columns if available."""
    if not saved_columns:
        return None
    return pa.schema(
        [
            pa.field(
                column["name"],
                _arrow_type_from_string(column["data_type"]),
                nullable=column.get("nullable", True),
            )
            for column in saved_columns
        ]
    )


def _apply_saved_schema(table: pa.Table, schema: pa.Schema | None) -> pa.Table:
    """Cast or align an Arrow Table to a saved schema."""
    if schema is None or len(table) == 0:
        return table
    new_columns = []
    new_names = []
    for field in schema:
        if field.name in table.column_names:
            col = table[field.name]
            try:
                col = col.cast(field.type)
            except Exception:
                pass
            new_columns.append(col)
            new_names.append(field.name)
        else:
            null_arr = pa.nulls(len(table), type=field.type)
            new_columns.append(null_arr)
            new_names.append(field.name)
    for name in table.column_names:
        if name not in new_names:
            new_columns.append(table[name])
            new_names.append(name)
    return pa.Table.from_arrays(new_columns, names=new_names)


def _scan_csv(
    context: SessionContext,
    paths: list[Path],
    options: dict[str, Any],
    schema: pa.Schema | None,
) -> DataFrame:
    from datafusion.options import CsvReadOptions

    raw_delim = options.get("delimiter") or ","
    if raw_delim == "\\t":
        raw_delim = "\t"
    read_options = CsvReadOptions(
        has_header=bool(options.get("has_header", True)),
        delimiter=raw_delim,
        quote=options.get("quote") or '"',
        escape=options.get("escape") or None,
        terminator=options.get("terminator") or None,
        comment=options.get("comment") or None,
        newlines_in_values=bool(options.get("newlines_in_values", False)),
        schema_infer_max_records=int(options.get("schema_infer_max_records", 1000)),
        schema=schema,
        file_compression_type=options.get("file_compression_type") or "",
        null_regex=options.get("null_regex") or None,
        truncated_rows=bool(options.get("truncated_rows", False)),
    )
    return context.read_csv([str(path) for path in paths], options=read_options)


def _scan_parquet(
    context: SessionContext,
    paths: list[Path],
    options: dict[str, Any],
    schema: pa.Schema | None,
) -> DataFrame:
    partition_columns: list[tuple[str, str]] = []
    for item in (options.get("partition_columns") or "").split(","):
        if item.strip():
            name, separator, data_type = item.strip().partition(":")
            if not separator or data_type not in {"string", "int"}:
                raise ValueError("Hive partition columns must use column:string or column:int.")
            partition_columns.append((name.strip(), data_type))
    frames = [
        context.read_parquet(
            str(path),
            parquet_pruning=bool(options.get("parquet_pruning", True)),
            skip_metadata=bool(options.get("skip_metadata", True)),
            table_partition_cols=partition_columns,
            schema=schema,
        )
        for path in paths
    ]
    if len(frames) == 1:
        return frames[0]
    table_names = [f"det_parquet_{index}_{uuid4().hex}" for index, path in enumerate(paths)]
    for name, dataframe in zip(table_names, frames, strict=True):
        context.register_view(name, dataframe)
    return context.sql(" UNION ALL ".join(f"SELECT * FROM {name}" for name in table_names))


def _scan_json(
    context: SessionContext,
    paths: list[Path],
    options: dict[str, Any],
    schema: pa.Schema | None,
) -> DataFrame:
    import json as pyjson

    json_format = (options.get("json_format") or "auto").lower().strip()
    if json_format == "auto":
        detected = "lines"
        with open(paths[0], "r", encoding="utf-8", errors="ignore") as file:
            for line in file:
                stripped = line.strip()
                if stripped:
                    if stripped.startswith("["):
                        detected = "array"
                    break
        json_format = detected

    if json_format == "lines":
        max_records = int(options.get("schema_infer_max_records", 1000))
        compression = options.get("file_compression_type") or ""
        frames = [
            context.read_json(
                str(path),
                schema=schema,
                schema_infer_max_records=max_records,
                file_extension=path.suffix or ".json",
                file_compression_type=compression,
            )
            for path in paths
        ]
        if len(frames) == 1:
            return frames[0]
        table_names = [f"det_json_{index}_{uuid4().hex}" for index, path in enumerate(paths)]
        for name, dataframe in zip(table_names, frames, strict=True):
            context.register_view(name, dataframe)
        return context.sql(" UNION ALL ".join(f"SELECT * FROM {name}" for name in table_names))

    all_records: list[dict[str, Any]] = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as file:
            data = pyjson.load(file)
            if isinstance(data, list):
                all_records.extend(data)
            elif isinstance(data, dict):
                all_records.append(data)
    if not all_records:
        raise ValueError(f"No JSON records found in {paths}")
    raw_table = pa.Table.from_pylist(all_records)
    table = _apply_saved_schema(raw_table, schema)
    return context.from_arrow(table)


def _scan_excel(
    context: SessionContext,
    paths: list[Path],
    options: dict[str, Any],
    schema: pa.Schema | None,
) -> DataFrame:
    sheet_name = (options.get("sheet_name") or "").strip()
    has_header = bool(options.get("has_header", True))
    header_row_idx = max(1, int(options.get("header_row", 1))) - 1
    data_start_row_idx = max(1, int(options.get("data_start_row", 2))) - 1

    # High-performance path: fastexcel (Rust calamine engine) -> zero-copy PyArrow
    try:
        import fastexcel

        arrow_tables: list[pa.Table] = []
        for path in paths:
            excel = fastexcel.read_excel(str(path))
            target_sheet: str | int = 0
            if sheet_name:
                if sheet_name in excel.sheet_names:
                    target_sheet = sheet_name
                else:
                    raise ValueError(f"Sheet {sheet_name!r} not found in {path.name}. Available: {excel.sheet_names}")
            skip_after_header = max(0, data_start_row_idx - header_row_idx - 1)
            sheet = excel.load_sheet(
                target_sheet,
                header_row=header_row_idx if has_header else None,
                skip_rows=skip_after_header if has_header and skip_after_header > 0 else None,
            )
            batch_or_table = sheet.to_arrow()
            if isinstance(batch_or_table, pa.RecordBatch):
                t = pa.Table.from_batches([batch_or_table])
            else:
                t = batch_or_table
            arrow_tables.append(t)

        if arrow_tables:
            if len(arrow_tables) == 1:
                combined_table = arrow_tables[0]
            else:
                try:
                    combined_table = pa.concat_tables(arrow_tables)
                except Exception:
                    rows = []
                    for t in arrow_tables:
                        rows.extend(t.to_pylist())
                    combined_table = pa.Table.from_pylist(rows)
            table = _apply_saved_schema(combined_table, schema)
            return context.from_arrow(table)
    except Exception:
        # Fall back to openpyxl for maximum compatibility
        pass

    import openpyxl

    all_rows: list[dict[str, Any]] = []
    for path in paths:
        workbook = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
        try:
            if sheet_name and sheet_name in workbook.sheetnames:
                worksheet = workbook[sheet_name]
            else:
                worksheet = workbook.active
            rows_iter = list(worksheet.iter_rows(values_only=True))
            if not rows_iter:
                continue
            if has_header:
                if header_row_idx >= len(rows_iter):
                    continue
                header_cells = rows_iter[header_row_idx]
                headers = [
                    str(cell).strip() if cell is not None and str(cell).strip() else f"col_{idx + 1}"
                    for idx, cell in enumerate(header_cells)
                ]
                data_rows = rows_iter[data_start_row_idx:]
            else:
                headers = [f"col_{idx + 1}" for idx in range(len(rows_iter[0]))]
                data_rows = rows_iter

            for row in data_rows:
                row_dict = {
                    headers[idx]: row[idx] if idx < len(row) else None
                    for idx in range(len(headers))
                }
                all_rows.append(row_dict)
        finally:
            workbook.close()

    if not all_rows:
        raise ValueError(f"No rows found in Excel sheet for {paths}")
    raw_table = pa.Table.from_pylist(all_rows)
    table = _apply_saved_schema(raw_table, schema)
    return context.from_arrow(table)


def _scan_xml(
    context: SessionContext,
    paths: list[Path],
    options: dict[str, Any],
    schema: pa.Schema | None,
) -> DataFrame:
    import xml.etree.ElementTree as ET

    row_tag = (options.get("row_tag") or "").strip()
    flatten_attribs = bool(options.get("flatten_attributes", True))

    all_rows: list[dict[str, Any]] = []
    for path in paths:
        tree = ET.parse(str(path))
        root = tree.getroot()
        if row_tag:
            elements = root.findall(f".//{row_tag}")
        else:
            elements = list(root)
        for element in elements:
            row: dict[str, Any] = {}
            if flatten_attribs:
                row.update(element.attrib)
            for child in element:
                tag = child.tag
                if "}" in tag:
                    tag = tag.split("}", 1)[1]
                val = child.text.strip() if child.text else None
                row[tag] = val
            all_rows.append(row)

    if not all_rows:
        raise ValueError(f"No XML elements matching '{row_tag or 'root children'}' found in {paths}")
    raw_table = pa.Table.from_pylist(all_rows)
    table = _apply_saved_schema(raw_table, schema)
    return context.from_arrow(table)


def _resolve_table_directory(options: dict[str, Any], workspace: Path) -> Path:
    raw_path = options.get("path", "")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("A table folder path is required.")
    table_dir = Path(raw_path.strip()).expanduser()
    if not table_dir.is_absolute():
        table_dir = workspace / table_dir
    table_dir = table_dir.resolve()
    if not table_dir.exists():
        raise FileNotFoundError(f"Configured table path does not exist: {table_dir}")
    return table_dir


def _scan_delta(
    context: SessionContext,
    table_dir: Path,
    options: dict[str, Any],
    schema: pa.Schema | None,
) -> DataFrame:
    from deltalake import DeltaTable

    version = options.get("version")
    if version is not None and str(version).strip():
        version = int(version)
    else:
        version = None
    dt = DeltaTable(str(table_dir), version=version)
    dataset = dt.to_pyarrow_dataset()
    view_name = f"det_delta_{uuid4().hex}"
    context.register_dataset(view_name, dataset)
    return context.sql(f"SELECT * FROM {view_name}")


def _scan_iceberg(
    context: SessionContext,
    table_dir: Path,
    options: dict[str, Any],
    schema: pa.Schema | None,
) -> DataFrame:
    try:
        from pyiceberg.table import StaticTable

        metadata_files = sorted(table_dir.glob("metadata/*.metadata.json"), reverse=True)
        if metadata_files:
            table = StaticTable.from_metadata(str(metadata_files[0]))
        else:
            root_meta = table_dir / "metadata.json"
            if root_meta.exists():
                table = StaticTable.from_metadata(str(root_meta))
            else:
                raise FileNotFoundError(f"No Iceberg metadata file found in {table_dir / 'metadata'}")

        scan = table.scan()
        snapshot_id = options.get("snapshot_id")
        if snapshot_id is not None and str(snapshot_id).strip():
            scan = scan.use_snapshot(int(snapshot_id))
        as_of_ts = options.get("as_of_timestamp")
        if as_of_ts is not None and str(as_of_ts).strip():
            scan = scan.as_of_time(int(as_of_ts))
        arrow_table = scan.to_arrow()
        table_to_register = _apply_saved_schema(arrow_table, schema)
        return context.from_arrow(table_to_register)
    except ImportError:
        data_dir = table_dir / "data"
        if data_dir.is_dir():
            parquet_files = sorted(data_dir.glob("**/*.parquet"))
            if parquet_files:
                return _scan_parquet(context, parquet_files, options, schema)
        raise RuntimeError(
            "Apache Iceberg connector requires 'pyiceberg'. "
            "Install it with: pip install pyiceberg"
        )


def scan_builtin(
    context: SessionContext,
    connector_guid: str,
    options: dict[str, Any],
    workspace: str | Path,
    saved_columns: list[dict[str, Any]] | None = None,
) -> DataFrame:
    """Build a lazy DataFusion scan using the saved built-in connector options."""
    resolved_workspace = Path(workspace).expanduser().resolve()
    connector_by_guid = {item.guid: item for item in connector_definitions()}
    connector = connector_by_guid.get(connector_guid)
    if connector is None:
        raise ValueError(f"Unknown connector GUID: {connector_guid}")

    schema = _build_arrow_schema(saved_columns)

    if connector.key in {"delta", "iceberg"}:
        table_dir = _resolve_table_directory(options, resolved_workspace)
        if connector.key == "delta":
            return _scan_delta(context, table_dir, options, schema)
        if connector.key == "iceberg":
            return _scan_iceberg(context, table_dir, options, schema)

    paths = _matched_paths(options, resolved_workspace)

    if connector.key == "csv":
        return _scan_csv(context, paths, options, schema)
    if connector.key == "parquet":
        return _scan_parquet(context, paths, options, schema)
    if connector.key == "json":
        return _scan_json(context, paths, options, schema)
    if connector.key == "excel":
        return _scan_excel(context, paths, options, schema)
    if connector.key == "xml":
        return _scan_xml(context, paths, options, schema)

    if connector.read is None:
        raise NotImplementedError(f"Connector {connector.label} does not provide a reader.")
    return connector.read(context, options, resolved_workspace)
