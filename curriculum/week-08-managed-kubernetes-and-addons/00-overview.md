# Week 8 — Managed Kubernetes and the Add-On Layer

> *A managed cluster is a kind cluster you do not have to run. Everything you learned last week still applies; what changes is who pages whom at 3 a.m. when etcd's disk fills up.*

Welcome to Week 8 of **C15 · Crunch DevOps**. Last week we opened the box: the control plane, the data plane, the API server as the single source of truth, the reconciliation loop that puts pods back when they die. You did all of it on a `kind` cluster that ran on your laptop and cost zero dollars. The mental model is now yours. This week we move the same mental model to a managed cluster on a cloud provider — and, crucially, we leave the manifests unchanged.

The pivot is operational. A managed cluster — Google's **GKE**, AWS's **EKS**, or Azure's **AKS** — is the same Kubernetes with the same API surface, the same `kubectl`, the same YAML. What the provider sells you is the operations: they run the API server, etcd, the scheduler, the controller manager, the upgrades, the security patches, the backup of etcd. You run the workloads. The split is sharp and it is the right split. Running etcd correctly is a full-time job for someone; outsourcing it to Google or AWS or Microsoft is, for any cluster that matters, the responsible choice.

The trap, on the way to a managed cluster, is to over-couple to a single provider. Once you start pulling proprietary load balancers, proprietary IAM glue, and proprietary observability into your manifests, your cluster is no longer *Kubernetes*; it is *Kubernetes-as-deployed-on-vendor-X*, and the day you want to move (or just to verify locally) you will discover that your YAML is full of `cloud.google.com/...` annotations that do not mean anything anywhere else. We will avoid that trap deliberately. The pattern we teach is: **open-source add-ons first, vendor glue only when you cannot do without**. NGINX Ingress, cert-manager, external-dns, ArgoCD — these run anywhere a Kubernetes API runs, including on the `kind` cluster from Week 7.

We use **GKE Autopilot** as the cloud example throughout this week because (a) it is the cleanest expression of "managed Kubernetes" on the market — Google operates the nodes too, not just the control plane — and (b) Google's free tier covers one zonal cluster's control plane indefinitely, so the cost panel is honest. We cover **EKS** and **AKS** in sidebars: the commands differ, the concepts do not. The mini-project deploys to a local `kind` cluster with the exact same manifests that would run on GKE Autopilot, so no student is gated behind a credit card.

By Sunday you will have a cluster (or kind-equivalent) running NGINX Ingress, cert-manager (issuing free Let's Encrypt certificates), external-dns (if you own a domain), and ArgoCD (syncing manifests from a Git repo), and you will understand why those four add-ons are present in almost every real-world Kubernetes deployment you will ever see.

---

## Learning objectives

By the end of this week, you will be able to:

- **Decide** whether to use a managed Kubernetes service (GKE / EKS / AKS / DOKS / Linode LKE) or to self-manage, and articulate the trade-off in four dimensions: operational burden, cost, control over the control plane, and lock-in.
- **Distinguish** GKE Autopilot from GKE Standard, name the three things Autopilot removes (node provisioning, node maintenance, node sizing) and the two things it constrains (no `hostPath` volumes, no privileged pods by default), and explain when Standard is the right pick.
- **Compose** the `gcloud container clusters create-auto` command and the equivalent `eksctl create cluster --fargate` and `az aks create` commands, and explain what each flag does at the cluster level.
- **Explain** node pools as the unit of node-template configuration on GKE Standard, EKS managed node groups, and AKS node pools; explain why Autopilot hides them entirely.
- **Reason** about the cluster autoscaler: what it watches (pending pods), what it does (provisions nodes), what it cannot do (resize an already-running pod), and where it differs from the horizontal pod autoscaler.
- **Configure** Workload Identity (GCP), IRSA (AWS), and Workload Identity (Azure, AAD-based) — the three vendor-specific ways a pod's KSA gets a cloud IAM identity without a long-lived secret on disk — and explain why this pattern is the cluster-security baseline in 2026.
- **Install** the canonical add-on stack from open-source: NGINX Ingress Controller, cert-manager (with the Let's Encrypt ClusterIssuer), external-dns (optional), and metrics-server. On a managed cluster you may swap NGINX for the GKE-bundled Gateway, but the API objects (`Ingress`, `Certificate`, `Issuer`) stay portable.
- **Deploy** ArgoCD to a cluster, point it at a Git repo, watch it reconcile a Helm chart, and explain why this is the production default in 2026 for declarative continuous delivery.
- **Defend** the choice of free, open-source add-ons over vendor-managed equivalents on portability and cost grounds, and name the exceptions where vendor-managed is the right pick (managed databases, managed DNS, managed certificate-of-record for compliance).
- **Operate** a kind cluster as a stand-in for a managed cluster: NGINX Ingress on the host port, cert-manager with a self-signed `ClusterIssuer` for offline TLS, ArgoCD syncing from a local Git remote. Everything you do on a $300/month GKE cluster, you can also do on your laptop with no credit card.

---

## Prerequisites

This week assumes you have completed **Weeks 1-7 of C15**. Specifically:

- You finished Week 7's mini-project — the three-tier app on a `kind` cluster — and you can recreate that cluster from memory in five minutes.
- You have `kind` (0.24+), `kubectl` (1.31+), `docker` running. Verify:

```bash
kind version
kubectl version --client
docker info | head -1
```

- You have an account on at least one cloud provider with a free trial credit. The defaults in this week's exercises assume **GCP** (its $300 free trial covers a small Autopilot cluster for weeks). If you prefer AWS or Azure, the sidebars give the equivalents. If you cannot or do not want to use a credit card, the **kind-equivalent path** in every exercise is supported — you can complete the entire week locally.
- You have `helm` (3.14+) installed (`brew install helm`). Cert-manager, NGINX Ingress, external-dns, and ArgoCD all publish Helm charts; we use them.
- You have ArgoCD CLI installed (`brew install argocd`) or will install it during Exercise 3.
- You can read YAML, you have a public Git repo (GitHub, GitLab, Codeberg), and you understand what `kubectl apply -f` does to a cluster. Week 7 covered all three.
- You have ~8 GB of free RAM if you are running the cloud-free path entirely on `kind`. The add-on stack (ArgoCD + NGINX + cert-manager + the mini-project app) brings the cluster to about 5-6 GB at idle.

We use **Kubernetes 1.31+** (the version GKE Autopilot defaults to in May 2026, and the version `kind` 0.24+ installs by default). API versions used this week: `apps/v1` (Deployment, StatefulSet), `networking.k8s.io/v1` (Ingress, NetworkPolicy), `cert-manager.io/v1` (Certificate, Issuer, ClusterIssuer), `argoproj.io/v1alpha1` (Application, AppProject). All current; no deprecated APIs in this week's material.

If you are coming back to this material after a break, the two relevant 2026 changes are: (a) the **Gateway API** (`gateway.networking.k8s.io/v1`) reached GA in 1.29 and is the project's strategic replacement for Ingress; we cover both and we use Ingress for portability; (b) **GKE Autopilot's Compute Classes** went GA in 2025, replacing the older per-pod resource-class annotations.

---

## Topics covered

- The managed-vs-self-managed decision. The four dimensions: operational burden (running etcd correctly is hard), cost (managed control planes are typically $73/month per cluster on GKE Standard, free on GKE Autopilot for one zonal cluster, $73/month on EKS, $0 on AKS basic), control (can you upgrade on your schedule, can you tune kubelet flags), and lock-in (the cloud-provider-specific annotations you accumulate).
- GKE Autopilot in depth. The model: you submit pods, Google provisions nodes sized to fit, you pay per pod-vCPU-second. The constraints: no `hostPath`, no privileged pods by default (you can grant exceptions via AllowlistedV2), no `nodeSelector`-of-your-own (Google manages node selection), no DaemonSets that need privileged access. The economics: a tiny app on Autopilot costs less than the same app on Standard because Google bin-packs aggressively.
- GKE Standard, EKS, AKS — the side-by-side. Cluster creation commands, IAM models, default networking (VPC-native vs route-based), default ingress story (GCE LB vs ALB vs Azure LB), upgrade behavior. The table at the end of Lecture 1 is the cheat sheet.
- Node pools and managed node groups. The unit of node configuration. Sizing, taints, labels, GPU nodes, spot/preemptible nodes, the relationship to the cluster autoscaler. Why Autopilot abstracts them away and why some teams need them anyway.
- The cluster autoscaler vs the horizontal pod autoscaler vs the vertical pod autoscaler. Three different controllers, three different inputs, three different actions. The order of operations when both HPA and cluster autoscaler are active: HPA wants more pods, pods cannot fit, cluster autoscaler adds a node, pods schedule. The pitfalls: too-fast scaling, too-slow scaling, the cost of cold nodes.
- Workload Identity (GCP). The IAM-to-KSA binding: a Kubernetes ServiceAccount is annotated with a GCP service account email, the pod uses the KSA, the GKE metadata server forges a token for the GCP SA when the pod calls Google APIs. No long-lived JSON key on disk. Equivalents on AWS (IRSA — IAM Roles for ServiceAccounts) and Azure (Workload Identity Federation).
- The canonical add-on stack. NGINX Ingress Controller (the open-source ingress, more flexible than vendor-bundled LB controllers). Cert-manager (the de facto certificate operator, issues Let's Encrypt certs for free). External-dns (syncs `Service` and `Ingress` hostnames to your DNS provider). Metrics-server (the dependency for `kubectl top` and the HPA).
- The Ingress vs Gateway debate. Ingress (the original, stable since 1.19, baroque, well-supported) vs Gateway API (the strategic replacement, GA in 1.29, cleaner separation of concerns, narrower adoption in 2026). We use Ingress for portability; we cover Gateway so you can read it when you encounter it.
- ArgoCD revisited. Last week's Argo CD was a black box pointing at a black box; this week the cluster is open and the deploy target is real. The `Application` resource, the `AppProject`, the auto-sync mode, the diff drift detection, the sync waves and hooks. Why teams pick ArgoCD over Flux (and vice versa) and why both are correct.
- The kind-equivalent path for every exercise. NGINX Ingress on `kind` with `extraPortMappings`. Cert-manager with a self-signed `ClusterIssuer` (for offline TLS — Let's Encrypt cannot reach a kind cluster behind your laptop's NAT). ArgoCD pointed at a local Git remote or a public GitHub repo. The full add-on stack runs on `kind` with one `kind create cluster --config` and a few `helm install` commands.

---

## Weekly schedule

The schedule below adds up to approximately **35 hours**. Total is what matters; reshuffle within the week as your life demands.

| Day       | Focus                                                       | Lectures | Exercises | Challenges | Quiz/Read | Homework | Mini-Project | Self-Study | Daily Total |
|-----------|-------------------------------------------------------------|---------:|----------:|-----------:|----------:|---------:|-------------:|-----------:|------------:|
| Monday    | Managed vs self-managed (Lecture 1)                         |    2h    |    1h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     5h      |
| Tuesday   | GKE Autopilot, node pools, Workload Identity (Lecture 2)    |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Wednesday | The add-on stack (Lecture 3)                                |    2h    |    2h     |     1h     |    0.5h   |   1h     |     0h       |    0.5h    |     7h      |
| Thursday  | Hands-on: ingress + cert-manager + ArgoCD on kind           |    1h    |    2h     |     1h     |    0.5h   |   1h     |     1h       |    0.5h    |     7h      |
| Friday    | Mini-project — full stack on kind, manifests cloud-portable |    0h    |    0h     |     0h     |    0.5h   |   1h     |     3h       |    0.5h    |     5h      |
| Saturday  | Mini-project finish; vendor sidebar (EKS / AKS dry-run)     |    0h    |    0h     |     1h     |    0h     |   0h     |     2h       |    0h      |     3h      |
| Sunday    | Quiz, recap, tear down clusters                             |    0h    |    0h     |     0h     |    0.5h   |   0h     |     1h       |    0h      |     1.5h    |
| **Total** |                                                             | **7h**   | **7h**    | **3h**     | **3h**    | **5h**   | **7h**       | **2.5h**   | **34.5h**   |

---

## How to navigate this week

| File | What is inside |
|------|----------------|
| [README.md](./00-overview.md) | This overview (you are here) |
| [resources.md](./01-resources.md) | Curated readings: GKE docs, EKS docs, AKS docs, cert-manager, ArgoCD, kind |
| [lecture-notes/01-managed-vs-self-managed-and-the-three-clouds.md](./02-lecture-notes/01-managed-vs-self-managed-and-the-three-clouds.md) | When managed wins; GKE / EKS / AKS side-by-side; the trade-offs |
| [lecture-notes/02-gke-autopilot-node-pools-and-workload-identity.md](./02-lecture-notes/02-gke-autopilot-node-pools-and-workload-identity.md) | Autopilot vs Standard, node pools, the cluster autoscaler, Workload Identity / IRSA |
| [lecture-notes/03-the-add-on-stack-ingress-certs-dns-argocd.md](./02-lecture-notes/03-the-add-on-stack-ingress-certs-dns-argocd.md) | NGINX Ingress, cert-manager, external-dns, metrics-server, ArgoCD |
| [exercises/exercise-01-stand-up-kind-with-ingress.md](./03-exercises/exercise-01-stand-up-kind-with-ingress.md) | Local cluster with NGINX Ingress exposed on host ports |
| [exercises/exercise-02-install-cert-manager-and-issue-a-cert.md](./03-exercises/exercise-02-install-cert-manager-and-issue-a-cert.md) | Cert-manager with a self-signed `ClusterIssuer` and a real `Certificate` |
| [exercises/exercise-03-bootstrap-argocd.md](./03-exercises/exercise-03-bootstrap-argocd.md) | ArgoCD installed, pointed at a Git repo, syncing a sample app |
| [exercises/exercise-04-gke-autopilot-dry-run.yaml](./03-exercises/exercise-04-gke-autopilot-dry-run.yaml) | The `gcloud` command file plus the manifests you would apply on GKE |
| [exercises/SOLUTIONS.md](./03-exercises/SOLUTIONS.md) | Worked solutions, expected output, the diagnostic questions to ask |
| [challenges/challenge-01-port-from-kind-to-autopilot.md](./04-challenges/challenge-01-port-from-kind-to-autopilot.md) | Take the Exercise 3 manifests and port them to GKE Autopilot in your head |
| [challenges/challenge-02-debug-a-stuck-argocd-sync.md](./04-challenges/challenge-02-debug-a-stuck-argocd-sync.md) | Five broken ArgoCD `Application`s; find and fix each |
| [quiz.md](./05-quiz.md) | 10 multiple-choice questions |
| [homework.md](./06-homework.md) | Six practice problems |
| [mini-project/README.md](./07-mini-project/00-overview.md) | Deploy a small app with NGINX Ingress + cert-manager + ArgoCD to kind; same manifests target GKE Autopilot |

---

## A note on cost

Week 8 is structured so that **no student needs a credit card to complete it**. Every exercise and the mini-project run on `kind` with the same manifests that target GKE Autopilot. The cloud-side material is taught via dry-runs: the `gcloud` commands are documented and explained, the manifests are the same ones you apply locally.

```
+-----------------------------------------------------+
|  COST PANEL - Week 8 incremental spend              |
|                                                     |
|  kind cluster (local, in Docker)         $0.00      |
|  NGINX Ingress, cert-manager, ArgoCD     $0.00      |
|    (all open-source, Helm-installed)                |
|  Let's Encrypt staging certs             $0.00      |
|  GitHub free public repo for GitOps      $0.00      |
|                                                     |
|  Optional path - GKE Autopilot                      |
|    One zonal Autopilot cluster                      |
|      control plane:                      $0.00      |
|      (free tier covers 1 zonal cluster)             |
|    Pod-vCPU-seconds for mini-project     ~$3-5/wk   |
|    NAT egress for Let's Encrypt          ~$0.10/wk  |
|                                                     |
|  Optional path - EKS                                |
|    Control plane                         ~$73/mo    |
|    EC2 t3.small node (1):                ~$15/mo    |
|    Load balancer (NLB):                  ~$16/mo    |
|                                                     |
|  Optional path - AKS                                |
|    Control plane (free tier)             $0.00      |
|    B2s node (1):                         ~$30/mo    |
|    Standard LB:                          ~$18/mo    |
|                                                     |
|  Required subtotal (kind path):          $0.00      |
+-----------------------------------------------------+
```

If you choose the GKE Autopilot path, **tear the cluster down on Sunday**. `gcloud container clusters delete <name> --region <region>` returns the credits. If you forget, a single Autopilot pod running 24/7 costs around $15-20/month; not ruinous, but not free.

The Week 8 design rule is that the *concepts* are taught on the *real* commands (`gcloud container clusters create-auto`, `eksctl create cluster`, `az aks create`), but the *practice* runs locally so the cost is bounded to your laptop's electricity bill.

---

## Stretch goals

If you finish early and want to push further:

- Run the mini-project on **both** kind and GKE Autopilot with the *exact* same Git repo as the source of truth. ArgoCD-sync the same manifests to two clusters; observe that the only difference is `Service` becomes a `LoadBalancer` (provider-issued external IP) on GKE versus a `ClusterIP` reached via Ingress on kind. The portability claim of this week is concrete; verify it.
- Read the **cert-manager source** at <https://github.com/cert-manager/cert-manager/tree/master/pkg/controller/certificates>. The reconciliation loop for a `Certificate` resource — request, await, store, renew — is about 800 lines of Go. Reading it once is the difference between treating cert-manager as magic and treating it as a finite state machine.
- Install **`gke-cloud-auth-plugin`** locally and point `kubectl` at a real Autopilot cluster (you do not need to deploy anything). The auth flow — `gcloud auth login`, the plugin exchanges your OAuth token for a Kubernetes API token — is worth tracing in `kubectl --v=8` mode.
- Read the **Gateway API specification** at <https://gateway-api.sigs.k8s.io/> and rewrite the Exercise 3 `Ingress` as a `Gateway` + `HTTPRoute`. The Ingress field-by-field maps to about 80% of the Gateway shape; the remaining 20% is where Gateway expresses things Ingress could not (cross-namespace routing, header-based routing without controller-specific annotations, multi-listener gateways).
- Install **`kube-prometheus-stack`** (the community Helm chart that bundles Prometheus + Grafana + Alertmanager). It is the canonical observability stack and it is the chart you will most often see referenced in production conversations. Week 12 will install it deliberately; doing it now as exploration is fine.
- Re-do the Workload Identity exercise using **IRSA** on EKS (free trial credit needed) and compare the binding shape. Three providers, three mechanisms, one pattern.

---

## Up next

Continue to **Week 9 — Helm and Operators** once you have shipped your Week 8 mini-project. Week 9 introduces Helm (the templating-and-packaging layer that every chart you installed this week is built on) and the operator pattern (custom resources + custom controllers, the way every cluster-native database from Postgres-operator to Crunchy Postgres extends the Kubernetes API). Week 10 takes us into observability — Prometheus, Grafana, OpenTelemetry — and Week 11 into cluster-level security and policy.

A note on the order: we did `kind` (Week 7) before managed (Week 8) before Helm (Week 9) deliberately. The mental model fixes first, the operational reality second, the templating layer third. Many engineers learn in the opposite order — Helm chart first, managed cluster as the only cluster they ever touch, the underlying model never inspected — and spend two years debugging surprises that would not have been surprises had the model been built first. By doing kind first, managed second, and Helm third, you can read any Kubernetes deployment in the world and trace it down to the four-property object model from Week 7.

---

*If you find errors in this material, please open an issue or send a PR. Future learners will thank you.*
