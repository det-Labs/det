"""HTTP API and static application for Catalog and Connectors."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from det.catalog.config import get_default_catalog_path, set_default_catalog_path
from det.catalog.models import (
    CatalogState,
    ColumnMetadata,
    DatasetMetadata,
    ScanResult,
)
from det.catalog.service import CatalogService
from det.connectors import (
    ConnectionTestResult,
    ConnectorError,
    DiscoveredObject,
    PreviewResult,
    SchemaResult,
    list_connectors_grouped,
)
from det.pipeline import PipelineService
from det.pipeline.models import PipelineCategory, Project

app = FastAPI(title="det Data Platform", version="0.1.0")
_INDEX_FILE = Path(__file__).parent / "static" / "index.html"
_service: CatalogService | None = None


def get_service() -> CatalogService:
    global _service
    if _service is None:
        _service = CatalogService()
    return _service


def set_service(service: CatalogService | None) -> None:
    global _service
    _service = service


# ---------------- Request Models ----------------


class CreateCatalogRequest(BaseModel):
    path: str = Field(min_length=1)
    name: str | None = None
    make_default: bool = False
    set_as_default: bool = False
    overwrite: bool = False


class OpenCatalogRequest(BaseModel):
    path: str = Field(min_length=1)
    make_default: bool = False
    set_as_default: bool = False


class CategoryRequest(BaseModel):
    name: str = Field(min_length=1)


class RenameCategoryRequest(BaseModel):
    old_name: str = Field(min_length=1)
    new_name: str = Field(min_length=1)


class CatalogSourceResponse(BaseModel):
    path: str
    content: str


class CreateConnectionRequest(BaseModel):
    name: str = Field(min_length=1)
    connector: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] = Field(default_factory=dict)
    connection_id: str | None = None
    source_id: str | None = None
    description: str = ""


class CreateSourceRequest(CreateConnectionRequest):
    """Backwards compatibility alias."""


class UpdateConnectionRequest(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    credentials: dict[str, Any] | None = None
    description: str | None = None


class UpdateSourceRequest(UpdateConnectionRequest):
    """Backwards compatibility alias."""


class CreateTableRequest(BaseModel):
    name: str = Field(min_length=1)
    namespace: str = "default"
    connector: str = Field(min_length=1)
    connection_id: str | None = None
    source_id: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    columns: list[ColumnMetadata] = Field(default_factory=list)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    row_count: int | None = None


class UpdateTableRequest(BaseModel):
    name: str | None = None
    namespace: str | None = None
    options: dict[str, Any] | None = None
    columns: list[ColumnMetadata] | None = None
    description: str | None = None
    tags: list[str] | None = None
    row_count: int | None = None


class ConnectorTestRequest(BaseModel):
    connector: str
    connection_id: str | None = None
    source_id: str | None = None
    source_config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class ConnectorDiscoverRequest(BaseModel):
    connector: str
    connection_id: str | None = None
    source_id: str | None = None
    source_config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class ConnectorSchemaRequest(BaseModel):
    connector: str
    connection_id: str | None = None
    source_id: str | None = None
    source_config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] = Field(default_factory=dict)
    table_options: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class ConnectorPreviewRequest(BaseModel):
    connector: str
    connection_id: str | None = None
    source_id: str | None = None
    source_config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] = Field(default_factory=dict)
    table_options: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    limit: int = 50



def _catalog_action(action, *args) -> Any:
    try:
        return action(*args)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ConnectorError, OSError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------- Static & Health Routes ----------------


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> HTMLResponse:
    if not _INDEX_FILE.is_file():
        raise HTTPException(status_code=500, detail="GUI assets are missing.")
    return HTMLResponse(_INDEX_FILE.read_text(encoding="utf-8"))


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


# ---------------- Catalog Lifecycle Routes ----------------


@app.get("/api/catalog/state", response_model=CatalogState)
def catalog_state() -> CatalogState:
    try:
        return get_service().state()
    except (OSError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/catalog/yaml", response_model=CatalogSourceResponse)
def catalog_yaml() -> CatalogSourceResponse:
    service = get_service()
    if service.active_path is None:
        raise HTTPException(status_code=409, detail="Open a catalog before viewing its YAML.")
    try:
        return CatalogSourceResponse(
            path=str(service.active_path),
            content=service.read_catalog_yaml(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/catalog/create")
def create_catalog(request: CreateCatalogRequest) -> dict[str, Any]:
    service = get_service()
    make_def = request.make_default or request.set_as_default
    try:
        new_path = service.create_catalog(
            request.path,
            name=request.name,
            make_default=make_def,
            overwrite=request.overwrite,
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

    state_dict = service.state().model_dump()
    state_dict["active_path"] = str(new_path.resolve())
    state_dict["dataset_count"] = len(service.list_datasets())
    state_dict["catalogs"] = service.get_full_tree()
    return state_dict


@app.post("/api/catalog/open")
def open_catalog(request: OpenCatalogRequest) -> dict[str, Any]:
    service = get_service()
    make_def = request.make_default or request.set_as_default
    try:
        service.switch_catalog(request.path, set_as_default=make_def)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to open catalog file: {exc}",
        ) from exc

    state_dict = service.state().model_dump()
    state_dict["catalogs"] = service.get_full_tree()
    return state_dict


@app.post("/api/catalog/refresh", response_model=CatalogState)
def refresh_catalog() -> CatalogState:
    return _catalog_action(get_service().refresh_active_catalog)


@app.post("/api/catalog/default", response_model=CatalogState)
def set_default_catalog() -> CatalogState:
    return _catalog_action(get_service().set_active_as_default)


# ---------------- Category Routes ----------------


@app.post("/api/catalog/categories", response_model=CatalogState, status_code=201)
def create_category(request: CategoryRequest) -> CatalogState:
    return _catalog_action(get_service().create_category, request.name)


@app.put("/api/catalog/categories", response_model=CatalogState)
def rename_category(request: RenameCategoryRequest) -> CatalogState:
    return _catalog_action(
        get_service().rename_category,
        request.old_name,
        request.new_name,
    )


@app.delete("/api/catalog/categories", response_model=CatalogState)
def delete_category(request: CategoryRequest) -> CatalogState:
    return _catalog_action(get_service().delete_category, request.name)


# ---------------- Connection Routes ----------------


@app.get("/api/catalog/connections")
@app.get("/api/catalog/sources")
def list_connections() -> list[dict[str, Any]]:
    return get_service().list_connections()


@app.post("/api/catalog/connections", response_model=CatalogState, status_code=201)
@app.post("/api/catalog/sources", response_model=CatalogState, status_code=201)
def create_connection(request: CreateConnectionRequest) -> CatalogState:
    cid = request.connection_id or request.source_id
    return _catalog_action(
        get_service().create_connection,
        request.name,
        request.connector,
        request.config,
        request.credentials,
        cid,
        request.description,
    )


@app.put("/api/catalog/connections/{connection_id}", response_model=CatalogState)
@app.put("/api/catalog/sources/{connection_id}", response_model=CatalogState)
def update_connection(connection_id: str, request: UpdateConnectionRequest) -> CatalogState:
    return _catalog_action(
        get_service().update_connection,
        connection_id,
        request.name,
        request.config,
        request.credentials,
        request.description,
    )


@app.delete("/api/catalog/connections/{connection_id}", response_model=CatalogState)
@app.delete("/api/catalog/sources/{connection_id}", response_model=CatalogState)
def delete_connection(connection_id: str) -> CatalogState:
    return _catalog_action(get_service().delete_connection, connection_id)


# ---------------- Table Routes ----------------


@app.post("/api/catalog/tables", response_model=CatalogState, status_code=201)
def create_table(request: CreateTableRequest) -> CatalogState:
    cid = request.connection_id or request.source_id
    return _catalog_action(
        get_service().create_table,
        request.name,
        request.namespace,
        request.connector,
        cid,
        cid,
        request.options,
        request.columns,
        request.description,
        request.tags,
        request.row_count,
    )


@app.get("/api/catalog/tables/{table_id:path}", response_model=DatasetMetadata)
def get_table(table_id: str) -> DatasetMetadata:
    return _catalog_action(get_service().get_table, table_id)


@app.put("/api/catalog/tables/{table_id:path}", response_model=CatalogState)
def update_table(table_id: str, request: UpdateTableRequest) -> CatalogState:
    return _catalog_action(
        get_service().update_table,
        table_id,
        request.name,
        request.namespace,
        request.options,
        request.columns,
        request.description,
        request.tags,
        request.row_count,
    )


@app.delete("/api/catalog/tables/{table_id:path}", response_model=CatalogState)
def delete_table(table_id: str) -> CatalogState:
    return _catalog_action(get_service().delete_table, table_id)


# ---------------- Connector Capability Routes ----------------


@app.get("/api/connectors")
def get_connectors() -> dict[str, list[dict[str, Any]]]:
    return list_connectors_grouped()


@app.post("/api/connectors/test", response_model=ConnectionTestResult)
def test_connector(request: ConnectorTestRequest) -> ConnectionTestResult:
    cid = request.connection_id or request.source_id
    cfg = dict(request.source_config or {})
    opts = dict(request.options or {})
    merged_cfg = {**cfg, **opts}
    return _catalog_action(
        get_service().test_connection,
        request.connector,
        cid,
        cid,
        merged_cfg,
        request.credentials,
    )


@app.post("/api/connectors/discover", response_model=list[DiscoveredObject])
def discover_objects(request: ConnectorDiscoverRequest) -> list[DiscoveredObject]:
    cid = request.connection_id or request.source_id
    return _catalog_action(
        get_service().discover_objects,
        request.connector,
        cid,
        cid,
        request.source_config,
        request.credentials,
        request.options,
    )


@app.post("/api/connectors/schema", response_model=SchemaResult)
def infer_schema(request: ConnectorSchemaRequest) -> SchemaResult:
    cid = request.connection_id or request.source_id
    opts = {**request.options, **request.table_options}
    return _catalog_action(
        get_service().infer_table_schema,
        request.connector,
        cid,
        cid,
        request.source_config,
        request.credentials,
        opts,
    )


@app.post("/api/connectors/preview", response_model=PreviewResult)
def preview_data(request: ConnectorPreviewRequest) -> PreviewResult:
    cid = request.connection_id or request.source_id
    opts = {**request.options, **request.table_options}
    return _catalog_action(
        get_service().preview_table_data,
        request.connector,
        cid,
        cid,
        request.source_config,
        request.credentials,
        opts,
        request.limit,
    )



# ---------------- Pipeline Integration ----------------

_pipeline_service: PipelineService | None = None


def get_pipeline_service() -> PipelineService:
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = PipelineService()
    return _pipeline_service


def set_pipeline_service(service: PipelineService | None) -> None:
    global _pipeline_service
    _pipeline_service = service


class CreateProjectRequest(BaseModel):
    name: str = Field(..., description="Project name")
    description: str | None = Field(None, description="Optional project description")


class UpdateProjectRequest(BaseModel):
    new_name: str | None = Field(None, description="New project name")
    description: str | None = Field(None, description="New project description")


class CreateCategoryRequest(BaseModel):
    name: str = Field(..., description="Category name")
    description: str | None = Field(None, description="Optional category description")


class UpdateCategoryRequest(BaseModel):
    new_name: str = Field(..., description="New category name")
    description: str | None = Field(None, description="New category description")


class SwitchPipelineFileRequest(BaseModel):
    path: str = Field(..., description="File path to the target pipeline YAML file")
    set_as_default: bool = Field(False, description="Whether to persist this as default")


class CreatePipelineFileRequest(BaseModel):
    path: str = Field(..., description="File path for the new pipeline YAML file")
    set_as_default: bool = Field(False, description="Whether to persist this as default")
    overwrite: bool = Field(False, description="Whether to overwrite if file exists")


class OpenPipelineFileRequest(BaseModel):
    path: str = Field(..., description="File path to existing pipeline YAML file")
    set_as_default: bool = Field(False, description="Whether to set as default")


class RemovePipelineFileRequest(BaseModel):
    path: str = Field(..., description="Path to pipeline YAML file to remove from explorer")


class SetDefaultPipelineFileRequest(BaseModel):
    path: str = Field(..., description="Path to pipeline YAML file to set as default")


@app.post("/api/pipelines/file/switch")
def switch_pipeline_file(req: SwitchPipelineFileRequest) -> dict[str, Any]:
    service = get_pipeline_service()
    try:
        new_path = service.switch_file(req.path, set_as_default=req.set_as_default)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to switch pipeline file: {exc}",
        ) from exc
    return {"active_path": str(new_path), "pipeline_files": service.get_full_tree()}


@app.post("/api/pipelines/file/create")
def create_pipeline_file(req: CreatePipelineFileRequest) -> dict[str, Any]:
    service = get_pipeline_service()
    try:
        new_path = service.create_pipeline_file(
            req.path,
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
            detail=f"Failed to create pipeline file: {exc}",
        ) from exc
    return {"active_path": str(new_path), "pipeline_files": service.get_full_tree()}


@app.post("/api/pipelines/file/open")
def open_pipeline_file(req: OpenPipelineFileRequest) -> dict[str, Any]:
    service = get_pipeline_service()
    try:
        service.switch_file(req.path, set_as_default=req.set_as_default)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to open pipeline file: {exc}",
        ) from exc
    return {"active_path": str(service.active_path), "pipeline_files": service.get_full_tree()}


@app.post("/api/pipelines/file/remove")
def remove_pipeline_file(req: RemovePipelineFileRequest) -> dict[str, Any]:
    service = get_pipeline_service()
    service.remove_pipeline_file(req.path)
    return {"active_path": str(service.active_path), "pipeline_files": service.get_full_tree()}


@app.post("/api/pipelines/file/set-default")
def set_default_pipeline_file(req: SetDefaultPipelineFileRequest) -> dict[str, Any]:
    from det.pipeline.config import set_default_pipeline_path

    try:
        set_default_pipeline_path(req.path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to set default pipeline file: {exc}",
        ) from exc
    service = get_pipeline_service()
    return {"active_path": str(service.active_path), "pipeline_files": service.get_full_tree()}


@app.get("/api/pipelines/tree")
def get_pipelines_tree(file_path: str | None = None) -> dict[str, Any]:
    service = get_pipeline_service()
    return service.get_tree(file_path=file_path)


@app.get("/api/pipelines/projects", response_model=list[Project])
def list_pipeline_projects(file_path: str | None = None) -> list[Project]:
    service = get_pipeline_service()
    return service.list_projects(file_path=file_path)


@app.post("/api/pipelines/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
def create_pipeline_project(req: CreateProjectRequest, file_path: str | None = None) -> Project:
    service = get_pipeline_service()
    try:
        return service.create_project(
            name=req.name, description=req.description, file_path=file_path
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.put("/api/pipelines/projects/{name}", response_model=Project)
def update_pipeline_project(
    name: str, req: UpdateProjectRequest, file_path: str | None = None
) -> Project:
    service = get_pipeline_service()
    try:
        return service.update_project(
            name=name, new_name=req.new_name, description=req.description, file_path=file_path
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.delete("/api/pipelines/projects/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline_project(name: str, file_path: str | None = None) -> None:
    service = get_pipeline_service()
    try:
        service.delete_project(name, file_path=file_path)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.get("/api/pipelines/projects/{project}/categories", response_model=list[PipelineCategory])
def list_pipeline_categories(project: str, file_path: str | None = None) -> list[PipelineCategory]:
    service = get_pipeline_service()
    try:
        return service.list_categories(project, file_path=file_path)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.post(
    "/api/pipelines/projects/{project}/categories",
    response_model=PipelineCategory,
    status_code=status.HTTP_201_CREATED,
)
def create_pipeline_category(
    project: str, req: CreateCategoryRequest, file_path: str | None = None
) -> PipelineCategory:
    service = get_pipeline_service()
    try:
        return service.create_category(
            project_name=project,
            category_name=req.name,
            description=req.description,
            file_path=file_path,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.put("/api/pipelines/projects/{project}/categories/{category}", response_model=PipelineCategory)
def update_pipeline_category(
    project: str, category: str, req: UpdateCategoryRequest, file_path: str | None = None
) -> PipelineCategory:
    service = get_pipeline_service()
    try:
        return service.update_category(
            project_name=project,
            category_name=category,
            new_name=req.new_name,
            description=req.description,
            file_path=file_path,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.delete(
    "/api/pipelines/projects/{project}/categories/{category}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_pipeline_category(project: str, category: str, file_path: str | None = None) -> None:
    service = get_pipeline_service()
    try:
        service.delete_category(project_name=project, category_name=category, file_path=file_path)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.get("/api/pipelines/yaml", response_class=PlainTextResponse)
def get_pipelines_yaml(path: str | None = None) -> PlainTextResponse:
    service = get_pipeline_service()
    return PlainTextResponse(service.export_yaml(file_path=path))


# --- Legacy Dataset & Namespace Endpoints for Compatibility ---


class CatalogStatusResponse(BaseModel):
    active_path: str
    default_path: str
    is_default: bool
    dataset_count: int


class ScanRequest(BaseModel):
    location: str
    format_hint: str | None = None


class SwitchCatalogRequest(BaseModel):
    path: str
    set_as_default: bool = False


class LegacyCreateCatalogRequest(BaseModel):
    path: str
    name: str = "det_catalog"
    set_as_default: bool = False
    overwrite: bool = False


class RemoveCatalogRequest(BaseModel):
    path: str


class SetDefaultCatalogRequest(BaseModel):
    path: str


class CreateNamespaceRequest(BaseModel):
    name: str
    catalog_path: str | None = None


class RenameNamespaceRequest(BaseModel):
    new_name: str
    catalog_path: str | None = None


@app.get("/api/catalog/status", response_model=CatalogStatusResponse)
def get_catalog_status() -> CatalogStatusResponse:
    service = get_service()
    active = str(service.active_path) if service.active_path else ""
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


@app.get("/api/tree")
def get_explorer_tree():
    service = get_service()
    return {"catalogs": service.get_full_tree()}


@app.post("/api/catalog/remove")
def remove_catalog_endpoint(req: RemoveCatalogRequest):
    service = get_service()
    service.remove_catalog(req.path)
    return {"catalogs": service.get_full_tree()}


@app.post("/api/catalog/set-default")
def set_default_catalog_endpoint(req: SetDefaultCatalogRequest):
    try:
        set_default_catalog_path(req.path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to set default catalog: {exc}",
        ) from exc
    service = get_service()
    return {"catalogs": service.get_full_tree()}


@app.get("/api/namespaces")
def list_namespaces(catalog_path: str | None = Query(None)):
    service = get_service()
    return service.list_namespaces(catalog_path=catalog_path)


@app.post("/api/namespaces", status_code=status.HTTP_201_CREATED)
def create_namespace(req: CreateNamespaceRequest):
    service = get_service()
    try:
        created = service.create_namespace(req.name, catalog_path=req.catalog_path)
        return {"name": created}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.put("/api/namespaces/{name}")
def rename_namespace(name: str, req: RenameNamespaceRequest):
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
    service = get_service()
    affected = service.delete_namespace(name, reassign_to=reassign_to, catalog_path=catalog_path)
    return {"name": name, "affected_datasets": affected}


@app.get("/api/datasets", response_model=list[DatasetMetadata])
def list_datasets(
    search: str | None = Query(None),
    namespace: str | None = Query(None),
    catalog_path: str | None = Query(None),
) -> list[DatasetMetadata]:
    service = get_service()
    return service.list_datasets(search=search, namespace=namespace, catalog_path=catalog_path)


@app.get("/api/datasets/{dataset_id:path}", response_model=DatasetMetadata)
def get_dataset(
    dataset_id: str,
    catalog_path: str | None = Query(None),
) -> DatasetMetadata:
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
    catalog_path: str | None = Query(None),
) -> DatasetMetadata:
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
    catalog_path: str | None = Query(None),
) -> DatasetMetadata:
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
    catalog_path: str | None = Query(None),
) -> None:
    service = get_service()
    if not service.delete_dataset(dataset_id, catalog_path=catalog_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )


@app.post("/api/datasets/{dataset_id:path}/rescan", response_model=DatasetMetadata)
def rescan_dataset(
    dataset_id: str,
    catalog_path: str | None = Query(None),
) -> DatasetMetadata:
    service = get_service()
    try:
        return service.rescan_dataset(dataset_id, catalog_path=catalog_path)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.post("/api/scan", response_model=ScanResult)
def scan_endpoint(req: ScanRequest) -> ScanResult:
    service = get_service()
    try:
        return service.scan_path(req.location, req.format_hint)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scan failed: {exc}",
        ) from exc
