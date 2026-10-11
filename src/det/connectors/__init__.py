"""Connector module exposing contract, registry, and registered connectors."""

from __future__ import annotations

from det.connectors.apis.graphql_connector import GraphQLConnector
from det.connectors.apis.rest_api_connector import RestApiConnector
from det.connectors.contract import (
    BaseConnector,
    ConfigField,
    ConnectionTestResult,
    ConnectorGroup,
    DiscoveredObject,
    FieldType,
    PreviewResult,
    SchemaResult,
)
from det.connectors.databases.postgres_connector import PostgresConnector
from det.connectors.databases.sqlite_connector import SQLiteConnector
from det.connectors.databases.sqlserver_connector import SQLServerConnector
from det.connectors.errors import (
    ConnectionTestError,
    ConnectorError,
    ConnectorValidationError,
    DiscoveryError,
    PreviewError,
    SchemaInferenceError,
)
from det.connectors.files.csv_connector import CSVConnector
from det.connectors.files.excel_connector import ExcelConnector
from det.connectors.files.json_connector import JSONConnector
from det.connectors.files.parquet_connector import ParquetConnector
from det.connectors.files.xml_connector import XMLConnector
from det.connectors.registry import (
    ConnectorRegistry,
    discover_and_register_from_directory,
    get_connector,
    get_registry,
    list_connectors,
    list_connectors_grouped,
    list_connectors_specs,
    register_connector,
)

# Register connectors incrementally: Files (CSV, Parquet, Excel, JSON, XML), Databases (SQLite, PostgreSQL, SQL Server), APIs (REST API, GraphQL).
register_connector(CSVConnector())
register_connector(ParquetConnector())
register_connector(ExcelConnector())
register_connector(JSONConnector())
register_connector(XMLConnector())
register_connector(SQLiteConnector())
register_connector(PostgresConnector())
register_connector(SQLServerConnector())
register_connector(RestApiConnector())
register_connector(GraphQLConnector())

__all__ = [
    "BaseConnector",
    "CSVConnector",
    "ConfigField",
    "ConnectionTestError",
    "ConnectionTestResult",
    "ConnectorError",
    "ConnectorGroup",
    "ConnectorRegistry",
    "ConnectorValidationError",
    "DiscoveredObject",
    "DiscoveryError",
    "ExcelConnector",
    "FieldType",
    "GraphQLConnector",
    "JSONConnector",
    "ParquetConnector",
    "PostgresConnector",
    "PreviewError",
    "PreviewResult",
    "RestApiConnector",
    "SQLServerConnector",
    "SQLiteConnector",
    "SchemaInferenceError",
    "SchemaResult",
    "XMLConnector",
    "discover_and_register_from_directory",
    "get_connector",
    "get_registry",
    "list_connectors",
    "list_connectors_grouped",
    "list_connectors_specs",
    "register_connector",
]
