"""Pipeline runner orchestrating DAG model materialization and egress destinations."""

from dataclasses import dataclass, field
import logging
from pathlib import Path
import time
from typing import Any
import duckdb

from det.engine.facade import EngineFacade
from det.models.base import DestinationSpec, WriteMode
from det.models.dag import ModelDAG
from det.models.definition import ModelDefinition

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelExecutionResult:
    """Telemetry outcome for an individual model run."""

    model_name: str
    status: str
    duration_ms: float
    row_count: int = 0
    error_message: str | None = None

    @property
    def is_success(self) -> bool:
        """Return True if model materialized without error."""
        return self.status == "SUCCESS"


@dataclass
class PipelineExecutionReport:
    """Summary metrics of an end-to-end pipeline DAG run."""

    total_models: int = 0
    succeeded: int = 0
    failed: int = 0
    duration_ms: float = 0.0
    results: list[ModelExecutionResult] = field(default_factory=list)

    @property
    def is_successful(self) -> bool:
        """Return True if all models succeeded."""
        return self.failed == 0

    def add_result(self, result: ModelExecutionResult) -> None:
        """Record model execution result into aggregate metrics."""
        self.total_models += 1
        self.results.append(result)
        if result.is_success:
            self.succeeded += 1
        else:
            self.failed += 1


class PipelineRunner:
    """Orchestrates staged execution of models and egress publishing."""

    def __init__(self, engine: EngineFacade | None = None) -> None:
        self._engine = engine or EngineFacade()

    def run_dag(
        self,
        dag: ModelDAG,
        selected_models: set[str] | None = None,
    ) -> PipelineExecutionReport:
        """Execute models in staged topological order against the engine session."""
        start_time = time.perf_counter()
        report = PipelineExecutionReport()
        stages = dag.get_execution_stages()

        for stage in stages:
            for model_name in stage.models:
                if selected_models is not None and model_name not in selected_models:
                    continue
                model = dag.get_model(model_name)
                if not model or not model.config.enabled:
                    continue
                result = self._execute_single_model(self._engine.session, model)
                report.add_result(result)
                if not result.is_success:
                    logger.error("Halting pipeline: Model '%s' failed.", model_name)
                    report.duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                    return report

        report.duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return report

    def _execute_single_model(
        self, con: duckdb.DuckDBPyConnection, model: ModelDefinition
    ) -> ModelExecutionResult:
        """Materialize model in DuckDB session and publish to configured destinations."""
        start = time.perf_counter()
        try:
            # 1. Primary local materialization
            ddl_sql = model.get_materialize_sql()
            con.execute(ddl_sql)

            # 2. Publish to secondary destinations
            self._publish_destinations(con, model)

            # 3. Telemetry row count
            count_res = con.execute(f"SELECT COUNT(*) FROM {model.name}").fetchall()
            row_count = int(count_res[0][0]) if count_res else 0
            elapsed = (time.perf_counter() - start) * 1000.0

            return ModelExecutionResult(
                model_name=model.name,
                status="SUCCESS",
                duration_ms=round(elapsed, 2),
                row_count=row_count,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000.0
            logger.error("Execution failed for model '%s': %s", model.name, exc)
            return ModelExecutionResult(
                model_name=model.name,
                status="FAILED",
                duration_ms=round(elapsed, 2),
                error_message=str(exc),
            )

    def _publish_destinations(
        self, con: duckdb.DuckDBPyConnection, model: ModelDefinition
    ) -> None:
        """Execute publishing SQL for each non-local destination."""
        for dest in model.config.destinations:
            if dest.target == "local" and not dest.path:
                continue
            out = dest.path or dest.target
            if out.lower().endswith((".xlsx", ".xls")):
                self._export_to_excel(con, model.name, out)
            elif out.lower().endswith((".parquet", ".csv", ".json")):
                fmt = (dest.format or out.split(".")[-1]).upper()
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                con.execute(f"COPY {model.name} TO '{out}' (FORMAT {fmt})")
            elif dest.mode == WriteMode.APPEND:
                publish_sql = f"INSERT INTO {dest.target} BY NAME SELECT * FROM {model.name}"
                con.execute(publish_sql)
            else:
                publish_sql = f"CREATE OR REPLACE TABLE {dest.target} AS SELECT * FROM {model.name}"
                con.execute(publish_sql)

    def _export_to_excel(
        self, con: duckdb.DuckDBPyConnection, table_name: str, out_path: str
    ) -> None:
        """Export table or view to an Excel workbook (.xlsx)."""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = table_name[:31]
        res = con.execute(f"SELECT * FROM {table_name}")
        ws.append([col[0] for col in res.description])
        for row in res.fetchall():
            ws.append(list(row))
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        wb.save(out_path)

