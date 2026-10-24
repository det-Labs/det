"""DuckDB session lifecycle management and configuration."""

import logging
import threading
from typing import Any
import duckdb

from det.engine.base import BaseSessionManager, EngineConfig

logger = logging.getLogger(__name__)


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
        con = duckdb.connect(database=config.database, config=cfg_dict)

        # Default core extensions to load
        core_exts = ["parquet", "json"] + [
            ext for ext in config.extensions if ext not in ("parquet", "json")
        ]
        self._load_extensions(con, core_exts)
        return con

    def _load_extensions(
        self, con: duckdb.DuckDBPyConnection, extensions: list[str]
    ) -> None:
        """Load requested extensions, logging any failures without crashing."""
        for ext in extensions:
            try:
                con.load_extension(ext)
            except Exception as exc:
                logger.warning("Failed to load DuckDB extension '%s': %s", ext, exc)

