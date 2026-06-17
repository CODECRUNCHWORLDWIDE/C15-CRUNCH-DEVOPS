# Lecture 2 — Grafana, Alertmanager, and Dashboards-as-Code

> *A dashboard that lives only in a UI is a dashboard your team will lose. A dashboard committed to Git is a dashboard your team will keep.*

In Lecture 1 you saw the metrics pillar and the query language that reads it. Prometheus is the store; PromQL is the language. The next two questions, in order, are: *how do humans look at the data*, and *how does the data wake humans up when something is wrong*. Those two questions are answered by Grafana (dashboards) and Alertmanager (routing). Both ship inside the `kube-prometheus-stack` Helm chart you install in Exercise 1; both have their own configuration shapes that are worth understanding directly because, in the field, you will write them by hand.

This lecture covers Grafana first, then Alertmanager, then the discipline that holds both together: dashboards-as-code and alerts-as-code. By the end you will know why every Grafana dashboard you ever care about should be a YAML file in a Git repo, never just a thing in a UI.

---

## 1. Grafana, the visualization layer

Grafana is a single Go binary that renders dashboards. It reads time-series data from one or more **data sources** (Prometheus, Loki, Tempo, Jaeger, Elasticsearch, Postgres, CloudWatch, BigQuery, and ~150 others via plugins) and paints them as panels in a dashboard. It does not store metrics itself. It is a thin presentation layer over whatever store you connect.

The reasons Grafana is the open-source default:

- **It speaks every protocol.** PromQL, LogQL, TraceQL, SQL, ElasticSearch, InfluxQL, Flux. New data sources show up as plugins; the architecture supports it.
- **It is operationally simple.** One binary, one SQLite database (for users and dashboards if you store them in the DB; we will not), one port. No required external dependency. Same operational model as Prometheus.
- **It is open-source under AGPL.** Grafana Labs sells a hosted version (Grafana Cloud) and a paid Enterprise version with extra features, but the core is free and self-hostable. You will see Grafana running in every cluster.
- **The dashboard JSON format is portable.** You can export a dashboard from one Grafana, import it into another, and it works. Same for the YAML provisioning format.
- **The community library is enormous.** <https://grafana.com/grafana/dashboards/> has 5,000+ community-published dashboards, many of which are good starting points. The `kube-prometheus-stack` chart bundles ~25 of them by default.

### The dashboard model: panels, rows, variables

A Grafana dashboard is a JSON document (or its YAML equivalent in provisioned form) with three main pieces:

1. **Panels** — visualization widgets. Each panel has a type (time-series, stat, gauge, bar gauge, table, heatmap, logs, traces, alert list, news, text), a query (PromQL, LogQL, etc.), and a set of options that control how the data is rendered.
2. **Rows** — horizontal groupings of panels. Used to organize dashboards into sections (e.g., "Latency", "Errors", "Resources").
3. **Variables** — templated parameters that change the queries. A variable named `$namespace` lets the user pick a namespace from a dropdown; all panels using `$namespace` in their query re-render with the new value.

A minimal time-series panel in JSON:

```json
{
  "type": "timeseries",
  "title": "HTTP request rate by route",
  "datasource": {"type": "prometheus", "uid": "prometheus"},
  "targets": [
    {
      "expr": "sum by (route) (rate(http_requests_total{namespace=\"$namespace\"}[5m]))",
      "legendFormat": "{{ route }}",
      "refId": "A"
    }
  ],
  "fieldConfig": {
    "defaults": {"unit": "reqps"}
  }
}
```

Six lines of substance. The `type: timeseries` is the panel kind. The `targets` array contains the queries; one query per panel is the common case. The `legendFormat` is a Go-template that produces the legend label from the time series's labels. The `unit: reqps` tells Grafana to render values with the "requests per second" unit suffix.

A real dashboard has 10-30 panels and ~500 lines of JSON. The full mini-project dashboard in Week 9 is ~600 lines.

### Variables: the templating layer

Variables are how dashboards become reusable. The pattern:

```json
{
  "templating": {
    "list": [
      {
        "name": "namespace",
        "type": "query",
        "datasource": {"type": "prometheus", "uid": "prometheus"},
        "query": "label_values(kube_pod_info, namespace)",
        "refresh": 1
      }
    ]
  }
}
```

This defines a variable `$namespace` whose values come from a PromQL query: `label_values(kube_pod_info, namespace)` returns every distinct value of the `namespace` label on the `kube_pod_info` metric. The user sees a dropdown of namespaces; selecting one re-renders the dashboard.

Variable types beyond `query`:

- `custom` — a static list (e.g., `"prod,staging,dev"`).
- `interval` — a list of time intervals (`30s, 1m, 5m, 30m`) the user picks for `rate()` ranges.
- `datasource` — pick a data source. Useful for multi-cluster dashboards.
- `constant` — a string that is set at provision time and not changed by the user.

The mini-project dashboard uses three variables: `$namespace`, `$service`, and `$interval`. We will write them in Exercise 4.

### Units, thresholds, and decorations

Grafana panels have three layers of cosmetics that matter:

1. **Unit** — `reqps`, `percent`, `bytes` (IEC, so `1024-based`), `s` (seconds, auto-scaled to ms/µs/ns), `dateTimeAsIso`. Setting the unit means Grafana renders values like `1.2k req/s` instead of `1234`. The list of valid unit strings is at the top of the Grafana docs: <https://grafana.com/docs/grafana/latest/panels-visualizations/configure-standard-options/>.
2. **Thresholds** — value-based color bands. "Color the panel red if the value is > 0.05, yellow if > 0.01, green otherwise." Used heavily on stat and gauge panels.
3. **Mappings** — value-to-text replacements. `0 -> "Healthy"`, `1 -> "Warning"`, `2 -> "Critical"`. Useful for state metrics like `kube_node_status_condition`.

These decorations are how a dashboard turns numbers into a story. Without them, every panel is a blue line on a black background; with them, the panel says "this is good" or "this is bad" without the reader having to interpret.

---

## 2. Dashboards-as-code: why YAML, not the UI

Grafana, by default, stores dashboards in its own SQLite (or external Postgres) database. You create them in the UI by clicking "Add panel", you save them, they live in the DB. This is fine for exploration. It is not fine for the dashboards your team actually depends on.

The reasons:

- **Cluster replacement loses them.** If you `kind delete cluster && kind create cluster && helm install kube-prometheus-stack`, every UI-created dashboard is gone. (You can back up the DB; few teams do.)
- **No audit.** Who changed the alerting threshold last Tuesday? With UI-created dashboards, no one knows. With Git-stored dashboards, `git blame` answers in one line.
- **No code review.** A new dashboard in the UI is a dashboard nobody else has looked at. A new dashboard in a Git repo is a pull request with reviewers.
- **No diff.** Two versions of a UI dashboard are two opaque blobs in SQLite. Two versions of a YAML dashboard are a unified diff a human can read.
- **No replicability across environments.** The staging cluster's dashboards should match the production cluster's. With UI dashboards, this is a manual export-import dance. With Git-stored dashboards, both clusters point at the same Git repo.

The solution is **provisioning**: Grafana reads dashboards from files on disk at startup and on a refresh interval. The files come from a `ConfigMap` (mounted as a volume) that Git is the source of truth for.

### The provisioning model

A provisioned Grafana has three configuration files:

1. **`datasources.yaml`** — declares the data sources (Prometheus, Loki, Tempo). Lives at `/etc/grafana/provisioning/datasources/`.
2. **`dashboards.yaml`** — declares which folders on disk Grafana should scan for dashboard JSON files, and how often. Lives at `/etc/grafana/provisioning/dashboards/`.
3. **The dashboard JSON files themselves** — one file per dashboard. Live wherever `dashboards.yaml` says to look. Typically `/var/lib/grafana/dashboards/<folder>/<name>.json`.

The `kube-prometheus-stack` chart sets all three up. You override the third by mounting a `ConfigMap` that contains your custom dashboards. The pattern:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-service-dashboard
  namespace: monitoring
  labels:
    grafana_dashboard: "1"
data:
  api-service.json: |-
    {
      "title": "API Service",
      "schemaVersion": 39,
      "panels": [
        ...
      ]
    }
```

The magic label is `grafana_dashboard: "1"`. The Grafana sidecar (a tiny container running alongside Grafana) watches for `ConfigMap`s with this label cluster-wide, extracts the JSON, and writes it into the directory Grafana provisions from. Grafana picks up the change within ~30 seconds.

This is the right pattern. Every dashboard you want to keep is a `ConfigMap` checked into Git, applied by ArgoCD (from Week 8), and synced to Grafana via the sidecar. We will set this up in Exercise 4.

### The dashboard JSON gotchas

Writing dashboard JSON by hand has a few sharp edges:

- **`schemaVersion`** — Grafana 11 uses `schemaVersion: 39`. If you copy an older dashboard with `schemaVersion: 16`, Grafana will auto-upgrade it on load and your file-on-disk will not match what Grafana renders. Always set `schemaVersion` to match your Grafana version.
- **`uid`** — every dashboard has a `uid` that is its stable identifier across Grafana versions. Set it explicitly; do not let Grafana auto-generate it. The `uid` is what URLs reference and what cross-dashboard links use.
- **`gridPos`** — every panel has an `x, y, w, h` in a 24-column grid. If you copy a panel without adjusting `gridPos`, two panels will overlap. The UI hides this from you; the JSON does not.
- **`datasource.uid`** — references to data sources are by `uid`, not by name. The `prometheus` and `loki` data sources installed by `kube-prometheus-stack` have predictable `uid`s, but you should set them in your `datasources.yaml` and reference them consistently.
- **Variables and panels are loaded in declaration order.** A panel that references `$namespace` before `$namespace` is declared will render before the variable resolves and may show errors briefly.

The Grafana docs at <https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/manage-dashboards/> cover the JSON schema. The reference for the panel-type-specific fields is at <https://grafana.com/docs/grafana/latest/panels-visualizations/>.

### Two tools worth knowing

- **Grizzly** — `grafana/grizzly` on GitHub. A CLI that wraps the Grafana API and lets you push/pull dashboards between a local YAML/JSON file and a running Grafana. Useful when you want to author in the UI (for the rich editor) and then commit the result. <https://github.com/grafana/grizzly>.
- **Jsonnet + Grafonnet** — a programmatic way to generate Grafana JSON from a Jsonnet library. The `kube-prometheus-stack` chart's bundled dashboards are mostly Grafonnet-generated. Useful for very large dashboard fleets where copy-paste between dashboards is too error-prone. <https://github.com/grafana/grafonnet>. Out of scope for this week; mentioned for orientation.

For a small project (this week's mini-project), hand-writing JSON in a `ConfigMap` is the right call. For a 50-dashboard fleet, Grizzly or Grafonnet starts to pay off.

---

## 3. Alertmanager, the routing layer

Prometheus fires alerts. Alertmanager routes them. The two components are separate processes connected by a webhook: Prometheus, when an alerting rule becomes true for its `for:` duration, POSTs the alert to Alertmanager's `/api/v2/alerts` endpoint; Alertmanager decides what to do with it.

Alertmanager has four responsibilities:

1. **Routing** — given an alert with labels (`severity`, `service`, `namespace`), pick the right *receiver* (Slack channel, PagerDuty service, email address, webhook).
2. **Grouping** — collapse many simultaneous alerts into one notification. When 200 pods of one service start failing at the same instant, you want one Slack message, not 200.
3. **Inhibition** — suppress lower-priority alerts when a higher-priority alert is firing. If `ServiceDown` is firing, do not also page on `HighLatency` for the same service; the latency is high because the service is down.
4. **Silencing** — temporarily mute alerts during planned maintenance, manually, via the Alertmanager UI or `amtool`.

### The routing tree

Alertmanager's config is a YAML tree:

```yaml
route:
  receiver: default-slack
  group_by: [alertname, cluster, service]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - matchers:
        - severity = "critical"
      receiver: pagerduty-oncall
      continue: false
    - matchers:
        - severity = "warning"
        - service =~ "billing|payments"
      receiver: billing-team-slack
      continue: false

receivers:
  - name: default-slack
    slack_configs:
      - api_url: "https://hooks.slack.com/services/T.../B.../..."
        channel: "#alerts-general"
  - name: pagerduty-oncall
    pagerduty_configs:
      - service_key: "abc123def456"
  - name: billing-team-slack
    slack_configs:
      - api_url: "https://hooks.slack.com/services/T.../B.../..."
        channel: "#alerts-billing"
```

Reading top-down:

- `route` — the root of the tree. The default receiver is `default-slack`.
- `group_by` — alerts are grouped by these labels. Two alerts with the same `(alertname, cluster, service)` go into one notification.
- `group_wait: 30s` — wait 30 seconds after the first alert in a group before notifying, in case more arrive that should be batched together.
- `group_interval: 5m` — once a group has been notified, wait 5 minutes before sending a new notification for changes within the same group.
- `repeat_interval: 4h` — if the alert is still firing, re-notify every 4 hours so it does not get forgotten.
- `routes` — child routes that match more specific patterns. Each match short-circuits unless `continue: true`.
- `receivers` — the destinations. Slack via webhook, PagerDuty via service key, email via SMTP, webhook for anything else.

The tree is evaluated top-down for each alert. The first child route that matches wins. If no child matches, the parent's receiver is used.

### Inhibition rules

```yaml
inhibit_rules:
  - source_matchers:
      - alertname = "KubernetesNodeDown"
    target_matchers:
      - alertname =~ "HighLatency|HighErrorRate"
    equal: [cluster]
```

Reading: "if `KubernetesNodeDown` is firing somewhere, suppress `HighLatency` and `HighErrorRate` alerts that share the same `cluster` label". The reasoning: when a node is down, all the services on it will go red; the latency and error-rate alerts are downstream symptoms.

Inhibition rules are how you keep the page-volume sane during a partial outage. Without them, one infrastructure failure produces 50 simultaneous pages and the on-call buries themselves in the inbox.

### Grouping in practice

Grouping is the single most important feature of Alertmanager. Without it, every alert is a page, and a busy cluster pages constantly. The rule of thumb:

- `group_by: [alertname]` — one notification per *type* of alert across all instances. Often too aggressive; loses detail.
- `group_by: [alertname, namespace]` — one per type per namespace. Reasonable for cluster-wide alerts.
- `group_by: [alertname, service]` — one per type per service. Reasonable for service-level alerts.
- `group_by: [alertname, instance]` — one per type per pod/host. Often too granular; defeats the point of grouping.

The default in the `kube-prometheus-stack` chart is `[namespace, alertname]`, which is a sensible starting point. Adjust as you learn what your team finds noisy.

### The PrometheusRule CRD again

The `PrometheusRule` CRD from Lecture 1 holds both recording rules and alerting rules. Alerts you write there land in Prometheus, which evaluates them on its schedule, which posts firing alerts to the Alertmanager. The CRD shape:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: api-service-alerts
  namespace: monitoring
  labels:
    release: kube-prometheus-stack
spec:
  groups:
    - name: api-availability
      interval: 30s
      rules:
        - alert: ApiServiceDown
          expr: up{job="api-service"} == 0
          for: 2m
          labels:
            severity: critical
            service: api
          annotations:
            summary: "API service has been down for 2 minutes"
            runbook: "https://wiki.example.com/runbooks/api-down"
        - alert: ApiHighErrorRate
          expr: |
            sum by (service) (rate(http_requests_total{status=~"5..",service="api"}[5m]))
              /
            sum by (service) (rate(http_requests_total{service="api"}[5m]))
              > 0.05
          for: 5m
          labels:
            severity: warning
            service: api
          annotations:
            summary: "API 5xx error rate above 5% for 5 minutes"
            runbook: "https://wiki.example.com/runbooks/api-errors"
```

Again, the `release: kube-prometheus-stack` label is required for the Operator to pick up the rule. Forgetting it is the single most common failure mode of writing alerts and we will repeat the reminder in Exercise 2.

---

## 4. A complete worked example: from metric to page

Let us walk a complete loop, end to end, to make the components concrete.

The scenario: your API service is returning a 5xx response on 10% of requests. You want to be paged when that exceeds 5% for 5 minutes. You want the page to land in PagerDuty (or, for this week, in a webhook to a local mock).

### Step 1 — the application exposes a metric

The FastAPI app you build in Exercise 3 emits this counter on every request:

```python
from prometheus_client import Counter

http_requests_total: Counter = Counter(
    "http_requests_total",
    "Total HTTP requests by route, method, and status",
    ["route", "method", "status"],
)

# In the handler:
http_requests_total.labels(route="/api/hello", method="GET", status="200").inc()
```

The app exposes `/metrics` on port 8080. A `curl http://localhost:8080/metrics` returns the counter in the Prometheus exposition format.

### Step 2 — Prometheus scrapes it

A `ServiceMonitor` selects the app's `Service`. Prometheus dials port 8080 every 15 seconds, reads `/metrics`, and stores the result. The series `http_requests_total{route="/api/hello",method="GET",status="200",service="api",namespace="default"}` is now in Prometheus's TSDB.

### Step 3 — an alerting rule evaluates the error rate

A `PrometheusRule` defines the `ApiHighErrorRate` alert from Section 3. Prometheus evaluates the rule every 30 seconds. The expression is the ratio of 5xx-status to total requests; when it exceeds 0.05 for 5 minutes, Prometheus marks the alert as firing.

### Step 4 — Prometheus POSTs the alert to Alertmanager

Prometheus and Alertmanager share a configuration: Prometheus knows the Alertmanager's address (`alertmanager.monitoring.svc.cluster.local:9093`). When the alert fires, Prometheus POSTs to `/api/v2/alerts` with the alert's labels and annotations.

### Step 5 — Alertmanager routes the alert

The routing tree sees `severity=warning, service=api`. There is no child route that matches, so the default receiver (`default-slack`) is used. Alertmanager waits `group_wait: 30s` to see if more alerts arrive that should be batched, then notifies.

### Step 6 — the receiver gets the notification

Slack (or PagerDuty, or the webhook mock for this week) receives a payload that looks like:

```json
{
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {"alertname": "ApiHighErrorRate", "service": "api", "severity": "warning"},
      "annotations": {
        "summary": "API 5xx error rate above 5% for 5 minutes",
        "runbook": "https://wiki.example.com/runbooks/api-errors"
      },
      "startsAt": "2026-05-14T14:23:17Z"
    }
  ]
}
```

The on-call sees the message, clicks the runbook link, and starts debugging. The whole chain — metric, scrape, rule, route, receive — is data on a wire from end to end.

### Step 7 — when the issue is resolved

When the error rate drops back below 5% and stays there for the rule's evaluation, Prometheus marks the alert as resolved and POSTs it again with `status: resolved`. Alertmanager sends a "resolved" notification to the same receiver. The Slack channel shows "Resolved: API 5xx error rate above 5%". The page is closed.

This is the loop. Everything else in observability is variations on this loop.

---

## 5. Alerts-as-code, applied

Alerts have the same rule as dashboards: **commit them to Git, peer-review them, never edit them only in a running cluster**. The reasons compound:

- **Alerts are runbooks waiting to happen.** Each new alert imposes a cost on the on-call: they have to know what it means and what to do. A new alert should be reviewed by the on-call rotation before merging.
- **Alert thresholds drift.** "Page on error rate > 5%" was right last quarter; it might be wrong this quarter. Git history shows what the threshold was and why it changed.
- **Tested alerts are better alerts.** Prometheus's `promtool` has a unit-test mode for alerting rules: you supply a synthetic time series and assert which alerts fire and at what time. We will see this in Exercise 2.
- **Cluster rebuilds.** Same argument as dashboards. A `kind delete cluster` should not lose your alerts; ArgoCD should reapply them from Git.

The `PrometheusRule` CRD makes this easy. Write the YAML, commit it, apply it via ArgoCD, and the Prometheus Operator reconciles it into Prometheus.

### `promtool` unit tests

`promtool` is the Prometheus CLI. One of its modes is rule-testing:

```bash
promtool test rules tests/api-service-alerts.test.yml
```

The test file:

```yaml
rule_files:
  - ../rules/api-service.rules.yml

evaluation_interval: 30s

tests:
  - interval: 30s
    input_series:
      - series: 'http_requests_total{status="500",service="api"}'
        values: '0 0 0 0 0 50 100 150 200 250'
      - series: 'http_requests_total{status="200",service="api"}'
        values: '0 100 200 300 400 500 600 700 800 900'
    alert_rule_test:
      - eval_time: 5m
        alertname: ApiHighErrorRate
        exp_alerts:
          - exp_labels:
              severity: warning
              service: api
              alertname: ApiHighErrorRate
            exp_annotations:
              summary: "API 5xx error rate above 5% for 5 minutes"
              runbook: "https://wiki.example.com/runbooks/api-errors"
```

Reading: "given these synthetic time series over 5 minutes, assert that the `ApiHighErrorRate` alert fires with the expected labels and annotations". Run it in CI; alert regressions are caught before they hit production.

Few teams write rule tests. The teams that do are the teams whose alerts you envy. Worth adopting.

---

## 6. Notification channels: a practical survey

Alertmanager supports many receiver types out of the box:

- **Slack** — webhook URL, channel name. Simple, free, the default for small teams.
- **PagerDuty** — service key, integration key. The default for teams with formal on-call rotations.
- **OpsGenie** — API key, team. Atlassian's PagerDuty competitor.
- **Email** — SMTP server credentials, recipient list. Fine for low-volume alerts; not fine for paging because email is unreliable for waking people.
- **Webhook (generic)** — any HTTPS endpoint. The universal escape hatch. We use this in Exercise 2 with a local mock.
- **Microsoft Teams** — webhook URL. Same shape as Slack.
- **Discord** — webhook URL. Same shape.

For this week's exercises, we send to a generic webhook running locally in the `kind` cluster — a small Python service that logs received alerts. No external dependency, no Slack token needed, but the routing and grouping logic is exactly the same as production.

### Notification templates

Alertmanager's notification text is templated. The default Slack message is fine; you can override it:

```yaml
receivers:
  - name: default-slack
    slack_configs:
      - api_url: "https://hooks.slack.com/services/..."
        channel: "#alerts"
        title: "{{ .GroupLabels.alertname }}"
        text: |
          *Status*: {{ .Status }}
          *Service*: {{ .CommonLabels.service }}
          *Severity*: {{ .CommonLabels.severity }}
          *Summary*: {{ .CommonAnnotations.summary }}
          {{ if .CommonAnnotations.runbook }}*Runbook*: {{ .CommonAnnotations.runbook }}{{ end }}
```

The `{{ }}` syntax is Go's text/template. The fields available — `.Status`, `.GroupLabels`, `.CommonLabels`, `.CommonAnnotations`, `.Alerts` — are documented at <https://prometheus.io/docs/alerting/latest/notifications/>.

Customizing the template is high-leverage: the on-call's first impression of an alert is the notification body, and a body that includes the runbook URL, the grafana URL, and the affected service is a body that resolves the page faster.

---

## 7. A note on Grafana Alerting (which we are not using)

Grafana has its own alerting system, separate from Alertmanager. Confusingly, Grafana Alerting can *also* use Alertmanager as its notification routing layer.

The pragmatic position:

- **Prometheus alerting rules + Alertmanager** — the canonical metrics-alerts pipeline. What we use this week. What every `kube-prometheus-stack` install uses by default.
- **Grafana Alerting** — a second alerting system, useful when your alerts span multiple data sources (a query that joins Prometheus and Loki, for example) or when your team standardizes on Grafana for both visualization and alerting.

For this week, we use the Prometheus side. The Grafana Alerting side is documented at <https://grafana.com/docs/grafana/latest/alerting/>; investigate it on your own time if your team's stack uses it.

---

## 8. The Lecture-2 ethic, stated plainly

The principle, in one sentence: **a dashboard or alert that lives only in a UI is a dashboard or alert your team will lose, and the loss will happen at the worst possible moment**.

The corollary principles:

1. **Every dashboard is a YAML file in Git.** Provisioned into Grafana via a `ConfigMap` watched by the sidecar.
2. **Every alert is a YAML file in Git.** Provisioned into Prometheus via a `PrometheusRule` CRD watched by the Operator.
3. **Every alert has a runbook URL in its annotations.** The URL goes to a wiki page that exists. If the wiki page does not exist yet, write a placeholder; do not skip the URL.
4. **Every alert has a `for:` clause.** Without one, you will page on transient spikes that resolve themselves.
5. **Every dashboard has a `uid` you set explicitly.** So that links from one dashboard to another do not break.
6. **Every variable on a dashboard has a sensible default.** So that the dashboard renders meaningfully when loaded fresh.
7. **Every notification template includes the runbook URL.** So that the on-call's first click is the right click.

We will operationalize all seven in Exercises 2 and 4. The mini-project enforces all seven on graded criteria. The discipline is the point.

---

## 9. Reading list before Lecture 3

- Grafana docs, **Configure provisioning**: <https://grafana.com/docs/grafana/latest/administration/provisioning/>. 15 minutes.
- Grafana docs, **Build dashboards** overview: <https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/>. 20 minutes.
- Prometheus docs, **Alertmanager configuration**: <https://prometheus.io/docs/alerting/latest/configuration/>. 20 minutes.
- **Chapter 10 of the SRE book** — *Practical Alerting*: <https://sre.google/sre-book/practical-alerting/>. 30 minutes.

The SRE book chapter especially — it ends with the principle that "every alert must be actionable; alerts that are not actionable are not alerts, they are notifications, and notifications go in a dashboard". That principle is what separates a working alerting practice from a slowly-growing inbox of noise. Read it before you write your first alert in Exercise 2.
