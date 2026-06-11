# Week 8 — Resources

Every resource on this page is **free** and **publicly accessible**. If a link 404s, please open an issue.

## Required reading (work it into your week)

- **GKE — "GKE overview"** — Google's own introduction to its managed Kubernetes service. Twelve minutes; the place to start before Monday: <https://cloud.google.com/kubernetes-engine/docs/concepts/kubernetes-engine-overview>.
- **GKE — "Autopilot overview"** — the model, the constraints, the billing. Read before Tuesday's lecture: <https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview>.
- **GKE — "Choose an Autopilot or Standard cluster"** — the decision tree from Google itself. Useful for the managed-vs-self-managed discussion: <https://cloud.google.com/kubernetes-engine/docs/concepts/choose-cluster-mode>.
- **EKS — "What is Amazon EKS?"** — the AWS counterpart, terminology and pricing: <https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html>.
- **AKS — "Azure Kubernetes Service overview"** — the Azure counterpart: <https://learn.microsoft.com/en-us/azure/aks/intro-kubernetes>.
- **cert-manager — "Getting Started"** — the canonical install plus a Let's Encrypt walkthrough. Do it before Wednesday: <https://cert-manager.io/docs/installation/>.
- **NGINX Ingress Controller — "Installation Guide"** — the open-source ingress, install on any cluster including kind: <https://kubernetes.github.io/ingress-nginx/deploy/>.
- **ArgoCD — "Getting Started"** — install, log in, sync a sample app. The 30-minute path: <https://argo-cd.readthedocs.io/en/stable/getting_started/>.
- **kind — "Ingress"** — the recipe for exposing an NGINX Ingress on a kind cluster via `extraPortMappings`. The recipe Exercise 1 uses: <https://kind.sigs.k8s.io/docs/user/ingress/>.

## The specs and reference docs (skim, do not memorize)

- **Kubernetes Ingress (`networking.k8s.io/v1`)** — the resource spec, the path matching rules, the `tls` block: <https://kubernetes.io/docs/concepts/services-networking/ingress/>.
- **Kubernetes Gateway API (`gateway.networking.k8s.io/v1`)** — the strategic replacement for Ingress, GA in 1.29: <https://gateway-api.sigs.k8s.io/>.
- **cert-manager — `Certificate` resource reference** — every field on the resource you use most: <https://cert-manager.io/docs/usage/certificate/>.
- **cert-manager — `Issuer` and `ClusterIssuer`** — namespaced vs cluster-scoped issuance, the ACME and self-signed flavors: <https://cert-manager.io/docs/configuration/>.
- **ArgoCD — `Application` CRD reference** — the resource you write most often when using ArgoCD: <https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/#applications>.
- **ArgoCD — `AppProject` CRD reference** — multi-tenant ArgoCD, RBAC for project-scoped sync: <https://argo-cd.readthedocs.io/en/stable/operator-manual/project-specification/>.
- **external-dns — provider list** — which DNS providers are supported and how to configure each: <https://github.com/kubernetes-sigs/external-dns/tree/master/docs/tutorials>.
- **metrics-server — install and verify** — the dependency for `kubectl top` and the HPA: <https://github.com/kubernetes-sigs/metrics-server>.

## Cloud provider references

- **`gcloud container clusters create-auto`** — every flag on the GKE Autopilot create command: <https://cloud.google.com/sdk/gcloud/reference/container/clusters/create-auto>.
- **`gcloud container clusters create`** — the GKE Standard create command (different defaults, more flags): <https://cloud.google.com/sdk/gcloud/reference/container/clusters/create>.
- **`eksctl create cluster`** — the unofficial-but-de-facto tool for creating EKS clusters: <https://eksctl.io/usage/creating-and-managing-clusters/>.
- **`az aks create`** — the AKS create command: <https://learn.microsoft.com/en-us/cli/azure/aks#az-aks-create>.
- **GKE pricing** — the only reliable answer on what your cluster will cost. Note the free tier covers one zonal cluster's control plane: <https://cloud.google.com/kubernetes-engine/pricing>.
- **EKS pricing** — control plane is a flat $73/month per cluster as of May 2026: <https://aws.amazon.com/eks/pricing/>.
- **AKS pricing** — control plane is free on the standard tier: <https://azure.microsoft.com/en-us/pricing/details/kubernetes-service/>.

## Workload Identity / IRSA / AAD Workload Identity

- **GKE — "Workload Identity overview"** — the canonical reference for the GCP IAM-to-KSA binding: <https://cloud.google.com/kubernetes-engine/docs/concepts/workload-identity>.
- **GKE — "Use Workload Identity"** — the step-by-step recipe: <https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity>.
- **EKS — "IAM Roles for Service Accounts (IRSA)"** — the AWS equivalent. Same idea, different mechanism (OIDC trust to a role): <https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html>.
- **AKS — "Workload Identity overview"** — the AAD-based equivalent: <https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview>.
- **`kubernetes-sigs/azure-workload-identity`** — the upstream project AKS Workload Identity is built on: <https://github.com/Azure/azure-workload-identity>.

## Helm (since every add-on this week is a Helm chart)

- **Helm — "Quickstart"** — install, search, install a chart. Twenty minutes: <https://helm.sh/docs/intro/quickstart/>.
- **Helm — "Using Helm"** — `helm install`, `helm upgrade`, `helm rollback`, the values file: <https://helm.sh/docs/intro/using_helm/>.
- **Artifact Hub** — the index of Helm charts. Search "nginx-ingress" / "cert-manager" / "argo-cd" / "external-dns" here: <https://artifacthub.io/>.
- **`ingress-nginx` Helm chart** — the chart we install in Exercise 1: <https://github.com/kubernetes/ingress-nginx/tree/main/charts/ingress-nginx>.
- **`cert-manager` Helm chart** — the chart we install in Exercise 2: <https://github.com/cert-manager/cert-manager/tree/master/deploy/charts/cert-manager>.
- **`argo-cd` Helm chart** — the chart we install in Exercise 3: <https://github.com/argoproj/argo-helm/tree/main/charts/argo-cd>.
- **`external-dns` Helm chart** — covered in homework: <https://github.com/kubernetes-sigs/external-dns/tree/master/charts/external-dns>.

## Free books and long-form writing

- **"Kubernetes Up & Running" (Burns, Beda, Hightower, Strebel) — chapters on managed clusters and add-ons** — free chapters on the publisher site; the chapter on Workload Identity is the cleanest write-up of the pattern in print: <https://www.oreilly.com/library/view/kubernetes-up-and/9781098110192/>.
- **"Production Kubernetes" (Strebel, Vest, White)** — covers the operational chapters this week introduces. Free preview on O'Reilly Online Learning trial: <https://www.oreilly.com/library/view/production-kubernetes/9781492092292/>.
- **CNCF — "Cloud Native Glossary" entries for "Ingress", "Operator", "GitOps"** — the project-neutral definitions: <https://glossary.cncf.io/>.
- **Google Cloud — "Best practices for running cost-optimized Kubernetes applications on GKE"** — Google's own write-up. The section on Autopilot bin-packing is the clearest explanation of the cost model: <https://cloud.google.com/architecture/best-practices-for-running-cost-optimized-kubernetes-applications-on-gke>.
- **"GitOps Principles" (OpenGitOps working group)** — the four principles, the formal definition. Worth reading once: <https://opengitops.dev/>.

## Talks and videos (free, no signup)

- **"GKE Autopilot — A Deeper Look" — Google Cloud Next** (~30 min) — the engineering team explaining the model, the constraints, and the bin-packing economics: <https://www.youtube.com/results?search_query=gke+autopilot+deeper+look>.
- **"Demystifying GKE Networking" — Tim Hockin (Google)** (~40 min) — one of the K8s networking maintainers walking through GKE's specific networking choices. The section on VPC-native vs route-based is the segment that pays for itself: <https://www.youtube.com/results?search_query=tim+hockin+gke+networking>.
- **"ArgoCD: GitOps for Kubernetes" — Alexander Matyushentsev (Intuit)** (~30 min) — the original ArgoCD maintainer presenting at KubeCon. The 8 minutes on sync waves is the segment to rewatch: <https://www.youtube.com/results?search_query=argocd+kubecon+sync+waves>.
- **"cert-manager Deep Dive" — Maartje Eyskens (Jetstack)** (~30 min) — the cert-manager maintainer team walking through the reconciliation loop for a `Certificate` resource: <https://www.youtube.com/results?search_query=cert-manager+deep+dive+kubecon>.
- **"Workload Identity on GKE — How It Works" — Google Cloud Tech** (~25 min) — the metadata-server-as-token-broker pattern. Watch after Lecture 2 Section 4: <https://www.youtube.com/results?search_query=workload+identity+gke+how+it+works>.
- **"IRSA from First Principles" — AWS re:Invent** (~30 min) — the AWS analog, more emphasis on the OIDC trust relationship: <https://www.youtube.com/results?search_query=irsa+aws+re%3Ainvent>.
- **"Kubernetes Gateway API: A New Frontier" — CNCF** (~30 min) — the project's positioning of Gateway API vs Ingress, with the migration path: <https://www.youtube.com/results?search_query=gateway+api+kubernetes+new+frontier>.

## Open-source manifests worth reading

You will learn more from one hour reading other people's add-on installations than from three hours of tutorials. Pick one and read it.

- **`kubernetes/ingress-nginx` deploy manifests** — the project's own static manifests, what `helm install` produces: <https://github.com/kubernetes/ingress-nginx/tree/main/deploy/static>.
- **`cert-manager/cert-manager` install bundle** — the all-in-one install manifest: <https://github.com/cert-manager/cert-manager/releases>.
- **`argoproj/argo-cd` install manifests** — the project's own static manifests: <https://github.com/argoproj/argo-cd/blob/master/manifests/install.yaml>.
- **`kubernetes-sigs/external-dns` example configs** — provider-specific examples: <https://github.com/kubernetes-sigs/external-dns/tree/master/docs/tutorials>.
- **`kubernetes-sigs/metrics-server` install manifest** — the components.yaml that 99% of operators apply: <https://github.com/kubernetes-sigs/metrics-server/releases>.

## kind-specific recipes

- **kind — "Ingress"** — the recipe Exercise 1 uses: <https://kind.sigs.k8s.io/docs/user/ingress/>.
- **kind — "Local Registry"** — the recipe for a local Docker registry that kind can pull from. Useful when you do not want to push to GHCR for every iteration: <https://kind.sigs.k8s.io/docs/user/local-registry/>.
- **kind — "LoadBalancer (MetalLB)"** — if you need a real `Service` type `LoadBalancer` on kind, MetalLB is the answer. Optional this week, useful eventually: <https://kind.sigs.k8s.io/docs/user/loadbalancer/>.
- **kind — "Configuration"** — every field on the kind `Cluster` config. The `extraPortMappings` and `extraMounts` fields are the ones we use this week: <https://kind.sigs.k8s.io/docs/user/configuration/>.

## Tools you will install this week

| Tool | Install | Purpose |
|------|---------|---------|
| `kind` | `brew install kind` | Local Kubernetes cluster (same as Week 7) |
| `kubectl` | `brew install kubectl` | The Kubernetes CLI (same as Week 7) |
| `helm` | `brew install helm` | Helm 3 client; installs charts for every add-on this week |
| `argocd` | `brew install argocd` | ArgoCD CLI; alternative to the web UI for Exercise 3 |
| `gcloud` (optional) | <https://cloud.google.com/sdk/docs/install> | Only if you want to provision a real GKE cluster |
| `eksctl` (optional) | `brew install eksctl` | Only if you want to provision a real EKS cluster |
| `az` (optional) | `brew install azure-cli` | Only if you want to provision a real AKS cluster |
| `jq` | `brew install jq` | JSON parser (same as Week 7) |
| `yq` | `brew install yq` | YAML parser (same as Week 7) |

## Glossary cheat sheet

Keep this open in a tab.

| Term | Plain English |
|------|---------------|
| **Managed Kubernetes** | A cluster where the cloud provider runs the control plane (API server, etcd, scheduler, controllers) and you run only the workloads. |
| **GKE** | Google Kubernetes Engine. Google's managed Kubernetes service. |
| **EKS** | Elastic Kubernetes Service. AWS's managed Kubernetes service. |
| **AKS** | Azure Kubernetes Service. Microsoft's managed Kubernetes service. |
| **GKE Autopilot** | The GKE mode where Google also runs the nodes. You submit pods; Google provisions, sizes, and bills per-pod. |
| **GKE Standard** | The GKE mode where you manage node pools. More control, more responsibility. |
| **Node pool** | A group of nodes with the same machine type, image, and config. The unit of node-template configuration on GKE Standard, EKS, AKS. |
| **Cluster autoscaler** | The controller that adds and removes nodes based on pending-pod pressure. Operates at the node-pool layer. |
| **Horizontal Pod Autoscaler (HPA)** | The controller that adds and removes pods within a Deployment based on CPU, memory, or custom metrics. |
| **Vertical Pod Autoscaler (VPA)** | The controller that resizes pods (their resource requests and limits) based on observed usage. Less common; requires restart. |
| **Workload Identity** | The GCP pattern for binding a Kubernetes ServiceAccount to a GCP IAM service account, so pods authenticate to Google APIs without a JSON key. |
| **IRSA** | IAM Roles for ServiceAccounts. The AWS equivalent of Workload Identity. |
| **Ingress** | The Kubernetes resource that routes external HTTP/HTTPS traffic to Services. Stable since 1.19. |
| **Ingress Controller** | The data-plane component (a pod, usually) that watches Ingress resources and configures itself accordingly. NGINX Ingress Controller is the canonical open-source one. |
| **Gateway API** | The strategic replacement for Ingress, GA in 1.29. Cleaner separation between platform and developer concerns. |
| **cert-manager** | The Kubernetes-native certificate operator. Watches `Certificate` resources, requests from an `Issuer` (Let's Encrypt, Vault, self-signed), stores the result as a Secret, renews automatically. |
| **`ClusterIssuer`** | A cert-manager `Issuer` that works across all namespaces. The most common shape for a single Let's Encrypt account per cluster. |
| **external-dns** | The Kubernetes controller that syncs `Service` and `Ingress` hostnames to your DNS provider (Cloudflare, Route 53, Google Cloud DNS). |
| **metrics-server** | The cluster-wide metrics aggregator. Required for `kubectl top` and the HPA. Not the same as Prometheus. |
| **ArgoCD** | The CNCF-graduated GitOps controller. Watches a Git repo, syncs manifests to the cluster, surfaces drift. The `Application` CRD is its core resource. |
| **GitOps** | The pattern: Git is the source of truth, a controller in the cluster reconciles the cluster toward Git, all changes go through pull request. |
| **Sync wave** | An ArgoCD ordering primitive. Resources annotated with `argocd.argoproj.io/sync-wave: "N"` apply in order, low N first. |
| **Helm** | The package manager for Kubernetes. A "chart" is a templated YAML bundle. We use it to install every add-on this week. |
| **`LoadBalancer`** Service | A Service type that asks the cloud provider for an external IP. Works on GKE / EKS / AKS; on kind, you need MetalLB. |
| **`ClusterIP`** Service | The default Service type. Internal-only virtual IP. Combined with Ingress, this is how most external traffic reaches a pod. |
| **`NodePort`** Service | A Service type that exposes a port on every node. Useful in labs; rare in production. |
| **VPC-native cluster** | A GKE cluster where pod IPs come from the VPC's subnets. The 2026 default. Routes are not used; the VPC's routing handles pod traffic. |
| **Pod Disruption Budget (PDB)** | A resource that caps how many pods can be voluntarily disrupted (e.g., during a node drain) at once. Important on managed clusters where nodes get recycled. |
| **`PriorityClass`** | A resource that assigns priorities to pods. The scheduler uses priority to decide what to evict when nodes are full. |

---

*If a link 404s, please [open an issue](https://github.com/CODECRUNCHWORLDWIDE) so we can replace it.*
