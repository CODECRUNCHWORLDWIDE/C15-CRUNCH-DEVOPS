# Quiz — Week 9

Twelve multiple-choice questions. Answer all twelve; one paragraph of reasoning each. The answer key is at the bottom. Do not peek.

---

### Q1. The three pillars of observability are:

a) Logs, traces, dashboards.
b) Metrics, logs, traces.
c) Prometheus, Loki, Tempo.
d) Health checks, alerts, on-call rotations.

<details>
<summary>Answer</summary>

**b)** Metrics, logs, traces. The "three pillars" framing was popularized by Cindy Sridharan's book and adopted by every observability vendor in 2018-2020.

</details>

---

### Q2. A Prometheus counter is:

a) A value that goes up and down freely.
b) A value that increases monotonically and resets to 0 only on process restart.
c) A bucketed histogram of observations.
d) A timestamp.

<details>
<summary>Answer</summary>

**b)** Monotonically increasing; resets only on process restart. The other types (gauge, histogram, summary) are different concepts. The `_total` suffix is the naming convention.

</details>

---

### Q3. In PromQL, why does `rate()` require a range vector?

a) Because `rate()` is alphabetically before `irate()`.
b) Because the function must look at multiple samples to compute per-second change.
c) Because Prometheus is a pull-based system.
d) Because `rate()` only works on counters.

<details>
<summary>Answer</summary>

**b)** `rate()` computes per-second rate of change; that requires at least two samples, which requires a range. (a) and (c) are unrelated; (d) is true but is not why a range is required.

</details>

---

### Q4. The Prometheus exposition format is:

a) Binary protobuf only.
b) Line-delimited text (with optional binary OpenMetrics).
c) JSON over HTTP.
d) gRPC streaming.

<details>
<summary>Answer</summary>

**b)** Plain text, line-delimited, with an optional binary OpenMetrics format. The text format is what every exporter emits and what every tutorial shows.

</details>

---

### Q5. A `ServiceMonitor` resource:

a) Watches the cluster for failing services and pages on-call.
b) Tells the Prometheus Operator which Kubernetes Services to scrape and how.
c) Is part of the Kubernetes core API.
d) Replaces the Service object.

<details>
<summary>Answer</summary>

**b)** Part of the Prometheus Operator's CRD set (`monitoring.coreos.com/v1`). It declares which Services to scrape. (a) and (c) are wrong; (d) is wrong.

</details>

---

### Q6. Cardinality in Prometheus refers to:

a) The number of Prometheus replicas.
b) The number of unique time series produced by a metric, given its labels.
c) The number of dashboards.
d) The number of alerts that have fired this week.

<details>
<summary>Answer</summary>

**b)** Series count, which equals the product of the unique values of each label on the metric. Unbounded labels (user_id, trace_id) explode cardinality.

</details>

---

### Q7. Which field on a Prometheus alerting rule prevents firing on single-sample noise?

a) `severity`.
b) `for:`.
c) `record:`.
d) `annotations`.

<details>
<summary>Answer</summary>

**b)** `for:` requires the alert condition to hold continuously for the specified duration before the alert fires. Filters out single-sample noise.

</details>

---

### Q8. In the RED method, "D" stands for:

a) Density.
b) Duration.
c) Deployment.
d) Discoverability.

<details>
<summary>Answer</summary>

**b)** Duration. RED = Rate, Errors, Duration. Coined by Tom Wilkie of Grafana Labs.

</details>

---

### Q9. An error budget is:

a) The maximum amount of dollars a team can spend on debugging.
b) The complement of an SLO (e.g., for a 99.9% SLO, 0.1% is the budget).
c) A line item in the CFO's report.
d) The number of bugs in the codebase.

<details>
<summary>Answer</summary>

**b)** The complement of the SLO. If the SLO is 99.9%, the budget is 0.1% of total requests over the window.

</details>

---

### Q10. OpenTelemetry's separation between API and SDK exists because:

a) Two teams disagreed about Go vs Python.
b) Libraries should be able to emit telemetry without committing the application to a backend.
c) The SDK is a separate company's product.
d) Backwards compatibility with OpenTracing.

<details>
<summary>Answer</summary>

**b)** Libraries can include the API without forcing a backend choice. The application picks the SDK at startup; libraries just emit. This is the key design innovation of OpenTelemetry vs OpenTracing.

</details>

---

### Q11. Loki indexes:

a) Every word in every log line (like Elasticsearch).
b) Only the labels on the log stream; the content is stored as compressed chunks.
c) Nothing; queries scan all logs from scratch.
d) Only the timestamps.

<details>
<summary>Answer</summary>

**b)** Labels indexed; content as compressed chunks. The trade-off vs Elasticsearch: smaller storage, slower full-text search.

</details>

---

### Q12. Dashboards-as-code (committing dashboards to Git) is preferred over UI-only dashboards because:

a) UI dashboards cost more in Grafana Cloud.
b) Cluster rebuilds, audit, peer review, replicability across environments.
c) Git is faster than the Grafana database.
d) The UI does not support all visualization types.

<details>
<summary>Answer</summary>

**b)** All of cluster rebuilds, audit, peer review, replicability. The UI is for exploration; Git is for the dashboards your team depends on.

---

</details>

---

## Scoring

12/12 — you have internalized the week. Move to the mini-project with confidence.
9-11/12 — solid; re-read the lecture for the misses.
6-8/12 — you skipped a lecture; go back.
<6/12 — re-read all three lectures before the mini-project.
