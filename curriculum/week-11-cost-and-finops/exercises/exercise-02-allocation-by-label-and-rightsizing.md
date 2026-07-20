# Exercise 2 — Allocation by label, Kyverno enforcement, right-sizing

**Estimated time:** 75 minutes.
**Prerequisite reading:** Lecture 2.
**Files used:** `manifests-kyverno-cost-labels.yaml`, `manifests-workloads.yaml`, `opencost_client.py`, `rightsize_report.py`.

The goal of this exercise is to attribute cost not just to namespaces but to teams. We will install Kyverno, apply a policy that refuses production Pods missing cost-allocation labels, query OpenCost by label, and run the right-sizing script.

This is the first exercise where you produce a deliverable that resembles a real engineering artifact: a one-page right-sizing recommendation for the `ratings-api` workload.

---

## Part A — Install Kyverno

We need an admission controller to enforce the label policy. Kyverno is the most ergonomic choice on a fresh cluster. Reference: <https://kyverno.io/docs/installation/>.

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update

helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace \
  --version 3.3.0 \
  --wait \
  --timeout 5m
```

Verify:

```bash
kubectl get pods -n kyverno
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/component=admission-controller \
  -n kyverno --timeout=180s
```

---

## Part B — Apply the cost-label policy

The policy in `manifests-kyverno-cost-labels.yaml` refuses any Pod or Deployment in a namespace labeled `environment=production` that does not carry the four required labels: `team`, `cost-center`, `environment`, `owner`.

```bash
kubectl apply -f manifests-kyverno-cost-labels.yaml
```

Verify the policies are installed and reporting Ready:

```bash
kubectl get clusterpolicy
```

Both `require-cost-labels` and `require-cost-labels-on-deployments` should show `READY: true`.

---

## Part C — Confirm the policy works

The `team-platform` namespace already has `environment=production` (look at the namespace labels in `manifests-workloads.yaml`). Try to deploy an unlabeled pod:

```bash
kubectl run debug-pod \
  --image=busybox:1.36 \
  --restart=Never \
  --namespace=team-platform \
  -- sleep 60
```

Expected response: an error citing the policy:

```
Error from server: admission webhook "validate.kyverno.svc-fail" denied the
request: ... Production pods must carry labels: team, cost-center, environment, owner.
```

Now retry with the labels:

```bash
kubectl run debug-pod \
  --image=busybox:1.36 \
  --restart=Never \
  --namespace=team-platform \
  --labels="team=platform,cost-center=cc-1001,environment=production,owner=sre-platform" \
  -- sleep 60
```

This pod should be admitted. Clean it up:

```bash
kubectl delete pod debug-pod -n team-platform
```

Already-running pods (including `unlabeled-app` from Exercise 1) are not affected — Kyverno's `validationFailureAction: Enforce` applies on admission, not on update of in-cluster state. The `background: true` setting means Kyverno reports the violation in the PolicyReport CRD even for existing objects:

```bash
kubectl get policyreport -A
```

You should see a report against `unlabeled-app` showing the violation.

Delete the unlabeled deployment to clean up:

```bash
kubectl delete deployment unlabeled-app -n team-platform
```

---

## Part D — Query allocation by team label

Now the labels are enforced; OpenCost can aggregate by them. Port-forward OpenCost if you have not already:

```bash
kubectl port-forward -n opencost svc/opencost 9003:9003 &
sleep 2
```

Query by the `team` label:

```bash
python3 opencost_client.py --window 24h --aggregate "label:team"
```

You should see three groups: `platform`, `payments`, `analytics`. Each row reports total cost, CPU and RAM costs, efficiency, and waste. The `platform` team's row should show the highest waste dollars because `ratings-api` is deliberately over-provisioned.

Query by team and environment together:

```bash
python3 opencost_client.py --window 24h \
  --aggregate "label:team,label:environment"
```

You should see groups like `platform/production`, `payments/production`, `analytics/staging`. This is the matrix view that finance and engineering leadership use as their weekly report.

A filtered query — only production workloads:

```bash
python3 opencost_client.py --window 24h \
  --aggregate "label:team" \
  --label "environment=production"
```

---

## Part E — Run the right-sizing report

The right-sizing script joins OpenCost cost data against Prometheus P95 usage data and produces a recommendation per workload. Port-forward Prometheus as well:

```bash
kubectl port-forward -n monitoring \
  svc/monitoring-kube-prometheus-prometheus 9090:9090 &
sleep 2
```

Run the report:

```bash
python3 rightsize_report.py \
  --opencost-url http://localhost:9003 \
  --prom-url http://localhost:9090 \
  --window 24h \
  --margin 1.3
```

Expected output: one line per Deployment, showing current requests, observed P95, recommended requests, and approximate monthly recoverable dollars.

The line for `team-platform/ratings-api` should show a sizable gap between requests (CPU: 800m, RAM: 1024MiB per pod, times 3 replicas) and observed P95 (well under 50m / 64MiB, since the pod is idle nginx). The recommendation is to drop the requests dramatically.

The line for `team-payments/checkout-api` should show a smaller gap because that workload was right-sized to begin with.

The line for `team-analytics/report-generator` should show an even larger gap because the workload is doing nothing at all (it sleeps in a loop).

---

## Part F — Write the right-sizing recommendation

The deliverable for this exercise is a one-page Markdown document, addressed to the owner of the `ratings-api` workload (in our case, `sre-platform`). The template:

```markdown
# Right-sizing recommendation: team-platform/ratings-api

**Date:** 2026-05-XX
**Owner:** sre-platform
**Prepared by:** [your name]
**Status:** Awaiting owner sign-off

## Current state

- Deployment: `team-platform/ratings-api`
- Replicas: 3
- Per-pod requests: CPU 800m, memory 1Gi
- Per-pod limits:   CPU 1500m, memory 2Gi
- Aggregate reserved: 2.4 vCPU, 3 GiB across 3 replicas

## Observed usage (last 24h, P95)

- Per-pod CPU P95:    [from the report]
- Per-pod memory P95: [from the report]
- cpuEfficiency:      [from OpenCost]
- ramEfficiency:      [from OpenCost]

## Recommendation

Reduce per-pod requests to:
- CPU:    250m
- memory: 128Mi

Keep limits at:
- CPU:    500m
- memory: 256Mi

Replica count unchanged at 3.

## Expected savings

Approximately $XX / month. [from rightsize_report.py output, scaled to monthly]

## Blast radius

- The workload itself, only.
- HPA (if present) will scale based on the new request size; the autoscaling
  behavior changes shape slightly.
- No upstream service sees a change.

## Rollback plan

```bash
kubectl rollout undo deployment/ratings-api -n team-platform
```

Reverts in ~30 seconds to the previous ReplicaSet.

## Risk assessment

- **Low.** The workload is currently using <10% of its request; reducing by
  60% leaves ample headroom above observed P95.

## Action

Owner reviews and approves. SRE applies the change in a 24-hour window with
a watcher on memory usage. Reverify cost and efficiency one week later.
```

Fill in the bracketed numbers with the actual values from your right-sizing report. Save the document as `rightsize-ratings-api.md` and paste a copy into `SOLUTIONS.md` for grading.

---

## Part G — Checkpoint

Capture the following and paste into `SOLUTIONS.md`:

1. The output of `kubectl get clusterpolicy` showing both Kyverno policies Ready.
2. The error message from the failed `kubectl run` in Part C.
3. The output of `python3 opencost_client.py --window 24h --aggregate "label:team"`.
4. The output of `python3 rightsize_report.py --window 24h`.
5. The completed `rightsize-ratings-api.md` document from Part F.

---

## Reading

- Kyverno writing-policies: <https://kyverno.io/docs/writing-policies/>
- Kyverno installation: <https://kyverno.io/docs/installation/>
- OpenCost filters and aggregations: <https://www.opencost.io/docs/api>
- VPA recommendation mode (the automated version of right-sizing): <https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler>
- Goldilocks (a VPA-based right-sizing dashboard): <https://github.com/FairwindsOps/goldilocks>

Continue to Exercise 3.
