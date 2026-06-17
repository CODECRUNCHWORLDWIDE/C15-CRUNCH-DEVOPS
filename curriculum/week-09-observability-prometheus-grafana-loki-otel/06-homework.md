# Homework — Week 9

Six practice problems. Do at least four. Write each answer in your notes file with the PromQL/LogQL/YAML you used and a one-paragraph explanation of why.

---

## Problem 1 — Pick a real-world service and define its RED

Pick a service you have worked on (or a public service you understand: GitHub, Stripe, a database, anything). Write:

- The **rate** metric: what unit of work counts? Requests, jobs, messages, events?
- The **error** definition: what counts as a failure for this service? 5xx HTTP? Returned status="error" with 200? An exception in a downstream consumer?
- The **duration** metric: what latency is the user feeling? The HTTP round-trip? The end-to-end job completion?

For each, write the PromQL you would use to compute it (you can use fictional metric names). Defend the choices in a paragraph.

---

## Problem 2 — Write a PromQL query for the four golden signals

The Google SRE book chapter 6 names four golden signals: **latency, traffic, errors, saturation**.

For the `greeter` service in your kind cluster, write one PromQL query per signal:

1. **Latency** — p95 of HTTP request duration over 5 minutes.
2. **Traffic** — requests per second over 5 minutes.
3. **Errors** — fraction of requests with status >= 500 over 5 minutes.
4. **Saturation** — pick a saturation metric for the greeter. Options: number of in-flight requests, pod CPU throttling, memory utilization. Choose one and explain why.

Verify each query in the Prometheus UI returns sensible data. Put each in a panel in your RED dashboard.

---

## Problem 3 — Write a LogQL query

Promtail or the OTel collector ships container logs to Loki. Once Loki is installed in your cluster (see the mini-project), write a LogQL query that:

1. Selects logs from the greeter pods.
2. Filters to lines containing `"error"` (case-insensitive).
3. Parses the JSON (if your logs are structured) and groups by `route`.
4. Counts the per-route error rate over 5 minutes.

If your logs are unstructured, the LogQL is simpler but less expressive; document why you would want structured logs in production.

---

## Problem 4 — Write a multi-burn-rate SLO alert pair

For one of your real-world services (Problem 1), define:

- An SLI definition (one sentence).
- An SLO target (e.g., "99.5% over 28 days").
- A multi-window multi-burn-rate alert pair (fast burn + slow burn) in `PrometheusRule` YAML.

Use the formulas from Challenge 1. For the fast-burn 1h window catching 2% of budget, the factor is `0.02 * (28d / 1h) = 13.44`. For the slow-burn 6h window catching 5% of budget, `5.6`. Multiply each by `(1 - SLO)` to get the error-fraction thresholds.

---

## Problem 5 — Audit a dashboard for "code smells"

Pick one of the dashboards bundled by `kube-prometheus-stack` ("Kubernetes / Compute Resources / Cluster" is a good one). Open its JSON via `kubectl get configmap -n monitoring -l app.kubernetes.io/name=grafana,grafana_dashboard=1 -o yaml | less`.

Look for:

1. Hardcoded namespace or service names (should be variables).
2. Panels missing a `unit` (numbers without unit suffixes are unreadable).
3. Panels missing thresholds (a stat panel with no color band is just a number).
4. Queries that compute the same thing twice (could be a recording rule).
5. Panels with no descriptive title.

Pick one smell and propose the fix in your notes. You do not have to apply it; just document.

---

## Problem 6 — Instrument a non-FastAPI service

Pick any service you have written — a CLI tool, a Django app, a Flask app, a worker process, an Express.js service. Add OpenTelemetry instrumentation. Document:

- The auto-instrumentation package(s) you imported.
- The manual span you added.
- The OTLP endpoint you configured.
- The trace you saw in Jaeger.

If you do not have a service handy, take a public Python project (a small Flask app from a tutorial) and instrument it. The point is the muscle memory of "instrument a service", not the specific service.

---

## Stretch

- **Read SRE-book chapter 6** (*Monitoring Distributed Systems*) and write a one-paragraph reflection on the "four golden signals". Where do they differ from RED?
- **Compare Loki and Elasticsearch** for log storage. Set up a small Elasticsearch instance (the Helm chart is `elastic/elasticsearch`, free up to ~6 GB heap) and ingest the same logs as Loki. Compare query speed for: (a) full-text search across all services for the last hour, (b) label-filtered search for one service for the last 5 minutes. Note the difference.
- **Read the OpenTelemetry semantic conventions** at <https://opentelemetry.io/docs/specs/semconv/>. The standardized attribute names for HTTP, database, messaging, and so on. Use them in your instrumentation; do not invent new ones.

---

## Grading rubric

Each problem is worth ~15 points. Total: 90 (with 10 points reserved for the quality of explanation across all problems).

- Correct PromQL/LogQL/YAML that compiles or evaluates: 5 points.
- Sensible defense of choices in a paragraph: 5 points.
- Concrete evidence of execution (screenshot of dashboard / Prometheus query / Jaeger trace): 5 points.

90+: pass.
75-89: pass with minor revisions.
<75: redo and resubmit.
