# Week 11 — Solutions

Paste your outputs and short-form answers here, one section per exercise. The grader looks for the right shape of output, not exact numerical match.

---

## Exercise 1 — Install OpenCost and read /allocation

### Part F.1 — `kubectl get pods -A`

Expected: pods Running in `monitoring`, `opencost`, `team-platform`, `team-payments`, `team-analytics`, `kube-system` namespaces. Approximate count: 15 to 20 pods total.

```
NAMESPACE        NAME                                                        READY   STATUS    RESTARTS
kube-system      coredns-...                                                 1/1     Running   0
kube-system      kindnet-...                                                 1/1     Running   0
kube-system      kube-proxy-...                                              1/1     Running   0
monitoring       monitoring-kube-state-metrics-...                           1/1     Running   0
monitoring       monitoring-prometheus-node-exporter-...                     1/1     Running   0
monitoring       prometheus-monitoring-kube-prometheus-prometheus-0          2/2     Running   0
opencost         opencost-...                                                2/2     Running   0
team-analytics   report-generator-...                                        1/1     Running   0
team-payments    checkout-api-...                                            1/1     Running   0
team-platform    ratings-api-...                                             1/1     Running   0
team-platform    unlabeled-app-...                                           1/1     Running   0
```

### Part F.2 — `python3 opencost_client.py --window 24h --aggregate namespace`

Expected: a fixed-width table. The `team-platform` and `team-analytics` rows should show high `waste$` values relative to their `total$` values, because their workloads are deliberately mis-sized. The `team-payments` row should show low waste.

```
name                              total$     cpu$     ram$  cpuEff  ramEff   waste$
----------------------------------------------------------------------------------------
team-platform                     0.0612   0.0410   0.0202    0.04    0.08   0.0563
team-analytics                    0.0428   0.0298   0.0130    0.01    0.05   0.0424
team-payments                     0.0049   0.0036   0.0013    0.21    0.43   0.0039
opencost                          0.0143   0.0098   0.0045    0.05    0.21   0.0136
monitoring                        0.0260   0.0180   0.0080    0.18    0.31   0.0213
kube-system                       0.0084   0.0050   0.0034    0.32    0.45   0.0057
```

The numbers will differ on your machine; the shape (team-platform and team-analytics having the worst efficiency) is what matters.

### Part F.3 — Observation

`team-platform` shows the highest absolute waste because `ratings-api` runs 3 replicas, each requesting 800m CPU and 1Gi memory, but is an idle nginx — its observed CPU is well under 50m per pod. The reserved-but-unused capacity is large in absolute terms.

`team-analytics` shows a similarly low efficiency because `report-generator` is a busybox sleeping in a loop; it requests 250m / 256Mi per pod across 4 replicas, and uses essentially none of it.

`team-payments` was right-sized at deployment (50m / 64Mi requests against an idle nginx that uses ~10m / 30Mi), so its efficiency is the highest of the three and its waste is the lowest in absolute terms.

---

## Exercise 2 — Allocation by label, Kyverno enforcement, right-sizing

### Part G.1 — `kubectl get clusterpolicy`

```
NAME                                       ADMISSION   BACKGROUND   READY   AGE   FAILURE POLICY
require-cost-labels                        true        true         True    1m    Fail
require-cost-labels-on-deployments         true        true         True    1m    Fail
```

### Part G.2 — Failed `kubectl run`

```
Error from server: admission webhook "validate.kyverno.svc-fail" denied the
request: resource Pod/team-platform/debug-pod was blocked due to the following
policies

require-cost-labels:
  check-required-cost-labels: |
    validation error: Production pods must carry labels: team, cost-center,
    environment, owner. See team standard for cost allocation. rule
    check-required-cost-labels failed at path /metadata/labels/team/
```

### Part G.3 — `python3 opencost_client.py --window 24h --aggregate "label:team"`

```
name                              total$     cpu$     ram$  cpuEff  ramEff   waste$
----------------------------------------------------------------------------------------
platform                          0.0612   0.0410   0.0202    0.04    0.08   0.0563
analytics                         0.0428   0.0298   0.0130    0.01    0.05   0.0424
payments                          0.0049   0.0036   0.0013    0.21    0.43   0.0039
__unallocated__                   0.0487   0.0328   0.0159    0.18    0.31   0.0399
```

The `__unallocated__` row represents the kube-system, opencost, and monitoring namespaces — none of which have a `team` label.

### Part G.4 — `python3 rightsize_report.py --window 24h`

```
Right-sizing report
===================
team-platform/ratings-api: req 2.40c/3072MiB -> p95 0.04c/41MiB; recommend 0.05c/64MiB; ~$56.23/mo recoverable
team-analytics/report-generator: req 1.00c/1024MiB -> p95 0.01c/8MiB; recommend 0.05c/64MiB; ~$38.91/mo recoverable
team-payments/checkout-api: req 0.10c/128MiB -> p95 0.02c/41MiB; recommend 0.05c/64MiB; ~$2.40/mo recoverable
```

### Part G.5 — `rightsize-ratings-api.md`

[The completed right-sizing recommendation document — see exercise-02-allocation-by-label-and-rightsizing.md Part F for the template]

---

## Exercise 3 — Cost anomaly detection in Python

### Part G.1 — Self-test

```
self-test: OK (6 cases)
```

### Part G.2 — Steady-state run (after Part B)

```
no anomalies detected
```

Or, on a freshly-created cluster, a small number of false positives from the percent-change rule firing on the first day against the zero-baseline.

### Part G.3 — After induced spike (Part D)

```
team-analytics: today $0.4250 vs baseline $0.0680 (+525.0%) > 50.0%
```

Exact percentage will differ; the rule should fire on `team-analytics` and not on `team-platform` or `team-payments`.

### Part G.4 — When does the z-score rule fire instead of the percent-change rule?

The percent-change rule fires on a single-day spike where today's cost is much higher than the day-of-week baseline from one week earlier. It is the right rule for autoscaler runaways and one-off log-pipe explosions.

The z-score rule is more useful for slower drifts — a workload whose cost has been creeping up by 5 to 10 percent per day, never crossing the 50-percent threshold in a single day, but which has accumulated several standard deviations of deviation from its rolling mean. This is the pattern of organic growth that should be flagged for review even when no single day looks anomalous.

A production system runs both rules in parallel. The percent-change rule fires on sudden incidents; the z-score rule fires on slow drifts.

---

## Exercise 4 — Pricing calculator workflow

### Part E.1 — AWS Pricing Calculator share URL

[Paste the share URL from <https://calculator.aws/>.]

### Part E.2 — GCP Pricing Calculator share URL

[Paste the share URL from <https://cloud.google.com/products/calculator>.]

### Part E.3 — Comparison

AWS top three line items: EC2 instances, RDS instance + storage, Application Load Balancer.
GCP top three line items: Compute Engine instances, Cloud SQL instance + storage, Cloud Load Balancing.

The two totals were within ~15 percent of each other. AWS came out slightly cheaper for the compute (m6i pricing is currently a fraction lower than n2 in this comparison), GCP came out slightly cheaper for the load balancer.

### Part E.4 — Aurora Serverless v2 trade-off

Aurora Serverless v2 is cheaper when the workload has variable traffic that exercises low average ACU consumption — for example a development environment used only during business hours, or a workload with strong diurnal traffic patterns. The 0.5 ACU minimum keeps a baseline cost ($44/month) below the equivalent fixed-size instance.

It is more expensive when the workload has steady-state traffic at or above the equivalent fixed-instance ACU rating. A 4-ACU workload on Serverless v2 costs ~$350/month; the equivalent fixed db.r6g.large is ~$190/month. The Serverless price premium is roughly 50 to 100 percent on a steady workload.

The rule of thumb: variable traffic with average utilization below 50 percent — Serverless v2 wins. Steady traffic above 70 percent — fixed-size wins. In between is judgement.

---

## Final checklist

Before submitting:

- [ ] Exercise 1 checkpoint pasted above.
- [ ] Exercise 2 checkpoint pasted above, including the right-sizing document.
- [ ] Exercise 3 checkpoint pasted above.
- [ ] Exercise 4 checkpoint pasted above, including calculator share URLs.
- [ ] One challenge attempted (see `challenges/`).
- [ ] Mini-project completed (see `mini-project/README.md`).
- [ ] Quiz completed (see `quiz.md`).

Submit the four files: this document, the challenge document, the mini-project report, and the quiz answers.
