"""HTTP route handlers for Pipeline exploration, DAG serialization, and execution."""

from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
from typing import Any
import urllib.parse

from det.gui.routes.common import send_error_json, send_json
from det.models.definition import ModelDefinition
from det.validation import validate_identifier
from det.workspace import Workspace


class PipelineRouteHandler:
    """Manages pipelines, interactive DAG nodes/edges, and execution."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def handle_get(
        self, handler: BaseHTTPRequestHandler, path: str, query: dict[str, list[str]] | None = None
    ) -> bool:
        """Route GET requests for pipelines metadata and interactive DAGs."""
        raw_path = path.split("?")[0]
        parsed_url = urllib.parse.urlparse(handler.path)
        active_query = query or urllib.parse.parse_qs(parsed_url.query)
        if raw_path == "/api/pipelines":
            send_json(handler, self._list_pipelines())
            return True
        if raw_path == "/api/pipelines/dag":
            send_json(handler, self._get_dag(active_query.get("project", ["default"])[0]))
            return True
        return False

    def handle_post(
        self, handler: BaseHTTPRequestHandler, path: str, body: dict[str, Any]
    ) -> bool:
        """Route POST requests for running pipelines and managing models."""
        routes = {
            "/api/pipelines/run": self._handle_run_pipeline,
            "/api/pipelines/test": self._handle_test_pipeline,
            "/api/pipelines/docs": self._handle_generate_docs,
            "/api/pipelines/compile": self._handle_compile_pipeline,
            "/api/pipelines/model/save": self._handle_save_model,
            "/api/pipelines/model/delete": self._handle_delete_model,
            "/api/pipelines/create": self._handle_create_pipeline,
        }
        if path in routes:
            return routes[path](handler, body)
        return False

    def _list_pipelines(self) -> list[dict[str, Any]]:
        """List all discovered pipelines and their contained models."""
        pipelines = []
        for proj_name in self._workspace.projects.discover_projects():
            models = self._workspace.projects.load_project_models(proj_name)
            pipelines.append({
                "name": proj_name, "folder": "Core Pipelines",
                "description": f"{proj_name.capitalize()} analytics pipeline",
                "models_count": len(models), "models": [self._serialize_model(m) for m in models],
            })
        return pipelines

    def _serialize_model(self, model: ModelDefinition) -> dict[str, Any]:
        """Convert ModelDefinition into JSON-serializable dictionary."""
        import re
        folder = model.file_path.parent.name if model.file_path and model.file_path.parent.name != "models" else ""
        clean = re.sub(r"\{\{\s*config\s*\((.*?)\)\s*\}\}", "", model.raw_sql, flags=re.DOTALL | re.IGNORECASE).strip()
        dests = [d.path or d.target for d in model.config.destinations if d.target != "local" or d.path]
        return {
            "name": model.name, "project": model.project, "materialized": model.config.materialized.value,
            "folder": folder, "description": model.config.description or model.description,
            "unique_key": model.config.unique_key or "", "destinations": dests,
            "refs": model.refs, "sources": model.sources, "direct_connections": model.direct_connections,
            "raw_sql": model.raw_sql, "clean_sql": clean, "compiled_sql": model.compiled_sql,
            "tests_count": len(self._get_inferred_tests(model)), "tests": self._get_inferred_tests(model),
        }

    def _get_inferred_tests(self, model: ModelDefinition) -> list[dict[str, Any]]:
        """Extract inferred and declared assertions for model."""
        from det.testing.definitions import TestDefinition
        tests = [
            {"name": t.name, "column": t.column_name, "type": t.test_type.value, "severity": t.severity.value, "origin": "inferred"}
            for t in TestDefinition.infer_from_model(model)
        ]
        if hasattr(self._workspace, "_load_explicit_tests"):
            explicit_map = self._workspace._load_explicit_tests(model.project or "default")
            for t in explicit_map.get(model.name, []):
                tests.append({"name": t.name, "column": t.column_name, "type": t.test_type.value, "severity": t.severity.value, "origin": "schema.yml"})
        return tests

    def _get_dag(self, project: str) -> dict[str, Any]:
        """Build and serialize DAG graph nodes and directed edges."""
        dag = self._workspace.projects.build_dag(project)
        nodes, edges, seen_sources = [], [], set()

        for name, model in dag._models.items():
            folder = model.file_path.parent.name if model.file_path and model.file_path.parent.name != "models" else ""
            tests = self._get_inferred_tests(model)
            nodes.append({
                "id": name, "name": name, "type": "model", "materialized": model.config.materialized.value,
                "folder": folder, "description": model.config.description or model.description,
                "dependencies": sorted(model.all_dependencies),
                "tests_count": len(tests), "tests": tests,
            })
            for dep in model.all_dependencies:
                edges.append({"from": dep, "to": name})
                if dep not in dag._models and dep not in seen_sources:
                    seen_sources.add(dep)
                    nodes.append({"id": dep, "name": dep, "type": "source", "materialized": "source", "folder": "sources", "description": "Source", "dependencies": []})

        return {"project": project, "nodes": nodes, "edges": edges, "has_cycles": bool(dag.detect_cycles())}

    def _handle_run_pipeline(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> bool:
        """Execute a pipeline or single model and return execution telemetry."""
        project, select = body.get("project", "default"), body.get("select")
        try:
            rep = self._workspace.run(project=project, select=select)
            res_data = [
                {"model_name": r.model_name, "status": r.status, "duration_ms": round(r.duration_ms, 2), "row_count": r.row_count}
                for r in rep.results
            ]
            first_rows = rep.results[0].row_count if rep.results else 0
            send_json(handler, {
                "status": "ok" if rep.is_successful else "failed",
                "duration_ms": round(rep.duration_ms, 2), "total_models": rep.total_models,
                "succeeded": rep.succeeded, "failed": rep.failed, "row_count": first_rows, "results": res_data,
            })
        except Exception as e:
            send_error_json(handler, f"Pipeline execution failed: {e}")
        return True

    def _handle_test_pipeline(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> bool:
        """Execute test suite for project and return detailed assertion results."""
        project = body.get("project", "default")
        try:
            report = self._workspace.test(project=project)
            res_data = [
                {
                    "test_name": r.test_name, "model_name": r.model_name, "column_name": r.column_name,
                    "severity": r.severity.value if hasattr(r.severity, "value") else str(r.severity),
                    "passed": r.passed, "failing_rows": r.failing_rows_count,
                    "passed_rows": getattr(r, "passed_rows_count", 0), "total_rows": getattr(r, "total_rows_count", 0),
                    "quarantined_table": r.quarantined_table, "execution_time_ms": round(r.execution_time_ms, 2), "error_message": r.error_message,
                }
                for r in report.results
            ]
            send_json(handler, {
                "status": "ok" if report.is_successful else "failed", "passed": report.passed,
                "warned": report.warned, "failed": report.errored, "total_tests": report.total_tests,
                "quarantined": report.quarantined, "results": res_data,
            })
        except Exception as e:
            send_error_json(handler, f"Test failed: {e}")
        return True

    def _handle_generate_docs(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> bool:
        """Generate static documentation portal."""
        project = body.get("project", "default")
        try:
            html_path = self._workspace.generate_docs(project=project)
            send_json(handler, {"status": "ok", "path": str(html_path)})
        except Exception as e:
            send_error_json(handler, f"Docs generation failed: {e}")
        return True

    def _handle_compile_pipeline(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> bool:
        """Compile and validate DAG without execution."""
        project = body.get("project", "default")
        try:
            dag = self._workspace.projects.build_dag(project)
            send_json(handler, {
                "status": "ok", "models_count": len(dag._models),
                "has_cycles": bool(dag.detect_cycles())
            })
        except Exception as e:
            send_error_json(handler, f"Compile failed: {e}")
        return True

    def _handle_save_model(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> bool:
        """Create or update a model SQL file."""
        project, name = body.get("project", "default"), body.get("name", "").strip()
        folder = body.get("folder", "").strip()
        sql, clean = body.get("sql", ""), body.get("clean_sql", "")
        if not name:
            send_error_json(handler, "Model name is required")
            return True
        try:
            name = validate_identifier(name, "Model name")
        except ValueError as ve:
            send_error_json(handler, str(ve))
            return True
        final_sql = self._format_saved_sql(body, clean or sql)
        try:
            models_dir = self._workspace.projects._get_models_directory(project)
            target_dir = models_dir / folder if folder and folder != "Ungrouped" else models_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / f"{name}.sql"
            target_file.write_text(final_sql, encoding="utf-8")
            send_json(handler, {"status": "ok", "path": str(target_file)})
        except Exception as e:
            send_error_json(handler, f"Failed to save model: {e}")
        return True

    def _format_saved_sql(self, body: dict[str, Any], sql_text: str) -> str:
        """Combine metadata with SQL query body if separate parameters were provided."""
        if not body.get("materialized") and not body.get("clean_sql"):
            return sql_text
        mat, desc, dest = body.get("materialized", "table"), (body.get("description") or "").replace("'", "\\'"), body.get("destinations", [])
        cfg = [f"materialized='{mat}'"]
        if desc: cfg.append(f"description='{desc}'")
        if body.get("unique_key"): cfg.append(f"unique_key='{body['unique_key']}'")
        if dest: cfg.append(f"destinations={dest if isinstance(dest, list) else [dest]}")
        return f"{{{{ config(\n    {',\n    '.join(cfg)}\n) }}}}\n\n{sql_text.strip()}"

    def _handle_delete_model(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> bool:
        """Remove a model SQL file."""
        project, name = body.get("project", "default"), body.get("name", "").strip()
        if not name:
            send_error_json(handler, "Model name is required")
            return True
        models = self._workspace.projects.load_project_models(project)
        target = next((m for m in models if m.name == name), None)
        if not target or not target.file_path or not target.file_path.exists():
            send_error_json(handler, f"Model '{name}' not found", status_code=404)
            return True
        try:
            target.file_path.unlink()
            send_json(handler, {"status": "ok", "deleted": name})
        except Exception as e:
            send_error_json(handler, f"Failed to delete model: {e}")
        return True

    def _handle_create_pipeline(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> bool:
        """Create a new project / pipeline directory."""
        name = body.get("name", "").strip()
        if not name:
            send_error_json(handler, "Pipeline name is required")
            return True
        try:
            name = validate_identifier(name, "Pipeline name")
            proj_dir = self._workspace.root / "projects" / name / "models"
            proj_dir.mkdir(parents=True, exist_ok=True)
            send_json(handler, {"status": "ok", "created": name})
        except Exception as e:
            send_error_json(handler, f"Failed to create pipeline: {e}")
        return True
