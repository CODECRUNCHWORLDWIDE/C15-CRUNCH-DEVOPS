# Solutions — Week 9 Exercises

Worked answers to the four exercises. Read them after you have attempted each exercise, not before. The point of an exercise is the struggle; the solution is the calibration.

---

## Exercise 1 — Install `kube-prometheus-stack`

### Q1. Why is the Prometheus pod a `StatefulSet` and not a `Deployment`?

Prometheus writes its TSDB (time-series database) to local disk. A `Deployment` allows any pod replica to land on any node and the volumes do not follow; a rolling update would lose data when the new pod cannot find the previous pod's PV. A `StatefulSet` gives each replica a stable network identity (`prometheus-kps-...-prometheus-0`) and a stable `volumeClaimTemplate` that follows the replica across restarts. The TSDB is durable because the replica's PVC is durable.

For HA, you would scale the StatefulSet to 2 replicas and the chart would create two independent TSDBs, each with its own PVC. Deduplication at query time happens via Thanos or equivalent.

### Q2. What does `kube_pod_status_phase{phase="Pending"}` tell you that `kubectl get pods` does not?

`kubectl get pods` is a point-in-time snapshot. `kube_pod_status_phase{phase="Pending"}` is a time series. The metric lets you ask "how many pods were stuck in Pending over the last 24 hours, per namespace" — which is a pattern question, not a snapshot question. The alert rule `kube_pod_status_phase{phase="Pending"} > 0 for 10m` is the canonical "something is wrong with scheduling" alert, and you cannot write it on top of `kubectl`.

### Q3. Where in the running Prometheus pod is the scrape configuration stored, and how does the Operator update it?

The Prometheus Operator generates the final `prometheus.yml` from all `ServiceMonitor`, `PodMonitor`, and `Probe` CRDs, serializes it, gzips it, base64-encodes it, and stores it in a Secret named `prometheus-<release>-kube-prometheus-stack-prometheus`. The Prometheus pod mounts that Secret at `/etc/prometheus/config_out/prometheus.env.yaml`. A sidecar container, `config-reloader`, watches the Secret and POSTs to Prometheus's `/-/reload` endpoint when it changes. The config-reload happens within a few seconds; you never restart Prometheus.

### Q4. If you scaled Prometheus to 2 replicas, what would change in the storage layer?

Two replicas each get their own PVC (the `volumeClaimTemplates` produces one PVC per replica index: `prometheus-kps-...-prometheus-0` and `prometheus-kps-...-prometheus-1`). Each scrapes the same targets independently. Each writes its own TSDB. The two TSDBs are not synchronized; they may have slightly different sample timestamps because the scrape clocks are independent.

Querying the deduplicated view requires a layer on top (Thanos Query, Mimir, or Cortex). Without that layer, you would have to pick one Prometheus to query and live with the duplicate when one is down.

---

## Exercise 2 — ServiceMonitor and PrometheusRule

### Q1. Why is `for: 2m` important? What if it were `for: 0s`?

`for:` is the duration the alert condition must hold continuously before the alert fires. With `for: 0s`, every single evaluation that finds the condition true (every 30 seconds in this rule) fires immediately. A one-sample blip — a transient network failure, a momentary scrape miss — pages the on-call. With `for: 2m`, the condition must be true for four consecutive evaluations. Blips are filtered.

The trade-off: a higher `for:` means slower detection. For critical alerts, you might want `for: 1m`. For low-priority alerts, `for: 10m` is fine. The default in the upstream chart's rules is mostly `for: 5m` for service-level alerts and `for: 15m` for capacity alerts.

### Q2. Recording rule interval (30s) vs alerting rule `for: 2m`

Different concepts:

- **Recording rule interval** — how often Prometheus evaluates the expression and writes the result to a new time series. Every 30 seconds, the recording rule computes the current `sum(rate(emitter_requests_total[1m]))` and stores it as `emitter:requests_per_second`.
- **Alerting rule `for: 2m`** — the alert evaluates every `interval` (also 30s in our config). When the boolean is true, the alert moves to "Pending". It stays Pending until 2 minutes of continuous truth have passed; only then does it move to "Firing".

If you set the recording interval to 5 minutes, the recording series would update only every 5 minutes; alerts on top of it would have less-frequent data to evaluate.

### Q3. If you delete the `release: kps` label from PrometheusRule, what happens?

By default, the `kube-prometheus-stack` chart configures Prometheus to watch only `PrometheusRule` objects with `release: <release-name>` label. Without the label, Prometheus does not pick up the rule. The alert never evaluates; the recording rule never produces its series.

We changed this default in Exercise 1 by setting `ruleSelectorNilUsesHelmValues: false`, which makes the Operator pick up *all* rules regardless of label. So in our cluster, removing the label actually still works — but in a default chart install, it would not. We explicitly relaxed the selector to avoid label gymnastics during teaching.

Production teams usually leave the selector strict and standardize on the chart's release label. The relaxed config makes the kind cluster easier; do not carry it into production.

### Q4. Why is `send_resolved: true` important on the webhook receiver?

By default, Alertmanager sends a notification only when an alert *starts* firing. When the alert resolves, no notification goes out. `send_resolved: true` tells Alertmanager to also POST a `status: resolved` payload when the alert clears.

Without `send_resolved: true`, the Slack channel (or webhook) accumulates "X is broken" messages and never gets "X is fixed" — the on-call has to remember which alerts they have already triaged. With it, the channel becomes a chat between Alertmanager and the team, with both sides of every conversation.

---

## Exercise 3 — Instrument FastAPI with OpenTelemetry

### Q1. Why send via the OpenTelemetry Collector, not directly to Jaeger?

Three reasons:

1. **Decoupling.** The application speaks OTLP. The collector speaks OTLP to Jaeger today, Tempo tomorrow, Datadog next quarter. Changing backends is a collector config change, not a redeploy of every service.
2. **Batching and back-pressure.** The collector buffers, batches, and retries. If Jaeger is briefly down, the collector queues; the application does not block.
3. **Processing.** The collector runs processors: tail sampling, attribute filtering, redaction, attribute enrichment with k8s metadata. None of those belong in the application code path.

For a single-service kind cluster, the collector is overkill. For any real environment, it is the right architecture. We use it from day one so the muscle memory builds.

### Q2. BatchSpanProcessor vs SimpleSpanProcessor

- **SimpleSpanProcessor** — exports every span immediately, synchronously, in the request thread. Adds 1-5 ms to every request even if export is fast; multiplies if it is slow. Used in tests; not production.
- **BatchSpanProcessor** — buffers spans in a background queue and exports them in batches every few seconds or when the queue reaches a threshold. Adds ~no latency to the request path. The right default.

Trade-off: the batch processor can drop spans if the queue fills (the process crashes while spans are buffered, or the queue overflows). For 100% trace capture you would need a more durable buffer (write spans to disk first); few teams need that level of guarantee.

### Q3. Why is `service.name` a resource attribute, not a span attribute?

A **resource attribute** is set once per process and attached to every span (and every metric, every log) emitted by that process. `service.name`, `service.version`, `deployment.environment`, and the Kubernetes pod / node / namespace are all resource attributes. They identify the *source* of telemetry.

A **span attribute** is set per span and describes the operation that span represents. `http.method`, `http.status_code`, `greeting.locale` — these are per-operation.

Putting `service.name` on every span individually would be wasteful (duplicate data) and error-prone (different spans could have different service names if the developer forgot to set it). The resource model fixes it at process boot.

### Q4. Sampling: what would change for production?

The SDK's default is `ParentBased(AlwaysOn)` — sample every trace, propagate the decision to child spans. Fine for kind; not fine for production.

Three production strategies:

1. **Head sampling at low rate** — `TraceIdRatioBased(0.01)` keeps 1% of traces. Random. Loses interesting traces (errors, slow ones) at the same rate as boring ones. Cheap. The default for many teams.
2. **Tail sampling in the collector** — keep every error trace, keep every slow trace, sample 1% of the rest. Configured in the collector's `tail_sampling` processor. Expensive (the collector buffers all spans for a trace) but the right answer for teams that can afford it.
3. **Adaptive sampling** — sample at a target rate (e.g., 10 traces/sec) and let the system increase the rate when error rates rise. Vendor-specific in 2026; the OpenTelemetry spec has a draft for it.

For a $100M-revenue company, tail sampling. For a $1M-revenue company, head sampling at 1-10% is fine. For a side project, sample everything.

---

## Exercise 4 — Grafana Dashboard as Code

### Q1. What does `schemaVersion` do?

Grafana uses `schemaVersion` to know which migrations to apply to a loaded dashboard. Older versions of the JSON shape are not invalid; they are auto-upgraded to the current shape on load. The result: if you save a dashboard from the UI in Grafana 11 and the original `schemaVersion` was 16, Grafana writes back `schemaVersion: 39` and your file-on-disk no longer matches what Grafana renders.

Set it explicitly to match your Grafana version. For Grafana 11, that is `39`. For Grafana 10, `38`.

### Q2. Why is `uid` important?

Three things use `uid`:

1. **Dashboard URLs.** The URL is `/d/<uid>/<slug>`; the slug is a hint, the uid is the lookup. Stable uid means stable URL.
2. **Cross-dashboard links.** A panel can include a "drill-down to this other dashboard" link, addressed by uid. If the target's uid changes, the link breaks.
3. **Provisioning.** Provisioned dashboards keyed by uid. If two dashboards share a uid, only one will load and the other gets a confusing error.

Always set `uid` explicitly. Use a short, kebab-cased string: `w09-emitter-red`, `mini-project-overview`, `cluster-resources`.

### Q3. `expr` vs `legendFormat`

- `expr` — the PromQL (or LogQL, or TraceQL) the panel evaluates. Returns time series.
- `legendFormat` — a Go template for the legend label. Has access to the series labels: `{{ route }}`, `{{ status }}`, `{{ pod }}`. The default is the full label set (`{route="/api/hello", status="200", instance="..."}`), which is unreadable; a custom `legendFormat` makes the legend useful.

The right template depends on the query. For a panel that sums by route, `{{ route }}`. For a panel that sums by service, `{{ service }}`. For an aggregate with no remaining labels, the literal string `"all"` works.

### Q4. RBAC for the sidecar

The dashboard sidecar (the `kiwigrid/k8s-sidecar` container) watches `ConfigMap`s cluster-wide. The minimal RBAC:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: grafana-sidecar-dashboards
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    verbs: ["get", "list", "watch"]
```

Bound via a `ClusterRoleBinding` to the Grafana pod's ServiceAccount. The `kube-prometheus-stack` chart installs all of this; you can inspect it with `kubectl get clusterrole | grep grafana`.

The watch is the load-bearing verb. Without it, the sidecar would have to poll, which is slow and chatty against the API server.

---

## A summary of the four exercises

By the end of Exercise 4 your cluster has:

- Prometheus scraping ~20 jobs and storing ~100,000 series.
- Grafana with the bundled chart dashboards plus your "Emitter RED" dashboard.
- Alertmanager with a webhook receiver that logs every firing and resolved alert.
- Jaeger receiving traces from the greeter service via the OpenTelemetry Collector.
- A metric-emitter pod and a greeter pod emitting metrics and traces respectively.

This is the foundation. The mini-project takes the greeter, adds full structured logging to Loki, writes a full RED dashboard, adds three alerts with runbook links, defines an SLO with a burn-rate alert, and ships the whole thing in one Git repo that ArgoCD applies.
