"""YAML Connector for structured YAML data files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl
from ruamel.yaml import YAML

from det.catalog.models import ColumnMetadata
from det.connectors.contract import (
    BaseConnector,
    ConfigField,
    ConnectionTestResult,
    ConnectorGroup,
    DiscoveredObject,
    PreviewResult,
    SchemaResult,
)
from det.connectors.errors import SchemaInferenceError


class YAMLConnector(BaseConnector):
    id = "yaml"
    name = "YAML"
    group = ConnectorGroup.FILES
    description = "YAML data files containing structured record lists."

    source_fields = [
        ConfigField(
            name="base_path",
            label="Base Directory",
            type="folder",
            placeholder="D:/Data",
            description="Root folder containing YAML files.",
        ),
    ]

    table_fields = [
        ConfigField(
            name="path",
            label="File Path",
            type="file",
            required=True,
            placeholder="data/configs.yaml",
            description="Path to .yaml or .yml file.",
        ),
        ConfigField(
            name="root_key",
            label="Root List Key (optional)",
            type="string",
            placeholder="items or records (leave blank if root is a list)",
            description="Key containing list of records if root is a mapping.",
            advanced=True,
        ),
    ]

    def _resolve_file(self, source_config: dict[str, Any], table_options: dict[str, Any]) -> Path:
        raw_path = str(table_options.get("path") or "").strip()
        base = str(source_config.get("base_path") or "").strip()
        target = Path(raw_path)
        if not target.is_absolute() and base:
            target = Path(base) / target
        return target.expanduser().resolve()

    def test_connection(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> ConnectionTestResult:
        base = str(source_config.get("base_path") or "").strip()
        if not base:
            return ConnectionTestResult(success=True, message="YAML connector ready.")
        target = Path(base).expanduser().resolve()
        if not target.exists():
            return ConnectionTestResult(success=False, message=f"Base path does not exist: {target}")
        return ConnectionTestResult(success=True, message=f"Base path is accessible: {target}")

    def discover_objects(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> list[DiscoveredObject]:
        base = str(source_config.get("base_path") or "").strip()
        if not base:
            return []
        target = Path(base).expanduser().resolve()
        if not target.is_dir():
            return []
        files = list(target.glob("*.yaml")) + list(target.glob("*.yml"))
        return [
            DiscoveredObject(id=f.name, name=f.name, type="file", path=str(f))
            for f in sorted(files)
        ]

    def _read_df(
        self,
        source_config: dict[str, Any],
        table_options: dict[str, Any],
        n_rows: int | None = None,
    ) -> pl.DataFrame:
        target = self._resolve_file(source_config, table_options)
        if not target.is_file():
            raise SchemaInferenceError(f"YAML file not found: {target}", connector_id=self.id)
        yaml = YAML(typ="safe")
        try:
            with target.open("r", encoding="utf-8") as stream:
                data = yaml.load(stream)
            root_key = table_options.get("root_key")
            if root_key and isinstance(data, dict):
                data = data.get(root_key, [])
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list):
                raise ValueError("YAML data must contain a list of records.")
            df = pl.DataFrame(data)
            if n_rows is not None:
                return df.head(n_rows)
            return df
        except Exception as exc:
            raise SchemaInferenceError(f"Failed to parse YAML file {target}: {exc}", connector_id=self.id) from exc

    def infer_schema(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
    ) -> SchemaResult:
        self.validate_table_options(table_options)
        df = self._read_df(source_config, table_options, n_rows=1000)
        columns = [
            ColumnMetadata(name=str(name), type=str(dtype), nullable=df[name].null_count() > 0)
            for name, dtype in zip(df.columns, df.dtypes)
        ]
        return SchemaResult(columns=columns, row_count_estimate=len(df), sample_size=len(df))

    def preview(
        self,
        source_config: dict[str, Any],
        credentials: dict[str, Any],
        table_options: dict[str, Any],
        limit: int = 50,
    ) -> PreviewResult:
        self.validate_table_options(table_options)
        df = self._read_df(source_config, table_options, n_rows=limit)
        rows: list[dict[str, Any]] = []
        for row_dict in df.to_dicts():
            rows.append({
                k: (str(v) if v is not None and not isinstance(v, (int, float, bool, str)) else v)
                for k, v in row_dict.items()
            })
        return PreviewResult(columns=df.columns, rows=rows, total_rows=len(rows))
