"""Extensions and connectors subsystem for pluggable data federation."""

from det.extensions.base import BaseConnector, ConnectorField, FieldType
from det.extensions.entrypoint_loader import EntrypointExtensionLoader
from det.extensions.local_loader import LocalExtensionLoader
from det.extensions.registry import ExtensionRegistry, global_registry
# Ensure builtins are imported and registered
import det.extensions.builtins  # noqa: F401

__all__ = [
    "BaseConnector",
    "ConnectorField",
    "EntrypointExtensionLoader",
    "ExtensionRegistry",
    "FieldType",
    "LocalExtensionLoader",
    "global_registry",
]

