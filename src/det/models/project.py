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
        """Discover all valid project folders in the workspace, including nested group folders."""
        projects_dir = self._root / "projects"
        if projects_dir.exists() and projects_dir.is_dir():
            found: list[str] = []
            for d in sorted(projects_dir.iterdir()):
                if not d.is_dir() or d.name.startswith((".", "_")):
                    continue
                # If directory is a project directly (contains models/ or det_project.yaml)
                if (d / "models").exists() or (d / "det_project.yaml").exists():
                    found.append(d.name)
                else:
                    # Directory is a filesystem group folder (e.g. projects/sample_pipelines/)
                    for sub in sorted(d.iterdir()):
                        if sub.is_dir() and not sub.name.startswith((".", "_")):
                            if (sub / "models").exists() or (sub / "det_project.yaml").exists():
                                found.append(sub.name)
            if found:
                return sorted(list(dict.fromkeys(found)))

        # Fallback to default single-project workspace
        if (self._root / "models").exists():
            return ["default"]
        return []

    def get_project_folder(self, project_name: str) -> str:
        """Resolve the parent folder name for a project based on its filesystem hierarchy."""
        models_dir = self._get_models_directory(project_name)
        if models_dir.exists():
            proj_dir = models_dir.parent
            try:
                rel = proj_dir.relative_to(self._root / "projects")
                if len(rel.parts) > 1:
                    return rel.parts[0]
            except ValueError:
                pass
        return "Core Pipelines"

    def delete_project(self, project_name: str) -> bool:
        """Delete a project folder from the workspace."""
        import shutil
        models_dir = self._get_models_directory(project_name)
        target_dir = models_dir.parent
        if target_dir.exists() and target_dir.is_dir() and target_dir != self._root / "projects":
            shutil.rmtree(target_dir, ignore_errors=True)
            # If parent group folder is now empty (e.g. sample_pipelines), remove it
            parent = target_dir.parent
            if parent != self._root / "projects" and parent.exists():
                try:
                    if not any(parent.iterdir()):
                        parent.rmdir()
                except OSError:
                    pass
            return True
        return False

    def load_project_models(self, project_name: str) -> list[ModelDefinition]:
        """Load and parse all SQL models belonging to a specific project with mtime caching."""
        models_dir = self._get_models_directory(project_name)
        if not models_dir.exists():
            return []

        all_sql_files = [f for f in sorted(models_dir.rglob("*.sql")) if not f.name.startswith((".", "_"))]
        current_mtime = max((f.stat().st_mtime for f in all_sql_files), default=0.0)
        if not hasattr(self, "_models_cache"):
            self._models_cache: dict[str, tuple[float, list[ModelDefinition]]] = {}
        cached = self._models_cache.get(project_name)
        if cached and cached[0] == current_mtime:
            return cached[1]

        known_connections = self._get_known_connection_names()
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

        self._models_cache[project_name] = (current_mtime, models)
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
        projects_dir = self._root / "projects"
        direct = projects_dir / project_name / "models"
        if direct.exists():
            return direct
        # Also check nested group folders, e.g. projects/<folder>/<project_name>/models
        if projects_dir.exists():
            for p in projects_dir.glob(f"**/{project_name}/models"):
                if p.is_dir():
                    return p
        return direct

    def _get_known_connection_names(self) -> set[str]:
        """Fetch all connection identifiers from the catalog manager if present."""
        if self._catalog is not None:
            return {c.name for c in self._catalog.list_connections()}
        return set()

