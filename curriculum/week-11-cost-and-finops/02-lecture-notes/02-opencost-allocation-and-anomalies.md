# Lecture 2 — OpenCost: Allocation, Efficiency, and Anomalies

> *Half of cost engineering is making the bill addressable. A bill is addressable when you can show a developer the rectangle of it that is theirs.*

Yesterday we installed OpenCost. The pods are running. The `/allocation` endpoint returns JSON. Today we read that JSON. We will spend the lecture on three questions. **How does OpenCost compute the numbers it shows?** **How do we attribute those numbers to teams, services, and engineers?** **How do we detect when one of those numbers has gone wrong?**

The first question is about the cost model. The second is about labels and aggregation. The third is about anomaly detection — the two flavors that matter most in practice (autoscaler runaways, log-pipe explosions) and the simple statistics that flag them.

By the end of the lecture you should be able to look at any OpenCost allocation response and (a) explain where each number came from, (b) re-aggregate it by any label you like, (c) write the Python that flags it as anomalous when it deviates from its baseline.

---

## 1. The OpenCost cost model

OpenCost is a controller that reads from Prometheus, reads from a pricing source, and writes nothing to the cluster (except its own internal cache). It exposes an HTTP API that the Kubecost UI, kubectl-cost, and downstream tooling consume. The cost model — how OpenCost arrives at a number — is documented at <https://github.com/opencost/opencost/blob/develop/docs/cost-model.md>. The essentials follow.

### 1.1 Data sources

OpenCost cross-joins three streams of data.

**Stream 1: cluster topology and assignment.** Read from kube-state-metrics. Which pods exist, which nodes they were scheduled on, what labels they carry, what their resource requests are, what PVCs they bind to. Prometheus metric examples:

- `kube_pod_container_resource_requests` — CPU and memory requests per container.
- `kube_pod_info` — pod-to-node assignment.
- `kube_pod_labels` — pod labels (kube-state-metrics emits one time series per pod labeled with the pod's labels).
- `kube_persistentvolume_info` and `kube_persistentvolumeclaim_info` — storage topology.

**Stream 2: actual resource usage.** Read from cAdvisor (via the kubelet) and node-exporter. Pod CPU and memory usage at second-granularity. Network bytes sent and received per pod. Disk I/O per pod. Prometheus metric examples:

- `container_cpu_usage_seconds_total` — counter, CPU seconds consumed.
- `container_memory_working_set_bytes` — gauge, working-set memory.
- `container_network_transmit_bytes_total` and `container_network_receive_bytes_total` — counters, network bytes.

**Stream 3: cloud pricing.** Read from the cloud-provider pricing API (AWS, GCP, Azure) or from a built-in default rate card if no cloud is configured. OpenCost's built-in defaults approximate AWS on-demand pricing for major instance families; they are documented at <https://github.com/opencost/opencost/blob/develop/docs/custom-pricing.md>. The data: hourly rate per instance type per region, per-GB-month rate per storage class, per-GB rate for network egress.

### 1.2 The allocation calculation

OpenCost computes, for each pod in each time window, the pod's share of the underlying assets (node, disk, load balancer, network). The formula, simplified:

```
pod_cost_in_window = node_cost_in_window
                   * (pod_cpu_share + pod_ram_share) / 2
```

where:

```
pod_cpu_share = pod_cpu_request_or_usage / node_cpu_allocatable
pod_ram_share = pod_ram_request_or_usage / node_ram_allocatable
```

The choice of request-vs-usage in the share calculation is configurable. The OpenCost default is to use *the maximum of request and usage* — a pod that requested 1 vCPU but used 1.5 is charged on the 1.5; a pod that requested 1 but used 0.2 is charged on the 1. This is more pessimistic than usage-only and more permissive than request-only; the rationale is that you cannot un-reserve the capacity, but if the pod is over-using its limit it is consuming real cycles.

Storage is allocated similarly. Each PersistentVolumeClaim is charged at the underlying PV's cost — typically a per-GB-month rate from the cloud provider's pricing for that StorageClass. Network is allocated per pod by the pod's share of the node's network egress, attributed against the egress price.

The result, for one pod in one one-hour window, is a single dollar figure. Sum across pods to get namespace cost. Sum across namespaces to get cluster cost. Aggregate by label to get team cost.

### 1.3 Efficiency

OpenCost also computes an **efficiency** ratio per pod:

```
cpu_efficiency = average_cpu_used / cpu_requested
ram_efficiency = average_ram_used / ram_requested
```

A pod with `cpu_efficiency: 0.2` is using 20 percent of what it reserved. The reciprocal is the over-provision waste: `(1 - efficiency) * cost` is the dollar amount paid for capacity reserved but not used.

The efficiency number is the headline number for right-sizing. A pod with `efficiency: 0.95` is well-sized; a pod with `efficiency: 0.15` is a candidate for a request reduction. The exact threshold is judgement — typical guidance is to right-size pods whose 14-day P95 usage is less than 40 percent of request. Below 40 percent the right-sizing savings are usually worth the engineering cost of the change.

---

## 2. The `/allocation` endpoint

The single most important OpenCost endpoint. It accepts a window (relative or absolute), an aggregation key (or list of keys), and a set of filters. It returns a JSON document with one entry per group, each entry containing cost, efficiency, and resource-totals fields.

### 2.1 A canonical request

```
GET /allocation?window=24h&aggregate=namespace
```

Returns, per namespace, the last 24 hours of cost. The response:

```json
{
  "code": 200,
  "data": [
    {
      "default": {
        "name": "default",
        "properties": {
          "namespace": "default",
          "cluster": "w11"
        },
        "window": {
          "start": "2026-05-13T00:00:00Z",
          "end":   "2026-05-14T00:00:00Z"
        },
        "cpuCoreHours":      0.78,
        "cpuCost":           0.0125,
        "ramByteHours":      8.05e+12,
        "ramCost":           0.0094,
        "pvByteHours":       0.0,
        "pvCost":            0.0,
        "networkCost":       0.0,
        "loadBalancerCost":  0.0,
        "totalCost":         0.0219,
        "cpuEfficiency":     0.23,
        "ramEfficiency":     0.38
      },
      "opencost": {
        "name": "opencost",
        "totalCost": 0.0143,
        "cpuEfficiency": 0.05,
        "ramEfficiency": 0.21
      },
      "ratings-service": {
        "name": "ratings-service",
        "totalCost": 0.4892,
        "cpuEfficiency": 0.18,
        "ramEfficiency": 0.45
      }
    }
  ]
}
```

A few things to note in the response shape.

First, the costs are **dollars** (the unit is implicit; OpenCost assumes the pricing source uses USD unless configured otherwise). A `totalCost: 0.0219` is two cents over the 24-hour window. A real cluster's namespaces will routinely show single-digit dollar daily costs; production clusters will show hundreds of dollars per namespace per day.

Second, the **efficiency** fields are dimensionless ratios in `[0, 1]` — except they can occasionally exceed 1 when actual usage was higher than the request. This is the case for pods without a request set, or pods bursting above their request inside their limit.

Third, the **cpu / ram / pv / network / load-balancer** decomposition lets us trace where the cost came from. A namespace with a $50 daily cost that is 90 percent `loadBalancerCost` is a different problem from one whose cost is 90 percent `cpuCost`.

### 2.2 Aggregation keys

The `aggregate` parameter takes a comma-separated list of grouping keys. The valid keys, as of OpenCost 1.115:

- `namespace`, `cluster`, `node`, `controller`, `controllerKind`, `pod`, `container`.
- `label:KEY` for any pod label. `label:team`, `label:cost-center`, `label:app`, `label:environment` are the typical ones.
- `annotation:KEY` for any pod annotation. Less commonly used.
- `service`, `deployment`, `statefulset`, `daemonset`, `job` — convenience aggregations.

Multi-key aggregation joins on the keys: `aggregate=namespace,label:team` returns one entry per (namespace, team) pair. A pod with no `team` label appears in the `__unallocated__` group.

### 2.3 Filters

The `filter` parameter narrows the result before aggregation. Examples:

- `filter=namespace:"production"` — only the production namespace.
- `filter=label[team]:"platform"` — only pods labeled `team=platform`.
- `filter=cluster:"w11"+namespace!="kube-system"` — w11 cluster, excluding kube-system. The `+` is the AND combinator.

The filter syntax is documented at <https://www.opencost.io/docs/api>. Mastering the filter language is the single largest lift in becoming productive with OpenCost.

### 2.4 Windows

The `window` parameter accepts:

- A relative window: `24h`, `7d`, `30d`.
- A named window: `today`, `yesterday`, `lastweek`, `month`.
- An absolute window: `2026-05-01T00:00:00Z,2026-05-08T00:00:00Z`.

The retention is governed by Prometheus's retention. The default kube-prometheus-stack chart retains 15 days of metrics, so 30-day OpenCost queries against a fresh cluster will return partial data. For longer retention, use Thanos, Cortex, or Mimir as the Prometheus long-term storage backend.

---

## 3. Cost allocation in practice

The technical pieces are now in place. The harder part is the discipline.

### 3.1 The label policy

OpenCost can aggregate by any label that exists on the pods. The pods have those labels only if the team puts them there. The single largest cost-visibility improvement at most organizations is to enforce a label policy at admission.

The team-standard labels we will adopt this week:

| Label          | Purpose                                                                | Example                  |
| -------------- | ---------------------------------------------------------------------- | ------------------------ |
| `team`         | The engineering team that owns the workload                            | `platform`, `payments`   |
| `cost-center` | The finance cost center the workload should be billed to              | `cc-1234`, `cc-5678`     |
| `environment`  | The deployment environment                                              | `production`, `staging`  |
| `owner`        | The person or rotation responsible for paging on this workload         | `sre-platform`, `alice`  |
| `app`          | The application (one application may have many deployments)            | `checkout-api`           |

The Kyverno policy that enforces them — applied in tomorrow's exercise — refuses to admit a Pod (or a Deployment that would produce a Pod) missing any of the first four. The `app` label is recommended, not required, because OpenCost can fall back on the Deployment name.

A label policy is unglamorous. It is also the difference between a cost report that says "the production namespace cost $14,800 this month" and a cost report that says "the platform team's checkout API in production cost $14,800 this month, allocated to cost center 1234, owned by SRE-Platform". The first is data; the second is a conversation.

### 3.2 The unallocated bucket

Every cost-allocation system has an **unallocated** bucket — the cost that could not be attributed to a label, a team, or a workload. It exists because:

- Some pods (kube-system, kube-public) do not have team labels and never should.
- Some resources (nodes themselves, idle capacity, the cluster control plane) are not pod-scoped.
- Some workloads predate the label policy.

A healthy cluster's unallocated bucket is 5 to 15 percent of total cost. A cluster with a 40 percent unallocated bucket is failing its label policy; the team standard is to drive the bucket below 10 percent through quarterly hygiene passes. OpenCost's `__unallocated__` and `__idle__` pseudo-groups surface the unallocated cost as a first-class entry in aggregation responses.

### 3.3 The reporting cadence

The mature cadence: a per-team cost report mailed to each team's owner every Monday morning, showing the last week's cost broken down by the team's workloads, week-over-week change, and any anomalies the previous week's automation flagged. Engineers cannot ignore a number that arrives in their inbox; they will ignore a dashboard they have to navigate to.

The technical piece is small — an OpenCost query, formatted as HTML, sent via SES or SendGrid. We will write the query in Exercise 3 but not the email pipeline (the email-pipeline build is the C16 (CloudOps) curriculum's territory).

---

## 4. Anomaly detection

A cost anomaly is a workload or namespace whose cost has changed enough, suddenly enough, to warrant a human looking at it. The discipline is: detect the anomaly, alert a human, do not auto-remediate. Cost anomalies are sometimes legitimate (a deliberate scale-up for a launch); auto-remediation would scale them back and produce an outage.

Two practical algorithms.

### 4.1 Percentage-change rule

Flag a workload whose 24-hour rolling cost is more than 50 percent higher than its 24-hour cost from seven days ago. Compare day-of-week to day-of-week so that weekend-vs-weekday traffic patterns do not produce false positives.

```python
def is_anomaly_pct(
    cost_now: float,
    cost_baseline: float,
    threshold_pct: float = 50.0,
) -> bool:
    if cost_baseline <= 0.01:
        return cost_now > 0.10
    change_pct = ((cost_now - cost_baseline) / cost_baseline) * 100.0
    return change_pct > threshold_pct
```

The function is intentionally tolerant of small baselines — a workload that costs one cent today and two cents tomorrow is technically a 100 percent increase but is not interesting. The `0.01` and `0.10` thresholds are judgement values; a real implementation parameterizes them.

### 4.2 Standard-deviation rule

Flag a namespace whose daily cost is more than two standard deviations above its 14-day rolling mean. This is the *z-score* rule from elementary statistics, and it fires on roughly 2.5 percent of days in a stationary process — meaning a healthy cluster with 100 namespaces will flag 2 to 3 namespaces per day on average. The triage burden is manageable.

```python
import statistics

def is_anomaly_zscore(
    cost_today: float,
    cost_history: list[float],
    z_threshold: float = 2.0,
) -> bool:
    if len(cost_history) < 7:
        return False
    mean: float = statistics.mean(cost_history)
    stdev: float = statistics.stdev(cost_history)
    if stdev <= 0.0:
        return False
    z: float = (cost_today - mean) / stdev
    return z > z_threshold
```

Both algorithms produce false positives. The discipline is to triage, not to auto-remediate.

### 4.3 The two famous causes

In practice, the cost anomalies that fire most often have one of two causes.

**The autoscaler runaway.** An HPA is configured to scale on a custom metric — typically requests-per-second pulled from a Prometheus adapter, or queue depth from a Kafka topic. The metric source breaks. The HPA reads the failure as zero, or worse, as a stale value. The scaling logic interprets the value against the target and, depending on the direction, scales up unbounded or down to zero. The unbounded case is the expensive one.

The Deployment goes from 3 replicas to 150 replicas overnight. The cluster autoscaler provisions 15 new nodes to accommodate. The morning's bill shows roughly $360 of unexpected compute (15 nodes * 12 hours * $0.10/hour * some margin). If the engineer on call does not catch it, the cost runs all weekend.

The fix is twofold. **Prevent.** Configure the HPA's `behavior.scaleUp.policies` with a sensible step cap — typically no more than doubling the replica count per minute. **Detect.** Alert when `current_replicas == max_replicas` for more than 15 minutes, on the theory that hitting the ceiling is rarely intentional. Both Prometheus alert rules are short; we write them in Exercise 3.

**The log-pipe explosion.** An engineer changes a log level to DEBUG to investigate an issue. The change is applied. The investigation completes. The change is forgotten. The application now logs at DEBUG indefinitely; the log shipper sends 50x its baseline volume to the log aggregator. The aggregator is a third-party SaaS billed per GB ingested. The end-of-month bill shows a five-figure overage on log ingest.

The cost shape is different from the autoscaler runaway. There is no compute spike; the cluster looks normal. The egress is the giveaway: `networkCost` per namespace climbs over a few hours and stays climbed. The detection is a network-cost anomaly rule, applied at the namespace level on a 24-hour rolling window.

The fix, at the discipline level, is a Kyverno policy that refuses to set log level to DEBUG in production namespaces — engineers must use a feature-flag-style mechanism to enable debug logging for a limited window. The fix, at the budget level, is a log-aggregator volume budget enforced upstream of the cost surfacing.

### 4.4 The reporting cycle

The mature cycle: every morning, an automated job pulls the previous day's OpenCost allocation, computes both anomaly rules, and posts a list of flagged workloads to a Slack channel. The on-call SRE triages. Most days the list is empty or one item. Once a month the list flags a real incident the team would otherwise have caught only when the bill arrived.

We build a simplified version of this job in Exercise 3.

---

## 5. Kubecost vs OpenCost — the practical line

OpenCost is the open-source data layer. Kubecost is the SaaS product line built on top. The free-vs-paid lines, as of the May 2026 review:

| Feature                                       | OpenCost (free) | Kubecost free tier | Kubecost paid |
| --------------------------------------------- | --------------- | ------------------ | ------------- |
| Single-cluster cost data via API              | Yes             | Yes                | Yes           |
| Single-cluster web UI                         | Limited *       | Yes                | Yes           |
| Multi-cluster aggregation                     | No              | No (1 cluster)     | Yes           |
| Cost data retention                           | Prometheus's    | Prometheus's       | 365 days +    |
| RBAC on the UI                                | No              | No                 | Yes           |
| Anomaly detection (built-in)                  | No              | Limited            | Yes           |
| Right-sizing recommendations                  | Via API         | Yes (UI)           | Yes (UI)      |
| Savings reports                               | Via API         | Yes (UI)           | Yes (UI)      |

* OpenCost has a minimal web UI in the `opencost-ui` companion project. It is functional and free; it is not as polished as Kubecost's UI.

The judgement: for a single cluster or a small team, OpenCost is sufficient. For a fleet of clusters across regions, with finance stakeholders demanding consolidated reports and RBAC, Kubecost (or a self-built equivalent on top of OpenCost data piped to a warehouse) is the practical answer.

The other practical consideration: the in-cluster Kubecost product (the "free tier") and a vanilla OpenCost install differ mostly in UI polish. Either way the data is yours, in your cluster. Neither product egresses your cost data to a third party in the free configuration. The Kubecost SaaS paid tier (Kubecost Cloud) does aggregate cross-cluster, but the on-cluster free product does not.

---

## 6. A note on multi-cluster and on the OpenCost specification

A digression worth flagging. The OpenCost project's stated scope is the single cluster. The `/allocation` and `/assets` endpoints return data for the cluster the OpenCost pod runs in. A team running ten production clusters across regions has ten OpenCost installations, each with its own API.

The aggregation across clusters is the work that the Kubecost paid product does well and that an OpenCost-only setup has to build. The pattern for a roll-your-own multi-cluster setup is straightforward in shape: each cluster's OpenCost ships its allocation data to a central data store (typically a BigQuery / Snowflake / Athena warehouse) on a schedule; a small dashboard reads from the warehouse and presents the consolidated view. The work is engineering, not research; estimate a week or two for a competent team to build a v1 that covers their fleet.

The OpenCost specification at <https://github.com/opencost/opencost/blob/develop/spec/opencost-specv01.md> is the document that pins the data model — what fields an OpenCost-conforming implementation must emit, what their meanings are. The specification matters because, as the ecosystem matures, downstream tooling (dashboards, alerting, the multi-cluster aggregator just described) wants to consume OpenCost data from any conforming implementation, not just the reference one. Read the specification once if you plan to build downstream tooling; ignore it otherwise.

The CNCF graduation criteria for OpenCost include the specification's stabilization. The project is currently at *incubating* status; *graduated* status would require a v1 specification published with the typical CNCF process. Track the graduation status at <https://www.cncf.io/projects/opencost/> if you are placing long-term bets on OpenCost being the data layer the industry standardizes on.

A note on **OpenTelemetry as a possible future direction**. The OpenTelemetry project has begun discussing whether resource-usage and cost data should be a first-class signal alongside traces, metrics, and logs. If that direction lands (it has not as of May 2026), the per-cluster OpenCost pattern may evolve to a per-application instrumentation pattern, with cost data emitted as OpenTelemetry signals from the application itself rather than computed from cluster topology. The shift would be substantial; the timeline is years not months. We mention it here because the curriculum should not pretend the present setup is the permanent setup.

---

## 7. What we have, where we are going

We can now read OpenCost's allocation responses, aggregate by label, and reason about efficiency. We can flag anomalies with two simple statistics. We understand the line between the open-source project and the commercial product.

Tomorrow's exercise has us aggregating by label and producing a right-sizing recommendation for a deliberately mis-sized workload. Friday's lecture moves up a level — from the technical (here is the tool, here is the API) to the cultural (here is how teams adopt the discipline). The FinOps Foundation framework provides the vocabulary; the practice provides the muscle.

The cluster from Week 9 is observable. From Week 10, it is trustworthy. From this week, it is accountable. Three years from now, the engineering organization that has adopted all three is the one that can deliver new product without a finance fire-drill every quarter. That is the long pole, and that is what we are building.

We meet Friday for Lecture 3.
