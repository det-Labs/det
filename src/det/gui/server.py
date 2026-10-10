"""det.gui.server - FastAPI backend server for the det Catalog Web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from det.catalog.config import get_default_catalog_path
from det.catalog.models import DatasetMetadata, ScanResult
from det.catalog.service import CatalogService
from det.pipeline import PipelineService
from det.pipeline.models import PipelineCategory, Project

app = FastAPI(
    title="det Data Platform Studio",
    description="Interactive graphical interface and REST API for det Catalog and Pipelines",
    version="0.1.0",
)

# Global catalog service instance managed by the server
_service: CatalogService | None = None
_pipeline_service: PipelineService | None = None


def get_service() -> CatalogService:
    """Retrieve the active CatalogService instance, initializing with default if needed."""
    global _service
    if _service is None:
        _service = CatalogService()
    return _service


def set_service(service: CatalogService) -> None:
    """Explicitly assign the active CatalogService instance."""
    global _service
    _service = service


def get_pipeline_service() -> PipelineService:
    """Retrieve the active PipelineService instance, initializing with default if needed."""
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = PipelineService()
    return _pipeline_service


def set_pipeline_service(service: PipelineService) -> None:
    """Explicitly assign the active PipelineService instance."""
    global _pipeline_service
    _pipeline_service = service


# --- Request & Response Models ---


class CreateProjectRequest(BaseModel):
    """Payload to create a new pipeline project."""

    name: str = Field(..., description="Project name")
    description: str | None = Field(None, description="Optional project description")


class UpdateProjectRequest(BaseModel):
    """Payload to edit/rename a pipeline project."""

    new_name: str | None = Field(None, description="New project name")
    description: str | None = Field(None, description="New project description")


class CreateCategoryRequest(BaseModel):
    """Payload to create a category inside a project."""

    name: str = Field(..., description="Category name")
    description: str | None = Field(None, description="Optional category description")


class UpdateCategoryRequest(BaseModel):
    """Payload to rename/edit a category."""

    new_name: str = Field(..., description="New category name")
    description: str | None = Field(None, description="New category description")


class SwitchCatalogRequest(BaseModel):
    """Payload to switch active catalog YAML file."""

    path: str = Field(..., description="File path to the target YAML catalog")
    set_as_default: bool = Field(False, description="Whether to persist this as the default catalog")


class CreateCatalogRequest(BaseModel):
    """Payload to create a new catalog YAML file."""

    path: str = Field(..., description="File path for the new catalog YAML file")
    name: str = Field("det_catalog", description="Display name for the catalog")
    set_as_default: bool = Field(False, description="Whether to persist this as default")
    overwrite: bool = Field(False, description="Whether to overwrite if file exists")


class CatalogStatusResponse(BaseModel):
    """Status details regarding active and default catalog paths."""

    active_path: str
    default_path: str
    is_default: bool
    dataset_count: int


class ScanRequest(BaseModel):
    """Payload to request schema scanning for a path."""

    location: str = Field(..., description="File or folder path to scan")
    format_hint: str | None = Field(None, description="Optional format hint")


# --- API Routes ---


@app.get("/api/catalog/status", response_model=CatalogStatusResponse)
def get_catalog_status() -> CatalogStatusResponse:
    """Return active catalog file path and default preference status."""
    service = get_service()
    active = str(service.active_path)
    default = str(get_default_catalog_path())
    datasets = service.list_datasets()
    return CatalogStatusResponse(
        active_path=active,
        default_path=default,
        is_default=(active == default),
        dataset_count=len(datasets),
    )


@app.post("/api/catalog/switch", response_model=CatalogStatusResponse)
def switch_catalog(req: SwitchCatalogRequest) -> CatalogStatusResponse:
    """Switch the active catalog file path and optionally set it as default."""
    service = get_service()
    try:
        new_path = service.switch_catalog(req.path, set_as_default=req.set_as_default)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to switch catalog file: {exc}",
        ) from exc

    active = str(new_path)
    default = str(get_default_catalog_path())
    datasets = service.list_datasets()
    return CatalogStatusResponse(
        active_path=active,
        default_path=default,
        is_default=(active == default),
        dataset_count=len(datasets),
    )


@app.post("/api/catalog/create", response_model=CatalogStatusResponse)
def create_catalog(req: CreateCatalogRequest) -> CatalogStatusResponse:
    """Create a new catalog YAML file and switch to it as active."""
    service = get_service()
    try:
        new_path = service.create_catalog(
            req.path,
            name=req.name,
            set_as_default=req.set_as_default,
            overwrite=req.overwrite,
        )
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create catalog file: {exc}",
        ) from exc

    active = str(new_path)
    default = str(get_default_catalog_path())
    datasets = service.list_datasets()
    return CatalogStatusResponse(
        active_path=active,
        default_path=default,
        is_default=(active == default),
        dataset_count=len(datasets),
    )


@app.get("/api/tree")
def get_explorer_tree():
    """Return the complete 3-level tree: Catalog > Namespace > Tables."""
    service = get_service()
    return {"catalogs": service.get_full_tree()}


class OpenCatalogRequest(BaseModel):
    path: str = Field(..., description="Path to existing catalog YAML file")
    set_as_default: bool = Field(False, description="Whether to set as default")


@app.post("/api/catalog/open")
def open_catalog(req: OpenCatalogRequest):
    """Register an existing catalog into known catalogs and switch to it."""
    service = get_service()
    try:
        service.switch_catalog(req.path, set_as_default=req.set_as_default)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to open catalog file: {exc}",
        ) from exc
    return {"catalogs": service.get_full_tree()}


class RemoveCatalogRequest(BaseModel):
    path: str = Field(..., description="Path to catalog YAML file to remove from explorer")


@app.post("/api/catalog/remove")
def remove_catalog(req: RemoveCatalogRequest):
    """Remove a catalog from the known catalogs list in explorer."""
    service = get_service()
    service.remove_catalog(req.path)
    return {"catalogs": service.get_full_tree()}


class SetDefaultCatalogRequest(BaseModel):
    path: str = Field(..., description="Path to catalog YAML file to set as default")


@app.post("/api/catalog/set-default")
def set_default_catalog(req: SetDefaultCatalogRequest):
    """Persist a catalog as the default catalog."""
    from det.catalog.config import set_default_catalog_path

    try:
        set_default_catalog_path(req.path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to set default catalog: {exc}",
        ) from exc
    service = get_service()
    return {"catalogs": service.get_full_tree()}


@app.get("/api/catalog/yaml", response_class=PlainTextResponse)
def get_catalog_yaml(path: str | None = Query(None, description="Optional catalog path")) -> str:
    """Return the raw YAML representation of the active or specified catalog."""
    service = get_service()
    content = service.export_yaml(path)
    if not content and path:
        resolved = Path(path).resolve()
        if not resolved.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Catalog file not found: {path}",
            )
    return content


# --- Namespace / Category Management ---


class CreateNamespaceRequest(BaseModel):
    name: str = Field(..., description="Name of the new namespace")
    catalog_path: str | None = Field(None, description="Optional catalog path to create inside")


class RenameNamespaceRequest(BaseModel):
    new_name: str = Field(..., description="New name for the namespace")
    catalog_path: str | None = Field(None, description="Optional catalog path to rename inside")


@app.get("/api/namespaces")
def list_namespaces(catalog_path: str | None = Query(None)):
    """List all namespaces / categories with their dataset counts."""
    service = get_service()
    if catalog_path:
        service.switch_catalog(catalog_path)
    return service.list_namespaces()


@app.post("/api/namespaces", status_code=status.HTTP_201_CREATED)
def create_namespace(req: CreateNamespaceRequest):
    """Create a new namespace in the catalog."""
    service = get_service()
    try:
        created = service.create_namespace(req.name, catalog_path=req.catalog_path)
        return {"name": created}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.put("/api/namespaces/{name}")
def rename_namespace(name: str, req: RenameNamespaceRequest):
    """Rename a namespace and cascade updates to all its datasets."""
    service = get_service()
    try:
        updated = service.rename_namespace(name, req.new_name, catalog_path=req.catalog_path)
        return {"old_name": name, "new_name": req.new_name, "updated_datasets": updated}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.delete("/api/namespaces/{name}")
def delete_namespace(
    name: str,
    reassign_to: str | None = Query("default"),
    catalog_path: str | None = Query(None),
):
    """Delete a namespace, reassigning or removing its datasets."""
    service = get_service()
    affected = service.delete_namespace(name, reassign_to=reassign_to, catalog_path=catalog_path)
    return {"name": name, "affected_datasets": affected}


@app.get("/api/datasets", response_model=list[DatasetMetadata])
def list_datasets(
    search: str | None = Query(None, description="Search term for names, columns, or tags"),
    namespace: str | None = Query(None, description="Filter by namespace"),
    catalog_path: str | None = Query(None, description="Optional catalog path"),
) -> list[DatasetMetadata]:
    """List all registered datasets in the active or specified catalog."""
    service = get_service()
    return service.list_datasets(search=search, namespace=namespace, catalog_path=catalog_path)


@app.get("/api/datasets/{dataset_id:path}", response_model=DatasetMetadata)
def get_dataset(
    dataset_id: str,
    catalog_path: str | None = Query(None, description="Optional catalog path"),
) -> DatasetMetadata:
    """Retrieve metadata for a specific dataset by ID."""
    service = get_service()
    dataset = service.get_dataset(dataset_id, catalog_path=catalog_path)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )
    return dataset


@app.post("/api/datasets", response_model=DatasetMetadata, status_code=status.HTTP_201_CREATED)
def register_dataset(
    dataset: DatasetMetadata,
    catalog_path: str | None = Query(None, description="Optional catalog path"),
) -> DatasetMetadata:
    """Register a new dataset in the catalog."""
    service = get_service()
    try:
        return service.register_dataset(dataset, catalog_path=catalog_path)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.put("/api/datasets/{dataset_id:path}", response_model=DatasetMetadata)
def update_dataset(
    dataset_id: str,
    updates: DatasetMetadata,
    catalog_path: str | None = Query(None, description="Optional catalog path"),
) -> DatasetMetadata:
    """Update an existing dataset's schema and metadata."""
    service = get_service()
    try:
        return service.update_dataset(dataset_id, updates, catalog_path=catalog_path)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.delete("/api/datasets/{dataset_id:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: str,
    catalog_path: str | None = Query(None, description="Optional catalog path"),
) -> None:
    """Delete a dataset from the catalog."""
    service = get_service()
    if not service.delete_dataset(dataset_id, catalog_path=catalog_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )


@app.post("/api/datasets/{dataset_id:path}/rescan", response_model=DatasetMetadata)
def rescan_dataset(
    dataset_id: str,
    catalog_path: str | None = Query(None, description="Optional catalog path"),
) -> DatasetMetadata:
    """Re-scan the underlying location for an existing dataset to update its schema."""
    service = get_service()
    try:
        return service.rescan_dataset(dataset_id, catalog_path=catalog_path)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to scan location: {exc}",
        ) from exc


@app.post("/api/scan", response_model=ScanResult)
def scan_path(req: ScanRequest) -> ScanResult:
    """Scan a file or directory path and infer schema and row count."""
    service = get_service()
    try:
        return service.scan_path(req.location, req.format_hint)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to scan '{req.location}': {exc}",
        ) from exc


# --- Pipelines / ETL API Routes ---


@app.get("/api/pipelines/tree")
def get_pipelines_tree() -> dict[str, Any]:
    """Retrieve full hierarchical tree of projects, categories, and pipelines."""
    service = get_pipeline_service()
    return service.get_tree()


@app.get("/api/pipelines/projects", response_model=list[Project])
def list_pipeline_projects() -> list[Project]:
    """List all configured pipeline projects."""
    service = get_pipeline_service()
    return service.list_projects()


@app.post("/api/pipelines/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_pipeline_project(req: CreateProjectRequest) -> Project:
    """Create a new data engineering project."""
    service = get_pipeline_service()
    try:
        return service.create_project(name=req.name, description=req.description)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.put("/api/pipelines/projects/{name}", response_model=Project)
def update_pipeline_project(name: str, req: UpdateProjectRequest) -> Project:
    """Update or rename an existing pipeline project."""
    service = get_pipeline_service()
    try:
        return service.update_project(name=name, new_name=req.new_name, description=req.description)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.delete("/api/pipelines/projects/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline_project(name: str) -> None:
    """Delete a project and all its categories and pipelines."""
    service = get_pipeline_service()
    try:
        service.delete_project(name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.get("/api/pipelines/projects/{project}/categories", response_model=list[PipelineCategory])
def list_pipeline_categories(project: str) -> list[PipelineCategory]:
    """List categories inside a project."""
    service = get_pipeline_service()
    try:
        return service.list_categories(project)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.post("/api/pipelines/projects/{project}/categories", response_model=PipelineCategory, status_code=status.HTTP_201_CREATED)
def create_pipeline_category(project: str, req: CreateCategoryRequest) -> PipelineCategory:
    """Create a new category inside a project."""
    service = get_pipeline_service()
    try:
        return service.create_category(
            project_name=project,
            category_name=req.name,
            description=req.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.put("/api/pipelines/projects/{project}/categories/{category}", response_model=PipelineCategory)
def update_pipeline_category(project: str, category: str, req: UpdateCategoryRequest) -> PipelineCategory:
    """Rename or update a category inside a project."""
    service = get_pipeline_service()
    try:
        return service.update_category(
            project_name=project,
            category_name=category,
            new_name=req.new_name,
            description=req.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.delete("/api/pipelines/projects/{project}/categories/{category}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline_category(project: str, category: str) -> None:
    """Delete a category and all its pipelines from a project."""
    service = get_pipeline_service()
    try:
        service.delete_category(project_name=project, category_name=category)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.get("/api/pipelines/yaml", response_class=PlainTextResponse)
def get_pipelines_yaml() -> PlainTextResponse:
    """Return raw YAML content of the pipeline store."""
    service = get_pipeline_service()
    return PlainTextResponse(service.export_yaml())


# --- Serve Frontend Single Page App ---


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Serve the primary HTML application interface."""
    static_html_path = Path(__file__).parent / "static" / "index.html"
    if static_html_path.is_file():
        with open(static_html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    return HTMLResponse(
        content="<h1>det Catalog UI</h1><p>UI assets not found. Please verify static/index.html.</p>"
    )
