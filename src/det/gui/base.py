"""Base contracts, UI module definitions, and theme models for the Web IDE."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class UIModule:
    """Represents a top-level navigational tab or tool in the Web IDE."""

    id: str
    title: str
    icon: str = "folder"
    order: int = 100
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert module definition to dictionary for frontend rendering."""
        return {
            "id": self.id,
            "title": self.title,
            "icon": self.icon,
            "order": self.order,
            "description": self.description,
        }


@dataclass(frozen=True)
class UITheme:
    """Custom color theme definition customizable by extensions."""

    id: str
    name: str
    css_variables: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert theme to dictionary for frontend CSS variable injection."""
        return {
            "id": self.id,
            "name": self.name,
            "variables": dict(self.css_variables),
        }


class BaseRouteHandler(ABC):
    """Abstract interface for modular HTTP request route handlers."""

    @abstractmethod
    def handle_get(self, handler: BaseHTTPRequestHandler, path: str) -> bool:
        """Handle GET requests. Returns True if handled, False otherwise."""
        pass

    @abstractmethod
    def handle_post(
        self, handler: BaseHTTPRequestHandler, path: str, body: dict[str, Any]
    ) -> bool:
        """Handle POST requests. Returns True if handled, False otherwise."""
        pass


class BaseGUIServer(ABC):
    """Abstract interface for the Web IDE HTTP server."""

    @abstractmethod
    def start(self, port: int = 8080, blocking: bool = True) -> None:
        """Start the HTTP server on the specified port."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Terminate the running HTTP server."""
        pass
