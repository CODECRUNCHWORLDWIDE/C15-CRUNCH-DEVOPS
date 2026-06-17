# Exercise 2 — Write a `ServiceMonitor`, a `PrometheusRule`, and Route an Alert

**Time:** 75 minutes (15 min reading, 45 min hands-on, 15 min write-up).
**Cost:** $0.00.
**Cluster:** The `w09` kind cluster from Exercise 1, with `kube-prometheus-stack` already installed.

---

## Goal

Deploy a small Python service that exposes `/metrics`, write a `ServiceMonitor` so Prometheus scrapes it, write a `PrometheusRule` with one recording rule and one alerting rule, deploy a webhook receiver that logs alerts, route the alert to it, and watch the alert fire and resolve.

After this exercise you should have:

- A `metric-emitter` Deployment in the `default` namespace, exposing `/metrics` on port 8080.
- A `ServiceMonitor` named `metric-emitter` in `monitoring`, scraping the deployment every 15s.
- A `PrometheusRule` named `metric-emitter-rules` with one recording rule and one alerting rule.
- An `alert-webhook` Deployment in `monitoring` that receives alert webhooks and logs them.
- A custom Alertmanager configuration that routes the alert to the webhook.
- A test where you force the metric to violate the rule and watch the alert fire, hit the webhook, and then resolve.

---

## Step 1 — Write the metric-emitter Python service

The service emits one counter (`emitter_requests_total`) that increments on every request to `/work`, one gauge (`emitter_in_flight`), and one histogram (`emitter_work_duration_seconds`). It also serves `/metrics` for Prometheus to scrape and `/health` for the readiness probe.

Save as `emitter.py`. Every function has type hints; the file is one `python3 -m py_compile` clean.

```python
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
```

A `Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir prometheus_client==0.20.0
COPY emitter.py .
EXPOSE 8080
CMD ["python", "-u", "emitter.py"]
```

Build and load into kind:

```bash
docker build -t metric-emitter:0.1 .
kind load docker-image metric-emitter:0.1 --name w09
```

---

## Step 2 — Deploy it to the cluster

Save as `emitter-manifest.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metric-emitter
  namespace: default
  labels:
    app.kubernetes.io/name: metric-emitter
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: metric-emitter
  template:
    metadata:
      labels:
        app.kubernetes.io/name: metric-emitter
    spec:
      containers:
        - name: emitter
          image: metric-emitter:0.1
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
          readinessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 2
            periodSeconds: 5
          resources:
            requests:
              cpu: 25m
              memory: 32Mi
            limits:
              cpu: 200m
              memory: 128Mi
---
apiVersion: v1
kind: Service
metadata:
  name: metric-emitter
  namespace: default
  labels:
    app.kubernetes.io/name: metric-emitter
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: metric-emitter
  ports:
    - name: http
      port: 8080
      targetPort: http
      protocol: TCP
```

Apply:

```bash
kubectl apply -f emitter-manifest.yaml
kubectl get pods -l app.kubernetes.io/name=metric-emitter
```

Wait for 2 pods `Running` and `1/1` ready.

Confirm metrics are emitted:

```bash
kubectl port-forward svc/metric-emitter 8080:8080
curl -s http://localhost:8080/metrics | grep emitter_
```

You should see `emitter_requests_total`, `emitter_in_flight`, `emitter_work_duration_seconds_*`. Stop the port-forward.

---

## Step 3 — Write the ServiceMonitor

Save as `emitter-servicemonitor.yaml`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: metric-emitter
  namespace: monitoring
  labels:
    release: kps
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: metric-emitter
  namespaceSelector:
    matchNames:
      - default
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
      scrapeTimeout: 10s
```

Apply and verify it propagates to Prometheus:

```bash
kubectl apply -f emitter-servicemonitor.yaml
kubectl port-forward -n monitoring svc/kps-kube-prometheus-stack-prometheus 9090:9090
```

Open <http://localhost:9090/targets>. Within 30 seconds you should see a new job: `serviceMonitor/monitoring/metric-emitter`. Both endpoints should be in `UP` state.

In the Prometheus search box, type `emitter_requests_total` and press Enter. You should see two series (one per pod). The values will be 0 because no traffic has hit `/work` yet.

---

## Step 4 — Generate some traffic

```bash
kubectl run loadgen --image=curlimages/curl:8.10.1 --rm -i --tty --restart=Never -- sh
```

Inside the loadgen pod:

```sh
while true; do
  curl -s "http://metric-emitter.default.svc.cluster.local:8080/work?ms=50" > /dev/null
  sleep 0.1
done
```

Leave it running. In Prometheus, the `emitter_requests_total` counter should now be increasing. Query `rate(emitter_requests_total[1m])` — you should see roughly 10 req/s per pod (the sleep 0.1 in loadgen).

---

## Step 5 — Write the PrometheusRule

Two rules: one recording rule (the per-second request rate aggregated across pods), and one alerting rule (fire if the rate drops below 5 req/s for 2 minutes).

Save as `emitter-rules.yaml`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: metric-emitter-rules
  namespace: monitoring
  labels:
    release: kps
spec:
  groups:
    - name: emitter-recording
      interval: 30s
      rules:
        - record: emitter:requests_per_second
          expr: |
            sum (rate(emitter_requests_total[1m]))
    - name: emitter-alerting
      interval: 30s
      rules:
        - alert: EmitterRateLow
          expr: emitter:requests_per_second < 5
          for: 2m
          labels:
            severity: warning
            service: metric-emitter
          annotations:
            summary: "metric-emitter request rate dropped below 5 req/s for 2 minutes"
            description: "Current rate is {{ $value | humanize }} req/s. Expected at least 5."
            runbook: "https://wiki.example.com/runbooks/emitter-rate-low"
```

Apply:

```bash
kubectl apply -f emitter-rules.yaml
```

In Prometheus, navigate to `/rules`. You should see the two groups. The recording rule's series — `emitter:requests_per_second` — is queryable. Try it: search for `emitter:requests_per_second`. The result is one series whose value is roughly 20 (two pods × 10 req/s).

---

## Step 6 — Deploy a webhook receiver

A 30-line Python service that logs every alert it receives. Save as `webhook.py`:

```python
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
```

Dockerfile (`Dockerfile.webhook`):

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY webhook.py .
EXPOSE 5001
CMD ["python", "-u", "webhook.py"]
```

Build and load:

```bash
docker build -t alert-webhook:0.1 -f Dockerfile.webhook .
kind load docker-image alert-webhook:0.1 --name w09
```

Deploy. Save as `webhook-manifest.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: alert-webhook
  namespace: monitoring
  labels:
    app.kubernetes.io/name: alert-webhook
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: alert-webhook
  template:
    metadata:
      labels:
        app.kubernetes.io/name: alert-webhook
    spec:
      containers:
        - name: webhook
          image: alert-webhook:0.1
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 5001
              protocol: TCP
---
apiVersion: v1
kind: Service
metadata:
  name: alert-webhook
  namespace: monitoring
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: alert-webhook
  ports:
    - name: http
      port: 5001
      targetPort: http
```

```bash
kubectl apply -f webhook-manifest.yaml
kubectl rollout status deploy/alert-webhook -n monitoring
```

---

## Step 7 — Configure Alertmanager to route to the webhook

The chart manages Alertmanager configuration via a `Secret` named `alertmanager-kps-kube-prometheus-stack-alertmanager`. We override it via the chart's values. Save as `kps-values-patch.yaml`:

```yaml
alertmanager:
  config:
    route:
      group_by: [alertname, service]
      group_wait: 30s
      group_interval: 1m
      repeat_interval: 5m
      receiver: webhook-default
      routes:
        - matchers:
            - severity = "warning"
          receiver: webhook-default
          continue: false
    receivers:
      - name: "null"
      - name: webhook-default
        webhook_configs:
          - url: "http://alert-webhook.monitoring.svc.cluster.local:5001/webhook"
            send_resolved: true
```

Apply the patch (Helm upgrade with merged values):

```bash
helm upgrade kps prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values kps-values.yaml \
  --values kps-values-patch.yaml \
  --wait \
  --timeout 5m
```

Verify the Alertmanager config in its UI (port-forward 9093): the `Status` page should show the new `route.receiver: webhook-default` and the new `webhook-default` receiver.

---

## Step 8 — Fire the alert

The alert fires when `emitter:requests_per_second < 5` for 2 minutes. Stop the loadgen pod from Step 4:

```bash
kubectl delete pod loadgen --now
```

Within 60 seconds the recording rule will show ~0 req/s. After 2 more minutes the alert fires. Watch:

- Prometheus `/alerts`: the `EmitterRateLow` alert should move from `INACTIVE` -> `PENDING` (during the `for: 2m`) -> `FIRING`.
- Alertmanager `/`: the alert appears in the dashboard, grouped under `alertname=EmitterRateLow, service=metric-emitter`.
- Webhook logs:

```bash
kubectl logs -n monitoring -l app.kubernetes.io/name=alert-webhook -f
```

You should see a JSON payload with `status: firing` and the alert's labels and annotations. The Slack-style integration would be the same shape; the webhook is the universal escape hatch.

---

## Step 9 — Watch the alert resolve

Restart loadgen:

```bash
kubectl run loadgen --image=curlimages/curl:8.10.1 --rm -i --tty --restart=Never -- sh
# inside the pod:
while true; do curl -s "http://metric-emitter.default.svc.cluster.local:8080/work?ms=50" > /dev/null; sleep 0.05; done
```

Within 90 seconds the rate is back above 5 req/s, the alert in Prometheus goes back to `INACTIVE`, Alertmanager sends a `status: resolved` webhook, and the webhook logs show it.

---

## Step 10 — Write up

In your notes, capture:

1. The recording rule and its purpose.
2. The alerting rule's PromQL expression and the `for:` duration.
3. The Alertmanager routing tree (in five lines).
4. A screenshot of the webhook log showing both `firing` and `resolved` payloads.

The diagnostic questions:

- **Q1.** Why is the `for: 2m` important? What would happen if you set it to `for: 0s`?
- **Q2.** What is the difference between the recording rule's interval (`30s`) and the alerting rule's `for: 2m`?
- **Q3.** If you delete the `release: kps` label from the `PrometheusRule`, what happens? (Try it; revert after.)
- **Q4.** Why is `send_resolved: true` important on the webhook receiver?

Answers in `SOLUTIONS.md`.

---

## Cleanup (do not, until end of week)

Leave the cluster running for Exercises 3 and 4 and the mini-project.

---

## What is next

Exercise 3 — instrument a FastAPI service with OpenTelemetry, run a Jaeger to receive traces, and see a request flow through as a trace tree.
