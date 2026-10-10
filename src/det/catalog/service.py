"""det.catalog.service - Command API and business service for catalog operations."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from det.catalog.config import get_default_catalog_path, set_default_catalog_path
from det.catalog.models import DatasetMetadata, ScanResult
from det.catalog.scanner import scan_location
from det.catalog.store import get_catalog_yaml_str, load_catalog, save_catalog


class CatalogService:
    """Core command API service for managing datasets in a YAML catalog."""

    def __init__(self, catalog_path: str | Path | None = None) -> None:
        self._path = Path(catalog_path).resolve() if catalog_path else get_default_catalog_path()

    @property
    def active_path(self) -> Path:
        """Return the path to the currently active catalog YAML file."""
        return self._path

    def switch_catalog(self, new_path: str | Path, set_as_default: bool = False) -> Path:
        """Switch the active catalog file, optionally saving it as the default."""
        self._path = Path(new_path).resolve()
        # Verify or initialize the file
        load_catalog(self._path)
        if set_as_default:
            set_default_catalog_path(self._path)
        return self._path

    def list_datasets(
        self, search: str | None = None, namespace: str | None = None
    ) -> list[DatasetMetadata]:
        """List all datasets in the active catalog, with optional search or namespace filter."""
        catalog = load_catalog(self._path)
        results = catalog.datasets

        if namespace:
            results = [d for d in results if d.namespace.lower() == namespace.lower()]

        if search:
            query = search.lower()
            results = [
                d
                for d in results
                if query in d.name.lower()
                or query in d.id.lower()
                or query in d.description.lower()
                or any(query in tag.lower() for tag in d.tags)
                or any(query in col.name.lower() for col in d.columns)
            ]

        return results

    def iter_datasets(self, namespace: str | None = None):
        """Yield registered datasets one by one from the active catalog.

        Args:
            namespace: Optional namespace filter.

        Yields:
            DatasetMetadata: Each matching dataset descriptor.
        """
        catalog = load_catalog(self._path)
        for d in catalog.datasets:
            if not namespace or d.namespace.lower() == namespace.lower():
                yield d

    def get_dataset(self, dataset_id: str) -> DatasetMetadata | None:
        """Retrieve a dataset by its unique ID."""
        catalog = load_catalog(self._path)
        for d in catalog.datasets:
            if d.id == dataset_id:
                return d
        return None

    def register_dataset(self, dataset: DatasetMetadata) -> DatasetMetadata:
        """Register a new dataset into the active catalog."""
        catalog = load_catalog(self._path)

        # Check for duplicate ID
        for existing in catalog.datasets:
            if existing.id == dataset.id:
                raise ValueError(f"Dataset with ID '{dataset.id}' already exists in catalog.")

        now_iso = datetime.now(UTC).isoformat()
        if not dataset.last_scanned:
            dataset.last_scanned = now_iso

        catalog.datasets.append(dataset)
        save_catalog(self._path, catalog)
        return dataset

    def update_dataset(self, dataset_id: str, updates: DatasetMetadata) -> DatasetMetadata:
        """Update an existing dataset's metadata and schema."""
        catalog = load_catalog(self._path)
        found_idx: int | None = None

        for idx, existing in enumerate(catalog.datasets):
            if existing.id == dataset_id:
                found_idx = idx
                break

        if found_idx is None:
            raise KeyError(f"Dataset '{dataset_id}' not found in catalog.")

        # If ID changed, ensure no collision with another dataset
        if updates.id != dataset_id:
            for existing in catalog.datasets:
                if existing.id == updates.id:
                    raise ValueError(f"Dataset with new ID '{updates.id}' already exists.")

        catalog.datasets[found_idx] = updates
        save_catalog(self._path, catalog)
        return updates

    def delete_dataset(self, dataset_id: str) -> bool:
        """Remove a dataset registration from the catalog (does not delete underlying data)."""
        catalog = load_catalog(self._path)
        initial_count = len(catalog.datasets)
        catalog.datasets = [d for d in catalog.datasets if d.id != dataset_id]

        if len(catalog.datasets) < initial_count:
            save_catalog(self._path, catalog)
            return True
        return False

    def scan_path(self, location: str | Path, format_hint: str | None = None) -> ScanResult:
        """Scan a file or folder path without saving to catalog yet."""
        return scan_location(location, format_hint)

    def rescan_dataset(self, dataset_id: str) -> DatasetMetadata:
        """Re-scan the underlying location for an existing dataset to refresh its schema."""
        dataset = self.get_dataset(dataset_id)
        if not dataset:
            raise KeyError(f"Dataset '{dataset_id}' not found in catalog.")

        scan = scan_location(dataset.location, dataset.format)
        dataset.columns = scan.columns
        if scan.row_count is not None:
            dataset.row_count = scan.row_count
        dataset.last_scanned = datetime.now(UTC).isoformat()

        return self.update_dataset(dataset_id, dataset)

    def list_namespaces(self) -> list[dict[str, Any]]:
        """List all namespaces / categories with their dataset counts."""
        catalog = load_catalog(self._path)
        # Collect unique namespaces preserving order
        ns_set = list(dict.fromkeys(catalog.namespaces + [d.namespace for d in catalog.datasets]))
        if "default" not in ns_set:
            ns_set.insert(0, "default")

        counts: dict[str, int] = {}
        for d in catalog.datasets:
            counts[d.namespace] = counts.get(d.namespace, 0) + 1

        return [{"name": ns, "count": counts.get(ns, 0)} for ns in ns_set]

    def create_namespace(self, name: str) -> str:
        """Create a new namespace / category in the catalog."""
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Namespace name cannot be empty.")

        catalog = load_catalog(self._path)
        if clean_name not in catalog.namespaces:
            catalog.namespaces.append(clean_name)
            save_catalog(self._path, catalog)
        return clean_name

    def rename_namespace(self, old_name: str, new_name: str) -> int:
        """Rename an existing namespace and update all its associated datasets."""
        clean_old = old_name.strip()
        clean_new = new_name.strip()
        if not clean_new:
            raise ValueError("New namespace name cannot be empty.")
        if clean_old == clean_new:
            return 0

        catalog = load_catalog(self._path)

        # Update in namespaces list
        if clean_old in catalog.namespaces:
            idx = catalog.namespaces.index(clean_old)
            catalog.namespaces[idx] = clean_new
        elif clean_new not in catalog.namespaces:
            catalog.namespaces.append(clean_new)

        # Update all datasets
        updated_count = 0
        for dataset in catalog.datasets:
            if dataset.namespace == clean_old:
                dataset.namespace = clean_new
                # If ID was prefixed with old namespace, update prefix
                if dataset.id.startswith(f"{clean_old}."):
                    dataset.id = f"{clean_new}.{dataset.name}"
                updated_count += 1

        save_catalog(self._path, catalog)
        return updated_count

    def delete_namespace(self, name: str, reassign_to: str | None = "default") -> int:
        """Delete a namespace, either reassigning its datasets or removing them."""
        clean_name = name.strip()
        catalog = load_catalog(self._path)

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
            # Delete datasets in this namespace
            initial_len = len(catalog.datasets)
            catalog.datasets = [d for d in catalog.datasets if d.namespace != clean_name]
            affected_count = initial_len - len(catalog.datasets)

        save_catalog(self._path, catalog)
        return affected_count

    def export_yaml(self) -> str:
        """Return raw YAML content of the catalog."""
        return get_catalog_yaml_str(self._path)
