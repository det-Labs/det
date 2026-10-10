"""det.cli - Command-line interface for the det data engineering framework by det Labs."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from det import __version__
from det.catalog import CatalogService, get_default_catalog_path, set_default_catalog_path

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
    typer.echo("Engines: Polars, PyArrow, DuckDB (planned)")


@catalog_app.command("list")
def catalog_list(
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Catalog YAML file to query")] = None,
    search: Annotated[str | None, typer.Option("--search", "-s", help="Filter by name, tag, or column")] = None,
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
    format_hint: Annotated[str | None, typer.Option("--format", help="Format hint (parquet, csv, json)")] = None,
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
    file: Annotated[Path | None, typer.Option("--file", "-f", help="Catalog YAML file to open")] = None,
    port: Annotated[int, typer.Option("--port", "-p", help="Port to run the web server on")] = 8501,
    no_browser: Annotated[bool, typer.Option("--no-browser", help="Do not automatically open browser")] = False,
) -> None:
    """Launch the interactive det Catalog Explorer in the local browser."""
    from det.gui import launch_gui

    launch_gui(catalog_path=file, port=port, open_browser=not no_browser)


def main() -> None:
    """CLI application entrypoint."""
    app()


if __name__ == "__main__":
    main()

