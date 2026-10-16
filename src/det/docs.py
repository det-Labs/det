"""det.docs - Automatic single-file documentation generator with lineage tracking.

Generates self-contained dbt-style HTML or Markdown documentation from pipeline definitions,
step SQL notes, catalog metadata, and DataFusion-inferred Arrow schemas.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from det.catalog import CatalogStore
from det.connectors import connector_definitions
from det.pipeline import Pipeline, PipelineStore
from det.validator import PipelineValidator


class PipelineDocsGenerator:
    """Generates comprehensive, single-file pipeline documentation in HTML or Markdown."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.catalog_store = CatalogStore(self.workspace)
        self.pipeline_store = PipelineStore(self.workspace)
        self.validator = PipelineValidator(self.workspace)

    def save(
        self,
        pipeline_input: str | dict[str, Any] | Pipeline,
        doc_format: str = "html",
    ) -> dict[str, Any]:
        """Generate and save documentation directly into workspace's documentation/<folder>/<name>.<ext>."""
        if isinstance(pipeline_input, str):
            p_data = self.pipeline_store.get_pipeline(pipeline_input)
            pipeline = Pipeline.model_validate(p_data)
        elif isinstance(pipeline_input, dict):
            pipeline = Pipeline.model_validate(pipeline_input)
        else:
            pipeline = pipeline_input

        content = self.generate(pipeline, doc_format=doc_format)
        ext = "md" if doc_format in ("markdown", "md") else "html"
        rel_folder = pipeline.folder or "default"
        rel_path = Path("documentation") / rel_folder / f"{pipeline.name}.{ext}"
        dest_path = self.workspace / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(content, encoding="utf-8")

        return {
            "saved_path": str(rel_path.as_posix()),
            "path": str(rel_path.as_posix()),
            "absolute_path": str(dest_path),
            "folder": rel_folder,
            "pipeline_name": pipeline.name,
            "filename": f"{pipeline.name}.{ext}",
            "format": ext,
            "bytes": len(content.encode("utf-8")),
            "bytes_written": len(content.encode("utf-8")),
            "content": content,
        }

    def list_docs(self) -> dict[str, Any]:
        """Scan documentation directories and list all generated documents."""
        docs_dir = self.workspace / "documentation"
        items: list[dict[str, Any]] = []
        folders_set: set[str] = set()

        if docs_dir.is_dir():
            for doc_file in sorted(docs_dir.glob("**/*")):
                if doc_file.is_file() and doc_file.suffix.lower() in (".html", ".md"):
                    rel_to_docs = doc_file.relative_to(docs_dir)
                    folder = str(rel_to_docs.parent).replace("\\", "/") if rel_to_docs.parent != Path(".") else ""
                    filename = doc_file.name
                    stem = doc_file.stem
                    ext = doc_file.suffix.lower().lstrip(".")
                    stat = doc_file.stat()
                    mod_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                    rel_path = f"{folder}/{filename}" if folder else filename
                    pipeline_key = f"{folder}/{stem}" if folder else stem

                    if folder:
                        folders_set.add(folder)

                    items.append({
                        "rel_path": rel_path,
                        "folder": folder,
                        "filename": filename,
                        "name": stem,
                        "format": ext,
                        "size_bytes": stat.st_size,
                        "modified_at": mod_iso,
                        "pipeline_key": pipeline_key,
                    })

        sorted_folders = sorted(folders_set)
        return {
            "total": len(items),
            "items": items,
            "folders": sorted_folders,
        }

    def get_doc(self, rel_path: str) -> dict[str, Any]:
        """Read content and metadata of a documentation file."""
        clean_rel = rel_path.strip().replace("\\", "/").lstrip("/")
        docs_dir = self.workspace / "documentation"
        target_path = (docs_dir / clean_rel).resolve()

        if not target_path.is_file() or not str(target_path).lower().startswith(str(docs_dir.resolve()).lower()):
            raise FileNotFoundError(f"Documentation file not found: {rel_path}")

        ext = target_path.suffix.lower().lstrip(".")
        content = target_path.read_text(encoding="utf-8")
        stat = target_path.stat()
        mod_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        rel_to_docs = target_path.relative_to(docs_dir)
        folder = str(rel_to_docs.parent).replace("\\", "/") if rel_to_docs.parent != Path(".") else ""

        return {
            "rel_path": clean_rel,
            "folder": folder,
            "filename": target_path.name,
            "name": target_path.stem,
            "format": ext,
            "size_bytes": stat.st_size,
            "modified_at": mod_iso,
            "content": content,
        }

    def delete_doc(self, rel_path: str) -> dict[str, Any]:
        """Delete a generated documentation file."""
        clean_rel = rel_path.strip().replace("\\", "/").lstrip("/")
        docs_dir = self.workspace / "documentation"
        target_path = (docs_dir / clean_rel).resolve()

        if not target_path.is_file() or not str(target_path).lower().startswith(str(docs_dir.resolve()).lower()):
            raise FileNotFoundError(f"Documentation file not found: {rel_path}")

        target_path.unlink()

        # If parent folder is now empty (and not docs_dir itself), remove it
        parent = target_path.parent
        if parent != docs_dir.resolve():
            try:
                if not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass

        return {"deleted": True, "rel_path": clean_rel}

    def regenerate_doc(self, rel_path: str, doc_format: str | None = None) -> dict[str, Any]:
        """Regenerate an existing documentation file from its pipeline definition."""
        clean_rel = rel_path.strip().replace("\\", "/").lstrip("/")
        p = Path(clean_rel)
        ext = doc_format or ("md" if p.suffix.lower() == ".md" else "html")
        folder = str(p.parent).replace("\\", "/") if p.parent != Path(".") else ""
        stem = p.stem

        pipeline_target = f"{folder}/{stem}" if folder else stem
        try:
            p_data = self.pipeline_store.get_pipeline(pipeline_target)
        except Exception:
            all_pipelines = self.pipeline_store.list_pipelines()
            match = next((item for item in all_pipelines if item.get("name") == stem), None)
            if not match:
                raise FileNotFoundError(f"Pipeline definition for '{clean_rel}' not found.")
            p_data = self.pipeline_store.get_pipeline(match.get("id") or f"{match.get('folder')}/{match.get('name')}")

        return self.save(p_data, doc_format=ext)

    def verify_staleness(self, rel_path: str) -> dict[str, Any]:
        """Check if a documentation file is out of sync with its pipeline definition or catalog."""
        clean_rel = rel_path.strip().replace("\\", "/").lstrip("/")
        docs_dir = self.workspace / "documentation"
        doc_file = (docs_dir / clean_rel).resolve()
        if not doc_file.is_file():
            raise FileNotFoundError(f"Documentation file not found: {rel_path}")

        doc_stat = doc_file.stat()
        doc_mtime = doc_stat.st_mtime
        doc_mod_iso = datetime.fromtimestamp(doc_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        p = Path(clean_rel)
        folder = str(p.parent).replace("\\", "/") if p.parent != Path(".") else ""
        stem = p.stem

        pipeline_target = f"{folder}/{stem}" if folder else stem
        pipeline_file: Path | None = None
        pipeline_name = stem
        catalog_name = "default.yaml"
        try:
            p_data = self.pipeline_store.get_pipeline(pipeline_target)
            pipe_folder = p_data.get("folder", folder)
            pipe_name = p_data.get("name", stem)
            pipeline_name = pipe_name
            catalog_name = p_data.get("catalog", "default.yaml")
            target_path = self.workspace / "pipelines" / pipe_folder / f"{pipe_name}.yaml"
            if target_path.is_file():
                pipeline_file = target_path
            elif (self.workspace / "pipelines" / f"{pipe_name}.yaml").is_file():
                pipeline_file = self.workspace / "pipelines" / f"{pipe_name}.yaml"
        except Exception:
            all_pipes = self.pipeline_store.list_pipelines()
            match = next((item for item in all_pipes if item.get("name") == stem), None)
            if match:
                pipe_folder = match.get("folder", "")
                pipe_name = match.get("name", stem)
                pipeline_name = pipe_name
                catalog_name = match.get("catalog", "default.yaml")
                cand = self.workspace / "pipelines" / pipe_folder / f"{pipe_name}.yaml"
                if cand.is_file():
                    pipeline_file = cand

        if not pipeline_file or not pipeline_file.is_file():
            return {
                "rel_path": clean_rel,
                "pipeline_name": pipeline_name,
                "is_stale": True,
                "reason": "Associated pipeline definition could not be located in workspace.",
                "doc_modified_at": doc_mod_iso,
                "pipeline_modified_at": None,
            }

        pipe_stat = pipeline_file.stat()
        pipe_mtime = pipe_stat.st_mtime
        pipe_mod_iso = datetime.fromtimestamp(pipe_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        catalog_is_newer = False
        catalog_mod_iso = None
        cat_file = self.workspace / "catalog" / catalog_name
        if cat_file.is_file():
            cat_stat = cat_file.stat()
            if cat_stat.st_mtime > doc_mtime + 1.0:
                catalog_is_newer = True
                catalog_mod_iso = datetime.fromtimestamp(cat_stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        if pipe_mtime > doc_mtime + 1.0:
            return {
                "rel_path": clean_rel,
                "pipeline_name": pipeline_name,
                "is_stale": True,
                "reason": f"Pipeline definition was modified ({pipe_mod_iso}) after documentation was generated ({doc_mod_iso}).",
                "doc_modified_at": doc_mod_iso,
                "pipeline_modified_at": pipe_mod_iso,
            }
        elif catalog_is_newer:
            return {
                "rel_path": clean_rel,
                "pipeline_name": pipeline_name,
                "is_stale": True,
                "reason": f"Catalog '{catalog_name}' was modified ({catalog_mod_iso}) after documentation was generated ({doc_mod_iso}).",
                "doc_modified_at": doc_mod_iso,
                "pipeline_modified_at": pipe_mod_iso,
            }

        return {
            "rel_path": clean_rel,
            "pipeline_name": pipeline_name,
            "is_stale": False,
            "reason": "Documentation is up to date with the pipeline definition and catalog.",
            "doc_modified_at": doc_mod_iso,
            "pipeline_modified_at": pipe_mod_iso,
        }

    def generate(
        self,
        pipeline_input: str | dict[str, Any] | Pipeline,
        doc_format: str = "html",
    ) -> str:
        """Generate documentation in 'html' or 'markdown' / 'md' format."""
        if isinstance(pipeline_input, str):
            p_data = self.pipeline_store.get_pipeline(pipeline_input)
            pipeline = Pipeline.model_validate(p_data)
        elif isinstance(pipeline_input, dict):
            pipeline = Pipeline.model_validate(pipeline_input)
        else:
            pipeline = pipeline_input

        # Pipeline file timestamps
        pipe_folder = pipeline.folder or "default"
        target_path = self.workspace / "pipelines" / pipe_folder / f"{pipeline.name}.yaml"
        if not target_path.is_file():
            target_path = self.workspace / "pipelines" / f"{pipeline.name}.yaml"

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        if target_path.is_file():
            stat = target_path.stat()
            created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            created_at = now_str
            modified_at = now_str

        meta = {
            "pipeline_id": pipeline.id,
            "created_at": created_at,
            "modified_at": modified_at,
            "gen_time": now_str,
        }

        # 1. Load catalog & connections
        catalog_file = pipeline.catalog or "default.yaml"
        try:
            catalog_doc = self.catalog_store.select(catalog_file)["catalog"]
        except Exception:
            catalog_doc = {"name": catalog_file, "folders": []}

        all_connections: dict[str, dict[str, Any]] = {}
        column_descriptions: dict[str, str] = {}
        for folder in catalog_doc.get("folders", []):
            for conn in folder.get("connections", []):
                all_connections[conn["name"]] = conn
                all_connections[conn["id"]] = conn
                for col in conn.get("columns", []):
                    if col.get("description"):
                        column_descriptions[col["name"].lower()] = col["description"]

        connectors = {c.guid: c for c in connector_definitions()}

        # 2. Derive schemas and analyze lineage dependencies per step
        steps_info: list[dict[str, Any]] = []
        prior_steps_context: list[dict[str, Any]] = []
        pipeline_sources: set[str] = set()
        pipeline_destinations: set[str] = set()

        for idx, step in enumerate(pipeline.steps):
            clean_step_id = re.sub(r"\W+", "_", step.name)
            step_sources = [
                name
                for name, conn in all_connections.items()
                if conn.get("is_source")
                and name == conn.get("name")
                and re.search(rf"\b{re.escape(name)}\b", step.sql, re.IGNORECASE)
            ]
            step_prior_refs = [
                s["name"]
                for s in prior_steps_context
                if re.search(rf"\b{re.escape(s['name'])}\b", step.sql, re.IGNORECASE)
            ]

            pipeline_sources.update(step_sources)
            pipeline_destinations.update(step.destinations)

            val_res = self.validator.validate_step_sql(
                step.sql,
                catalog_file=catalog_file,
                prior_steps=prior_steps_context,
            )

            schema_cols: list[dict[str, Any]] = []
            if val_res.get("valid") and val_res.get("schema"):
                for col in val_res["schema"]:
                    desc = column_descriptions.get(col["name"].lower(), "")
                    schema_cols.append({
                        "name": col["name"],
                        "data_type": col["data_type"],
                        "nullable": col.get("nullable", True),
                        "description": desc,
                    })

            steps_info.append({
                "index": idx + 1,
                "name": step.name,
                "clean_id": clean_step_id,
                "description": step.description or "",
                "sql": step.sql.strip(),
                "destinations": step.destinations,
                "keep_temporary": step.keep_temporary,
                "sources": sorted(step_sources),
                "prior_steps": sorted(step_prior_refs),
                "schema": schema_cols,
                "valid": val_res.get("valid", False),
                "error": val_res.get("error"),
                "downstream_steps": [],
            })

            prior_steps_context.append({"name": step.name, "sql": step.sql})

        # Calculate downstream step dependencies
        for s in steps_info:
            s["downstream_steps"] = [
                other["name"] for other in steps_info if s["name"] in other["prior_steps"]
            ]

        # 3. Build rich sources_info
        sources_info: list[dict[str, Any]] = []
        for src in sorted(pipeline_sources):
            conn = all_connections.get(src, {})
            c_guid = conn.get("connector", "")
            c_def = connectors.get(c_guid)
            loc = conn.get("options", {}).get("path") or conn.get("options", {}).get("table") or conn.get("options", {}).get("query") or "—"
            ref_by = [s["name"] for s in steps_info if src in s["sources"]]
            sources_info.append({
                "name": src,
                "clean_id": re.sub(r"\W+", "_", src),
                "description": conn.get("description", ""),
                "connector_type": c_def.label if c_def else (conn.get("connector") or "Catalog Source"),
                "location": str(loc),
                "settings": conn.get("options", {}),
                "schema": conn.get("columns", []),
                "referenced_by": ref_by,
            })

        # 4. Build rich destinations_info
        destinations_info: list[dict[str, Any]] = []
        for dest in sorted(pipeline_destinations):
            conn = all_connections.get(dest, {})
            c_guid = conn.get("connector", "")
            c_def = connectors.get(c_guid)
            loc = conn.get("options", {}).get("path") or conn.get("options", {}).get("table") or "—"
            written_by = [s["name"] for s in steps_info if dest in s["destinations"]]
            target_schema = []
            for s in steps_info:
                if dest in s["destinations"] and s["schema"]:
                    target_schema = s["schema"]
                    break
            destinations_info.append({
                "name": dest,
                "clean_id": re.sub(r"\W+", "_", dest),
                "description": conn.get("description", ""),
                "connector_type": c_def.label if c_def else (conn.get("connector") or "Catalog Destination"),
                "location": str(loc),
                "settings": conn.get("options", {}),
                "schema": target_schema or conn.get("columns", []),
                "written_by": written_by,
            })

        fmt = doc_format.lower().strip()
        if fmt in {"markdown", "md"}:
            return self._render_markdown(pipeline, catalog_doc, steps_info, pipeline_sources, pipeline_destinations, meta=meta)
        return self._render_html(pipeline, catalog_doc, steps_info, sources_info, destinations_info, meta=meta)

    def _render_markdown(
        self,
        pipeline: Pipeline,
        catalog_doc: dict[str, Any],
        steps: list[dict[str, Any]],
        sources: set[str],
        destinations: set[str],
        meta: dict[str, Any] | None = None,
    ) -> str:
        meta = meta or {}
        gen_time = meta.get("gen_time") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        md: list[str] = []

        md.append(f"# {pipeline.name} Documentation\n")
        md.append(
            f"> **Folder:** `{pipeline.folder}` &nbsp;|&nbsp; **Catalog:** `{pipeline.catalog}` &nbsp;|&nbsp; "
            f"**GUID:** `{meta.get('pipeline_id', pipeline.id)}` &nbsp;|&nbsp; **Generated:** {gen_time}\n"
        )

        if pipeline.description:
            md.append("## Overview")
            md.append(f"{pipeline.description}\n")

        # Lineage Graph via Mermaid
        md.append("## Data Lineage & Dependency Graph")
        md.append("```mermaid")
        md.append("flowchart LR")
        if sources:
            md.append('  subgraph Sources ["Catalog Sources"]')
            for s in sorted(sources):
                clean_id = re.sub(r"\W+", "_", s)
                md.append(f'    src_{clean_id}["{s}"]')
            md.append("  end")

        md.append('  subgraph Steps ["Pipeline Steps"]')
        for s in steps:
            clean_id = re.sub(r"\W+", "_", s["name"])
            badge = " (view)" if s["keep_temporary"] else ""
            md.append(f'    step_{clean_id}["{s["index"]:02d}: {s["name"]}{badge}"]')
        md.append("  end")

        if destinations:
            md.append('  subgraph Destinations ["Target Destinations"]')
            for d in sorted(destinations):
                clean_id = re.sub(r"\W+", "_", d)
                md.append(f'    dest_{clean_id}["{d}"]')
            md.append("  end")

        for s in steps:
            clean_step = re.sub(r"\W+", "_", s["name"])
            for src in s["sources"]:
                clean_src = re.sub(r"\W+", "_", src)
                md.append(f"    src_{clean_src} --> step_{clean_step}")
            for ps in s["prior_steps"]:
                clean_ps = re.sub(r"\W+", "_", ps)
                md.append(f"    step_{clean_ps} --> step_{clean_step}")
            for dest in s["destinations"]:
                clean_dest = re.sub(r"\W+", "_", dest)
                md.append(f"    step_{clean_step} --> dest_{clean_dest}")

        md.append("```\n")

        # Step breakdown
        md.append("## Pipeline Steps")
        for s in steps:
            temp_badge = "Materialized as temporary view" if s["keep_temporary"] else "Published to catalog"
            md.append(f"### Step {s['index']}: `{s['name']}`")
            md.append(f"*Mode: {temp_badge}*  \n")
            if s["description"]:
                md.append(f"**Notes / Business Logic:**  \n{s['description']}\n")

            if s["sources"] or s["prior_steps"]:
                inputs = [f"`{x}` (source)" for x in s["sources"]] + [f"`{x}` (prior step)" for x in s["prior_steps"]]
                md.append(f"**Inputs / Dependencies:** {', '.join(inputs)}  \n")
            if s["destinations"]:
                md.append(f"**Destinations:** {', '.join([f'`{d}`' for d in s['destinations']])}  \n")

            md.append("#### SQL Transformation")
            md.append(f"```sql\n{s['sql']}\n```\n")

            md.append("#### Evaluated Output Schema (DataFusion / Arrow)")
            if s["schema"]:
                md.append("| Column Name | Arrow Type | Nullable | Notes / Description |")
                md.append("|---|---|---|---|")
                for c in s["schema"]:
                    md.append(f"| `{c['name']}` | `{c['data_type']}` | {'Yes' if c['nullable'] else 'No'} | {c['description'] or '—'} |")
            else:
                md.append("*No schema derived or step failed evaluation.*")
            md.append("\n---\n")

        # Security & Disclaimer
        md.append("## Notice & Disclaimer")
        md.append("> **Auto-generated Documentation:** Automatically created by `det` ETL engine.\n>")
        md.append("> **Security Alert:** Please scan this documentation for any credentials, passwords, or secret keys before sharing.\n>")
        md.append("> **Inferred Schemas:** Schemas are inferred by Apache DataFusion via AST inspection and should be reviewed against production data.\n")

        return "\n".join(md)

    def _render_html(
        self,
        pipeline: Pipeline,
        catalog_doc: dict[str, Any],
        steps: list[dict[str, Any]],
        sources_info: list[dict[str, Any]],
        destinations_info: list[dict[str, Any]],
        meta: dict[str, Any] | None = None,
    ) -> str:
        meta = meta or {}
        gen_time = meta.get("gen_time") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        created_at = meta.get("created_at") or gen_time
        modified_at = meta.get("modified_at") or gen_time
        pipeline_guid = meta.get("pipeline_id") or pipeline.id

        p_name = html.escape(pipeline.name)
        p_folder = html.escape(pipeline.folder)
        p_catalog = html.escape(pipeline.catalog or "default.yaml")
        p_desc = html.escape(pipeline.description or "No pipeline overview provided.")

        # --- 1. Resolve DAG dependency & depths ---
        node_depths: dict[str, int] = {s["name"]: 0 for s in sources_info}
        for s in steps:
            input_depths = [node_depths.get(src, 0) for src in s["sources"]] + [
                node_depths.get(ps, 0) for ps in s["prior_steps"]
            ]
            node_depths[s["name"]] = (max(input_depths) + 1) if input_depths else 1
        max_step_depth = max([node_depths.get(s["name"], 1) for s in steps], default=1)
        for d in destinations_info:
            node_depths[d["name"]] = max_step_depth + 1

        # Group into visual DAG stages
        dag_stages: dict[int, list[dict[str, Any]]] = {}
        # Stage 0: Sources
        if sources_info:
            dag_stages[0] = [
                {
                    "type": "source",
                    "name": s["name"],
                    "clean_id": s["clean_id"],
                    "subtitle": s["connector_type"],
                    "anchor": f"#src-{s['clean_id']}",
                }
                for s in sources_info
            ]

        # Stage 1..max_step_depth: Steps
        for s in steps:
            d = node_depths.get(s["name"], 1)
            if d not in dag_stages:
                dag_stages[d] = []
            dag_stages[d].append({
                "type": "step",
                "name": s["name"],
                "clean_id": s["clean_id"],
                "subtitle": f"Step {s['index']:02d} ({'view' if s['keep_temporary'] else 'export'})",
                "anchor": f"#step-{s['clean_id']}",
                "sources": s["sources"],
                "prior_steps": s["prior_steps"],
                "destinations": s["destinations"],
            })

        # Stage max_step_depth + 1: Destinations
        if destinations_info:
            d_idx = max_step_depth + 1
            dag_stages[d_idx] = [
                {
                    "type": "destination",
                    "name": d["name"],
                    "clean_id": d["clean_id"],
                    "subtitle": d["connector_type"],
                    "anchor": f"#dest-{d['clean_id']}",
                }
                for d in destinations_info
            ]

        # Build visual DAG columns HTML
        dag_columns_html: list[str] = []
        sorted_stage_keys = sorted(dag_stages.keys())
        for idx, k in enumerate(sorted_stage_keys):
            nodes = dag_stages[k]
            if k == 0:
                stage_label = "Sources"
            elif k == max_step_depth + 1:
                stage_label = "Destinations"
            else:
                stage_label = f"Stage {k}"

            nodes_html = []
            for n in nodes:
                n_type = n["type"]
                icon = "📦" if n_type == "source" else ("⚡" if n_type == "step" else "🎯")
                card_class = f"dag-node is-{n_type}"
                nodes_html.append(f"""
                  <a href="{n['anchor']}" class="{card_class}" title="View {html.escape(n['name'])}">
                    <span class="dag-node-icon">{icon}</span>
                    <div class="dag-node-body">
                      <strong class="dag-node-name">{html.escape(n['name'])}</strong>
                      <span class="dag-node-sub">{html.escape(n['subtitle'])}</span>
                    </div>
                  </a>
                """)

            dag_columns_html.append(f"""
              <div class="dag-stage-column">
                <div class="dag-stage-header">{stage_label}</div>
                <div class="dag-stage-nodes">
                  {''.join(nodes_html)}
                </div>
              </div>
            """)

        # Build Mermaid code
        mermaid_lines = ["flowchart LR"]
        if sources_info:
            mermaid_lines.append('  subgraph Sources ["Catalog Sources"]')
            for s in sources_info:
                mermaid_lines.append(f'    src_{s["clean_id"]}["📦 {s["name"]}"]')
            mermaid_lines.append("  end")

        mermaid_lines.append('  subgraph Steps ["Pipeline Stages"]')
        for s in steps:
            badge = " (view)" if s["keep_temporary"] else ""
            mermaid_lines.append(f'    step_{s["clean_id"]}["⚡ {s["index"]:02d}: {s["name"]}{badge}"]')
        mermaid_lines.append("  end")

        if destinations_info:
            mermaid_lines.append('  subgraph Destinations ["Target Destinations"]')
            for d in destinations_info:
                mermaid_lines.append(f'    dest_{d["clean_id"]}["🎯 {d["name"]}"]')
            mermaid_lines.append("  end")

        for s in steps:
            for src in s["sources"]:
                s_clean = re.sub(r"\W+", "_", src)
                mermaid_lines.append(f"    src_{s_clean} --> step_{s['clean_id']}")
            for ps in s["prior_steps"]:
                ps_clean = re.sub(r"\W+", "_", ps)
                mermaid_lines.append(f"    step_{ps_clean} --> step_{s['clean_id']}")
            for dest in s["destinations"]:
                d_clean = re.sub(r"\W+", "_", dest)
                mermaid_lines.append(f"    step_{s['clean_id']} --> dest_{d_clean}")

        for s in sources_info:
            mermaid_lines.append(f'    click src_{s["clean_id"]} href "#src-{s["clean_id"]}"')
        for s in steps:
            mermaid_lines.append(f'    click step_{s["clean_id"]} href "#step-{s["clean_id"]}"')
        for d in destinations_info:
            mermaid_lines.append(f'    click dest_{d["clean_id"]} href "#dest-{d["clean_id"]}"')

        mermaid_code = "\n".join(mermaid_lines)

        # --- Helper for Schema Tables (Markdown-like) ---
        def render_schema_table(schema: list[dict[str, Any]]) -> str:
            if not schema:
                return '<p class="text-muted"><em>No schema fields recorded or step un-evaluated.</em></p>'
            rows = []
            for col in schema:
                c_name = html.escape(str(col.get("name", "")))
                c_type = html.escape(str(col.get("data_type", "Utf8")))
                c_null = "Nullable" if col.get("nullable", True) else "Required"
                c_desc = html.escape(str(col.get("description", "") or "—"))
                rows.append(
                    f"<tr><td><code>{c_name}</code></td><td><code>{c_type}</code></td>"
                    f"<td>{c_null}</td><td>{c_desc}</td></tr>"
                )
            return f"""
            <table class="doc-table">
              <thead>
                <tr>
                  <th>Column</th>
                  <th>Type</th>
                  <th>Nullability</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>{''.join(rows)}</tbody>
            </table>
            """

        # --- Helper for Options / Settings Grid ---
        def render_settings_table(settings: dict[str, Any]) -> str:
            if not settings:
                return ""
            rows = []
            for k, v in settings.items():
                k_esc = html.escape(str(k))
                v_esc = html.escape(str(v))
                rows.append(f"<tr><td><code>{k_esc}</code></td><td><code>{v_esc}</code></td></tr>")
            return f"""
            <table class="settings-table">
              <thead><tr><th>Setting Key</th><th>Value</th></tr></thead>
              <tbody>{''.join(rows)}</tbody>
            </table>
            """

        # --- 2. Sources Section Items ---
        sources_index_items = [
            f'<li><a href="#src-{s["clean_id"]}">{html.escape(s["name"])}</a> <span class="badge">{html.escape(s["connector_type"])}</span></li>'
            for s in sources_info
        ]
        sources_index_html = f'<ul class="doc-index">{"".join(sources_index_items)}</ul>' if sources_index_items else ""
        sources_cards = []
        for s in sources_info:
            ref_steps_html = []
            for r in s["referenced_by"]:
                clean_r = re.sub(r"\W+", "_", r)
                s_obj = next((st for st in steps if st["name"] == r), None)
                s_idx = f"Step {s_obj['index']:02d}" if s_obj else "Step"
                ref_steps_html.append(f'<a href="#step-{clean_r}" class="ref-link">⚡ {s_idx}: {html.escape(r)}</a>')
            ref_rendered = ", ".join(ref_steps_html) if ref_steps_html else "<em>None</em>"

            sources_cards.append(f"""
            <div id="src-{s['clean_id']}" class="doc-item">
              <h3>📦 {html.escape(s['name'])} <span class="badge">{html.escape(s['connector_type'])}</span></h3>
              <p>{html.escape(s['description']) if s['description'] else '<em class="text-muted">No description specified.</em>'}</p>
              <p><strong>Connector:</strong> <code>{html.escape(s['connector_type'])}</code> &nbsp;|&nbsp; <strong>Location:</strong> <code>{html.escape(s['location'])}</code></p>
              {render_settings_table(s['settings'])}
              <h4>Catalog Schema</h4>
              {render_schema_table(s['schema'])}
              <p class="ref-line"><strong>Referenced by (Pipeline Steps):</strong> {ref_rendered}</p>
            </div>
            """)

        # --- 3. Steps Section Items ---
        steps_index_items = [
            f'<li><a href="#step-{s["clean_id"]}">{html.escape(s["name"])}</a> <span class="badge">{"Temporary View" if s["keep_temporary"] else "Destination Export"}</span></li>'
            for s in steps
        ]
        steps_index_html = f'<ol class="doc-index">{"".join(steps_index_items)}</ol>' if steps_index_items else ""
        steps_cards = []
        for s in steps:
            up_html = []
            for src_name in s["sources"]:
                c_src = re.sub(r"\W+", "_", src_name)
                up_html.append(f'<a href="#src-{c_src}" class="ref-link">📦 {html.escape(src_name)}</a>')
            for ps_name in s["prior_steps"]:
                c_ps = re.sub(r"\W+", "_", ps_name)
                ps_obj = next((st for st in steps if st["name"] == ps_name), None)
                ps_idx = f"Step {ps_obj['index']:02d}" if ps_obj else "Step"
                up_html.append(f'<a href="#step-{c_ps}" class="ref-link">⚡ {ps_idx}: {html.escape(ps_name)}</a>')
            up_rendered = ", ".join(up_html) if up_html else "<em>None (root step)</em>"

            down_html = []
            for ds_name in s["downstream_steps"]:
                c_ds = re.sub(r"\W+", "_", ds_name)
                ds_obj = next((st for st in steps if st["name"] == ds_name), None)
                ds_idx = f"Step {ds_obj['index']:02d}" if ds_obj else "Step"
                down_html.append(f'<a href="#step-{c_ds}" class="ref-link">⚡ {ds_idx}: {html.escape(ds_name)}</a>')
            for d_name in s["destinations"]:
                c_d = re.sub(r"\W+", "_", d_name)
                down_html.append(f'<a href="#dest-{c_d}" class="ref-link">🎯 {html.escape(d_name)}</a>')
            down_rendered = ", ".join(down_html) if down_html else "<em>Temporary view (not exported)</em>"

            mode_text = "Temporary View" if s["keep_temporary"] else "Destination Export"

            steps_cards.append(f"""
            <div id="step-{s['clean_id']}" class="doc-item">
              <h3>⚡ Step {s['index']:02d}: {html.escape(s['name'])} <span class="badge">{mode_text}</span></h3>
              <p>{html.escape(s['description']) if s['description'] else '<em class="text-muted">No step description provided.</em>'}</p>
              <div class="code-box">
                <div class="code-box-header">
                  <span>SQL Transformation (Apache DataFusion)</span>
                  <button class="copy-btn" type="button" onclick="const c=this.closest('.code-box').querySelector('code').innerText;navigator.clipboard.writeText(c);this.textContent='Copied!';setTimeout(()=>this.textContent='Copy SQL',1500)">Copy SQL</button>
                </div>
                <pre><code>{html.escape(s['sql'])}</code></pre>
              </div>
              <h4>Evaluated Output Schema (Arrow / DataFusion)</h4>
              {render_schema_table(s['schema'])}
              <p class="ref-line"><strong>Upstream Dependencies (Inputs):</strong> {up_rendered}</p>
              <p class="ref-line"><strong>Downstream Consumers (Outputs):</strong> {down_rendered}</p>
            </div>
            """)

        # --- 4. Destinations Section Items ---
        dest_index_items = [
            f'<li><a href="#dest-{d["clean_id"]}">{html.escape(d["name"])}</a> <span class="badge">{html.escape(d["connector_type"])}</span></li>'
            for d in destinations_info
        ]
        dest_index_html = f'<ul class="doc-index">{"".join(dest_index_items)}</ul>' if dest_index_items else ""
        dest_cards = []
        for d in destinations_info:
            written_html = []
            for w in d["written_by"]:
                clean_w = re.sub(r"\W+", "_", w)
                w_obj = next((st for st in steps if st["name"] == w), None)
                w_idx = f"Step {w_obj['index']:02d}" if w_obj else "Step"
                written_html.append(f'<a href="#step-{clean_w}" class="ref-link">⚡ {w_idx}: {html.escape(w)}</a>')
            written_rendered = ", ".join(written_html) if written_html else "<em>None</em>"

            dest_cards.append(f"""
            <div id="dest-{d['clean_id']}" class="doc-item">
              <h3>🎯 {html.escape(d['name'])} <span class="badge">{html.escape(d['connector_type'])}</span></h3>
              <p>{html.escape(d['description']) if d['description'] else '<em class="text-muted">Target destination sink.</em>'}</p>
              <p><strong>Connector:</strong> <code>{html.escape(d['connector_type'])}</code> &nbsp;|&nbsp; <strong>Location:</strong> <code>{html.escape(d['location'])}</code></p>
              {render_settings_table(d['settings'])}
              <p class="ref-line"><strong>Written by (Pipeline Steps):</strong> {written_rendered}</p>
              <h4>Target Schema</h4>
              {render_schema_table(d['schema'])}
            </div>
            """)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{p_name} Documentation</title>
  <style>
    :root {{
      --bg: #ffffff;
      --surface: #ffffff;
      --sidebar-bg: #f6f8fa;
      --border: #d0d7de;
      --border-muted: #e1e4e8;
      --text: #1f2328;
      --text-muted: #656d76;
      --accent: #0969da;
      --code-bg: #f6f8fa;
      --table-th-bg: #f6f8fa;
      --callout-bg: #fff8c5;
      --callout-border: #d4a72c;
      --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
      --font-mono: ui-monospace, SFMono-Regular, "Cascadia Code", Menlo, Consolas, monospace;
    }}

    :root[data-theme="dark"] {{
      --bg: #0d1117;
      --surface: #0d1117;
      --sidebar-bg: #161b22;
      --border: #30363d;
      --border-muted: #21262d;
      --text: #e6edf3;
      --text-muted: #848d97;
      --accent: #2f81f7;
      --code-bg: #161b22;
      --table-th-bg: #161b22;
      --callout-bg: #1f1b0d;
      --callout-border: #9e6a03;
    }}

    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      padding: 0;
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      font-size: 13px;
      line-height: 1.6;
    }}
    [id] {{ scroll-margin-top: 16px; }}

    /* Layout */
    .doc-layout {{
      display: flex;
      min-height: 100vh;
    }}

    /* Sidebar */
    .doc-sidebar {{
      width: 220px;
      min-width: 220px;
      max-width: 220px;
      height: 100vh;
      position: sticky;
      top: 0;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      background: var(--sidebar-bg);
      border-right: 1px solid var(--border);
      padding: 16px 12px;
      overflow-y: auto;
    }}
    .sidebar-top {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .sidebar-brand {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 2px 4px 12px;
      border-bottom: 1px solid var(--border);
    }}
    .brand-tag {{
      font-size: 10px;
      font-weight: 700;
      padding: 2px 5px;
      border-radius: 4px;
      background: var(--border);
      color: var(--text);
    }}
    .brand-title {{
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .sidebar-nav {{
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}
    .nav-link {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 6px 8px;
      border-radius: 6px;
      color: var(--text-muted);
      text-decoration: none;
      font-size: 12px;
      font-weight: 500;
      transition: background 100ms ease, color 100ms ease;
    }}
    .nav-link:hover {{
      background: var(--border-muted);
      color: var(--text);
    }}
    .nav-count {{
      font-size: 11px;
      color: var(--text-muted);
    }}
    .sidebar-bottom {{
      margin-top: auto;
      padding-top: 12px;
      border-top: 1px solid var(--border);
    }}
    .theme-toggle {{
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      background: var(--bg);
      border: 1px solid var(--border);
      color: var(--text);
      font-family: inherit;
      font-size: 11.5px;
      font-weight: 500;
      padding: 6px 10px;
      border-radius: 6px;
      cursor: pointer;
    }}
    .theme-toggle:hover {{
      border-color: var(--accent);
    }}

    /* Main Content (Markdown Style) */
    .doc-main {{
      flex: 1;
      min-width: 0;
      padding: 28px 40px 60px;
      max-width: 980px;
    }}
    h1.pipeline-title {{
      font-size: 22px;
      font-weight: 600;
      margin: 0 0 16px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border);
    }}
    h2 {{
      font-size: 16px;
      font-weight: 600;
      margin: 32px 0 12px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--border);
    }}
    h3 {{
      font-size: 14px;
      font-weight: 600;
      margin: 20px 0 8px;
    }}
    h4 {{
      font-size: 12px;
      font-weight: 600;
      margin: 14px 0 6px;
      color: var(--text-muted);
    }}
    p {{ margin: 0 0 10px; line-height: 1.6; }}
    .text-muted {{ color: var(--text-muted); }}
    .section-desc {{ font-size: 12px; color: var(--text-muted); margin-bottom: 12px; }}

    /* Metadata Table */
    .meta-table {{
      width: 100%;
      border-collapse: collapse;
      margin: 0 0 24px;
      font-size: 11.5px;
    }}
    .meta-table th, .meta-table td {{
      border: 1px solid var(--border);
      padding: 6px 10px;
      text-align: left;
    }}
    .meta-table th {{
      width: 140px;
      background: var(--table-th-bg);
      font-weight: 600;
      color: var(--text-muted);
    }}

    /* DAG Lineage */
    .dag-container {{
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 16px;
      background: var(--surface);
      overflow-x: auto;
      margin-bottom: 10px;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 120px;
    }}
    .mermaid-diagram {{
      width: 100%;
      display: flex;
      justify-content: center;
      font-family: var(--font-mono);
      font-size: 11px;
      line-height: 1.5;
      overflow-x: auto;
    }}
    .mermaid-diagram svg {{
      max-width: 100%;
      height: auto;
    }}
    .mermaid-details {{
      margin-top: 8px;
      font-size: 11px;
    }}
    .mermaid-details summary {{
      cursor: pointer;
      color: var(--text-muted);
    }}
    pre.mermaid-raw {{
      margin-top: 6px;
      padding: 10px;
      background: var(--code-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      font-family: var(--font-mono);
      font-size: 11px;
      overflow-x: auto;
    }}
    /* Index Lists */
    .doc-index {{
      margin: 8px 0 20px;
      padding-left: 20px;
      font-size: 12.5px;
      line-height: 1.8;
    }}
    .doc-index li {{
      margin-bottom: 2px;
    }}
    .doc-index a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 500;
    }}
    .doc-index a:hover {{
      text-decoration: underline;
    }}

    /* Doc item blocks */
    .doc-item {{
      border-top: 1px solid var(--border-muted);
      padding-top: 14px;
      margin-top: 20px;
    }}
    .doc-item:first-of-type {{
      border-top: none;
      padding-top: 0;
      margin-top: 0;
    }}
    .badge {{
      display: inline-block;
      font-size: 10px;
      font-weight: 500;
      padding: 1px 6px;
      border-radius: 4px;
      background: var(--border);
      color: var(--text-muted);
      vertical-align: middle;
      margin-left: 6px;
    }}

    /* Tables */
    table.doc-table, table.settings-table {{
      width: 100%;
      border-collapse: collapse;
      margin: 8px 0 14px;
      font-size: 11.5px;
    }}
    table.doc-table th, table.doc-table td,
    table.settings-table th, table.settings-table td {{
      border: 1px solid var(--border);
      padding: 5px 8px;
      text-align: left;
    }}
    table.doc-table th, table.settings-table th {{
      background: var(--table-th-bg);
      font-weight: 600;
      color: var(--text);
    }}
    table.settings-table {{
      width: auto;
      min-width: 320px;
    }}

    /* Code & pre */
    code {{
      font-family: var(--font-mono);
      font-size: 11.5px;
      background: var(--code-bg);
      padding: 2px 4px;
      border-radius: 3px;
    }}
    .code-box {{
      border: 1px solid var(--border);
      border-radius: 6px;
      margin: 10px 0 14px;
      overflow: hidden;
      background: var(--code-bg);
    }}
    .code-box-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 4px 10px;
      background: var(--sidebar-bg);
      border-bottom: 1px solid var(--border);
      font-size: 10.5px;
      color: var(--text-muted);
    }}
    .copy-btn {{
      background: var(--bg);
      border: 1px solid var(--border);
      color: var(--text);
      font-family: inherit;
      font-size: 10px;
      padding: 2px 8px;
      border-radius: 4px;
      cursor: pointer;
    }}
    .copy-btn:hover {{ border-color: var(--accent); }}
    .code-box pre {{
      margin: 0;
      padding: 10px 12px;
      overflow-x: auto;
      font-family: var(--font-mono);
      font-size: 11.5px;
      line-height: 1.5;
    }}

    /* References */
    .ref-line {{
      font-size: 12px;
      margin: 8px 0;
    }}
    .ref-link {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 500;
    }}
    .ref-link:hover {{ text-decoration: underline; }}

    /* Security Callout */
    .callout-block {{
      border-left: 3px solid var(--callout-border);
      background: var(--callout-bg);
      padding: 12px 16px;
      border-radius: 0 6px 6px 0;
      margin: 14px 0;
      font-size: 12px;
    }}
    .callout-block p {{ margin: 0 0 6px; }}
    .callout-block p:last-child {{ margin: 0; }}

    /* Footer */
    .doc-footer {{
      margin-top: 48px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
      font-size: 11px;
      color: var(--text-muted);
      text-align: center;
    }}

    @media (max-width: 768px) {{
      .doc-layout {{ flex-direction: column; }}
      .doc-sidebar {{
        width: 100%;
        max-width: 100%;
        height: auto;
        position: static;
        border-right: none;
        border-bottom: 1px solid var(--border);
        padding: 12px 16px;
      }}
      .sidebar-nav {{ flex-direction: row; flex-wrap: wrap; gap: 4px; }}
      .doc-main {{ padding: 16px 20px 48px; }}
    }}
  </style>
  <base target="_self">
</head>
<body>
  <div class="doc-layout">
    <!-- Sidebar Navigation -->
    <aside class="doc-sidebar">
      <div class="sidebar-top">
        <div class="sidebar-brand">
          <span class="brand-tag">DET</span>
          <span class="brand-title" title="{p_name}">{p_name}</span>
        </div>
        <nav class="sidebar-nav">
          <a href="#overview" class="nav-link">
            <span>Overview</span>
          </a>
          <a href="#lineage" class="nav-link">
            <span>Lineage DAG</span>
          </a>
          <a href="#sources" class="nav-link">
            <span>Sources</span>
            <span class="nav-count">({len(sources_info)})</span>
          </a>
          <a href="#steps" class="nav-link">
            <span>Steps</span>
            <span class="nav-count">({len(steps)})</span>
          </a>
          <a href="#destinations" class="nav-link">
            <span>Destinations</span>
            <span class="nav-count">({len(destinations_info)})</span>
          </a>
          <a href="#disclaimer" class="nav-link">
            <span>Security &amp; Notes</span>
          </a>
        </nav>
      </div>
      <div class="sidebar-bottom">
        <button id="theme-toggle" class="theme-toggle" type="button" aria-label="Toggle theme">
          <span class="theme-text">☀️ Light</span>
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="doc-main">
      <header class="doc-header">
        <h1 class="pipeline-title">{p_name} Documentation</h1>
        <table class="meta-table">
          <tbody>
            <tr>
              <th>Pipeline GUID</th>
              <td><code>{html.escape(pipeline_guid)}</code></td>
              <th>Catalog</th>
              <td><code>{p_catalog}</code></td>
            </tr>
            <tr>
              <th>Created at</th>
              <td>{html.escape(created_at)}</td>
              <th>Folder</th>
              <td><code>{p_folder if p_folder else '/'}</code></td>
            </tr>
            <tr>
              <th>Last Modified at</th>
              <td>{html.escape(modified_at)}</td>
              <th>Document Generated</th>
              <td>{html.escape(gen_time)}</td>
            </tr>
          </tbody>
        </table>
      </header>

      <!-- Overview Section -->
      <section id="overview" class="doc-section">
        <h2>Overview</h2>
        <p>{p_desc}</p>
      </section>

      <!-- Lineage Section -->
      <section id="lineage" class="doc-section">
        <h2>Data Lineage &amp; DAG Dependencies</h2>
        <p class="section-desc">Directed Acyclic Graph across sources, transformation stages, and export sinks.</p>
        <div class="dag-container dag-stage-column">
          <div id="lineage-graph" class="mermaid-diagram" data-src="{html.escape(mermaid_code)}">{html.escape(mermaid_code)}</div>
        </div>
        <details class="mermaid-details">
          <summary>View Mermaid Diagram Definition</summary>
          <pre class="mermaid-raw"><code>{html.escape(mermaid_code)}</code></pre>
        </details>
      </section>

      <!-- Sources Section -->
      <section id="sources" class="doc-section">
        <h2>Catalog Sources ({len(sources_info)})</h2>
        {sources_index_html}
        {''.join(sources_cards) if sources_cards else '<p><em>No catalog sources referenced.</em></p>'}
      </section>

      <!-- Steps Section -->
      <section id="steps" class="doc-section">
        <h2>Pipeline Steps ({len(steps)})</h2>
        {steps_index_html}
        {''.join(steps_cards)}
      </section>

      <!-- Destinations Section -->
      <section id="destinations" class="doc-section">
        <h2>Target Destinations ({len(destinations_info)})</h2>
        {dest_index_html}
        {''.join(dest_cards) if dest_cards else '<p><em>No persistent export sinks configured. All steps run as temporary in-memory views.</em></p>'}
      </section>

      <!-- Security & Disclaimer Section -->
      <section id="disclaimer" class="doc-section">
        <h2>Security &amp; Disclaimer Notice</h2>
        <div class="callout-block">
          <p><strong>🛡️ Auto-generated Documentation:</strong> Automatically generated by the <code>det</code> ETL engine.</p>
          <p><strong>🔑 Security &amp; Secret Key Scanning:</strong> Please scan this documentation for any sensitive credentials, connection passwords, tokens, or private secrets before sharing or publishing.</p>
          <p><strong>🧪 Inferred Schema Review:</strong> Schemas are statically inferred by Apache DataFusion and Apache Arrow query planning. Review inferred column types and nullabilities against production schemas.</p>
        </div>
      </section>

      <footer class="doc-footer">
        Generated automatically by <strong>det</strong> ETL engine &middot; Powered by Apache DataFusion &amp; Apache Arrow
      </footer>
    </main>
  </div>

  <script>
    (function() {{
      const root = document.documentElement;
      const btn = document.getElementById("theme-toggle");

      function renderMermaid() {{
        function run() {{
          if (typeof mermaid === "undefined") return;
          const isDark = root.getAttribute("data-theme") === "dark";
          mermaid.initialize({{
            startOnLoad: false,
            theme: isDark ? "dark" : "neutral",
            securityLevel: "loose",
            flowchart: {{
              useMaxWidth: false,
              htmlLabels: true,
              curve: "basis"
            }}
          }});
          const el = document.getElementById("lineage-graph");
          if (el) {{
            const src = el.getAttribute("data-src") || el.textContent;
            const renderId = "mermaid-svg-" + Math.floor(Math.random() * 1000000);
            mermaid.render(renderId, src)
              .then(res => {{ el.innerHTML = res.svg; }})
              .catch(err => {{ console.warn("Mermaid render error:", err); }});
          }}
        }}

        if (typeof mermaid === "undefined") {{
          const s = document.createElement("script");
          s.src = "/mermaid.min.js";
          s.onload = run;
          s.onerror = () => {{
            const s2 = document.createElement("script");
            s2.src = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
            s2.onload = run;
            document.head.appendChild(s2);
          }};
          document.head.appendChild(s);
        }} else {{
          run();
        }}
      }}

      function applyTheme(theme) {{
        root.setAttribute("data-theme", theme);
        if (btn) {{
          const txt = btn.querySelector(".theme-text");
          if (txt) txt.textContent = theme === "dark" ? "☀️ Light" : "🌙 Dark";
        }}
        renderMermaid();
      }}

      const saved = localStorage.getItem("det-doc-theme");
      if (saved) {{
        applyTheme(saved);
      }} else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {{
        applyTheme("dark");
      }} else {{
        applyTheme("light");
      }}

      if (btn) {{
        btn.addEventListener("click", function() {{
          const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
          localStorage.setItem("det-doc-theme", next);
          applyTheme(next);
        }});
      }}

      // Safe navigation: smooth scroll in-page anchors, open external links in new window, block app recursion
      document.addEventListener("click", function(e) {{
        const link = e.target.closest("a");
        if (!link) return;
        const href = link.getAttribute("href");
        if (!href) return;

        if (href.startsWith("#")) {{
          e.preventDefault();
          const targetId = href.substring(1);
          const targetEl = document.getElementById(targetId) || document.querySelector(`[name="${{targetId}}"]`);
          if (targetEl) {{
            targetEl.scrollIntoView({{ behavior: "smooth", block: "start" }});
            try {{ history.replaceState(null, "", href); }} catch(err) {{}}
          }}
        }} else if (href.startsWith("http://") || href.startsWith("https://")) {{
          e.preventDefault();
          window.open(href, "_blank", "noopener,noreferrer");
        }} else {{
          e.preventDefault();
        }}
      }});
    }})();
  </script>
</body>
</html>"""


