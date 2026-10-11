"""Connector exceptions and error definitions."""

from __future__ import annotations

from typing import Any


class ConnectorError(Exception):
    """Base error for connector operations."""

    def __init__(self, message: str, connector_id: str = "", details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.connector_id = connector_id
        self.details = details or {}


class ConnectionTestError(ConnectorError):
    """Failed connection test."""


class DiscoveryError(ConnectorError):
    """Failed object / table discovery."""


class SchemaInferenceError(ConnectorError):
    """Failed schema inference."""


class PreviewError(ConnectorError):
    """Failed data preview."""


class ConnectorValidationError(ConnectorError):
    """Invalid connector configuration parameters."""
