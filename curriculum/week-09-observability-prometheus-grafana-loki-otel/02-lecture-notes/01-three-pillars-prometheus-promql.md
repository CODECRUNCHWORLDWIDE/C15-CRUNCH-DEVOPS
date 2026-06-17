# Lecture 1 — The Three Pillars, Prometheus, and PromQL

> *Monitoring is what you do when you already know what you are looking for. Observability is what you do when you do not.*

In Week 8 you stood up a cluster, deployed a service behind an Ingress, and watched ArgoCD reconcile changes from a Git repo. Everything you needed to know about whether the cluster was healthy you could get from `kubectl get pods`. Everything you needed to know about whether the *application* was healthy you could get from `curl https://app.localhost/api/health`. That was sufficient for Week 8 because Week 8 was a deploy story; whether the app worked under load, under load it had not seen before, in a configuration you had not tested — none of those questions were on the table.

This week they are. The question Week 9 is built around is: *when something is wrong with the service, what tells you, and how fast?* The answer in 2026 has three parts — metrics, logs, traces — each of which is a different kind of signal emitted by the application, each of which lands in a different store, and each of which answers a different question. The first lecture is about those three pillars at the conceptual level, then about Prometheus (the canonical store for the first pillar) in depth, and finally about the query language that comes out of Prometheus and that every dashboard you read this week will use: PromQL.

---

## 1. The three pillars, named and distinguished

The "three pillars of observability" is shorthand for **metrics**, **logs**, and **traces**. The phrase is in some sense a marketing simplification — you can build a working observability practice with two of the three, or with traces alone if your tooling is sharp enough — but the three pillars is the framing every existing tool uses, every existing job description references, and every existing book chapter is organized around. So we start with it.

### Pillar 1 — metrics

A metric is a numerical time series. A value (an integer or float) sampled at a regular interval (every 15 seconds, say) with a set of labels that identify the *thing* being measured. The Prometheus exposition format for one sample of one metric looks like this:

```
http_requests_total{method="GET",route="/api/health",status="200"} 14732 1731715200000
```

Five things:

- `http_requests_total` — the metric name. By convention, snake_case, with a `_total` suffix on counters.
- `{method="GET",route="/api/health",status="200"}` — the label set. Three labels here. Each unique combination of label values is a separate time series.
- `14732` — the value at this sample.
- `1731715200000` — the timestamp in milliseconds since the Unix epoch (optional in scrape responses; Prometheus assigns one if absent).
- The implicit type — `counter` in this case; we will get to the four types in Section 3.

What metrics are good at:

- **Aggregation across many sources is cheap.** You can sum the request count across 100 pods of one service by adding 100 small numbers.
- **Storage is small.** A few bytes per sample. A year of 15-second-interval metrics for one time series is ~2 MB.
- **Alerting is fast.** A PromQL expression evaluated every 30 seconds against a time series is cheap to compute.
- **Dashboards are fast.** A range query over a million samples returns in milliseconds because the samples are stored in a compressed columnar format that is cheap to scan.

What metrics are bad at:

- **High cardinality.** Each unique label combination is a new series, which doubles storage and triples query cost. A label like `user_id` (which can take a million values) is a footgun; the system will be unusable in a week.
- **Per-request detail.** A metric is an aggregate; you cannot, from a metric, reconstruct which one of the 14,732 requests returned a 500 last Thursday at 14:23:17. You need logs or traces for that.
- **String content.** Metrics carry numbers, not text. The error message that came back with the 500 is not in the metric.

The canonical metric store is **Prometheus**, the subject of this lecture. The other contenders — InfluxDB, M3DB, TimescaleDB, Cortex (Prometheus-as-a-service), Mimir (Grafana's distributed Prometheus), VictoriaMetrics, Thanos (Prometheus-with-object-storage-backed-long-term-retention) — all speak the Prometheus exposition format and most accept PromQL queries. The standard is set. Choose Prometheus or a Prometheus-API-compatible alternative; do not choose anything that is not. (We say more on this in Lecture 3.)

### Pillar 2 — logs

A log line is a text event with a timestamp and, optionally, some structured fields. The canonical structured-log shape in 2026 is JSON:

```json
{"ts":"2026-05-14T14:23:17.118Z","level":"error","route":"/api/hello","msg":"upstream timeout","user_id":"u-77231","trace_id":"4bf92f3577b34da6a3ce929d0e0e4736"}
```

Or, less ideally but still common, an unstructured text line:

```
2026-05-14T14:23:17.118Z [ERROR] /api/hello: upstream timeout for user u-77231 trace=4bf92f3577b34da6a3ce929d0e0e4736
```

Structured logs are correct. Unstructured logs are common. The Week 9 stack — Loki with LogQL — accepts both, but you will write structured logs in the FastAPI service this week because parsing fields out of text at query time is wasteful when you could have written them as keys at emit time.

What logs are good at:

- **High cardinality** is fine. Loki indexes only the *labels* on the log stream, not the content. A log line with `user_id=u-77231` does not create a new index entry; it just lands in the content of the `{service="api"}` stream.
- **Per-event detail.** Every line is one event with full context: the exception trace, the request body, the user ID, the trace ID linking back to the trace pillar.
- **Forensics.** When something has gone wrong, the logs are where you find what happened, in detail, in order.

What logs are bad at:

- **Aggregation is expensive.** Counting "how many errors in the last hour" by scanning a million log lines is slower than reading one PromQL counter that increments on each error.
- **Storage is large.** A typical log line is 200-500 bytes. A busy service emits 10,000 lines per second. That is 10 GB per hour per service.
- **Cardinality of *labels* still matters.** Loki labels (the stream identifiers, not the content) follow the same cardinality rules as Prometheus labels. Do not put `user_id` in a Loki label. Put it in the line content; Loki will find it via grep.

The canonical log store in the open-source 2026 stack is **Loki**. The historical canonical store was Elasticsearch (and the ELK stack — Elasticsearch + Logstash + Kibana). Elasticsearch is heavier, indexes every term, and consequently has unbounded storage and CPU costs. Loki was designed by Grafana Labs as the deliberate alternative: index only the labels, store the content as compressed chunks, and accept that grepping the content at query time is the cost paid. Lecture 3 covers Loki in detail.

### Pillar 3 — traces

A trace is a directed acyclic graph of **spans**, one trace per request, with all spans sharing a single **trace ID**. Each span represents a unit of work: an HTTP handler, a database call, an internal function. Spans have a start time, a duration, a parent span ID, and a name. The shape looks like this (simplified):

```
trace 4bf92f3577b34da6a3ce929d0e0e4736
+-- span "GET /api/hello"               (1.2 ms total)   [api-service]
    +-- span "fetch user from postgres"   (0.4 ms)         [api-service]
    +-- span "render greeting"            (0.1 ms)         [api-service]
    +-- span "call upstream notifier"     (0.6 ms)         [api-service]
        +-- span "POST /notify"             (0.5 ms)         [notifier-service]
            +-- span "redis SET"              (0.2 ms)         [notifier-service]
```

Six spans, two services, one trace ID. The trace tells a complete causal story of how one user's request flowed through the system.

What traces are good at:

- **Cross-service causality.** Which call in service A caused which call in service B? A trace makes it explicit because the parent-child relationship crosses the network.
- **Latency forensics.** Which span in a slow request was the slow one? A trace shows you in the UI as a flame graph.
- **Unknown unknowns.** Per Charity Majors's definition of observability, traces let you ask questions about behavior you did not anticipate. "Show me all traces where the postgres span took >100 ms and the user was on a free plan" is a query you would not have known to write as a metric or a log filter.

What traces are bad at:

- **Volume.** Tracing every request is expensive. Production systems sample — keep 1% of traces, or every trace from one in 100 users, or every trace that includes an error.
- **Aggregation.** A trace is one request. Computing "the p95 latency of the postgres call across all requests in the last hour" from traces alone is possible but expensive; it is the kind of question metrics answer faster.
- **Storage cost.** A single trace is small (~5 KB) but a busy service produces millions of traces a day. Even at 1% sampling, the storage adds up.

The canonical trace stores in the open-source 2026 stack are **Tempo** (Grafana Labs's newer system, designed for object-storage-backed scale) and **Jaeger** (the older CNCF project, simpler operationally). Both accept the OpenTelemetry Protocol (OTLP) and both are visualized in Grafana via the Tempo data source. We use Jaeger in the exercises this week because its single-binary mode is the easiest to install on `kind`. Lecture 3 covers OpenTelemetry — the instrumentation SDK — and the trace pillar in detail.

### The pillars together

A useful mental model: the three pillars are **three different views of the same event**.

A single HTTP request to your service produces:

- One increment to the `http_requests_total{route="/api/hello"}` counter — a tiny update to a metric time series.
- One JSON log line emitted by the request handler, structured, with the user ID and the trace ID — a row in a log stream.
- One trace, with spans for the HTTP handler, the database call, and any downstream service calls — a graph in the trace store.

When the service is healthy, you look at the metrics. When something is wrong, you start with the metrics (to see what is wrong), pivot to the logs (to see the error messages), and pivot to the traces (to see *why* the error happened across services). Each pillar has its job. The mature observability practice has all three and connects them through correlation fields (the trace ID appears in both logs and traces; the service label appears in metrics and logs).

The 2026 best practice — and the practice we will build this week — is to emit all three from one SDK (OpenTelemetry) so the correlation is automatic. We will revisit this in Lecture 3.

---

## 2. Why Prometheus is the metrics store you choose

There were many metrics stores in 2014. Graphite, OpenTSDB, InfluxDB, Datadog, New Relic, the home-grown StatsD pipelines, the home-grown carbon-data pipelines. In 2026 there is one open-source default for cluster-native systems and it is **Prometheus**. The reasons are worth naming because they explain the design.

### Reason 1 — pull, not push

Prometheus *scrapes* its targets. The targets do not push to Prometheus; Prometheus dials them every `scrape_interval` seconds (default 15s), reads `/metrics`, and stores the result. This is the inverse of StatsD-style push systems.

The arguments for pull:

- **Targets self-describe.** The target's `/metrics` endpoint is the source of truth. There is no separate registration step. Adding a new pod means the pod exists with `/metrics` exposed and Prometheus discovers it.
- **Discovery is centralized.** Prometheus knows the universe of targets because it owns the discovery loop. In Kubernetes, it uses the API server as the discovery source: it watches `Pod` and `Service` and `Endpoints` and computes the scrape target list dynamically.
- **Broken scrapes are visible.** When Prometheus cannot reach a target, the target's `up` metric goes to 0 and Prometheus emits a `scrape_duration_seconds` of a particular shape. In a push system, a target that has stopped pushing looks identical to a target that is running fine but has no events to report. Prometheus distinguishes the two.
- **Operational simplicity.** Targets do not need to know where Prometheus lives. They just expose a port.

The arguments against pull (for completeness):

- **Push is more natural for short-lived jobs.** A cron job that runs for 10 seconds is dead by the time Prometheus next scrapes. Prometheus solves this with the **Pushgateway** — a small intermediary that holds pushed metrics until Prometheus scrapes it.
- **Push works better through one-way NATs.** If your target lives behind a NAT that Prometheus cannot reach, you have to push.

In practice, on a Kubernetes cluster, pull is the right answer. The Pushgateway is for the cron-job edge case. Everything else scrapes.

### Reason 2 — the exposition format is plain text

The Prometheus exposition format is line-oriented text. You can `curl` it:

```bash
$ curl -s http://localhost:8080/metrics | head -8
# HELP http_requests_total Number of HTTP requests served.
# TYPE http_requests_total counter
http_requests_total{method="GET",route="/api/health",status="200"} 14732
http_requests_total{method="GET",route="/api/hello",status="200"} 8341
http_requests_total{method="GET",route="/api/hello",status="500"} 12
# HELP process_resident_memory_bytes Resident memory size in bytes.
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes 4.521728e+07
```

Plain text. No SDK required to emit. No SDK required to read. You can `grep` and `awk` against it. You can copy it into a doc. You can diff two versions of it. The format is the API; the API is text. This decision — text format, not protocol buffer over gRPC — is a large part of why Prometheus won. (For the record: Prometheus also accepts an **OpenMetrics** binary format, which is the more efficient version of the same model, but the text format is what every tutorial and most production exporters use.)

The four metric types in the format:

- **counter** — monotonically increasing, resets to 0 only when the process restarts. Suffix convention: `_total`. Example: `http_requests_total`.
- **gauge** — a value that can go up or down. No suffix convention. Example: `process_resident_memory_bytes`, `queue_depth`.
- **histogram** — a counter of observations bucketed by value, with a `_bucket{le="<upper-bound>"}` series per bucket plus a `_sum` and `_count`. Used for distributions: latency, response size. Example: `http_request_duration_seconds_bucket`.
- **summary** — similar to histogram but pre-aggregated client-side into quantiles (p50, p95, p99). Older, harder to aggregate across instances, generally avoided in 2026 in favor of histograms.

The default is to use **counters** for things you count, **gauges** for things you measure, and **histograms** for things you distribute. Summaries are a third-system-effect mistake of the early Prometheus era. If you find yourself reaching for a summary in 2026, reach for a histogram instead.

### Reason 3 — the data model is labels and time series

A Prometheus time series is identified by the *combination* of its metric name and its label set. `http_requests_total{method="GET",route="/api/health"}` is a different series from `http_requests_total{method="POST",route="/api/health"}` and from `http_requests_total{method="GET",route="/api/hello"}`. Each unique combination is one series.

The implication is **cardinality**. The cardinality of a metric is the product of the unique values of each label. A metric with labels `method` (5 values), `route` (10 values), and `status` (10 values) has cardinality 500: 500 distinct series. Prometheus can handle millions of series comfortably; it cannot handle billions.

The footgun is putting a high-cardinality field in a label. Things you should never put in a label:

- **User ID, customer ID, request ID, trace ID, session ID.** These have effectively unbounded cardinality. Put them in logs or traces; do not put them in metric labels.
- **URL with query parameters.** A label `url="/api/hello?name=Alice"` is different from `url="/api/hello?name=Bob"`. Normalize to a route template: `route="/api/hello"`.
- **IP addresses, especially client IPs.** Unbounded.
- **Timestamps.** Always unbounded.

The rule: **labels are for the dimensions you will aggregate on**, not for the dimensions you will look up by. Aggregate on `method`, `route`, `status`, `service`, `namespace`, `pod_name`. Look up by `user_id` in the logs.

### Reason 4 — the operational model is one binary

A Prometheus server is one Go binary that reads one YAML configuration file, scrapes a list of targets, and writes a local TSDB to disk. That is the entire operational model. There is no required external dependency. No database. No message queue. No coordinator. Just the binary.

For scale beyond a single binary — multi-region, multi-year retention, federated queries — there are layered systems: Thanos, Cortex, Mimir, Promscale. Each takes the same Prometheus model and extends it. But the floor is one binary, and for the workload most teams have, the floor is sufficient. A Prometheus server on a $40/month VM can comfortably handle 1-2 million active series. Most clusters at most companies are well below that limit.

### Reason 5 — the open-source community is mature

Prometheus is a CNCF graduated project. Released in 2012, donated to CNCF in 2016, graduated in 2018. It has had a stable release cadence for a decade. Every Kubernetes distribution ships with `kube-state-metrics` and `node-exporter` integrations. Every major framework (Spring, Express, Django, Flask, FastAPI, Rails, Go's net/http, .NET's Kestrel) has a Prometheus exporter. Every observability vendor speaks the Prometheus protocol. The standardization is real.

---

## 3. Prometheus scraping in Kubernetes

In a Kubernetes cluster, Prometheus discovers its targets via the API server. The canonical Helm chart we use this week — `kube-prometheus-stack` — installs the **Prometheus Operator**, which turns scrape configuration from raw YAML into a Kubernetes CRD: the `ServiceMonitor`.

### The `ServiceMonitor` CRD

A `ServiceMonitor` is a thin object that selects a set of `Service` resources by labels and tells Prometheus to scrape every endpoint behind those services. The shape:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: api-service
  namespace: monitoring
  labels:
    release: kube-prometheus-stack
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: api
  namespaceSelector:
    matchNames:
      - default
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
      scrapeTimeout: 10s
```

What every line does:

- `apiVersion: monitoring.coreos.com/v1` — the Prometheus Operator's CRD group. The version is `v1`, stable since 2019.
- `metadata.labels.release: kube-prometheus-stack` — this label is how the Prometheus instance discovers which `ServiceMonitor` objects to include. By default, the `kube-prometheus-stack` chart configures Prometheus to watch only `ServiceMonitor`s with this label. If you forget the label, your scrape config is ignored silently. We will repeat this in Exercise 2.
- `spec.selector.matchLabels.app.kubernetes.io/name: api` — selects `Service` objects whose pods have this label.
- `spec.namespaceSelector.matchNames: [default]` — only look in the `default` namespace. Without this, every namespace matches.
- `spec.endpoints[0].port: http` — the *named port* on the `Service` to scrape. The Service must have a port named `http`. (You can also use `targetPort` with a port number, but named ports are the convention.)
- `spec.endpoints[0].path: /metrics` — the HTTP path. `/metrics` is the convention; some apps expose `/actuator/prometheus` (Spring) or `/admin/metrics` (custom). Override as needed.
- `spec.endpoints[0].interval: 15s` — how often Prometheus scrapes. 15s is the Prometheus default; 30s is also common; 1m is fine for low-importance metrics.
- `spec.endpoints[0].scrapeTimeout: 10s` — the per-scrape timeout. Should always be less than the interval.

### The equivalent raw `prometheus.yml`

If you are not using the Operator (some teams choose not to), the equivalent scrape configuration in raw `prometheus.yml` is:

```yaml
scrape_configs:
  - job_name: api-service
    kubernetes_sd_configs:
      - role: endpoints
        namespaces:
          names: [default]
    relabel_configs:
      - source_labels: [__meta_kubernetes_service_label_app_kubernetes_io_name]
        action: keep
        regex: api
      - source_labels: [__meta_kubernetes_endpoint_port_name]
        action: keep
        regex: http
    scrape_interval: 15s
    scrape_timeout: 10s
    metrics_path: /metrics
```

Same effect; more YAML. The Operator's value is that it makes the common case (one ServiceMonitor per Service) declarative and short.

### Cluster-level metrics: node-exporter, kube-state-metrics, cAdvisor

The `kube-prometheus-stack` chart installs three cluster-level metric sources that you do not have to write:

- **node-exporter** — a DaemonSet (one pod per node) that exposes Linux kernel metrics: CPU per core, memory, disk I/O, network bytes, filesystem usage. Metrics prefix: `node_*`. Example: `node_cpu_seconds_total{mode="user",cpu="0"}`.
- **kube-state-metrics** — a Deployment that watches the Kubernetes API and emits metrics about Kubernetes objects: `kube_pod_status_phase{phase="Running"}`, `kube_deployment_status_replicas`, `kube_node_status_condition`. This is how you ask Prometheus "how many pods are in CrashLoopBackOff right now".
- **cAdvisor** — built into the kubelet on every node, exposes per-container resource usage. Metrics prefix: `container_*`. Example: `container_memory_usage_bytes{pod="api-xyz",namespace="default"}`.

Together, these three give you a complete picture of cluster and workload state without your application emitting anything. You add your application's metrics on top. That is what we do in Exercise 2.

### Scrape interval — the choice

15 seconds is the Prometheus default and the right default for most metrics. The reasoning:

- Shorter than 10 seconds is rarely useful. Your alert rules will average over `[1m]` or `[5m]` ranges; 4-5 samples per range is enough.
- Longer than 30 seconds blurs short spikes. A 60-second saturation event will show up as a small bump on a 30s scrape and as a flat line on a 5m scrape.
- Per-target overrides are fine. Cluster-level metrics that change slowly (`kube_deployment_status_replicas`) are happy at 30s. Latency histograms during a load test might want 5s, briefly.

The cost is linear in scrape rate. A doubling of the scrape interval doubles the storage and the query cost. Do not panic-tune it.

---

## 4. PromQL from the ground up

PromQL is the query language Prometheus exposes for reading the time series it has stored. You will write PromQL all week — in the Grafana dashboards, in the alerting rules, in the ad-hoc exploration. It is worth learning carefully.

### The four query result types

A PromQL expression evaluates to one of four shapes:

1. **Instant vector** — a set of time series, each with one value, at one timestamp. Example: `http_requests_total`. The result is "for every unique label combination, the current value of this counter".
2. **Range vector** — a set of time series, each with a *list* of values, over a time range. Example: `http_requests_total[5m]`. The result is "for every unique label combination, all the samples from the last 5 minutes". You cannot graph a range vector directly; you apply a function to it.
3. **Scalar** — a single number. Example: `count(up == 1)`. (Actually this returns an instant vector with one element, which is convertible to a scalar.) Pure scalars are rare in practice.
4. **String** — almost never used in PromQL. Mentioned here for completeness.

The graphing tools always render instant vectors over time (one point per evaluation step). What you build in PromQL is a chain that ends in an instant vector.

### The `rate()` function and why range vectors exist

The single most important PromQL function for counters is `rate()`. It takes a range vector and returns an instant vector: the per-second rate of increase, averaged over the range.

```promql
rate(http_requests_total[5m])
```

This says: "for each label combination, compute the per-second rate of HTTP requests, averaged over the last 5 minutes".

Why `[5m]` and not just `http_requests_total`? Because a counter is monotonically increasing; reading its current value tells you the total since process start. You almost never want that. You want the per-second rate, and the per-second rate is computed by dividing the value-increase by the time-elapsed across some range. `rate()` does that math; you give it the range.

The corollary: **always use `rate()` on counters, never on gauges**. A gauge can go up and down; `rate(gauge[5m])` is mathematically meaningless. Use `delta()` or `deriv()` for gauges instead, or just plot the gauge directly.

### `rate()` vs `irate()`

There is a second function, `irate()`, that returns the rate over the *last two samples* in the range vector. The difference:

- `rate([5m])` averages over 5 minutes. Smooths out spikes; shows the long-run rate.
- `irate([5m])` looks only at the last two samples within that 5-minute window. Shows the most recent rate; spikes are visible.

The rule of thumb: **use `rate()` for alerts and dashboards. Use `irate()` only when you specifically need spike-visibility, and only when you understand the failure mode** (if the scrape interval is longer than the irate's range, irate returns nothing).

### Histograms and `histogram_quantile()`

Histograms are the metric type for distributions. The Prometheus histogram is a set of cumulative buckets: how many observations were `<= 0.1s`, how many were `<= 0.25s`, how many were `<= 0.5s`, how many were `<= 1s`, and so on, up to a `+Inf` bucket that always contains the total count.

The naming convention: a histogram of `http_request_duration_seconds` produces:

- `http_request_duration_seconds_bucket{le="0.1"}` — count of requests with duration <= 0.1s.
- `http_request_duration_seconds_bucket{le="0.25"}` — count of requests with duration <= 0.25s.
- ...
- `http_request_duration_seconds_bucket{le="+Inf"}` — total count.
- `http_request_duration_seconds_sum` — sum of all durations.
- `http_request_duration_seconds_count` — total count (same as the `+Inf` bucket).

To compute the p95 latency, you use `histogram_quantile()`:

```promql
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))
```

Three layers, inside out:

1. `rate(http_request_duration_seconds_bucket[5m])` — per-second rate of each bucket. (The buckets are counters, so you take their rate.)
2. `sum by (le) (...)` — sum across all label dimensions *except* `le`. This collapses pods, instances, replicas — anything you do not want to slice on. The `le` label has to survive because `histogram_quantile` needs it.
3. `histogram_quantile(0.95, ...)` — compute the 95th-percentile latency from the bucketed distribution.

The result is an instant vector with one element per remaining label combination (in this case, one element total) whose value is "the 95th percentile of HTTP request latency over the last 5 minutes".

**The bucket bounds are a design choice you make at instrumentation time, not at query time.** If you instrument with buckets at `[0.1, 0.25, 0.5, 1, 2.5, 5]` and your real p99 latency is 6 seconds, `histogram_quantile(0.99, ...)` will return `+Inf` because the data falls outside the bucket range. We will see this in Exercise 3 and adjust.

### Labels: aggregation, matching, and `by` vs `without`

PromQL aggregates with `sum`, `avg`, `min`, `max`, `count`, `stddev`, `stdvar`, `topk`, `bottomk`. Each takes an `instant vector` and aggregates across some subset of labels:

```promql
sum by (service, namespace) (rate(http_requests_total[5m]))
```

"Per-service per-namespace request rate".

The dual:

```promql
sum without (instance, pod) (rate(http_requests_total[5m]))
```

"Sum across all labels *except* keep all labels other than `instance` and `pod`". Same shape; different grammar.

When in doubt, prefer `by`. It is the more common form and the easier to read.

### `topk`, `bottomk`, `absent()`

Three operators worth memorizing:

- `topk(5, rate(http_requests_total[5m]))` — the five highest-rate request series. Useful for "which routes are the busiest right now".
- `bottomk(5, ...)` — the five lowest. Useful for "which routes are getting no traffic" — sometimes the absence is the signal.
- `absent(up{job="api-service"})` — returns a value if the series is missing entirely. Useful for "alert me when the scrape target disappears". The standard alert idiom is `for: 5m`, `expr: absent(up{job="api"})`.

### A cardinality footgun and how to spot it

If you write this query:

```promql
rate(http_requests_total[5m])
```

and the response is 50,000 series, you have a cardinality problem. The fix is to find the high-cardinality label and remove it from the metric. The query to find which label is exploding:

```promql
count by (label_name) (count by (label_name, label_value) (http_requests_total))
```

(Imperfect; the real diagnostic involves looking at `__name__` and counting distinct values per label.) The Prometheus UI's `tsdb-status` page (`/tsdb-status`) shows the top label-value cardinalities, which is the quickest way to spot the offender.

We will see a real cardinality explosion in Challenge 2 and you will diagnose it.

---

## 5. Recording rules and alerting rules

PromQL is fast. Some PromQL is faster than others. A query that aggregates across 100,000 series and joins against another 100,000 series can take seconds to evaluate. When that query is on a dashboard that 50 engineers load 100 times a day, the cumulative cost is real.

**Recording rules** are PromQL queries pre-evaluated by Prometheus at the scrape interval and stored as new metrics. The pattern:

```yaml
groups:
  - name: api-recording
    interval: 30s
    rules:
      - record: api:http_requests_per_second
        expr: |
          sum by (route, status) (
            rate(http_requests_total[1m])
          )
```

What this does: every 30 seconds, Prometheus evaluates the expression and writes the result as new time series named `api:http_requests_per_second{route=..., status=...}`. A dashboard query that reads `api:http_requests_per_second` is now reading one pre-computed series instead of re-evaluating a `rate` and a `sum` over a `[1m]` range vector.

**Convention:** the recording-rule name uses a colon to distinguish it from a raw metric. `api:http_requests_per_second` is a recording rule. `http_requests_total` is a raw metric. This convention is from the Prometheus best-practices page.

**Alerting rules** are PromQL boolean conditions that fire as alerts when true for a duration:

```yaml
groups:
  - name: api-alerting
    rules:
      - alert: HighErrorRate
        expr: |
          sum by (service) (rate(http_requests_total{status=~"5.."}[5m]))
            /
          sum by (service) (rate(http_requests_total[5m]))
            > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Error rate on {{ $labels.service }} above 5% for 5 minutes"
          runbook: "https://wiki.example.com/runbooks/high-error-rate"
```

Reading top-down:

- `alert: HighErrorRate` — the alert name. Appears in Alertmanager and in pages.
- `expr: ...` — the boolean condition. Here: error-rate / total-rate > 5%.
- `for: 5m` — the condition must hold continuously for 5 minutes before the alert fires. Filters out single-sample noise.
- `labels.severity: warning` — labels are how Alertmanager routes alerts to receivers. We will use them in Lecture 2.
- `annotations.summary` — human-readable description; templated with `{{ $labels.service }}` so the receiver sees the actual service name.
- `annotations.runbook` — link to the runbook. **Every alert needs a runbook link**, because every alert that wakes someone up at 3 a.m. is an alert that needs to be answerable at 3 a.m. without thinking.

Recording rules and alerting rules are the same YAML grammar; the `record:` and `alert:` fields distinguish them. Both are loaded into Prometheus by the `PrometheusRule` CRD (or by raw `rule_files:` in `prometheus.yml`). We will write both in Exercise 2.

---

## 6. What we have skipped

This lecture deliberately did not cover:

- **Long-term storage.** Prometheus has a default retention of 15 days. For longer retention, you stack Thanos or Cortex or Mimir on top of Prometheus. Out of scope for this week; the kind cluster does not need it.
- **High availability.** Production Prometheus is deployed in pairs (active-active) with deduplication at query time, typically via Thanos. The `kube-prometheus-stack` chart can do this with `replicas: 2`. Out of scope; the kind cluster has one replica.
- **Federation.** Multi-cluster Prometheus federation, where a top-level Prometheus aggregates from many sub-Prometheuses. Out of scope; we have one cluster.
- **The OpenMetrics binary protocol.** A faster wire format that Prometheus and some clients can negotiate. Not strictly needed; the text format works everywhere.
- **The exposition format details for histograms with `_created` timestamps.** Subtle; covered in the Prometheus docs.

We pick up Grafana and Alertmanager in Lecture 2, and Loki, traces, OpenTelemetry, and SLOs in Lecture 3.

---

## 7. Reading list before Lecture 2

- The **introduction page** of the Prometheus docs: <https://prometheus.io/docs/introduction/overview/>. 10 minutes.
- The **best-practices** page on naming and labels: <https://prometheus.io/docs/practices/naming/>. 15 minutes.
- The **best-practices** page on histograms vs summaries: <https://prometheus.io/docs/practices/histograms/>. 15 minutes.
- The **PromQL basics** page: <https://prometheus.io/docs/prometheus/latest/querying/basics/>. 20 minutes.
- **Chapter 6 of the SRE book** — *Monitoring Distributed Systems*: <https://sre.google/sre-book/monitoring-distributed-systems/>. 45 minutes.

That is roughly 105 minutes. Do it in two sittings if needed. The PromQL queries you write in Exercise 2 will lean on the *naming* and *basics* pages especially.
