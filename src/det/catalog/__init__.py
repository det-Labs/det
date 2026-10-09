import yaml
import os
from filelock import FileLock
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class DatasetDescriptor:
    name: str
    namespace: str
    location: str
    type: str
    schema_info: Optional[Dict[str, Any]] = None
    last_refresh: Optional[str] = None
    row_count: Optional[int] = None
    tags: Optional[List[str]] = None

    def to_dict(self):
        d = {
            "name": self.name,
            "namespace": self.namespace,
            "location": self.location,
            "type": self.type
        }
        if self.schema_info:
            d["schema"] = self.schema_info
        if self.last_refresh:
            d["last_refresh"] = self.last_refresh
        if self.row_count is not None:
            d["row_count"] = self.row_count
        if self.tags:
            d["tags"] = self.tags
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(
            name=data["name"],
            namespace=data.get("namespace", "default"),
            location=data["location"],
            type=data["type"],
            schema_info=data.get("schema"),
            last_refresh=data.get("last_refresh"),
            row_count=data.get("row_count"),
            tags=data.get("tags")
        )

class CatalogStore:
    def __init__(self, filepath: str = "catalog.yaml"):
        self.filepath = filepath
        if not os.path.exists(self.filepath):
            self._write_catalog({"datasets": []})

    def _read_catalog(self) -> Dict[str, Any]:
        if not os.path.exists(self.filepath):
            return {"datasets": []}

        with open(self.filepath, 'r') as f:
            try:
                # Basic read, lock can be used to prevent partial reads during writes
                # but for simplicity we rely on atomic renames for writes
                content = yaml.safe_load(f)
                return content or {"datasets": []}
            except yaml.YAMLError:
                return {"datasets": []}

    def _write_catalog(self, data: Dict[str, Any]) -> None:
        """Atomic write to prevent corruption during concurrent updates."""
        temp_file = f"{self.filepath}.tmp"
        with open(temp_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        # Atomic replace
        os.rename(temp_file, self.filepath)

    def register(self, dataset: DatasetDescriptor) -> None:
        """Register a new dataset or update an existing one without saving credentials."""
        # Note: Exclude any credential logic here; only metadata is processed

        # We need a cross-platform locking mechanism for concurrent processes. We use FileLock.
        lock_file = f"{self.filepath}.lock"
        with FileLock(lock_file):
            catalog = self._read_catalog()
            datasets = catalog.get("datasets", [])

            # Check for existing
            existing_idx = None
            for i, d in enumerate(datasets):
                if d.get("name") == dataset.name and d.get("namespace", "default") == dataset.namespace:
                    existing_idx = i
                    break

            if existing_idx is not None:
                datasets[existing_idx] = dataset.to_dict()
            else:
                datasets.append(dataset.to_dict())

            catalog["datasets"] = datasets
            self._write_catalog(catalog)

    def search(self, name: Optional[str] = None, namespace: Optional[str] = None,
               dataset_type: Optional[str] = None, tags: Optional[List[str]] = None) -> List[DatasetDescriptor]:
        """Search for datasets matching the criteria."""
        catalog = self._read_catalog()
        results = []
        for d in catalog.get("datasets", []):
            match = True
            if name and d.get("name") != name:
                match = False
            if namespace and d.get("namespace", "default") != namespace:
                match = False
            if dataset_type and d.get("type") != dataset_type:
                match = False
            if tags:
                d_tags = set(d.get("tags", []))
                if not set(tags).issubset(d_tags):
                    match = False
            if match:
                results.append(DatasetDescriptor.from_dict(d))
        return results

    def resolve(self, name: str, namespace: str = "default") -> Optional[DatasetDescriptor]:
        """Resolve a specific dataset by name and namespace."""
        results = self.search(name=name, namespace=namespace)
        return results[0] if results else None
