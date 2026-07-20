# Exercise 3 — Instrument a FastAPI Service with OpenTelemetry

**Time:** 75 minutes (15 min reading, 45 min hands-on, 15 min write-up).
**Cost:** $0.00.
**Cluster:** The `w09` kind cluster from Exercises 1 and 2.

---

## Goal

Build a small FastAPI service, instrument it with the OpenTelemetry Python SDK (auto-instrumentation + one manual span), run Jaeger in the cluster to receive traces, and observe a request as a trace tree in the Jaeger UI.

After this exercise you should have:

- A `greeter` FastAPI service in `default` exposing `GET /api/hello?name=X` and `GET /api/health`.
- The OpenTelemetry SDK configured at app startup, exporting traces via OTLP/gRPC to a collector inside the cluster.
- A Jaeger all-in-one Deployment in `observability` receiving traces.
- The OpenTelemetry Collector running as a Deployment, configured with an `otlp` receiver and a `jaeger` exporter.
- A working trace visible in the Jaeger UI for every request, with the root span (FastAPI auto-instrumented) and one manual child span (`compute_greeting`).

---

## Step 1 — Install Jaeger

Jaeger has a single-binary "all-in-one" image that runs the collector, query service, and storage in one process. Perfect for kind.

Save as `jaeger-manifest.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: observability
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jaeger
  namespace: observability
  labels:
    app.kubernetes.io/name: jaeger
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: jaeger
  template:
    metadata:
      labels:
        app.kubernetes.io/name: jaeger
    spec:
      containers:
        - name: jaeger
          image: jaegertracing/all-in-one:1.55
          env:
            - name: COLLECTOR_OTLP_ENABLED
              value: "true"
          ports:
            - name: ui
              containerPort: 16686
            - name: otlp-grpc
              containerPort: 4317
            - name: otlp-http
              containerPort: 4318
          readinessProbe:
            httpGet:
              path: /
              port: ui
            initialDelaySeconds: 5
            periodSeconds: 5
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
---
apiVersion: v1
kind: Service
metadata:
  name: jaeger
  namespace: observability
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: jaeger
  ports:
    - name: ui
      port: 16686
      targetPort: ui
    - name: otlp-grpc
      port: 4317
      targetPort: otlp-grpc
    - name: otlp-http
      port: 4318
      targetPort: otlp-http
```

Apply:

```bash
kubectl apply -f jaeger-manifest.yaml
kubectl rollout status deploy/jaeger -n observability
```

Verify:

```bash
kubectl port-forward -n observability svc/jaeger 16686:16686
```

Open <http://localhost:16686>. The Jaeger UI loads; the service dropdown is empty (no traces have arrived yet).

---

## Step 2 — Install the OpenTelemetry Collector

We run the collector as a small Deployment (one replica). For production, you would run it as a DaemonSet for node-local collection; for the kind cluster, one replica is sufficient.

Save as `otelcol-config.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: otelcol-config
  namespace: observability
data:
  config.yaml: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
          http:
            endpoint: 0.0.0.0:4318
    processors:
      batch:
        timeout: 5s
        send_batch_size: 100
      memory_limiter:
        check_interval: 5s
        limit_percentage: 75
        spike_limit_percentage: 15
    exporters:
      otlp/jaeger:
        endpoint: jaeger.observability.svc.cluster.local:4317
        tls:
          insecure: true
      debug:
        verbosity: basic
    service:
      pipelines:
        traces:
          receivers: [otlp]
          processors: [memory_limiter, batch]
          exporters: [otlp/jaeger, debug]
      telemetry:
        logs:
          level: info
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otelcol
  namespace: observability
  labels:
    app.kubernetes.io/name: otelcol
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: otelcol
  template:
    metadata:
      labels:
        app.kubernetes.io/name: otelcol
    spec:
      containers:
        - name: otelcol
          image: otel/opentelemetry-collector-contrib:0.108.0
          args:
            - "--config=/conf/config.yaml"
          ports:
            - name: otlp-grpc
              containerPort: 4317
            - name: otlp-http
              containerPort: 4318
          volumeMounts:
            - name: config
              mountPath: /conf
          resources:
            requests:
              cpu: 50m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
      volumes:
        - name: config
          configMap:
            name: otelcol-config
---
apiVersion: v1
kind: Service
metadata:
  name: otelcol
  namespace: observability
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: otelcol
  ports:
    - name: otlp-grpc
      port: 4317
      targetPort: otlp-grpc
    - name: otlp-http
      port: 4318
      targetPort: otlp-http
```

Apply:

```bash
kubectl apply -f otelcol-config.yaml
kubectl rollout status deploy/otelcol -n observability
```

Read the logs to verify the collector started cleanly:

```bash
kubectl logs -n observability -l app.kubernetes.io/name=otelcol --tail=50
```

You should see `Starting otelcol-contrib...` and the pipelines coming up. Any red lines about parse errors mean the ConfigMap has a typo.

---

## Step 3 — Write the FastAPI service

Save as `greeter.py`. Type-hinted, `python3 -m py_compile` clean.

```python
"""Greeter FastAPI service for Week 9 Exercise 3.

Endpoints:
    GET /api/hello?name=X  - returns a greeting
    GET /api/health        - liveness probe

Instrumented with OpenTelemetry:
    - FastAPI auto-instrumentation for HTTP spans
    - One manual span around compute_greeting
    - Traces exported via OTLP/gRPC to the OpenTelemetry Collector
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


LOG: logging.Logger = logging.getLogger("greeter")


def configure_tracing(service_name: str, otlp_endpoint: str) -> None:
    """Configure the OpenTelemetry TracerProvider for this process."""
    resource: Resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "0.1.0",
            "deployment.environment": os.environ.get("DEPLOY_ENV", "dev"),
        }
    )
    provider: TracerProvider = TracerProvider(resource=resource)
    exporter: OTLPSpanExporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=True,
    )
    processor: BatchSpanProcessor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    LOG.info("tracing configured: service=%s endpoint=%s", service_name, otlp_endpoint)


def compute_greeting(name: str, locale: str) -> dict[str, Any]:
    """Compute a greeting for the given name and locale.

    Wrapped in a manual span so we can attribute the operation
    and slice the trace data by locale and name length.
    """
    tracer: trace.Tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("compute_greeting") as span:
        span.set_attribute("greeting.name_length", len(name))
        span.set_attribute("greeting.locale", locale)
        # Simulate a tiny bit of work so the span has measurable duration.
        time.sleep(0.005)
        message: str = render_message(name, locale)
        span.set_attribute("greeting.message_length", len(message))
        return {"greeting": message, "locale": locale}


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


def build_app() -> FastAPI:
    """Construct and instrument the FastAPI app."""
    otlp_endpoint: str = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "otelcol.observability.svc.cluster.local:4317")
    service_name: str = os.environ.get("OTEL_SERVICE_NAME", "greeter")
    configure_tracing(service_name=service_name, otlp_endpoint=otlp_endpoint)
    app: FastAPI = FastAPI(title="greeter", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/hello")
    def hello(name: str = "world", locale: str = "en") -> dict[str, Any]:
        return compute_greeting(name=name, locale=locale)

    FastAPIInstrumentor().instrument_app(app)
    return app


app: FastAPI = build_app()


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

A `requirements.txt`:

```text
fastapi==0.115.0
uvicorn==0.30.6
opentelemetry-api==1.27.0
opentelemetry-sdk==1.27.0
opentelemetry-exporter-otlp-proto-grpc==1.27.0
opentelemetry-instrumentation-fastapi==0.48b0
```

A `Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY greeter.py .
EXPOSE 8080
CMD ["python", "-u", "greeter.py"]
```

Build and load:

```bash
docker build -t greeter:0.1 .
kind load docker-image greeter:0.1 --name w09
```

---

## Step 4 — Deploy the greeter

Save as `greeter-manifest.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: greeter
  namespace: default
  labels:
    app.kubernetes.io/name: greeter
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: greeter
  template:
    metadata:
      labels:
        app.kubernetes.io/name: greeter
    spec:
      containers:
        - name: greeter
          image: greeter:0.1
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8080
          env:
            - name: OTEL_SERVICE_NAME
              value: greeter
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: otelcol.observability.svc.cluster.local:4317
            - name: DEPLOY_ENV
              value: dev
          readinessProbe:
            httpGet:
              path: /api/health
              port: http
            initialDelaySeconds: 3
            periodSeconds: 5
          resources:
            requests:
              cpu: 50m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
---
apiVersion: v1
kind: Service
metadata:
  name: greeter
  namespace: default
  labels:
    app.kubernetes.io/name: greeter
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: greeter
  ports:
    - name: http
      port: 8080
      targetPort: http
```

Apply:

```bash
kubectl apply -f greeter-manifest.yaml
kubectl rollout status deploy/greeter
```

---

## Step 5 — Generate traffic and watch traces arrive

```bash
kubectl run loadgen --image=curlimages/curl:8.10.1 --rm -i --tty --restart=Never -- sh
```

Inside:

```sh
for i in $(seq 1 50); do
  curl -s "http://greeter.default.svc.cluster.local:8080/api/hello?name=Test$i&locale=es" > /dev/null
  sleep 0.2
done
```

In another terminal, port-forward Jaeger:

```bash
kubectl port-forward -n observability svc/jaeger 16686:16686
```

Open <http://localhost:16686>. The service dropdown now has `greeter`. Pick it. Click "Find Traces". You should see ~50 traces, each ~10 ms long.

Click one trace. The trace view shows:

- The root span: `GET /api/hello` (FastAPI auto-instrumentation).
- One child span: `compute_greeting` (your manual span).
- The duration of each, the attributes on each (`http.method`, `http.route`, `http.status_code` on the root; `greeting.locale`, `greeting.name_length`, `greeting.message_length` on the child).

This is the trace pillar in one screen.

---

## Step 6 — Search and filter

In Jaeger:

- Filter by tag: in the "Tags" search box, enter `greeting.locale=es`. Only the Spanish-locale traces show up.
- Filter by duration: set "Min Duration" to `8ms`. The slower traces filter to the top.
- Filter by error: set "Tags" to `error=true`. None right now (no errors); we will see this in the mini-project.

---

## Step 7 — Connect Grafana to Jaeger

In Grafana (port-forward `kps-grafana 3000:80`), navigate to **Connections -> Data sources -> Add new data source**. Pick **Jaeger**.

- URL: `http://jaeger.observability.svc.cluster.local:16686`
- Save and test.

Once saved, you can use Grafana's **Explore** view to query traces just like you query metrics. The trace-to-logs and trace-to-metrics correlations Grafana supports start to become useful once you wire the same `service.name` across all three pillars; we set that up in the mini-project.

---

## Step 8 — Write up

In your notes:

1. The four lines of code in `configure_tracing` and what each does.
2. The shape of a trace from a single `/api/hello` request (root span + manual child).
3. The attributes on the manual span and why each one is useful for diagnosis.
4. What `FastAPIInstrumentor().instrument_app(app)` does (in your own words).

Diagnostic questions:

- **Q1.** Why is the OTLP exporter pointed at the *collector*, not at Jaeger directly?
- **Q2.** What is the BatchSpanProcessor doing, and what would happen if you used SimpleSpanProcessor instead?
- **Q3.** Why is `service.name` set as a resource attribute and not a span attribute?
- **Q4.** Sampling is set to 100% (the SDK default). What changes would you make for production?

Answers in `SOLUTIONS.md`.

---

## What is next

Exercise 4 — write a Grafana dashboard as JSON, commit it to a `ConfigMap`, and watch the sidecar provision it into Grafana automatically.
