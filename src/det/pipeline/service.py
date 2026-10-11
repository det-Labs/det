"""det.pipeline.service - Programmatic Command API for Pipeline Projects and Categories."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from det.pipeline.config import (
    add_known_pipeline_file,
    get_default_pipeline_path,
    get_known_pipeline_files,
    remove_known_pipeline_file,
    set_default_pipeline_path,
)
from det.pipeline.models import PipelineCategory, PipelineStoreFile, Project, _utcnow_iso
from det.pipeline.store import get_pipeline_yaml_str, load_pipeline_store, save_pipeline_store

_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _validate_identifier(name: str, entity_type: str = "Name") -> str:
    """Ensure identifier is non-empty and contains valid characters."""
    clean = name.strip()
    if not clean:
        raise ValueError(f"{entity_type} cannot be empty.")
    if not _NAME_PATTERN.match(clean):
        raise ValueError(
            f"{entity_type} '{clean}' is invalid. Use letters, numbers, underscores, and hyphens."
        )
    return clean


class PipelineService:
    """Service providing business logic and CRUD operations for pipeline projects and categories."""

    def __init__(self, file_path: str | Path | None = None) -> None:
        """Initialize service bound to a specific or default pipelines YAML file."""
        if file_path is not None:
            self.active_path = Path(file_path).resolve()
        else:
            self.active_path = get_default_pipeline_path()

    def _resolve_path(self, file_path: str | Path | None = None) -> Path:
        """Resolve target pipeline file path, falling back to active path."""
        if file_path:
            p = Path(file_path).resolve()
            if not p.is_file():
                for known in get_known_pipeline_files():
                    if (
                        known.name == p.name
                        or known.stem == p.stem
                        or str(known).endswith(str(file_path))
                    ):
                        return known
            return p
        return self.active_path

    def _load(self, file_path: str | Path | None = None) -> PipelineStoreFile:
        """Load the pipeline store for target path."""
        return load_pipeline_store(self._resolve_path(file_path))

    def _save(self, store: PipelineStoreFile, file_path: str | Path | None = None) -> None:
        """Save the pipeline store to the target path."""
        save_pipeline_store(self._resolve_path(file_path), store)

    # --- Multi-File Pipeline Store Management ---

    def switch_file(self, new_path: str | Path, set_as_default: bool = False) -> Path:
        """Switch active pipeline file path and optionally set as default."""
        path = Path(new_path).resolve()
        if not path.is_file():
            self.create_pipeline_file(path, set_as_default=set_as_default)
            return path
        self.active_path = path
        add_known_pipeline_file(path)
        if set_as_default:
            set_default_pipeline_path(path)
        return path

    def create_pipeline_file(
        self,
        new_path: str | Path,
        set_as_default: bool = False,
        overwrite: bool = False,
    ) -> Path:
        """Create a new pipeline YAML file and switch to it as active."""
        path = Path(new_path).resolve()
        if path.exists() and not overwrite:
            raise FileExistsError(f"Pipeline YAML file already exists at '{path}'.")

        new_store = PipelineStoreFile(
            version=1,
            projects=[
                Project(
                    name="default_project",
                    description="Default Data Engineering project",
                    created_at=_utcnow_iso(),
                    updated_at=_utcnow_iso(),
                    categories=[
                        PipelineCategory(
                            name="default",
                            description="Default pipeline category",
                            pipelines=[],
                        )
                    ],
                )
            ],
        )
        save_pipeline_store(path, new_store)
        self.active_path = path
        add_known_pipeline_file(path)
        if set_as_default:
            set_default_pipeline_path(path)
        return path

    def remove_pipeline_file(self, path: str | Path) -> bool:
        """Remove a pipeline file from the known pipelines list."""
        removed = remove_known_pipeline_file(path)
        resolved = Path(path).resolve()
        if self.active_path == resolved:
            self.active_path = get_default_pipeline_path()
        return removed

    def get_full_tree(self) -> list[dict[str, Any]]:
        """Return the multi-file pipeline hierarchy for all known pipeline files."""
        known_paths = get_known_pipeline_files()
        default_path = get_default_pipeline_path()
        tree: list[dict[str, Any]] = []

        for p_path in known_paths:
            try:
                store = load_pipeline_store(p_path)
            except OSError, ValueError, TypeError:
                continue

            is_active = p_path == self.active_path
            is_default = p_path == default_path

            projects_tree = []
            file_categories_count = 0
            file_pipelines_count = 0

            for p in store.projects:
                cats = []
                proj_pipe_count = 0
                for c in p.categories:
                    cats.append(
                        {
                            "name": c.name,
                            "description": c.description,
                            "pipeline_count": len(c.pipelines),
                            "total_pipelines": len(c.pipelines),
                            "pipelines": [pipe.model_dump() for pipe in c.pipelines],
                        }
                    )
                    proj_pipe_count += len(c.pipelines)

                file_categories_count += len(p.categories)
                file_pipelines_count += proj_pipe_count

                projects_tree.append(
                    {
                        "name": p.name,
                        "description": p.description,
                        "created_at": p.created_at,
                        "updated_at": p.updated_at,
                        "category_count": len(p.categories),
                        "total_categories": len(p.categories),
                        "pipeline_count": proj_pipe_count,
                        "total_pipelines": proj_pipe_count,
                        "categories": cats,
                    }
                )

            tree.append(
                {
                    "path": str(p_path),
                    "filename": p_path.name,
                    "name": p_path.stem,
                    "is_active": is_active,
                    "is_default": is_default,
                    "total_projects": len(store.projects),
                    "total_categories": file_categories_count,
                    "total_pipelines": file_pipelines_count,
                    "projects": projects_tree,
                }
            )

        return tree

    # --- Project CRUD ---

    def list_projects(
        self, search: str | None = None, file_path: str | Path | None = None
    ) -> list[Project]:
        """List all projects, optionally filtering by search substring."""
        store = self._load(file_path)
        if not search:
            return store.projects
        query = search.strip().lower()
        return [
            p
            for p in store.projects
            if query in p.name.lower() or (p.description and query in p.description.lower())
        ]

    def get_project(self, name: str, file_path: str | Path | None = None) -> Project | None:
        """Retrieve a project by name."""
        clean_name = name.strip()
        store = self._load(file_path)
        for p in store.projects:
            if p.name == clean_name:
                return p
        return None

    def create_project(
        self,
        name: str,
        description: str | None = None,
        file_path: str | Path | None = None,
    ) -> Project:
        """Create a new project with an initial default category."""
        clean_name = _validate_identifier(name, "Project name")
        store = self._load(file_path)

        for p in store.projects:
            if p.name.lower() == clean_name.lower():
                raise ValueError(f"Project '{clean_name}' already exists.")

        now = _utcnow_iso()
        project = Project(
            name=clean_name,
            description=description.strip() if description else None,
            created_at=now,
            updated_at=now,
            categories=[
                PipelineCategory(name="default", description="Default category", pipelines=[])
            ],
        )
        store.projects.append(project)
        self._save(store, file_path)
        return project

    def update_project(
        self,
        name: str,
        new_name: str | None = None,
        description: str | None = None,
        file_path: str | Path | None = None,
    ) -> Project:
        """Update an existing project's name and/or description."""
        clean_name = name.strip()
        store = self._load(file_path)
        target_idx: int | None = None

        for idx, p in enumerate(store.projects):
            if p.name == clean_name:
                target_idx = idx
                break

        if target_idx is None:
            raise ValueError(f"Project '{clean_name}' not found.")

        proj = store.projects[target_idx]

        if new_name is not None:
            clean_new_name = _validate_identifier(new_name, "Project name")
            if clean_new_name != proj.name:
                for idx, p in enumerate(store.projects):
                    if idx != target_idx and p.name.lower() == clean_new_name.lower():
                        raise ValueError(f"Project '{clean_new_name}' already exists.")
                proj.name = clean_new_name

        if description is not None:
            proj.description = description.strip() if description else None

        proj.updated_at = _utcnow_iso()
        store.projects[target_idx] = proj
        self._save(store, file_path)
        return proj

    def delete_project(self, name: str, file_path: str | Path | None = None) -> bool:
        """Permanently delete a project and all its categories and pipelines."""
        clean_name = name.strip()
        store = self._load(file_path)
        original_count = len(store.projects)
        store.projects = [p for p in store.projects if p.name != clean_name]

        if len(store.projects) == original_count:
            raise ValueError(f"Project '{clean_name}' not found.")

        self._save(store, file_path)
        return True

    # --- Category CRUD ---

    def list_categories(
        self, project_name: str, file_path: str | Path | None = None
    ) -> list[PipelineCategory]:
        """List all categories within a project."""
        proj = self.get_project(project_name, file_path=file_path)
        if proj is None:
            raise ValueError(f"Project '{project_name}' not found.")
        return proj.categories

    def get_category(
        self, project_name: str, category_name: str, file_path: str | Path | None = None
    ) -> PipelineCategory | None:
        """Retrieve a specific category inside a project."""
        proj = self.get_project(project_name, file_path=file_path)
        if proj is None:
            return None
        clean_cat = category_name.strip()
        for c in proj.categories:
            if c.name == clean_cat:
                return c
        return None

    def create_category(
        self,
        project_name: str,
        category_name: str,
        description: str | None = None,
        file_path: str | Path | None = None,
    ) -> PipelineCategory:
        """Create a new category in a project."""
        clean_proj = project_name.strip()
        clean_cat = _validate_identifier(category_name, "Category name")
        store = self._load(file_path)

        target_proj: Project | None = None
        for p in store.projects:
            if p.name == clean_proj:
                target_proj = p
                break

        if target_proj is None:
            raise ValueError(f"Project '{clean_proj}' not found.")

        for c in target_proj.categories:
            if c.name.lower() == clean_cat.lower():
                raise ValueError(
                    f"Category '{clean_cat}' already exists in project '{clean_proj}'."
                )

        new_category = PipelineCategory(
            name=clean_cat,
            description=description.strip() if description else None,
            pipelines=[],
        )
        target_proj.categories.append(new_category)
        target_proj.updated_at = _utcnow_iso()
        self._save(store, file_path)
        return new_category

    def update_category(
        self,
        project_name: str,
        category_name: str,
        new_name: str,
        description: str | None = None,
        file_path: str | Path | None = None,
    ) -> PipelineCategory:
        """Update/rename a category inside a project."""
        clean_proj = project_name.strip()
        clean_old_cat = category_name.strip()
        clean_new_name = _validate_identifier(new_name, "Category name")
        store = self._load(file_path)

        target_proj: Project | None = None
        for p in store.projects:
            if p.name == clean_proj:
                target_proj = p
                break

        if target_proj is None:
            raise ValueError(f"Project '{clean_proj}' not found.")

        cat_idx: int | None = None
        for idx, c in enumerate(target_proj.categories):
            if c.name == clean_old_cat:
                cat_idx = idx
                break

        if cat_idx is None:
            raise ValueError(f"Category '{clean_old_cat}' not found in project '{clean_proj}'.")

        if clean_new_name != clean_old_cat:
            for idx, c in enumerate(target_proj.categories):
                if idx != cat_idx and c.name.lower() == clean_new_name.lower():
                    raise ValueError(
                        f"Category '{clean_new_name}' already exists in project '{clean_proj}'."
                    )
            target_proj.categories[cat_idx].name = clean_new_name

        if description is not None:
            target_proj.categories[cat_idx].description = (
                description.strip() if description else None
            )

        target_proj.updated_at = _utcnow_iso()
        self._save(store, file_path)
        return target_proj.categories[cat_idx]

    def delete_category(
        self, project_name: str, category_name: str, file_path: str | Path | None = None
    ) -> bool:
        """Permanently delete a category and all pipelines inside from a project."""
        clean_proj = project_name.strip()
        clean_cat = category_name.strip()
        store = self._load(file_path)

        target_proj: Project | None = None
        for p in store.projects:
            if p.name == clean_proj:
                target_proj = p
                break

        if target_proj is None:
            raise ValueError(f"Project '{clean_proj}' not found.")

        orig_len = len(target_proj.categories)
        target_proj.categories = [c for c in target_proj.categories if c.name != clean_cat]

        if len(target_proj.categories) == orig_len:
            raise ValueError(f"Category '{clean_cat}' not found in project '{clean_proj}'.")

        target_proj.updated_at = _utcnow_iso()
        self._save(store, file_path)
        return True

    # --- Tree View Helper for GUI ---

    def get_tree(self, file_path: str | Path | None = None) -> dict[str, Any]:
        """Return hierarchical tree for Explorer GUI (Project > Category > Pipelines)."""
        target_path = self._resolve_path(file_path)
        store = self._load(target_path)
        projects_tree = []
        total_categories = 0
        total_pipelines = 0

        for p in store.projects:
            cats = []
            proj_pipelines_count = 0
            for c in p.categories:
                cats.append(
                    {
                        "name": c.name,
                        "description": c.description,
                        "pipeline_count": len(c.pipelines),
                        "total_pipelines": len(c.pipelines),
                        "pipelines": [pipe.model_dump() for pipe in c.pipelines],
                    }
                )
                proj_pipelines_count += len(c.pipelines)

            total_categories += len(p.categories)
            total_pipelines += proj_pipelines_count

            projects_tree.append(
                {
                    "name": p.name,
                    "description": p.description,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                    "category_count": len(p.categories),
                    "total_categories": len(p.categories),
                    "pipeline_count": proj_pipelines_count,
                    "total_pipelines": proj_pipelines_count,
                    "categories": cats,
                }
            )

        return {
            "active_path": str(self.active_path),
            "target_path": str(target_path),
            "total_projects": len(store.projects),
            "total_categories": total_categories,
            "total_pipelines": total_pipelines,
            "projects": projects_tree,
            "pipeline_files": self.get_full_tree(),
        }

    def export_yaml(self, file_path: str | Path | None = None) -> str:
        """Export raw YAML representation of the pipeline store."""
        target_path = self._resolve_path(file_path)
        return get_pipeline_yaml_str(target_path)
