"""Command-line interface for the det data orchestration engine."""

import argparse
import logging
from pathlib import Path
import sys

from det.workspace import Workspace

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("det")


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser with subcommands."""
    parser = argparse.ArgumentParser(prog="det", description="Data Engineering Tool (DuckDB 2.0 Edition)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # det init [path]
    init_cmd = subparsers.add_parser("init", help="Scaffold a new det workspace")
    init_cmd.add_argument("path", nargs="?", default=".", help="Target workspace directory")

    # det run [--project <p>] [--select <s>]
    run_cmd = subparsers.add_parser("run", help="Execute models in topological order")
    run_cmd.add_argument("--project", "-p", help="Target project identifier")
    run_cmd.add_argument("--select", "-s", help="Model selector (+model, model+)")

    # det test [--project <p>]
    test_cmd = subparsers.add_parser("test", help="Execute data quality assertions")
    test_cmd.add_argument("--project", "-p", help="Target project identifier")

    # det docs [generate]
    docs_cmd = subparsers.add_parser("docs", help="Compile pipeline documentation")
    docs_sub = docs_cmd.add_subparsers(dest="docs_action", required=True)
    gen_sub = docs_sub.add_parser("generate", help="Generate static HTML documentation")
    gen_sub.add_argument("--project", "-p", help="Target project identifier")

    # det catalog [test]
    cat_cmd = subparsers.add_parser("catalog", help="Manage catalog connections")
    cat_sub = cat_cmd.add_subparsers(dest="catalog_action", required=True)
    cat_sub.add_parser("test", help="Test live connection health and latency")

    # det gui [--port <port>] [--open]
    gui_cmd = subparsers.add_parser("gui", help="Launch interactive Web IDE")
    gui_cmd.add_argument("--port", "-p", type=int, default=8080, help="Port to host Web IDE")
    gui_cmd.add_argument("--open", "-o", action="store_true", help="Automatically open browser")

    return parser


def handle_init(args: argparse.Namespace) -> int:
    """Handle det init command."""
    target_path = Path(args.path).resolve()
    ws = Workspace.init(target_path)
    ws.close()
    print(f"Initialized det workspace in: {target_path}")
    return 0


def handle_run(args: argparse.Namespace) -> int:
    """Handle det run command."""
    ws = Workspace.open(Path(".").resolve())
    try:
        report = ws.run(project=args.project, select=args.select)
        for res in report.results:
            status_symbol = "✓" if res.is_success else "✗"
            print(f"[{status_symbol}] {res.model_name} ({res.row_count} rows, {res.duration_ms}ms)")

        if not report.is_successful:
            print(f"\nPipeline run failed! ({report.failed} failed out of {report.total_models})")
            return 1
        print(f"\nPipeline completed successfully in {report.duration_ms}ms ({report.succeeded} models).")
        return 0
    finally:
        ws.close()


def handle_test(args: argparse.Namespace) -> int:
    """Handle det test command."""
    ws = Workspace.open(Path(".").resolve())
    try:
        report = ws.test(project=args.project)
        for res in report.results:
            status_label = "PASS" if res.passed else res.severity.value.upper()
            quarantine_info = f" -> {res.quarantined_table}" if res.quarantined_table else ""
            print(f"[{status_label}] {res.test_name} ({res.failing_rows_count} failing rows{quarantine_info})")

        print(f"\nTests summary: {report.passed} passed, {report.warned} warned, {report.quarantined} quarantined, {report.errored} errored.")
        return 0 if report.is_successful else 1
    finally:
        ws.close()


def handle_docs(args: argparse.Namespace) -> int:
    """Handle det docs commands."""
    ws = Workspace.open(Path(".").resolve())
    try:
        if args.docs_action == "generate":
            out_path = ws.generate_docs(project=args.project)
            print(f"Documentation compiled successfully: {out_path}")
            return 0
        return 1
    finally:
        ws.close()


def handle_catalog(args: argparse.Namespace) -> int:
    """Handle det catalog commands."""
    ws = Workspace.open(Path(".").resolve())
    try:
        if args.catalog_action == "test":
            results = ws.test_catalog()
            for name, res in results.items():
                status = "OK" if res.is_healthy else "FAIL"
                err = f" ({res.error_message})" if res.error_message else ""
                print(f"[{status}] {name} ({res.latency_ms}ms){err}")
            return 0
        return 1
    finally:
        ws.close()


def handle_gui(args: argparse.Namespace) -> int:
    """Launch embedded Web IDE HTTP server."""
    import webbrowser
    from det.gui.server import start_gui_server

    ws = Workspace.open(Path(".").resolve())
    try:
        url = f"http://127.0.0.1:{args.port}"
        print(f"det Web IDE running at {url} (Press Ctrl+C to stop)")
        if args.open:
            webbrowser.open(url)
        start_gui_server(ws, port=args.port, blocking=True)
        return 0
    finally:
        ws.close()


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint dispatching commands to specific handlers."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return handle_init(args)
    if args.command == "run":
        return handle_run(args)
    if args.command == "test":
        return handle_test(args)
    if args.command == "docs":
        return handle_docs(args)
    if args.command == "catalog":
        return handle_catalog(args)
    if args.command == "gui":
        return handle_gui(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
