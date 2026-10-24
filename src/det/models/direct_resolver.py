"""Auto-discovery of direct catalog connection references inside SQL queries."""

import re
from det.models.base import BaseDirectResolver

# Pattern matching FROM or JOIN followed by table/view identifier
TABLE_REF_PATTERN = re.compile(
    r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)",
    re.IGNORECASE,
)
# Pattern matching CTE names: WITH cte_name AS (...) or , cte_name AS (...)
CTE_PATTERN = re.compile(
    r"(?:WITH|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(", re.IGNORECASE
)


class DirectConnectionResolver(BaseDirectResolver):
    """Detects connection identifiers queried directly without {{ source() }}."""

    def resolve_connections(
        self,
        sql: str,
        known_connections: set[str],
        known_models: set[str] | None = None,
    ) -> set[str]:
        """Return set of known connection names referenced as tables in SQL."""
        models = known_models or set()
        ctes = self._extract_cte_names(sql)
        excluded = models.union(ctes)

        referenced_tables = self._extract_table_identifiers(sql)
        detected_connections: set[str] = set()

        for table_ident in referenced_tables:
            root_name = self._get_root_identifier(table_ident)
            if root_name in excluded:
                continue
            if root_name in known_connections:
                detected_connections.add(root_name)

        return detected_connections

    def resolve_model_refs(
        self,
        sql: str,
        known_models: set[str],
        current_model: str | None = None,
    ) -> set[str]:
        """Return set of known model names referenced directly as tables in SQL."""
        ctes = self._extract_cte_names(sql)
        excluded = ctes.union({current_model} if current_model else set())
        referenced_tables = self._extract_table_identifiers(sql)
        detected_models: set[str] = set()

        for table_ident in referenced_tables:
            root_name = self._get_root_identifier(table_ident)
            if root_name in excluded:
                continue
            if root_name in known_models:
                detected_models.add(root_name)

        return detected_models

    def _extract_table_identifiers(self, sql: str) -> set[str]:
        """Extract all table or relation names following FROM or JOIN."""
        tables: set[str] = set()
        for match in TABLE_REF_PATTERN.finditer(sql):
            raw_target = match.group(1).strip()
            if raw_target:
                tables.add(raw_target)
        return tables

    def _extract_cte_names(self, sql: str) -> set[str]:
        """Extract Common Table Expression (CTE) aliases from WITH clauses."""
        ctes: set[str] = set()
        for match in CTE_PATTERN.finditer(sql):
            cte_name = match.group(1).strip()
            if cte_name:
                ctes.add(cte_name)
        return ctes

    def _get_root_identifier(self, full_ident: str) -> str:
        """Extract root catalog/connection identifier from dotted names."""
        parts = full_ident.split(".")
        return parts[0].strip()

