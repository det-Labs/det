"""Local HTTP server for the modular browser UI."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from det.api import (
    configure_ui,
    delete_pipeline,
    get_catalog_store,
    get_connector_metadata,
    get_monitoring_store,
    get_monitoring_summary,
    get_pipeline,
    get_pipeline_run,
    get_pipeline_store,
    get_ui_state,
    infer_connection_schema,
    list_pipeline_folders,
    list_pipeline_runs,
    list_pipelines,
    preview_connection,
    run_pipeline,
    save_pipeline,
    update_ui_state,
    validate_pipeline,
    validate_step_sql,
    generate_pipeline_docs,
    save_pipeline_docs,
    list_pipeline_docs,
    get_pipeline_doc,
    delete_pipeline_doc,
    regenerate_pipeline_doc,
    verify_pipeline_doc_sync,
)

UI_DIRECTORY = Path(__file__).parent / "ui"
HOST = "127.0.0.1"


class DetRequestHandler(BaseHTTPRequestHandler):
    """Serve the bundled UI and expose the public Python UI API."""

    def do_GET(self) -> None:
        try:
            request = urlsplit(self.path)
            path = request.path
            query = parse_qs(request.query)

            # --- State & Metadata ---
            if path == "/api/state":
                self._send_json(200, get_ui_state())
            elif path == "/api/catalogs":
                self._send_json(200, get_catalog_store().describe_catalogs())
            elif path == "/api/catalog":
                self._send_json(200, get_catalog_store().read())
            elif path == "/api/connectors":
                self._send_json(200, {"items": get_connector_metadata()})

            # --- Catalog Connections ---
            elif path.startswith("/api/catalog/connections/"):
                parts = path.strip("/").split("/")
                connection_id = parts[3]
                if len(parts) == 5 and parts[4] == "preview":
                    self._send_json(200, preview_connection(connection_id))
                elif len(parts) == 4:
                    self._send_json(200, get_catalog_store().get_connection(connection_id))
                else:
                    self._send_json(404, {"error": "Not found"})

            # --- Pipelines ---
            elif path == "/api/pipelines":
                folder = query.get("folder", [None])[0]
                self._send_json(
                    200,
                    {
                        "folders": list_pipeline_folders(),
                        "items": list_pipelines(folder=folder),
                    },
                )
            elif path.startswith("/api/pipelines/item/"):
                identifier = unquote(path[len("/api/pipelines/item/") :])
                self._send_json(200, get_pipeline(identifier))

            # --- Monitoring ---
            elif path == "/api/monitoring/summary":
                self._send_json(200, get_monitoring_summary())
            elif path == "/api/monitoring/runs":
                pipeline_id = query.get("pipeline_id", [None])[0]
                pipeline_name = query.get("pipeline_name", [None])[0]
                folder = query.get("folder", [None])[0]
                status = query.get("status", [None])[0]
                date_from = query.get("date_from", [None])[0]
                date_to = query.get("date_to", [None])[0]
                limit = int(query.get("limit", [50])[0])
                self._send_json(
                    200,
                    {
                        "items": list_pipeline_runs(
                            pipeline_id=pipeline_id,
                            pipeline_name=pipeline_name,
                            folder=folder,
                            status=status,
                            date_from=date_from,
                            date_to=date_to,
                            limit=limit,
                        )
                    },
                )
            elif path.startswith("/api/monitoring/runs/"):
                run_id = unquote(path[len("/api/monitoring/runs/") :])
                self._send_json(200, get_pipeline_run(run_id))
            elif path.startswith("/api/monitoring/pipelines/"):
                pipeline_ident = unquote(path[len("/api/monitoring/pipelines/") :])
                self._send_json(200, get_monitoring_store().get_pipeline_log(pipeline_ident))

            # --- Documentation ---
            elif path == "/api/docs":
                self._send_json(200, list_pipeline_docs())
            elif path.startswith("/api/docs/verify/"):
                doc_ident = unquote(path[len("/api/docs/verify/") :])
                self._send_json(200, verify_pipeline_doc_sync(doc_ident))
            elif path.startswith("/api/docs/item/"):
                doc_ident = unquote(path[len("/api/docs/item/") :])
                self._send_json(200, get_pipeline_doc(doc_ident))

            # --- Static UI Assets ---
            elif path in ("/", "/index.html"):
                self._send_file("index.html", "text/html; charset=utf-8")
            elif path == "/styles.css":
                self._send_file("styles.css", "text/css; charset=utf-8")
            elif path == "/app.js":
                self._send_file("app.js", "text/javascript; charset=utf-8")
            elif path == "/help-data.js":
                self._send_file("help-data.js", "text/javascript; charset=utf-8")
            elif path == "/mermaid.min.js":
                self._send_file("mermaid.min.js", "text/javascript; charset=utf-8")
            elif path.startswith("/api/docs/download/"):
                doc_ident = unquote(path[len("/api/docs/download/") :])
                workspace = Path(get_ui_state()["workspace"]).resolve()
                clean_rel = doc_ident.strip().replace("\\", "/").lstrip("/")
                doc_file = (workspace / "documentation" / clean_rel).resolve()
                if doc_file.is_file() and str(doc_file).lower().startswith(str(workspace).lower()):
                    content_type = "text/html; charset=utf-8" if doc_file.suffix == ".html" else "text/markdown; charset=utf-8"
                    data = doc_file.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Disposition", f'attachment; filename="{doc_file.name}"')
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self._send_json(404, {"error": "Documentation file not found"})
            elif path.startswith("/documentation/"):
                workspace = Path(get_ui_state()["workspace"]).resolve()
                rel_path = path.lstrip("/")
                doc_file = (workspace / rel_path).resolve()
                if doc_file.is_file() and str(doc_file).lower().startswith(str(workspace).lower()):
                    content_type = "text/html; charset=utf-8" if doc_file.suffix == ".html" else "text/markdown; charset=utf-8"
                    data = doc_file.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    self._send_json(404, {"error": "Documentation file not found"})
            else:
                self._send_json(404, {"error": "Not found"})

        except FileNotFoundError as error:
            self._send_json(404, {"error": str(error)})
        except (TypeError, ValueError, OSError) as error:
            self._send_json(400, {"error": str(error)})

    def do_POST(self) -> None:
        try:
            payload = self._read_json_body()
            path = urlsplit(self.path).path

            # --- Shell State ---
            if path == "/api/state":
                result = update_ui_state(
                    module=payload.get("module"),
                    theme=payload.get("theme"),
                )

            # --- Catalog CRUD ---
            elif path == "/api/catalogs":
                result = get_catalog_store().create_catalog(payload.get("name", ""))
            elif path == "/api/catalog/folders":
                result = get_catalog_store().add_folder(payload.get("name", ""))
            elif path.startswith("/api/catalog/folders/") and path.endswith("/connections"):
                parts = path.strip("/").split("/")
                result = get_catalog_store().add_connection(
                    parts[3],
                    payload,
                )
            elif path.startswith("/api/catalog/connections/") and path.endswith("/infer-schema"):
                connection_id = path.strip("/").split("/")[3]
                result = infer_connection_schema(connection_id)

            # --- Pipeline CRUD & Execution ---
            elif path == "/api/pipelines":
                result = save_pipeline(payload)
            elif path == "/api/pipelines/folders":
                result = {"folder": get_pipeline_store().create_folder(payload.get("name", ""))}
            elif path == "/api/pipelines/validate":
                target = payload.get("pipeline", payload) if isinstance(payload, dict) and "pipeline" in payload else payload
                result = validate_pipeline(target)
            elif path == "/api/pipelines/validate-sql":
                result = validate_step_sql(
                    payload.get("sql", ""),
                    catalog_file=payload.get("catalog_file", "default.yaml"),
                    prior_steps=payload.get("prior_steps"),
                )
            elif path == "/api/pipelines/run":
                target = payload.get("pipeline", payload) if isinstance(payload, dict) else payload
                result = run_pipeline(target)
            elif path == "/api/pipelines/docs":
                target = payload.get("pipeline", payload) if isinstance(payload, dict) and "pipeline" in payload else payload
                doc_format = payload.get("format", "html") if isinstance(payload, dict) else "html"
                result = save_pipeline_docs(target, doc_format=doc_format)
            elif path == "/api/docs/regenerate":
                rel_path = payload.get("rel_path") or payload.get("path", "")
                doc_format = payload.get("format")
                result = regenerate_pipeline_doc(rel_path, doc_format=doc_format)
            elif path == "/api/docs/verify-sync":
                rel_path = payload.get("rel_path") or payload.get("path", "")
                result = verify_pipeline_doc_sync(rel_path)

            # --- Sample Data ---
            elif path in ("/api/sample-data/install", "/api/sample-data"):
                from det.api import install_sample_data
                result = install_sample_data(select_catalog=True)

            else:
                self._send_json(404, {"error": "Not found"})
                return

            self._send_json(200, result)

        except FileNotFoundError as error:
            self._send_json(404, {"error": str(error)})
        except (json.JSONDecodeError, TypeError, ValueError, OSError) as error:
            self._send_json(400, {"error": str(error)})

    def do_PUT(self) -> None:
        try:
            payload = self._read_json_body()
            path = urlsplit(self.path).path

            if path == "/api/state":
                result = update_ui_state(
                    module=payload.get("module"),
                    theme=payload.get("theme"),
                )
            elif path == "/api/catalogs/active":
                result = get_catalog_store().select(payload.get("filename", ""))
            elif path == "/api/catalog":
                result = get_catalog_store().save_yaml(payload.get("content", ""))
            elif path == "/api/catalog/name":
                result = get_catalog_store().rename_catalog(payload.get("name", ""))
            elif path.startswith("/api/catalog/folders/"):
                folder_id = path.strip("/").split("/")[3]
                result = get_catalog_store().update_folder(folder_id, payload.get("name", ""))
            elif path.startswith("/api/catalog/connections/"):
                connection_id = path.strip("/").split("/")[3]
                result = get_catalog_store().update_connection(connection_id, payload)

            # --- Pipelines ---
            elif path.startswith("/api/pipelines/item/"):
                result = save_pipeline(payload)
            elif path.startswith("/api/pipelines/folders/"):
                folder_name = unquote(path.strip("/").split("/")[3])
                result = {
                    "folder": get_pipeline_store().rename_folder(
                        folder_name, payload.get("name", "")
                    )
                }

            else:
                self._send_json(404, {"error": "Not found"})
                return

            self._send_json(200, result)

        except FileNotFoundError as error:
            self._send_json(404, {"error": str(error)})
        except (json.JSONDecodeError, TypeError, ValueError, OSError) as error:
            self._send_json(400, {"error": str(error)})

    def do_DELETE(self) -> None:
        path = urlsplit(self.path).path
        try:
            if path.startswith("/api/catalog/folders/"):
                folder_id = path.strip("/").split("/")[3]
                result = get_catalog_store().delete_folder(folder_id)
            elif path.startswith("/api/catalog/connections/"):
                connection_id = path.strip("/").split("/")[3]
                result = get_catalog_store().delete_connection(connection_id)

            # --- Pipelines ---
            elif path.startswith("/api/pipelines/item/"):
                identifier = unquote(path[len("/api/pipelines/item/") :])
                result = {"deleted": delete_pipeline(identifier)}
            elif path.startswith("/api/pipelines/folders/"):
                folder_name = unquote(path.strip("/").split("/")[3])
                result = {"deleted": get_pipeline_store().delete_folder(folder_name)}
            elif path.startswith("/api/docs/item/"):
                doc_ident = unquote(path[len("/api/docs/item/") :])
                result = delete_pipeline_doc(doc_ident)

            else:
                self._send_json(404, {"error": "Not found"})
                return

            self._send_json(200, result)

        except FileNotFoundError as error:
            self._send_json(404, {"error": str(error)})
        except (TypeError, ValueError, OSError) as error:
            self._send_json(400, {"error": str(error)})

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length > 1_048_576:
            raise ValueError("Request body is too large.")
        payload: Any = json.loads(self.rfile.read(content_length) or b"{}")
        if not isinstance(payload, (dict, list, str)):
            raise ValueError("Request body must be valid JSON.")
        return payload

    def _send_file(self, filename: str, content_type: str) -> None:
        content = (UI_DIRECTORY / filename).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        content = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[det] {self.address_string()} - {format % args}")


def serve_gui(workspace: str | Path, port: int) -> None:
    """Serve the UI for an initialized workspace until interrupted."""
    configure_ui(workspace)
    server = ThreadingHTTPServer((HOST, port), DetRequestHandler)
    print(f"det GUI: http://{HOST}:{server.server_port} (workspace: {Path(workspace).resolve()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping det GUI.")
    finally:
        server.server_close()
