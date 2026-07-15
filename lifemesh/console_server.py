from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from .config import LifemeshConfig
from .console_service import ConsoleError, ConsoleService


LOOPBACK_HOST = "127.0.0.1"
MAX_BODY_BYTES = 64 * 1024
ASSET_DIR = Path(__file__).with_name("console_ui")
ENTRY_ASSETS = {
    "/": "index.html",
    "/index.html": "index.html",
}


class ConsoleHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], service: ConsoleService) -> None:
        super().__init__(address, ConsoleRequestHandler)
        self.service = service
        self.allowed_host = f"{LOOPBACK_HOST}:{self.server_port}"
        self.allowed_origin = f"http://{self.allowed_host}"


class ConsoleRequestHandler(BaseHTTPRequestHandler):
    server: ConsoleHTTPServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        if not self._valid_host():
            return
        parsed = urlsplit(self.path)
        try:
            if parsed.path == "/api/overview":
                self._json(HTTPStatus.OK, self.server.service.overview())
            elif parsed.path == "/api/records":
                query = parse_qs(parsed.query)
                domain = _first(query, "domain", "")
                limit = int(_first(query, "limit", "80"))
                self._json(HTTPStatus.OK, {"domain": domain, "items": self.server.service.records(domain, limit=limit)})
            elif parsed.path.startswith("/api/records/"):
                parts = parsed.path.split("/", 4)
                if len(parts) != 5:
                    raise ConsoleError("record route requires domain and id")
                self._json(HTTPStatus.OK, self.server.service.record(parts[3], unquote(parts[4])))
            elif parsed.path == "/api/search":
                query = parse_qs(parsed.query)
                self._json(
                    HTTPStatus.OK,
                    self.server.service.search(
                        _first(query, "q", ""),
                        limit=int(_first(query, "limit", "30")),
                    ),
                )
            elif parsed.path == "/api/graph":
                query = parse_qs(parsed.query)
                self._json(
                    HTTPStatus.OK,
                    self.server.service.graph(limit=int(_first(query, "limit", "40"))),
                )
            elif parsed.path == "/api/timeline":
                query = parse_qs(parsed.query)
                self._json(
                    HTTPStatus.OK,
                    self.server.service.timeline(limit=int(_first(query, "limit", "120"))),
                )
            elif parsed.path in ENTRY_ASSETS or parsed.path.startswith("/assets/"):
                self._asset(parsed.path)
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
        except (ConsoleError, ValueError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Console request failed"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        if not self._valid_host() or not self._valid_origin():
            return
        parsed = urlsplit(self.path)
        if parsed.path != "/api/bundles":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            payload = self._read_json()
            self._json(HTTPStatus.OK, self.server.service.assemble_bundle(payload))
        except ConsoleError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Bundle assembly failed"})

    def log_message(self, _format: str, *_args: Any) -> None:
        # Query strings can contain personal search text. Do not echo requests.
        return

    def _valid_host(self) -> bool:
        if self.headers.get("Host") == self.server.allowed_host:
            return True
        self._json(HTTPStatus.FORBIDDEN, {"error": "Host rejected"})
        return False

    def _valid_origin(self) -> bool:
        if self.headers.get("Origin") == self.server.allowed_origin:
            return True
        self._json(HTTPStatus.FORBIDDEN, {"error": "Origin rejected"})
        return False

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ConsoleError("Invalid Content-Length") from exc
        if length < 1 or length > MAX_BODY_BYTES:
            raise ConsoleError("Request body must be between 1 byte and 64 KiB")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConsoleError("Request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ConsoleError("Request body must be a JSON object")
        return payload

    def _json(self, status: HTTPStatus, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _asset(self, request_path: str) -> None:
        relative_path = ENTRY_ASSETS.get(request_path, request_path.lstrip("/"))
        asset_root = ASSET_DIR.resolve()
        asset_path = (asset_root / relative_path).resolve()
        if not asset_path.is_relative_to(asset_root) or not asset_path.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "Console asset missing"})
            return
        body = asset_path.read_bytes()
        content_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type == "application/javascript":
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )


def create_console_server(config: LifemeshConfig, *, port: int = 0) -> ConsoleHTTPServer:
    if port < 0 or port > 65535:
        raise ConsoleError("Console port must be between 0 and 65535")
    return ConsoleHTTPServer((LOOPBACK_HOST, port), ConsoleService(config))


def run_console(config: LifemeshConfig, *, port: int = 0, open_browser: bool = True) -> None:
    server = create_console_server(config, port=port)
    url = server.allowed_origin
    print(f"LifeMesh Console: {url}")
    print("Read-only local session. Press Ctrl-C to stop.")
    if open_browser:
        threading.Timer(0.15, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _first(query: dict[str, list[str]], key: str, default: str) -> str:
    values = query.get(key)
    return values[0] if values else default
