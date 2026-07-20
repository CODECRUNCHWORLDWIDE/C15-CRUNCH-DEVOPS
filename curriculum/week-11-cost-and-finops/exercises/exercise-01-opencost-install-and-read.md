# Exercise 1 — Install OpenCost on `kind` and read the allocation API

**Estimated time:** 60 minutes.
**Prerequisite reading:** Lecture 1.
**Files used:** `kind-w11.yaml`, `manifests-opencost-values.yaml`, `manifests-workloads.yaml`, `opencost_client.py`.

The goal of this exercise is to stand up a fresh `kind` cluster, install kube-prometheus-stack and OpenCost, deploy three small workloads, and read OpenCost's `/allocation` API. By the end you will have a JSON response that shows cost broken down by namespace.

We use only free, open-source components. OpenCost is the CNCF-incubating project at <https://www.opencost.io/>. The Helm chart is at <https://github.com/opencost/opencost-helm-chart>.

---

## Part A — Spin up the cluster

From the `exercises/` directory:

```bash
kind create cluster --name w11 --config kind-w11.yaml
kubectl cluster-info --context kind-w11
kubectl get nodes
```

You should see one control-plane and two worker nodes. If `kind create` fails because port 30090 is in use, edit `kind-w11.yaml` to use a different host port or remove the `extraPortMappings` block (the exercises do not require NodePort exposure).

Set the current context (kind already did this, but be explicit):

```bash
kubectl config use-context kind-w11
```

---

## Part B — Install kube-prometheus-stack

OpenCost reads from a Prometheus that scrapes kube-state-metrics, cAdvisor, and node-exporter. The kube-prometheus-stack chart installs all four in one shot.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --version 65.0.0 \
  --set prometheus.prometheusSpec.retention=15d \
  --set prometheus.prometheusSpec.resources.requests.memory=400Mi \
  --set grafana.enabled=false \
  --set alertmanager.enabled=false \
  --wait \
  --timeout 10m
```

Notes on the flags:

- `grafana.enabled=false` saves ~150 MB and a pod. We will not use Grafana this week; OpenCost ships its own minimal UI.
- `alertmanager.enabled=false` saves another pod. We do not fire alerts this week; anomaly detection is run as a Python script on demand.
- `--version 65.0.0` pins a known-good chart version. Newer versions occasionally rename keys; pin in CI.

Verify Prometheus is up:

```bash
kubectl get pods -n monitoring
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=prometheus \
  -n monitoring --timeout=180s
```

You should see `prometheus-monitoring-kube-prometheus-prometheus-0` Running.

A quick smoke test that kube-state-metrics is exporting:

```bash
kubectl port-forward -n monitoring svc/monitoring-kube-state-metrics 8080:8080 &
KSM_PF_PID=$!
sleep 2
curl -s http://localhost:8080/metrics | grep -E '^kube_pod_info' | head -5
kill $KSM_PF_PID
```

If you see lines beginning with `kube_pod_info{...}`, kube-state-metrics is exporting correctly.

---

## Part C — Install OpenCost

Add the OpenCost Helm repository:

```bash
helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm repo update
```

Install OpenCost with our prepared values:

```bash
helm install opencost opencost/opencost \
  --namespace opencost \
  --create-namespace \
  --version 1.45.0 \
  --values manifests-opencost-values.yaml \
  --wait \
  --timeout 5m
```

The values file points OpenCost at the in-cluster Prometheus we just installed (`prometheus-monitoring-kube-prometheus-prometheus.monitoring.svc:9090`) and provides a custom rate card approximating AWS us-east-1 m6i pricing.

Verify OpenCost is up:

```bash
kubectl get pods -n opencost
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=opencost \
  -n opencost --timeout=180s
```

Two pods should be Running — the exporter and the UI.

---

## Part D — Deploy the test workloads

Apply the three deliberately mis-sized Deployments from `manifests-workloads.yaml`:

```bash
kubectl apply -f manifests-workloads.yaml
```

This creates three namespaces (`team-platform`, `team-payments`, `team-analytics`) with one Deployment each. Two are mis-sized (`ratings-api`, `report-generator`), one is right-sized (`checkout-api`). The differences will surface in the OpenCost output once it has accumulated enough data.

> Note: applying `manifests-workloads.yaml` also attempts to create the `unlabeled-app` Deployment in `team-platform`. With no Kyverno policy installed yet, this Deployment will succeed. Exercise 2 installs the Kyverno policy and the Deployment will then be refused.

Verify the pods are running:

```bash
kubectl get pods -n team-platform
kubectl get pods -n team-payments
kubectl get pods -n team-analytics
```

Wait at least 5 minutes for OpenCost to accumulate cost data. OpenCost computes allocations on a 5-minute cycle; the first /allocation response is approximately empty.

---

## Part E — Read /allocation

Port-forward the OpenCost service to localhost:

```bash
kubectl port-forward -n opencost svc/opencost 9003:9003 9090:9090 &
OPENCOST_PF_PID=$!
sleep 2
```

The exporter API is on port 9003; the UI is on port 9090. Open <http://localhost:9090/> in a browser for the UI.

Pull an allocation report from the command line:

```bash
curl -s 'http://localhost:9003/allocation?window=24h&aggregate=namespace' \
  | python3 -m json.tool
```

You should see a JSON response with `code: 200` and a `data` array containing one entry per namespace. Each entry includes `totalCost`, `cpuCost`, `ramCost`, `cpuEfficiency`, `ramEfficiency`. The numbers may be small (single cents) because the workloads are small and the time window is short.

Now use our Python client:

```bash
python3 opencost_client.py --window 24h --aggregate namespace
```

Expected output is a fixed-width table. The mis-sized `ratings-api` should appear in `team-platform` with low CPU and RAM efficiency. The right-sized `checkout-api` in `team-payments` should have higher efficiency.

A second aggregation, by deployment:

```bash
python3 opencost_client.py --window 24h --aggregate deployment
```

And one filtered by namespace:

```bash
python3 opencost_client.py --window 24h --aggregate deployment \
  --namespace team-platform
```

---

## Part F — Checkpoint

Capture the following and paste into `SOLUTIONS.md`:

1. The output of `kubectl get pods -A` after the install completes.
2. The output of `python3 opencost_client.py --window 24h --aggregate namespace`.
3. A one-paragraph observation: which namespace has the highest `waste$` value, and why does that match what you would expect from the manifests in `manifests-workloads.yaml`?

The third item is the qualitative part. The discipline of cost engineering is reading these numbers in context — the manifest deliberately over-provisioned `ratings-api`, and the report should confirm it.

---

## Troubleshooting

**OpenCost shows zero cost for all namespaces.** OpenCost takes 5 to 10 minutes from start to first allocation. If it has been longer, check:

```bash
kubectl logs -n opencost -l app.kubernetes.io/name=opencost --tail 100
```

Look for "Could not fetch Prometheus" or "no data" messages. The most common cause is a mismatch between the Prometheus service name in `manifests-opencost-values.yaml` and the actual service name. Run:

```bash
kubectl get svc -n monitoring
```

The Prometheus service should be `monitoring-kube-prometheus-prometheus`. If it has a different name, edit the values file and `helm upgrade` OpenCost.

**The /allocation response is HTTP 400.** Common cause: an invalid filter syntax. Strip the filter parameter and retry the bare `aggregate=namespace` query first.

**OpenCost pods crash on start.** Check the resource limits in `manifests-opencost-values.yaml`. On constrained machines, increase the memory limit to 1Gi.

**OpenCost UI is empty.** The UI talks to the exporter via the cluster-internal service URL. If you port-forward to `9090:9090`, the UI loads but its API calls fail because they target the in-cluster URL. Use `kubectl port-forward` to expose both ports as in Part E; the UI is the secondary view this week, the API is primary.

---

## Tear-down

At the end of the week, delete the cluster:

```bash
kubectl delete -f manifests-workloads.yaml --ignore-not-found
helm uninstall opencost -n opencost
helm uninstall monitoring -n monitoring
kind delete cluster --name w11
```

Leave the cluster up for Exercises 2 and 3; tear down on Sunday after the mini-project.

---

## Reading

- OpenCost installation reference: <https://www.opencost.io/docs/installation/install>
- OpenCost configuration reference: <https://www.opencost.io/docs/configuration/configuration>
- OpenCost cost model: <https://github.com/opencost/opencost/blob/develop/docs/cost-model.md>
- OpenCost custom pricing: <https://github.com/opencost/opencost/blob/develop/docs/custom-pricing.md>
- kube-prometheus-stack chart values: <https://github.com/prometheus-community/helm-charts/blob/main/charts/kube-prometheus-stack/values.yaml>
- Prometheus query basics: <https://prometheus.io/docs/prometheus/latest/querying/basics/>

Continue to Exercise 2.
