"""Workspace root facade unifying Engine, Catalog, Multi-Projects, Runner, and Docs."""

import logging
from pathlib import Path
from typing import Any

from det.catalog.base import ConnectionTestResult
from det.catalog.manager import CatalogManager
from det.config import WorkspaceConfig
from det.docs.base import ProjectDoc
from det.docs.extractor import DocsExtractor
from det.docs.generator import DocsGenerator
from det.docs.lineage import LineageGenerator
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
        self.root = root_path
        self.config = config or WorkspaceConfig.load(self.root / ".det" / "config.yaml")
        self.engine = engine or EngineFacade(self.config.to_engine_config(self.root))
        self.catalog = catalog or CatalogManager(self.root / "catalog" / "connections.yaml")
        self.projects = projects or ProjectManager(self.root, catalog_manager=self.catalog)
        self.runner = runner or PipelineRunner(engine=self.engine)
        self.tester = tester or TestRunner()
        self.docs_gen = docs_gen or DocsGenerator()
        self.lineage_gen = LineageGenerator()
        self.docs_extractor = DocsExtractor()
        self.monitoring = TelemetryManager(self.root)

        # Eagerly mount all catalog connections into the shared engine session
        self.mount_catalog()

    def mount_catalog(self) -> MountReport:
        """Eagerly register all catalog connections into the shared DuckDB session."""
        mountable_items = self.catalog.get_mountable_items()
        report = self.engine.mount_all(mountable_items)
        logger.debug("Mounted %d catalog connections into workspace.", len(report.mounted))
        return report

    @classmethod
    def init(cls, workspace_path: Path) -> "Workspace":
        """Scaffold standard workspace directory structure and default templates."""
        workspace_path.mkdir(parents=True, exist_ok=True)
        cls._scaffold_directories(workspace_path)
        cls._scaffold_initial_files(workspace_path)
        logger.info("Initialized new det workspace in '%s'", workspace_path)
        return cls(workspace_path)

    @classmethod
    def open(cls, workspace_path: Path) -> "Workspace":
        """Open an existing workspace, validating directory structure."""
        if not workspace_path.exists():
            raise FileNotFoundError(f"Workspace directory '{workspace_path}' does not exist.")
        return cls(workspace_path)

    def run(
        self, project: str | None = None, select: str | None = None
    ) -> PipelineExecutionReport:
        """Execute models in topological order, optionally filtered by selector."""
        proj_name = project or self.config.default_project
        dag = self.projects.build_dag(proj_name)
        selected = dag.select_models(select) if select else None
        rep = self.runner.run_dag(dag, selected_models=selected)
        try:
            self._record_telemetry_run(proj_name, rep)
        except Exception as e:
            logger.warning("Telemetry run logging notice: %s", e)
        return rep

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
        """Discover and parse declarative schema tests for project models."""
        models_dir = self.projects._get_models_directory(project)
        tests_by_model: dict[str, list[Any]] = {}
        if not models_dir.exists():
            return tests_by_model
        import yaml
        for sf in sorted(models_dir.rglob("schema.y*ml")):
            try:
                data = yaml.safe_load(sf.read_text(encoding="utf-8")) or {}
                for t in self.tester.parse_schema_tests(data):
                    tests_by_model.setdefault(t.model_name, []).append(t)
            except Exception as e:
                logger.warning("Error loading schema tests from %s: %s", sf, e)
        return tests_by_model

    def test(self, project: str | None = None) -> TestSuiteReport:
        """Run data quality assertions and update quarantine sinks."""
        target_proj = project or self.config.default_project
        dag = self.projects.build_dag(target_proj)
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

    def _record_telemetry_test_audits(self, project: str, results: list[Any]) -> None:
        """Convert test results to telemetry audit records and persist."""
        import datetime
        from det.monitoring.base import TestAuditRecord, generate_telemetry_id
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        audits = []
        for r in results:
            sev = r.severity.value if hasattr(r.severity, "value") else str(r.severity)
            f_count = getattr(r, "failing_rows_count", 0)
            msg = getattr(r, "error_message", None) or ("PASSED" if r.passed else f"{f_count} failing rows")
            act = "QUARANTINE" if getattr(r, "quarantined_table", None) else ("HALT" if not r.passed and sev == "error" else "LOG")
            audits.append(
                TestAuditRecord(
                    audit_id=generate_telemetry_id("audit"),
                    run_id=generate_telemetry_id("trun"),
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

    def generate_docs(self, project: str | None = None) -> Path:
        """Compile and emit self-contained HTML documentation for a project."""
        proj_name = project or self.config.default_project
        dag = self.projects.build_dag(proj_name)
        models = self.projects.load_project_models(proj_name)

        all_tests: list[TestDefinition] = []
        for m in models:
            all_tests.extend(TestDefinition.infer_from_model(m))
        explicit_tests = self._load_explicit_tests(proj_name)
        for t_list in explicit_tests.values():
            all_tests.extend([TestDefinition.from_dict("model", t) if isinstance(t, dict) else t for t in t_list])

        models_dir = self.projects._get_models_directory(proj_name)
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
        return self.docs_gen.write_docs(self._docs_dir(proj_name), proj_doc)

    def _docs_dir(self, proj_name: str) -> Path:
        """Resolve docs directory path for project."""
        p_dir = self.root / "projects" / proj_name / "docs"
        return p_dir if (self.root / "projects").exists() else self.root / "docs"

    def delete_docs(self, project: str | None = None) -> bool:
        """Delete generated static HTML documentation and manifest for a project."""
        import shutil
        out_dir = self._docs_dir(project or self.config.default_project)
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
            return True
        return False

    def test_catalog(self) -> dict[str, ConnectionTestResult]:
        """Ping all registered catalog connections and report latency."""
        return self.catalog.test_all(self.engine.session)

    def close(self) -> None:
        """Safely close active engine session and flush disk buffers."""
        self.engine.close()

    @classmethod
    def _scaffold_directories(cls, root: Path) -> None:
        """Create standard folder layout."""
        for p in (".det", "catalog", "extensions", "projects/default/models/staging", "projects/default/models/marts"):
            (root / p).mkdir(parents=True, exist_ok=True)

    @classmethod
    def _scaffold_initial_files(cls, root: Path) -> None:
        """Write starting templates for config, catalog, and default model."""
        cfg = root / ".det" / "config.yaml"
        if not cfg.exists():
            WorkspaceConfig().save(cfg)
        cat = root / "catalog" / "connections.yaml"
        if not cat.exists():
            cat.write_text("connections: {}\n", encoding="utf-8")
        proj = root / "projects" / "default" / "det_project.yaml"
        if not proj.exists():
            proj.write_text("name: default\nversion: 0.1.0\n", encoding="utf-8")
