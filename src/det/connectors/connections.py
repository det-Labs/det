"""YAML-backed connections file management for reusable connections and credentials."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from filelock import FileLock
from ruamel.yaml import YAML

from det.catalog import config as catalog_config

MASKED_SECRET_PLACEHOLDER = "••••••••"
_custom_connections_path: Path | None = None


def set_connections_path(path: Path | str | None) -> None:
    global _custom_connections_path
    _custom_connections_path = Path(path).expanduser().resolve() if path else None


def get_connections_path() -> Path:
    if _custom_connections_path is not None:
        return _custom_connections_path
    return catalog_config.CONFIG_DIR / "connections.yaml"


def __getattr__(name: str) -> Any:
    if name == "CONNECTIONS_FILE":
        return get_connections_path()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")




def _yaml_parser() -> YAML:
    yaml_obj = YAML(typ="safe")
    yaml_obj.default_flow_style = False
    return yaml_obj


def _load_all_connections_unlocked(path: Path) -> dict[str, dict[str, Any]]:

    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as stream:
            data = _yaml_parser().load(stream)
            if isinstance(data, dict):
                conns = data.get("connections", {})
                if isinstance(conns, dict):
                    return conns
            return {}
    except Exception:
        return {}


def load_all_connections() -> dict[str, dict[str, Any]]:
    path = get_connections_path()
    if not path.is_file():
        return {}
    lock_path = Path(str(path) + ".lock")
    try:
        with (
            FileLock(str(lock_path), timeout=5),
            path.open("r", encoding="utf-8") as stream,
        ):
            data = _yaml_parser().load(stream)
            if isinstance(data, dict):
                conns = data.get("connections", {})
                if isinstance(conns, dict):
                    return conns
    except Exception:
        pass
    return {}



def get_connection(connection_id: str) -> dict[str, Any] | None:
    all_conns = load_all_connections()
    return all_conns.get(connection_id)


def get_connection_credentials(connection_id: str) -> dict[str, Any]:
    conn = get_connection(connection_id)
    if conn and isinstance(conn.get("credentials"), dict):
        return conn["credentials"]
    return {}


def save_connection(
    connection_id: str,
    name: str,
    connector: str,
    config: dict[str, Any],
    credentials: dict[str, Any],
    description: str = "",
) -> None:
    path = get_connections_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = Path(str(path) + ".lock")
    temp_path = path.with_name(f"{path.name}.tmp")

    with FileLock(str(lock_path), timeout=10):
        all_conns = _load_all_connections_unlocked(path)
        all_conns[connection_id] = {
            "id": connection_id,
            "name": name,
            "connector": connector,
            "config": {k: v for k, v in config.items() if v is not None},
            "credentials": {k: v for k, v in credentials.items() if v is not None},
            "description": description or "",
        }
        try:
            with temp_path.open("w", encoding="utf-8") as stream:
                _yaml_parser().dump({"connections": all_conns}, stream)
            temp_path.replace(path)
        finally:
            if temp_path.exists():
                temp_path.unlink()


def delete_connection(connection_id: str) -> None:
    path = get_connections_path()
    if not path.is_file():
        return
    lock_path = Path(str(path) + ".lock")
    temp_path = path.with_name(f"{path.name}.tmp")

    with FileLock(str(lock_path), timeout=10):
        all_conns = _load_all_connections_unlocked(path)
        if connection_id in all_conns:
            del all_conns[connection_id]
            try:
                with temp_path.open("w", encoding="utf-8") as stream:
                    _yaml_parser().dump({"connections": all_conns}, stream)
                temp_path.replace(path)
            finally:
                if temp_path.exists():
                    temp_path.unlink()



def list_connections(mask_secrets: bool = True) -> list[dict[str, Any]]:
    all_conns = load_all_connections()
    results: list[dict[str, Any]] = []
    for cid, conn in all_conns.items():
        item = {
            "id": cid,
            "name": conn.get("name") or cid,
            "connector": conn.get("connector") or "",
            "description": conn.get("description") or "",
            "config": dict(conn.get("config") or {}),
            "has_credentials": bool(conn.get("credentials")),
        }
        if not mask_secrets:
            item["credentials"] = dict(conn.get("credentials") or {})
        results.append(item)
    return results


def mask_secret_value(value: Any) -> str:
    if value is not None and str(value).strip():
        return MASKED_SECRET_PLACEHOLDER
    return ""


def mask_credentials_dict(credentials: dict[str, Any], secret_keys: set[str]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for k, v in credentials.items():
        if k in secret_keys and v:
            masked[k] = MASKED_SECRET_PLACEHOLDER
        else:
            masked[k] = v
    return masked


def merge_incoming_credentials(
    connection_id: str,
    incoming: dict[str, Any],
    secret_keys: set[str],
) -> dict[str, Any]:
    existing = get_connection_credentials(connection_id)
    merged = dict(existing)
    for k, v in incoming.items():
        if k in secret_keys:
            if v == MASKED_SECRET_PLACEHOLDER or v is None or v == "":
                pass
            else:
                merged[k] = v
        else:
            merged[k] = v
    return merged


# Backwards compatibility aliases
get_source_credentials = get_connection_credentials
def has_source_credentials(sid: str) -> bool:
    return bool(get_connection_credentials(sid))


def save_source_credentials(sid: str, creds: Any) -> None:
    return None
delete_source_credentials = delete_connection
