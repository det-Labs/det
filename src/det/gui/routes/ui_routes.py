"""UI module registry, navigation manifest, and theme configuration endpoints."""

from http.server import BaseHTTPRequestHandler
from typing import Any

from det.gui.base import BaseRouteHandler, UIModule, UITheme
from det.gui.routes.common import send_json


class UIRouteHandler(BaseRouteHandler):
    """Provides dynamic UI navigation items and themes extensible via plugins."""

    def __init__(self) -> None:
        self._modules: list[UIModule] = self._get_default_modules()
        self._themes: list[UITheme] = self._get_default_themes()

    def register_module(self, module: UIModule) -> None:
        """Register a new UI module / navigational tab from an extension."""
        self._modules.append(module)
        self._modules.sort(key=lambda m: m.order)

    def register_theme(self, theme: UITheme) -> None:
        """Register a new UI theme from an extension."""
        self._themes.append(theme)

    def handle_get(self, handler: BaseHTTPRequestHandler, path: str) -> bool:
        """Serve /api/ui/manifest containing navigation tabs and theme definitions."""
        if path == "/api/ui/manifest":
            manifest = {
                "modules": [m.to_dict() for m in self._modules],
                "themes": [t.to_dict() for t in self._themes],
            }
            send_json(handler, manifest)
            return True
        return False

    def handle_post(
        self, handler: BaseHTTPRequestHandler, path: str, body: dict[str, Any]
    ) -> bool:
        """Handle POST requests for UI routes."""
        return False

    def _get_default_modules(self) -> list[UIModule]:
        """Return the standard built-in navigation modules."""
        return [
            UIModule(id="catalog", title="Catalog", icon="plug", order=10, description="Data source connections"),
            UIModule(id="pipelines", title="Pipelines", icon="git-merge", order=20, description="ETL DAG models & editor"),
            UIModule(id="monitoring", title="Monitoring", icon="activity", order=30, description="Quarantine & run telemetry"),
            UIModule(id="docs", title="Docs", icon="book-open", order=40, description="Interactive data dictionary"),
        ]

    def _get_default_themes(self) -> list[UITheme]:
        """Return default dark, light, and high contrast themes."""
        return [
            self._get_dark_theme(),
            self._get_light_theme(),
            self._get_contrast_theme(),
        ]

    def _get_dark_theme(self) -> UITheme:
        """Return midnight dark theme."""
        return UITheme(
            id="dark",
            name="Midnight Dark",
            css_variables={
                "--bg": "#090d16",
                "--surface": "#131b2e",
                "--surface-card": "#182238",
                "--border": "#23304c",
                "--text": "#f8fafc",
                "--muted": "#94a3b8",
                "--accent": "#3b82f6",
                "--accent-hover": "#2563eb",
                "--logo-color": "#f59e0b",
                "--badge-entity-bg": "rgba(59, 130, 246, 0.15)",
                "--badge-entity-text": "#60a5fa",
                "--badge-db-bg": "rgba(16, 185, 129, 0.15)",
                "--badge-db-text": "#34d399",
                "--badge-folder-bg": "rgba(255, 255, 255, 0.06)",
                "--badge-folder-text": "#cbd5e1",
                "--badge-item-bg": "#182238",
                "--badge-item-text": "#94a3b8",
                "--hover-bg": "rgba(255, 255, 255, 0.06)",
                "--success": "#10b981",
            },
        )

    def _get_light_theme(self) -> UITheme:
        """Return clean slate light theme."""
        return UITheme(
            id="light",
            name="Clean Slate",
            css_variables={
                "--bg": "#f8fafc",
                "--surface": "#ffffff",
                "--surface-card": "#f1f5f9",
                "--border": "#cbd5e1",
                "--text": "#0f172a",
                "--muted": "#475569",
                "--accent": "#2563eb",
                "--accent-hover": "#1d4ed8",
                "--badge-entity-bg": "rgba(37, 99, 235, 0.1)",
                "--badge-entity-text": "#1d4ed8",
                "--badge-db-bg": "rgba(16, 185, 129, 0.12)",
                "--badge-db-text": "#047857",
                "--badge-folder-bg": "#e2e8f0",
                "--badge-folder-text": "#334155",
                "--badge-item-bg": "#e2e8f0",
                "--badge-item-text": "#334155",
                "--hover-bg": "rgba(15, 23, 42, 0.06)",
                "--success": "#16a34a",
            },
        )

    def _get_contrast_theme(self) -> UITheme:
        """Return accessibility high contrast theme."""
        return UITheme(
            id="high_contrast",
            name="High Contrast",
            css_variables={
                "--bg": "#000000",
                "--surface": "#121212",
                "--surface-card": "#1e1e1e",
                "--border": "#3f3f46",
                "--text": "#ffffff",
                "--muted": "#d4d4d8",
                "--accent": "#22c55e",
                "--accent-hover": "#16a34a",
                "--badge-entity-bg": "#000000",
                "--badge-entity-text": "#60a5fa",
                "--badge-db-bg": "#000000",
                "--badge-db-text": "#4ade80",
                "--badge-folder-bg": "#1e1e1e",
                "--badge-folder-text": "#ffffff",
                "--badge-item-bg": "#1e1e1e",
                "--badge-item-text": "#ffffff",
                "--hover-bg": "rgba(255, 255, 255, 0.15)",
                "--success": "#4ade80",
            },
        )
