"""Shared fixtures: tiny local HTTP/TCP servers and a webhook capture server."""
from __future__ import annotations

import http.server
import socket
import threading

import pytest


def make_http_server(status=200, body=b"ok", fail_first=0):
    """Threading HTTP server on an ephemeral port.

    fail_first: how many initial requests return 503 before the server
    starts returning `status`/`body`.
    """

    class Handler(http.server.BaseHTTPRequestHandler):
        remaining = fail_first

        def do_GET(self):  # noqa: N802
            if type(self).remaining > 0:
                type(self).remaining -= 1
                self.send_response(503)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(b"degraded")))
                self.end_headers()
                self.wfile.write(b"degraded")
            else:
                self.send_response(status)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002
            pass

    return http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)


@pytest.fixture
def http_ok():
    server = make_http_server(status=200, body=b"ok")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def http_flaky():
    server = make_http_server(status=200, body=b"ok", fail_first=3)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def tcp_listener():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(8)

    def _accept_loop():
        while True:
            try:
                conn, _ = server.accept()
                conn.close()
            except OSError:
                return

    threading.Thread(target=_accept_loop, daemon=True).start()
    yield server
    server.close()


@pytest.fixture
def webhook_server():
    """HTTP server that captures POST bodies; yields (server, captured_list)."""
    captured = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            captured.append(self.rfile.read(length))
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args):  # noqa: A002
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, captured
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def free_port():
    """A port that is almost certainly closed (bind, note, close)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port
