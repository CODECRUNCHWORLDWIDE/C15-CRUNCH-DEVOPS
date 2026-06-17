# Week 9 — Observability: Prometheus, Grafana, Loki, and OpenTelemetry

> *Observability is not a product. It is a property of a system. A system is observable when, by reading what it emits, you can answer questions you did not think to ask in advance.*

Welcome to Week 9 of **C15 · Crunch DevOps**. Last week you stood up a cluster, installed the add-on stack — NGINX Ingress, cert-manager, ArgoCD — and shipped a small app behind an Ingress. The cluster works. The app runs. You can `curl` it and get an HTML response. Everything is fine.

Until it is not. A request returns a 500. A pod restarts in a loop. P95 latency triples on Tuesday and nobody notices until Friday's customer call. The CPU graph on the cloud console looks healthy and the application is, in some literal sense, "up", but a user 2,000 miles away is staring at a spinner. The cluster is observable to itself. The application running on it is, at present, opaque to you. This week we fix that.

The pivot from Week 8 to Week 9 is the pivot from running services to operating them. Operating a service in 2026 means three things. First, the service emits **signals** — metrics, logs, traces — in shapes the operator can read. Second, those signals land in **stores** the operator can query — Prometheus for metrics, Loki for logs, Tempo or Jaeger for traces. Third, the operator has **dashboards** and **alerts** that turn those queries into a calm Tuesday afternoon when nothing is wrong and a fast escalation when something is. The discipline that ties the three together is called observability, and the open-source stack that implements it is the subject of this week.

We will install the stack — `kube-prometheus-stack` (which bundles Prometheus, Grafana, Alertmanager, node-exporter, and kube-state-metrics into one chart), Loki with Promtail or the OpenTelemetry collector, and a small FastAPI service instrumented with the **OpenTelemetry** SDK — onto the same `kind` cluster from Week 8. We will write a Prometheus scrape config and reason about scrape intervals. We will write Grafana dashboards as YAML, not by clicking around the UI, because dashboards-as-code is the only way to keep them when the cluster is replaced. We will define recording rules and alert rules. We will run the alert through Alertmanager and watch it route to a fake receiver. We will trace a request through the FastAPI service, see the span in Jaeger, and reason about what the trace tells us that the metrics did not.

By Sunday you will have a fully instrumented service. You will have written one PromQL query, one LogQL query, and one trace query. You will know what RED and USE mean and when to use which. You will have defined an SLO with an error budget and watched the budget burn for thirty seconds. And you will have read at least one chapter of the Google SRE book ([sre.google/sre-book](https://sre.google/sre-book/table-of-contents/)) — the canonical text on this discipline, written by the team that, in many real senses, invented the discipline.

---

## Learning objectives

By the end of this week, you will be able to:

- **Articulate** the three pillars of observability — metrics, logs, and traces — and explain what each pillar answers that the other two cannot. Name the canonical open-source store for each: Prometheus, Loki, Tempo/Jaeger.
- **Distinguish** monitoring (known-knowns: "is the service up", "is the queue lag growing") from observability (unknown-unknowns: "why is this one user's request slow on Tuesdays at 10:14"). Explain why both matter and why the second is the harder problem.
- **Configure** Prometheus scraping. Write a `ServiceMonitor` (the `kube-prometheus-stack` CRD that becomes a scrape job) and a raw `prometheus.yml` scrape config. Reason about scrape intervals (15s default, 30s for cheap-to-emit-expensive-to-store metrics, 1s for high-cardinality but only briefly).
- **Write** PromQL queries: instant queries, range queries, the rate/irate distinction, `histogram_quantile`, joins on labels, the `topk` and `bottomk` operators, the `absent()` function for alerting on disappeared scrape targets. Recognize and avoid the common cardinality footguns.
- **Define** recording rules (precomputed queries materialized into new time series) and alerting rules (PromQL boolean conditions that fire on `for: 5m`). Explain why a slow PromQL query becomes a fast recording rule and why this matters for dashboards that millions of engineers load every day.
- **Provision** Grafana dashboards as YAML / JSON in a `ConfigMap`, mounted into Grafana via a sidecar provisioner. Reason about why dashboards-as-code is required (cluster rebuilds, audit, peer review of dashboard changes) and where the UI is appropriate (exploration).
- **Install** Loki and either Promtail or the OpenTelemetry collector. Write a LogQL query (`{namespace="default"} |= "error"`). Explain Loki's design — log streams indexed by labels, log content stored as compressed chunks — and why it scales differently from Elasticsearch.
- **Instrument** a Python service with OpenTelemetry. Auto-instrument a FastAPI app for HTTP and database spans. Add manual spans around a critical business operation. Export traces to a local Jaeger via OTLP/gRPC. Read the trace in the Jaeger UI and explain what each span represents.
- **Apply** the RED method (Rate / Errors / Duration) to a request-driven service, and the USE method (Utilization / Saturation / Errors) to a resource (CPU, memory, disk, network). Explain why request-driven services use RED and resources use USE, and how the two methods combine for a full picture.
- **Define** an SLI (a measurable signal that proxies user experience), an SLO (a target on that signal, e.g., 99.9% of requests under 200ms over 28 days), and an error budget (the inverse: 0.1% × total requests × 28 days). Explain why error budgets are a *contract*, not a *metric*, and how teams use them to balance release velocity against reliability.
- **Configure** Alertmanager: routing trees, receivers (webhook to Slack or a local mock), inhibition rules (do not page on `HighLatency` while `ServiceDown` is firing), grouping (one alert per cluster per minute, not 200).
- **Defend** the choice of the OpenTelemetry SDK over a vendor agent (Datadog, New Relic, Splunk) on portability grounds, and name the exceptions where vendor instrumentation is the right pick (heavily-managed runtimes, contractual support requirements).

---

## Prerequisites

This week assumes you have completed **Weeks 1-8 of C15**. Specifically:

- You finished Week 8's mini-project — NGINX Ingress + cert-manager + ArgoCD on a `kind` cluster. We will install the observability stack into a fresh `w09` cluster but the muscle memory from Week 8 is required.
- You have `kind` (0.24+), `kubectl` (1.31+), `helm` (3.14+), `docker` running, and `python3` (3.11+). Verify:

```bash
kind version
kubectl version --client
helm version --short
docker info | head -1
python3 --version
```

- You have ~10 GB of free RAM. The observability stack is heavier than Week 8's add-on stack: Prometheus retains 15 days of metrics by default, Loki ingests every container's stdout, and Grafana runs alongside. At idle the full stack is ~3 GB; with the mini-project app emitting metrics, ~4 GB. Plus 2-3 GB for the kind cluster itself.
- You have a working OpenTelemetry mental model — or you do not, and this week will give you one. We will write the first manual span in Exercise 3.
- You can read YAML, you can read Python with type hints, and you understand that `kubectl apply -f` writes objects to the API server and the controllers reconcile them. Week 7 covered all three.

We use **Kubernetes 1.31+**, **`kube-prometheus-stack` chart version 60+**, **Grafana 11.x**, **Loki 3.x**, **Tempo 2.x** (or Jaeger 1.55+), and the **OpenTelemetry Python SDK 1.27+**. All current; no deprecated APIs in this week's material. API versions used: `apps/v1` (Deployment, StatefulSet, DaemonSet), `networking.k8s.io/v1` (Ingress), `monitoring.coreos.com/v1` (ServiceMonitor, PrometheusRule, Alertmanager — the CRDs the kube-prometheus-stack installs), `opentelemetry.io/v1alpha1` (Instrumentation — the OTel-operator CRD, used optionally).

If you are coming back to this material after a break, the relevant 2026 changes are: (a) **OpenTelemetry's Python SDK reached 1.0** in late 2024 and is now stable across the API surface we use; (b) **Prometheus 3.0** shipped in late 2024 and changed a few PromQL parser behaviors (notably stricter handling of `__name__` in `count()` — we use the safe forms throughout); (c) **Grafana 11** moved to the new dashboard schema (`schemaVersion: 39+`) and the YAML provisioning format added the `folder` field as a first-class top-level key.

---

## Topics covered

- The three pillars: metrics (numerical time series, aggregated, cheap to store, used for alerts and dashboards), logs (text events, high-cardinality, used for incident forensics and audit), traces (per-request causal chains across services, used to diagnose latency and to discover unknown unknowns). What each pillar is good at, what each is bad at, and why a mature observability practice has all three.
- Prometheus, the metrics store. Pull-based scraping (Prometheus dials the target, target exposes `/metrics` on HTTP), the exposition format (line-delimited text, label sets, `# HELP` and `# TYPE` directives), the four metric types (counter, gauge, histogram, summary). The reasoning behind pull-over-push: targets self-describe, discovery is centralized in Prometheus, broken scrapes are visible to the operator.
- PromQL. The query language. Instant vectors vs range vectors, the rate function and why `rate()` requires a range, the irate function and when it is correct (or, more often, when it is wrong). Histograms and the `histogram_quantile` function. Joins on labels for cross-metric computation (e.g., requests-per-deployment by joining `http_requests_total` with `kube_deployment_status_replicas`). Cardinality: the silent killer of Prometheus servers. The rule: keep label cardinality bounded, push high-cardinality fields to logs or traces.
- Recording rules and alerting rules. Recording rules: precomputed time series materialized into new metrics, used to keep dashboards fast. Alerting rules: PromQL booleans that fire when true for a duration. The `for:` clause and why you almost always want one. Severity labels (`critical`, `warning`, `info`) and the routing tree.
- Alertmanager. The component that receives alerts from Prometheus and routes them to receivers. Receivers: Slack, PagerDuty, OpsGenie, generic webhooks, email. Inhibition rules (one symptom does not fire if a deeper symptom is already firing). Grouping (collapse 200 simultaneous alerts into one notification). Silence (mute alerts during planned maintenance). Routes (the tree that decides which receiver gets which alert).
- `kube-prometheus-stack` — the canonical Helm chart. What it installs: Prometheus, Alertmanager, Grafana, node-exporter (a DaemonSet that exposes node-level metrics), kube-state-metrics (a deployment that turns Kubernetes objects into metrics), the Prometheus Operator (the controller that reconciles `ServiceMonitor` and `PrometheusRule` CRDs). The values file: what to override and what to leave alone. Why this chart is the floor of every cluster in 2026 you will see in production.
- Grafana. The dashboard layer. Panels (time-series, stat, gauge, table, logs, traces), variables (templating: `$namespace`, `$pod`), data sources (Prometheus, Loki, Tempo, Jaeger, OpenSearch, Postgres). Dashboards-as-code via the file-based provisioning sidecar. Why never to keep the most important dashboards solely in the UI: every cluster rebuild loses them; every edit is unaudited.
- Loki. The log store. Designed by Grafana Labs to be "Prometheus for logs": same label model, same horizontal scaling, but logs are stored as compressed chunks indexed only by their labels. LogQL: the query language, syntactically similar to PromQL but for log streams. The architecture: distributor → ingester → store, query frontend → querier → store. Promtail (the file-tailing agent) vs the OpenTelemetry collector (the unified-pipeline agent that can also handle metrics and traces). Why Loki scales differently from Elasticsearch (no full-text index by default, just label-indexed chunks).
- Traces and OpenTelemetry. The shape of a trace: a directed acyclic graph of spans, each span representing one unit of work, all spans sharing a trace ID. The W3C Trace Context propagation header (`traceparent: 00-<trace-id>-<span-id>-<flags>`) that crosses service boundaries. The OpenTelemetry SDK: the API (what application code calls), the SDK (the configuration layer), the exporters (where spans go: OTLP/gRPC, OTLP/HTTP, Jaeger, Zipkin). Auto-instrumentation for FastAPI, requests, redis, psycopg, sqlalchemy. Manual spans around business logic. The OpenTelemetry collector: the proxy that receives, processes, and exports. Why every vendor (Datadog, New Relic, Splunk, Honeycomb) accepts OTLP — and why you should use the OTel SDK over their proprietary one.
- RED and USE. Two methodologies for picking *which* metrics matter. RED (Rate, Errors, Duration) for request-driven services: the per-route counts, error rates, and latency distributions. USE (Utilization, Saturation, Errors) for resources: CPU utilization, queue saturation, disk errors. Tom Wilkie (Grafana Labs) coined RED; Brendan Gregg coined USE. The two methods combine: USE the nodes, RED the services.
- SLIs, SLOs, error budgets. The SRE vocabulary. SLI: the indicator (e.g., "fraction of HTTP requests under 200ms"). SLO: the objective (e.g., "99.9% over 28 days"). Error budget: the complement (0.1% × total requests). The contract: when the budget is healthy, the team ships; when the budget is burning, the team stops shipping and fixes reliability. Reading: the Google SRE book chapters 3 and 4, both free at [sre.google](https://sre.google/sre-book/table-of-contents/).
- The Week 9 ethic: dashboards-as-code, alerts-as-code, instrumentation-in-the-app-code-not-the-agent. Every part of the observability story checked into Git, peer-reviewed, replicable.

---

## Weekly schedule

The schedule below adds up to approximately **35 hours**. Total is what matters; reshuffle within the week as your life demands.

| Day       | Focus                                                       | Lectures | Exercises | Challenges | Quiz/Read | Homework | Mini-Project | Self-Study | Daily Total |
|-----------|-------------------------------------------------------------|---------:|----------:|-----------:|----------:|---------:|-------------:|-----------:|------------:|
| Monday    | Three pillars, Prometheus, PromQL (Lecture 1)               |    2h    |    1.5h   |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     5.5h    |
| Tuesday   | Grafana, dashboards-as-code, Alertmanager (Lecture 2)       |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Wednesday | OpenTelemetry, Loki, RED, USE, SLOs (Lecture 3)             |    2h    |    2h     |     1h     |    0.5h   |   1h     |     0h       |    0.5h    |     7h      |
| Thursday  | Hands-on: instrument the FastAPI app end-to-end             |    0h    |    2h     |     1h     |    0.5h   |   1h     |     1h       |    0.5h    |     6h      |
| Friday    | Mini-project — full observability stack on kind             |    0h    |    0h     |     0h     |    0.5h   |   1h     |     3h       |    0.5h    |     5h      |
| Saturday  | Mini-project finish; read the SRE book chapters             |    0h    |    0h     |     0h     |    1h     |   0h     |     2h       |    0h      |     3h      |
| Sunday    | Quiz, recap, tear down clusters                             |    0h    |    0h     |     0h     |    0.5h   |   0h     |     1h       |    0h      |     1.5h    |
| **Total** |                                                             | **6h**   | **7.5h**  | **2h**     | **4h**    | **5h**   | **7h**       | **2.5h**   | **34h**     |

---

## How to navigate this week

| File | What is inside |
|------|----------------|
| [README.md](./00-overview.md) | This overview (you are here) |
| [resources.md](./01-resources.md) | Curated readings: prometheus.io, grafana.com, opentelemetry.io, the SRE book |
| [lecture-notes/01-three-pillars-prometheus-promql.md](./02-lecture-notes/01-three-pillars-prometheus-promql.md) | The pillars, the Prometheus model, PromQL from the ground up |
| [lecture-notes/02-grafana-alertmanager-dashboards-as-code.md](./02-lecture-notes/02-grafana-alertmanager-dashboards-as-code.md) | Grafana, dashboards-as-YAML, Alertmanager routing |
| [lecture-notes/03-opentelemetry-loki-red-use-slos.md](./02-lecture-notes/03-opentelemetry-loki-red-use-slos.md) | OpenTelemetry SDK, Loki, RED, USE, SLIs and error budgets |
| [exercises/exercise-01-install-kube-prometheus-stack.md](./03-exercises/exercise-01-install-kube-prometheus-stack.md) | Install the stack on kind; verify Prometheus is scraping the cluster |
| [exercises/exercise-02-write-a-service-monitor-and-an-alert.md](./03-exercises/exercise-02-write-a-service-monitor-and-an-alert.md) | ServiceMonitor + PrometheusRule; fire an alert and watch it route |
| [exercises/exercise-03-instrument-fastapi-with-otel.md](./03-exercises/exercise-03-instrument-fastapi-with-otel.md) | A FastAPI app with auto-instrumentation and a manual span; export to Jaeger |
| [exercises/exercise-04-grafana-dashboard-as-code.md](./03-exercises/exercise-04-grafana-dashboard-as-code.md) | A dashboard committed to a ConfigMap, provisioned into Grafana |
| [exercises/SOLUTIONS.md](./03-exercises/SOLUTIONS.md) | Worked solutions, expected output, the diagnostic questions to ask |
| [challenges/challenge-01-define-an-slo-and-watch-the-budget-burn.md](./04-challenges/challenge-01-define-an-slo-and-watch-the-budget-burn.md) | Pick an SLI, define an SLO, write the burn-rate alerts |
| [challenges/challenge-02-debug-a-noisy-cardinality-explosion.md](./04-challenges/challenge-02-debug-a-noisy-cardinality-explosion.md) | A Prometheus that fell over; find the bad label and fix it |
| [quiz.md](./05-quiz.md) | 12 multiple-choice questions |
| [homework.md](./06-homework.md) | Six practice problems |
| [mini-project/README.md](./07-mini-project/00-overview.md) | A FastAPI service on kind with full metrics, logs, traces, dashboards, alerts |

---

## A note on cost

Week 9 is structured so that **no student needs a credit card to complete it**. The entire observability stack — Prometheus, Grafana, Alertmanager, Loki, Tempo / Jaeger — is open-source and runs comfortably on the same `kind` cluster you used in Week 8. The OpenTelemetry SDK is open-source. The Google SRE book is free.

```
+-----------------------------------------------------+
|  COST PANEL - Week 9 incremental spend              |
|                                                     |
|  kind cluster (local, in Docker)         $0.00      |
|  kube-prometheus-stack (Prometheus,                 |
|    Grafana, Alertmanager,                           |
|    node-exporter, kube-state-metrics)    $0.00      |
|  Loki + Promtail (Helm)                  $0.00      |
|  Tempo or Jaeger (Helm)                  $0.00      |
|  OpenTelemetry Python SDK                $0.00      |
|  OpenTelemetry Collector (DaemonSet)     $0.00      |
|                                                     |
|  Optional reading                                   |
|    Google SRE book (free, online)        $0.00      |
|    Prometheus Up & Running, 2nd ed.      $40 ish    |
|      (recommended, not required)                    |
|                                                     |
|  Required subtotal (kind path):          $0.00      |
+-----------------------------------------------------+
```

If you optionally also push the stack to a real GKE Autopilot cluster from last week, the incremental compute cost is roughly $0.10-$0.50/hour for the duration the stack is running. Tear the cluster down on Sunday if you go that path.

---

## Stretch goals

If you finish early and want to push further:

- Add **Tempo** alongside Jaeger and configure the OpenTelemetry collector to send traces to both. Compare the UIs. Tempo's TraceQL is the newer query language; Jaeger's UI is the older but more polished one. Decide which you prefer and why.
- Configure **Grafana Loki's metric extraction**: in LogQL, the `| unwrap` and `| rate` operators let you derive metrics from log lines. Build a panel that graphs the rate of `ERROR` log lines and compare it to the same rate computed from Prometheus's counter. They should agree; if they do not, that is a finding.
- Read the **Prometheus storage internals** at <https://prometheus.io/docs/prometheus/latest/storage/>. The TSDB block format, the WAL, the head block compaction, the 2-hour block windows. The 200 lines of explanation will change how you reason about cardinality.
- Write a **synthetic prober**: a small Go or Python program that hits the FastAPI service's `/health` endpoint every 5 seconds and exports the latency as a metric. Use `blackbox_exporter` instead if you want the off-the-shelf version. The point: external probes catch outages that internal metrics never see (because if the service is down, it cannot tell Prometheus it is down).
- Try **eBPF-based observability**: install **Pixie** or **Parca** on the kind cluster (both free, both Helm-installable). Watch CPU profiles flow into the UI without instrumenting the application. This is the frontier; it is worth knowing exists.
- Read **chapter 6** of the SRE book — *Monitoring Distributed Systems* — at <https://sre.google/sre-book/monitoring-distributed-systems/>. It is the chapter that defined the four golden signals (latency, traffic, errors, saturation), which precede and inform RED and USE.

---

## Up next

Continue to **Week 10 — Security, Policy, and Supply Chain** once you have shipped your Week 9 mini-project. Week 10 turns to the security side of the cluster: pod security admission, network policy, image signing with Cosign and Sigstore, SBOM generation, runtime detection with Falco, and the policy engines (OPA Gatekeeper, Kyverno) that enforce house rules across every namespace. Week 11 takes us into service mesh (Istio, Linkerd) and the question of when mesh is the right tool versus when plain Kubernetes networking is enough. Week 12 closes the curriculum with the production-readiness checklist: capacity planning, on-call rotations, incident review, the things you do on Friday before a long weekend.

A note on the order: we did observability (Week 9) before security (Week 10) deliberately. The argument is that security without observability is theater — you cannot defend what you cannot see, and you cannot tell a successful attack from a flaky test if you have no signals. The Week 9 stack — Prometheus + Grafana + Loki + OTel — is also the substrate for the Week 10 security tooling: Falco emits alerts to Prometheus, image-signing failures become metrics, OPA Gatekeeper's decisions land in logs. Observability is the foundation. Security is the application of the foundation.

---

*If you find errors in this material, please open an issue or send a PR. Future learners will thank you.*
