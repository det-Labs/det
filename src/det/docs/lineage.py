"""Generation of interactive Mermaid DAG lineage flowcharts."""

from det.docs.base import BaseLineageGenerator
from det.models.dag import ModelDAG


class LineageGenerator(BaseLineageGenerator):
    """Compiles pipeline dependency graph into clean, styled Mermaid flowchart markup."""

    def generate_mermaid(self, dag: ModelDAG) -> str:
        """Construct complete Mermaid flowchart LR diagram string from DAG."""
        lines: list[str] = ["flowchart LR"]
        sources = self._collect_external_sources(dag)

        # Style definitions
        lines.extend(self._build_style_definitions())

        # Render source nodes
        for src in sorted(sources):
            lines.append(f'    src_{self._sanitize_id(src)}[("{src}")]:::sourceNode')

        # Render model nodes & dependency edges
        for model_name in sorted(dag._models.keys()):
            model_id = f"mod_{self._sanitize_id(model_name)}"
            lines.append(f'    {model_id}["{model_name}"]:::modelNode')

            # Edges from providers
            for provider in sorted(dag._dependencies.get(model_name, set())):
                provider_id = (
                    f"mod_{self._sanitize_id(provider)}"
                    if provider in dag._models
                    else f"src_{self._sanitize_id(provider)}"
                )
                lines.append(f"    {provider_id} --> {model_id}")

        return "\n".join(lines)

    def _collect_external_sources(self, dag: ModelDAG) -> set[str]:
        """Identify all dependency identifiers that are not internal models."""
        sources: set[str] = set()
        for deps in dag._dependencies.values():
            for dep in deps:
                if dep not in dag._models:
                    sources.add(dep)
        return sources

    def _build_style_definitions(self) -> list[str]:
        """Return Mermaid classDef styling rules for sources and models."""
        return [
            "    classDef sourceNode fill:#059669,stroke:#047857,color:#ffffff,stroke-width:2px;",
            "    classDef modelNode fill:#2563eb,stroke:#1d4ed8,color:#ffffff,stroke-width:2px;",
        ]

    def _sanitize_id(self, identifier: str) -> str:
        """Sanitize node identifier replacing non-alphanumeric characters with underscores."""
        return "".join(c if c.isalnum() else "_" for c in identifier)

