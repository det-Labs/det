"""det.sample_data - Package containing sample warehouse source data, catalog, and pipelines."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from det.workspace import validate_workspace


SAMPLE_DATA_ROOT = Path(__file__).parent.resolve()


def install_sample_data(
    workspace: str | Path,
    *,
    select_catalog: bool = True,
    overwrite_existing: bool = True,
) -> dict[str, Any]:
    """Recreate sample warehouse source data, catalog, and pipelines in the specified workspace."""
    target_workspace = validate_workspace(workspace)

    # 1. Recreate source_data/
    source_data_src = SAMPLE_DATA_ROOT / "source_data"
    source_data_dst = target_workspace / "source_data"
    source_data_dst.mkdir(parents=True, exist_ok=True)
    if source_data_src.is_dir():
        for item in source_data_src.iterdir():
            target_item = source_data_dst / item.name
            if item.is_dir():
                if target_item.exists() and overwrite_existing:
                    shutil.rmtree(target_item)
                if not target_item.exists():
                    shutil.copytree(item, target_item)
            else:
                if not target_item.exists() or overwrite_existing:
                    shutil.copy2(item, target_item)

    # 2. Recreate catalog/sample_warehouse.yaml
    catalog_src = SAMPLE_DATA_ROOT / "catalog" / "sample_warehouse.yaml"
    catalog_dst = target_workspace / "catalog" / "sample_warehouse.yaml"
    catalog_dst.parent.mkdir(parents=True, exist_ok=True)
    if catalog_src.is_file():
        shutil.copy2(catalog_src, catalog_dst)

    # 3. Recreate pipelines/Sample_Warehouse_Pipelines/
    pipelines_src = SAMPLE_DATA_ROOT / "pipelines" / "Sample_Warehouse_Pipelines"
    pipelines_dst = target_workspace / "pipelines" / "Sample_Warehouse_Pipelines"
    pipelines_dst.mkdir(parents=True, exist_ok=True)
    if pipelines_src.is_dir():
        for pipe_file in pipelines_src.glob("*.yaml"):
            target_pipe = pipelines_dst / pipe_file.name
            shutil.copy2(pipe_file, target_pipe)

    # 4. Optional: Select catalog in workspace
    active_catalog = "sample_warehouse.yaml"
    if select_catalog:
        try:
            from det.catalog import CatalogStore

            c_store = CatalogStore(target_workspace)
            c_store.select("sample_warehouse.yaml")
        except Exception:
            pass

    pipeline_count = len(list(pipelines_dst.glob("*.yaml")))
    return {
        "status": "SUCCESS",
        "workspace": str(target_workspace),
        "catalog": "sample_warehouse.yaml",
        "active_catalog": active_catalog,
        "pipelines_folder": "Sample_Warehouse_Pipelines",
        "pipeline_count": pipeline_count,
        "source_data_folder": "source_data",
        "message": "Sample warehouse datasets, catalog, and pipelines installed successfully.",
    }

