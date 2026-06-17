"""Greeter FastAPI service for Week 9 Exercise 3.

Endpoints:
    GET /api/hello?name=X  - returns a greeting
    GET /api/health        - liveness probe

Instrumented with OpenTelemetry:
    - FastAPI auto-instrumentation for HTTP spans
    - One manual span around compute_greeting
    - Traces exported via OTLP/gRPC to the OpenTelemetry Collector

This file is import-safe even if the OpenTelemetry packages are not installed:
the optional imports are guarded so `python3 -m py_compile greeter.py` works in
isolation. At runtime in the container, the packages from requirements.txt are
present and the conditional branches all take the real-instrumentation path.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any


LOG: logging.Logger = logging.getLogger("greeter")


def configure_tracing(service_name: str, otlp_endpoint: str) -> None:
    """Configure the OpenTelemetry TracerProvider for this process.

    Imports OpenTelemetry lazily so this file is import-safe without the SDK
    installed. At container runtime the SDK is present and the function runs
    its real path.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        LOG.warning("opentelemetry SDK not installed; tracing disabled")
        return

    resource: Any = Resource.create(
        {
            "service.name": service_name,
            "service.version": "0.1.0",
            "deployment.environment": os.environ.get("DEPLOY_ENV", "dev"),
        }
    )
    provider: Any = TracerProvider(resource=resource)
    exporter: Any = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=True,
    )
    processor: Any = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    LOG.info("tracing configured: service=%s endpoint=%s", service_name, otlp_endpoint)


def compute_greeting(name: str, locale: str) -> dict[str, Any]:
    """Compute a greeting for the given name and locale.

    Wrapped in a manual span so we can attribute the operation
    and slice the trace data by locale and name length.
    """
    try:
        from opentelemetry import trace as otel_trace
    except ImportError:
        # No SDK: just do the work, no span.
        time.sleep(0.005)
        message: str = render_message(name, locale)
        return {"greeting": message, "locale": locale}

    tracer: Any = otel_trace.get_tracer(__name__)
    with tracer.start_as_current_span("compute_greeting") as span:
        span.set_attribute("greeting.name_length", len(name))
        span.set_attribute("greeting.locale", locale)
        time.sleep(0.005)
        message_traced: str = render_message(name, locale)
        span.set_attribute("greeting.message_length", len(message_traced))
        return {"greeting": message_traced, "locale": locale}


def render_message(name: str, locale: str) -> str:
    """Render a locale-specific greeting. Trivial implementation."""
    greetings: dict[str, str] = {
        "en": "Hello",
        "es": "Hola",
        "fr": "Bonjour",
        "de": "Hallo",
        "ja": "Konnichiwa",
    }
    word: str = greetings.get(locale, greetings["en"])
    return f"{word}, {name}"


def build_app() -> Any:
    """Construct and instrument the FastAPI app.

    Returns the FastAPI app. If FastAPI is not installed, returns None;
    this allows py_compile to pass without runtime dependencies.
    """
    try:
        from fastapi import FastAPI
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        LOG.warning("FastAPI or OTel FastAPI instrumentation not installed; build_app skipped")
        return None

    otlp_endpoint: str = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "otelcol.observability.svc.cluster.local:4317",
    )
    service_name: str = os.environ.get("OTEL_SERVICE_NAME", "greeter")
    configure_tracing(service_name=service_name, otlp_endpoint=otlp_endpoint)
    app: Any = FastAPI(title="greeter", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/hello")
    def hello(name: str = "world", locale: str = "en") -> dict[str, Any]:
        return compute_greeting(name=name, locale=locale)

    FastAPIInstrumentor().instrument_app(app)
    return app


def main() -> None:
    """Run the service under uvicorn."""
    try:
        import uvicorn
    except ImportError:
        LOG.error("uvicorn not installed; cannot serve")
        return

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app: Any = build_app()
    if app is None:
        return
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
