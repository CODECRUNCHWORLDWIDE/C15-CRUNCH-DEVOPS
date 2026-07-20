# Resources — Week 9

A curated list. All resources are free except where noted. Read at least one item from each of the four sections below before Friday.

---

## 1. The canonical specifications and reference docs

These are the primary sources. When two blog posts disagree, these are the tiebreakers.

- **Prometheus documentation** — <https://prometheus.io/docs/introduction/overview/>. The introduction page is short and clear. From there, the *Querying* section ([prometheus.io/docs/prometheus/latest/querying/basics/](https://prometheus.io/docs/prometheus/latest/querying/basics/)) is the PromQL reference. The *Configuration* section ([prometheus.io/docs/prometheus/latest/configuration/configuration/](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)) is the scrape-config reference. The *Best practices* section ([prometheus.io/docs/practices/](https://prometheus.io/docs/practices/)) contains the famous "naming" and "histograms-and-summaries" pages — both required reading.
- **Grafana documentation** — <https://grafana.com/docs/grafana/latest/>. The *Dashboards* and *Provisioning* sections are what you will reference all week. The *Alerting* section covers Grafana's own alerting system (separate from Prometheus's Alertmanager — we use Prometheus Alertmanager in this week's exercises, but Grafana Alerting is worth knowing about).
- **OpenTelemetry documentation** — <https://opentelemetry.io/docs/>. The *Concepts* page ([opentelemetry.io/docs/concepts/](https://opentelemetry.io/docs/concepts/)) is the single most important read for trace semantics. The Python-specific docs are at <https://opentelemetry.io/docs/languages/python/> — both the SDK reference and the auto-instrumentation list.
- **Loki documentation** — <https://grafana.com/docs/loki/latest/>. The *LogQL* reference ([grafana.com/docs/loki/latest/query/](https://grafana.com/docs/loki/latest/query/)) is short and well-organized. The *Architecture* page is the one to read first; it explains why Loki scales differently from Elasticsearch.
- **Tempo documentation** — <https://grafana.com/docs/tempo/latest/>. The newer of the two trace stores. TraceQL — Tempo's query language — is documented at <https://grafana.com/docs/tempo/latest/traceql/>.
- **Jaeger documentation** — <https://www.jaegertracing.io/docs/latest/>. The older trace store. Simpler UI, narrower query language. Many existing deployments still run it.
- **Alertmanager documentation** — <https://prometheus.io/docs/alerting/latest/alertmanager/>. The routing-tree config language is documented at <https://prometheus.io/docs/alerting/latest/configuration/>.
- **Kubernetes monitoring docs** — <https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-usage-monitoring/>. The upstream Kubernetes guidance on what to monitor and how.

---

## 2. The Google SRE book — free chapters

The single most influential book on operating production services at scale. Written by Google engineers over the 2010s; released free at <https://sre.google/books/>. Every chapter is online.

The chapters most relevant to this week:

- **Chapter 3 — Embracing Risk** — <https://sre.google/sre-book/embracing-risk/>. Where the concept of an "error budget" is introduced. Read this first if you read nothing else.
- **Chapter 4 — Service Level Objectives** — <https://sre.google/sre-book/service-level-objectives/>. The SLI / SLO / SLA distinction, the math of error budgets, the indicators worth measuring.
- **Chapter 6 — Monitoring Distributed Systems** — <https://sre.google/sre-book/monitoring-distributed-systems/>. The "four golden signals" (latency, traffic, errors, saturation) are defined here. Predecessor to RED and USE.
- **Chapter 10 — Practical Alerting** — <https://sre.google/sre-book/practical-alerting/>. How to write an alert that pages a human at 3 a.m. without ruining their week. The chapter that ends with "if a page is not actionable, it is not an alert; it is a notification, and notifications go in a dashboard, not a pager".

A second book, **The Site Reliability Workbook**, is the companion volume of practical exercises, also free at <https://sre.google/workbook/table-of-contents/>. Chapters 1, 2, and 5 (the SLO workbook chapters) are the relevant ones for this week.

---

## 3. Talks, papers, and long-form articles

These complement the docs. Pick at least two.

- **Tom Wilkie — *RED Method: Patterns for Instrumentation and Monitoring*** — <https://www.youtube.com/watch?v=zk77VS98Em8>. A 30-minute talk by the engineer who coined the RED method. He explains why RED, not USE, for request-driven services, and why three numbers per route is enough to operate the service.
- **Brendan Gregg — *The USE Method*** — <https://www.brendangregg.com/usemethod.html>. Brendan Gregg's site, where the USE method is fully documented with checklists per resource type (CPU, memory, disk, network). The companion talk is <https://www.youtube.com/watch?v=oGTLR2RsAOg>.
- **Ben Sigelman — *Three Pillars with Zero Answers* — Honeycomb's critique of the three-pillars framing** — <https://lightstep.com/blog/three-pillars-with-zero-answers-rebooting-observability>. Honeycomb's argument that "three pillars" was always a marketing simplification and that traces, alone, can answer most of the questions metrics and logs are used for. Worth reading even if you disagree with the conclusion; sharpens the question.
- **Charity Majors — *Observability: A Manifesto*** — <https://www.honeycomb.io/blog/observability-a-manifesto>. The post that defined modern observability vocabulary. The "high-cardinality, high-dimensionality, explorable" definition originates here.
- **Tom Wilkie + Bjorn Rabenstein — *PromQL for Humans*** — <https://grafana.com/blog/2020/02/04/introduction-to-promql-the-prometheus-query-language/>. The clearest single introduction to PromQL.
- **OpenTelemetry team — *A Year of OpenTelemetry GA*** — the OTel blog at <https://opentelemetry.io/blog/>. Several posts cover the design rationale: why W3C Trace Context, why OTLP, why a separate API and SDK.
- **Frederic Branczyk — *Prometheus 3.0 Release Notes*** — <https://prometheus.io/blog/2024/11/14/prometheus-3-0/>. The most recent major version's design changes.

---

## 4. Hands-on guides and Helm-chart docs

For when you are stuck in the middle of an exercise.

- **`kube-prometheus-stack` Helm chart** — <https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack>. The values file is ~3,500 lines. Read the README first, then the values file by section.
- **`loki` Helm chart** — <https://github.com/grafana/loki/tree/main/production/helm/loki>. The "single-binary" mode is what we use this week.
- **`tempo` Helm chart** — <https://github.com/grafana/helm-charts/tree/main/charts/tempo>. Again, the single-binary mode for the kind-cluster use case.
- **`opentelemetry-collector` Helm chart** — <https://github.com/open-telemetry/opentelemetry-helm-charts/tree/main/charts/opentelemetry-collector>. The DaemonSet mode is the right pick for node-local collection.
- **`promtail` Helm chart** — <https://github.com/grafana/helm-charts/tree/main/charts/promtail>. Promtail's role is the file-tailing agent that ships container stdout to Loki.

For instrumenting Python:

- **OpenTelemetry Python — Getting Started** — <https://opentelemetry.io/docs/languages/python/getting-started/>. Walks through a Flask example; the FastAPI mapping is identical except for the auto-instrumentation package name (`opentelemetry-instrumentation-fastapi`).
- **OpenTelemetry Python — Auto-instrumentation list** — <https://opentelemetry.io/docs/languages/python/automatic/>. The list of frameworks and libraries that auto-instrument without code changes: FastAPI, Flask, Django, requests, httpx, psycopg, sqlalchemy, redis, pymongo, kafka, grpc, urllib3, and others.

---

## 5. Books (optional, not required)

- **Brendan Gregg — *Systems Performance: Enterprise and the Cloud*, 2nd ed.** (Pearson, 2020). Out-of-scope for this week — it is a 700-page reference on Linux performance — but if you are serious about USE, this is the canonical text.
- **Brian Brazil — *Prometheus: Up & Running*, 2nd ed.** (O'Reilly, 2023). The Prometheus book by the engineer who maintained it for a decade. About $40. Worth it if you are going deep on PromQL.
- **Cindy Sridharan — *Distributed Systems Observability*** (O'Reilly, 2018). A short free e-book from O'Reilly at <https://www.oreilly.com/library/view/distributed-systems-observability/9781492033431/>. Predates OpenTelemetry but the framing is durable.
- **Niall Murphy et al. — *Site Reliability Engineering*** (O'Reilly, 2016). The print version of the SRE book listed in Section 2. Free online; about $40 in print.

---

## 6. Tools that show up in this week's exercises

Each of these is referenced from at least one exercise or the mini-project.

- **`kubectl`** — the Kubernetes CLI. <https://kubernetes.io/docs/reference/kubectl/>.
- **`helm`** — the package manager. <https://helm.sh/docs/>.
- **`kind`** — Kubernetes in Docker. <https://kind.sigs.k8s.io/>.
- **`promtool`** — Prometheus's CLI for config validation, rule testing, and unit tests of alerting rules. <https://prometheus.io/docs/prometheus/latest/command-line/promtool/>.
- **`amtool`** — Alertmanager's CLI for routing-tree validation and silence management. <https://github.com/prometheus/alertmanager#amtool>.
- **`logcli`** — Loki's CLI for LogQL queries from the terminal. <https://grafana.com/docs/loki/latest/query/logcli/>.
- **`otelcol-contrib`** — the OpenTelemetry collector, distributed as a single binary. <https://github.com/open-telemetry/opentelemetry-collector-releases>.

---

## 7. The list of things deliberately not covered this week

Worth flagging so you know where to look later:

- **Vendor APM agents** — Datadog, New Relic, Splunk, Dynatrace, Honeycomb. All accept OTLP in 2026, so the OpenTelemetry instrumentation you write this week is portable to any of them. We do not use any one of them because they are not free and they are not portable. Honeycomb has a generous free tier worth trying if you have time.
- **eBPF-based observability** — Pixie ([px.dev](https://px.dev/)), Parca ([parca.dev](https://parca.dev/)), Cilium Hubble. The frontier of cluster-level observability without instrumenting the application. Recommended as a stretch goal.
- **Continuous profiling** — Grafana Pyroscope ([grafana.com/oss/pyroscope/](https://grafana.com/oss/pyroscope/)). The fourth pillar in some frameworks. Worth knowing about; out of scope for this week.
- **Service-mesh observability** — Istio's and Linkerd's built-in dashboards. Covered in Week 11.
- **Real-user monitoring (RUM)** — Sentry, Grafana Faro, OpenTelemetry's browser SDK. Web-frontend observability. Out of scope for a backend-focused week.

If a topic is on this list and you need it for your project, follow the link; it will lead you to a primary source.
