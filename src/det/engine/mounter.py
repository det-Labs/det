"""Catalog mounting and virtual view binding for DuckDB."""

import logging
import re
import duckdb

from det.engine.base import BaseMounter, MountReport, Mountable

logger = logging.getLogger(__name__)

# Valid SQL identifier: starts with letter or underscore, followed by letters, numbers, or underscores
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class CatalogMounter(BaseMounter):
    """Mounts databases and binds entity views into a DuckDB session."""

    def bind_entity_view(
        self, con: duckdb.DuckDBPyConnection, name: str, select_sql: str
    ) -> None:
        """Bind an entity connection as a virtual view (CREATE OR REPLACE VIEW)."""
        valid_name = self._validate_identifier(name)
        sql = f"CREATE OR REPLACE VIEW {valid_name} AS {select_sql}"
        logger.debug("Binding entity view: %s", sql)
        con.execute(sql)

    def mount_database(
        self,
        con: duckdb.DuckDBPyConnection,
        name: str,
        conn_str: str,
        db_type: str | None = None,
    ) -> None:
        """Attach an external database catalog via DuckDB ATTACH."""
        valid_name = self._validate_identifier(name)
        type_clause = f" (TYPE {db_type.upper()})" if db_type else ""
        escaped_conn = conn_str.replace("'", "''")
        sql = f"ATTACH '{escaped_conn}' AS {valid_name}{type_clause}"
        logger.debug("Attaching database: %s", sql)
        con.execute(sql)

    def mount_item(
        self, con: duckdb.DuckDBPyConnection, item: Mountable
    ) -> None:
        """Mount a single Mountable object by executing its generated SQL."""
        self._validate_identifier(item.name)

        # 1. Dynamically load extensions if needed
        conn_type = getattr(item, "type", "").lower()
        if conn_type in ("azure", "abfss", "onelake"):
            try:
                con.load_extension("azure")
            except Exception as exc:
                logger.debug("Optional extension 'azure' load notice: %s", exc)
        elif conn_type in ("s3", "aws"):
            try:
                con.load_extension("aws")
            except Exception as exc:
                logger.debug("Optional extension 'aws' load notice: %s", exc)
        elif conn_type in ("delta", "delta_lake"):
            try:
                con.load_extension("delta")
            except Exception as exc:
                logger.debug("Optional extension 'delta' load notice: %s", exc)

        # 2. Configure DuckDB Secrets if credentials or cloud configs exist
        if hasattr(item, "get_secret_sql"):
            from det.engine.secrets import SecretResolver
            secret_sql = item.get_secret_sql(resolver=SecretResolver())
            if secret_sql:
                logger.debug("Configuring secret for item '%s': %s", item.name, secret_sql)
                try:
                    con.execute(secret_sql)
                except Exception as exc:
                    logger.warning("Secret configuration warning for '%s': %s", item.name, exc)

        # 3. Mount item
        sql = item.get_mount_sql()
        logger.debug("Mounting item '%s' (%s): %s", item.name, item.tier, sql)
        con.execute(sql)

    def mount_all(
        self, con: duckdb.DuckDBPyConnection, items: list[Mountable]
    ) -> MountReport:
        """Mount all items, isolating failures per item into a report."""
        report = MountReport()
        for item in items:
            try:
                self.mount_item(con, item)
                report.mounted.append(item.name)
            except Exception as exc:
                err_msg = str(exc)
                logger.warning("Failed to mount '%s': %s", item.name, err_msg)
                report.failed[item.name] = err_msg
        return report

    def _validate_identifier(self, identifier: str) -> str:
        """Validate and return safe SQL identifier or raise ValueError."""
        if not identifier or not IDENTIFIER_PATTERN.match(identifier):
            raise ValueError(
                f"Invalid SQL identifier: '{identifier}'. "
                "Must begin with a letter or underscore and contain only alphanumeric characters."
            )
        return identifier

