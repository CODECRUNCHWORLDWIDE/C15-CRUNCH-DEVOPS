# Challenge 2 — Debug a Cardinality Explosion in Prometheus

**Time:** 75 minutes.
**Cost:** $0.00.
**Prerequisite:** Exercises 1 and 2 complete. The `w09` kind cluster is running.

---

## Goal

You will deliberately introduce a cardinality explosion into the `metric-emitter` service, observe Prometheus's behavior as it ingests millions of series, diagnose the bad label using Prometheus's own diagnostics, and fix the explosion by changing the application code.

After this challenge you will have:

- An understanding of what cardinality is and how to measure it in a running Prometheus.
- The PromQL queries to identify the metric with the most series.
- The `/tsdb-status` page bookmarked and understood.
- An application-side fix that bounds the cardinality of the offending label.
- An alert that fires when cardinality grows unexpectedly.

---

## Step 1 — Add a bad label deliberately

In `emitter.py`, change the counter definition to include a `request_id` label, and increment it with a random UUID on every request. Save as `emitter-v2.py`:

```python
import uuid
from prometheus_client import Counter

REQUESTS_BAD: Counter = Counter(
    "emitter_requests_with_id_total",
    "Total work requests, labelled by request_id (this is bad).",
    ["status", "request_id"],
)

# In the handler:
rid: str = str(uuid.uuid4())
REQUESTS_BAD.labels(status="ok", request_id=rid).inc()
```

Build a new image:

```bash
docker build -t metric-emitter:0.2 .
kind load docker-image metric-emitter:0.2 --name w09
kubectl set image deploy/metric-emitter emitter=metric-emitter:0.2
kubectl rollout status deploy/metric-emitter
```

Now generate load:

```bash
kubectl run loadgen --image=curlimages/curl:8.10.1 --rm -i --tty --restart=Never -- sh
# inside:
while true; do
  curl -s "http://metric-emitter.default.svc.cluster.local:8080/work?ms=20" > /dev/null
done
```

Let it run for ~5 minutes. Each request creates a new label combination. After 5 minutes at ~50 req/s × 2 pods = 600 req/s, you have 180,000 new series. After 30 minutes, 1 million.

---

## Step 2 — Observe Prometheus's symptoms

Port-forward Prometheus:

```bash
kubectl port-forward -n monitoring svc/kps-kube-prometheus-stack-prometheus 9090:9090
```

Open <http://localhost:9090/tsdb-status>. This page lists:

- **Number of series** by metric name.
- **Number of series** by label name.
- **Top label-value cardinalities**: for each label name, the values with the most series.

You should see `emitter_requests_with_id_total` near the top with 100,000+ series. You should also see `request_id` as a label name with 100,000+ unique values. This is the explosion.

Check Prometheus's own metrics:

```promql
prometheus_tsdb_head_series
```

The total number of in-memory series in the head block. Normal is 10,000-100,000 for a small cluster. Yours will be approaching or exceeding 1,000,000.

```promql
process_resident_memory_bytes{job="prometheus-k8s"}
```

Prometheus's RAM usage. Normal: ~500 MB. Yours: 2 GB and climbing.

```promql
rate(prometheus_tsdb_head_samples_appended_total[5m])
```

Sample append rate. Spiking.

If you leave this running long enough, the Prometheus pod will OOM and be killed by the kubelet.

---

## Step 3 — Diagnose

Three PromQL queries that find cardinality explosions:

**Q1. Which metric has the most series?**

```promql
topk(10, count by (__name__)({__name__=~".+"}))
```

Returns the top 10 metric names by series count. `emitter_requests_with_id_total` should be at the top.

**Q2. Which label is the culprit?**

```promql
count(count by (request_id) (emitter_requests_with_id_total))
```

Returns the number of distinct `request_id` values. This should be enormous.

Equivalent in `/tsdb-status` — Prometheus's UI shows the same data without you having to write the PromQL. Bookmark this page; it is the first stop for any "Prometheus is slow" investigation.

**Q3. What is the per-series append rate?**

```promql
rate(prometheus_tsdb_head_samples_appended_total[5m])
```

If this is suddenly 10× normal and series count is matching, you are ingesting an explosion.

---

## Step 4 — Fix the explosion

Two fixes, in order of severity:

### Fix A — change the application

Remove the `request_id` label from the metric. The request_id belongs in logs and traces, not in metrics. Edit `emitter-v2.py` to revert:

```python
REQUESTS: Counter = Counter(
    "emitter_requests_total",
    "Total work requests.",
    ["status"],  # no request_id
)
REQUESTS.labels(status="ok").inc()
```

Rebuild, reload, redeploy. The exploded series stop receiving new samples; Prometheus will eventually mark them stale and drop them in the next 2-hour compaction.

### Fix B — drop the metric at scrape time

Sometimes you cannot change the application immediately. Prometheus supports `metric_relabel_configs` to drop metrics post-scrape:

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
    matchNames: [default]
  endpoints:
    - port: http
      path: /metrics
      interval: 15s
      metricRelabelings:
        - action: drop
          sourceLabels: [__name__]
          regex: emitter_requests_with_id_total
```

This drops the offending metric at the scrape boundary; Prometheus never stores it. Apply this *first* if the app fix will take time, then fix the app.

### Fix C — limit cardinality with a label rewrite

A nuanced fix: keep the metric but truncate the high-cardinality label. Replace `request_id` with `request_id_prefix` (first 2 characters of the UUID) so the cardinality is bounded to 256 instead of millions:

```yaml
endpoints:
  - port: http
    path: /metrics
    interval: 15s
    metricRelabelings:
      - action: replace
        sourceLabels: [request_id]
        targetLabel: request_id_prefix
        regex: '^(..).*'
        replacement: '$1'
      - action: labeldrop
        regex: request_id
```

This is unusual but useful when a label has *some* analytical value at low cardinality.

In production, prefer Fix A. The application is the right place to think about cardinality.

---

## Step 5 — Add a cardinality alert

Save as `prometheus-cardinality-alert.yaml`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: prometheus-cardinality
  namespace: monitoring
  labels:
    release: kps
spec:
  groups:
    - name: prometheus-self
      interval: 30s
      rules:
        - alert: PrometheusTSDBHeadSeriesTooHigh
          expr: prometheus_tsdb_head_series > 1000000
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "Prometheus head series exceeded 1M"
            description: "Current: {{ $value | humanize }} series. Investigate via /tsdb-status."
            runbook: "https://wiki.example.com/runbooks/prometheus-cardinality"
        - alert: PrometheusTSDBMemoryTooHigh
          expr: |
            process_resident_memory_bytes{job="prometheus-k8s"} > 2 * 1024 * 1024 * 1024
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "Prometheus is using more than 2 GB of RAM"
            runbook: "https://wiki.example.com/runbooks/prometheus-cardinality"
```

Apply and verify the rules are loaded.

The first alert is the canonical cardinality canary: 1M series is the line where most teams' Prometheus starts to feel pressure. The threshold is per-team; adjust based on your normal series count.

---

## Step 6 — Write up

In your notes:

1. The bad metric definition (one paragraph).
2. The `tsdb-status` screenshot showing the explosion.
3. The fix you applied.
4. The PromQL query for "top 10 metrics by series count" that you would run during an incident.
5. Reflection: which other application labels (in real systems you have worked on) have unbounded cardinality? user_id? trace_id? request_id? URL? IP?

---

## Stretch

- **`promtool tsdb analyze`** is a Prometheus CLI command that analyzes a TSDB block on disk and reports cardinality. Run it against the Prometheus pod's PV (via `kubectl cp` or by `exec`ing in).
- **Read the Prometheus paper** on cardinality: <https://prometheus.io/docs/practices/naming/#labels>. The official guidance on what belongs in a label.
- **Compare to Loki labels.** Loki has the same problem, with similar consequences. The `nginx_log` label being `pod_name` (bounded) is fine; the `nginx_log` label being `user_session_id` (unbounded) is fatal. Look at your Loki labels and audit them.

---

## Notes

Cardinality is the single most common cause of "Prometheus is slow" or "Prometheus is OOM" pages in 2026. The fix is almost always at the application boundary: do not put unbounded fields in labels.

When the cluster is finally healthy again, document the bad metric in a "known bad ideas" page and add the `PrometheusTSDBHeadSeriesTooHigh` alert to your standard rule set. Both costs near nothing; both prevent the next incident.
