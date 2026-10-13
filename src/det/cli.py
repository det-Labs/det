"""Command-line entry point."""

import argparse
from pathlib import Path

from det.gui import serve_gui
from det.workspace import initialize_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="det", description="Modular SQL ETL workspace")
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="initialize a workspace folder")
    init_parser.add_argument(
        "workspace",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="workspace location (default: current directory)",
    )

    gui_parser = commands.add_parser("gui", help="launch the browser interface")
    gui_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="initialized workspace (default: current directory)",
    )
    gui_parser.add_argument("--port", type=int, default=8765, help="port to bind (default: 8765)")

    run_parser = commands.add_parser("run", help="execute a pipeline via DataFusion")
    run_parser.add_argument("pipeline", help="pipeline identifier or path (e.g. demo/summarize)")
    run_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="workspace location (default: current directory)",
    )

    val_parser = commands.add_parser("validate", help="pre-flight validate a pipeline")
    val_parser.add_argument("pipeline", help="pipeline identifier or path (e.g. demo/summarize)")
    val_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="workspace location (default: current directory)",
    )

    pipe_parser = commands.add_parser("pipeline", help="inspect pipeline definitions")
    pipe_sub = pipe_parser.add_subparsers(dest="subcommand", required=True)
    pipe_list = pipe_sub.add_parser("list", help="list configured pipelines")
    pipe_list.add_argument("--folder", default=None, help="filter by folder")
    pipe_list.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="workspace location (default: current directory)",
    )

    runs_parser = commands.add_parser("runs", help="list pipeline execution telemetry")
    runs_parser.add_argument("--pipeline", default=None, help="filter by pipeline name or ID")
    runs_parser.add_argument("--limit", type=int, default=20, help="maximum runs to display")
    runs_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="workspace location (default: current directory)",
    )

    docs_parser = commands.add_parser("docs", help="generate single-file documentation with lineage diagrams")
    docs_parser.add_argument("pipeline", help="pipeline folder/name or ID")
    docs_parser.add_argument("--format", choices=["html", "markdown", "md"], default="html", help="output format (default: html)")
    docs_parser.add_argument("--output", type=Path, default=None, help="output file path")
    docs_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="workspace location (default: current directory)",
    )

    samples_parser = commands.add_parser(
        "sample-data",
        aliases=["samples"],
        help="install sample warehouse datasets, catalog, and pipelines into workspace",
    )
    samples_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="workspace location (default: current directory)",
    )
    samples_parser.add_argument(
        "--no-select-catalog",
        action="store_true",
        help="do not set sample_warehouse.yaml as active catalog",
    )

    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "init":
        workspace = initialize_workspace(args.workspace)
        print(f"Initialized det workspace: {workspace}")
        return

    if args.command in ("sample-data", "samples"):
        from det.sample_data import install_sample_data

        result = install_sample_data(
            args.workspace,
            select_catalog=not getattr(args, "no_select_catalog", False),
        )
        print(f"Installed sample warehouse in: {result['workspace']}")
        print(f"  - Source data: {result['source_data_folder']}/")
        print(f"  - Catalog: catalog/{result['catalog']} (active)")
        print(f"  - Pipelines: pipelines/{result['pipelines_folder']}/ ({result['pipeline_count']} pipelines)")
        return

    if args.command == "gui":
        serve_gui(args.workspace, args.port)
        return

    # Headless commands configure the workspace first
    from det.api import configure_api, get_monitoring_store, get_pipeline_store, run_pipeline, validate_pipeline

    configure_api(args.workspace)

    if args.command == "run":
        print(f"Executing pipeline: {args.pipeline}...")
        result = run_pipeline(args.pipeline)
        dur = result.get("total_duration_seconds", 0) * 1000
        status = result.get("status", "UNKNOWN")
        steps = result.get("steps", [])
        total_rows = sum(s.get("rows_processed", 0) for s in steps)
        print(f"Status: {status} ({dur:.1f}ms) | {len(steps)} step(s) | {total_rows} rows processed")
        for s in steps:
            print(f"  - Step '{s['step_name']}': {s['status']} ({s['duration_ms']:.1f}ms, {s['rows_processed']} rows)")
            for d in s.get("destinations", []):
                print(f"    -> Destination '{d['destination_name']}' ({d['format']}): {d['rows_written']} rows in {d['duration_ms']:.1f}ms")
        if result.get("error"):
            print(f"Error: {result['error']}")
            raise SystemExit(1)
        return

    if args.command == "validate":
        print(f"Validating pipeline: {args.pipeline}...")
        result = validate_pipeline(args.pipeline)
        if result.get("valid"):
            print(f"Valid: YES | {len(result.get('steps', []))} step(s) verified.")
            for s in result.get("steps", []):
                print(f"  - Step '{s['step_name']}': {s['column_count']} column(s) inferred")
        else:
            print(f"Valid: NO | Failed in step '{result.get('failed_step')}'")
            print(f"Error: {result.get('error')}")
            for h in result.get("hints", []):
                print(f"  Hint: {h}")
            raise SystemExit(1)
        return

    if args.command == "pipeline" and args.subcommand == "list":
        store = get_pipeline_store()
        items = store.list_pipelines(args.folder)
        print(f"Pipelines ({len(items)} found):")
        for p in items:
            step_count = len(p.get("steps", []))
            print(f"  - {p['folder']}/{p['name']} ({step_count} step{'s' if step_count != 1 else ''}) [{p.get('catalog', 'default.yaml')}]")
        return

    if args.command == "runs":
        mstore = get_monitoring_store()
        runs = mstore.list_runs(pipeline_name=args.pipeline, limit=args.limit)
        print(f"Execution Runs ({len(runs)} found):")
        for r in runs:
            dur = r.get("total_duration_seconds", 0) * 1000
            print(f"  [{r['status']}] {r['folder_at_run']}/{r['pipeline_name_at_run']} | {dur:.1f}ms | {r['started_at']}")
        return

    if args.command == "docs":
        from det.api import generate_pipeline_docs, save_pipeline_docs
        fmt = "markdown" if args.format in ("md", "markdown") else "html"
        if args.output:
            content = generate_pipeline_docs(args.pipeline, doc_format=fmt)
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            print(f"Generated {fmt.upper()} documentation: {out_path} ({len(content)} bytes)")
        else:
            result = save_pipeline_docs(args.pipeline, doc_format=fmt)
            print(f"Generated {fmt.upper()} documentation: {result['saved_path']} ({result['bytes_written']} bytes)")
        return


if __name__ == "__main__":
    main()
