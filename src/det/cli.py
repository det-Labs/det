"""Command-line interface for the det data orchestration engine."""

import argparse
import logging
from pathlib import Path
import sys

from det import __version__
from det.session import (
    is_valid_environment,
    resolve_active_root,
    set_active_environment,
)
from det.workspace import Workspace

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("det")

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser with subcommands."""
    parser = argparse.ArgumentParser(prog="det", description="Data Engineering Tool (DuckDB 2.0 Edition)")
    parser.add_argument("--version", "-v", action="version", version=f"det-core {__version__}")
    parser.add_argument("--dir", "-C", default=None, help="Target det environment directory")

    subparsers = parser.add_subparsers(dest="command", required=False)

    # det init [path]
    init_cmd = subparsers.add_parser("init", help="Scaffold a new det environment")
    init_cmd.add_argument("path", nargs="?", default=".", help="Target environment directory")

    # det activate <path>
    act_cmd = subparsers.add_parser("activate", help="Set active det environment folder for this session")
    act_cmd.add_argument("path", help="Path to existing det environment folder")

    # det status
    subparsers.add_parser("status", help="Show active det environment and scoped folders status")

    # det run [pipeline] [--select <s>] [--verbose]
    run_cmd = subparsers.add_parser("run", help="Execute models in topological order")
    run_cmd.add_argument("pipeline", nargs="?", default=None, help="Target pipeline identifier")
    run_cmd.add_argument("--project", "-p", dest="project_flag", default=None, help="Target pipeline identifier")
    run_cmd.add_argument("--select", "-s", help="Model selector (+model, model+)")
    run_cmd.add_argument("--verbose", "-v", action="store_true", help="Verbose execution output")

    # det test [pipeline]
    test_cmd = subparsers.add_parser("test", help="Execute data quality assertions")
    test_cmd.add_argument("pipeline", nargs="?", default=None, help="Target pipeline identifier")
    test_cmd.add_argument("--project", "-p", dest="project_flag", default=None, help="Target pipeline identifier")

    # det compile <pipeline>
    comp_cmd = subparsers.add_parser("compile", help="Compile and validate single pipeline without execution")
    comp_cmd.add_argument("pipeline", help="Name of pipeline to compile")

    # det pipeline [list | compile | test | run | delete | models]
    pipe_cmd = subparsers.add_parser("pipeline", aliases=["pipelines"], help="Manage and execute pipelines")
    pipe_sub = pipe_cmd.add_subparsers(dest="pipeline_action", required=False)

    # 1. det pipeline list [--folder <f>] [--filter <q>]
    p_list = pipe_sub.add_parser("list", help="List available pipelines")
    p_list.add_argument("--folder", "-f", default=None, help="Filter pipelines by folder")
    p_list.add_argument("--filter", "-q", "--contains", dest="filter", default=None, help="Filter pipelines by name substring")

    # 2. det pipeline compile <name>
    p_comp = pipe_sub.add_parser("compile", help="Compile and validate single pipeline")
    p_comp.add_argument("pipeline", help="Name of pipeline to compile")

    # 3. det pipeline test <name>
    p_test = pipe_sub.add_parser("test", help="Execute data quality assertions for single pipeline")
    p_test.add_argument("pipeline", help="Name of pipeline to test")

    # 4. det pipeline run <name> [--select <s>] [--verbose]
    p_run = pipe_sub.add_parser("run", help="Execute models in single pipeline")
    p_run.add_argument("pipeline", help="Name of pipeline to run")
    p_run.add_argument("--select", "-s", help="Model selector (+model, model+)")
    p_run.add_argument("--verbose", "-v", action="store_true", help="Verbose execution output")

    # 5. det pipeline delete <name> [--yes]
    p_del = pipe_sub.add_parser("delete", help="Delete single pipeline")
    p_del.add_argument("pipeline", help="Name of pipeline to delete")
    p_del.add_argument("--yes", "-y", action="store_true", help="Confirm deletion without prompting")

    # 6. det pipeline models <name>
    p_mod = pipe_sub.add_parser("models", aliases=["list-models"], help="List models in a given pipeline")
    p_mod.add_argument("pipeline", help="Name of pipeline to list models for")

    # 7. det pipeline docs <name>
    p_docs = pipe_sub.add_parser("docs", help="Generate documentation for a single pipeline")
    p_docs.add_argument("pipeline", help="Name of pipeline to generate docs for")

    # det docs [generate | delete | export | open]
    docs_cmd = subparsers.add_parser("docs", help="Manage pipeline documentation")
    docs_sub = docs_cmd.add_subparsers(dest="docs_action", required=False)

    # 1. det docs generate <pipeline>
    gen_sub = docs_sub.add_parser("generate", help="Generate or regenerate static HTML documentation for a single pipeline")
    gen_sub.add_argument("pipeline", nargs="?", default=None, help="Name of target pipeline")
    gen_sub.add_argument("--project", "-p", dest="project_flag", default=None, help=argparse.SUPPRESS)

    # 2. det docs delete <pipeline>
    del_sub = docs_sub.add_parser("delete", aliases=["rm", "clean"], help="Delete generated documentation for a single pipeline")
    del_sub.add_argument("pipeline", nargs="?", default=None, help="Name of target pipeline")
    del_sub.add_argument("--project", "-p", dest="project_flag", default=None, help=argparse.SUPPRESS)

    # 3. det docs export <pipeline> [--output <path>]
    exp_sub = docs_sub.add_parser("export", help="Export self-contained single-file HTML documentation for a single pipeline")
    exp_sub.add_argument("pipeline", nargs="?", default=None, help="Name of target pipeline")
    exp_sub.add_argument("--project", "-p", dest="project_flag", default=None, help=argparse.SUPPRESS)
    exp_sub.add_argument("--output", "-o", default=None, help="Destination file or directory path (defaults to ./<pipeline>_docs.html)")

    # 4. det docs open <pipeline> [--serve] [--port 8080]
    open_sub = docs_sub.add_parser("open", aliases=["view", "serve"], help="Open documentation for a single pipeline in your default web browser")
    open_sub.add_argument("pipeline", nargs="?", default=None, help="Name of target pipeline")
    open_sub.add_argument("--project", "-p", dest="project_flag", default=None, help=argparse.SUPPRESS)
    open_sub.add_argument("--serve", "-s", action="store_true", help="Start local embedded HTTP server instead of opening local file")
    open_sub.add_argument("--port", type=int, default=8080, help="Port to bind HTTP server to (default: 8080)")
    open_sub.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")

    # det catalog [list | test | display | details | delete]
    cat_cmd = subparsers.add_parser("catalog", help="Manage catalog connections")
    cat_sub = cat_cmd.add_subparsers(dest="catalog_action", required=False)

    # 1. det catalog list [--folder <f>] [--filter <q>]
    cat_list = cat_sub.add_parser("list", help="List registered catalog connections")
    cat_list.add_argument("--folder", "-f", default=None, help="Filter connections by folder")
    cat_list.add_argument("--filter", "-q", "--contains", dest="filter", default=None, help="Filter connections by name substring")

    # 2. det catalog test [connection] [--folder <f>]
    test_cat = cat_sub.add_parser("test", help="Test live connection health and latency")
    test_cat.add_argument("connection", nargs="?", default=None, help="Optional connection name to test")
    test_cat.add_argument("--folder", "-f", default=None, help="Filter connections to test by folder")

    # 3. det catalog display <connection> [--limit <N>]
    disp_cat = cat_sub.add_parser("display", help="Preview top rows from a catalog connection")
    disp_cat.add_argument("connection", help="Name of connection to preview")
    disp_cat.add_argument("--limit", "-n", type=int, default=10, help="Number of rows to display (default: 10)")

    # 4. det catalog details <connection>
    det_cat = cat_sub.add_parser("details", help="Show full metadata and properties for a connection")
    det_cat.add_argument("connection", help="Name of connection to inspect")

    # 5. det catalog delete <connection> [--yes]
    del_cat = cat_sub.add_parser("delete", help="Delete an individual catalog connection")
    del_cat.add_argument("connection", help="Name of connection to delete")
    del_cat.add_argument("--yes", "-y", action="store_true", help="Confirm deletion without prompting")

    # det gui [--port <port>] [--host <host>] [--no-browser / --no-open]
    gui_cmd = subparsers.add_parser("gui", help="Launch interactive Web IDE")
    gui_cmd.add_argument("--port", "-p", type=int, default=8080, help="Port to host Web IDE (default: 8080)")
    gui_cmd.add_argument("--host", default="127.0.0.1", help="Host interface to bind to (default: 127.0.0.1)")
    gui_cmd.add_argument("--no-browser", "--no-open", dest="no_browser", action="store_true", help="Do not automatically launch web browser")
    gui_cmd.add_argument("--open", "-o", dest="open_browser", action="store_true", default=True, help="Automatically open browser (default: True)")

    # det demo [path] [--remote] [--open]
    demo_cmd = subparsers.add_parser("demo", help="Scaffold sample demo environment with datasets and pipelines")
    demo_cmd.add_argument("path", nargs="?", default=".", help="Target environment directory")
    demo_cmd.add_argument("--remote", action="store_true", help="Download online datasets via HTTPS")
    demo_cmd.add_argument("--open", "-o", action="store_true", help="Automatically launch and open Web IDE")
    demo_cmd.add_argument("--port", "-p", type=int, default=8080, help="Port to host Web IDE")

    # det monitor [runs | run | audits | status | clean]
    mon_cmd = subparsers.add_parser("monitor", aliases=["monitoring"], help="Inspect pipeline execution telemetry, quality test audits, and sink status")
    mon_sub = mon_cmd.add_subparsers(dest="monitor_action", required=False)

    # 1. det monitor runs [pipeline] [--limit N] [--days 30] [--failed] [--filter <q>]
    mon_runs = mon_sub.add_parser("runs", help="List recent pipeline execution runs")
    mon_runs.add_argument("pipeline", nargs="?", default=None, help="Optional pipeline name to filter")
    mon_runs.add_argument("--limit", "-n", type=int, default=20, help="Number of recent runs to display (default: 20)")
    mon_runs.add_argument("--days", "-d", type=int, default=30, help="Time horizon in days (default: 30)")
    mon_runs.add_argument("--failed", action="store_true", help="Show only failed runs")
    mon_runs.add_argument("--filter", "-q", "--contains", dest="filter", default=None, help="Filter by pipeline or run ID substring")

    # 2. det monitor run <run_id>
    mon_run = mon_sub.add_parser("run", aliases=["details", "show"], help="Show detailed breakdown of a single pipeline run")
    mon_run.add_argument("run_id", help="Target run ID")

    # 3. det monitor audits [pipeline] [--run <run_id>] [--failed] [--limit N] [--filter <q>]
    mon_aud = mon_sub.add_parser("audits", help="List data quality test execution audit logs")
    mon_aud.add_argument("pipeline", nargs="?", default=None, help="Optional pipeline name to filter")
    mon_aud.add_argument("--run", "-r", dest="run_id", default=None, help="Filter audits by specific run ID")
    mon_aud.add_argument("--failed", action="store_true", help="Show only failed assertions (warned, dropped, halted)")
    mon_aud.add_argument("--limit", "-n", type=int, default=50, help="Maximum number of audit records to display (default: 50)")
    mon_aud.add_argument("--filter", "-q", "--contains", dest="filter", default=None, help="Filter by model or test name substring")

    # 4. det monitor status
    mon_stat = mon_sub.add_parser("status", aliases=["info"], help="Show monitoring sink and storage status")

    # 5. det monitor clean [--days N] [--pipeline <name>] [--yes]
    mon_clean = mon_sub.add_parser("clean", aliases=["purge", "prune"], help="Purge historical telemetry runs and test audits")
    mon_clean.add_argument("--days", "-d", type=int, default=30, help="Purge records older than N days (default: 30)")
    mon_clean.add_argument("--pipeline", "-p", default=None, help="Optional pipeline to clean")
    mon_clean.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")

    return parser


def open_active_workspace(args: argparse.Namespace) -> Workspace | None:
    """Resolve and open active det environment, validating scope."""
    explicit_dir = getattr(args, "dir", None)
    root = resolve_active_root(explicit_dir)
    if not is_valid_environment(root):
        print(f"Error: No active det environment found at '{root}'.")
        print("Hint: Run 'det init [path]' to create an environment, or 'det activate <path>' to activate an existing one.")
        return None
    try:
        return Workspace.open(root)
    except Exception as exc:
        print(f"Error opening det environment at '{root}': {exc}")
        return None


def handle_init(args: argparse.Namespace) -> int:
    """Handle det init command."""
    target_path = Path(args.path).resolve()
    ws = Workspace.init(target_path)
    ws.close()
    set_active_environment(target_path)
    print(f"Initialized det environment in: {target_path}")
    print(f"Active det environment set to: {target_path}")
    print("Scoped folders: catalog/, pipelines/, data/, extensions/ (other folders ignored)")
    return 0


def handle_activate(args: argparse.Namespace) -> int:
    """Explicitly activate a det environment for this session."""
    target_path = Path(args.path).resolve()
    if not is_valid_environment(target_path):
        print(f"Error: '{target_path}' is not a valid det environment.")
        print("Hint: Run 'det init [path]' to initialize this folder.")
        return 1
    set_active_environment(target_path)
    print(f"Active det environment set to: {target_path}")
    return 0


def handle_status(args: argparse.Namespace) -> int:
    """Show active det environment and scoped folders status."""
    root = resolve_active_root(getattr(args, "dir", None))
    print(f"Active det environment: {root}")
    if not is_valid_environment(root):
        print("Status: NOT INITIALIZED")
        print("Hint: Run 'det init [path]' to initialize.")
        return 1

    print("\nScoped Folders:")
    for folder in ("catalog", "pipelines", "data", "extensions", ".det"):
        folder_path = root / folder
        status = "OK" if folder_path.exists() else "MISSING"
        print(f"  [{status}] {folder}/")

    # Detect any extra/unscoped folders to confirm they are ignored
    other_folders = [
        d.name for d in sorted(root.iterdir())
        if d.is_dir() and d.name not in ("catalog", "pipelines", "data", "extensions", ".det", "projects")
    ]
    if other_folders:
        print(f"\nIgnored folders (out of det scope): {', '.join(other_folders)}")

    ws = Workspace.open(root)
    try:
        conns = ws.list_catalog()
        pipes = ws.projects.discover_projects()
        print(f"\nCatalog: {len(conns)} connection(s) configured")
        print(f"Pipelines: {len(pipes)} pipeline(s) scoped ({', '.join(pipes) if pipes else 'none'})")
    finally:
        ws.close()
    return 0


def handle_run(args: argparse.Namespace) -> int:
    """Handle det run command."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    try:
        target_project = getattr(args, "pipeline", None) or getattr(args, "project_flag", None) or getattr(args, "project", None)
        report = ws.run(project=target_project, select=args.select)
        for res in report.results:
            status_symbol = "PASS" if res.is_success else "FAIL"
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
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    try:
        target_project = getattr(args, "pipeline", None) or getattr(args, "project_flag", None) or getattr(args, "project", None)
        report = ws.test(project=target_project)
        for res in report.results:
            status_label = "PASS" if res.passed else res.severity.value.upper()
            action_info = f" -> {res.quarantined_table}" if res.quarantined_table else ""
            print(f"[{status_label}] {res.test_name} ({res.failing_rows_count} failing rows{action_info})")

        print(f"\nTests summary: {report.passed} passed, {report.warned} warned, {report.dropped} dropped, {report.errored} errored.")
        return 0 if report.is_successful else 1
    finally:
        ws.close()


def handle_pipeline_list(args: argparse.Namespace) -> int:
    """List pipelines (all / folder / filter by name)."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    try:
        folder = getattr(args, "folder", None)
        name_filter = getattr(args, "filter", None)
        pipelines = ws.list_pipelines(folder=folder, name_filter=name_filter)
        if not pipelines:
            filter_parts = []
            if folder:
                filter_parts.append(f"in folder '{folder}'")
            if name_filter:
                filter_parts.append(f"matching '{name_filter}'")
            desc = f" ({', '.join(filter_parts)})" if filter_parts else ""
            print(f"No pipelines found{desc}.")
            return 0

        header_text = f"Pipelines ({len(pipelines)} found"
        filter_parts = []
        if folder:
            filter_parts.append(f"in folder '{folder}'")
        if name_filter:
            filter_parts.append(f"matching '{name_filter}'")
        if filter_parts:
            header_text += f" - {', '.join(filter_parts)}"
        header_text += "):"
        print(header_text)

        max_name = max(max(len(p["name"]) for p in pipelines), 8)
        max_folder = max(max(len(p["folder"] or "Core") for p in pipelines), 6)
        max_models = max(max(len(str(p["models_count"])) for p in pipelines), 6)

        header = f"{'PIPELINE'.ljust(max_name)}  {'FOLDER'.ljust(max_folder)}  {'MODELS'.ljust(max_models)}  LOCATION"
        sep = "-" * max(len(header), 60)
        print(sep)
        print(header)
        print(sep)
        for p in pipelines:
            folder_val = p["folder"] or "Core"
            print(f"{p['name'].ljust(max_name)}  {folder_val.ljust(max_folder)}  {str(p['models_count']).ljust(max_models)}  {p['path']}")
        print(sep)
        return 0
    finally:
        ws.close()


def handle_pipeline_compile(args: argparse.Namespace) -> int:
    """Compile a single pipeline, verifying DAG, cycles, and dependencies."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    pipeline_name = getattr(args, "pipeline", None)
    if not pipeline_name:
        print("Error: Pipeline name is required for compile.")
        return 1
    try:
        print(f"Compiling pipeline '{pipeline_name}'...")
        res = ws.compile_pipeline(pipeline_name)
        if not res["is_valid"]:
            print(f"\n[FAIL] Pipeline '{pipeline_name}' compilation failed:")
            for err in res["errors"]:
                print(f"  - {err}")
            return 1

        print(f"[OK] Model DAG compiled ({res['models_count']} model(s), 0 cycles detected)")
        print(f"[OK] Dependencies verified: {len(res['sources'])} catalog source(s), {len(res['refs'])} model ref(s)")
        print(f"\nPipeline '{pipeline_name}' compiled successfully.")
        return 0
    except KeyError as e:
        print(f"Error: {e}")
        return 1
    finally:
        ws.close()


def handle_pipeline_test(args: argparse.Namespace) -> int:
    """Run data quality assertions for a single pipeline."""
    pipeline_name = getattr(args, "pipeline", None) or getattr(args, "project_flag", None) or getattr(args, "project", None)
    if not pipeline_name:
        print("Error: Pipeline name is required.")
        return 1
    args.project = pipeline_name
    return handle_test(args)


def handle_pipeline_run(args: argparse.Namespace) -> int:
    """Run models for a single pipeline."""
    pipeline_name = getattr(args, "pipeline", None) or getattr(args, "project_flag", None) or getattr(args, "project", None)
    if not pipeline_name:
        print("Error: Pipeline name is required.")
        return 1
    args.project = pipeline_name
    return handle_run(args)


def handle_pipeline_delete(args: argparse.Namespace) -> int:
    """Delete a single pipeline."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    pipeline_name = getattr(args, "pipeline", None)
    if not pipeline_name:
        print("Error: Pipeline name is required.")
        return 1
    try:
        known = ws.projects.discover_projects()
        if pipeline_name not in known:
            print(f"Error: Pipeline '{pipeline_name}' not found.")
            return 1

        if not getattr(args, "yes", False) and sys.stdin.isatty():
            confirm = input(f"Are you sure you want to delete pipeline '{pipeline_name}'? [y/N]: ")
            if confirm.strip().lower() not in ("y", "yes"):
                print("Aborted.")
                return 0

        deleted = ws.delete_pipeline(pipeline_name)
        if deleted:
            print(f"Deleted pipeline '{pipeline_name}'.")
            return 0
        print(f"Error: Could not delete pipeline '{pipeline_name}'.")
        return 1
    finally:
        ws.close()


def handle_pipeline_models(args: argparse.Namespace) -> int:
    """List all models in a given pipeline."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    pipeline_name = getattr(args, "pipeline", None)
    if not pipeline_name:
        print("Error: Pipeline name is required.")
        return 1
    try:
        models = ws.list_pipeline_models(pipeline_name)
        if not models:
            print(f"Pipeline '{pipeline_name}' contains 0 models.")
            return 0

        print(f"Models in pipeline '{pipeline_name}' ({len(models)} model(s)):")
        max_name = max(max(len(m.name) for m in models), 5)
        mat_strings = [
            m.config.materialized.value if hasattr(m.config.materialized, "value") else str(m.config.materialized)
            for m in models
        ]
        max_mat = max(max(len(s) for s in mat_strings), 15)

        layers = []
        for m in models:
            layer = m.file_path.parent.name if m.file_path else "models"
            layers.append(layer)
        max_layer = max(max(len(l) for l in layers), 5)

        header = f"{'MODEL'.ljust(max_name)}  {'MATERIALIZATION'.ljust(max_mat)}  {'LAYER'.ljust(max_layer)}  DEPENDENCIES"
        sep = "-" * max(len(header), 60)
        print(sep)
        print(header)
        print(sep)

        for m, mat_str, layer in zip(models, mat_strings, layers):
            deps = [f"source('{s}')" for s in m.sources] + [f"ref('{r}')" for r in m.refs]
            dep_str = ", ".join(deps) if deps else "-"
            print(f"{m.name.ljust(max_name)}  {mat_str.ljust(max_mat)}  {layer.ljust(max_layer)}  {dep_str}")
        print(sep)
        return 0
    except KeyError as e:
        print(f"Error: {e}")
        return 1
    finally:
        ws.close()


def handle_pipeline(args: argparse.Namespace) -> int:
    """Dispatch pipeline subcommands."""
    action = getattr(args, "pipeline_action", None) or "list"
    if action == "list":
        return handle_pipeline_list(args)
    if action == "compile":
        return handle_pipeline_compile(args)
    if action == "test":
        return handle_pipeline_test(args)
    if action == "run":
        return handle_pipeline_run(args)
    if action == "delete":
        return handle_pipeline_delete(args)
    if action in ("models", "list-models"):
        return handle_pipeline_models(args)
    if action == "docs":
        return handle_pipeline_docs(args)
    print(f"Unknown pipeline action: {action}")
    return 1


def handle_pipeline_docs(args: argparse.Namespace) -> int:
    """Generate static HTML documentation for a single pipeline."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    try:
        pipeline_name = args.pipeline
        known = ws.projects.discover_projects()
        if known and pipeline_name not in known:
            print(f"Error: Pipeline '{pipeline_name}' does not exist. Available: {', '.join(known)}")
            return 1
        out_path = ws.generate_docs(pipeline=pipeline_name)
        print(f"[OK] Documentation generated successfully: {out_path.resolve()}")
        return 0
    except KeyError as e:
        print(f"Error: {e}")
        return 1
    finally:
        ws.close()


def handle_docs(args: argparse.Namespace) -> int:
    """Handle det docs commands: generate, delete, export, open."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    try:
        action = getattr(args, "docs_action", None) or "generate"
        pipeline_name = (
            getattr(args, "pipeline", None)
            or getattr(args, "project_flag", None)
            or getattr(args, "project", None)
        )

        known = ws.projects.discover_projects()
        if not pipeline_name:
            if len(known) == 1:
                pipeline_name = known[0]
            elif getattr(ws.config, "default_project", None) in known:
                pipeline_name = ws.config.default_project
            else:
                print(f"[ERROR] Pipeline name is required for docs {action}. Usage: det docs {action} <pipeline>")
                if known:
                    print(f"Available pipelines: {', '.join(known)}")
                return 1

        if known and pipeline_name not in known:
            print(f"[ERROR] Pipeline '{pipeline_name}' does not exist. Available: {', '.join(known)}")
            return 1

        if action == "generate":
            out_path = ws.generate_docs(pipeline=pipeline_name)
            print(f"[OK] Documentation generated successfully: {out_path.resolve()}")
            return 0

        elif action in ("delete", "rm", "clean"):
            deleted = ws.delete_docs(pipeline=pipeline_name)
            if deleted:
                print(f"[OK] Documentation deleted successfully for pipeline '{pipeline_name}'.")
            else:
                print(f"[INFO] No generated documentation found for pipeline '{pipeline_name}'.")
            return 0

        elif action == "export":
            out_arg = getattr(args, "output", None)
            exported = ws.export_docs(pipeline=pipeline_name, output_path=out_arg)
            print(f"[OK] Documentation exported successfully to: {exported.resolve()}")
            return 0

        elif action in ("open", "view", "serve"):
            index_path = ws.get_docs_path(pipeline_name)
            if index_path is None or not index_path.exists():
                print(f"[INFO] Documentation not yet generated for '{pipeline_name}'. Compiling now...")
                index_path = ws.generate_docs(pipeline=pipeline_name)

            abs_index = index_path.resolve()
            serve_mode = getattr(args, "serve", False) or action == "serve"
            no_browser = getattr(args, "no_browser", False)

            if serve_mode:
                port = getattr(args, "port", 8080)
                url = f"http://127.0.0.1:{port}"
                print(f"[OK] Serving documentation for pipeline '{pipeline_name}' at {url}")
                print(f"Directory: {abs_index.parent.resolve()}")
                print("Press Ctrl+C to stop the server.")
                if not no_browser:
                    import webbrowser
                    webbrowser.open(url)
                ws.docs_server.start_server(abs_index.parent, port=port)
                return 0
            else:
                uri = abs_index.as_uri()
                print(f"[OK] Opening documentation in browser: {uri}")
                if not no_browser:
                    import webbrowser
                    webbrowser.open(uri)
                return 0

        print(f"[ERROR] Unknown docs action: '{action}'")
        return 1
    except Exception as e:
        print(f"[ERROR] Docs command failed: {e}")
        return 1
    finally:
        ws.close()


def handle_catalog(args: argparse.Namespace) -> int:
    """Handle det catalog commands: list, test, display, details, delete."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    try:
        action = getattr(args, "catalog_action", None) or "list"

        # 1. list (all / under one folder / filter by name)
        if action == "list":
            folder = getattr(args, "folder", None)
            name_filter = getattr(args, "filter", None)
            conns = ws.list_catalog(folder=folder, name_filter=name_filter)
            if not conns:
                filter_parts = []
                if folder:
                    filter_parts.append(f"in folder '{folder}'")
                if name_filter:
                    filter_parts.append(f"matching '{name_filter}'")
                filter_msg = f" ({', '.join(filter_parts)})" if filter_parts else ""
                print(f"No catalog connections configured{filter_msg}.")
                print("Define connections in catalog/connections.yaml or via the Web IDE.")
                return 0

            header_text = f"Catalog Connections ({len(conns)} configured"
            filter_parts = []
            if folder:
                filter_parts.append(f"in folder '{folder}'")
            if name_filter:
                filter_parts.append(f"matching '{name_filter}'")
            if filter_parts:
                header_text += f" - {', '.join(filter_parts)}"
            header_text += "):"
            print(header_text)

            max_name = max(max(len(c.name) for c in conns), 4)
            max_type = max(max(len(c.type) for c in conns), 4)
            max_tier = max(max(len(c.tier_value) for c in conns), 4)
            max_folder = max(max(len(c.folder or "(Root)") for c in conns), 6)

            header = (
                f"{'NAME'.ljust(max_name)}  {'TYPE'.ljust(max_type)}  {'TIER'.ljust(max_tier)}  "
                f"{'FOLDER'.ljust(max_folder)}  TARGET / PATH"
            )
            separator = "-" * max(len(header), 60)
            print(separator)
            print(header)
            print(separator)

            for c in conns:
                target = (
                    c.options.get("path")
                    or c.options.get("table_path")
                    or c.options.get("url")
                    or c.options.get("database")
                    or c.options.get("query")
                    or "-"
                )
                folder_val = c.folder or "(Root)"
                print(
                    f"{c.name.ljust(max_name)}  {c.type.ljust(max_type)}  {c.tier_value.ljust(max_tier)}  "
                    f"{folder_val.ljust(max_folder)}  {target}"
                )
            print(separator)
            return 0

        # 2. test (single / all / under one folder)
        if action == "test":
            target_conn = getattr(args, "connection", None)
            target_folder = getattr(args, "folder", None)
            try:
                results = ws.test_catalog(connection=target_conn, folder=target_folder)
            except KeyError as e:
                print(f"Error: {e}")
                return 1

            if not results:
                target_desc = f"in folder '{target_folder}'" if target_folder else "found"
                print(f"No catalog connections {target_desc} to test.")
                return 0

            for name, res in results.items():
                status = "OK" if res.is_healthy else "FAIL"
                err = f" ({res.error_message})" if res.error_message else ""
                print(f"[{status}] {name} ({res.latency_ms}ms){err}")

            all_ok = all(r.is_healthy for r in results.values())
            return 0 if all_ok else 1

        # 3. display (return top N rows from connection)
        if action == "display":
            name = args.connection
            limit = getattr(args, "limit", 10) or 10
            try:
                columns, rows = ws.display_catalog(name=name, limit=limit)
            except KeyError as e:
                print(f"Error: {e}")
                return 1
            except Exception as e:
                print(f"Error reading connection '{name}': {e}")
                return 1

            if not rows:
                print(f"Connection '{name}' contains 0 rows.")
                return 0

            print(f"Preview '{name}' (Top {len(rows)} row(s)):")
            col_widths = [len(c) for c in columns]
            str_rows = []
            for r in rows:
                row_strs = [str(val) if val is not None else "NULL" for val in r]
                for i, s in enumerate(row_strs):
                    col_widths[i] = max(col_widths[i], len(s))
                str_rows.append(row_strs)

            col_widths = [min(w, 40) for w in col_widths]
            header_parts = [columns[i].ljust(col_widths[i])[:col_widths[i]] for i in range(len(columns))]
            header = " | ".join(header_parts)
            sep = "-+-".join(["-" * col_widths[i] for i in range(len(columns))])

            print(sep)
            print(header)
            print(sep)
            for r in str_rows:
                parts = [r[i].ljust(col_widths[i])[:col_widths[i]] for i in range(len(r))]
                print(" | ".join(parts))
            print(sep)
            return 0

        # 4. details (connection name, type, and all properties/metadata)
        if action == "details":
            name = args.connection
            try:
                det = ws.details_catalog(name=name)
            except KeyError as e:
                print(f"Error: {e}")
                return 1

            print(f"\nConnection Details: {det['name']}")
            print("-" * 60)
            print(f"Name:        {det['name']}")
            print(f"Type:        {det['type']}")
            print(f"Tier:        {det['tier']}")
            print(f"Folder:      {det['folder']}")
            if det["description"]:
                print(f"Description: {det['description']}")
            print("Options:")
            for k, v in det["options"].items():
                print(f"  {k}: {v}")
            if det["credentials"]:
                print("Credentials:")
                for k, v in det["credentials"].items():
                    print(f"  {k}: {v}")
            print("\nMount SQL:")
            print(f"  {det['mount_sql']}")
            print("-" * 60)
            return 0

        # 5. delete (deletes individual connection)
        if action == "delete":
            name = args.connection
            conn = ws.catalog.get_connection(name)
            if conn is None:
                print(f"Error: Connection '{name}' not found in catalog.")
                return 1

            if not getattr(args, "yes", False) and sys.stdin.isatty():
                confirm = input(f"Are you sure you want to delete connection '{name}'? [y/N]: ")
                if confirm.strip().lower() not in ("y", "yes"):
                    print("Aborted.")
                    return 0

            ws.delete_catalog_connection(name)
            print(f"Deleted connection '{name}' from catalog/connections.yaml.")
            return 0

        print(f"Unknown catalog action: {action}")
        return 1
    finally:
        ws.close()


def handle_gui(args: argparse.Namespace) -> int:
    """Launch embedded Web IDE HTTP server."""
    import threading
    import webbrowser
    from det.gui.server import start_gui_server

    ws = open_active_workspace(args)
    if ws is None:
        return 1
    try:
        host = getattr(args, "host", "127.0.0.1")
        port = getattr(args, "port", 8080)
        url = f"http://{host}:{port}"
        print(f"Attached Workspace : {ws.root}")
        print(f"det Web IDE running at {url} (Press Ctrl+C to stop)")

        should_open = not getattr(args, "no_browser", False)
        if should_open:
            threading.Timer(0.3, lambda: webbrowser.open(url)).start()

        start_gui_server(ws, host=host, port=port, blocking=True)
        return 0
    finally:
        ws.close()


def handle_demo(args: argparse.Namespace) -> int:
    """Handle det demo / sample command."""
    from det.demo import setup_demo_workspace
    target_path = Path(args.path).resolve()
    print(f"Scaffolding det demo workspace in: {target_path}...")
    res = setup_demo_workspace(target_path, use_remote=args.remote)
    set_active_environment(target_path)
    print(f"[+] Generated {len(res['datasets'])} datasets in data/")
    print(f"[+] Created catalog connections in catalog/connections.yaml")
    print(f"[+] Scaffolded {len(res['pipelines'])} sample pipelines: {', '.join(res['pipelines'])}")
    print(f"Active det environment set to: {target_path}")
    if args.open:
        args.command = "gui"
        return handle_gui(args)
    print("\nTo explore in Web IDE, run:")
    print("  det gui --open")
    return 0


def handle_monitor_runs(args: argparse.Namespace) -> int:
    """List recent pipeline execution runs with inclusive priority."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    try:
        pipeline = getattr(args, "pipeline", None)
        limit = getattr(args, "limit", 20)
        days = getattr(args, "days", 30)
        failed = getattr(args, "failed", False)
        name_filter = getattr(args, "filter", None)

        runs = ws.monitor_runs(project=pipeline, limit=limit, days=days, failed_only=failed)
        if name_filter:
            q = name_filter.lower()
            runs = [r for r in runs if q in r.project.lower() or q in r.run_id.lower()]

        if not runs:
            print("No pipeline execution runs found.")
            return 0

        header = f"{'RUN ID'.ljust(28)}  {'PIPELINE'.ljust(20)}  {'STATUS'.ljust(10)}  {'STARTED AT'.ljust(22)}  {'DURATION'.ljust(12)}  {'MODELS'.ljust(8)}  ROWS"
        sep = "-" * max(len(header), 115)
        print(sep)
        print(header)
        print(sep)
        for r in runs:
            st = f"[{r.status}]"
            dur = f"{r.duration_ms:.1f}ms" if r.duration_ms < 1000 else f"{r.duration_ms/1000:.2f}s"
            rows_str = f"{r.rows_affected:,}"
            start_str = r.started_at[:19].replace("T", " ")
            print(f"{r.run_id.ljust(28)}  {r.project.ljust(20)}  {st.ljust(10)}  {start_str.ljust(22)}  {dur.ljust(12)}  {str(r.models_executed).ljust(8)}  {rows_str}")
        print(sep)
        return 0
    finally:
        ws.close()


def handle_monitor_run_detail(args: argparse.Namespace) -> int:
    """Show detailed model breakdown of a single pipeline run."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    try:
        run_id = args.run_id
        run = ws.monitor_run_detail(run_id)
        if not run:
            print(f"Error: Run '{run_id}' not found.")
            return 1

        dur = f"{run.duration_ms:.1f}ms" if run.duration_ms < 1000 else f"{run.duration_ms/1000:.2f}s"
        sep = "-" * 70
        print(sep)
        print(f"RUN DETAILS: {run.run_id}")
        print(sep)
        print(f"Pipeline        : {run.project}")
        print(f"Status          : [{run.status}]")
        print(f"Started At      : {run.started_at}")
        print(f"Completed At    : {run.completed_at}")
        print(f"Duration        : {dur}")
        print(f"Models Executed : {run.models_executed}")
        print(f"Rows Affected   : {run.rows_affected:,}")
        if run.error_message:
            print(f"Error Message   : {run.error_message}")
        print(sep)

        if run.models_detail:
            m_header = f"{'MODEL'.ljust(25)}  {'STATUS'.ljust(10)}  {'DURATION'.ljust(12)}  {'ROWS'.ljust(10)}  ERROR"
            print(m_header)
            print("-" * max(len(m_header), 70))
            for m in run.models_detail:
                m_name = m.get("model_name", "-")
                m_st = f"[{m.get('status', 'SUCCESS')}]"
                m_dur = f"{float(m.get('duration_ms', 0)):.1f}ms"
                m_rows = f"{int(m.get('rows_affected', 0)):,}"
                m_err = m.get("error_message") or "-"
                print(f"{m_name.ljust(25)}  {m_st.ljust(10)}  {m_dur.ljust(12)}  {m_rows.ljust(10)}  {m_err}")
            print(sep)
        return 0
    finally:
        ws.close()


def handle_monitor_audits(args: argparse.Namespace) -> int:
    """List data quality test execution audit logs."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    try:
        pipeline = getattr(args, "pipeline", None)
        run_id = getattr(args, "run_id", None)
        failed = getattr(args, "failed", False)
        limit = getattr(args, "limit", 50)
        name_filter = getattr(args, "filter", None)

        audits = ws.monitor_audits(project=pipeline, run_id=run_id, failed_only=failed, limit=limit)
        if name_filter:
            q = name_filter.lower()
            audits = [a for a in audits if q in a.model_name.lower() or q in a.test_name.lower()]

        if not audits:
            print("No test audit records found.")
            return 0

        header = f"{'AUDIT ID'.ljust(26)}  {'MODEL'.ljust(20)}  {'TEST NAME'.ljust(28)}  {'SEV'.ljust(8)}  {'PASSED'.ljust(8)}  {'FAILURES'.ljust(10)}  ACTION TAKEN"
        sep = "-" * max(len(header), 120)
        print(sep)
        print(header)
        print(sep)
        for a in audits:
            pass_str = "PASS" if a.passed else "FAIL"
            print(f"{a.audit_id.ljust(26)}  {a.model_name.ljust(20)}  {a.test_name.ljust(28)}  {a.severity.ljust(8)}  {pass_str.ljust(8)}  {str(a.failures_count).ljust(10)}  {a.action_taken}")
        print(sep)
        return 0
    finally:
        ws.close()


def handle_monitor_status(args: argparse.Namespace) -> int:
    """Show monitoring sink and storage status."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    try:
        info = ws.monitor_status()
        sep = "-" * 60
        print(sep)
        print("DET TELEMETRY & MONITORING STATUS")
        print(sep)
        print(f"Active Sink     : {info.get('active_sink', 'duckdb')}")
        print(f"Available Sinks : {', '.join(info.get('available_sinks', []))}")
        print(f"Storage Path    : {info.get('storage_path', '-')}")
        print(f"Total Runs      : {info.get('total_runs', 0):,}")
        print(f"Total Audits    : {info.get('total_audits', 0):,}")
        print(sep)
        return 0
    finally:
        ws.close()


def handle_monitor_clean(args: argparse.Namespace) -> int:
    """Purge historical telemetry runs and test audits."""
    ws = open_active_workspace(args)
    if ws is None:
        return 1
    try:
        days = getattr(args, "days", 30)
        pipeline = getattr(args, "pipeline", None)
        auto_yes = getattr(args, "yes", False)

        scope_str = f" for pipeline '{pipeline}'" if pipeline else ""
        if not auto_yes and sys.stdin.isatty():
            prompt = f"Are you sure you want to purge telemetry records older than {days} days{scope_str}? [y/N]: "
            ans = input(prompt).strip().lower()
            if ans not in ("y", "yes"):
                print("Operation cancelled.")
                return 0

        res = ws.monitor_clean(days=days, project=pipeline)
        purged_r = res.get("purged_runs", 0)
        purged_a = res.get("purged_audits", 0)
        print(f"[OK] Purged {purged_r} runs and {purged_a} test audits older than {days} days{scope_str}.")
        return 0
    finally:
        ws.close()


def handle_monitor(args: argparse.Namespace) -> int:
    """Dispatch det monitor commands."""
    action = getattr(args, "monitor_action", None) or "runs"
    if action == "runs":
        return handle_monitor_runs(args)
    if action in ("run", "details", "show"):
        return handle_monitor_run_detail(args)
    if action == "audits":
        return handle_monitor_audits(args)
    if action in ("status", "info"):
        return handle_monitor_status(args)
    if action in ("clean", "purge", "prune"):
        return handle_monitor_clean(args)
    print(f"Unknown monitor action: {action}")
    return 1


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint dispatching commands to specific handlers."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "init":
        return handle_init(args)
    if args.command == "activate":
        return handle_activate(args)
    if args.command == "status":
        return handle_status(args)
    if args.command == "run":
        return handle_run(args)
    if args.command == "test":
        return handle_test(args)
    if args.command in ("pipeline", "pipelines"):
        return handle_pipeline(args)
    if args.command == "compile":
        return handle_pipeline_compile(args)
    if args.command == "docs":
        return handle_docs(args)
    if args.command == "catalog":
        return handle_catalog(args)
    if args.command == "gui":
        return handle_gui(args)
    if args.command == "demo":
        return handle_demo(args)
    if args.command in ("monitor", "monitoring"):
        return handle_monitor(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
