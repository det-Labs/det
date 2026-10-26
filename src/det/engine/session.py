"""DuckDB session lifecycle management and configuration."""

import logging
import threading
from typing import Any
import duckdb

from det.engine.base import BaseSessionManager, EngineConfig

logger = logging.getLogger(__name__)


def load_or_install_extension(con: Any, ext: str) -> bool:
    """Load a DuckDB extension, attempting to install it first if missing."""
    try:
        con.load_extension(ext)
        return True
    except Exception:
        try:
            if hasattr(con, "install_extension"):
                con.install_extension(ext)
            else:
                con.execute(f"INSTALL {ext};")
            con.load_extension(ext)
            return True
        except Exception as exc:
            logger.debug("Failed to load/install extension '%s': %s", ext, exc)
            return False


class DuckDBSessionManager(BaseSessionManager):
    """Manages a singleton-style DuckDB connection lifecycle."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self._config: EngineConfig = config or EngineConfig()
        self._connection: duckdb.DuckDBPyConnection | None = None
        self._lock = threading.Lock()

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Retrieve or initialize the active DuckDB connection."""
        if self._connection is not None:
            return self._connection

        with self._lock:
            if self._connection is None:
                self._connection = self._initialize_connection(self._config)
            return self._connection

    def close_connection(self) -> None:
        """Safely terminate and clear the active DuckDB connection."""
        with self._lock:
            if self._connection is not None:
                try:
                    self._connection.close()
                except Exception as exc:
                    logger.warning("Error while closing DuckDB connection: %s", exc)
                finally:
                    self._connection = None

    def _build_config_dict(self, config: EngineConfig) -> dict[str, Any]:
        """Build dictionary of DuckDB connection configuration options."""
        cfg: dict[str, Any] = {}
        if config.threads is not None:
            cfg["threads"] = config.threads
        if config.memory_limit is not None:
            cfg["max_memory"] = config.memory_limit
        return cfg

    def _initialize_connection(
        self, config: EngineConfig
    ) -> duckdb.DuckDBPyConnection:
        """Instantiate DuckDB connection and load configured extensions."""
        cfg_dict = self._build_config_dict(config)
        try:
            con = duckdb.connect(database=config.database, config=cfg_dict)
        except Exception as exc:
            # Handle database file locking gracefully (e.g. concurrent CLI commands while GUI is running)
            if config.database != ":memory:" and "used by another process" in str(exc).lower() or "io error" in str(exc).lower():
                logger.info("Database file '%s' locked by another process; opening read-only or in-memory session.", config.database)
                try:
                    con = duckdb.connect(database=config.database, read_only=True, config=cfg_dict)
                except Exception:
                    con = duckdb.connect(database=":memory:", config=cfg_dict)
            else:
                raise

        # Enable on-demand auto-installation for extensions required by queries/connectors
        try:
            con.execute("SET autoinstall_known_extensions = true;")
            con.execute("SET autoload_known_extensions = true;")
        except Exception as exc:
            logger.debug("Auto-install extension settings note: %s", exc)

        # Default core extensions to load: only built-in formats (parquet, json)
        core_exts = ["parquet", "json"] + [
            ext for ext in config.extensions if ext not in ("parquet", "json")
        ]
        self._load_extensions(con, core_exts)
        return con

    def _load_extensions(
        self, con: duckdb.DuckDBPyConnection, extensions: list[str]
    ) -> None:
        """Load requested extensions, installing on-demand if necessary, without crashing."""
        for ext in extensions:
            load_or_install_extension(con, ext)

