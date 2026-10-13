"""det.validator - Pre-execution DataFusion logical plan analysis, schema derivation, and SQL error hinting."""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any

from det.catalog import CatalogStore
from det.connectors import scan_builtin
from det.engine import create_session_context, run_sql
from det.pipeline import Pipeline, PipelineStep


class PipelineValidator:
    """Pre-flight SQL plan validator and schema inferrer using Apache DataFusion lazy plans."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.catalog_store = CatalogStore(self.workspace)

    def validate_pipeline(
        self,
        pipeline_input: str | dict[str, Any] | Pipeline,
    ) -> dict[str, Any]:
        """Validate an entire multi-step pipeline before execution.

        Checks table names, column names, SQL syntax, type compatibility,
        and destination connections without executing or loading data rows.
        """
        if isinstance(pipeline_input, str):
            from det.pipeline import PipelineStore
            p_data = PipelineStore(self.workspace).get_pipeline(pipeline_input)
            pipeline = Pipeline.model_validate(p_data)
        elif isinstance(pipeline_input, dict):
            pipeline = Pipeline.model_validate(pipeline_input)
        else:
            pipeline = pipeline_input

        context = create_session_context()
        catalog_file = pipeline.catalog or "default.yaml"

        # Load catalog connections
        try:
            catalog_doc = self.catalog_store.select(catalog_file)["catalog"]
        except Exception as exc:
            return {
                "valid": False,
                "error": f"Failed to load catalog '{catalog_file}': {exc}",
                "hints": ["Ensure the catalog file exists in catalog/ and is valid YAML."],
                "steps": [],
            }

        all_connections: dict[str, dict[str, Any]] = {}
        available_tables: list[str] = []

        for folder in catalog_doc.get("folders", []):
            for conn in folder.get("connections", []):
                all_connections[conn["id"]] = conn
                all_connections[conn["name"]] = conn

                if conn.get("is_source"):
                    available_tables.append(conn["name"])
                    try:
                        df = scan_builtin(
                            context,
                            conn["connector"],
                            conn["options"],
                            self.workspace,
                            saved_columns=conn.get("columns") or None,
                        )
                        context.register_view(conn["name"], df)
                    except Exception as scan_err:
                        return {
                            "valid": False,
                            "error": f"Failed to register source connection '{conn['name']}': {scan_err}",
                            "hints": [f"Check connection options and file path for '{conn['name']}' in catalog."],
                            "steps": [],
                        }

        validated_steps: list[dict[str, Any]] = []
        registered_step_views: list[str] = []

        for step_idx, step in enumerate(pipeline.steps, start=1):
            step_result = self._validate_step(
                context,
                step,
                available_tables=available_tables + registered_step_views,
                all_connections=all_connections,
                catalog_file=catalog_file,
            )
            validated_steps.append(step_result)

            if not step_result["valid"]:
                return {
                    "valid": False,
                    "error": f"Step {step_idx} ('{step.name}') validation failed: {step_result['error']}",
                    "hints": step_result["hints"],
                    "failed_step": step.name,
                    "steps": validated_steps,
                    "available_tables": available_tables + registered_step_views,
                }

            # Register step view into context for subsequent step planning
            registered_step_views.append(step.name)

        return {
            "valid": True,
            "error": None,
            "hints": [],
            "steps": validated_steps,
            "available_tables": available_tables + registered_step_views,
        }

    def validate_step_sql(
        self,
        sql: str,
        *,
        catalog_file: str = "default.yaml",
        prior_steps: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Validate a single SQL query against catalog sources and prior step definitions."""
        context = create_session_context()
        try:
            catalog_doc = self.catalog_store.select(catalog_file)["catalog"]
        except Exception as exc:
            return {
                "valid": False,
                "error": f"Could not load catalog {catalog_file}: {exc}",
                "hints": [],
                "schema": [],
            }

        available_tables: list[str] = []
        all_connections: dict[str, dict[str, Any]] = {}

        for folder in catalog_doc.get("folders", []):
            for conn in folder.get("connections", []):
                all_connections[conn["id"]] = conn
                all_connections[conn["name"]] = conn
                if conn.get("is_source"):
                    available_tables.append(conn["name"])
                    try:
                        df = scan_builtin(
                            context,
                            conn["connector"],
                            conn["options"],
                            self.workspace,
                            saved_columns=conn.get("columns") or None,
                        )
                        context.register_view(conn["name"], df)
                    except Exception:
                        pass

        # Register prior steps if any
        if prior_steps:
            for prior in prior_steps:
                p_name = prior.get("name")
                p_sql = prior.get("sql")
                if p_name and p_sql:
                    try:
                        p_df = run_sql(context, p_sql)
                        context.register_view(p_name, p_df)
                        available_tables.append(p_name)
                    except Exception:
                        pass

        dummy_step = PipelineStep(name="preview_step", sql=sql)
        return self._validate_step(
            context,
            dummy_step,
            available_tables=available_tables,
            all_connections=all_connections,
            catalog_file=catalog_file,
        )

    def _validate_step(
        self,
        context: Any,
        step: PipelineStep,
        available_tables: list[str],
        all_connections: dict[str, dict[str, Any]],
        catalog_file: str,
    ) -> dict[str, Any]:
        """Dry-run plan validation for a single step."""
        try:
            # 1. Ask DataFusion to parse and build the logical plan
            df = context.sql(step.sql)

            # 2. Derive output schema directly from DataFusion's logical plan
            inferred_schema = [
                {
                    "name": field.name,
                    "data_type": str(field.type),
                    "nullable": field.nullable,
                }
                for field in df.schema()
            ]

            # 3. Register view so next steps in the loop can plan against it
            context.register_view(step.name, df)

            # 4. Validate destinations if specified
            dest_warnings: list[str] = []
            for dest_ref in step.destinations:
                conn = all_connections.get(dest_ref)
                if not conn:
                    raise ValueError(
                        f"Destination '{dest_ref}' was not found in catalog '{catalog_file}'."
                    )
                if not conn.get("is_destination"):
                    raise ValueError(
                        f"Connection '{conn['name']}' is marked as source-only. "
                        "Enable 'Destination' role in catalog before writing to it."
                    )

            return {
                "step_name": step.name,
                "valid": True,
                "schema": inferred_schema,
                "column_count": len(inferred_schema),
                "error": None,
                "hints": [],
                "warnings": dest_warnings,
            }

        except Exception as exc:
            hints = self._generate_error_hints(str(exc), available_tables)
            return {
                "step_name": step.name,
                "valid": False,
                "schema": [],
                "column_count": 0,
                "error": str(exc),
                "hints": hints,
                "warnings": [],
            }

    @staticmethod
    def _generate_error_hints(error_message: str, available_tables: list[str]) -> list[str]:
        """Generate human-friendly suggestions based on DataFusion error messages."""
        hints: list[str] = []

        # 1. Table not found error
        table_match = re.search(r"table '.*?\.([a-zA-Z0-9_]+)' not found", error_message, re.IGNORECASE) or \
                      re.search(r"table '([a-zA-Z0-9_]+)' not found", error_message, re.IGNORECASE)
        if table_match:
            missing_table = table_match.group(1)
            matches = difflib.get_close_matches(missing_table, available_tables, n=3, cutoff=0.4)
            if matches:
                hints.append(f"Did you mean table '{matches[0]}'? (Closest matches: {', '.join(matches)})")
            hints.append(f"Available tables in catalog and prior steps: {', '.join(available_tables)}")

        # 2. Column not found / Schema error
        direct_suggestion = re.search(r"Did you mean '(.*?)'\?", error_message)
        if direct_suggestion:
            hints.append(f"Did you mean column '{direct_suggestion.group(1)}'?")

        col_match = re.search(r"No field named ([a-zA-Z0-9_]+)", error_message)
        valid_fields_match = re.search(r"Valid fields are ([^\r\n]+)", error_message)
        if valid_fields_match:
            raw_fields = [f.strip().rstrip(".") for f in valid_fields_match.group(1).split(",")]
            clean_fields = []
            for rf in raw_fields:
                clean = rf.split(".")[-1].strip()
                if clean and clean not in clean_fields:
                    clean_fields.append(clean)
            if col_match and not direct_suggestion:
                missing_col = col_match.group(1)
                matches = difflib.get_close_matches(missing_col, clean_fields, n=3, cutoff=0.3)
                if matches:
                    hints.append(f"Did you mean column '{matches[0]}'? (Closest matches: {', '.join(matches)})")
            hints.append(f"Valid fields in referenced table: {', '.join(clean_fields)}")

        # 3. GROUP BY error
        if "must appear in the GROUP BY clause" in error_message:
            hints.append("Add the referenced non-aggregated columns to your GROUP BY clause, or wrap them in an aggregate function like SUM, AVG, or MAX.")

        # 4. Type coercion error
        if "Cannot coerce" in error_message or "type" in error_message.lower():
            hints.append("Check column data types. You can use CAST(column AS TYPE) to convert between numeric, string, or date types.")

        if not hints:
            hints.append("Check SQL syntax and verify that table and column names match catalog definitions.")

        return hints
