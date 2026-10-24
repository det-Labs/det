"""Schema introspection, column type extraction, and test badge matching."""

import logging
from pathlib import Path
from typing import Any
import duckdb

from det.docs.base import (
    BaseDocsExtractor,
    ColumnDoc,
    DestinationDoc,
    ModelDoc,
    SourceDoc,
    TestDoc,
)
from det.models.definition import ModelDefinition
from det.testing.definitions import TestDefinition

logger = logging.getLogger(__name__)


class DocsExtractor(BaseDocsExtractor):
    """Extracts column metadata, data types, descriptions, and test assertions."""

    def extract_model_doc(
        self,
        con: duckdb.DuckDBPyConnection,
        model: ModelDefinition,
        tests: list[TestDefinition] | None = None,
        catalog: Any = None,
        column_descriptions: dict[str, str] | None = None,
        model_description: str | None = None,
    ) -> ModelDoc:
        """Construct full ModelDoc by inspecting live DuckDB table and test definitions."""
        model_tests = [t for t in (tests or []) if t.model_name == model.name]
        columns = self._introspect_columns(con, model, model_tests, column_descriptions=column_descriptions)
        destinations = [d.path or d.target for d in model.config.destinations if d.target != "local" or d.path]

        mat_val = (
            model.config.materialized.value
            if hasattr(model.config.materialized, "value")
            else str(model.config.materialized)
        )
        sources_list = model.sources + model.direct_connections
        desc = model.description or model.config.description or model_description or ""

        return ModelDoc(
            name=model.name,
            project=model.project,
            description=desc,
            materialization=mat_val,
            destinations=destinations,
            tags=model.config.tags,
            columns=columns,
            compiled_sql=model.compiled_sql,
            raw_sql=model.raw_sql,
            upstream_models=model.refs,
            upstream_sources=sources_list,
            sources_detail=self._extract_sources_detail(sources_list, catalog),
            destinations_detail=self._extract_destinations_detail(model.config.destinations),
            tests_detail=self._extract_tests_detail(model_tests),
        )

    def _extract_sources_detail(self, sources: list[str], catalog: Any) -> list[SourceDoc]:
        """Resolve full connection metadata (type, tier, file path) from catalog."""
        details: list[SourceDoc] = []
        for src in sources:
            conn = catalog.get_connection(src) if catalog and hasattr(catalog, "get_connection") else None
            if conn:
                tier_str = conn.tier.value if hasattr(conn.tier, "value") else str(conn.tier)
                opts = getattr(conn, "options", None) or getattr(conn, "config", {}) or {}
                path_str = str(opts.get("path") or opts.get("url") or opts.get("query") or opts.get("database") or "")
                conn_type = getattr(conn, "type", None) or getattr(conn, "connector_type", "csv")
                details.append(SourceDoc(name=conn.name, connector_type=conn_type, tier=tier_str, path=path_str, description=conn.description or ""))
            else:
                details.append(SourceDoc(name=src, connector_type="inferred", tier="entity", path="", description="Source connection"))
        return details

    def _extract_destinations_detail(self, dests: list[Any]) -> list[DestinationDoc]:
        """Convert model destination specs to detailed documentation records."""
        details: list[DestinationDoc] = []
        for d in dests:
            if d.target != "local" or d.path:
                target_str = getattr(d, "target", "csv")
                path_str = str(getattr(d, "path", "") or "")
                if not path_str and ("/" in target_str or "\\" in target_str or "." in target_str):
                    path_str = target_str
                    ext = Path(path_str).suffix.replace(".", "").lower() or "csv"
                    target_str = ext
                mode_val = getattr(d, "mode", "replace")
                mode_str = mode_val.value if hasattr(mode_val, "value") else str(mode_val)
                opts = {"mode": mode_str}
                if getattr(d, "format", None):
                    opts["format"] = d.format
                if getattr(d, "connection", None):
                    opts["connection"] = d.connection
                details.append(DestinationDoc(target=target_str, path=path_str, options=opts))
        return details

    def _extract_tests_detail(self, tests: list[TestDefinition]) -> list[TestDoc]:
        """Build comprehensive test assertion specifications and failure behavior."""
        details: list[TestDoc] = []
        for t in tests:
            sev_val = t.severity.value if hasattr(t.severity, "value") else str(t.severity)
            action = (
                "Isolates violating records to quarantine sink; pipeline continues"
                if sev_val == "quarantine"
                else ("Logs warning notification; pipeline continues" if sev_val == "warn" else "Halts pipeline execution immediately; prevents downstream write")
            )
            ttype_val = t.test_type.value if hasattr(t.test_type, "value") else str(t.test_type)
            params = getattr(t, "parameters", None) or getattr(t, "params", {}) or {}
            cond = f"Values: {params.get('values', [])}" if ttype_val == "accepted_values" else (f"Expr: {params.get('expression', '')}" if ttype_val == "expression" else ("Zero duplicate values" if ttype_val == "unique" else "Zero NULL values"))
            details.append(TestDoc(name=t.name, column=t.column_name or "", test_type=ttype_val.upper(), severity=sev_val.upper(), action_on_failure=action, details=cond))
        return details

    def _introspect_columns(
        self,
        con: duckdb.DuckDBPyConnection,
        model: ModelDefinition,
        tests: list[TestDefinition],
        column_descriptions: dict[str, str] | None = None,
    ) -> list[ColumnDoc]:
        """Introspect table schema via DESCRIBE and associate test badges with columns."""
        raw_schema = self._fetch_describe_schema(con, model)
        columns: list[ColumnDoc] = []
        descs = column_descriptions or {}
        for col_name, data_type in raw_schema:
            badges = self._collect_test_badges(col_name, tests)
            desc = descs.get(col_name, "")
            columns.append(ColumnDoc(name=col_name, data_type=data_type, description=desc, test_badges=badges))
        return columns

    @staticmethod
    def load_schema_descriptions(models_dir: Path) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
        """Extract model-level and column-level descriptions from schema.yml files."""
        model_descs: dict[str, str] = {}
        col_descs: dict[str, dict[str, str]] = {}
        if not models_dir.exists():
            return model_descs, col_descs
        import yaml
        for sf in sorted(models_dir.rglob("schema.y*ml")):
            try:
                data = yaml.safe_load(sf.read_text(encoding="utf-8")) or {}
                for m in data.get("models", []):
                    m_name = m.get("name")
                    if not m_name:
                        continue
                    if m.get("description"):
                        model_descs[m_name] = str(m["description"]).strip()
                    m_cols = col_descs.setdefault(m_name, {})
                    for c in m.get("columns", []):
                        c_name = c.get("name")
                        if c_name and c.get("description"):
                            m_cols[c_name] = str(c["description"]).strip()
            except Exception:
                pass
        return model_descs, col_descs

    def _fetch_describe_schema(
        self, con: duckdb.DuckDBPyConnection, model: ModelDefinition
    ) -> list[tuple[str, str]]:
        """Query DuckDB DESCRIBE statement, handling missing tables gracefully."""
        try:
            res = con.execute(f"DESCRIBE {model.name}").fetchall()
            return [(str(row[0]), str(row[1])) for row in res]
        except Exception:
            pass
        if model.compiled_sql:
            try:
                res = con.execute(f"DESCRIBE ({model.compiled_sql})").fetchall()
                return [(str(row[0]), str(row[1])) for row in res]
            except Exception as exc:
                logger.debug("Could not DESCRIBE model '%s': %s", model.name, exc)
        return []

    def _collect_test_badges(self, column_name: str, tests: list[TestDefinition]) -> list[str]:
        """Collect all active test assertion badges for a given column."""
        badges: list[str] = []
        for t in tests:
            if t.column_name == column_name:
                badge = f"{t.test_type.value.upper()}"
                if t.severity.value == "quarantine":
                    badge += " (QUARANTINE)"
                badges.append(badge)
        return sorted(badges)
