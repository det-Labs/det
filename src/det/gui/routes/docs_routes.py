"""HTTP route handlers for Data Dictionary, Lineage, and Documentation Portal."""

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler
from typing import Any
import urllib.parse

from det.docs.base import ProjectDoc
from det.docs.extractor import DocsExtractor
from det.docs.lineage import LineageGenerator
from det.gui.routes.common import send_error_json, send_json
from det.testing.definitions import TestDefinition
from det.workspace import Workspace


class DocsRouteHandler:
    """Manages data dictionary, metadata extraction, and static docs generation."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace
        self._extractor = DocsExtractor()
        self._lineage_gen = LineageGenerator()

    def handle_get(
        self, handler: BaseHTTPRequestHandler, path: str, query: dict[str, list[str]] | None = None
    ) -> bool:
        """Route GET requests for documentation metadata and project data dictionary."""
        raw_path = path.split("?")[0]
        parsed_url = urllib.parse.urlparse(handler.path)
        active_query = query or urllib.parse.parse_qs(parsed_url.query)

        if raw_path == "/api/docs/content":
            project = active_query.get("project", ["default"])[0]
            send_json(handler, self._get_docs_payload(project))
            return True
        return False

    def handle_post(
        self, handler: BaseHTTPRequestHandler, path: str, body: dict[str, Any]
    ) -> bool:
        """Route POST requests for compiling static documentation packages."""
        if path == "/api/docs/generate":
            project = body.get("project", "default")
            try:
                out_path = self._workspace.generate_docs(project=project)
                send_json(handler, {"status": "ok", "path": str(out_path)})
            except Exception as e:
                send_error_json(handler, f"Docs generation failed: {e}")
            return True
        if path == "/api/docs/delete":
            project = body.get("project", "default")
            try:
                deleted = self._workspace.delete_docs(project=project)
                send_json(handler, {"status": "ok", "deleted": deleted, "project": project})
            except Exception as e:
                send_error_json(handler, f"Docs deletion failed: {e}")
            return True
        if path == "/api/docs/column/description":
            project, model = body.get("project", "default"), body.get("model", "")
            column, desc = body.get("column", ""), body.get("description", "").strip()
            try:
                self._update_column_description(project, model, column, desc)
                send_json(handler, {"status": "ok", "project": project, "model": model, "column": column, "description": desc})
            except Exception as e:
                send_error_json(handler, f"Failed to update column description: {e}")
            return True
        return False

    def _get_docs_payload(self, project: str) -> dict[str, Any]:
        """Extract project documentation models, column schemas, and tests."""
        try:
            dag = self._workspace.projects.build_dag(project)
            models = self._workspace.projects.load_project_models(project)
            all_tests = self._collect_all_tests(project, models)
            models_dir = self._workspace.projects._get_models_directory(project)
            m_descs, c_descs = DocsExtractor.load_schema_descriptions(models_dir)
            model_docs = [
                self._extractor.extract_model_doc(
                    self._workspace.engine.session, m, all_tests, catalog=self._workspace.catalog,
                    column_descriptions=c_descs.get(m.name, {}),
                    model_description=m_descs.get(m.name),
                )
                for m in models
            ]
            lineage = self._lineage_gen.generate_mermaid(dag)
            dest_count = sum(len(m.config.destinations) for m in models if m.config.destinations and (m.config.destinations[0].target != "local" or m.config.destinations[0].path))

            proj_doc = ProjectDoc(
                project_name=project, version="0.1.0",
                description=f"Automated pipeline documentation for {project}",
                total_models=len(models), total_sources=len(dag._dependencies),
                total_tests=len(all_tests), models=model_docs, lineage_mermaid=lineage,
            )
            payload = asdict(proj_doc)
            payload["destinations_count"] = dest_count
            payload["dag"] = self._build_dag_dict(dag, project)
            return payload
        except Exception as e:
            return {"project_name": project, "error": str(e), "models": [], "total_models": 0, "total_sources": 0, "total_tests": 0}

    def _collect_all_tests(self, project: str, models: list[Any]) -> list[TestDefinition]:
        """Collect all inferred and declared data quality assertions."""
        all_tests: list[TestDefinition] = []
        for m in models:
            all_tests.extend(TestDefinition.infer_from_model(m))
        if hasattr(self._workspace, "_load_explicit_tests"):
            explicit_map = self._workspace._load_explicit_tests(project)
            for t_list in explicit_map.values():
                all_tests.extend([TestDefinition.from_dict("model", t) if isinstance(t, dict) else t for t in t_list])
        return all_tests

    def _build_dag_dict(self, dag: Any, project: str) -> dict[str, Any]:
        """Build lightweight DAG node and edge topology for visual rendering."""
        nodes, edges, seen_sources = [], [], set()
        for name, model in dag._models.items():
            nodes.append({
                "id": name, "name": name, "type": "model",
                "materialized": model.config.materialized.value,
                "dependencies": sorted(model.all_dependencies),
            })
            for dep in model.all_dependencies:
                edges.append({"from": dep, "to": name})
                if dep not in dag._models and dep not in seen_sources:
                    seen_sources.add(dep)
                    nodes.append({"id": dep, "name": dep, "type": "source", "materialized": "source", "dependencies": []})
        return {"project": project, "nodes": nodes, "edges": edges}

    def _update_column_description(self, project: str, model_name: str, col_name: str, description: str) -> None:
        """Persist updated column description to project schema.yml."""
        models_dir = self._workspace.projects._get_models_directory(project)
        schema_file = models_dir / "schema.yml"
        import yaml
        data = {}
        if schema_file.exists():
            try:
                data = yaml.safe_load(schema_file.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}
        if "version" not in data:
            data["version"] = 2
        models = data.setdefault("models", [])
        target_model = next((m for m in models if m.get("name") == model_name), None)
        if not target_model:
            target_model = {"name": model_name, "columns": []}
            models.append(target_model)
        cols = target_model.setdefault("columns", [])
        target_col = next((c for c in cols if c.get("name") == col_name), None)
        if not target_col:
            cols.append({"name": col_name, "description": description})
        else:
            target_col["description"] = description
        schema_file.parent.mkdir(parents=True, exist_ok=True)
        schema_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
