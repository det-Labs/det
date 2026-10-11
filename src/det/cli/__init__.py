"""det.cli - Command-line interface for the det data engineering framework by det Labs."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from det import __version__
from det.catalog import CatalogService, get_default_catalog_path, set_default_catalog_path
from det.pipeline import (
    PipelineService,
    get_default_pipeline_path,
    set_default_pipeline_path,
)

app = typer.Typer(
    name="det",
    help="det - Modular Data Engineering Framework by det Labs",
    add_completion=False,
)

catalog_app = typer.Typer(
    name="catalog",
    help="Catalog management commands (list, scan, gui, set-default)",
)
app.add_typer(catalog_app, name="catalog")

pipeline_app = typer.Typer(
    name="pipeline",
    help="Data Engineering & ETL pipeline management (Projects, Categories, Pipelines)",
)
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(pipeline_app, name="etl")

pipeline_file_app = typer.Typer(
    name="file",
    help="Manage pipeline YAML files (list, create, open, remove, set-default)",
)
pipeline_app.add_typer(pipeline_file_app, name="file")

project_app = typer.Typer(
    name="project",
    help="Manage data engineering projects (list, create, edit, delete)",
)
pipeline_app.add_typer(project_app, name="project")

category_app = typer.Typer(
    name="category",
    help="Manage pipeline categories within a project (list, create, edit, delete)",
)
pipeline_app.add_typer(category_app, name="category")


@app.command()
def version() -> None:
    """Print the installed det framework version."""
    typer.echo(f"det version {__version__} (det Labs)")


@app.command()
def info() -> None:
    """Display environment details, active Python runtime, and engine status."""
    typer.echo(f"det Framework: {__version__} by det Labs")
    typer.echo(f"Python Version: {sys.version.split()[0]}")
    typer.echo(f"Default Catalog: {get_default_catalog_path()}")
    typer.echo(f"Default Pipeline Store: {get_default_pipeline_path()}")
    typer.echo("Engines: Polars, PyArrow, DuckDB (planned)")


@app.command("gui")
def gui_shortcut(
    file: Annotated[
        Path | None, typer.Option("--file", "-f", help="Catalog YAML file to open")
    ] = None,
    port: Annotated[int, typer.Option("--port", "-p", help="Port to run the web server on")] = 8501,
    no_browser: Annotated[
        bool, typer.Option("--no-browser", help="Do not automatically open browser")
    ] = False,
) -> None:
    """Launch the interactive det Catalog Explorer in the local browser."""
    from det.gui import launch_gui

    launch_gui(catalog_path=file, port=port, open_browser=not no_browser)


@catalog_app.command("list")
def catalog_list(
    file: Annotated[
        Path | None, typer.Option("--file", "-f", help="Catalog YAML file to query")
    ] = None,
    search: Annotated[
        str | None, typer.Option("--search", "-s", help="Filter by name, tag, or column")
    ] = None,
) -> None:
    """List datasets registered in the catalog."""
    service = CatalogService(file)
    datasets = service.list_datasets(search=search)
    typer.echo(f"Catalog: {service.active_path} ({len(datasets)} datasets)")
    for d in datasets:
        cols_count = len(d.columns)
        rows_str = f", {d.row_count:,} rows" if d.row_count is not None else ""
        typer.echo(f" • [{d.format.upper()}] {d.id} ({cols_count} cols{rows_str}) - {d.location}")


@catalog_app.command("scan")
def catalog_scan(
    location: Annotated[str, typer.Argument(help="Path to a file or directory to scan")],
    format_hint: Annotated[
        str | None, typer.Option("--format", help="Format hint (parquet, csv, json)")
    ] = None,
) -> None:
    """Scan a file or directory location and print its inferred schema."""
    service = CatalogService()
    try:
        res = service.scan_path(location, format_hint=format_hint)
        typer.echo(f"Location: {res.location}")
        typer.echo(f"Detected Format: {res.format}")
        if res.row_count is not None:
            typer.echo(f"Total Rows: {res.row_count:,}")
        typer.echo("Columns:")
        for col in res.columns:
            nullable_str = "nullable" if col.nullable else "not null"
            typer.echo(f"  - {col.name}: {col.type} ({nullable_str})")
    except Exception as exc:
        typer.echo(f"Error scanning location: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@catalog_app.command("set-default")
def catalog_set_default(
    file: Annotated[Path, typer.Argument(help="Path to catalog YAML file to set as default")],
) -> None:
    """Set the default catalog YAML path for future sessions."""
    resolved = set_default_catalog_path(file)
    typer.echo(f"Default catalog path updated to: {resolved}")


@catalog_app.command("gui")
def catalog_gui(
    file: Annotated[
        Path | None, typer.Option("--file", "-f", help="Catalog YAML file to open")
    ] = None,
    port: Annotated[int, typer.Option("--port", "-p", help="Port to run the web server on")] = 8501,
    no_browser: Annotated[
        bool, typer.Option("--no-browser", help="Do not automatically open browser")
    ] = False,
) -> None:
    """Launch the interactive det Catalog Explorer in the local browser."""
    from det.gui import launch_gui

    launch_gui(catalog_path=file, port=port, open_browser=not no_browser)


@pipeline_app.command("gui")
def pipeline_gui_cmd(
    port: Annotated[int, typer.Option("--port", "-p", help="Port to run the web server on")] = 8501,
    no_browser: Annotated[
        bool, typer.Option("--no-browser", help="Do not automatically open browser")
    ] = False,
) -> None:
    """Launch the interactive det GUI in the local browser."""
    from det.gui import launch_gui

    launch_gui(port=port, open_browser=not no_browser)


@pipeline_app.command("set-default")
def pipeline_set_default(
    file: Annotated[Path, typer.Argument(help="Path to pipeline YAML file to set as default")],
) -> None:
    """Set the default pipeline YAML path for future sessions."""
    resolved = set_default_pipeline_path(file)
    typer.echo(f"Default pipeline path updated to: {resolved}")


# --- Pipeline / ETL File Commands ---


@pipeline_file_app.command("list")
def pipeline_file_list() -> None:
    """List all known pipeline YAML files."""
    service = PipelineService()
    files = service.get_full_tree()
    default_path = get_default_pipeline_path().resolve()
    typer.echo(f"Known Pipeline Files ({len(files)} registered):")
    for f in files:
        f_path = Path(f["path"]).resolve()
        is_default = f_path == default_path
        flags = []
        if is_default:
            flags.append("DEFAULT")
        if f.get("is_active"):
            flags.append("ACTIVE")
        flag_str = f"[{' '.join(flags)}] " if flags else ""
        projs = f.get("total_projects", 0)
        cats = f.get("total_categories", 0)
        pipes = f.get("total_pipelines", 0)
        typer.echo(
            f" • {flag_str}{f['filename']} ({projs} projects, {cats} categories, {pipes} pipelines) - {f['path']}"
        )


@pipeline_file_app.command("create")
def pipeline_file_create(
    path: Annotated[Path, typer.Argument(help="Path to the new pipeline YAML file to create")],
    set_default: Annotated[
        bool, typer.Option("--default", "-d", help="Set this file as the default pipeline file")
    ] = False,
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Overwrite file if it already exists")
    ] = False,
) -> None:
    """Create a new empty pipeline YAML file."""
    service = PipelineService()
    try:
        created = service.create_pipeline_file(
            path, set_as_default=set_default, overwrite=overwrite
        )
        def_msg = " (set as default)" if set_default else ""
        typer.echo(f"Created pipeline file: {created}{def_msg}")
    except Exception as exc:
        typer.echo(f"Error creating pipeline file: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@pipeline_file_app.command("open")
def pipeline_file_open(
    path: Annotated[
        Path, typer.Argument(help="Path to existing pipeline YAML file to open/register")
    ],
    set_default: Annotated[
        bool, typer.Option("--default", "-d", help="Set this file as the default pipeline file")
    ] = False,
) -> None:
    """Register an existing pipeline file into known pipelines and switch to it."""
    service = PipelineService()
    try:
        opened = service.switch_file(path, set_as_default=set_default)
        def_msg = " (set as default)" if set_default else ""
        typer.echo(f"Opened pipeline file: {opened}{def_msg}")
    except Exception as exc:
        typer.echo(f"Error opening pipeline file: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@pipeline_file_app.command("remove")
def pipeline_file_remove(
    path: Annotated[
        Path, typer.Argument(help="Path to pipeline YAML file to remove from known list")
    ],
) -> None:
    """Remove a pipeline YAML file from the known pipelines list (does not delete from disk)."""
    service = PipelineService()
    removed = service.remove_pipeline_file(path)
    if removed:
        typer.echo(f"Removed pipeline file from known list: {path}")
    else:
        typer.echo(f"Pipeline file was not in known list: {path}")


@pipeline_file_app.command("set-default")
def pipeline_file_set_default(
    file: Annotated[Path, typer.Argument(help="Path to pipeline YAML file to set as default")],
) -> None:
    """Set the default pipeline YAML path for future sessions."""
    resolved = set_default_pipeline_path(file)
    typer.echo(f"Default pipeline path updated to: {resolved}")


# --- Pipeline / ETL Project Commands ---


@project_app.command("list")
def project_list(
    file: Annotated[
        Path | None, typer.Option("--file", "-f", help="Pipelines YAML file to query")
    ] = None,
    search: Annotated[
        str | None, typer.Option("--search", "-s", help="Filter projects by name")
    ] = None,
) -> None:
    """List data engineering projects."""
    service = PipelineService(file)
    projects = service.list_projects(search=search)
    typer.echo(f"Pipeline Store: {service.active_path} ({len(projects)} projects)")
    for p in projects:
        cat_count = len(p.categories)
        pipe_count = sum(len(c.pipelines) for c in p.categories)
        desc_str = f" - {p.description}" if p.description else ""
        typer.echo(
            f" • [PROJECT] {p.name} ({cat_count} categories, {pipe_count} pipelines){desc_str}"
        )


@project_app.command("create")
def project_create(
    name: Annotated[str, typer.Argument(help="Name of the new project")],
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Optional project description")
    ] = None,
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Pipelines YAML file")] = None,
) -> None:
    """Create a new data engineering project."""
    service = PipelineService(file)
    try:
        proj = service.create_project(name=name, description=description)
        typer.echo(f"Created project: '{proj.name}' in {service.active_path}")
    except Exception as exc:
        typer.echo(f"Error creating project: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@project_app.command("edit")
def project_edit(
    name: Annotated[str, typer.Argument(help="Current name of the project to edit")],
    new_name: Annotated[str | None, typer.Option("--name", "-n", help="New project name")] = None,
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="New description")
    ] = None,
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Pipelines YAML file")] = None,
) -> None:
    """Update/rename an existing project."""
    service = PipelineService(file)
    try:
        proj = service.update_project(name=name, new_name=new_name, description=description)
        typer.echo(f"Updated project: '{proj.name}'")
    except Exception as exc:
        typer.echo(f"Error updating project: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@project_app.command("delete")
def project_delete(
    name: Annotated[str, typer.Argument(help="Name of the project to delete")],
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Confirm deletion without prompting")
    ] = False,
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Pipelines YAML file")] = None,
) -> None:
    """Permanently delete a project and all its categories and pipelines."""
    service = PipelineService(file)
    proj = service.get_project(name)
    if not proj:
        typer.echo(f"Error: Project '{name}' not found.", err=True)
        raise typer.Exit(code=1)

    if not yes:
        confirmed = typer.confirm(
            f"Warning: Deleting project '{name}' will permanently delete all {len(proj.categories)} categories "
            f"and contained pipelines. Are you sure you want to proceed?"
        )
        if not confirmed:
            typer.echo("Deletion cancelled.")
            raise typer.Abort()

    try:
        service.delete_project(name)
        typer.echo(f"Deleted project: '{name}' and all contents.")
    except Exception as exc:
        typer.echo(f"Error deleting project: {exc}", err=True)
        raise typer.Exit(code=1) from exc


# --- Pipeline / ETL Category Commands ---


@category_app.command("list")
def category_list(
    project: Annotated[str, typer.Argument(help="Parent project name")],
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Pipelines YAML file")] = None,
) -> None:
    """List categories inside a project."""
    service = PipelineService(file)
    try:
        categories = service.list_categories(project_name=project)
        typer.echo(f"Project '{project}' ({len(categories)} categories):")
        for c in categories:
            desc_str = f" - {c.description}" if c.description else ""
            typer.echo(f" • [CATEGORY] {c.name} ({len(c.pipelines)} pipelines){desc_str}")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@category_app.command("create")
def category_create(
    project: Annotated[str, typer.Argument(help="Parent project name")],
    name: Annotated[str, typer.Argument(help="Category name to create")],
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="Optional description")
    ] = None,
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Pipelines YAML file")] = None,
) -> None:
    """Create a new category in a project."""
    service = PipelineService(file)
    try:
        cat = service.create_category(
            project_name=project, category_name=name, description=description
        )
        typer.echo(f"Created category: '{cat.name}' in project '{project}'")
    except Exception as exc:
        typer.echo(f"Error creating category: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@category_app.command("edit")
def category_edit(
    project: Annotated[str, typer.Argument(help="Parent project name")],
    name: Annotated[str, typer.Argument(help="Current category name")],
    new_name: Annotated[str, typer.Option("--name", "-n", help="New category name")],
    description: Annotated[
        str | None, typer.Option("--description", "-d", help="New description")
    ] = None,
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Pipelines YAML file")] = None,
) -> None:
    """Update/rename a category inside a project."""
    service = PipelineService(file)
    try:
        cat = service.update_category(
            project_name=project,
            category_name=name,
            new_name=new_name,
            description=description,
        )
        typer.echo(f"Updated category: '{cat.name}' in project '{project}'")
    except Exception as exc:
        typer.echo(f"Error updating category: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@category_app.command("delete")
def category_delete(
    project: Annotated[str, typer.Argument(help="Parent project name")],
    name: Annotated[str, typer.Argument(help="Category name to delete")],
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Confirm deletion without prompting")
    ] = False,
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Pipelines YAML file")] = None,
) -> None:
    """Permanently delete a category and all pipelines inside."""
    service = PipelineService(file)
    cat = service.get_category(project_name=project, category_name=name)
    if not cat:
        typer.echo(f"Error: Category '{name}' not found in project '{project}'.", err=True)
        raise typer.Exit(code=1)

    if not yes:
        confirmed = typer.confirm(
            f"Warning: Deleting category '{name}' will permanently delete all {len(cat.pipelines)} pipelines inside. "
            f"Are you sure you want to proceed?"
        )
        if not confirmed:
            typer.echo("Deletion cancelled.")
            raise typer.Abort()

    try:
        service.delete_category(project_name=project, category_name=name)
        typer.echo(f"Deleted category: '{name}' from project '{project}'.")
    except Exception as exc:
        typer.echo(f"Error deleting category: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def main() -> None:
    """CLI application entrypoint."""
    app()


if __name__ == "__main__":
    main()
