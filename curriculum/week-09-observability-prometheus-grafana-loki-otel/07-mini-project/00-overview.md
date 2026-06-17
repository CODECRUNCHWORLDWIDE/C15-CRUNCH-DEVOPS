# Week 9 Mini-Project — A Fully Observable FastAPI Service

**Time:** ~7 hours (~6h building, ~1h write-up).
**Cost:** $0.00 (kind path).
**Prerequisites:** All four exercises complete. The `w09` kind cluster is running with `kube-prometheus-stack`, Jaeger, the OpenTelemetry Collector, and the `greeter` service.

---

## What you are building

A FastAPI service — call it `weather` — that exposes one user-visible endpoint (`GET /api/weather?city=<name>`) and one health endpoint. The service is fully instrumented:

1. **Metrics** — Prometheus counters, gauges, and histograms via `prometheus_client`.
2. **Logs** — structured JSON to stdout, scraped by the OpenTelemetry Collector and shipped to Loki. Every log line carries the active trace ID.
3. **Traces** — OpenTelemetry auto-instrumented HTTP spans plus two manual spans (one around the upstream API call, one around the response transformation). Exported via OTLP to Jaeger.
4. **Dashboards** — a Grafana dashboard committed to Git as a `ConfigMap`, provisioned via the sidecar. Three RED panels, two log panels, one trace-search shortcut.
5. **Alerts** — three `PrometheusRule` alerts: ServiceDown, HighErrorRate, HighLatency. All have `for:` clauses and runbook URLs.
6. **SLO** — one SLI (availability), one SLO (99.5% over 28 days), one burn-rate alert pair.

The whole thing — application code, Dockerfile, manifests, ServiceMonitor, PrometheusRule, dashboard ConfigMap — lives in a Git repo. ArgoCD applies it.

---

## The application

The `weather` service:

- `GET /api/health` — returns `{"status":"ok"}`. Used by readiness probes.
- `GET /api/weather?city=<name>` — returns a fake weather payload for the city. To keep the service self-contained, we do not call a real weather API; we simulate with a deterministic-by-city pseudo-response, plus a random latency injection and a random failure rate (configurable via env var).
- `GET /metrics` — Prometheus exposition.
- `GET /docs` — FastAPI's bundled OpenAPI UI. Free; comes with FastAPI.

The deliberately-injected failure rate (default 1%) gives the SLO and alert pages something to observe.

---

## Architecture

```
                  +------------------------------------+
                  |   Browser / curl                   |
                  +-----------------+------------------+
                                    |
                                    | HTTP
                                    v
                  +------------------------------------+
                  |   kind cluster, w09                |
                  |                                    |
                  |  +----------------------+          |
                  |  |  weather Deployment  |          |
                  |  |  (2 pods)            |          |
                  |  |                      |          |
                  |  |  prometheus_client   |  ----+   |
                  |  |  /metrics  ----------+----  |   |
                  |  |  python logging  ----+--+   |   |
                  |  |  OTel SDK  ---+---+--|--+   |   |
                  |  +---------------|---|--|--|   |   |
                  |                  |   |  |  |   |   |
                  |     spans (OTLP) |   |  |  |   |   |
                  |                  v   |  |  |   |   |
                  |  +-----------------+  |  |  |   |   |
                  |  | OTel Collector   | |  |  |   |   |
                  |  +---+----+---+-----+ |  |  |   |   |
                  |      |    |   |        |  |  |   |   |
                  |      v    v   v        |  |  |   |   |
                  |   Jaeger Loki ...      |  |  |   |   |
                  |                        |  |  |   |   |
                  |  +----------------+    |  |  |   |   |
                  |  | Prometheus     +----+--+--+---+   |
                  |  |  scrapes /metrics every 15s       |
                  |  +-------+--------+                   |
                  |          |                            |
                  |          v                            |
                  |  +----------------+                   |
                  |  | Grafana        |                   |
                  |  |  + dashboard   |                   |
                  |  +----------------+                   |
                  +------------------------------------+
                                    ^
                                    |
                                    | watches main branch
                                    |
                  +------------------------------------+
                  |   Git repo: github.com/YOU/c15-w09 |
                  |   path: manifests/                 |
                  +------------------------------------+
```

---

## Required deliverables

A Git repo containing:

```
c15-week09-mini-project/
+-- README.md                            - your project description
+-- app/
|   +-- Dockerfile
|   +-- requirements.txt
|   +-- weather.py                       - the FastAPI service
|   +-- logging_config.py                - structured-JSON logger with trace_id
+-- manifests/                           - what ArgoCD applies
|   +-- 00-namespace.yaml
|   +-- 10-deployment.yaml               - weather Deployment + Service
|   +-- 20-servicemonitor.yaml           - tells Prometheus to scrape
|   +-- 30-prometheusrule.yaml           - 3 alerts + 4 SLO recording rules + 2 SLO alerts
|   +-- 40-dashboard-configmap.yaml      - the Grafana dashboard
|   +-- 50-loki.yaml                     - Loki single-binary install (optional; from Helm too)
|   +-- 60-promtail.yaml                 - or the OTel collector log pipeline
+-- dashboards/                          - dashboard JSON source (copied into ConfigMap)
|   +-- weather-overview.json
+-- runbooks/                            - markdown for each alert
|   +-- weather-down.md
|   +-- weather-high-error-rate.md
|   +-- weather-high-latency.md
|   +-- weather-slo-burn.md
+-- screenshots/                         - your evidence
|   +-- dashboard.png
|   +-- jaeger-trace.png
|   +-- alert-firing.png
|   +-- slo-burn-rate.png
```

Total expected size: ~50 files, ~2,500 lines (mostly the dashboard JSON).

---

## Step 1 — Build the application

Write `weather.py`. The shape:

```python
"""Weather FastAPI service for Week 9 mini-project.

Endpoints:
    GET /api/weather?city=<name>  - returns a fake weather payload
    GET /api/health                - liveness
    GET /metrics                    - Prometheus
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from fastapi.responses import Response


REQUESTS: Counter = Counter(
    "weather_requests_total",
    "Total weather requests.",
    ["route", "status"],
)
IN_FLIGHT: Gauge = Gauge("weather_in_flight", "In-flight requests.")
DURATION: Histogram = Histogram(
    "weather_request_duration_seconds",
    "Distribution of weather request durations.",
    ["route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


def fake_weather(city: str) -> dict[str, Any]:
    """Deterministic-by-city fake weather payload."""
    seed: int = sum(ord(c) for c in city.lower())
    rng: random.Random = random.Random(seed)
    temp_c: float = rng.uniform(-10, 35)
    return {
        "city": city,
        "temp_c": round(temp_c, 1),
        "temp_f": round(temp_c * 9 / 5 + 32, 1),
        "humidity_pct": rng.randint(20, 95),
        "condition": rng.choice(["sunny", "cloudy", "rainy", "windy"]),
    }


# (full code in app/weather.py - see the file in your repo)
```

The full file is roughly 200 lines. Include:

- Auto-instrumentation: `FastAPIInstrumentor().instrument_app(app)`.
- Two manual spans: one around `fake_weather()` (representing the upstream call), one around the response building (representing the transformation).
- A `FAIL_RATE` env var (default 0.01 = 1%) that makes the handler raise `HTTPException(500)` randomly.
- A `LATENCY_MS_MEAN` env var (default 30) that makes the handler `time.sleep(random.uniform(0, 2 * mean) / 1000.0)`.
- Structured-JSON logging that includes the trace_id from the active span.

A reference implementation skeleton is in this README's appendix; flesh it out yourself.

---

## Step 2 — Containerize

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY weather.py logging_config.py ./
EXPOSE 8080
CMD ["python", "-u", "weather.py"]
```

`requirements.txt`:

```text
fastapi==0.115.0
uvicorn==0.30.6
prometheus_client==0.20.0
opentelemetry-api==1.27.0
opentelemetry-sdk==1.27.0
opentelemetry-exporter-otlp-proto-grpc==1.27.0
opentelemetry-instrumentation-fastapi==0.48b0
```

Build and load:

```bash
docker build -t weather:0.1 .
kind load docker-image weather:0.1 --name w09
```

---

## Step 3 — Write the manifests

Six manifest files. Bring them in order:

1. **`00-namespace.yaml`** — a `weather` namespace.
2. **`10-deployment.yaml`** — Deployment (2 replicas, requests/limits set, readiness probe) + Service (ClusterIP).
3. **`20-servicemonitor.yaml`** — selects the Service, scrapes `/metrics` every 15s.
4. **`30-prometheusrule.yaml`** — three alerts (Down / HighErrorRate / HighLatency), four recording rules (SLI ratios over 5m, 1h, 6h windows), two SLO burn-rate alerts.
5. **`40-dashboard-configmap.yaml`** — the dashboard JSON wrapped in a `ConfigMap` with label `grafana_dashboard: "1"`.
6. **`50-loki.yaml`** — Loki single-binary in `observability` (or install via Helm; see Step 4).

Apply manually first to debug, then commit to Git and let ArgoCD apply.

---

## Step 4 — Install Loki and a log shipper

Use the Helm path for simplicity:

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm install loki grafana/loki \
  --namespace observability \
  --create-namespace \
  --set deploymentMode=SingleBinary \
  --set loki.commonConfig.replication_factor=1 \
  --set loki.storage.type=filesystem \
  --set singleBinary.replicas=1
helm install promtail grafana/promtail \
  --namespace observability \
  --set config.clients[0].url=http://loki.observability.svc.cluster.local:3100/loki/api/v1/push
```

Or, if you prefer, configure the OpenTelemetry Collector you installed in Exercise 3 with a `loki` exporter and a `filelog` receiver. The collector approach is more general but the Helm path is faster for a kind cluster.

Add Loki as a data source in Grafana. The URL is `http://loki.observability.svc.cluster.local:3100`. Verify a LogQL query like `{namespace="weather"}` returns the weather pod logs.

---

## Step 5 — Author the dashboard

Six panels, in a 24-column grid:

| Panel | Type | Query | Position |
|---|---|---|---|
| Request rate by route | timeseries | `sum by (route) (rate(weather_requests_total[1m]))` | x=0, y=0, w=8, h=8 |
| Error rate | timeseries | `sum(rate(weather_requests_total{status=~"5.."}[5m])) / sum(rate(weather_requests_total[5m]))` | x=8, y=0, w=8, h=8 |
| p95 duration | stat | `histogram_quantile(0.95, sum by (le, route) (rate(weather_request_duration_seconds_bucket[5m])))` | x=16, y=0, w=8, h=8 |
| In-flight | stat | `sum(weather_in_flight)` | x=0, y=8, w=6, h=4 |
| SLO burn rate (1h) | gauge | `greeter:availability_sli:error_ratio_rate1h / 0.005` | x=6, y=8, w=6, h=4 |
| Recent errors (logs) | logs | `{namespace="weather"} |= "error"` | x=0, y=12, w=24, h=8 |

Save the JSON to `dashboards/weather-overview.json`. Pack into the ConfigMap in `manifests/40-dashboard-configmap.yaml`.

---

## Step 6 — Write the runbooks

Each alert annotation includes a `runbook` URL. The URL must point at something. Write a one-page markdown for each:

```markdown
# Runbook — Weather Service Down

## Symptom

The `WeatherServiceDown` alert is firing. The `up{job="weather"}` metric has been 0 for >2 minutes.

## Triage

1. `kubectl get pods -n weather` — are the pods Running?
2. `kubectl describe pod -n weather <name>` — recent events?
3. `kubectl logs -n weather <name>` — error messages?

## Common causes

- Image pull failure: `kind load docker-image weather:0.1 --name w09` if testing locally.
- Crash loop: check logs.
- ServiceMonitor label drift: `kubectl get servicemonitor -n monitoring weather -o yaml`.

## Resolution

Once the pods are Running, the alert clears within 2 minutes.

## Escalation

If unresolvable within 30 minutes, page the service owner via PagerDuty.
```

Four runbook files, ~50 lines each.

---

## Step 7 — Wire ArgoCD

If you have ArgoCD running from Week 8, point an `Application` at this repo:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: weather
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOU/c15-week09-mini-project
    targetRevision: HEAD
    path: manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: weather
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

If you do not have ArgoCD, `kubectl apply -k manifests/` (with a Kustomization) is fine.

---

## Step 8 — Generate traffic and verify

Start a load generator with both happy and unhappy mixes:

```bash
kubectl run loadgen --image=curlimages/curl:8.10.1 --rm -i --tty --restart=Never -- sh
# inside:
while true; do
  curl -s "http://weather.weather.svc.cluster.local:8080/api/weather?city=Miami" > /dev/null
  curl -s "http://weather.weather.svc.cluster.local:8080/api/weather?city=Tokyo" > /dev/null
  curl -s "http://weather.weather.svc.cluster.local:8080/api/weather?city=$(date +%s)" > /dev/null
  sleep 0.1
done
```

The 1% failure rate produces ~1 error per 100 requests. Over 1000 requests, the metrics, logs, and traces should all show the same ~10 errors.

Open:

- Grafana → "Weather Overview" dashboard. RED panels populate.
- Loki query `{namespace="weather"} |= "error"` shows the error log lines.
- Jaeger search for `service=weather, tags=error=true` shows the error traces.
- Prometheus `/alerts` shows the alerts in INACTIVE state.

Now bump the failure rate temporarily:

```bash
kubectl set env deploy/weather -n weather FAIL_RATE=0.15
```

Within 5 minutes the `HighErrorRate` alert fires. The webhook from Exercise 2 receives it. The dashboard's error-rate panel goes red.

Lower the rate back:

```bash
kubectl set env deploy/weather -n weather FAIL_RATE=0.01
```

Watch the alert resolve.

---

## Step 9 — The write-up

Write a `README.md` in your repo's root that covers:

1. **What the service does.** (1 paragraph.)
2. **The observability story.** (1-2 paragraphs covering metrics + logs + traces, with screenshots.)
3. **The SLI/SLO.** (1 paragraph defining the SLI, justifying the SLO target, naming the error budget.)
4. **The alerts.** (Bullet list with name, severity, what it means, link to runbook.)
5. **The dashboards.** (Screenshot, with one sentence per panel.)
6. **The known gaps.** (Things that would be different in production: TLS, secrets management, multi-cluster, real OAuth on Grafana, etc.)

---

## Grading rubric

Each deliverable below is worth a fixed number of points. Total: 100.

| Deliverable | Points |
|---|---:|
| Service compiles and runs (`python3 -m py_compile`) | 5 |
| Container image builds and loads into kind | 5 |
| Manifests apply cleanly via `kubectl apply` | 10 |
| ServiceMonitor produces scrape targets in Prometheus | 10 |
| Three RED panels in dashboard render with real data | 15 |
| Logs visible in Loki, queryable by service | 10 |
| Traces visible in Jaeger with manual spans | 10 |
| Three alerts evaluable; one fires correctly when forced | 15 |
| SLO recording rules + burn-rate alert | 10 |
| README with screenshots and reflection | 10 |

90+: distinguished.
75-89: passes.
<75: revise.

---

## Cleanup at end of week

```bash
helm uninstall promtail loki -n observability
helm uninstall kps -n monitoring
kubectl delete namespace observability monitoring weather
kind delete cluster --name w09
```

Or keep the cluster running into Week 10 if your laptop has the RAM and the work is in progress.

---

## Appendix — reference implementation skeleton for `weather.py`

```python
"""Weather FastAPI service for Week 9 mini-project."""
from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Any

# Logging setup (structured JSON)
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        try:
            from opentelemetry import trace as otel_trace
            span = otel_trace.get_current_span()
            ctx = span.get_span_context() if span else None
            trace_id = f"{ctx.trace_id:032x}" if ctx and ctx.trace_id else ""
        except ImportError:
            trace_id = ""
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
            "trace_id": trace_id,
        }
        return json.dumps(payload)


def configure_logging() -> None:
    handler: logging.StreamHandler[Any] = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root: logging.Logger = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def get_fail_rate() -> float:
    try:
        return float(os.environ.get("FAIL_RATE", "0.01"))
    except ValueError:
        return 0.01


def get_latency_ms_mean() -> float:
    try:
        return float(os.environ.get("LATENCY_MS_MEAN", "30"))
    except ValueError:
        return 30.0
```

This is half the file. Finish it: add the `prometheus_client` counters/gauges/histograms, the OpenTelemetry tracing setup (copy from `greeter.py`), the FastAPI `app`, the two handlers, the `/metrics` route, the manual spans around `fake_weather()`, and the failure injection. Aim for ~250 lines total.
