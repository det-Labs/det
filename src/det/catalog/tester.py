"""Connection health checking and latency measurement."""

import logging
import time
import duckdb

from det.catalog.base import (
    BaseConnectionTester,
    ConnectionTestResult,
    ConnectionTestStatus,
    ConnectionTier,
)
from det.catalog.definitions import ConnectionDefinition
from det.engine.session import load_or_install_extension

logger = logging.getLogger(__name__)


class ConnectionTester(BaseConnectionTester):
    """Executes live heartbeat probes on connections using DuckDB."""

    def test_connection(
        self, con: duckdb.DuckDBPyConnection, conn_def: ConnectionDefinition
    ) -> ConnectionTestResult:
        """Probe an active connection and return result with latency in ms."""
        start_time = time.perf_counter()
        try:
            self._probe(con, conn_def)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ConnectionTestResult(
                status=ConnectionTestStatus.SUCCESS,
                latency_ms=round(elapsed_ms, 2),
                error_message=None,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = str(exc)
            logger.warning("Connection test failed for '%s': %s", conn_def.name, err_msg)
            return ConnectionTestResult(
                status=ConnectionTestStatus.FAILED,
                latency_ms=round(elapsed_ms, 2),
                error_message=err_msg,
            )

    def _probe(
        self, con: duckdb.DuckDBPyConnection, conn_def: ConnectionDefinition
    ) -> None:
        """Execute mount and probe queries for entity or database tier."""
        conn_type = conn_def.type.lower()
        if conn_type in ("azure", "abfss", "onelake"):
            load_or_install_extension(con, "azure")
        elif conn_type in ("s3", "aws", "gcs", "gs"):
            load_or_install_extension(con, "httpfs")
        elif conn_type in ("delta", "delta_lake"):
            load_or_install_extension(con, "delta")

        if hasattr(conn_def, "get_secret_sql"):
            from det.engine.secrets import SecretResolver
            secret_sql = conn_def.get_secret_sql(resolver=SecretResolver())
            if secret_sql:
                try:
                    con.execute(secret_sql)
                except Exception as exc:
                    logger.debug("Test probe secret configuration note: %s", exc)

        try:
            mount_sql = conn_def.get_mount_sql()
            con.execute(mount_sql)
        except Exception as exc:
            err = str(exc).lower()
            if "already exists" not in err and "already attached" not in err:
                raise

        # Run heartbeat query
        if conn_def.tier == ConnectionTier.ENTITY:
            probe_sql = f"SELECT 1 FROM {conn_def.name} LIMIT 1"
            con.execute(probe_sql).fetchall()
        else:
            probe_sql = f"SHOW TABLES FROM {conn_def.name}"
            con.execute(probe_sql).fetchall()

