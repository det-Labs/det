"""Multi-project workspace discovery, model loading, and DAG compilation."""

import logging
from pathlib import Path
from typing import Any

from det.catalog.manager import CatalogManager
from det.models.base import BaseProjectManager
from det.models.dag import ModelDAG
from det.models.definition import ModelDefinition
from det.models.direct_resolver import DirectConnectionResolver
from det.models.parser import ModelParser

logger = logging.getLogger(__name__)


class ProjectManager(BaseProjectManager):
    """Discovers, parses, and orchestrates multi-project model workspaces."""

    def __init__(
        self,
        workspace_root: Path,
        catalog_manager: CatalogManager | None = None,
        parser: ModelParser | None = None,
        direct_resolver: DirectConnectionResolver | None = None,
    ) -> None:
        self._root = workspace_root
        self._catalog = catalog_manager
        self._parser = parser or ModelParser()
        self._resolver = direct_resolver or DirectConnectionResolver()

    def discover_projects(self) -> list[str]:
        """Discover all valid project folders in the workspace."""
        projects_dir = self._root / "projects"
        if projects_dir.exists() and projects_dir.is_dir():
            found = [
                d.name
                for d in projects_dir.iterdir()
                if d.is_dir() and not d.name.startswith((".", "_"))
            ]
            if found:
                return sorted(found)

        # Fallback to default single-project workspace
        if (self._root / "models").exists():
            return ["default"]
        return []

    def load_project_models(self, project_name: str) -> list[ModelDefinition]:
        """Load and parse all SQL models belonging to a specific project."""
        models_dir = self._get_models_directory(project_name)
        if not models_dir.exists():
            return []

        known_connections = self._get_known_connection_names()
        all_sql_files = [f for f in sorted(models_dir.rglob("*.sql")) if not f.name.startswith((".", "_"))]
        known_models = {f.stem for f in all_sql_files}
        models: list[ModelDefinition] = []

        for sql_file in all_sql_files:
            model = self._parser.parse_file(sql_file, project=project_name)
            # Auto-resolve direct connection references in the SQL
            direct_conns = self._resolver.resolve_connections(
                model.compiled_sql,
                known_connections=known_connections,
                known_models=known_models,
            )
            model.direct_connections = sorted(direct_conns)
            # Auto-resolve direct model references without {{ ref(...) }}
            direct_refs = self._resolver.resolve_model_refs(
                model.compiled_sql,
                known_models=known_models,
                current_model=model.name,
            )
            for r in direct_refs:
                if r not in model.refs:
                    model.refs.append(r)
            model.refs.sort()
            models.append(model)

        return models

    def build_dag(self, project_name: str | None = None) -> ModelDAG:
        """Compile a ModelDAG for a single project or all projects in workspace."""
        dag = ModelDAG()
        target_projects = [project_name] if project_name else self.discover_projects()

        for proj in target_projects:
            for model in self.load_project_models(proj):
                if model.config.enabled:
                    dag.add_model(model)

        return dag

    def _get_models_directory(self, project_name: str) -> Path:
        """Resolve directory path containing model SQL files for a project."""
        if project_name == "default" and (self._root / "models").exists():
            return self._root / "models"
        return self._root / "projects" / project_name / "models"

    def _get_known_connection_names(self) -> set[str]:
        """Fetch all connection identifiers from the catalog manager if present."""
        if self._catalog is not None:
            return {c.name for c in self._catalog.list_connections()}
        return set()

