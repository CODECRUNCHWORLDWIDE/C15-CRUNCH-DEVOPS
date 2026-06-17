# Exercise 1 — Install `kube-prometheus-stack` on `kind`

**Time:** 60 minutes (15 min reading, 30 min hands-on, 15 min write-up).
**Cost:** $0.00 (entirely local).
**Cluster:** A new `kind` cluster named `w09`. If you still have `w08` from last week, delete it (`kind delete cluster --name w08`) to free RAM.

---

## Goal

Stand up a `kind` cluster with the `kube-prometheus-stack` Helm chart installed. By the end you will have Prometheus, Grafana, and Alertmanager running, with Prometheus scraping the cluster's own components (kubelet, kube-state-metrics, node-exporter) and Grafana showing the bundled dashboards.

After this exercise you should have:

- A `kind` cluster named `w09`, configured with ingress-friendly port mappings.
- The `kube-prometheus-stack` chart installed in the `monitoring` namespace.
- Prometheus reachable at `http://localhost:9090` (via port-forward).
- Grafana reachable at `http://localhost:3000` (via port-forward).
- The Alertmanager UI reachable at `http://localhost:9093` (via port-forward).
- A working list of scrape targets visible in Prometheus's `/targets` page.

---

## Step 1 — Verify your tools

```bash
kind version
kubectl version --client
helm version --short
docker info | head -1
```

Expected:

```
kind v0.24.0 go1.22.4 darwin/arm64
Client Version: v1.31.0
v3.14.4+gabcde
Server Version: 25.0.5
```

If any one is missing:

| Tool | Install |
|---|---|
| `kind` | `brew install kind` |
| `kubectl` | `brew install kubectl` |
| `helm` | `brew install helm` |
| `docker` | Docker Desktop, Colima, or Podman with Docker compat |

---

## Step 2 — Write the kind config

Save this as `kind-w09.yaml`:

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: w09
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
```

Same shape as Week 8's; only the name differs. Two ports are mapped because we will use NGINX Ingress for the dashboard URLs in Exercise 4 (optionally; port-forward also works).

---

## Step 3 — Create the cluster

```bash
kind create cluster --config kind-w09.yaml
```

90 seconds. Verify:

```bash
kubectl cluster-info --context kind-w09
kubectl get nodes
```

You should see one node, `w09-control-plane`, in `Ready` state.

---

## Step 4 — Add the helm repo

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm search repo prometheus-community/kube-prometheus-stack
```

The last command should print one line with a chart version (60+ in 2026) and an app version (the bundled Prometheus version, ~3.0+).

---

## Step 5 — Install the chart

Create a values file `kps-values.yaml` to set sensible defaults for a small cluster:

```yaml
prometheus:
  prometheusSpec:
    retention: 15d
    resources:
      requests:
        cpu: 100m
        memory: 512Mi
      limits:
        cpu: 1000m
        memory: 2Gi
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false
    ruleSelectorNilUsesHelmValues: false

grafana:
  adminPassword: "admin"
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 512Mi
  sidecar:
    dashboards:
      enabled: true
      label: grafana_dashboard
      labelValue: "1"
    datasources:
      enabled: true

alertmanager:
  alertmanagerSpec:
    resources:
      requests:
        cpu: 25m
        memory: 64Mi
      limits:
        cpu: 250m
        memory: 256Mi
```

What every block does:

- `prometheus.prometheusSpec.retention: 15d` — keep 15 days of metrics. The Prometheus default.
- The three `*SelectorNilUsesHelmValues: false` flags — by default the Prometheus Operator only watches `ServiceMonitor`s with the chart's own labels. Setting these to `false` lets Prometheus discover *any* `ServiceMonitor` we create later, regardless of label. This is the most common confusion in the chart; we set it now so Exercise 2 works without label gymnastics.
- `grafana.adminPassword: "admin"` — for local dev only. Production must override this.
- `grafana.sidecar.dashboards.enabled: true, label: grafana_dashboard` — turns on the dashboard provisioning sidecar. Any `ConfigMap` with label `grafana_dashboard: "1"` cluster-wide will be loaded as a dashboard. We use this in Exercise 4.
- `alertmanager.alertmanagerSpec.resources` — sized for the kind cluster.

Install:

```bash
kubectl create namespace monitoring
helm install kps prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values kps-values.yaml \
  --wait \
  --timeout 10m
```

The `--wait` flag blocks until every resource is ready. On a laptop with 8 GB free, this is 3-5 minutes. Watch with `kubectl get pods -n monitoring -w` in another terminal.

When `helm install` returns:

```bash
kubectl get pods -n monitoring
```

You should see:

```
NAME                                                     READY   STATUS    RESTARTS   AGE
alertmanager-kps-kube-prometheus-stack-alertmanager-0    2/2     Running   0          2m
kps-grafana-xxxxxxxx-xxxxx                               3/3     Running   0          2m
kps-kube-prometheus-stack-operator-xxxxxxxx-xxxxx        1/1     Running   0          2m
kps-kube-state-metrics-xxxxxxxx-xxxxx                    1/1     Running   0          2m
kps-prometheus-node-exporter-xxxxx                       1/1     Running   0          2m
prometheus-kps-kube-prometheus-stack-prometheus-0        2/2     Running   0          2m
```

Six pods. Each has a job:

- `alertmanager-...-0` — the Alertmanager StatefulSet.
- `kps-grafana-...` — Grafana.
- `kps-kube-prometheus-stack-operator-...` — the Prometheus Operator. Watches `ServiceMonitor`, `PodMonitor`, `PrometheusRule`, `Prometheus`, `Alertmanager` CRDs and reconciles them.
- `kps-kube-state-metrics-...` — kube-state-metrics. Exposes `kube_*` metrics.
- `kps-prometheus-node-exporter-...` — node-exporter as a DaemonSet. Exposes `node_*` metrics.
- `prometheus-...-0` — the Prometheus StatefulSet.

If any pod is in `CrashLoopBackOff` or `Pending`, `kubectl describe pod -n monitoring <name>` reveals why. The most common issue is insufficient RAM on the kind node.

---

## Step 6 — Verify Prometheus is scraping

Port-forward the Prometheus UI:

```bash
kubectl port-forward -n monitoring svc/kps-kube-prometheus-stack-prometheus 9090:9090
```

Open <http://localhost:9090/targets>. You should see ~10-15 scrape jobs, all in state `UP`. Names you will recognize:

- `serviceMonitor/monitoring/kps-kube-prometheus-stack-apiserver` — the Kubernetes API server.
- `serviceMonitor/monitoring/kps-kube-prometheus-stack-kubelet` — every node's kubelet, including the cAdvisor metrics.
- `serviceMonitor/monitoring/kps-kube-prometheus-stack-node-exporter` — node-exporter.
- `serviceMonitor/monitoring/kps-kube-state-metrics` — kube-state-metrics.
- `serviceMonitor/monitoring/kps-kube-prometheus-stack-operator` — the Operator's own metrics.
- A few others (CoreDNS, etcd, kube-proxy, scheduler, controller-manager).

If any are `DOWN`, click them to see the error. On `kind`, the kube-proxy and controller-manager scrapes occasionally fail to start; restart the pods if so.

Try a query: in the search box at top, type `up` and press Enter. The graph shows every `up` series; all should be at value 1.

Try a more interesting query: `rate(prometheus_tsdb_head_samples_appended_total[5m])`. This is Prometheus's own ingest rate — how many samples it is writing per second. On the kind cluster you should see a few hundred per second.

---

## Step 7 — Verify Grafana

In a second terminal:

```bash
kubectl port-forward -n monitoring svc/kps-grafana 3000:80
```

Open <http://localhost:3000>. Log in:

- Username: `admin`
- Password: `admin`

You will be asked to change the password. For local dev, click "Skip".

Navigate to **Dashboards** in the left sidebar. The chart bundles ~25 dashboards in folders named "General", "Kubernetes / Compute Resources / ...", "Kubernetes / Networking / ...", "Node Exporter / ...". Click into "Kubernetes / Compute Resources / Cluster". You should see a populated dashboard with CPU and memory usage broken down by namespace.

Verify the data sources: **Connections -> Data sources**. There should be one entry, `Prometheus`, with the Prometheus URL set to `http://kps-kube-prometheus-stack-prometheus:9090`. We will add Loki and Jaeger in Exercise 3.

---

## Step 8 — Verify Alertmanager

```bash
kubectl port-forward -n monitoring svc/kps-kube-prometheus-stack-alertmanager 9093:9093
```

Open <http://localhost:9093>. The page shows "No alerts" — nothing has fired yet. That is expected.

Click **Status** at the top. The page shows the Alertmanager's loaded configuration. Scrolling down, the `route:` tree is the default the chart installs: `group_by: [namespace]`, `group_wait: 30s`, `group_interval: 5m`, `repeat_interval: 12h`. We will customize this in Exercise 2.

---

## Step 9 — Inspect what the chart created

```bash
kubectl get prometheus -n monitoring
kubectl get alertmanager -n monitoring
kubectl get servicemonitor -n monitoring
kubectl get prometheusrule -n monitoring
```

You should see:

- One `Prometheus` resource: `kps-kube-prometheus-stack-prometheus`.
- One `Alertmanager` resource: `kps-kube-prometheus-stack-alertmanager`.
- ~15 `ServiceMonitor` resources, one per scrape job.
- ~25 `PrometheusRule` resources, each containing a group of alerting and recording rules.

The chart's `PrometheusRule` objects are the *upstream* set of "common" Kubernetes alerts: `KubePodCrashLooping`, `KubeMemoryOvercommit`, `KubeAPIDown`, `NodeFilesystemAlmostOutOfSpace`, and so on. About 200 rules total. Spend 5 minutes paging through them with `kubectl get prometheusrule -n monitoring -o yaml | less`. These are the floor of cluster monitoring; whatever you add in Exercise 2 is on top.

---

## Step 10 — Write up what you saw

In your week-09 notes file:

1. The `kubectl get pods -n monitoring` output.
2. The list of scrape targets from `/targets`.
3. The top 5 dashboards you found most useful.
4. Three questions you still have.

The four questions you should be prepared to answer:

- **Q1.** Why is the Prometheus pod a `StatefulSet` and not a `Deployment`?
- **Q2.** What does the `kube_pod_status_phase{phase="Pending"}` metric tell you that `kubectl get pods` does not?
- **Q3.** Where in the running Prometheus pod is the scrape configuration stored, and how does the Operator update it?
- **Q4.** If you scaled Prometheus to 2 replicas, what would change in the storage layer?

Answers are in `SOLUTIONS.md`. Try them first.

---

## Cleanup (do not do this until end of week)

Do not tear down the cluster. Exercises 2, 3, and 4 and the mini-project all build on this cluster. When you do want to tear it down at the end of the week:

```bash
kind delete cluster --name w09
```

If you only want to free the helm chart:

```bash
helm uninstall kps -n monitoring
kubectl delete namespace monitoring
```

---

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `helm install` times out | Insufficient RAM | Close other apps; the chart needs ~3 GB |
| Prometheus pod in `CrashLoopBackOff` | Misformatted values file | `kubectl logs -n monitoring -l app.kubernetes.io/name=prometheus` |
| Targets `DOWN` for `kube-proxy` | Known kind issue | Restart the kube-proxy pods: `kubectl delete pods -n kube-system -l k8s-app=kube-proxy` |
| Grafana `503` | Sidecar not ready | Wait 60s, refresh |
| Port-forward fails | Another process on the port | `lsof -i :9090` and stop the other process |

---

## What is next

Exercise 2 — write your own `ServiceMonitor` for a small test deployment, then a `PrometheusRule` that fires when the test deployment's pod count drops below 1, then route the alert to a webhook running in the cluster.
