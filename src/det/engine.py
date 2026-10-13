"""Thin Apache DataFusion integration for local SQL pipeline work."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
from datafusion import DataFrame, SessionContext
from datafusion.plan import ExecutionPlan, LogicalPlan


@dataclass(frozen=True)
class DataFrameAnalysis:
    """Native DataFusion schema and plans for a lazy DataFrame."""

    schema: pa.Schema
    logical_plan: LogicalPlan
    optimized_logical_plan: LogicalPlan
    execution_plan: ExecutionPlan


def create_session_context() -> SessionContext:
    """Create a DataFusion session for one pipeline execution."""
    return SessionContext()


def scan_file(context: SessionContext, location: str | Path) -> DataFrame:
    """Build a lazy DataFusion scan for a supported local file."""
    source = Path(location).expanduser()
    suffix = source.suffix.lower()

    if suffix == ".csv":
        return context.read_csv(source)
    if suffix == ".parquet":
        return context.read_parquet(source)
    if suffix in {".json", ".jsonl"}:
        return context.read_json(source, file_extension=suffix)
    raise ValueError(
        f"Unsupported DataFusion file format {suffix or '(no extension)'!r}: {source}"
    )


def register_dataframe(
    context: SessionContext,
    name: str,
    dataframe: DataFrame,
) -> None:
    """Register a source or prior stage as a lazy SQL view."""
    context.register_view(name, dataframe)


def run_sql(
    context: SessionContext,
    query: str,
    *,
    parameters: dict[str, Any] | None = None,
) -> DataFrame:
    """Create a lazy DataFusion DataFrame from SQL."""
    return context.sql(query, param_values=parameters)


def analyze_dataframe(dataframe: DataFrame) -> DataFrameAnalysis:
    """Return DataFusion's schema and logical/physical plans without collecting."""
    return DataFrameAnalysis(
        schema=dataframe.schema(),
        logical_plan=dataframe.logical_plan(),
        optimized_logical_plan=dataframe.optimized_logical_plan(),
        execution_plan=dataframe.execution_plan(),
    )
