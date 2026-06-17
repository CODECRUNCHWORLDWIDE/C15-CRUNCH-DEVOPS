"""Tiny webhook server for Week 9 Exercise 2.

Logs every POST /webhook payload to stdout as JSON.
"""
from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


LOG: logging.Logger = logging.getLogger("alert-webhook")


class WebhookHandler(BaseHTTPRequestHandler):
    """Receives Alertmanager webhook payloads."""

    def do_POST(self) -> None:  # noqa: N802
        length: int = int(self.headers.get("Content-Length", "0"))
        body: bytes = self.rfile.read(length) if length else b""
        try:
            payload: Any = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            payload = {"raw": body.decode("utf-8", errors="replace")}
        LOG.info("ALERT %s", json.dumps(payload, indent=2))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"received":true}')

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, fmt: str, *args: Any) -> None:
        LOG.info("%s - %s", self.client_address[0], fmt % args)


def serve(host: str, port: int) -> None:
    """Run the webhook server."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    httpd: HTTPServer = HTTPServer((host, port), WebhookHandler)
    LOG.info("webhook listening on %s:%d", host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == "__main__":
    serve("0.0.0.0", 5001)
