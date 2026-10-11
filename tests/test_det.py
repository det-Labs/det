import tomllib
from pathlib import Path

import det


def test_import():
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    expected = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    assert det.__version__ == expected

