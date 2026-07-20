# Mini-project — Instrument and report on a mis-sized workload

**Estimated time:** 3 to 5 hours.
**Due:** Sunday end-of-day.
**Prerequisites:** Exercises 1 through 4 completed; the `w11` kind cluster running.

The mini-project for Week 11 is a single end-to-end exercise that asks you to act in the role of a FinOps engineer at a hypothetical organization. The output is a complete artifact — a cost report, a right-sizing recommendation, and a one-page summary for engineering leadership — of the kind a real FinOps engineer would produce in a real organization.

The work splits into three parts. **Part A** instruments the workload. **Part B** produces the cost report. **Part C** produces the leadership summary. Each part has a deliverable.

You may work alone or in pairs. If you work in pairs, submit one set of deliverables and credit both names.

---

## Scenario

You have just joined the FinOps team at *Crunch Worldwide Foods*, a hypothetical 200-engineer SaaS company. The CFO has asked your team for a report on the engineering organization's cloud spend. Your manager has narrowed your scope to one cluster — a multi-tenant production Kubernetes cluster running ~50 workloads across ~15 teams. (For our exercise, you will use the `w11` kind cluster from Exercise 1 plus some additional workloads you will deploy in Part A.)

You have one week to produce three artifacts:

1. A **cost report** broken down by team, environment, and workload, with efficiency ratios for each workload.
2. A **right-sizing recommendation** for the three most over-provisioned workloads, prioritized by recoverable dollars.
3. A **one-page summary** for engineering leadership, suitable for inclusion in a quarterly review deck.

---

## Part A — Instrument

Deploy three additional workloads into the cluster, simulating real production diversity. The manifests are below; save as `mini-project/manifests-additional.yaml`. Apply them with `kubectl apply -f manifests-additional.yaml`.

```yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: team-growth
  labels:
    team: growth
    cost-center: cc-1004
    environment: production
---
apiVersion: v1
kind: Namespace
metadata:
  name: team-data
  labels:
    team: data
    cost-center: cc-1005
    environment: production
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: email-sender
  namespace: team-growth
  labels:
    app: email-sender
    team: growth
    cost-center: cc-1004
    environment: production
    owner: sre-growth
spec:
  replicas: 6
  selector:
    matchLabels:
      app: email-sender
  template:
    metadata:
      labels:
        app: email-sender
        team: growth
        cost-center: cc-1004
        environment: production
        owner: sre-growth
    spec:
      containers:
        - name: app
          image: nginx:1.27.0
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "1Gi"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: data-pipeline
  namespace: team-data
  labels:
    app: data-pipeline
    team: data
    cost-center: cc-1005
    environment: production
    owner: sre-data
spec:
  replicas: 2
  selector:
    matchLabels:
      app: data-pipeline
  template:
    metadata:
      labels:
        app: data-pipeline
        team: data
        cost-center: cc-1005
        environment: production
        owner: sre-data
    spec:
      containers:
        - name: app
          image: busybox:1.36
          command: ["/bin/sh", "-c", "while true; do dd if=/dev/zero of=/dev/null bs=1M count=10; sleep 1; done"]
          resources:
            requests:
              cpu: "300m"
              memory: "256Mi"
            limits:
              cpu: "600m"
              memory: "512Mi"
```

Wait at least 20 minutes for OpenCost to ingest the new workloads and produce a meaningful cost report. During the wait, port-forward OpenCost and Prometheus:

```bash
kubectl port-forward -n opencost svc/opencost 9003:9003 &
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090 &
```

---

## Part B — Cost report

Produce a cost report covering the last 24 hours, with the following sections:

### Section 1 — By team

Run:

```bash
python3 ../exercises/opencost_client.py --window 24h --aggregate "label:team"
```

Tabulate the output. Note which team has the highest total cost, the highest waste, the lowest efficiency.

### Section 2 — By environment

```bash
python3 ../exercises/opencost_client.py --window 24h --aggregate "label:environment"
```

How much of the cluster's cost is going to production vs staging vs unallocated.

### Section 3 — By team and environment combined

```bash
python3 ../exercises/opencost_client.py --window 24h \
  --aggregate "label:team,label:environment"
```

The matrix view. This is the canonical FinOps weekly report.

### Section 4 — Top 3 waste sources

Run the right-sizing report:

```bash
python3 ../exercises/rightsize_report.py --window 24h --margin 1.3
```

Capture the three workloads with the highest recoverable monthly waste. These are your right-sizing candidates for Part C.

### Section 5 — Unallocated cost

The `__unallocated__` and `__idle__` pseudo-groups represent cluster overhead, pods without team labels, and unscheduled resources. Compute the unallocated cost as a percentage of total cluster cost.

> **Target.** A healthy FinOps practice has unallocated cost below 10 percent of total. If your cluster's unallocated is above 10 percent, name the cause (typically kube-system or monitoring is unlabeled; that is expected and acceptable).

Compile all five sections into a single document: `mini-project/cost-report.md`.

---

## Part C — Right-sizing recommendations

For each of the three top-waste workloads from Section 4, produce a right-sizing recommendation document using the template from Exercise 2 Part F. The three documents:

1. `mini-project/rightsize-1.md`
2. `mini-project/rightsize-2.md`
3. `mini-project/rightsize-3.md`

Each document is one page, addressed to the workload's owner, with:

- Current state (workload, replicas, requests).
- Observed usage.
- Recommendation (new requests, new limits, unchanged replicas in most cases).
- Expected monthly savings.
- Blast radius and rollback plan.
- Risk assessment.

Use the actual numbers from the right-sizing report; do not invent them.

---

## Part D — Leadership summary

Produce a one-page summary, `mini-project/leadership-summary.md`, addressed to the VP of Engineering. The summary's audience is non-technical-detail; the audience cares about totals, trends, and the next quarter's actions.

Required content:

1. **Headline.** One sentence: "The cluster cost $X per month at current rates; we have identified $Y of monthly recoverable waste across N workloads, representing Z percent of total spend."
2. **By-team breakdown.** A table or bulleted list of the team costs from Part B Section 1, with one-line comments on each.
3. **The three right-sizing actions.** A bulleted list of the three workloads identified in Part C, with the recoverable dollar amount and the owner.
4. **The unallocated story.** A single paragraph naming the unallocated percentage and what the team is doing about it (label policy enforcement, quarterly hygiene, etc.).
5. **Next quarter.** Three concrete actions the FinOps team will take in the next quarter — for example: "(1) Apply the three right-sizing recommendations identified above. (2) Implement scheduled scale-down for staging environments per Challenge 1. (3) Run anomaly detection as a daily CronJob per Challenge 2."

Total length: one page. The discipline is brevity. A leadership summary that runs to three pages will not be read.

---

## Submission

Submit all files in a single directory named `mini-project-w11`:

```
mini-project-w11/
├── manifests-additional.yaml
├── cost-report.md
├── rightsize-1.md
├── rightsize-2.md
├── rightsize-3.md
└── leadership-summary.md
```

Either commit to your homework repo or hand in as a zipped folder.

---

## Grading rubric

- **Cost report completeness** (25 percent). All five sections present, with real numbers and real interpretation.
- **Right-sizing recommendations** (30 percent). Three workloads, each with a complete document, defensible numbers, and a real rollback plan.
- **Leadership summary** (30 percent). One page, written for the audience, with the five required sections.
- **Operational thinking** (15 percent). Did you notice anything not asked for. Did you call out the unallocated bucket. Did you propose the next quarter's actions in a way that sounds like a real plan.

A passing submission scores 60 percent overall. A strong submission scores 80 percent or higher.

---

## What this exercise is teaching

The technical work this week — OpenCost, Kyverno, Python — is the easy half. The work that compounds across a career is the work this mini-project asks for: producing the artifacts that translate technical measurement into business decisions. A FinOps engineer's job is not to install OpenCost. It is to be the person who, when the CFO asks "what is engineering spending and what is the plan", produces the answer.

The mini-project is the smallest version of that artifact. Produce it once; the second time is faster. Produce it monthly for a year; the practice becomes structural. That is the discipline.

Good luck.
