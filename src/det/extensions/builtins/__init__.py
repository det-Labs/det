"""Built-in connectors package registering standard data sources."""

from det.extensions.builtins.delta_lake import DeltaLakeConnector
from det.extensions.builtins.excel import ExcelConnector
from det.extensions.builtins.filesystem import (
    CSVConnector,
    JSONConnector,
    ParquetConnector,
)
from det.extensions.builtins.httpfs import HTTPFSConnector
from det.extensions.builtins.huggingface import HuggingFaceConnector
from det.extensions.builtins.iceberg import IcebergConnector
from det.extensions.builtins.mssql import MSSQLConnector
from det.extensions.builtins.mysql import MySQLConnector
from det.extensions.builtins.onelake import OneLakeConnector
from det.extensions.builtins.postgres import PostgresConnector
from det.extensions.builtins.s3 import S3Connector
from det.extensions.builtins.sqlite import SQLiteConnector
from det.extensions.registry import ExtensionRegistry, global_registry

BUILTIN_CONNECTORS = [
    CSVConnector,
    ParquetConnector,
    JSONConnector,
    ExcelConnector,
    SQLiteConnector,
    PostgresConnector,
    MySQLConnector,
    MSSQLConnector,
    HTTPFSConnector,
    S3Connector,
    HuggingFaceConnector,
    IcebergConnector,
    DeltaLakeConnector,
    OneLakeConnector,
]


def register_builtins(registry: ExtensionRegistry) -> None:
    """Register all standard built-in connectors into the given registry."""
    for connector_cls in BUILTIN_CONNECTORS:
        registry.register(connector_cls)


# Automatically populate global registry with builtins
register_builtins(global_registry)

__all__ = [
    "BUILTIN_CONNECTORS",
    "CSVConnector",
    "DeltaLakeConnector",
    "ExcelConnector",
    "HTTPFSConnector",
    "HuggingFaceConnector",
    "IcebergConnector",
    "JSONConnector",
    "MSSQLConnector",
    "MySQLConnector",
    "OneLakeConnector",
    "ParquetConnector",
    "PostgresConnector",
    "S3Connector",
    "SQLiteConnector",
    "register_builtins",
]

