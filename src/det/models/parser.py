"""SQL model parser extracting frontmatter configs, refs, and source dependencies."""

import ast
import logging
from pathlib import Path
import re
from typing import Any

from det.models.base import BaseModelParser
from det.models.definition import ModelConfig, ModelDefinition

logger = logging.getLogger(__name__)

CONFIG_REGEX = re.compile(r"\{\{\s*config\s*\((.*?)\)\s*\}\}", re.DOTALL | re.IGNORECASE)
DOCBLOCK_REGEX = re.compile(r"^\s*(?:/\*(.*?)\*/|\"\"\"(.*?)\"\"\"|'''(.*?)''')", re.DOTALL)
REF_REGEX = re.compile(
    r"\{\{\s*ref\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?\s*\)\s*\}\}",
    re.IGNORECASE,
)
SOURCE_REGEX = re.compile(
    r"\{\{\s*source\s*\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?\s*\)\s*\}\}",
    re.IGNORECASE,
)
THIS_REGEX = re.compile(r"\{\{\s*this\s*\}\}", re.IGNORECASE)
KWARG_REGEX = re.compile(
    r"(\w+)\s*=\s*(\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|\[[^\]]*\]|\{[^\}]*\}|'[^']*'|\"[^\"]*\"|[^,)]+)"
)


class ModelParser(BaseModelParser):
    """Parses SQL models, extracts configs, and resolves Jinja-like macros."""

    def parse_file(self, file_path: Path, project: str = "default") -> ModelDefinition:
        """Read and parse a SQL model file from disk."""
        model_name = file_path.stem
        raw_sql = file_path.read_text(encoding="utf-8")
        return self.parse_text(
            name=model_name,
            sql_text=raw_sql,
            project=project,
            file_path=file_path,
        )

    def parse_text(
        self,
        name: str,
        sql_text: str,
        project: str = "default",
        file_path: Path | None = None,
    ) -> ModelDefinition:
        """Parse raw SQL string into a structured ModelDefinition."""
        docblock_desc, sql_after_docblock = self._extract_docblock(sql_text)
        config, stripped_sql = self.parse_config(sql_after_docblock)
        description = config.description or docblock_desc

        refs = self.parse_refs(stripped_sql)
        sources = self.parse_sources(stripped_sql)
        compiled_sql = self.compile_sql(stripped_sql, name)

        return ModelDefinition(
            name=name,
            project=project,
            raw_sql=sql_text,
            compiled_sql=compiled_sql,
            config=config,
            description=description,
            refs=refs,
            sources=sources,
            file_path=file_path,
        )

    def _extract_docblock(self, sql_text: str) -> tuple[str, str]:
        """Extract multi-line header docblock (/* ... */ or triple quotes) if present."""
        match = DOCBLOCK_REGEX.match(sql_text)
        if not match:
            return "", sql_text

        doc_content = match.group(1) or match.group(2) or match.group(3) or ""
        remaining_sql = sql_text[match.end():].strip()
        return doc_content.strip(), remaining_sql
        sources = self.parse_sources(stripped_sql)
        compiled_sql = self.compile_sql(stripped_sql, name)

        return ModelDefinition(
            name=name,
            project=project,
            raw_sql=sql_text,
            compiled_sql=compiled_sql,
            config=config,
            refs=refs,
            sources=sources,
            file_path=file_path,
        )

    def parse_config(self, raw_sql: str) -> tuple[ModelConfig, str]:
        """Extract {{ config(...) }} block and return parsed config with remaining SQL."""
        match = CONFIG_REGEX.search(raw_sql)
        if not match:
            return ModelConfig(), raw_sql.strip()

        config_body = match.group(1).strip()
        config_dict = self._extract_kwargs(config_body)
        cleaned_sql = CONFIG_REGEX.sub("", raw_sql).strip()
        return ModelConfig.from_dict(config_dict), cleaned_sql

    def parse_refs(self, sql: str) -> list[str]:
        """Extract referenced model names from {{ ref('...') }} statements."""
        refs: list[str] = []
        for match in REF_REGEX.finditer(sql):
            first_arg = match.group(1)
            second_arg = match.group(2)
            # If two arguments e.g. ref('project', 'model'), second is model name
            model_ref = second_arg if second_arg else first_arg
            if model_ref not in refs:
                refs.append(model_ref)
        return refs

    def parse_sources(self, sql: str) -> list[str]:
        """Extract source connections from {{ source('...') }} statements."""
        sources: list[str] = []
        for match in SOURCE_REGEX.finditer(sql):
            source_name = match.group(1)
            if source_name not in sources:
                sources.append(source_name)
        return sources

    def compile_sql(self, sql: str, model_name: str) -> str:
        """Compile macros: replaces {{ this }} and {{ ref(...) }} with table identifiers."""
        # Replace {{ this }} with the model name
        compiled = THIS_REGEX.sub(model_name, sql)

        # Replace {{ ref('target') }} with target
        def _replace_ref(m: re.Match[str]) -> str:
            return m.group(2) if m.group(2) else m.group(1)

        compiled = REF_REGEX.sub(_replace_ref, compiled)

        # Replace {{ source('conn', 'tbl') }} with conn.tbl or conn
        def _replace_source(m: re.Match[str]) -> str:
            if m.group(2):
                return f"{m.group(1)}.{m.group(2)}"
            return m.group(1)

        compiled = SOURCE_REGEX.sub(_replace_source, compiled)
        return compiled.strip()

    def _extract_kwargs(self, config_body: str) -> dict[str, Any]:
        """Extract key-value pairs from comma-separated config parameters."""
        extracted: dict[str, Any] = {}
        for match in KWARG_REGEX.finditer(config_body):
            key = match.group(1).strip()
            val_raw = match.group(2).strip()
            extracted[key] = self._safe_eval_value(val_raw)
        return extracted

    def _safe_eval_value(self, raw_val: str) -> Any:
        """Safely evaluate Python literals or fallback to stripped strings."""
        try:
            return ast.literal_eval(raw_val)
        except Exception:
            return raw_val.strip("'\"")

