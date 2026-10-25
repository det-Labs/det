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
        if raw_path == "/api/pipelines/running":
            send_json(handler, {
                "running": self._workspace.get_running_pipelines(),
            })
            return True
        if raw_path == "/api/pipelines/dag":
            send_json(handler, self._get_dag(active_query.get("project", ["default"])[0]))
            return True
        if raw_path == "/api/pipelines/model/schema":
            project = active_query.get("project", ["default"])[0]
            model = active_query.get("model", [""])[0]
            send_json(handler, self._get_model_schema(project, model))
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
            "/api/pipelines/delete": self._handle_delete_pipeline,
            "/api/pipelines/model/schema": self._handle_save_model_schema,
            "/api/pipelines/model/assertion/save": self._handle_save_model_assertion,
            "/api/pipelines/model/assertion/delete": self._handle_delete_model_assertion,
        }
        if path in routes:
            return routes[path](handler, body)
        return False

    def _list_pipelines(self) -> list[dict[str, Any]]:
        """List all discovered pipelines and their contained models."""
        pipelines = []
        for proj_name in self._workspace.projects.discover_projects():
            models = self._workspace.projects.load_project_models(proj_name)
            folder = self._workspace.projects.get_project_folder(proj_name)
            explicit_map = self._workspace._load_explicit_tests(proj_name) if hasattr(self._workspace, "_load_explicit_tests") else {}
            pipelines.append({
                "name": proj_name, "folder": folder,
                "description": f"{proj_name.replace('_', ' ').title()} analytics pipeline",
                "models_count": len(models), "models": [self._serialize_model(m, explicit_map=explicit_map) for m in models],
            })
        return pipelines

    def _serialize_model(self, model: ModelDefinition, explicit_map: dict[str, list[Any]] | None = None) -> dict[str, Any]:
        """Convert ModelDefinition into JSON-serializable dictionary."""
        import re
        folder = model.file_path.parent.name if model.file_path and model.file_path.parent.name != "models" else ""
        clean = re.sub(r"\{\{\s*config\s*\((.*?)\)\s*\}\}", "", model.raw_sql, flags=re.DOTALL | re.IGNORECASE).strip()
        dests = [d.path or d.target for d in model.config.destinations if d.target != "local" or d.path]
        tests = self._get_inferred_tests(model, explicit_map=explicit_map)
        return {
            "name": model.name, "project": model.project, "materialized": model.config.materialized.value,
            "folder": folder, "description": model.config.description or model.description,
            "unique_key": model.config.unique_key or "", "destinations": dests,
            "refs": model.refs, "sources": model.sources, "direct_connections": model.direct_connections,
            "raw_sql": model.raw_sql, "clean_sql": clean, "compiled_sql": model.compiled_sql,
            "tests_count": len(tests), "tests": tests,
        }

    def _get_inferred_tests(self, model: ModelDefinition, explicit_map: dict[str, list[Any]] | None = None) -> list[dict[str, Any]]:
        """Extract inferred and declared assertions for model."""
        from det.testing.definitions import TestDefinition
        tests = [
            {"name": t.name, "column": t.column_name, "type": t.test_type.value, "severity": t.severity.value, "origin": "inferred"}
            for t in TestDefinition.infer_from_model(model)
        ]
        if explicit_map is None and hasattr(self._workspace, "_load_explicit_tests"):
            explicit_map = self._workspace._load_explicit_tests(model.project or "default")
        if explicit_map:
            for t in explicit_map.get(model.name, []):
                param_expr = (t.parameters or {}).get("expression", "")
                param_vals = (t.parameters or {}).get("values", [])
                val_str = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in param_vals) if param_vals else ""
                tests.append({
                    "name": t.name,
                    "column": t.column_name,
                    "type": t.test_type.value,
                    "severity": t.severity.value,
                    "origin": "schema.yml",
                    "expression": param_expr,
                    "accepted_values": val_str,
                })
        return tests

    def _get_dag(self, project: str) -> dict[str, Any]:
        """Build and serialize DAG graph nodes and directed edges."""
        dag = self._workspace.projects.build_dag(project)
        nodes, edges, seen_sources = [], [], set()
        explicit_map = self._workspace._load_explicit_tests(project) if hasattr(self._workspace, "_load_explicit_tests") else {}

        for name, model in dag._models.items():
            folder = model.file_path.parent.name if model.file_path and model.file_path.parent.name != "models" else ""
            tests = self._get_inferred_tests(model, explicit_map=explicit_map)
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

        return {"project": project, "nodes": nodes, "edges": edges, "has_cycles": bool(dag.detect_cycles())}

    def _handle_run_pipeline(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> bool:
        """Execute a pipeline or single model and return execution telemetry."""
        project, select = body.get("project", "default"), body.get("select")
        if self._workspace.is_pipeline_running(project):
            send_error_json(
                handler,
                f"Pipeline '{project}' is already running. Parallel runs of the same pipeline are prevented.",
                status_code=409,
            )
            return True
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
        folder = body.get("folder", "").strip()
        if not name:
            send_error_json(handler, "Pipeline name is required")
            return True
        try:
            name = validate_identifier(name, "Pipeline name")
            if folder and folder not in ("Core Pipelines", "Ungrouped"):
                proj_dir = self._workspace.root / "projects" / folder / name / "models"
            else:
                proj_dir = self._workspace.root / "projects" / name / "models"
            proj_dir.mkdir(parents=True, exist_ok=True)
            send_json(handler, {"status": "ok", "created": name, "folder": folder or "Core Pipelines"})
        except Exception as e:
            send_error_json(handler, f"Failed to create pipeline: {e}")
        return True

    def _handle_delete_pipeline(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> bool:
        """Remove an entire pipeline project directory."""
        name = body.get("name", "").strip()
        if not name:
            send_error_json(handler, "Pipeline name is required")
            return True
        try:
            success = self._workspace.delete_pipeline(name)
            if success:
                send_json(handler, {"status": "ok", "deleted": name})
            else:
                send_error_json(handler, f"Pipeline '{name}' not found", status_code=404)
        except Exception as e:
            send_error_json(handler, f"Failed to delete pipeline: {e}")
        return True

    def _resolve_schema_file(self, project: str, model: ModelDefinition | None) -> Path:
        """Locate closest schema.yml file for project or model folder."""
        models_dir = self._workspace.projects._get_models_directory(project)
        if model and model.file_path:
            parent_yml = model.file_path.parent / "schema.yml"
            parent_yaml = model.file_path.parent / "schema.yaml"
            if parent_yml.exists():
                return parent_yml
            if parent_yaml.exists():
                return parent_yaml
        if (models_dir / "schema.yml").exists():
            return models_dir / "schema.yml"
        if (models_dir / "schema.yaml").exists():
            return models_dir / "schema.yaml"
        return models_dir / "schema.yml"

    def _get_model_schema(self, project: str, model_name: str) -> dict[str, Any]:
        """Fetch introspected columns, descriptions from schema.yml, and raw YAML."""
        import yaml
        from det.docs.extractor import DocsExtractor
        models = self._workspace.projects.load_project_models(project)
        model = next((m for m in models if m.name == model_name), None)
        schema_file = self._resolve_schema_file(project, model)

        existing_data = {}
        model_entry = None
        if schema_file.exists():
            try:
                existing_data = yaml.safe_load(schema_file.read_text(encoding="utf-8")) or {}
                for m in existing_data.get("models", []):
                    if isinstance(m, dict) and m.get("name") == model_name:
                        model_entry = m
                        break
            except Exception:
                pass

        extractor = DocsExtractor()
        tests = self._get_inferred_tests(model) if model else []
        m_descs, c_descs = DocsExtractor.load_schema_descriptions(
            self._workspace.projects._get_models_directory(project)
        )

        raw_cols = []
        if model:
            raw_cols = extractor._fetch_describe_schema(self._workspace.engine.session, model)

        seen_cols = set()
        columns = []
        model_col_map = {}
        if model_entry and "columns" in model_entry:
            for c in model_entry.get("columns", []):
                if isinstance(c, dict) and c.get("name"):
                    model_col_map[c["name"]] = c

        for col_name, data_type in raw_cols:
            seen_cols.add(col_name)
            col_info = model_col_map.get(col_name, {})
            desc = col_info.get("description") or c_descs.get(model_name, {}).get(col_name, "")
            badges = [t["type"].upper() for t in tests if t.get("column") == col_name]
            columns.append({
                "name": col_name,
                "data_type": data_type,
                "description": desc,
                "test_badges": badges,
            })

        for col_name, col_info in model_col_map.items():
            if col_name not in seen_cols:
                badges = [t["type"].upper() for t in tests if t.get("column") == col_name]
                columns.append({
                    "name": col_name,
                    "data_type": col_info.get("data_type", "VARCHAR"),
                    "description": col_info.get("description", ""),
                    "test_badges": badges,
                })

        model_desc = ""
        if model_entry and model_entry.get("description"):
            model_desc = model_entry["description"]
        elif model:
            model_desc = model.config.description or model.description or ""

        single_entry = model_entry or {
            "name": model_name,
            "description": model_desc,
            "columns": [{"name": c["name"], "description": c["description"]} for c in columns if c["description"]],
        }
        yaml_content = yaml.safe_dump({"version": 2, "models": [single_entry]}, sort_keys=False)

        return {
            "status": "ok",
            "project": project,
            "model": model_name,
            "description": model_desc,
            "columns": columns,
            "raw_yaml": yaml_content,
            "schema_file": str(schema_file.name),
        }

    def _handle_save_model_schema(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> bool:
        """Update model schema and column descriptions in schema.yml."""
        import yaml
        project = body.get("project", "default")
        model_name = body.get("model", "").strip()
        raw_yaml = body.get("raw_yaml")
        columns = body.get("columns")
        description = body.get("description")

        if not model_name:
            send_error_json(handler, "Model name is required")
            return True

        models = self._workspace.projects.load_project_models(project)
        model = next((m for m in models if m.name == model_name), None)
        schema_file = self._resolve_schema_file(project, model)

        existing_data = {}
        if schema_file.exists():
            try:
                existing_data = yaml.safe_load(schema_file.read_text(encoding="utf-8")) or {}
            except Exception as e:
                send_error_json(handler, f"Existing schema.yml is invalid: {e}")
                return True

        if not isinstance(existing_data, dict):
            existing_data = {}
        if "version" not in existing_data:
            existing_data["version"] = 2
        models_list = existing_data.setdefault("models", [])
        if not isinstance(models_list, list):
            models_list = []
            existing_data["models"] = models_list

        target_model = next((m for m in models_list if isinstance(m, dict) and m.get("name") == model_name), None)

        if raw_yaml is not None:
            try:
                parsed = yaml.safe_load(raw_yaml)
            except Exception as e:
                send_error_json(handler, f"Invalid YAML syntax: {e}", status_code=400)
                return True

            if isinstance(parsed, dict):
                if "models" in parsed and isinstance(parsed["models"], list) and len(parsed["models"]) > 0:
                    new_model_def = parsed["models"][0]
                elif parsed.get("name") == model_name:
                    new_model_def = parsed
                else:
                    new_model_def = {"name": model_name}
            else:
                send_error_json(handler, "YAML root must be a mapping or contain 'models' list", status_code=400)
                return True

            new_model_def["name"] = model_name

            if target_model:
                idx = models_list.index(target_model)
                models_list[idx] = new_model_def
            else:
                models_list.append(new_model_def)
        else:
            if not target_model:
                target_model = {"name": model_name}
                models_list.append(target_model)

            if description is not None:
                target_model["description"] = description.strip()

            if columns is not None and isinstance(columns, list):
                existing_cols = target_model.setdefault("columns", [])
                if not isinstance(existing_cols, list):
                    existing_cols = []
                    target_model["columns"] = existing_cols

                col_map = {c.get("name"): c for c in existing_cols if isinstance(c, dict) and c.get("name")}
                for col_in in columns:
                    cname = col_in.get("name")
                    cdesc = (col_in.get("description") or "").strip()
                    if not cname:
                        continue
                    if cname in col_map:
                        if cdesc:
                            col_map[cname]["description"] = cdesc
                        elif "description" in col_map[cname]:
                            del col_map[cname]["description"]
                    elif cdesc:
                        existing_cols.append({"name": cname, "description": cdesc})

        schema_file.parent.mkdir(parents=True, exist_ok=True)
        schema_file.write_text(yaml.safe_dump(existing_data, sort_keys=False), encoding="utf-8")
        if hasattr(self._workspace, "_explicit_tests_cache"):
            self._workspace._explicit_tests_cache.pop(project, None)

        updated_payload = self._get_model_schema(project, model_name)
        send_json(handler, updated_payload)
        return True

    def _handle_save_model_assertion(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> bool:
        """Add or update an assertion in schema.yml."""
        import yaml
        project = body.get("project", "default")
        model_name = body.get("model", "").strip()
        column_name = body.get("column", "").strip()
        test_type = body.get("type", "expression").strip()
        expression = body.get("expression", "").strip()
        accepted_values = body.get("accepted_values", "")
        severity = body.get("severity", "error").strip()
        old_test_name = body.get("old_test_name")

        if not model_name:
            send_error_json(handler, "Model name is required")
            return True

        models = self._workspace.projects.load_project_models(project)
        model = next((m for m in models if m.name == model_name), None)
        schema_file = self._resolve_schema_file(project, model)

        existing_data = {}
        if schema_file.exists():
            try:
                existing_data = yaml.safe_load(schema_file.read_text(encoding="utf-8")) or {}
            except Exception as e:
                send_error_json(handler, f"Existing schema.yml is invalid: {e}")
                return True

        if not isinstance(existing_data, dict):
            existing_data = {}
        existing_data.setdefault("version", 2)
        models_list = existing_data.setdefault("models", [])
        if not isinstance(models_list, list):
            models_list = []
            existing_data["models"] = models_list

        target_model = next((m for m in models_list if isinstance(m, dict) and m.get("name") == model_name), None)
        if not target_model:
            target_model = {"name": model_name}
            models_list.append(target_model)

        # Build new test entry
        if test_type == "not_null":
            new_test = "not_null" if severity == "error" else {"not_null": {"severity": severity}}
        elif test_type == "unique":
            new_test = "unique" if severity == "error" else {"unique": {"severity": severity}}
        elif test_type == "accepted_values":
            if isinstance(accepted_values, str):
                vals = [v.strip().strip("'\"") for v in accepted_values.split(",") if v.strip()]
            else:
                vals = list(accepted_values)
            new_test = {"accepted_values": {"values": vals}}
            if severity != "error":
                new_test["accepted_values"]["severity"] = severity
        else:  # expression
            new_test = {"expression": expression}
            if severity != "error":
                new_test["severity"] = severity

        # Target column tests or model tests
        if column_name:
            cols = target_model.setdefault("columns", [])
            target_col = next((c for c in cols if isinstance(c, dict) and c.get("name") == column_name), None)
            if not target_col:
                target_col = {"name": column_name}
                cols.append(target_col)
            tests_list = target_col.setdefault("tests", [])

            # Remove old test if editing
            if old_test_name:
                tests_list = [t for t in tests_list if not self._test_matches(t, old_test_name, test_type, column_name, model_name)]
            tests_list.append(new_test)
            target_col["tests"] = tests_list
        else:
            tests_list = target_model.setdefault("tests", [])
            if old_test_name:
                tests_list = [t for t in tests_list if not self._test_matches(t, old_test_name, test_type, "", model_name)]
            tests_list.append(new_test)
            target_model["tests"] = tests_list

        schema_file.parent.mkdir(parents=True, exist_ok=True)
        schema_file.write_text(yaml.safe_dump(existing_data, sort_keys=False), encoding="utf-8")
        if hasattr(self._workspace, "_explicit_tests_cache"):
            self._workspace._explicit_tests_cache.pop(project, None)

        send_json(handler, {"status": "ok", "message": "Assertion saved successfully"})
        return True

    def _handle_delete_model_assertion(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> bool:
        """Delete an assertion from schema.yml."""
        import yaml
        project = body.get("project", "default")
        model_name = body.get("model", "").strip()
        column_name = body.get("column", "").strip()
        test_name = body.get("test_name", "").strip()
        test_type = body.get("type", "").strip()

        if not model_name or not test_name:
            send_error_json(handler, "Model name and test name are required")
            return True

        models = self._workspace.projects.load_project_models(project)
        model = next((m for m in models if m.name == model_name), None)
        schema_file = self._resolve_schema_file(project, model)

        if not schema_file.exists():
            send_error_json(handler, "schema.yml not found")
            return True

        try:
            existing_data = yaml.safe_load(schema_file.read_text(encoding="utf-8")) or {}
        except Exception as e:
            send_error_json(handler, f"Invalid schema.yml: {e}")
            return True

        models_list = existing_data.get("models", [])
        target_model = next((m for m in models_list if isinstance(m, dict) and m.get("name") == model_name), None)
        if not target_model:
            send_error_json(handler, f"Model '{model_name}' not found in schema.yml")
            return True

        removed = False
        if column_name:
            for col in target_model.get("columns", []):
                if isinstance(col, dict) and col.get("name") == column_name:
                    tests = col.get("tests", [])
                    new_tests = [t for t in tests if not self._test_matches(t, test_name, test_type, column_name, model_name)]
                    if len(new_tests) != len(tests):
                        col["tests"] = new_tests
                        removed = True
                    break
        else:
            tests = target_model.get("tests", [])
            new_tests = [t for t in tests if not self._test_matches(t, test_name, test_type, "", model_name)]
            if len(new_tests) != len(tests):
                target_model["tests"] = new_tests
                removed = True

        if not removed:
            for col in target_model.get("columns", []):
                if isinstance(col, dict):
                    tests = col.get("tests", [])
                    new_tests = [t for t in tests if not self._test_matches(t, test_name, test_type, col.get("name", ""), model_name)]
                    if len(new_tests) != len(tests):
                        col["tests"] = new_tests
                        removed = True

        schema_file.write_text(yaml.safe_dump(existing_data, sort_keys=False), encoding="utf-8")
        if hasattr(self._workspace, "_explicit_tests_cache"):
            self._workspace._explicit_tests_cache.pop(project, None)

        send_json(handler, {"status": "ok", "message": f"Assertion '{test_name}' deleted"})
        return True

    def _test_matches(self, test_item: Any, test_name: str, test_type: str, col_name: str, model_name: str) -> bool:
        """Check if YAML test definition matches test_name and type."""
        if isinstance(test_item, str):
            if test_item == test_type:
                return True
            expected_name = f"{model_name}_{col_name}_{test_item}"
            return test_name == expected_name or test_item == test_name
        if isinstance(test_item, dict):
            for k in test_item:
                if k == test_type:
                    return True
                expected_name = f"{model_name}_{col_name}_{k}"
                if test_name == expected_name or test_item.get("name") == test_name:
                    return True
        return False
        return True
