"""det.gui.server - FastAPI backend server for the det Catalog Web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from det.catalog.config import get_default_catalog_path
from det.catalog.models import DatasetMetadata, ScanResult
from det.catalog.service import CatalogService

app = FastAPI(
    title="det Catalog Explorer",
    description="Interactive graphical interface and REST API for the det YAML Catalog",
    version="0.1.0",
)

# Global catalog service instance managed by the server
_service: CatalogService | None = None


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


# --- Request & Response Models ---


class SwitchCatalogRequest(BaseModel):
    """Payload to switch active catalog YAML file."""

    path: str = Field(..., description="File path to the target YAML catalog")
    set_as_default: bool = Field(False, description="Whether to persist this as the default catalog")


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


@app.get("/api/catalog/yaml", response_class=PlainTextResponse)
def get_catalog_yaml() -> str:
    """Return the raw YAML representation of the active catalog."""
    service = get_service()
    return service.export_yaml()


# --- Namespace / Category Management ---


class CreateNamespaceRequest(BaseModel):
    name: str = Field(..., description="Name of the new namespace")


class RenameNamespaceRequest(BaseModel):
    new_name: str = Field(..., description="New name for the namespace")


@app.get("/api/namespaces")
def list_namespaces():
    """List all namespaces / categories with their dataset counts."""
    service = get_service()
    return service.list_namespaces()


@app.post("/api/namespaces", status_code=status.HTTP_201_CREATED)
def create_namespace(req: CreateNamespaceRequest):
    """Create a new namespace in the catalog."""
    service = get_service()
    try:
        created = service.create_namespace(req.name)
        return {"name": created}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.put("/api/namespaces/{name}")
def rename_namespace(name: str, req: RenameNamespaceRequest):
    """Rename a namespace and cascade updates to all its datasets."""
    service = get_service()
    try:
        updated = service.rename_namespace(name, req.new_name)
        return {"old_name": name, "new_name": req.new_name, "updated_datasets": updated}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.delete("/api/namespaces/{name}")
def delete_namespace(name: str, reassign_to: str | None = Query("default")):
    """Delete a namespace, reassigning or removing its datasets."""
    service = get_service()
    affected = service.delete_namespace(name, reassign_to=reassign_to)
    return {"name": name, "affected_datasets": affected}


@app.get("/api/datasets", response_model=list[DatasetMetadata])
def list_datasets(
    search: str | None = Query(None, description="Search term for names, columns, or tags"),
    namespace: str | None = Query(None, description="Filter by namespace"),
) -> list[DatasetMetadata]:
    """List all registered datasets in the active catalog."""
    service = get_service()
    return service.list_datasets(search=search, namespace=namespace)


@app.get("/api/datasets/{dataset_id:path}", response_model=DatasetMetadata)
def get_dataset(dataset_id: str) -> DatasetMetadata:
    """Retrieve metadata for a specific dataset by ID."""
    service = get_service()
    dataset = service.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )
    return dataset


@app.post("/api/datasets", response_model=DatasetMetadata, status_code=status.HTTP_201_CREATED)
def register_dataset(dataset: DatasetMetadata) -> DatasetMetadata:
    """Register a new dataset in the catalog."""
    service = get_service()
    try:
        return service.register_dataset(dataset)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.put("/api/datasets/{dataset_id:path}", response_model=DatasetMetadata)
def update_dataset(dataset_id: str, updates: DatasetMetadata) -> DatasetMetadata:
    """Update an existing dataset's schema and metadata."""
    service = get_service()
    try:
        return service.update_dataset(dataset_id, updates)
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
def delete_dataset(dataset_id: str) -> None:
    """Delete a dataset from the catalog."""
    service = get_service()
    if not service.delete_dataset(dataset_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )


@app.post("/api/datasets/{dataset_id:path}/rescan", response_model=DatasetMetadata)
def rescan_dataset(dataset_id: str) -> DatasetMetadata:
    """Re-scan the underlying location for an existing dataset to update its schema."""
    service = get_service()
    try:
        return service.rescan_dataset(dataset_id)
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
