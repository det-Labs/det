"""Comprehensive test suite for Documentation CLI commands and Workspace facade."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from det.cli import main
from det.workspace import Workspace


def test_docs_generate_overwrite_and_absolute_paths(tmp_path: Path):
    """Test generating docs for a single pipeline, verifying absolute paths and overwrite behavior."""
    ws = Workspace.init(tmp_path)

    # 1. Pipeline default exists
    models_dir = tmp_path / "pipelines" / "default" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "m1.sql").write_text("SELECT 42 AS value", encoding="utf-8")

    # Generate docs
    html_path = ws.generate_docs(pipeline="default")
    assert html_path.is_absolute()
    assert html_path.exists()
    assert html_path.name == "index.html"
    assert "m1" in html_path.read_text(encoding="utf-8")

    manifest_path = html_path.parent / "manifest.json"
    assert manifest_path.is_absolute()
    assert manifest_path.exists()

    # 2. Add another model and re-generate: must overwrite without error
    (models_dir / "m2.sql").write_text("SELECT 100 AS num", encoding="utf-8")
    html_path_re = ws.generate_docs(pipeline="default")
    assert html_path_re == html_path
    content = html_path_re.read_text(encoding="utf-8")
    assert "m1" in content
    assert "m2" in content

    # 3. get_docs_path returns absolute path
    found_path = ws.get_docs_path("default")
    assert found_path is not None
    assert found_path.is_absolute()
    assert found_path == html_path

    # Non-existent pipeline raises KeyError
    with pytest.raises(KeyError, match="Pipeline 'missing_pipe' does not exist"):
        ws.generate_docs(pipeline="missing_pipe")

    ws.close()


def test_docs_delete_facade(tmp_path: Path):
    """Test deleting generated documentation via workspace facade."""
    ws = Workspace.init(tmp_path)
    models_dir = tmp_path / "pipelines" / "default" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "m1.sql").write_text("SELECT 1", encoding="utf-8")

    ws.generate_docs(pipeline="default")
    assert ws.get_docs_path("default") is not None

    # Delete docs
    assert ws.delete_docs(pipeline="default") is True
    assert ws.get_docs_path("default") is None

    # Deleting again returns False
    assert ws.delete_docs(pipeline="default") is False

    ws.close()


def test_docs_export_facade(tmp_path: Path):
    """Test exporting single-file HTML documentation to custom absolute locations."""
    ws = Workspace.init(tmp_path)
    models_dir = tmp_path / "pipelines" / "default" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / "m1.sql").write_text("SELECT 1", encoding="utf-8")

    # Export to explicit file path
    target_file = tmp_path / "exports" / "custom_doc.html"
    exported = ws.export_docs("default", output_path=target_file)
    assert exported.is_absolute()
    assert exported.exists()
    assert exported == target_file.resolve()
    assert "<!DOCTYPE html>" in exported.read_text(encoding="utf-8")

    # Export to directory
    export_dir = tmp_path / "dist"
    exported_dir = ws.export_docs("default", output_path=export_dir)
    assert exported_dir.is_absolute()
    assert exported_dir.exists()
    assert exported_dir == (export_dir / "default_docs.html").resolve()

    ws.close()


def test_cli_docs_generate_and_delete(tmp_path: Path, monkeypatch):
    """Test det docs generate and det docs delete CLI commands."""
    monkeypatch.chdir(tmp_path)
    assert main(["init", str(tmp_path)]) == 0

    # CLI generate with pipeline name
    ret = main(["docs", "generate", "default"])
    assert ret == 0
    docs_file = tmp_path / "pipelines" / "default" / "docs" / "index.html"
    assert docs_file.resolve().exists()

    # CLI delete
    ret_del = main(["docs", "delete", "default"])
    assert ret_del == 0
    assert not docs_file.exists()

    # CLI delete non-existent docs
    ret_del_again = main(["docs", "delete", "default"])
    assert ret_del_again == 0


def test_cli_docs_export(tmp_path: Path, monkeypatch):
    """Test det docs export CLI command with default and custom outputs."""
    monkeypatch.chdir(tmp_path)
    assert main(["init", str(tmp_path)]) == 0

    # Default export (creates ./default_docs.html)
    ret = main(["docs", "export", "default"])
    assert ret == 0
    default_export = tmp_path / "default_docs.html"
    assert default_export.resolve().exists()
    assert "<!DOCTYPE html>" in default_export.read_text(encoding="utf-8")

    # Custom export path
    custom_target = tmp_path / "out" / "my_report.html"
    ret_custom = main(["docs", "export", "default", "--output", str(custom_target)])
    assert ret_custom == 0
    assert custom_target.resolve().exists()


def test_cli_docs_open_browser_and_serve(tmp_path: Path, monkeypatch):
    """Test det docs open in direct browser mode and HTTP serve mode."""
    monkeypatch.chdir(tmp_path)
    assert main(["init", str(tmp_path)]) == 0

    # Test open direct in browser (mock webbrowser.open)
    with patch("webbrowser.open") as mock_open:
        ret = main(["docs", "open", "default"])
        assert ret == 0
        mock_open.assert_called_once()
        called_url = mock_open.call_args[0][0]
        assert called_url.startswith("file://")
        assert "default" in called_url

    # Test open with --serve and --no-browser
    with patch("det.docs.server.DocsServer.start_server") as mock_start:
        ret_serve = main(["docs", "open", "default", "--serve", "--port", "9999", "--no-browser"])
        assert ret_serve == 0
        mock_start.assert_called_once()
        args, kwargs = mock_start.call_args
        assert kwargs["port"] == 9999 or args[1] == 9999


def test_cli_pipeline_docs_alias(tmp_path: Path, monkeypatch):
    """Test det pipeline docs <name> alias."""
    monkeypatch.chdir(tmp_path)
    assert main(["init", str(tmp_path)]) == 0

    ret = main(["pipeline", "docs", "default"])
    assert ret == 0
    assert (tmp_path / "pipelines" / "default" / "docs" / "index.html").exists()

    # Non-existent pipeline fails cleanly
    ret_err = main(["pipeline", "docs", "phantom_pipe"])
    assert ret_err == 1

