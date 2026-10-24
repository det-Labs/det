"""Routes package organizing modular REST API handlers for the Web IDE."""

from det.gui.routes.catalog_routes import CatalogRouteHandler
from det.gui.routes.common import read_json_body, send_error_json, send_json
from det.gui.routes.docs_routes import DocsRouteHandler
from det.gui.routes.explorer_routes import ExplorerRouteHandler
from det.gui.routes.pipeline_routes import PipelineRouteHandler
from det.gui.routes.status_routes import StatusRouteHandler
from det.gui.routes.ui_routes import UIRouteHandler

__all__ = [
    "CatalogRouteHandler",
    "DocsRouteHandler",
    "ExplorerRouteHandler",
    "PipelineRouteHandler",
    "StatusRouteHandler",
    "UIRouteHandler",
    "read_json_body",
    "send_error_json",
    "send_json",
]
