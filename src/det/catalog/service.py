"""Single-active-catalog application service with source and table operations."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from det.catalog.config import (
    add_known_catalog,
    get_default_catalog_path,
    get_known_catalogs,
    remove_known_catalog,
    set_default_catalog_path,
)
from det.catalog.models import (
    CatalogFile,
    CatalogState,
    ColumnMetadata,
    DatasetMetadata,
    ScanResult,
)
from det.catalog.scanner import scan_location
from det.catalog.store import (
    create_catalog as create_catalog_file,
)
from det.catalog.store import (
    get_catalog_yaml_str,
    load_catalog,
    read_catalog_yaml,
    save_catalog,
)
from det.connectors.connections import (
    delete_connection,
    get_connection,
    get_connection_credentials,
    list_connections,
    load_all_connections,
    merge_incoming_credentials,
    save_connection,
)
from det.connectors.contract import (
    BaseConnector,
    ConnectionTestResult,
    DiscoveredObject,
    PreviewResult,
    SchemaResult,
)
from det.connectors.registry import get_connector


def slugify_id(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text.strip().lower()).strip("_")
    return cleaned or "conn"


class CatalogService:
    """Manage one open catalog at a time, including categories, connections, and tables."""

    def __init__(self, catalog_path: str | Path | None = None) -> None:
        if catalog_path is not None:
            target = Path(catalog_path).resolve()
            self._active_path = target
            if target.is_file():
                self._catalog = load_catalog(target)
            else:
                self._catalog = create_catalog_file(target, target.stem)
            add_known_catalog(target)
        else:
            default_path = get_default_catalog_path()
            self._active_path = None
            self._catalog = None
            if default_path is not None and default_path.is_file():
                self._catalog = load_catalog(default_path)
                self._active_path = default_path
                add_known_catalog(default_path)

    @property
    def active_path(self) -> Path | None:
        return self._active_path

    @property
    def catalog(self) -> CatalogFile | None:
        return self._catalog

    def state(self) -> CatalogState:
        default_path = get_default_catalog_path()
        conns = self.list_connections()
        return CatalogState(
            active_path=str(self._active_path) if self._active_path else None,
            default_path=str(default_path) if default_path else None,
            is_default=(
                self._active_path is not None
                and default_path is not None
                and self._active_path == default_path
            ),
            catalog_name=self._catalog.catalog_name if self._catalog else None,
            categories=self._catalog.category_tree() if self._catalog else [],
            connections=conns,
            sources=conns,
            dataset_count=len(self.list_datasets()) if self._catalog else 0,
        )


    def create_catalog(
        self,
        path: str | Path,
        name: str | None = None,
        make_default: bool = False,
        overwrite: bool = False,
    ) -> Path:
        target = self._validate_yaml_path(path)
        if not overwrite and target.exists():
            raise FileExistsError(f"Catalog file already exists: {target}")
        display_name = name.strip() if name and name.strip() else target.stem
        catalog = create_catalog_file(target, display_name, overwrite=overwrite)
        if make_default:
            set_default_catalog_path(target)
        self._active_path = target
        self._catalog = catalog
        add_known_catalog(target)
        return target

    def open_catalog(self, path: str | Path, make_default: bool = False) -> CatalogState:
        target = self._validate_yaml_path(path)
        catalog = load_catalog(target)
        if make_default:
            set_default_catalog_path(target)
        self._active_path = target
        self._catalog = catalog
        return self.state()

    def refresh_active_catalog(self) -> CatalogState:
        if self._active_path is None:
            raise ValueError("Open a catalog before refreshing it.")
        catalog = load_catalog(self._active_path)
        self._catalog = catalog
        return self.state()

    def set_active_as_default(self) -> CatalogState:
        if self._active_path is None:
            raise ValueError("Open a catalog before setting it as the default.")
        set_default_catalog_path(self._active_path)
        return self.state()

    def read_catalog_yaml(self) -> str:
        if self._active_path is None:
            raise ValueError("Open a catalog before viewing its YAML.")
        return read_catalog_yaml(self._active_path)

    # ---------------- Category Operations ----------------

    def create_category(self, name: str) -> CatalogState:
        catalog = self._require_catalog().model_copy(deep=True)
        clean_name = self._validate_category_name(name)
        if any(category.casefold() == clean_name.casefold() for category in catalog.namespaces):
            raise ValueError(f"Category '{clean_name}' already exists.")
        catalog.namespaces.append(clean_name)
        self._save_catalog(catalog)
        return self.state()

    def rename_category(self, old_name: str, new_name: str) -> CatalogState:
        catalog = self._require_catalog().model_copy(deep=True)
        old = old_name.strip()
        new = self._validate_category_name(new_name)
        if old == "default":
            raise ValueError("The default category cannot be renamed.")
        if old not in catalog.namespaces:
            raise KeyError(f"Category '{old}' does not exist.")
        if old == new:
            return self.state()
        if old != new and any(name.casefold() == new.casefold() for name in catalog.namespaces):
            raise ValueError(f"Category '{new}' already exists.")
        catalog.namespaces[catalog.namespaces.index(old)] = new
        for table in catalog.datasets:
            if table.namespace == old:
                table.namespace = new
                if table.id.startswith(f"{old}."):
                    table.id = f"{new}.{table.name}"
        self._save_catalog(catalog)
        return self.state()

    def delete_category(self, name: str) -> CatalogState:
        catalog = self._require_catalog().model_copy(deep=True)
        clean_name = name.strip()
        if clean_name == "default":
            raise ValueError("The default category cannot be deleted.")
        if clean_name not in catalog.namespaces:
            raise KeyError(f"Category '{clean_name}' does not exist.")
        if any(table.namespace == clean_name for table in catalog.datasets):
            raise ValueError("Category contains tables; move or remove its tables before deleting it.")
        catalog.namespaces.remove(clean_name)
        self._save_catalog(catalog)
        return self.state()

    # ---------------- Reusable Connections (connections.yaml) ----------------

    def list_connections(self) -> list[dict[str, Any]]:
        return list_connections(mask_secrets=True)

    def get_connection(self, connection_id: str) -> dict[str, Any]:
        conn = get_connection(connection_id)
        if conn is None:
            raise KeyError(f"Connection '{connection_id}' does not exist.")
        return conn

    def create_connection(
        self,
        name: str,
        connector: str,
        config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        connection_id: str | None = None,
        description: str = "",
    ) -> CatalogState:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Connection name cannot be empty.")

        conn_instance = get_connector(connector)
        raw_id = connection_id.strip() if connection_id and connection_id.strip() else slugify_id(clean_name)
        cid = raw_id
        all_conns = load_all_connections()
        counter = 1
        while cid in all_conns:
            cid = f"{raw_id}_{counter}"
            counter += 1

        cfg = dict(config or {})
        creds = dict(credentials or {})
        secret_keys = conn_instance.get_secret_field_names(scope="all")

        cleaned_config = {k: v for k, v in cfg.items() if k not in secret_keys and v is not None}
        extracted_creds = {k: v for k, v in cfg.items() if k in secret_keys and v is not None}
        creds.update(extracted_creds)

        save_connection(
            connection_id=cid,
            name=clean_name,
            connector=conn_instance.id,
            config=cleaned_config,
            credentials=creds,
            description=description.strip(),
        )
        return self.state()

    def update_connection(
        self,
        connection_id: str,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> CatalogState:
        conn = self.get_connection(connection_id)
        conn_instance = get_connector(conn["connector"])
        secret_keys = conn_instance.get_secret_field_names(scope="all")

        new_name = name.strip() if name is not None else conn["name"]
        if not new_name:
            raise ValueError("Connection name cannot be empty.")
        new_desc = description.strip() if description is not None else conn.get("description", "")

        new_cfg = dict(conn.get("config") or {})
        if config is not None:
            new_cfg = {k: v for k, v in config.items() if k not in secret_keys and v is not None}
            incoming_secrets = {k: v for k, v in config.items() if k in secret_keys and v is not None}
            if incoming_secrets:
                if credentials is None:
                    credentials = {}
                credentials.update(incoming_secrets)

        new_creds = dict(conn.get("credentials") or {})
        if credentials is not None:
            new_creds = merge_incoming_credentials(connection_id, credentials, secret_keys)

        save_connection(
            connection_id=connection_id,
            name=new_name,
            connector=conn["connector"],
            config=new_cfg,
            credentials=new_creds,
            description=new_desc,
        )
        return self.state()

    def delete_connection(self, connection_id: str) -> CatalogState:
        self.get_connection(connection_id)
        if self._catalog:
            tables_using = [
                t.name for t in self._catalog.datasets
                if t.connection_id == connection_id or t.source_id == connection_id
            ]
            if tables_using:
                raise ValueError(
                    f"Connection '{connection_id}' cannot be deleted because it is used by tables: {', '.join(tables_using)}."
                )
        delete_connection(connection_id)
        return self.state()

    # Backwards compatibility aliases
    list_sources = list_connections
    get_source = get_connection
    create_source = create_connection
    update_source = update_connection
    delete_source = delete_connection

    # ---------------- Table CRUD Operations ----------------

    def create_table(
        self,
        name: str,
        namespace: str,
        connector: str,
        connection_id: str | None = None,
        source_id: str | None = None,
        options: dict[str, Any] | None = None,
        columns: list[ColumnMetadata] | None = None,
        description: str = "",
        tags: list[str] | None = None,
        row_count: int | None = None,
    ) -> CatalogState:
        catalog = self._require_catalog().model_copy(deep=True)
        clean_name = self._validate_table_name(name)
        clean_namespace = namespace.strip() or "default"

        if clean_namespace not in catalog.namespaces:
            raise ValueError(f"Category '{clean_namespace}' does not exist.")

        for table in catalog.datasets:
            if table.namespace == clean_namespace and table.name.casefold() == clean_name.casefold():
                raise ValueError(
                    f"Table '{clean_name}' already exists in category '{clean_namespace}'."
                )

        effective_cid = connection_id or source_id
        if effective_cid:
            # Verify connection exists
            self.get_connection(effective_cid)

        conn_instance = get_connector(connector)
        opts = options or {}
        location = str(opts.get("path") or opts.get("table_name") or "")

        table_id = f"{clean_namespace}.{clean_name}"
        dataset = DatasetMetadata(
            id=table_id,
            name=clean_name,
            namespace=clean_namespace,
            format=conn_instance.id,
            connector=conn_instance.id,
            connection_id=effective_cid,
            source_id=effective_cid,
            options=opts,
            location=location,
            description=description.strip(),
            columns=columns or [],
            tags=tags or [],
            row_count=row_count,
        )
        catalog.datasets.append(dataset)
        self._save_catalog(catalog)
        return self.state()

        return self.state()

    def update_table(
        self,
        table_id: str,
        name: str | None = None,
        namespace: str | None = None,
        options: dict[str, Any] | None = None,
        columns: list[ColumnMetadata] | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        row_count: int | None = None,
    ) -> CatalogState:
        catalog = self._require_catalog().model_copy(deep=True)
        table = None
        for t in catalog.datasets:
            if t.id == table_id:
                table = t
                break
        if table is None:
            raise KeyError(f"Table '{table_id}' does not exist.")

        new_namespace = namespace.strip() if namespace else table.namespace
        new_name = self._validate_table_name(name) if name else table.name

        if new_namespace not in catalog.namespaces:
            raise ValueError(f"Category '{new_namespace}' does not exist.")

        # If changing name or namespace, ensure uniqueness
        if new_name != table.name or new_namespace != table.namespace:
            for t in catalog.datasets:
                if t.id != table_id and t.namespace == new_namespace and t.name.casefold() == new_name.casefold():
                    raise ValueError(
                        f"Table '{new_name}' already exists in category '{new_namespace}'."
                    )

        table.name = new_name
        table.namespace = new_namespace
        table.id = f"{new_namespace}.{new_name}"

        if options is not None:
            table.options = options
            loc = str(options.get("path") or options.get("table_name") or "")
            if loc:
                table.location = loc

        if columns is not None:
            table.columns = columns

        if description is not None:
            table.description = description.strip()

        if tags is not None:
            table.tags = tags

        if row_count is not None:
            table.row_count = row_count

        self._save_catalog(catalog)
        return self.state()

    def delete_table(self, table_id: str) -> CatalogState:
        catalog = self._require_catalog().model_copy(deep=True)
        table = None
        for t in catalog.datasets:
            if t.id == table_id:
                table = t
                break
        if table is None:
            raise KeyError(f"Table '{table_id}' does not exist.")

        catalog.datasets.remove(table)
        self._save_catalog(catalog)
        return self.state()

    def get_table(self, table_id: str) -> DatasetMetadata:
        catalog = self._require_catalog()
        for t in catalog.datasets:
            if t.id == table_id:
                return t
        raise KeyError(f"Table '{table_id}' does not exist.")

    # ---------------- Connector Discovery & Preview ----------------

    def _resolve_connection_params(
        self,
        connector_id: str,
        connection_id: str | None = None,
        source_id: str | None = None,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
    ) -> tuple[BaseConnector, dict[str, Any], dict[str, Any]]:
        conn = get_connector(connector_id)
        resolved_cfg: dict[str, Any] = {}
        resolved_creds: dict[str, Any] = {}

        cid = connection_id or source_id
        if cid:
            conn_data = self.get_connection(cid)
            resolved_cfg.update(conn_data.get("config") or {})
            resolved_creds.update(get_connection_credentials(cid))

        if source_config:
            resolved_cfg.update(source_config)
        if credentials:
            resolved_creds.update(credentials)

        return conn, resolved_cfg, resolved_creds

    def test_connection(
        self,
        connector_id: str,
        connection_id: str | None = None,
        source_id: str | None = None,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
    ) -> ConnectionTestResult:
        conn, cfg, creds = self._resolve_connection_params(
            connector_id, connection_id, source_id, source_config, credentials
        )
        return conn.test_connection(cfg, creds)

    test_source_connection = test_connection

    def discover_objects(
        self,
        connector_id: str,
        connection_id: str | None = None,
        source_id: str | None = None,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> list[DiscoveredObject]:
        conn, cfg, creds = self._resolve_connection_params(
            connector_id, connection_id, source_id, source_config, credentials
        )
        return conn.discover_objects(cfg, creds, options)

    def infer_table_schema(
        self,
        connector_id: str,
        connection_id: str | None = None,
        source_id: str | None = None,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
    ) -> SchemaResult:
        conn, cfg, creds = self._resolve_connection_params(
            connector_id, connection_id, source_id, source_config, credentials
        )
        return conn.infer_schema(cfg, creds, table_options or {})

    def preview_table_data(
        self,
        connector_id: str,
        connection_id: str | None = None,
        source_id: str | None = None,
        source_config: dict[str, Any] | None = None,
        credentials: dict[str, Any] | None = None,
        table_options: dict[str, Any] | None = None,
        limit: int = 50,
    ) -> PreviewResult:
        conn, cfg, creds = self._resolve_connection_params(
            connector_id, connection_id, source_id, source_config, credentials
        )
        return conn.preview(cfg, creds, table_options or {}, limit=limit)


    # ---------------- Internal Helpers ----------------

    @staticmethod
    def _validate_yaml_path(path: str | Path) -> Path:
        target = Path(path).expanduser().resolve()
        if target.suffix.lower() not in {".yaml", ".yml"}:
            raise ValueError("Catalog file must use a .yaml or .yml extension.")
        return target

    @staticmethod
    def _validate_category_name(name: str) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Category name cannot be empty.")
        if "/" in clean_name or "\\" in clean_name:
            raise ValueError("Category names cannot contain path separators.")
        return clean_name

    @staticmethod
    def _validate_table_name(name: str) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Table name cannot be empty.")
        if "/" in clean_name or "\\" in clean_name:
            raise ValueError("Table names cannot contain path separators.")
        return clean_name

    def _require_catalog(self) -> CatalogFile:
        if self._catalog is None or self._active_path is None:
            raise ValueError("Create or open a catalog before managing items.")
        return self._catalog

    def _save_catalog(self, catalog: CatalogFile) -> None:
        if self._active_path is None:
            raise ValueError("No catalog is open.")
        save_catalog(self._active_path, catalog)
        self._catalog = catalog


    def switch_catalog(self, new_path: str | Path, set_as_default: bool = False) -> Path:
        self._active_path = Path(new_path).resolve()
        if self._active_path.is_file():
            self._catalog = load_catalog(self._active_path)
        else:
            self._catalog = create_catalog_file(self._active_path, self._active_path.stem)
        add_known_catalog(self._active_path)
        if set_as_default:
            set_default_catalog_path(self._active_path)
        return self._active_path

    def remove_catalog(self, catalog_path: str | Path) -> bool:
        path = Path(catalog_path).resolve()
        removed = remove_known_catalog(path)
        if path == self._active_path:
            self._active_path = get_default_catalog_path()
            if self._active_path and self._active_path.is_file():
                self._catalog = load_catalog(self._active_path)
            else:
                self._catalog = None
        return removed

    def get_full_tree(self) -> list[dict[str, Any]]:
        known_paths = get_known_catalogs()
        default_path = get_default_catalog_path()
        tree: list[dict[str, Any]] = []

        for path in known_paths:
            try:
                cat = load_catalog(path)
                cat_dict = {
                    "path": str(path),
                    "name": cat.catalog_name,
                    "is_active": (path == self._active_path),
                    "is_default": (path == default_path),
                    "namespaces": [],
                }
                ns_set = list(dict.fromkeys(cat.namespaces + [d.namespace for d in cat.datasets]))
                if "default" not in ns_set:
                    ns_set.insert(0, "default")

                for ns in ns_set:
                    ns_dict = {
                        "name": ns,
                        "datasets": [
                            {"id": d.id, "name": d.name, "format": d.format}
                            for d in cat.datasets
                            if d.namespace == ns
                        ],
                    }
                    cat_dict["namespaces"].append(ns_dict)
                tree.append(cat_dict)
            except Exception:
                pass
        return tree

    def list_datasets(
        self,
        namespace: str | None = None,
        search: str | None = None,
        tag: str | None = None,
        catalog_path: str | Path | None = None,
    ) -> list[DatasetMetadata]:
        target_path = Path(catalog_path).resolve() if catalog_path else self._active_path
        if not target_path or not target_path.is_file():
            return []
        catalog = load_catalog(target_path)
        results: list[DatasetMetadata] = []
        q = search.lower().strip() if search else None

        for d in catalog.datasets:
            if namespace and d.namespace != namespace:
                continue
            if tag and tag not in d.tags:
                continue
            if q:
                match = (
                    q in d.name.lower()
                    or q in d.id.lower()
                    or q in d.description.lower()
                    or any(q in col.name.lower() for col in d.columns)
                )
                if not match:
                    continue
            results.append(d)
        return results

    def get_dataset(
        self, dataset_id: str, catalog_path: str | Path | None = None
    ) -> DatasetMetadata | None:
        target_path = Path(catalog_path).resolve() if catalog_path else self._active_path
        if not target_path or not target_path.is_file():
            return None
        catalog = load_catalog(target_path)
        for d in catalog.datasets:
            if d.id == dataset_id:
                return d
        return None

    def register_dataset(
        self, dataset: DatasetMetadata, catalog_path: str | Path | None = None
    ) -> DatasetMetadata:
        target_path = Path(catalog_path).resolve() if catalog_path else self._active_path
        if not target_path:
            raise ValueError("No active catalog.")
        catalog = load_catalog(target_path)
        for existing in catalog.datasets:
            if existing.id == dataset.id:
                raise ValueError(f"Dataset with ID '{dataset.id}' already exists in catalog.")
        now_iso = datetime.now(UTC).isoformat()
        if not dataset.last_scanned:
            dataset.last_scanned = now_iso
        catalog.datasets.append(dataset)
        save_catalog(target_path, catalog)
        self._catalog = catalog
        return dataset

    def update_dataset(
        self,
        dataset_id: str,
        updates: DatasetMetadata,
        catalog_path: str | Path | None = None,
    ) -> DatasetMetadata:
        target_path = Path(catalog_path).resolve() if catalog_path else self._active_path
        if not target_path:
            raise ValueError("No active catalog.")
        catalog = load_catalog(target_path)
        found_idx = None
        for idx, existing in enumerate(catalog.datasets):
            if existing.id == dataset_id:
                found_idx = idx
                break
        if found_idx is None:
            raise KeyError(f"Dataset '{dataset_id}' not found in catalog.")
        if updates.id != dataset_id:
            for existing in catalog.datasets:
                if existing.id == updates.id:
                    raise ValueError(f"Dataset with new ID '{updates.id}' already exists.")
        catalog.datasets[found_idx] = updates
        save_catalog(target_path, catalog)
        self._catalog = catalog
        return updates

    def delete_dataset(
        self, dataset_id: str, catalog_path: str | Path | None = None
    ) -> bool:
        target_path = Path(catalog_path).resolve() if catalog_path else self._active_path
        if not target_path:
            return False
        catalog = load_catalog(target_path)
        init_len = len(catalog.datasets)
        catalog.datasets = [d for d in catalog.datasets if d.id != dataset_id]
        if len(catalog.datasets) < init_len:
            save_catalog(target_path, catalog)
            self._catalog = catalog
            return True
        return False

    def scan_path(self, location: str | Path, format_hint: str | None = None) -> ScanResult:
        return scan_location(location, format_hint)

    def rescan_dataset(
        self, dataset_id: str, catalog_path: str | Path | None = None
    ) -> DatasetMetadata:
        target_path = Path(catalog_path).resolve() if catalog_path else self._active_path
        dataset = self.get_dataset(dataset_id, catalog_path=target_path)
        if not dataset:
            raise KeyError(f"Dataset '{dataset_id}' not found in catalog.")
        scan = scan_location(dataset.location, dataset.format)
        dataset.columns = scan.columns
        if scan.row_count is not None:
            dataset.row_count = scan.row_count
        dataset.last_scanned = datetime.now(UTC).isoformat()
        return self.update_dataset(dataset_id, dataset, catalog_path=target_path)

    def list_namespaces(
        self, catalog_path: str | Path | None = None
    ) -> list[dict[str, Any]]:
        target_path = Path(catalog_path).resolve() if catalog_path else self._active_path
        if not target_path or not target_path.is_file():
            return []
        catalog = load_catalog(target_path)
        ns_set = list(dict.fromkeys(catalog.namespaces + [d.namespace for d in catalog.datasets]))
        if "default" not in ns_set:
            ns_set.insert(0, "default")
        counts: dict[str, int] = {}
        for d in catalog.datasets:
            counts[d.namespace] = counts.get(d.namespace, 0) + 1
        return [{"name": ns, "count": counts.get(ns, 0)} for ns in ns_set]

    def create_namespace(self, name: str, catalog_path: str | Path | None = None) -> str:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Namespace name cannot be empty.")
        target_path = Path(catalog_path).resolve() if catalog_path else self._active_path
        if not target_path:
            raise ValueError("No active catalog.")
        catalog = load_catalog(target_path)
        if clean_name not in catalog.namespaces:
            catalog.namespaces.append(clean_name)
            save_catalog(target_path, catalog)
            self._catalog = catalog
        return clean_name

    def rename_namespace(
        self, old_name: str, new_name: str, catalog_path: str | Path | None = None
    ) -> int:
        clean_old = old_name.strip()
        clean_new = new_name.strip()
        if not clean_new:
            raise ValueError("New namespace name cannot be empty.")
        if clean_old == clean_new:
            return 0
        target_path = Path(catalog_path).resolve() if catalog_path else self._active_path
        if not target_path:
            raise ValueError("No active catalog.")
        catalog = load_catalog(target_path)
        if clean_old in catalog.namespaces:
            idx = catalog.namespaces.index(clean_old)
            catalog.namespaces[idx] = clean_new
        elif clean_new not in catalog.namespaces:
            catalog.namespaces.append(clean_new)
        updated_count = 0
        for d in catalog.datasets:
            if d.namespace == clean_old:
                d.namespace = clean_new
                if d.id.startswith(f"{clean_old}."):
                    d.id = f"{clean_new}.{d.name}"
                updated_count += 1
        save_catalog(target_path, catalog)
        self._catalog = catalog
        return updated_count

    def delete_namespace(
        self, name: str, reassign_to: str | None = "default", catalog_path: str | Path | None = None
    ) -> int:
        clean_name = name.strip()
        target_path = Path(catalog_path).resolve() if catalog_path else self._active_path
        if not target_path:
            return 0
        catalog = load_catalog(target_path)
        if clean_name in catalog.namespaces:
            catalog.namespaces.remove(clean_name)
        affected_count = 0
        if reassign_to:
            target_ns = reassign_to.strip()
            if target_ns not in catalog.namespaces:
                catalog.namespaces.append(target_ns)
            for d in catalog.datasets:
                if d.namespace == clean_name:
                    d.namespace = target_ns
                    if d.id.startswith(f"{clean_name}."):
                        d.id = f"{target_ns}.{d.name}"
                    affected_count += 1
        else:
            init_len = len(catalog.datasets)
            catalog.datasets = [d for d in catalog.datasets if d.namespace != clean_name]
            affected_count = init_len - len(catalog.datasets)
        save_catalog(target_path, catalog)
        self._catalog = catalog
        return affected_count

    def export_yaml(self, catalog_path: str | Path | None = None) -> str:
        target_path = Path(catalog_path).resolve() if catalog_path else self._active_path
        if not target_path or not target_path.is_file():
            return ""
        return get_catalog_yaml_str(target_path)


