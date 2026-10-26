"""Session state and active environment resolution for det."""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("det.session")

SESSION_DIR = Path.home() / ".det_session"
SESSION_FILE = SESSION_DIR / "session.json"
LEGACY_SESSION_FILE = Path.home() / ".det" / "session.json"


def get_session_file() -> Path:
    """Return path to user-level session state file."""
    return SESSION_FILE


def set_active_environment(path: Path) -> Path:
    """Store active det environment location for current and subsequent commands."""
    resolved = path.resolve()
    try:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        import datetime

        data = {
            "active_dir": str(resolved),
            "activated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        SESSION_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.debug("Could not write session file %s: %s", SESSION_FILE, exc)

    os.environ["DET_ACTIVE_DIR"] = str(resolved)
    return resolved


def get_stored_environment() -> Path | None:
    """Read stored environment from user session file if valid on disk."""
    for s_file in (SESSION_FILE, LEGACY_SESSION_FILE):
        if s_file.exists():
            try:
                data = json.loads(s_file.read_text(encoding="utf-8"))
                active = data.get("active_dir")
                if active:
                    p = Path(active).resolve()
                    if p.exists() and p.is_dir() and is_valid_environment(p):
                        return p
            except Exception as exc:
                logger.debug("Could not read session file %s: %s", s_file, exc)
    return None


def find_environment_in_parents(start_dir: Path | None = None) -> Path | None:
    """Walk up parent directory tree to find an existing det environment folder.

    Home directory is explicitly skipped unless it explicitly contains a catalog/connections.yaml or pipelines/.
    """
    current = (start_dir or Path.cwd()).resolve()
    home_dir = Path.home().resolve()
    for parent in [current, *current.parents]:
        if parent == home_dir:
            if (parent / "catalog" / "connections.yaml").exists() or (parent / "pipelines").exists():
                return parent
            continue
        if (
            (parent / "catalog" / "connections.yaml").exists()
            or (parent / "pipelines").exists()
            or (parent / "projects").exists()
            or ((parent / ".det").is_dir() and (parent / ".det" / "workspace.yaml").exists())
        ):
            return parent
    return None


def resolve_active_root(explicit_path: Path | str | None = None) -> Path:
    """Resolve active det root directory using priority order:
    1. Explicit path parameter (e.g. --dir / -C flag).
    2. Parent directory search from current working directory.
    3. Environment variable DET_ACTIVE_DIR / DET_HOME.
    4. Stored user session (~/.det_session/session.json).
    5. Fallback to current working directory.
    """
    if explicit_path:
        return Path(explicit_path).resolve()

    parent_root = find_environment_in_parents()
    if parent_root:
        return parent_root

    env_dir = os.environ.get("DET_ACTIVE_DIR") or os.environ.get("DET_HOME")
    if env_dir:
        p = Path(env_dir).resolve()
        if p.exists() and p.is_dir() and is_valid_environment(p):
            return p

    stored = get_stored_environment()
    if stored and stored.exists() and is_valid_environment(stored):
        return stored

    return Path.cwd().resolve()


def is_valid_environment(root: Path) -> bool:
    """Check if target path contains det environment markers."""
    resolved = root.resolve()
    if resolved == Path.home().resolve():
        return (
            (resolved / "catalog" / "connections.yaml").exists()
            or (resolved / "pipelines").exists()
        )
    return (
        (resolved / "catalog" / "connections.yaml").exists()
        or (resolved / "pipelines").exists()
        or (resolved / "projects").exists()
        or ((resolved / ".det").is_dir() and (resolved / ".det" / "workspace.yaml").exists())
    )
