"""Common HTTP helpers for sending JSON responses and extracting query params."""

from http.server import BaseHTTPRequestHandler
import json
from typing import Any


def send_json(
    handler: BaseHTTPRequestHandler,
    data: Any,
    status_code: int = 200,
) -> None:
    """Serialize data as JSON and write HTTP response with CORS headers."""
    payload = json.dumps(data).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(payload)


def send_error_json(
    handler: BaseHTTPRequestHandler,
    message: str,
    status_code: int = 400,
) -> None:
    """Send structured JSON error response."""
    send_json(handler, {"error": message, "status": "error"}, status_code=status_code)


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    """Parse JSON body payload from incoming HTTP request."""
    length_header = handler.headers.get("Content-Length", "0")
    try:
        content_length = int(length_header)
    except ValueError:
        return {}

    if content_length <= 0:
        return {}

    raw_body = handler.rfile.read(content_length).decode("utf-8")
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError:
        return {}
