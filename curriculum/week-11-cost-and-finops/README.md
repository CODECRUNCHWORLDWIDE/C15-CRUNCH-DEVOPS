# Week 11 — Cloud Cost Engineering and FinOps

> *The cheapest line of code is the one you do not run. The second cheapest is the one you run on a machine you already own. The third is the one you run on a machine you turn off when nobody is using it. Everything past that is somebody else's revenue.*

Welcome to Week 11 of **C15 · Crunch DevOps**. Last week we made the cluster trustworthy — secrets out of Git, images signed, SBOMs scanned, supply chain auditable. The artifacts that reach production now arrive with a paper trail. The cluster is observable, the cluster is governed, and the cluster has receipts.

This week the question changes again. It is no longer "is the service healthy" or "do I trust what is running" but "how much does it cost, and is that the right amount". The bill arrives at the end of the month. By then it is too late to argue with it. The discipline of asking that question continuously — of building a feedback loop between an engineer's deployment decisions on Monday and the line item that appears on the cloud bill three weeks later — is called **FinOps**. The FinOps Foundation ([finops.org](https://www.finops.org/)) defines it as "the operational framework and cultural practice which maximizes the business value of cloud". The catechism is shorter: every dollar that leaves the company should be traceable to a workload, that workload to a team, and that team should be able to defend the dollar.

We will spend the week on three axes. **First**, the unit-economics mindset — how a mature cloud team reasons about cost not in "we spent $40,000 on EC2 last month" terms but in "we spend $0.0012 per request, our daily active users have grown 40 percent, and our cost per active user has fallen from $0.18 to $0.13 over the quarter" terms. The transformation matters because the second view answers an executive's question — *is the unit economics improving* — and the first view does not. **Second**, the open-source tooling to actually measure this on Kubernetes. We will install **OpenCost** ([opencost.io](https://www.opencost.io/)) — the CNCF-incubating, fully free project that reads from Prometheus and from the cloud provider's pricing API and produces a per-namespace, per-workload, per-label cost breakdown updated every five minutes. We will discuss **Kubecost** ([kubecost.com](https://www.kubecost.com/)) as the SaaS commercial product built on top of OpenCost, and where the open-source and paid lines split. **Third**, the practice of cost governance — tag policies, anomaly detection, budget alerts, the FinOps Foundation framework's three phases (Inform, Optimize, Operate), and the FinOps Certified Practitioner certification track — all free guidance from a Linux Foundation project, and the certification itself is currently free for one attempt for individuals who complete the free coursework on the FinOps Foundation site as of the 2026 review window.

By Sunday you will have stood up a `kind` cluster with OpenCost installed, applied a workload deliberately mis-sized to demonstrate over-provisioning, exported a cost-allocation report by namespace and label, written a small Python tool to flag anomalies (a workload whose cost doubled day-over-day), and produced a one-page "right-sizing recommendation" document of the kind a real engineering team would circulate to the workload's owner. The cluster from Week 10 grows one more layer: it now knows what it costs to run, who to bill it to, and which of its resources are being paid for and not used.

---

## Learning objectives

By the end of this week, you will be able to:

- **Articulate** the unit-economics mindset and compute three primary unit metrics: cost per request, cost per active user (daily, monthly), and cost per GB processed (or per equivalent throughput unit appropriate to the workload). Explain why a falling absolute spend with a flat unit cost is not a win, and why a rising absolute spend with a falling unit cost usually is.
- **Decompose** any cloud bill into the three buckets — **compute** (instances, containers, serverless), **storage** (block, object, archive), **network** (data transfer in, out, cross-zone, cross-region) — and identify which of the three a given line item belongs to. Cite the AWS pricing structure at <https://aws.amazon.com/pricing/> and the GCP pricing structure at <https://cloud.google.com/pricing>.
- **Distinguish** the three primary purchase modalities — **on-demand**, **reserved / committed-use**, and **spot / preemptible** — and articulate the trade-off matrix: discount depth, commitment length, interruption risk, suitability per workload class. Reason about why a stateless web tier is a candidate for spot and a stateful Postgres primary is not.
- **Enumerate** the three biggest waste sources in a typical Kubernetes cluster: (1) **over-provisioned compute** — pods with requests set far above their actual use, holding capacity nobody benefits from; (2) **idle resources** — staging environments left running on weekends, orphaned PersistentVolumes from deleted workloads, ELBs attached to nothing; (3) **egress charges** — data transfer out of the cloud or across zones, almost always under-modeled at design time. Estimate the magnitude of each from a real cost report.
- **Install** OpenCost on a `kind` cluster via the official Helm chart ([github.com/opencost/opencost-helm-chart](https://github.com/opencost/opencost-helm-chart)). Configure it to scrape from kube-state-metrics and from a local Prometheus. Confirm it produces an `/allocation` API response within five minutes of a workload start.
- **Read** an OpenCost allocation response. Attribute cost by namespace, by label (`team`, `app`, `environment`), and by aggregation interval. Explain the difference between a "cost" (what was charged) and an "efficiency" (cost vs minimum-required cost given observed CPU and memory).
- **Configure** Kubernetes labels and annotations for **cost allocation** — the `team`, `cost-center`, `environment`, and `owner` labels we will adopt as the team standard. Reason about why a label policy enforced at admission (Kyverno / OPA) is the only label policy that survives contact with real engineers.
- **Identify** a cost anomaly: a workload whose cost rose more than 50 percent day-over-day, or a namespace whose cost is more than two standard deviations above its 14-day rolling mean. Write the Python that computes this from OpenCost's API and emits an alert. Reason about the two most common causes — an **autoscaler runaway** (HPA scaling to 200 replicas because a metric source broke) and a **log-pipe explosion** (the application started logging at DEBUG and the log shipper is now egressing 50x its baseline).
- **Reproduce** the FinOps Foundation framework: the six principles, the three phases (**Inform** — make cost visible; **Optimize** — reduce it; **Operate** — keep it reduced), and the personas (engineer, finance, leadership). Cite [finops.org/framework](https://www.finops.org/framework/). Reason about why "show the engineer the bill" is the single most effective cost intervention any organization can make.
- **Compute** a workload's cost in three places: (a) in the AWS Pricing Calculator at <https://calculator.aws/> using the published on-demand rate; (b) in the GCP Pricing Calculator at <https://cloud.google.com/products/calculator>; (c) on the running `kind` cluster via OpenCost's reported cost. Reason about the gap between the three.
- **Defend** a right-sizing recommendation. Given an OpenCost report showing a Deployment with `requests: {cpu: 1000m, memory: 2Gi}` but observed P95 use of `200m / 600Mi`, write the one-page document a SRE would send to the workload's owner — what to change, expected savings, blast radius, rollback plan.
- **Recognize** the four most common cost anti-patterns: (1) **the always-on staging environment**; (2) **the never-resized "we set it once" workload**; (3) **the unused PersistentVolume retained by `reclaimPolicy: Retain`**; (4) **the application that logs at DEBUG in production**. For each, cite the OpenCost / cloud cost report query that surfaces it.
- **Critique** a vendor pitch. The cloud cost SaaS market is loud. Read a Kubecost feature page and identify which features are in open-source OpenCost (free), which require Kubecost (paid), and which the team could build themselves on top of OpenCost in a week. Reason about which path makes sense for a five-person team and which for a five-hundred-person team.

---

## Prerequisites

This week assumes you have completed **Weeks 1-10 of C15**. Specifically:

- You finished Week 10's mini-project — a signed, SBOM-scanned, secrets-managed FastAPI service. We will not reuse that cluster directly; we will spin up `w11` fresh. The discipline you learned — Helm, manifests, reading controller logs — is what we use this week.
- You have `kind` (0.24+), `kubectl` (1.31+), `helm` (3.14+), `docker` running, `python3` (3.11+), and a fresh terminal. Verify:

```bash
kind version
kubectl version --client
helm version --short
docker info | head -1
python3 --version
```

- You have ~4 GB of free RAM. The Week 11 footprint is light — Prometheus (small retention), OpenCost (~150 MB), kube-state-metrics (~50 MB), our workloads (~500 MB). Plus 2 GB for the kind cluster itself.
- You understand Prometheus and `kubectl top` from Week 9 — we will read CPU and memory usage from Prometheus directly to compare against requests.
- You are comfortable parsing JSON from a REST API in Python. OpenCost's allocation API is JSON; the exercises script against it.
- You do **not** need an active cloud account this week. We use the AWS and GCP pricing calculators (free, no login) and OpenCost's local-mode pricing (a built-in default rate card that approximates AWS on-demand pricing for the major instance families). The point of the week is the discipline, not a real cloud bill.

We use **Kubernetes 1.31+**, **OpenCost 1.115+** (the version stream stabilized after the CNCF incubation graduation review), **kube-state-metrics 2.13+**, **Prometheus 2.55+** (via the kube-prometheus-stack chart 65.x), and **Kyverno 1.13+** for the label-policy exercise. All current; no deprecated APIs in this week's material. API versions used: `apps/v1` (Deployment), `v1` (Namespace, ConfigMap, Service, ServiceAccount), `policy/v1` (PodDisruptionBudget where referenced), `kyverno.io/v1` (ClusterPolicy), `monitoring.coreos.com/v1` (ServiceMonitor — installed by the kube-prometheus-stack CRDs).

If you are coming back to this material after a break, the relevant 2025-2026 changes are: (a) **OpenCost was accepted into CNCF incubation** in 2024 and the project has stabilized its `/allocation` and `/assets` API shapes; v1 of the API is now considered stable for downstream tooling. (b) **Kubecost — the SaaS — has consolidated its free tier**: the free, in-cluster Kubecost product (sometimes called "Kubecost Community") is the same thing as installing OpenCost plus the open-source frontend; the paid Kubecost tier adds multi-cluster aggregation, RBAC, and longer history. (c) **The FinOps Foundation framework was refreshed** for 2024 with explicit AI/ML cost guidance — relevant if you operate GPU workloads, which we do not this week but will revisit in C17 (LLMOps).

---

## Topics covered

- **The unit-economics mindset.** Why "we spent X" is the wrong question and "we spent X to deliver Y units" is the right one. The three primary unit metrics for a typical SaaS: cost per request, cost per DAU (daily active user) and MAU (monthly active user), cost per GB processed (or per equivalent throughput unit). The unit-economics tracking dashboard — usually a Grafana panel that divides cost from OpenCost by an application metric from Prometheus.
- **Cost decomposition.** Compute, storage, network. The three are not equal in any of: dollar share of the bill (compute usually dominates), engineering visibility (compute is the most visible, network is the least), or surprise factor (network is the highest, by a wide margin — engineers consistently under-model egress at design time).
- **Pricing modalities.** On-demand: pay per second, no commitment, full price. Reserved / committed-use: pay for a 1-year or 3-year commit, ~30 to 55 percent discount, must use it or waste it. Spot / preemptible: deeply discounted (~60 to 90 percent off) capacity that the cloud reclaims with minutes of notice. Suitability matrix: stateless and idempotent — spot is great; stateful primary databases — never spot; long-running steady-state baseline — reserved; bursty short-lived — on-demand.
- **The three waste sources.** (1) **Over-provisioned compute.** A pod with `requests: {cpu: 1000m, memory: 2Gi}` but observed P95 use of `200m / 600Mi` is paying for 800m of CPU and 1.4Gi of memory it is not using. The cluster autoscaler obligingly keeps a node around to satisfy the request. The cost difference is real cash. (2) **Idle resources.** Staging environments left on overnight and on weekends. Dev clusters with `restartPolicy` always running. PersistentVolumes that outlived their owning workloads because `reclaimPolicy: Retain`. ELBs that no Service still references. (3) **Egress charges.** Data transferred *out* of the cloud (to the public internet, to another cloud). Cross-zone (within the same region but across AZ). Cross-region. The price per GB is small per unit and devastating per terabyte.
- **OpenCost — what it is and what it measures.** A CNCF incubating project, founded by Kubecost and contributed to CNCF. Reads CPU/memory/disk/network usage from Prometheus. Reads node pricing from the cloud provider's pricing API (or a local default rate card). Allocates the node's cost across the pods that ran on it, proportional to their actual usage. Exposes a REST API at `/allocation` and `/assets` (assets = nodes, disks, load balancers — the things the cloud bills for) and `/cloudCost` (when wired to a cloud cost-and-usage report, optional). The same project, the same code, runs in production at multi-thousand-node fleets.
- **OpenCost vs Kubecost.** OpenCost is Apache-2.0 licensed. Kubecost the company sells a SaaS that ingests the OpenCost data from many clusters into a central dashboard, adds longer retention, RBAC, anomaly detection that is more sophisticated than the free version, and account-management features. The free, in-cluster Kubecost product is OpenCost with a polished UI. For a single cluster or a small fleet, OpenCost is the floor of capability and the floor of cost (zero).
- **Cost allocation by namespace, label, and annotation.** OpenCost reads Kubernetes labels off pods and aggregates by any combination. The team standard we will adopt: every workload's pod template has labels `team`, `cost-center`, `environment`, `owner`. Enforced by a Kyverno admission policy that refuses pods missing the labels. The discipline is unglamorous and it is the largest single multiplier in cost visibility.
- **Cost anomaly detection.** Two practical algorithms: (1) **percentage change** — flag a workload whose 24-hour rolling cost is more than 50 percent above its 24-hour cost from seven days ago; (2) **standard deviations** — flag a namespace whose daily cost is more than two standard deviations above its 14-day mean. Both fire on real anomalies, both also fire on false positives (a deliberate scale-up). The output is a list a human triages, not an automated action.
- **The two famous anomaly causes.** **Autoscaler runaway.** An HPA configured to scale on `requests_per_second` from a Prometheus adapter. The adapter loses its metric source. The HPA reads zero — or worse, NaN — and the scaling logic interprets that as "scale to max". The Deployment goes to 100 replicas overnight. The bill the next day reflects 100 replicas times 12 hours. The fix: `behavior.scaleUp.policies` with a sensible step cap, and an alert that fires when current replicas equals max replicas. **Log-pipe explosion.** An engineer changes the log level to DEBUG to debug an issue. The change is rolled out. The fix forgets to revert. The log shipper now egresses 50x its baseline data volume to the log aggregator. The aggregator is billed per GB ingested. The cost line at month-end is the surprise. The fix: a log-level annotation that an admission controller refuses to set to DEBUG in production namespaces, and a cost alert tied to log-aggregator volume.
- **The FinOps Foundation framework.** A Linux Foundation project ([finops.org](https://www.finops.org/)). The framework: six principles (teams need to collaborate, decisions are driven by the business value of cloud, everyone takes ownership of their cloud usage, FinOps reports should be accessible and timely, a centralized team drives FinOps, take advantage of the variable cost model of the cloud), three phases (Inform → Optimize → Operate), personas (engineer, finance, leadership), and a set of capabilities (cost allocation, anomaly management, forecasting, rate optimization, workload optimization). The FinOps Certified Practitioner certification is the discipline's entry credential; the courseware is free.
- **Tag governance.** Cloud-side tagging (AWS tags, GCP labels) is the analogue to Kubernetes labels and has the same hygiene problems. The largest single cost-visibility improvement at most organizations is making one tag — `cost-center` or `team` — mandatory and enforced at provisioning. AWS Tag Policies and GCP Resource Manager hierarchical labels are the cloud-side tools; for our cluster we use Kyverno.
- **Pricing calculators.** AWS Pricing Calculator (<https://calculator.aws/>) and GCP Pricing Calculator (<https://cloud.google.com/products/calculator>). Both free, both browser-based, both produce a shareable estimate URL. The discipline: every architecture proposal includes a calculator URL before it ships. The calculator is wrong by ~10 to 30 percent in either direction in practice — the discipline matters more than the number.
- **Right-sizing as a workflow.** OpenCost's `/allocation` endpoint reports cost; comparing it against observed CPU and memory from Prometheus identifies over-provisioned workloads. The right-sizing document is a one-page artifact: current requests, observed P95 usage, recommended requests, expected savings, blast radius, rollback plan. The owner of the workload signs off; the SRE applies the change.

---

## Schedule

| Day       | Focus                                                                         | Files                                                                 |
| --------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Monday    | Lecture 1 — Unit economics, cloud pricing, the three waste sources            | `lecture-notes/01-unit-economics-pricing-and-waste.md`                |
| Tuesday   | Exercise 1 — Install OpenCost on `kind`, read the allocation API              | `exercises/exercise-01-opencost-install-and-read.md`                  |
| Wednesday | Lecture 2 — OpenCost internals, cost allocation, anomalies                    | `lecture-notes/02-opencost-allocation-and-anomalies.md`               |
| Thursday  | Exercise 2 — Cost-by-label and a right-sizing report                          | `exercises/exercise-02-allocation-by-label-and-rightsizing.md`        |
| Friday    | Lecture 3 — The FinOps Foundation framework and the practice of cost culture  | `lecture-notes/03-finops-framework-and-culture.md`                    |
| Saturday  | Exercise 3 — Anomaly detection script; Exercise 4 — Pricing calculator review | `exercises/exercise-03-anomaly-detection.md`, `exercise-04-pricing-calculators.md` |
| Sunday    | Challenges, quiz, mini-project — instrument and report on a real workload     | `challenges/`, `quiz.md`, `mini-project/README.md`                    |

---

## How to run this week

Spin up a fresh kind cluster from `exercises/kind-w11.yaml`:

```bash
kind create cluster --name w11 --config exercises/kind-w11.yaml
kubectl cluster-info --context kind-w11
```

Install the kube-prometheus-stack and OpenCost from the manifests in `exercises/`. The first exercise walks the steps line by line. Subsequent exercises assume the install is complete and the OpenCost API is reachable at `http://opencost.opencost.svc.cluster.local:9003`.

Tear down the cluster at the end of the week:

```bash
kind delete cluster --name w11
```

---

## Deliverables

By Sunday evening, submit:

1. **All four exercises completed.** Each exercise has a checkpoint at the end — typically a JSON response, a Python script that runs to completion, or a `kubectl get` output. Paste the checkpoint output into `exercises/SOLUTIONS.md`.
2. **One of the two challenges completed.** The challenges are deeper than the exercises and the grading is rubric-based; see `challenges/README.md`.
3. **The mini-project.** Detailed in `mini-project/README.md` — instrument an intentionally mis-sized workload, produce a cost-allocation report grouped by `team` label, identify the most over-provisioned workload, and write a one-page right-sizing recommendation. Submit the report and the recommendation as a single PDF or Markdown file.
4. **The quiz.** Twenty questions; `quiz.md`. Closed-book the first pass; open-book the second pass with citations to OpenCost docs, FinOps Foundation framework, or the AWS / GCP pricing calculators where applicable.

---

## A note on tone

Cost engineering is, in a lot of organizations, a thing engineers actively dislike. It feels like accountancy. It feels like an interruption. It is neither — it is the single most undervalued lever on the long-term shape of an engineering organization, because every dollar saved on infrastructure is a dollar that funds the next hire or the next product bet. The teams that build the discipline early are the teams that, three years in, are not handed a "we must cut 30 percent" directive from finance with two weeks of notice. The discipline is unglamorous; the outcome is freedom.

The week is light on code by C15 standards — OpenCost installs itself, the API is a JSON endpoint, the Python is small. The week is heavy on judgement — every exercise asks you to make a recommendation, to defend it, to estimate magnitudes. That is what the discipline is, on a real team. The numbers come from the tools; the choices come from you.

Onward.
