# Week 7 — Kubernetes from First Principles

> *A cluster is a database with a reconciliation loop. Everything else — pods, deployments, services, ingress — is a row in that database and the controller that watches that row.*

Welcome to Week 7 of **C15 · Crunch DevOps**. Week 1 told you what a container is. Week 2 made you build one well. Week 3 wired several together with `compose`. Week 4 shipped them to a registry on every merge. Week 5 turned a `terraform apply` into a real public-facing app. Week 6 took the human out of the deploy loop with Packer and a GitOps controller. This week we open the box you have been pointing controllers at since Wednesday of Week 6 — the `kind` cluster — and explain what is actually inside it.

The temptation, when you first meet Kubernetes, is to learn it as a list of commands. You memorize `kubectl apply -f`, you memorize that a `Deployment` makes pods and a `Service` makes them reachable, you memorize the YAML shape, and you ship. That works for about three weeks. Then a pod is stuck in `CrashLoopBackOff` and the error message is not in your memorized list, and you do not know what to do. The whole point of this week is to avoid that future by giving you the **mental model** first and the commands second. The mental model is small and the commands are infinite; learn them in the right order.

We use **Kubernetes 1.31+** (the version `kind` 0.24+ installs by default) on a **local `kind` cluster** (free, runs inside Docker, brings up in 60 seconds). No managed cluster, no cloud cost, no `GKE` / `EKS` / `AKS` keystrokes this week. The whole curriculum runs on your laptop. We will move to a managed cluster in Week 8; this week is the model.

The pivot from Week 6 is this: there, GitOps and immutable infrastructure were the *patterns*; Argo CD and Flux were the *implementations*. This week we open the implementation Argo CD and Flux were pointing at. By Sunday you will be able to draw the Kubernetes control plane on a whiteboard from memory, name every component, name what each one stores in etcd, and explain why a pod that crashes is restarted in under a second without anything you wrote being involved. The answer is "a controller is watching." The whole rest of this course is variations on that sentence.

---

## Learning objectives

By the end of this week, you will be able to:

- **Explain** the problem Kubernetes solves in one paragraph that does not use the word "orchestration": you have many containers, on many machines, that need to be placed, restarted, exposed, configured, and replaced, and you do not want a human in the loop for any of those operations.
- **Sketch** the control-plane / data-plane split on a whiteboard, label every component (API server, etcd, scheduler, controller-manager, cloud-controller-manager, kubelet, kube-proxy, container runtime), name what each one does in one sentence, and name what each one stores or does not store in etcd.
- **Describe** the API server as the single point of truth: every other component is a client of the API server; no component talks to etcd except the API server; this is why the API server's availability is the cluster's availability.
- **Name** the four properties of a Kubernetes object that every YAML you write must have (`apiVersion`, `kind`, `metadata`, `spec`), and explain why `status` is set by the controller and never by you.
- **Compose** the core objects from first principles: a `Pod` is the unit of scheduling; a `ReplicaSet` keeps N pods running; a `Deployment` rolls a `ReplicaSet` forward and back; a `Service` is a stable virtual IP that selects pods by label; `Endpoints` is the live list of pod IPs behind that Service; a `ConfigMap` is a key-value blob that mounts into a pod; a `Secret` is the same shape with a slightly different RBAC posture.
- **Operate** a `kind` cluster: bring one up, tear one down, install a workload, scale it, expose it, drift it, and watch the controller put it back. The keystrokes are the same on any Kubernetes cluster you will ever touch.
- **Read** `kubectl get`, `kubectl describe`, `kubectl explain`, and `kubectl get -o jsonpath` fluently. These four commands cover 95% of what you do as a Kubernetes operator in the first year.
- **Defend** the choice of labels and selectors as the binding mechanism between a `Service` and its `Pod`s, name the three failure modes of label-based binding (typo in the selector, label missing on the pod, two services with overlapping selectors), and write a one-line diagnostic for each.
- **Diagnose** a broken Deployment using only `kubectl describe`, the pod's events, and the container's logs — without reaching for a third-party tool, a debugger, or a search engine. The cluster tells you what is wrong; the skill is reading the cluster.
- **Write** a `readinessProbe` and a `livenessProbe` that distinguish the two states the cluster needs to know about ("is this pod ready to receive traffic?" vs "is this pod still alive at all?") and explain why the two probes solve different problems.

---

## Prerequisites

This week assumes you have completed **Weeks 1-6 of C15** and have the `kind` cluster from Week 6 either still running or trivially recreatable. Specifically:

- You have Docker (or Colima, or Podman with Docker compatibility) running on your laptop. `kind` brings Kubernetes up inside Docker; without a container runtime, none of this works.
- You can build a multi-stage Dockerfile and push the image to GHCR with a tag. You did this in Weeks 2, 3, and 4. We will use one of those images this week.
- You have `kind` (0.24+), `kubectl` (1.31+), and `docker` installed. Verify:

```bash
kind version
kubectl version --client
docker info | head -1
```

- You finished the Week 6 Exercise 2 (`Argo CD on kind`) and Exercise 3 (`Flux on kind`). Both involved a `kind` cluster you treated as a black box. This week we open the box.
- You can read YAML without panicking. If you cannot tell the difference between `image:` and `image:\n  - ...` at a glance, take 30 minutes with the [YAML spec quick reference](https://yaml.org/refcard.html) before Monday.
- You have ~6 GB of free RAM on your laptop. A single-node `kind` cluster needs 2-3 GB; the three-tier mini-project pushes it to 4-5 GB. If you are on a 16 GB laptop, close the browser tabs.

We use **Kubernetes 1.31+** (the latest stable line as of May 2026), **`kind` 0.24+** (the project that runs Kubernetes inside Docker; the name is short for "Kubernetes IN Docker"), and **`kubectl` 1.31+** (the CLI; rule of thumb: keep `kubectl` within one minor version of the cluster). We do not install **`minikube`** in this week's exercises — `kind` and `minikube` solve the same problem and we picked one — but the lectures cover both, and the mini-project notes a `minikube`-flavored variant for the curious.

If you are coming back to this material after a break, the two things that recently changed and matter this week are: (a) the **`PodSecurityPolicy`** resource was finally fully removed in 1.25; the replacement is **`PodSecurity` admission**, configured per-namespace; (b) the **client-side apply** workflow has been gradually deprecated in favor of **server-side apply** since 1.22, and `kubectl apply --server-side` is the recommended shape for new code in 2026.

---

## Topics covered

- The problem Kubernetes solves: bin-packing, restart-on-failure, rolling updates, service discovery, configuration injection, and credential injection for many containers on many machines. The history that produced it: Borg (Google, 2003-onward) → Omega (Google, 2013) → Kubernetes (Google + community, 2014 onward, CNCF since 2015).
- The pre-Kubernetes alternatives and why they lost: hand-rolled scripts, Capistrano, Puppet's exec resources, Mesos + Marathon, Docker Swarm (still maintained, still niche), Nomad (still maintained, smaller scope), and the spectrum of "container orchestrators" from 2014-2017.
- The control plane: API server (`kube-apiserver`), etcd, scheduler (`kube-scheduler`), controller manager (`kube-controller-manager`), cloud controller manager (`cloud-controller-manager`). What each one stores, what each one watches, what each one writes.
- The data plane: kubelet (the node-local agent), kube-proxy (the network plumbing), the container runtime (`containerd` in 2026; `docker-shim` was removed in 1.24), CNI plugins (the network), CSI plugins (the storage).
- The API server's role as the single source of truth: every read goes through it, every write goes through it, no component talks to etcd directly, the API surface is versioned (`apiVersion`), and the resources are introspectable (`kubectl explain`, `kubectl api-resources`).
- etcd: a strongly-consistent, watch-capable key-value store; the only stateful component in the control plane; the thing you back up; the thing that makes the cluster's availability bounded by etcd's availability.
- Controllers and the reconciliation loop: a controller is a process that watches a resource type, compares desired to actual, and converges. The reconciliation loop is the pattern. Every built-in controller (Deployment, ReplicaSet, StatefulSet, DaemonSet, Job, CronJob, EndpointSlice, ...) is an instance of this pattern; custom resources + custom controllers are how you extend the cluster.
- The core objects in composition order: `Pod` (the unit of scheduling) → `ReplicaSet` (keeps N pods alive) → `Deployment` (rolls ReplicaSets) → `Service` (stable virtual IP) → `Endpoints` / `EndpointSlice` (the live pod list). Plus `ConfigMap` and `Secret` (configuration injection), `Namespace` (the soft tenancy boundary), `Node` (the machine).
- Labels and selectors: the binding mechanism. Labels are key-value strings on objects; selectors are queries against labels (`app=hello,tier=frontend`). Services find pods by selector; Deployments find their pods by selector; you should be able to name what every label on your objects is for.
- `kubectl` as a thin layer on the API: `kubectl get` is `HTTP GET /apis/...`, `kubectl apply` is a `PATCH`, `kubectl describe` is `GET + events`. The `--v=8` flag prints every HTTP call, which is the fastest way to see this.
- The four `kubectl` flavors of object access: imperative commands (`kubectl run`, `kubectl expose` — fine for labs, anti-pattern in production), imperative object configuration (`kubectl create -f`), declarative object configuration (`kubectl apply -f` — the production default), and server-side apply (`kubectl apply --server-side` — the post-2022 production default).
- Readiness and liveness probes: the cluster's mechanism for "should this pod receive traffic?" (readiness) and "is this pod still alive?" (liveness). Three probe types (`httpGet`, `tcpSocket`, `exec`), and the failure-mode rules for each.
- `kind` vs `minikube` vs `k3d`: three free local-cluster options. `kind` is the project's de facto upstream test target; `minikube` is the most beginner-friendly; `k3d` is the K3s-flavored variant. We pick `kind`; we explain why the others exist.

---

## Weekly schedule

The schedule below adds up to approximately **35 hours**. As always, total is what matters; reshuffle within the week as your life demands.

| Day       | Focus                                                        | Lectures | Exercises | Challenges | Quiz/Read | Homework | Mini-Project | Self-Study | Daily Total |
|-----------|--------------------------------------------------------------|---------:|----------:|-----------:|----------:|---------:|-------------:|-----------:|------------:|
| Monday    | What problem k8s solves (Lecture 1)                          |    2h    |    1h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     5h      |
| Tuesday   | Control plane and the API server (Lecture 2)                 |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Wednesday | Core objects and how they compose (Lecture 3)                |    2h    |    2h     |     1h     |    0.5h   |   1h     |     0h       |    0.5h    |     7h      |
| Thursday  | Hands-on: `kubectl` the cluster (Exercise 2 + 3)             |    1h    |    2h     |     1h     |    0.5h   |   1h     |     1h       |    0.5h    |     7h      |
| Friday    | Mini-project — three-tier app on kind                        |    0h    |    0h     |     1h     |    0.5h   |   1h     |     3h       |    0.5h    |     6h      |
| Saturday  | Mini-project finish; readiness/liveness challenge            |    0h    |    0h     |     1h     |    0h     |   0h     |     2h       |    0h      |     3h      |
| Sunday    | Quiz, recap, tear down clusters                              |    0h    |    0h     |     0h     |    0.5h   |   0h     |     0h       |    0h      |     0.5h    |
| **Total** |                                                              | **7h**   | **7h**    | **4h**     | **3h**    | **5h**   | **6h**       | **2.5h**   | **34.5h**   |

---

## How to navigate this week

| File | What's inside |
|------|---------------|
| [README.md](./README.md) | This overview (you are here) |
| [resources.md](./resources.md) | Curated readings: kubernetes.io docs, CNCF talks, the K8s API reference |
| [lecture-notes/01-what-problem-k8s-solves.md](./lecture-notes/01-what-problem-k8s-solves.md) | The history (VMs → Docker → Swarm → Kubernetes), what problem it solves, the alternatives that lost |
| [lecture-notes/02-control-plane-and-the-api-server.md](./lecture-notes/02-control-plane-and-the-api-server.md) | API server, etcd, scheduler, controller manager, kubelet, kube-proxy, the reconciliation loop |
| [lecture-notes/03-the-core-objects-and-how-they-compose.md](./lecture-notes/03-the-core-objects-and-how-they-compose.md) | Pod → ReplicaSet → Deployment, Service → Endpoints, ConfigMap, Secret, labels and selectors |
| [exercises/exercise-01-bootstrap-a-cluster.md](./exercises/exercise-01-bootstrap-a-cluster.md) | Bring up a `kind` cluster, inspect every component, tear it down |
| [exercises/exercise-02-kubectl-the-cluster.md](./exercises/exercise-02-kubectl-the-cluster.md) | `get`, `describe`, `explain`, `-o jsonpath`, the four flavours of object access |
| [exercises/exercise-03-deploy-a-stateless-app.yaml](./exercises/exercise-03-deploy-a-stateless-app.yaml) | A complete manifest: Deployment + Service + ConfigMap, with a walkthrough |
| [exercises/SOLUTIONS.md](./exercises/SOLUTIONS.md) | Worked solutions, expected output, the diagnostic questions to ask when output diverges |
| [challenges/challenge-01-debug-a-broken-deployment.md](./challenges/challenge-01-debug-a-broken-deployment.md) | Five broken Deployments; find and fix each using only `kubectl describe` and the cluster's events |
| [challenges/challenge-02-write-a-readiness-and-liveness-probe.md](./challenges/challenge-02-write-a-readiness-and-liveness-probe.md) | Write probes for a Python API that does a slow startup and an occasional hang |
| [quiz.md](./quiz.md) | 10 multiple-choice questions |
| [homework.md](./homework.md) | Six practice problems |
| [mini-project/README.md](./mini-project/README.md) | Deploy a 3-tier app (nginx → Python API → Postgres) on a single `kind` cluster, all from YAML in git |

---

## A note on cost

Week 7 is the cheapest week of C15 since Week 2. The whole curriculum runs on your laptop.

```
┌─────────────────────────────────────────────────────┐
│  COST PANEL — Week 7 incremental spend              │
│                                                     │
│  kind cluster (local, in Docker)         $0.00      │
│  kubectl, docker, kind binaries          $0.00      │
│  Container images (pulled from GHCR /                │
│    Docker Hub, anonymous)                $0.00      │
│  Optional: keep Week 6 droplet running   $6 / wk    │
│    (only if you have not torn it down                │
│     yet; this week does not depend on it)            │
│                                                     │
│  Subtotal new spend this week:           $0.00      │
└─────────────────────────────────────────────────────┘
```

If you tore down the Week 6 droplet on Sunday, this week is genuinely free. If you left it up because you wanted to keep the mini-project running, the prorated weekly cost is around $6. The Week 7 mini-project does not depend on the Week 6 droplet — every byte of state we touch this week lives on your laptop.

The trade-off `kind` makes is RAM and disk: a single-node `kind` cluster is 2-3 GB of RAM at idle and about 4 GB of disk. The three-tier mini-project (nginx + Python API + Postgres) pushes the cluster to about 4-5 GB of RAM. If you are on a 16 GB laptop with Chrome, Slack, and a JetBrains IDE open, you will feel it. Close tabs.

---

## Stretch goals

If you finish early and want to push further:

- Read the **Kubernetes API reference** at <https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.31/> end to end for the resources we cover this week (`Pod`, `ReplicaSet`, `Deployment`, `Service`, `Endpoints`, `ConfigMap`, `Secret`). It is dry; it is also the canonical answer to every "what fields can I set on this object" question, and the time it takes to read scales with the time it saves you in the next year.
- Read the **kubelet source** at <https://github.com/kubernetes/kubernetes/tree/master/pkg/kubelet>, specifically `pkg/kubelet/kubelet.go`'s `syncPod()` function. About 200 lines of Go. After this you will understand what the kubelet actually does when the API server tells it "schedule this pod" — and the diagnostic questions to ask when a pod is `Pending` get sharper.
- Install **`k9s`** (`brew install k9s`) and learn three commands in it. `k9s` is the terminal UI for Kubernetes that every operator picks up after a few months. It is not a replacement for `kubectl` (you still need to be fluent in `kubectl` for scripts, CI, and `--dry-run`), but for *operating* a cluster interactively, it is faster.
- Read the **KEP index** at <https://github.com/kubernetes/enhancements/tree/master/keps>. KEPs (Kubernetes Enhancement Proposals) are how every new feature in the project lands. Pick one that interests you (KEP-3257 on sidecar containers, KEP-4381 on container resize, KEP-4006 on transitioning from SPDY to WebSocket) and read its design doc. You will see the project's argumentation style and the level of detail required for a feature to land.
- Re-do the **Argo CD exercise from Week 6** against the cluster you stand up this week, this time *understanding* every line of the `Application` resource. Last week the `Application` was a black box pointed at a black-box cluster; this week neither is.

---

## Up next

Continue to **Week 8 — From Local to Managed: DigitalOcean Kubernetes** once you have shipped your Week 7 mini-project. Week 8 takes the same three-tier app you deployed on `kind` and moves it to a real managed cluster on DigitalOcean (DOKS), with a real ingress controller, real TLS via cert-manager, and a real LoadBalancer service. Week 9 then layers Helm (the templating layer) and operators (the custom-controller pattern) on top.

A note on the order: we deliberately put `kind` before the managed cluster, and the conceptual model before either. Many engineers learn Kubernetes by starting on GKE / EKS / AKS and treating the cluster as a black box, then spending two years failing to understand why pods get stuck or why services do not resolve. The black-box-first path is faster on day one and slower for the rest of your career. By doing `kind` first you see every component — the API server is a process you can `kubectl exec` into, etcd is a database you can `etcdctl get` from, the kubelet is a binary on a Docker container that is acting as a Kubernetes node — and the model gets fixed before any cloud opacity is added on top.

---

*If you find errors in this material, please open an issue or send a PR. Future learners will thank you.*
