"""Workspace root facade unifying Engine, Catalog, Multi-Projects, Runner, and Docs."""

import logging
from pathlib import Path
import threading
from typing import Any

from det.catalog.base import ConnectionTestResult
from det.catalog.definitions import ConnectionDefinition
from det.catalog.manager import CatalogManager
from det.config import WorkspaceConfig
from det.docs.base import ProjectDoc
from det.docs.extractor import DocsExtractor
from det.docs.generator import DocsGenerator
from det.docs.lineage import LineageGenerator
from det.docs.server import DocsServer
from det.engine.base import MountReport
from det.engine.facade import EngineFacade
from det.models.dag import ModelDAG
from det.models.project import ProjectManager
from det.monitoring.manager import TelemetryManager
from det.runner import PipelineExecutionReport, PipelineRunner
from det.testing.base import TestSuiteReport
from det.testing.definitions import TestDefinition
from det.testing.runner import TestRunner

logger = logging.getLogger(__name__)


class Workspace:
    """Root platform facade coordinating all subsystem services."""

    def __init__(
        self,
        root_path: Path,
        config: WorkspaceConfig | None = None,
        engine: EngineFacade | None = None,
        catalog: CatalogManager | None = None,
        projects: ProjectManager | None = None,
        runner: PipelineRunner | None = None,
        tester: TestRunner | None = None,
        docs_gen: DocsGenerator | None = None,
    ) -> None:
        self.root = root_path.resolve()
        self.config = config or WorkspaceConfig.load(self.root / ".det" / "config.yaml")
        self.engine = engine or EngineFacade(self.config.to_engine_config(self.root))
        self.catalog = catalog or CatalogManager(self.root / "catalog" / "connections.yaml")
        self.projects = projects or ProjectManager(self.root, catalog_manager=self.catalog)
        self.runner = runner or PipelineRunner(engine=self.engine, workspace_root=self.root)
        self.tester = tester or TestRunner()
        self.docs_gen = docs_gen or DocsGenerator()
        self.lineage_gen = LineageGenerator()
        self.docs_extractor = DocsExtractor()
        self.docs_server = DocsServer()
        self.monitoring = TelemetryManager(self.root)
        self._active_runs: set[str] = set()
        self._run_lock = threading.Lock()

        # Eagerly mount all catalog connections into the shared engine session
        self.mount_catalog()

    def is_pipeline_running(self, project: str) -> bool:
        """Check if a specific pipeline project is actively running."""
        with self._run_lock:
            return project in self._active_runs

    def get_running_pipelines(self) -> list[str]:
        """Return list of pipeline names currently executing."""
        with self._run_lock:
            return sorted(self._active_runs)

    def mount_catalog(self) -> MountReport:
        """Eagerly register all catalog connections into the shared DuckDB session."""
        try:
            self.engine.session.execute(f"SET file_search_path = '{self.root.as_posix()}'")
        except Exception as exc:
            logger.debug("Could not set file_search_path: %s", exc)
        mountable_items = self.catalog.get_mountable_items()
        report = self.engine.mount_all(mountable_items)
        logger.debug("Mounted %d catalog connections into workspace.", len(report.mounted))
        return report

    def setup_demo(self, use_remote: bool = False) -> dict[str, Any]:
        """Scaffold and mount sample demo datasets, connections, and pipelines."""
        from det.demo import setup_demo_workspace
        result = setup_demo_workspace(self.root, use_remote=use_remote)
        self.catalog = CatalogManager(self.root / "catalog" / "connections.yaml")
        self.mount_catalog()
        return result

    @classmethod
    def init(cls, workspace_path: Path | str) -> "Workspace":
        """Scaffold standard workspace directory structure and default templates."""
        resolved = Path(workspace_path).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        cls._scaffold_directories(resolved)
        cls._scaffold_initial_files(resolved)
        logger.info("Initialized new det workspace in '%s'", resolved)
        return cls(resolved)

    @classmethod
    def open(cls, workspace_path: Path | str) -> "Workspace":
        """Open an existing workspace, validating directory structure."""
        resolved = Path(workspace_path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Workspace directory '{resolved}' does not exist.")
        return cls(resolved)

    def run(
        self, project: str | None = None, select: str | None = None
    ) -> PipelineExecutionReport:
        """Execute models in topological order, optionally filtered by selector."""
        proj_name = project or self.config.default_project
        with self._run_lock:
            if proj_name in self._active_runs:
                raise RuntimeError(
                    f"Pipeline '{proj_name}' is already running. Please wait for the current run to finish."
                )
            self._active_runs.add(proj_name)

        try:
            dag = self.projects.build_dag(proj_name)
            selected = dag.select_models(select) if select else None
            rep = self.runner.run_dag(dag, selected_models=selected)
            try:
                self._record_telemetry_run(proj_name, rep)
            except Exception as e:
                logger.warning("Telemetry run logging notice: %s", e)
            return rep
        finally:
            with self._run_lock:
                self._active_runs.discard(proj_name)

    def _record_telemetry_run(self, project: str, rep: PipelineExecutionReport) -> None:
        """Persist pipeline execution report and per-model stage telemetry."""
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        total_rows = sum(r.row_count for r in rep.results)
        err = next((r.error_message for r in rep.results if r.error_message), None)
        stages = [
            {"model_name": r.model_name, "status": r.status, "started_at": now,
             "duration_ms": round(r.duration_ms, 2), "rows_affected": r.row_count,
             "error_message": r.error_message}
            for r in rep.results
        ]
        self.monitoring.log_run(
            project=project, status="SUCCESS" if rep.is_successful else "FAILED",
            duration_ms=rep.duration_ms, models_executed=rep.total_models,
            rows_affected=total_rows, error_message=err, models_detail=stages,
        )

    def _load_explicit_tests(self, project: str) -> dict[str, list[Any]]:
        """Discover and parse declarative schema tests for project models with mtime caching."""
        models_dir = self.projects._get_models_directory(project)
        tests_by_model: dict[str, list[Any]] = {}
        if not models_dir.exists():
            return tests_by_model

        schema_files = sorted(models_dir.rglob("schema.y*ml"))
        if not schema_files:
            return tests_by_model

        current_mtime = max(sf.stat().st_mtime for sf in schema_files)
        if not hasattr(self, "_explicit_tests_cache"):
            self._explicit_tests_cache: dict[str, tuple[float, dict[str, list[Any]]]] = {}

        cached = self._explicit_tests_cache.get(project)
        if cached and cached[0] == current_mtime:
            return cached[1]

        import yaml
        for sf in schema_files:
            try:
                data = yaml.safe_load(sf.read_text(encoding="utf-8")) or {}
                for t in self.tester.parse_schema_tests(data):
                    tests_by_model.setdefault(t.model_name, []).append(t)
            except Exception as e:
                logger.warning("Error loading schema tests from %s: %s", sf, e)

        self._explicit_tests_cache[project] = (current_mtime, tests_by_model)
        return tests_by_model

    def test(self, project: str | None = None, build: bool = False) -> TestSuiteReport:
        """Run data quality assertions against configured policies (error, warning, drop)."""
        target_proj = project or self.config.default_project
        dag = self.projects.build_dag(target_proj)

        if build:
            self.run(target_proj)
        else:
            self._ensure_models_staged_for_testing(dag)

        explicit_map = self._load_explicit_tests(target_proj)
        all_tests = []
        for model in dag._models.values():
            explicit = explicit_map.get(model.name, [])
            all_tests.extend(self.tester.run_model_tests(self.engine.session, model, explicit_tests=explicit).results)

        report = TestSuiteReport()
        for res in all_tests:
            report.add_result(res)
        try:
            self._record_telemetry_test_audits(target_proj, all_tests)
        except Exception as e:
            logger.debug("Telemetry test audit notice: %s", e)
        return report

    def _ensure_models_staged_for_testing(self, dag: ModelDAG) -> None:
        """Ensure all enabled models in the DAG are available in the engine session for assertion testing.

        If a model is already materialized in DuckDB, it is preserved. If not present in the session,
        it is lazily staged as a transient DuckDB view in topological dependency order. If view
        creation fails, it falls back to full materialization.
        """
        stages = dag.get_execution_stages()
        for stage in stages:
            for model_name in stage.models:
                model = dag.get_model(model_name)
                if not model or not model.config.enabled:
                    continue
                # Check if model table/view already exists in this DuckDB session
                already_exists = False
                try:
                    self.engine.session.execute(f"SELECT 1 FROM {model.name} LIMIT 0")
                    already_exists = True
                except Exception:
                    already_exists = False

                if not already_exists:
                    try:
                        PipelineRunner._prepare_target(self.engine.session, model.name, target_is_table=False)
                        self.engine.session.execute(f"CREATE OR REPLACE VIEW {model.name} AS {model.compiled_sql}")
                    except Exception as view_exc:
                        logger.debug(
                            "Fast JIT view staging for '%s' note: %s. Falling back to materialization.",
                            model.name,
                            view_exc,
                        )
                        try:
                            self.runner._execute_single_model(self.engine.session, model)
                        except Exception as run_exc:
                            logger.warning("Could not stage model '%s' for testing: %s", model.name, run_exc)

    def _record_telemetry_test_audits(self, project: str, results: list[Any], run_id: str | None = None) -> None:
        """Convert test results to aggregate telemetry audit records without row-level bloat."""
        import datetime
        from det.monitoring.base import TestAuditRecord, generate_telemetry_id
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        active_run_id = run_id or generate_telemetry_id("run")
        audits = []
        for r in results:
            sev = r.severity.value if hasattr(r.severity, "value") else str(r.severity)
            f_count = getattr(r, "failing_rows_count", 0)
            if r.passed:
                act = "PASSED"
                msg = "PASSED"
            elif sev.lower() in ("warn", "warning"):
                act = "WARNED"
                msg = f"{f_count} rows raised warning"
            elif sev.lower() in ("drop", "quarantine"):
                act = "DROPPED"
                msg = f"Dropped {f_count} failing rows from dataset"
            else:
                act = "HALTED"
                msg = f"Halted: {f_count} rows violated test"

            audits.append(
                TestAuditRecord(
                    audit_id=generate_telemetry_id("audit"),
                    run_id=active_run_id,
                    project=project,
                    model_name=getattr(r, "model_name", "unknown"),
                    test_name=getattr(r, "test_name", "test"),
                    test_type=getattr(r, "test_name", "").split("_")[-1] or "assertion",
                    severity=sev.upper(),
                    passed=bool(getattr(r, "passed", True)),
                    failures_count=int(f_count),
                    action_taken=act,
                    details=str(msg),
                    executed_at=now,
                )
            )
        self.monitoring.active_sink.record_test_audits(audits)

    def monitor_runs(
        self,
        project: str | None = None,
        limit: int = 20,
        days: int = 30,
        failed_only: bool = False,
    ) -> list[Any]:
        """Fetch recent pipeline execution runs with inclusive priority."""
        return self.monitoring.get_runs(
            project=project, limit=limit, days=days, failed_only=failed_only
        )

    def monitor_run_detail(self, run_id: str) -> Any | None:
        """Fetch detailed model trace for a single pipeline run."""
        return self.monitoring.get_run(run_id)

    def monitor_audits(
        self,
        project: str | None = None,
        run_id: str | None = None,
        failed_only: bool = False,
        limit: int = 50,
    ) -> list[Any]:
        """Fetch data quality test audit records."""
        audits = self.monitoring.get_test_audits(
            run_id=run_id, project=project, limit=limit
        )
        if failed_only:
            audits = [a for a in audits if not a.passed]
        return audits

    def monitor_status(self) -> dict[str, Any]:
        """Fetch telemetry sink status and storage metadata."""
        return self.monitoring.get_sink_info()

    def monitor_clean(self, days: int = 30, project: str | None = None) -> dict[str, int]:
        """Purge telemetry runs and test audits older than N days."""
        return self.monitoring.clean(days=days, project=project)

    def generate_docs(self, pipeline: str | None = None, project: str | None = None) -> Path:
        """Compile and emit self-contained HTML documentation for a single pipeline."""
        proj_name = pipeline or project or self.config.default_project
        known = self.projects.discover_projects()
        if known and proj_name not in known:
            raise KeyError(f"Pipeline '{proj_name}' does not exist.")

        dag = self.projects.build_dag(proj_name)
        models = self.projects.load_project_models(proj_name)

        all_tests: list[TestDefinition] = []
        for m in models:
            all_tests.extend(TestDefinition.infer_from_model(m))
        explicit_tests = self._load_explicit_tests(proj_name)
        for t_list in explicit_tests.values():
            all_tests.extend([TestDefinition.from_dict("model", t) if isinstance(t, dict) else t for t in t_list])

        models_dir = self.projects._get_models_directory(proj_name).resolve()
        m_descs, c_descs = DocsExtractor.load_schema_descriptions(models_dir)
        model_docs = [
            self.docs_extractor.extract_model_doc(
                self.engine.session, m, all_tests, catalog=self.catalog,
                column_descriptions=c_descs.get(m.name, {}),
                model_description=m_descs.get(m.name),
            )
            for m in models
        ]
        lineage = self.lineage_gen.generate_mermaid(dag)

        proj_doc = ProjectDoc(
            project_name=proj_name, version="0.1.0",
            description=f"Automated pipeline documentation for {proj_name}",
            total_models=len(models), total_sources=len(dag._dependencies),
            total_tests=len(all_tests), models=model_docs, lineage_mermaid=lineage,
        )
        out_dir = self._docs_dir(proj_name).resolve()
        return self.docs_gen.write_docs(out_dir, proj_doc).resolve()

    def _docs_dir(self, proj_name: str) -> Path:
        """Resolve absolute docs directory path for pipeline."""
        root = self.root.resolve()
        models_dir = self.projects._get_models_directory(proj_name).resolve()
        if models_dir.parent.exists() and models_dir.parent != root:
            return (models_dir.parent / "docs").resolve()
        p_dir = (root / "pipelines" / proj_name / "docs").resolve()
        return p_dir if (root / "pipelines").exists() else (root / "docs").resolve()

    def get_docs_path(self, pipeline: str) -> Path | None:
        """Return absolute path to generated index.html if it exists, else None."""
        docs_dir = self._docs_dir(pipeline).resolve()
        index_file = (docs_dir / "index.html").resolve()
        return index_file if index_file.exists() else None

    def export_docs(self, pipeline: str, output_path: str | Path | None = None) -> Path:
        """Export single-file HTML documentation for a single pipeline to an absolute target path."""
        html_path = self.generate_docs(pipeline=pipeline).resolve()
        if output_path is None:
            target = (Path.cwd().resolve() / f"{pipeline}_docs.html").resolve()
        else:
            p = Path(output_path).resolve()
            if p.is_dir() or not p.suffix or str(output_path).endswith(("/", "\\")):
                target = (p / f"{pipeline}_docs.html").resolve()
            else:
                target = p.resolve()

        target.parent.resolve().mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(html_path, target)
        return target.resolve()

    def delete_docs(self, pipeline: str | None = None, project: str | None = None) -> bool:
        """Delete generated static HTML documentation and manifest for a pipeline."""
        import shutil
        target = pipeline or project or self.config.default_project
        out_dir = self._docs_dir(target).resolve()
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
            return True
        return False

    def delete_pipeline(self, name: str) -> bool:
        """Delete a pipeline project directory and its generated artifacts."""
        deleted = self.projects.delete_project(name)
        if deleted:
            self.delete_docs(pipeline=name)
            if not self.projects.discover_projects():
                (self.root.resolve() / "pipelines" / "default" / "models").mkdir(parents=True, exist_ok=True)
        return deleted

    def list_pipelines(
        self, folder: str | None = None, name_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """List pipelines with metadata, optionally filtered by folder and name substring."""
        return self.projects.list_pipelines(folder=folder, name_filter=name_filter)

    def list_pipeline_models(self, pipeline_name: str) -> list[ModelDefinition]:
        """Return list of parsed model definitions for a given pipeline."""
        known = self.projects.discover_projects()
        if pipeline_name not in known:
            raise KeyError(f"Pipeline '{pipeline_name}' does not exist.")
        return self.projects.load_project_models(pipeline_name)

    def compile_pipeline(self, pipeline_name: str) -> dict[str, Any]:
        """Compile and validate pipeline DAG, models, and dependencies without execution."""
        known = self.projects.discover_projects()
        if pipeline_name not in known:
            raise KeyError(f"Pipeline '{pipeline_name}' does not exist.")

        models = self.projects.load_project_models(pipeline_name)
        dag = self.projects.build_dag(pipeline_name)

        errors: list[str] = []

        # 1. Cycle detection
        cycles = dag.detect_cycles()
        if cycles:
            errors.append(f"Circular dependency detected: {' -> '.join(cycles)}")

        # 2. Dependency verification
        known_connections = self.projects._get_known_connection_names()
        known_model_names = set(dag._models.keys())

        all_sources: set[str] = set()
        all_refs: set[str] = set()

        for m in models:
            for s in m.sources:
                all_sources.add(s)
                if known_connections and s not in known_connections:
                    errors.append(f"Model '{m.name}' references unknown catalog source('{s}').")
            for r in m.refs:
                all_refs.add(r)
                if r not in known_model_names and (known_connections and r not in known_connections):
                    errors.append(f"Model '{m.name}' references unknown model ref('{r}').")

        return {
            "pipeline": pipeline_name,
            "models_count": len(models),
            "cycles": cycles,
            "sources": sorted(all_sources),
            "refs": sorted(all_refs),
            "is_valid": len(errors) == 0,
            "errors": errors,
        }

    def list_catalog(
        self, folder: str | None = None, name_filter: str | None = None
    ) -> list[ConnectionDefinition]:
        """List registered catalog connections, optionally filtered by folder and name substring."""
        return self.catalog.list_connections(folder=folder, name_filter=name_filter)

    def test_catalog(
        self, connection: str | None = None, folder: str | None = None
    ) -> dict[str, ConnectionTestResult]:
        """Ping a single connection, connections under a folder, or all connections."""
        return self.catalog.test_connections(self.engine.session, connection=connection, folder=folder)

    def display_catalog(
        self, name: str, limit: int = 10
    ) -> tuple[list[str], list[tuple[Any, ...]]]:
        """Fetch and return top rows from a registered catalog connection."""
        return self.catalog.display_connection(self.engine.session, name, limit=limit)

    def details_catalog(self, name: str) -> dict[str, Any]:
        """Retrieve complete metadata and configuration properties for a connection."""
        return self.catalog.get_connection_details(name)

    def delete_catalog_connection(self, name: str) -> bool:
        """Delete an individual connection definition from the catalog."""
        return self.catalog.delete_connection(name, persist=True)

    def close(self) -> None:
        """Safely close active engine session and flush disk buffers."""
        self.engine.close()

    CORE_FOLDERS = ("catalog", "pipelines", "data", "extensions")

    @classmethod
    def _scaffold_directories(cls, root: Path) -> None:
        """Create standard folder layout if folders do not already exist."""
        folders = [
            ".det",
            ".det/bin",
            "catalog",
            "pipelines",
            "pipelines/default/models/staging",
            "pipelines/default/models/marts",
            "data",
            "extensions",
        ]
        for rel in folders:
            folder_path = root / rel
            if not folder_path.exists():
                folder_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _scaffold_initial_files(cls, root: Path) -> None:
        """Write starting templates if they do not already exist."""
        cfg = root / ".det" / "config.yaml"
        if not cfg.exists():
            WorkspaceConfig().save(cfg)
        cat = root / "catalog" / "connections.yaml"
        if not cat.exists():
            cat.write_text("connections: {}\n", encoding="utf-8")
        proj = root / "pipelines" / "default" / "det_project.yaml"
        if not proj.exists():
            proj.parent.mkdir(parents=True, exist_ok=True)
            proj.write_text("name: default\nversion: 0.1.0\n", encoding="utf-8")

        cls._scaffold_activation_scripts(root)

    @classmethod
    def _scaffold_activation_scripts(cls, root: Path) -> None:
        """Write activation scripts into .det/bin/ if they do not exist."""
        bin_dir = root / ".det" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)

        ps1 = bin_dir / "activate.ps1"
        if not ps1.exists():
            ps1.write_text(
                '# Activate det environment for PowerShell\n'
                '$script:DetRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path\n'
                '$env:DET_ACTIVE_DIR = $script:DetRoot\n'
                'try {\n'
                '    $sessionDir = Join-Path $HOME ".det"\n'
                '    if (-not (Test-Path $sessionDir)) { New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null }\n'
                '    @{ active_dir = $script:DetRoot } | ConvertTo-Json | Set-Content (Join-Path $sessionDir "session.json") -Encoding utf8\n'
                '} catch {}\n'
                'Write-Host "Activated det environment: $env:DET_ACTIVE_DIR" -ForegroundColor Green\n',
                encoding="utf-8",
            )

        bat = bin_dir / "activate.bat"
        if not bat.exists():
            bat.write_text(
                '@echo off\n'
                'pushd "%~dp0..\\.."\n'
                'set "DET_ACTIVE_DIR=%CD%"\n'
                'popd\n'
                'echo Activated det environment: %DET_ACTIVE_DIR%\n',
                encoding="utf-8",
            )

        sh = bin_dir / "activate"
        if not sh.exists():
            sh.write_text(
                '#!/usr/bin/env sh\n'
                'DET_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"\n'
                'export DET_ACTIVE_DIR="$DET_ROOT"\n'
                'mkdir -p "$HOME/.det" 2>/dev/null\n'
                'echo "{\\"active_dir\\": \\"$DET_ROOT\\"}" > "$HOME/.det/session.json" 2>/dev/null\n'
                'echo "Activated det environment: $DET_ACTIVE_DIR"\n',
                encoding="utf-8",
            )
