"""Zero-dependency HTML documentation portal and manifest generator."""

import html
import json
import logging
from pathlib import Path
from typing import Any

from det.docs.base import BaseDocsGenerator, ColumnDoc, DestinationDoc, ModelDoc, ProjectDoc, SourceDoc, TestDoc

logger = logging.getLogger(__name__)


class DocsGenerator(BaseDocsGenerator):
    """Compiles self-contained HTML documentation portals and JSON manifests."""

    def generate_html(self, project_doc: ProjectDoc) -> str:
        """Render complete standalone HTML page with Clean Slate / High Contrast themes."""
        body_content = "\n".join([
            self._render_header(project_doc),
            self._render_kpis(project_doc),
            self._render_lineage_section(project_doc),
            self._render_models_section(project_doc),
        ])
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(project_doc.project_name)} - Documentation</title>
    <style>{self._get_stylesheet()}</style>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});
        }});
        function toggleTheme() {{
            document.body.classList.toggle("theme-contrast");
            var btn = document.getElementById("theme-toggle-btn");
            if (btn) btn.textContent = document.body.classList.contains("theme-contrast") ? "Clean Slate Theme" : "High Contrast Theme";
        }}
    </script>
</head>
<body>
    <div class="container">
        {body_content}
    </div>
</body>
</html>"""

    def write_docs(self, output_dir: Path, project_doc: ProjectDoc) -> Path:
        """Atomically persist index.html and manifest.json into destination directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
        html_path = output_dir / "index.html"
        json_path = output_dir / "manifest.json"
        html_path.write_text(self.generate_html(project_doc), encoding="utf-8")
        json_path.write_text(json.dumps(self._build_manifest(project_doc), indent=2), encoding="utf-8")
        logger.info("Generated documentation in '%s'", output_dir)
        return html_path

    def _render_header(self, doc: ProjectDoc) -> str:
        """Render project title, theme toggle, version badge, and pipeline description."""
        esc_name = html.escape(doc.project_name)
        esc_ver = html.escape(doc.version)
        esc_desc = html.escape(doc.description or "Automated analytical pipeline documentation.")
        return f"""
        <header class="header">
            <div class="title-row">
                <div>
                    <h1>{esc_name} <span class="badge badge-version">v{esc_ver}</span></h1>
                    <p class="subtitle">{esc_desc}</p>
                </div>
                <button id="theme-toggle-btn" class="theme-btn" onclick="toggleTheme()">High Contrast Theme</button>
            </div>
        </header>"""

    def _render_kpis(self, doc: ProjectDoc) -> str:
        """Render executive metrics summary cards."""
        return f"""
        <div class="kpi-grid">
            <div class="kpi-card"><h3>Pipeline Models</h3><p>{doc.total_models}</p></div>
            <div class="kpi-card"><h3>Catalog Sources</h3><p>{doc.total_sources}</p></div>
            <div class="kpi-card"><h3>Active Test Rules</h3><p>{doc.total_tests}</p></div>
        </div>"""

    def _render_lineage_section(self, doc: ProjectDoc) -> str:
        """Render Mermaid DAG flowchart section."""
        return f"""
        <section class="section">
            <h2>Pipeline Lineage & DAG Architecture</h2>
            <div class="mermaid-box"><pre class="mermaid">{doc.lineage_mermaid}</pre></div>
        </section>"""

    def _render_models_section(self, doc: ProjectDoc) -> str:
        """Render list of models with schema dictionary, sources, tests, and SQL."""
        rendered = [self._render_single_model(m) for m in doc.models]
        return f"""
        <section class="section">
            <h2>Model Data Dictionary & Quality Contracts</h2>
            <div class="models-list">{"".join(rendered)}</div>
        </section>"""

    def _render_single_model(self, m: ModelDoc) -> str:
        """Render a single model card containing sources, destinations, columns, and tests."""
        esc_name, esc_mat = html.escape(m.name), html.escape(m.materialization.upper())
        esc_desc = html.escape(m.description or "No description provided.")
        src_table = self._render_sources_table(m.sources_detail)
        dest_table = self._render_destinations_table(m.destinations_detail)
        col_table = self._render_columns_table(m.columns)
        tests_table = self._render_tests_table(m.tests_detail)
        return f"""
        <div class="card model-card" id="model-{esc_name}">
            <div class="model-header"><h3>{esc_name}</h3><span class="badge badge-mat">{esc_mat}</span></div>
            <p class="model-desc">{esc_desc}</p>
            <h4>Upstream Ingestion Sources</h4>{src_table}
            <h4>Export Destinations</h4>{dest_table}
            <h4>Column Schema & Data Types</h4>{col_table}
            <h4>Quality Assertions & Failure Policies</h4>{tests_table}
            <h4>Compiled ANSI SQL</h4><pre class="sql-box"><code>{html.escape(m.compiled_sql)}</code></pre>
        </div>"""

    def _render_sources_table(self, sources: list[SourceDoc]) -> str:
        """Render HTML table of actual upstream sources, connection types, and locations."""
        if not sources:
            return "<p class='empty-text'>No external catalog sources (root transformation or ref only).</p>"
        rows = [
            f"<tr><td><code>{html.escape(s.name)}</code></td><td><span class='badge badge-tier'>{html.escape(s.tier.upper())}</span></td><td><span class='type-tag'>{html.escape(s.connector_type.upper())}</span></td><td><code>{html.escape(s.path or '(direct query)')}</code></td><td>{html.escape(s.description or '—')}</td></tr>"
            for s in sources
        ]
        return f"""<div class="table-wrap"><table class="table" style="min-width:720px;"><thead><tr><th style="min-width:140px;">Source</th><th style="min-width:90px;">Tier</th><th style="min-width:100px;">Type</th><th style="min-width:210px;">Location / File Path</th><th style="min-width:180px;">Description</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>"""

    def _render_destinations_table(self, dests: list[DestinationDoc]) -> str:
        """Render HTML table of export targets, formats, and physical destination paths."""
        if not dests:
            return "<p class='empty-text'>Materialized internally in DuckDB (no external export destinations).</p>"
        rows = [
            f"<tr><td><span class='type-tag'>{html.escape(d.target.upper())}</span></td><td><code>{html.escape(d.path)}</code></td><td><code>{html.escape(str(d.options) if d.options else 'default')}</code></td></tr>"
            for d in dests
        ]
        return f"""<div class="table-wrap"><table class="table" style="min-width:560px;"><thead><tr><th style="min-width:120px;">Target Format</th><th style="min-width:260px;">File Path / Location</th><th style="min-width:180px;">Export Options</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>"""

    def _render_columns_table(self, columns: list[ColumnDoc]) -> str:
        """Render HTML table of column names, data types, and test badges."""
        if not columns:
            return "<p class='empty-text'>No column metadata available.</p>"
        rows = [
            f"<tr><td><code>{html.escape(c.name)}</code></td><td><span class='type-tag'>{html.escape(c.data_type)}</span></td><td>{' '.join(f'<span class=\"badge badge-test\">{html.escape(b)}</span>' for b in c.test_badges) or '<span class=\"muted\">—</span>'}</td><td>{html.escape(c.description or '—')}</td></tr>"
            for c in columns
        ]
        return f"""<div class="table-wrap"><table class="table" style="min-width:650px;"><thead><tr><th style="min-width:160px;">Column</th><th style="min-width:120px;">Data Type</th><th style="min-width:180px;">Assertions</th><th style="min-width:190px;">Description</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>"""

    def _render_tests_table(self, tests: list[TestDoc]) -> str:
        """Render HTML table of test assertion contracts, conditions, and failure actions."""
        if not tests:
            return "<p class='empty-text'>No explicit or inferred tests registered for this model.</p>"
        rows = [
            f"<tr><td style=\"min-width:250px;\"><code>{html.escape(t.name)}</code></td><td style=\"min-width:120px;\"><code>{html.escape(t.column or 'model')}</code></td><td style=\"min-width:170px;\">{html.escape(t.details)}</td><td style=\"min-width:90px;\"><span class='badge badge-sev-{t.severity.lower()}'>{html.escape(t.severity)}</span></td><td style=\"min-width:250px;\"><strong>{html.escape(t.action_on_failure)}</strong></td></tr>"
            for t in tests
        ]
        return f"""<div class="table-wrap"><table class="table" style="min-width:880px;"><thead><tr><th style="min-width:250px;">Assertion Name</th><th style="min-width:120px;">Column</th><th style="min-width:170px;">Rule Condition</th><th style="min-width:90px;">Severity</th><th style="min-width:250px;">Action on Failure</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>"""

    def _build_manifest(self, doc: ProjectDoc) -> dict[str, Any]:
        """Convert ProjectDoc into dictionary for manifest.json export."""
        return {
            "project": doc.project_name, "version": doc.version, "description": doc.description,
            "stats": {"models": doc.total_models, "sources": doc.total_sources, "tests": doc.total_tests},
            "models": [{"name": m.name, "description": m.description, "materialization": m.materialization, "columns": [{"name": c.name, "type": c.data_type, "tests": c.test_badges} for c in m.columns]} for m in doc.models],
        }

    def _get_stylesheet(self) -> str:
        """Return Clean Slate primary CSS stylesheet with High Contrast mode support."""
        return """
        :root { --bg: #f8fafc; --card: #ffffff; --border: #cbd5e1; --text: #0f172a; --muted: #64748b; --accent: #2563eb; --sql-bg: #f1f5f9; --sql-text: #0f172a; --badge-bg: #e2e8f0; --badge-text: #1e293b; }
        body.theme-contrast { --bg: #000000; --card: #0a0a0a; --border: #ffffff; --text: #ffffff; --muted: #e2e8f0; --accent: #38bdf8; --sql-bg: #000000; --sql-text: #ffffff; --badge-bg: #262626; --badge-text: #ffffff; }
        body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem; }
        .header { margin-bottom: 2rem; border-bottom: 2px solid var(--border); padding-bottom: 1.25rem; }
        .title-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
        h1, h2, h3, h4 { margin: 0 0 0.5rem; color: var(--text); }
        h4 { margin-top: 1.25rem; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); }
        .subtitle { color: var(--muted); margin: 0; }
        .theme-btn { padding: 0.45rem 0.9rem; border: 1px solid var(--border); border-radius: 6px; background: var(--card); color: var(--text); cursor: pointer; font-weight: 600; font-size: 0.85rem; }
        .badge { font-size: 0.72rem; padding: 0.2rem 0.55rem; border-radius: 4px; font-weight: 700; text-transform: uppercase; font-family: monospace; }
        .badge-version { background: #10b981; color: #fff; }
        .badge-mat { background: #2563eb; color: #fff; }
        .badge-tier { background: #6366f1; color: #fff; }
        .badge-test { background: rgba(16, 185, 129, 0.15); color: #059669; border: 1px solid rgba(16, 185, 129, 0.4); }
        .badge-sev-error { background: rgba(239, 68, 68, 0.15); color: #dc2626; border: 1px solid rgba(239, 68, 68, 0.4); }
        .badge-sev-quarantine { background: rgba(168, 85, 247, 0.15); color: #7c3aed; border: 1px solid rgba(168, 85, 247, 0.4); }
        .badge-sev-warn { background: rgba(245, 158, 11, 0.15); color: #d97706; border: 1px solid rgba(245, 158, 11, 0.4); }
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .kpi-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1.25rem; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .kpi-card h3 { color: var(--muted); font-size: 0.82rem; text-transform: uppercase; }
        .kpi-card p { font-size: 2.2rem; font-weight: 700; margin: 0; color: var(--accent); }
        .section { margin-bottom: 3rem; }
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1.75rem; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .mermaid-box { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; overflow-x: auto; text-align: center; }
        .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; border: 1px solid var(--border); border-radius: 6px; margin: 0.5rem 0 1.25rem 0; background: var(--card); }
        .table { width: 100%; border-collapse: collapse; margin: 0; font-size: 0.88rem; }
        .table th, .table td { text-align: left; padding: 0.65rem 0.85rem; border-bottom: 1px solid var(--border); }
        .table th { background: var(--bg); color: var(--muted); font-weight: 700; font-size: 0.75rem; text-transform: uppercase; white-space: nowrap; }
        .type-tag { font-family: monospace; font-size: 0.8rem; color: var(--accent); font-weight: 600; }
        .sql-box { background: var(--sql-bg); color: var(--sql-text); border: 1px solid var(--border); border-radius: 6px; padding: 1rem; overflow-x: auto; font-size: 0.82rem; font-family: monospace; line-height: 1.5; }
        .model-desc { color: var(--text); margin-bottom: 1rem; font-size: 0.95rem; }
        .empty-text { color: var(--muted); font-style: italic; font-size: 0.85rem; margin: 0.4rem 0 1rem; }
        """
