# Exercise 4 — Grafana Dashboard as Code

**Time:** 45 minutes (15 min reading, 20 min hands-on, 10 min write-up).
**Cost:** $0.00.
**Cluster:** The `w09` kind cluster from Exercises 1, 2, and 3.

---

## Goal

Author a small Grafana dashboard as a JSON document, package it inside a Kubernetes `ConfigMap`, and watch the Grafana sidecar provision it into the running Grafana automatically. By the end you will have a dashboard called "Emitter RED" that you have never opened in the UI; it was loaded entirely from Git-shaped configuration.

After this exercise you should have:

- A `ConfigMap` named `dashboard-emitter-red` in `monitoring`, with label `grafana_dashboard: "1"`.
- A dashboard called "Emitter RED" visible in Grafana, with three panels: request rate, error rate, and p95 duration.
- Confidence that updating the `ConfigMap` updates the dashboard within ~30 seconds.

---

## Step 1 — The dashboard shape

The Grafana JSON schema is dense. We will use a small dashboard with three panels. The shape:

```
+----------------------------------------------+
| Emitter RED                                   |
+-----------------+-----------------+---------+
| Request rate    | Error rate %    | p95 dur |
| (time-series)   | (time-series)   | (stat)  |
+-----------------+-----------------+---------+
```

Three panels in a single row, occupying a 24-column grid (8 columns each).

---

## Step 2 — Author the dashboard JSON

Save as `dashboard-emitter-red.json` (we will embed this into a `ConfigMap` in Step 3):

```json
{
  "annotations": {"list": []},
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "id": 1,
      "type": "timeseries",
      "title": "Emitter request rate (req/s)",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "gridPos": {"h": 8, "w": 8, "x": 0, "y": 0},
      "targets": [
        {
          "expr": "sum(rate(emitter_requests_total[1m]))",
          "legendFormat": "all",
          "refId": "A"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "reqps",
          "color": {"mode": "palette-classic"}
        }
      },
      "options": {
        "tooltip": {"mode": "multi", "sort": "none"},
        "legend": {"displayMode": "list", "placement": "bottom", "showLegend": true}
      }
    },
    {
      "id": 2,
      "type": "timeseries",
      "title": "Emitter error %",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "gridPos": {"h": 8, "w": 8, "x": 8, "y": 0},
      "targets": [
        {
          "expr": "100 * sum(rate(emitter_requests_total{status=\"error\"}[5m])) / clamp_min(sum(rate(emitter_requests_total[5m])), 1)",
          "legendFormat": "error %",
          "refId": "A"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "color": {"mode": "thresholds"},
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "green", "value": null},
              {"color": "yellow", "value": 1},
              {"color": "red", "value": 5}
            ]
          }
        }
      },
      "options": {
        "tooltip": {"mode": "single", "sort": "none"},
        "legend": {"displayMode": "list", "placement": "bottom", "showLegend": true}
      }
    },
    {
      "id": 3,
      "type": "stat",
      "title": "Emitter p95 duration",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "gridPos": {"h": 8, "w": 8, "x": 16, "y": 0},
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum by (le) (rate(emitter_work_duration_seconds_bucket[5m])))",
          "legendFormat": "p95",
          "refId": "A"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "s",
          "color": {"mode": "thresholds"},
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {"color": "green", "value": null},
              {"color": "yellow", "value": 0.5},
              {"color": "red", "value": 1.0}
            ]
          }
        }
      },
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
        "textMode": "auto"
      }
    }
  ],
  "refresh": "30s",
  "schemaVersion": 39,
  "tags": ["week-09", "red", "emitter"],
  "templating": {"list": []},
  "time": {"from": "now-1h", "to": "now"},
  "timepicker": {},
  "timezone": "browser",
  "title": "Emitter RED",
  "uid": "w09-emitter-red",
  "version": 1,
  "weekStart": ""
}
```

What every notable field does:

- `schemaVersion: 39` — matches Grafana 11. Older numbers trigger an auto-upgrade.
- `uid: w09-emitter-red` — stable identifier. Other dashboards can link to this dashboard by uid.
- `panels[].gridPos` — `x`, `y`, `w`, `h` in a 24-column grid. The three panels share `y: 0` and have `x: 0`, `x: 8`, `x: 16`, each `w: 8`.
- `panels[].datasource.uid: "prometheus"` — references the Prometheus data source. The `kube-prometheus-stack` chart names its Prometheus data source with this uid.
- `panels[].targets[].expr` — the PromQL.
- `panels[].fieldConfig.defaults.thresholds` — color bands by value. The error % panel is green below 1%, yellow 1-5%, red above 5%.
- `refresh: "30s"` — the dashboard re-queries every 30 seconds.

---

## Step 3 — Package as a ConfigMap

The trick is that the dashboard JSON has to be a *string* inside the `ConfigMap`'s `data` field. The simplest tool is `kubectl create configmap --from-file`:

```bash
kubectl create configmap dashboard-emitter-red \
  --namespace monitoring \
  --from-file=emitter-red.json=dashboard-emitter-red.json \
  --dry-run=client \
  -o yaml > dashboard-emitter-red-cm.yaml
```

This produces `dashboard-emitter-red-cm.yaml`. Open it and add the magic label `grafana_dashboard: "1"` so the sidecar picks it up. The final shape:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: dashboard-emitter-red
  namespace: monitoring
  labels:
    grafana_dashboard: "1"
data:
  emitter-red.json: |-
    {
      "annotations": {"list": []},
      "editable": true,
      ...
      "uid": "w09-emitter-red",
      "version": 1,
      "weekStart": ""
    }
```

The `data.emitter-red.json` field is the entire JSON document as a string (the `|-` is YAML's "block literal, no trailing newline" indicator).

---

## Step 4 — Apply and verify provisioning

```bash
kubectl apply -f dashboard-emitter-red-cm.yaml
```

The Grafana sidecar watches `ConfigMap`s cluster-wide with the `grafana_dashboard: "1"` label. Within ~30 seconds it should see the new one and copy the JSON into Grafana's provisioning directory.

Watch the sidecar log:

```bash
kubectl logs -n monitoring -l app.kubernetes.io/name=grafana -c grafana-sc-dashboard --tail=30 -f
```

You should see lines like:

```
Working on configmap monitoring/dashboard-emitter-red
File in configmap monitoring/dashboard-emitter-red emitter-red.json ADDED
File ... successfully read
```

If the sidecar log says `0 dashboards processed`, the label is wrong; double-check `grafana_dashboard: "1"`.

---

## Step 5 — See the dashboard in Grafana

Port-forward Grafana:

```bash
kubectl port-forward -n monitoring svc/kps-grafana 3000:80
```

Open <http://localhost:3000>. Log in (`admin` / `admin`). Navigate to **Dashboards**. There should be a new entry, "Emitter RED", under a default folder.

Click it. The three panels render. The request rate panel shows the loadgen traffic from Exercise 2 (or zero if loadgen is not running; restart it). The error rate is zero. The p95 panel is roughly 50-60 ms (the loadgen's `ms=50` parameter).

---

## Step 6 — Make a change, see it propagate

Edit the JSON to add a fourth panel: in-flight requests. Add this to the `panels` array:

```json
{
  "id": 4,
  "type": "stat",
  "title": "In-flight",
  "datasource": {"type": "prometheus", "uid": "prometheus"},
  "gridPos": {"h": 4, "w": 24, "x": 0, "y": 8},
  "targets": [
    {
      "expr": "sum(emitter_in_flight)",
      "legendFormat": "in flight",
      "refId": "A"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "none",
      "color": {"mode": "thresholds"},
      "thresholds": {
        "mode": "absolute",
        "steps": [
          {"color": "green", "value": null},
          {"color": "yellow", "value": 5},
          {"color": "red", "value": 20}
        ]
      }
    }
  },
  "options": {
    "colorMode": "value",
    "graphMode": "area",
    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": false},
    "textMode": "auto"
  }
}
```

Bump the dashboard's `version` field from `1` to `2`. Regenerate the ConfigMap:

```bash
kubectl create configmap dashboard-emitter-red \
  --namespace monitoring \
  --from-file=emitter-red.json=dashboard-emitter-red.json \
  --dry-run=client \
  -o yaml | \
  kubectl apply -f -
```

Wait 30 seconds; refresh the Grafana page. The dashboard now has a fourth panel.

This is the workflow. Edit the JSON, apply the ConfigMap, see the dashboard change. Everything lives in Git; nothing lives in the Grafana UI.

---

## Step 7 — A few realistic improvements

If you have time, try these (each ~5 minutes):

- **Add a namespace variable.** In the dashboard JSON, set `templating.list` to include a query variable:

```json
{
  "name": "namespace",
  "type": "query",
  "datasource": {"type": "prometheus", "uid": "prometheus"},
  "query": "label_values(kube_pod_info, namespace)",
  "refresh": 1,
  "current": {"text": "default", "value": "default"}
}
```

Then change panel queries to filter by `$namespace` (e.g., `... emitter_requests_total{namespace="$namespace"} ...`). The dashboard now has a namespace dropdown.

- **Set a sensible default time range.** `"time": {"from": "now-15m", "to": "now"}` is more useful than the default 1h for a busy dashboard.

- **Add a folder.** Provisioning supports folders via the `dashboards.yaml` provisioner config. The chart's default folder is "General"; you can move dashboards into a per-app folder by tweaking the sidecar's folder annotations. Documented at <https://grafana.com/docs/grafana/latest/administration/provisioning/#dashboards>.

---

## Step 8 — Write up

In your notes:

1. The three panels and their PromQL.
2. Why the `clamp_min(..., 1)` is in the error-rate panel's expression.
3. The exact sidecar log lines showing the dashboard being picked up.
4. The change you made in Step 6 and how long it took to appear.

Diagnostic questions:

- **Q1.** What is the role of `schemaVersion`? What happens if you set it to `5` for a Grafana 11 install?
- **Q2.** Why is `uid` important? What breaks if two dashboards share a uid?
- **Q3.** What is the difference between Grafana's `panels[].targets[].expr` (the PromQL) and `panels[].targets[].legendFormat` (the legend template)?
- **Q4.** The sidecar uses a Kubernetes API watch to find `ConfigMap`s. What is the RBAC required for the sidecar's ServiceAccount?

Answers in `SOLUTIONS.md`.

---

## What is next

The mini-project. Take the FastAPI greeter from Exercise 3, instrument it fully (metrics + logs + traces), write a real RED dashboard for it, write alerts, and ship the whole observability story as YAML in a Git repo.
