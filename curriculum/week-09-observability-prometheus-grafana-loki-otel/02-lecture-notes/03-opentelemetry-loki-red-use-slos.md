# Lecture 3 — OpenTelemetry, Loki, RED, USE, and SLOs

> *An error budget is not a metric. It is a contract between the team that ships and the team that pages. When the budget is healthy, the first team's job is to ship faster. When it is burning, the first team's job is to stop and help the second.*

In Lecture 1 you saw metrics and the Prometheus model. In Lecture 2 you saw dashboards and alerting. Both lectures stayed inside one pillar: metrics. This lecture is the joining lecture. It covers the second and third pillars (logs via Loki, traces via OpenTelemetry), then the two methodologies that decide *what to measure* (RED for services, USE for resources), then the SRE vocabulary that turns those measurements into a working operational practice (SLI, SLO, error budget). It is the longest lecture of the week because it is the lecture where the pieces become a discipline.

---

## 1. OpenTelemetry, the unified instrumentation SDK

In 2018 there were two tracing standards: **OpenTracing** (vendor-neutral, started by LightStep) and **OpenCensus** (vendor-neutral, started by Google). They were doing the same job, slightly differently, and the engineers who had to write instrumentation libraries had to choose. In 2019 the two projects merged under the CNCF as **OpenTelemetry**. The merged project absorbed the goals of both: one SDK, one wire protocol, one set of semantic conventions, every language, every vendor.

In 2026 OpenTelemetry is the default. Every observability vendor — Datadog, New Relic, Honeycomb, Lightstep, Dynatrace, Splunk, Elastic, Grafana — accepts OTLP (the OpenTelemetry Protocol). The auto-instrumentation library for every major framework in every major language is OpenTelemetry. Writing observability code against a vendor agent in 2026 is choosing lock-in for no reason; the OpenTelemetry SDK works against every backend, including the open-source ones we use this week.

### The architecture: API, SDK, exporter, collector

The OpenTelemetry stack has four layers:

1. **The API.** A stable, small, language-specific interface that application code calls. The Python API has functions like `tracer.start_as_current_span(...)` and `meter.create_counter(...)`. The API is meant to be safe to import in a library: if no SDK is configured, the API is a no-op; if an SDK is configured, the API routes through it.
2. **The SDK.** The implementation layer. Configures samplers, processors, exporters. The application chooses an SDK at startup; libraries do not. The Python SDK is `opentelemetry-sdk`.
3. **The exporter.** A pluggable backend that the SDK sends data to. The standard exporter is OTLP/gRPC (port 4317) or OTLP/HTTP (port 4318). Vendor-specific exporters exist (Jaeger Thrift, Zipkin JSON, Datadog Trace API) but the recommended path in 2026 is OTLP to a collector that does the vendor translation.
4. **The collector.** A separate process (the OpenTelemetry Collector, `otelcol-contrib`) that receives telemetry from applications, processes it (sampling, batching, filtering, attribute enrichment), and exports it to one or more backends. Typically deployed as a DaemonSet (one collector per Kubernetes node) so applications can send to `localhost` without going over the network.

The separation between API and SDK is the most important design decision of OpenTelemetry. It means a library that emits spans does not have to commit to a backend; the application that uses the library commits the backend. Datadog and New Relic for decades shipped libraries that emitted directly to their own backends and that conflicted with each other when both were imported. OpenTelemetry's API/SDK split fixes the conflict at the architectural level.

### Spans, traces, and the W3C Trace Context

A **span** is the unit of work. It has a name (`GET /api/hello`), a start time, an end time, a parent span (or null if it is the root), a set of attributes (key-value pairs), and a status (OK or ERROR). A **trace** is the set of spans sharing one trace ID, organized into a tree by parent-child relationships.

The trace ID is a 16-byte random identifier. The span ID is an 8-byte random identifier. Both are formatted as lowercase hex in the wire protocol. A trace ID looks like `4bf92f3577b34da6a3ce929d0e0e4736`.

Propagation across services uses the **W3C Trace Context** header:

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

Reading: `00` (version) - `4bf92f3577b34da6a3ce929d0e0e4736` (trace ID) - `00f067aa0ba902b7` (parent span ID) - `01` (flags: sampled).

When service A calls service B, A includes the `traceparent` header. B's instrumentation reads the header, takes the trace ID and the parent span ID, starts a new span as a child of the parent, and continues the trace. The result is that a single trace can span any number of services and the parent-child relationships are preserved across the network.

The W3C Trace Context spec is at <https://www.w3.org/TR/trace-context/>. Read it once; it is short.

### Auto-instrumentation in Python

The OpenTelemetry Python SDK has auto-instrumentation libraries for every major framework. The pattern: you `pip install opentelemetry-instrumentation-<framework>` and call its `instrument()` method at app startup. The instrumentation wraps the framework's internals — for FastAPI, the ASGI middleware; for `requests`, the Session — and emits spans around every HTTP call.

The relevant Python packages for this week:

- `opentelemetry-api` — the API.
- `opentelemetry-sdk` — the SDK.
- `opentelemetry-instrumentation-fastapi` — auto-instruments FastAPI HTTP handlers.
- `opentelemetry-instrumentation-requests` — auto-instruments outgoing HTTP requests via the `requests` library.
- `opentelemetry-instrumentation-httpx` — same for `httpx`.
- `opentelemetry-exporter-otlp-proto-grpc` — the OTLP/gRPC exporter.

Setup at app startup (Exercise 3 has the complete file; this is the skeleton):

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


def configure_tracing(service_name: str, otlp_endpoint: str) -> None:
    resource: Resource = Resource.create({"service.name": service_name})
    provider: TracerProvider = TracerProvider(resource=resource)
    exporter: OTLPSpanExporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    processor: BatchSpanProcessor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)


# In the FastAPI app:
configure_tracing(service_name="api", otlp_endpoint="otelcol.observability.svc:4317")
FastAPIInstrumentor().instrument_app(app)
```

After those four lines and the `instrument_app(app)` call, every HTTP request to the FastAPI app emits a span. The span carries the route name, the method, the status code, the client IP, the duration, and any exception that bubbled up. No application code changes.

### Manual spans

Auto-instrumentation covers framework boundaries: HTTP in, HTTP out, database round-trip, cache call. For business-logic boundaries — "fetch the user's plan", "compute the discount", "format the receipt" — you add manual spans:

```python
from opentelemetry import trace
from typing import Any

tracer: trace.Tracer = trace.get_tracer(__name__)


def compute_greeting(name: str, locale: str) -> dict[str, Any]:
    with tracer.start_as_current_span("compute_greeting") as span:
        span.set_attribute("greeting.locale", locale)
        span.set_attribute("greeting.name_length", len(name))
        message: str = render_locale_specific_greeting(name, locale)
        span.set_attribute("greeting.message_length", len(message))
        return {"greeting": message}
```

The `with` block opens a span at entry and closes it at exit (even on exception). Attributes are added during the work. The result is a span named `compute_greeting` that is a child of whichever span was current when the function was called.

Three rules for manual spans:

1. **Span around business-logic boundaries, not around lines of code.** A span per function is overkill; a span per "logical operation" is right.
2. **Attribute the inputs and outputs you would want to query.** Not the full request body (PII); the dimensions you would slice on.
3. **Always close the span.** The `with` block does this automatically. Manual `span.end()` calls leak spans when an exception bubbles.

### Metrics and logs from the same SDK

OpenTelemetry is not only traces. The SDK also has APIs for metrics and logs:

- The **metrics API** has counters, up-down counters, histograms, gauges. The SDK exports them via OTLP. A collector receives them and forwards to Prometheus (via the `prometheusexporter` or via the `prometheusremotewriteexporter`). The shape on the Prometheus side is identical to what `prometheus_client` would have produced.
- The **logs API** lets the application emit structured log records. The SDK exports them via OTLP. A collector forwards to Loki (via the `lokiexporter`). The log record carries the trace ID automatically, so the correlation between log lines and traces is native.

In Exercise 3 we use OpenTelemetry for traces and we keep `prometheus_client` for metrics (the canonical pattern in 2026 — OTel-traces, Prometheus-metrics, structured-logs-to-Loki). The full OTel-everything path is documented at <https://opentelemetry.io/docs/languages/python/> and is reasonable if your team standardizes on it.

### Sampling

Every production trace system samples. Tracing every request is too expensive at any scale that matters; tracing one in 100 is the default.

Sampling strategies:

- **Head sampling** — the decision is made at the start of the trace, before the work is done. Random sampling (1% of traces) or rate-limiting (10 traces per second). Cheap; loses interesting traces randomly.
- **Tail sampling** — the decision is made at the end of the trace, after seeing all the spans. Keep every trace with an error; keep every trace where latency exceeded 1 second; sample the rest at 1%. Expensive (the collector has to buffer all spans for the trace duration); keeps the interesting traces.

The OpenTelemetry Collector implements tail sampling via the `tail_sampling` processor. The configuration is at <https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/processor/tailsamplingprocessor>. For Week 9 we use head sampling at 100% (the volume on a kind cluster is tiny). Production deployments use tail sampling at single-digit percentages.

---

## 2. Loki, the log store

Loki is a log store designed by Grafana Labs in 2018 as a deliberate alternative to Elasticsearch. Its slogan: "Like Prometheus, but for logs." The design point: index only the labels (the stream identifier), store the content as compressed chunks, accept that grepping at query time is the cost.

### The architecture: distributor, ingester, store

Loki has three core components (plus a few auxiliary ones):

1. **Distributor** — receives log lines from clients (Promtail, OTel collector, Fluent Bit). Validates them, batches them, sends them to ingesters.
2. **Ingester** — buffers log lines in memory by stream (label set), flushes chunks to long-term storage every ~30 minutes.
3. **Store** — the long-term storage. Originally a Cassandra/BigTable schema; in 2026 the standard is S3-compatible object storage (S3, GCS, Azure Blob, MinIO). The index is a separate small store (BoltDB-shipper, TSDB) that maps `(label set) -> (list of chunks)`.

For a kind cluster we run Loki in "single-binary" mode: one pod that does all three roles, backed by local filesystem storage. Production deployments split the three and use object storage; the architecture scales horizontally cleanly.

### Streams and labels

A Loki **stream** is the unit of log organization, identified by a label set. Every log line belongs to exactly one stream. The labels are *not* indexed across content; they are indexed *as* the stream key.

Typical stream labels in a Kubernetes deployment:

- `namespace` — e.g., `default`, `monitoring`, `kube-system`.
- `pod` — the pod name, e.g., `api-deployment-abc123-xyz789`.
- `container` — the container name within the pod, e.g., `api`, `sidecar`.
- `app` — the application label.

That is roughly 4 labels with bounded cardinality (a cluster has dozens of namespaces, hundreds of pods, single-digit containers per pod, dozens of apps). Total stream count: a few thousand. Loki handles this comfortably.

The cardinality footgun is the same as Prometheus: do not put unbounded labels (`user_id`, `trace_id`, `request_id`) into the stream labels. Put them in the log line content; LogQL will find them via grep.

### LogQL

LogQL is the query language. It looks like PromQL but operates on log streams.

The basic shape:

```logql
{namespace="default", app="api"}
```

Returns all log lines from streams matching those labels. A range query over the last 5 minutes:

```logql
{namespace="default", app="api"} [5m]
```

Filters on content:

```logql
{namespace="default", app="api"} |= "error"
{namespace="default", app="api"} != "health"
{namespace="default", app="api"} |~ "timeout|deadline"
```

`|=` is contains, `!=` is does-not-contain, `|~` is regex-match, `!~` is regex-not-match.

Field extraction from JSON logs:

```logql
{namespace="default", app="api"} | json | level="error" | duration_ms > 1000
```

The `| json` parser extracts every JSON field as a queryable attribute. The pipeline filters lines where the `level` field is `error` and the `duration_ms` field is over 1000.

Metrics from logs:

```logql
sum by (route) (rate({namespace="default", app="api"} |= "error" [5m]))
```

This computes the per-second rate of error log lines, grouped by the `route` extracted from the line. The result is an instant vector, identical in shape to a PromQL rate; Grafana can plot it on a time-series panel.

The LogQL reference is at <https://grafana.com/docs/loki/latest/query/>.

### Promtail vs the OpenTelemetry Collector

Loki accepts log lines from any client that speaks its push API. The two canonical clients:

- **Promtail** — Grafana Labs's log-tailing daemon. A DaemonSet that watches every container's stdout/stderr on the node, labels the streams, and pushes to Loki. Simple, narrow, well-tested. The default in the Loki Helm chart.
- **OpenTelemetry Collector** — the unified pipeline. Same DaemonSet pattern, but also collects metrics and traces. Configured via OTel's collector YAML.

For a Kubernetes cluster in 2026, the choice is roughly:

- If you only want logs and you want simplicity, use Promtail.
- If you are unifying logs, metrics, and traces under one agent, use the OpenTelemetry Collector.

We use the OpenTelemetry Collector in this week's mini-project because it is the more general-purpose choice and because we are using OTel for traces anyway. The Promtail path is documented in Exercise SOLUTIONS as an alternative.

### Why Loki is small and fast (and what it gives up)

Loki indexes labels, not content. The index for one cluster's logs is typically ~10 MB. The chunks are gzip-compressed; the storage is roughly 10% the size of the equivalent Elasticsearch index.

The tradeoff: full-text search is slower in Loki than in Elasticsearch, because Loki has to decompress and grep chunks instead of querying an inverted index. For typical operational queries — "show me all the errors from this service in the last hour" — Loki is plenty fast because the label filter narrows to a few streams and the time filter narrows to a few chunks. For "find every log line in any service that ever mentioned this user's ID" — Loki is slow because every chunk must be scanned.

The 2026 best practice is to **use Loki for operational logs and use a separate analytics store (BigQuery, ClickHouse, Iceberg) for ad-hoc text search at scale**. The two systems are complementary; Loki is for "what is happening right now", the analytics store is for "what happened across the last 30 days".

---

## 3. RED — the methodology for request-driven services

The RED method, coined by Tom Wilkie of Grafana Labs (originally Weaveworks), names three metrics that every request-driven service should expose:

- **R**ate — the number of requests per second. Often broken down by route, method, and other route-level dimensions.
- **E**rrors — the number of failed requests per second. The definition of "failed" depends on the service; typically HTTP 5xx, sometimes also HTTP 4xx, sometimes also business-logic failures that returned 200 but did the wrong thing.
- **D**uration — the distribution of request latencies. Always a histogram; never a single average. p50, p95, p99 at minimum.

Three numbers per route. That is enough.

### The PromQL queries

Rate:

```promql
sum by (route) (rate(http_requests_total[5m]))
```

Errors (as a rate):

```promql
sum by (route) (rate(http_requests_total{status=~"5.."}[5m]))
```

Errors (as a fraction):

```promql
sum by (route) (rate(http_requests_total{status=~"5.."}[5m]))
  /
sum by (route) (rate(http_requests_total[5m]))
```

Duration (p95):

```promql
histogram_quantile(
  0.95,
  sum by (route, le) (rate(http_request_duration_seconds_bucket[5m]))
)
```

These three queries are the floor of a service's RED dashboard. Lecture 4 of the mini-project dashboard uses exactly these queries.

### Why RED works

The RED method works because the three numbers are the user's perspective. The user does not care about CPU utilization. The user cares about: did my request go through (rate), did it succeed (errors), and was it fast (duration). A service whose rate is healthy, error fraction is below threshold, and p95 latency is bounded *is* serving its users correctly, regardless of what the CPU charts say.

The corollary: when something is wrong, RED tells you first. The alert that says "p95 latency is now 2 seconds and it was 200 ms an hour ago" is more actionable than the alert that says "CPU on node-7 is 90%". The user feels the latency; the CPU is a means, not an end.

### What RED does not cover

RED is request-driven. For:

- **Queue-based services** — workers that pull from a queue. RED's "rate" still applies (work-items per second), but the "duration" is the per-item processing time, not the request latency. The complementary metric is the queue depth and the queue age, which are gauges.
- **Stream processors** — services that consume from Kafka or similar. RED's "rate" is the consume rate; "duration" is the processing latency per message; an additional critical metric is the consumer lag.
- **Periodic jobs (cron)** — RED does not fit. The relevant metrics are "did the job run on schedule" and "did it complete successfully". These are best modeled as `job_last_success_timestamp_seconds` (a gauge) and an alert on `time() - job_last_success_timestamp_seconds > expected_period`.

RED is the right starting point for an HTTP service. Adjust for the workload shape.

---

## 4. USE — the methodology for resources

The USE method, coined by Brendan Gregg, names three metrics that every resource should expose:

- **U**tilization — the average percentage of the time the resource is busy. For CPU, the fraction of cycles in user/system mode vs idle. For disk, the fraction of time the disk is doing I/O. For memory, the percentage used.
- **S**aturation — the degree to which the resource has extra work it cannot service immediately. For CPU, the run queue length. For disk, the I/O queue length. For memory, the swap-out rate.
- **E**rrors — error count. For CPU, hardware error counters. For disk, read/write error counters. For memory, ECC error counters. For network, packet-drop counters.

Three numbers per resource. The complement to RED.

### Where USE applies

The classic resources:

- **CPU** — utilization (`rate(node_cpu_seconds_total{mode!="idle"}[5m])`), saturation (`node_load1` divided by `count(node_cpu_seconds_total{mode="idle"})`), errors (rare; hardware-specific).
- **Memory** — utilization (`node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes`), saturation (`node_vmstat_pswpout`), errors (ECC; from `node_edac_*`).
- **Disk** — utilization (`rate(node_disk_io_time_seconds_total[5m])`), saturation (`rate(node_disk_io_time_weighted_seconds_total[5m])`), errors (`rate(node_disk_read_errors_total[5m])` if available).
- **Network** — utilization (`rate(node_network_receive_bytes_total[5m])` divided by `node_network_speed_bytes`), saturation (`rate(node_network_receive_drop_total[5m])`), errors (`rate(node_network_receive_errs_total[5m])`).

For pods, the cAdvisor and kube-state-metrics series give you the equivalent per-pod. `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes`, etc.

### Why USE complements RED

RED tells you the service is slow. USE tells you why. The two methods are vertical and horizontal:

- RED across the **service** — five RED dashboards for five services.
- USE down the **stack** — USE the nodes (the hardware), USE the pods (the containers), USE the application (any internal queues or pools).

When the service's p95 latency rises (RED finds it), you walk down the USE stack: are the nodes saturated? are the pods CPU-throttled? is the database connection pool exhausted? Each USE answer narrows the cause.

The mature operational practice has both. Service dashboards are RED-shaped. Infrastructure dashboards are USE-shaped. Alerts fire from both sides, with inhibition rules from Lecture 2 to keep the noise down.

---

## 5. SLIs, SLOs, and error budgets

The vocabulary in this section comes from Google's SRE practice and from the freely-available SRE book. Read chapters 3 and 4 before doing Challenge 1; they are short and they are the canonical source.

### SLI — Service Level Indicator

An SLI is a measurable signal that proxies user-perceived quality. The classic SLIs:

- **Availability** — fraction of requests that returned a non-5xx response.
- **Latency** — fraction of requests served under some threshold.
- **Throughput** — requests per second (not usually an SLI for individual users, but for batch users).
- **Correctness** — fraction of requests where the response was right (harder to measure; usually requires a probe).
- **Freshness** — for caches and reports, how old the data is.

The good SLIs are:

1. **User-centric.** The user can feel the change in the SLI. A CPU utilization SLI is bad because the user does not feel CPU.
2. **Computable from metrics already emitted.** Adding a new SLI should not require new instrumentation.
3. **Bounded and clear.** "Fraction of HTTP requests with status 200-499 over total requests" is bounded \[0, 1] and clear. "Quality of user experience" is neither.

The canonical SLIs for an HTTP service:

```
availability_SLI = count(status in [200..499]) / count(all requests)
latency_SLI = count(duration <= 200ms) / count(all requests)
```

Both expressed as ratios over a window (usually 28 days).

### SLO — Service Level Objective

An SLO is a target on an SLI. "The availability SLI should be at least 99.9% over a 28-day rolling window." Or: "The latency SLI should be at least 99% over a 28-day rolling window".

Choosing the SLO numbers is a *product* decision, not a *technical* decision. The question is: what level of unreliability is the user willing to tolerate before they leave for a competitor? For a payment service, the answer might be "no more than five minutes of unavailability per month" — which is about 99.99%. For a blog comment service, the answer might be "users will not notice an hour per month" — which is about 99.86%.

The SLO is set by talking to the product team, the customer support team, and (where they exist) the customers themselves. It is not set by the engineering team alone. This is one of the harder bits of SRE practice to internalize.

### Error budget — the contract

The error budget is the inverse of the SLO. If the SLO is "99.9% availability", the error budget is "0.1% unavailability". Over 28 days (40,320 minutes), 0.1% is 40.32 minutes. The team has, on average, 40 minutes of allowable unavailability per month.

The contract:

- **When the budget is healthy** (the SLI is meeting the SLO with room to spare), the team can ship aggressively. New features, refactors, infrastructure changes. The budget is the buffer.
- **When the budget is burning** (the SLI is approaching or below the SLO), the team stops shipping and works on reliability. No new features until the budget recovers.

This is the contract that makes SLOs interesting. Without the contract, an SLO is a vanity metric. With the contract, the SLO is the mechanism by which the team self-regulates the velocity-vs-reliability trade-off.

### Burn-rate alerts

The naive alert on an SLO is "alert when the SLO is below target". This is too slow; by the time the 28-day SLI drops below 99.9%, the budget is already spent. The mature alert is on the *burn rate* — how fast the budget is being consumed.

If the 28-day budget is 0.1% (about 40 minutes), and you are currently consuming the budget at the rate of 10x the long-run rate, then you will burn the full budget in about 2.8 days. The Google SRE book recommends paging on:

- **2% of the budget consumed in 1 hour** — fast burn, page immediately. (This is roughly 14.4x the long-run rate.)
- **5% of the budget consumed in 6 hours** — slower burn, page in business hours.

The PromQL for a fast-burn alert (simplified):

```promql
(
  1 - (
    sum(rate(http_requests_total{status!~"5.."}[1h]))
      /
    sum(rate(http_requests_total[1h]))
  )
) > (14.4 * 0.001)
```

Reading: "the error fraction over the last hour exceeds 14.4 times the SLO's allowed error fraction (0.1%)". A nicer formulation uses two windows (a short window for sensitivity, a long window to avoid flapping); the SRE Workbook chapter 5 covers it in detail.

We will write a burn-rate alert in Challenge 1.

### A worked SLO example

Suppose your service serves 1,000,000 requests per day. You set an SLO: 99.9% of requests are served with status < 500 over a 28-day window.

- 28 days = 28,000,000 requests total.
- 0.1% budget = 28,000 errors allowed.
- Currently consuming errors at 100/hour = 2,400/day = 67,200/month, which is 240% of budget. The team is burning.

The implication: stop shipping. Investigate. Fix the failing dependency, the bad release, the noisy neighbor. When the rate drops below the long-run target (100 errors/day = 2,800/28 days), the budget begins to recover. After enough good days, the team can resume shipping.

The exact math is detail. The principle is contract: budget is a fixed thing; consumption rate is variable; the team adjusts behavior to keep consumption inside the budget.

---

## 6. Putting it all together: an instrumented service

The mini-project this week builds an instrumented FastAPI service. The shape of the instrumentation:

1. **Metrics** — `prometheus_client` exposes a `/metrics` endpoint. Counter for requests, histogram for duration, gauge for in-flight requests, counter for errors.
2. **Logs** — Python's `logging` module writes structured JSON to stdout. Every line carries the trace ID (injected by the OTel SDK so logs and traces correlate). The kubelet collects stdout; the OpenTelemetry Collector DaemonSet forwards to Loki.
3. **Traces** — OpenTelemetry SDK auto-instruments FastAPI and emits to the OpenTelemetry Collector via OTLP/gRPC. Manual spans around business logic. The collector forwards to Jaeger.
4. **Dashboards** — Grafana, provisioned via a `ConfigMap`. One dashboard with the RED panels, one panel with the recent error logs (LogQL), one panel with the trace search shortcut.
5. **Alerts** — Prometheus alerting rules in a `PrometheusRule` CRD. ApiHighErrorRate, ApiHighLatency, ApiDown. All with `for:` clauses and runbook URLs.
6. **SLO** — One SLI (`availability` = non-5xx fraction), one SLO (99.5% over 28 days for this toy service), one burn-rate alert.

The result is a single service with the full observability story, all of it checked into Git, all of it reconciled by ArgoCD. When the service misbehaves, you have metrics, logs, and traces from a single instrumented entry point and a dashboard that tells the story.

This is the floor of a 2026 production service. Below this floor, you are operating blind.

---

## 7. The Week-9 ethic, restated

Three principles that bind the week:

1. **Observability is a property, not a tool.** You do not "buy" observability. You design it in. The OpenTelemetry SDK is the substrate; the Prometheus + Loki + Tempo backends are the stores; the dashboards and alerts are the surface.
2. **Code, not UI.** Every dashboard, every alert, every recording rule is YAML in Git. ArgoCD applies it. Grafana renders it. Prometheus evaluates it. The cluster is replaceable; the Git repo is the source of truth.
3. **Budget, not target.** Reliability is a quantity to budget, not a quality to maximize. The error budget is the contract that makes the budget visible. When the budget is healthy, ship. When the budget burns, fix.

The exercises this week practice the first principle by instrumenting a real service. Exercise 4 and the mini-project practice the second. Challenge 1 practices the third. By Sunday, all three should feel like ordinary engineering, not arcane operations.

---

## 8. Reading list before exercises

- The **OpenTelemetry concepts** page: <https://opentelemetry.io/docs/concepts/>. 20 minutes.
- The **OpenTelemetry Python getting-started**: <https://opentelemetry.io/docs/languages/python/getting-started/>. 20 minutes.
- The **Loki architecture** overview: <https://grafana.com/docs/loki/latest/get-started/architecture/>. 15 minutes.
- The **LogQL** reference: <https://grafana.com/docs/loki/latest/query/>. 15 minutes.
- **Chapter 3 of the SRE book** — *Embracing Risk*: <https://sre.google/sre-book/embracing-risk/>. 30 minutes.
- **Chapter 4 of the SRE book** — *Service Level Objectives*: <https://sre.google/sre-book/service-level-objectives/>. 30 minutes.
- Tom Wilkie's RED talk (video, 30 minutes): <https://www.youtube.com/watch?v=zk77VS98Em8>.
- Brendan Gregg's USE method page: <https://www.brendangregg.com/usemethod.html>. 15 minutes.

Total: about 3 hours of reading. Do it across the week, not in one sitting. The SRE book chapters especially repay slow reading.
