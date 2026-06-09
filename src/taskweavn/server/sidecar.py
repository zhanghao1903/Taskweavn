"""Stdlib local HTTP binding for the Plato sidecar transport."""

from __future__ import annotations

import json
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol, cast
from urllib.parse import urlsplit

from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import ApiError

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_DEFAULT_ALLOWED_METHODS = "GET, POST, PATCH, OPTIONS"
_DEFAULT_ALLOWED_HEADERS = "authorization, content-type, accept, x-request-id"
_CLIENT_DISCONNECT_ERRORS = (
    BrokenPipeError,
    ConnectionAbortedError,
    ConnectionResetError,
)


class SidecarTransport(Protocol):
    """Transport boundary consumed by the stdlib sidecar server."""

    def handle(self, request: HttpApiRequest) -> HttpApiResponse: ...


@dataclass(frozen=True)
class LocalSidecarConfig:
    """Runtime options for the local stdlib sidecar server."""

    host: str = "127.0.0.1"
    port: int = 0
    allow_remote: bool = False
    allowed_origin_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "::1")
    allow_null_origin: bool = True


class LocalSidecarServer:
    """Small loopback-only stdlib HTTP server for Plato UI development."""

    def __init__(
        self,
        transport: SidecarTransport,
        *,
        config: LocalSidecarConfig | None = None,
    ) -> None:
        self._config = config or LocalSidecarConfig()
        if not self._config.allow_remote and self._config.host not in _LOOPBACK_HOSTS:
            raise ValueError("LocalSidecarServer binds to loopback hosts by default")
        self._server = _SidecarHTTPServer(
            (self._config.host, self._config.port),
            _SidecarRequestHandler,
            transport=transport,
            config=self._config,
        )
        self._thread: threading.Thread | None = None

    @property
    def server_address(self) -> tuple[str, int]:
        return cast(tuple[str, int], self._server.server_address)

    @property
    def base_url(self) -> str:
        host, port = self.server_address
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"http://{host}:{port}"

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def start_in_thread(self) -> threading.Thread:
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._thread = threading.Thread(
            target=self.serve_forever,
            name="taskweavn-local-sidecar",
            daemon=True,
        )
        self._thread.start()
        return self._thread

    def shutdown(self) -> None:
        self._server.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def server_close(self) -> None:
        self._server.server_close()

    def __enter__(self) -> LocalSidecarServer:
        self.start_in_thread()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.shutdown()
        self.server_close()


class _SidecarHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class: type[BaseHTTPRequestHandler],
        *,
        transport: SidecarTransport,
        config: LocalSidecarConfig,
    ) -> None:
        super().__init__(server_address, request_handler_class)
        self.transport = transport
        self.config = config

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Suppress expected client disconnect tracebacks.

        ``BaseHTTPRequestHandler`` can raise before it reaches our request
        methods, for example while reading the request line after a browser
        closes or resets a socket. The stdlib default is to print a traceback;
        for a local browser sidecar this is normal transport churn, not a
        server failure.
        """
        _, exc, _ = sys.exc_info()
        if isinstance(exc, _CLIENT_DISCONNECT_ERRORS):
            return
        super().handle_error(request, client_address)


class _SidecarRequestHandler(BaseHTTPRequestHandler):
    server: _SidecarHTTPServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()

    def do_OPTIONS(self) -> None:
        cors_headers = _cors_headers(self.headers.get("origin"), self.server.config)
        if cors_headers is None:
            self._send_response(_origin_denied_response())
            return
        self._send_response(
            HttpApiResponse(
                status_code=204,
                headers={
                    **cors_headers,
                    "access-control-allow-headers": _DEFAULT_ALLOWED_HEADERS,
                    "access-control-allow-methods": _DEFAULT_ALLOWED_METHODS,
                    "access-control-max-age": "600",
                    "content-type": "text/plain",
                },
                body="",
            )
        )

    def log_message(self, format: str, *args: object) -> None:
        return

    def _handle(self) -> None:
        cors_headers = _cors_headers(self.headers.get("origin"), self.server.config)
        if cors_headers is None:
            self._send_response(_origin_denied_response())
            return

        body_or_response = self._read_json_body()
        if isinstance(body_or_response, HttpApiResponse):
            self._send_response(body_or_response, extra_headers=cors_headers)
            return

        request = HttpApiRequest(
            method=self.command,
            path=self.path,
            headers={key: value for key, value in self.headers.items()},
            body=body_or_response,
        )
        response = self.server.transport.handle(request)
        self._send_response(response, extra_headers=cors_headers)

    def _read_json_body(self) -> dict[str, Any] | None | HttpApiResponse:
        raw_length = self.headers.get("content-length")
        if raw_length is None:
            return None
        try:
            length = int(raw_length)
        except ValueError:
            return _bad_request_response("invalid Content-Length header")
        if length == 0:
            return None
        raw_body = self.rfile.read(length)
        try:
            decoded = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _bad_request_response("request body must be valid JSON")
        if not isinstance(decoded, dict):
            return _bad_request_response("request body must be a JSON object")
        return cast(dict[str, Any], decoded)

    def _send_response(
        self,
        response: HttpApiResponse,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        headers = dict(response.headers)
        headers.update(extra_headers or {})
        body_bytes = _response_body_bytes(response)
        headers.setdefault("content-length", str(len(body_bytes)))
        try:
            self.send_response(response.status_code)
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD" and body_bytes:
                self.wfile.write(body_bytes)
        except _CLIENT_DISCONNECT_ERRORS:
            # Browsers and dev servers can cancel in-flight requests during
            # navigation, reload, or React query retries. This is not a
            # sidecar failure; suppress the stdlib handler traceback.
            return


def _response_body_bytes(response: HttpApiResponse) -> bytes:
    body = response.body
    content_type = response.headers.get("content-type", "")
    if response.status_code == 204:
        return b""
    if isinstance(body, str):
        return body.encode("utf-8")
    if content_type.startswith("application/json"):
        return json.dumps(body, separators=(",", ":")).encode("utf-8")
    return str(body).encode("utf-8")


def _cors_headers(origin: str | None, config: LocalSidecarConfig) -> dict[str, str] | None:
    if origin is None:
        return {}
    if origin == "null" and config.allow_null_origin:
        return {"access-control-allow-origin": "null", "vary": "origin"}
    parsed = urlsplit(origin)
    if parsed.hostname in config.allowed_origin_hosts:
        return {"access-control-allow-origin": origin, "vary": "origin"}
    return None


def _bad_request_response(message: str) -> HttpApiResponse:
    return _json_error_response(
        status_code=400,
        error=ApiError(code="bad_request", message=message),
    )


def _origin_denied_response() -> HttpApiResponse:
    return _json_error_response(
        status_code=403,
        error=ApiError(code="permission_denied", message="origin is not allowed"),
    )


def _json_error_response(*, status_code: int, error: ApiError) -> HttpApiResponse:
    return HttpApiResponse(
        status_code=status_code,
        headers={"content-type": "application/json"},
        body={
            "requestId": None,
            "ok": False,
            "data": None,
            "error": error.model_dump(mode="json"),
        },
    )


__all__ = [
    "LocalSidecarConfig",
    "LocalSidecarServer",
    "SidecarTransport",
]
