"""Small metric-emitter service for Week 9 Exercise 2.

Exposes:
    GET /work?ms=<int>   - sleeps for <ms> milliseconds then returns
    GET /metrics          - Prometheus exposition format
    GET /health           - liveness probe
"""
from __future__ import annotations

import logging
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


LOG: logging.Logger = logging.getLogger("emitter")

REQUESTS: Counter = Counter(
    "emitter_requests_total",
    "Total work requests served.",
    ["status"],
)

IN_FLIGHT: Gauge = Gauge(
    "emitter_in_flight",
    "Number of in-flight work requests.",
)

DURATION: Histogram = Histogram(
    "emitter_work_duration_seconds",
    "Distribution of work durations in seconds.",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


def parse_work_ms(query: str) -> int:
    """Extract the ms parameter from a query string. Default 50."""
    params: dict[str, list[str]] = parse_qs(query)
    raw: str = params.get("ms", ["50"])[0]
    try:
        return max(0, int(raw))
    except ValueError:
        return 50


class EmitterHandler(BaseHTTPRequestHandler):
    """HTTP handler for the metric-emitter service."""

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler convention)
        parsed: Any = urlparse(self.path)
        if parsed.path == "/metrics":
            self._serve_metrics()
        elif parsed.path == "/health":
            self._serve_health()
        elif parsed.path == "/work":
            self._serve_work(parsed.query)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:
        """Suppress default access log; emit through stdlib logging instead."""
        LOG.info("%s - %s", self.client_address[0], fmt % args)

    def _serve_metrics(self) -> None:
        body: bytes = generate_latest(REGISTRY)
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPE_LATEST)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_health(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def _serve_work(self, query: str) -> None:
        ms: int = parse_work_ms(query)
        IN_FLIGHT.inc()
        start: float = time.perf_counter()
        try:
            time.sleep(ms / 1000.0)
            DURATION.observe(time.perf_counter() - start)
            REQUESTS.labels(status="ok").inc()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"work":"done"}')
        except Exception:  # pragma: no cover
            REQUESTS.labels(status="error").inc()
            self.send_response(500)
            self.end_headers()
        finally:
            IN_FLIGHT.dec()


def serve(host: str, port: int) -> None:
    """Run the HTTP server until interrupted."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    httpd: HTTPServer = HTTPServer((host, port), EmitterHandler)
    LOG.info("emitter listening on %s:%d", host, port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        LOG.info("shutting down")
        httpd.server_close()


if __name__ == "__main__":
    serve("0.0.0.0", 8080)
