"""Tests for DocsGenerator emitting standalone HTML portals and manifest.json."""

from pathlib import Path
from det.docs.base import ColumnDoc, ModelDoc, ProjectDoc
from det.docs.generator import DocsGenerator


def _build_sample_project_doc() -> ProjectDoc:
    model_doc = ModelDoc(
        name="daily_sales",
        project="retail",
        description="Calculates daily revenue metrics.",
        materialization="table",
        destinations=["local", "prod_pg.public.sales"],
        tags=["core"],
        columns=[
            ColumnDoc(name="day", data_type="DATE", test_badges=["NOT_NULL"]),
            ColumnDoc(name="revenue", data_type="DOUBLE"),
        ],
        compiled_sql="SELECT day, revenue FROM sales_table",
        raw_sql="SELECT day, revenue FROM {{ ref('sales_table') }}",
    )
    return ProjectDoc(
        project_name="retail_analytics",
        version="1.2.0",
        description="Retail pipeline documentation",
        total_models=1,
        total_sources=2,
        total_tests=1,
        models=[model_doc],
        lineage_mermaid="flowchart LR\n    src --> daily_sales",
    )


def test_docs_generator_renders_html_and_writes_manifest(tmp_path: Path) -> None:
    """Verify DocsGenerator creates valid HTML and manifest.json for a project."""
    project_doc = _build_sample_project_doc()
    gen = DocsGenerator()
    html_output = gen.generate_html(project_doc)

    assert "<!DOCTYPE html>" in html_output
    assert "retail_analytics" in html_output
    assert "v1.2.0" in html_output
    assert "daily_sales" in html_output
    assert "Calculates daily revenue metrics." in html_output
    assert "NOT_NULL" in html_output

    output_dir = tmp_path / "projects" / "retail" / "docs"
    html_file = gen.write_docs(output_dir, project_doc)

    assert html_file.exists()
    assert (output_dir / "index.html").exists()
    assert (output_dir / "manifest.json").exists()

