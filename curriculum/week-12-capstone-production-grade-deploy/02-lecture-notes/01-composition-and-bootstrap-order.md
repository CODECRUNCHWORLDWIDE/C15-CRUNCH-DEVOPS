# Lecture 1 — The Composition, the Bootstrap Order, the Repository Layout

> *Eleven weeks of Lego blocks. The week that produces an engineer is the week we stop describing each block and start describing the order in which they snap together.*

The eleven weeks of C15 covered, one block at a time, the components of a production-grade deployment. Containers and images. Compose and CI. Terraform and ArgoCD. Manifests, ingress, certificates. Metrics, logs, traces. Vault, cosign, OpenCost. Each was useful on its own; each had its own mini-project. None of them, alone, is what a competent platform engineer ships, because what gets shipped is the composition — the cluster on which all eleven pieces sit together, the application that flows through all of them in sequence, the order in which the install happens, the order in which a failure recovers, the documentation that lets someone else continue the work.

This lecture is the conceptual setup for the capstone. We will cover three things, in order. **First**, the composition itself — what the eleven blocks look like when they are assembled into one running system, and why the assembly looks the way it does. **Second**, the bootstrap order — the specific sequence in which components install, and why getting that sequence wrong is the most common reason a junior platform engineer's first cluster does not come up cleanly. **Third**, the repository layout — the shape of the Git directory that holds the cluster's source of truth, and the principles that make one repository readable and another unreadable by a successor.

By the end of the lecture you should be able to draw the bootstrap-order diagram from memory and explain why each arrow points the way it does. The diagram is not memorization for its own sake; the diagram is what you will explain to a colleague six months from now when they ask "why are we installing things in this order".

---

## 1. The composition

The capstone deliverable, drawn as a system diagram from the outside in, looks like this:

```
                        +-------------------+
                        |   public client   |
                        +---------+---------+
                                  | HTTPS (port 443)
                                  v
                        +-------------------+
                        |  DNS -> Ingress   |   <-- external-dns or /etc/hosts
                        +---------+---------+
                                  | TLS termination here
                                  v
                        +-------------------+
                        |   ingress-nginx   |   <-- cert-manager mints cert
                        +---------+---------+
                                  | HTTP (cluster network)
                                  v
                        +-------------------+
                        |   FastAPI app     |   <-- 2 replicas; HPA; PDB
                        |   /quote /metrics |       reads secret from Vault Agent
                        +-+-------+-------+-+
                          |       |       |
                          v       v       v
              +-----------+ +-----+----+ +-+-------------------+
              | Postgres  | | Vault    | |  OTel Collector     |
              | (PVC)     | | agent    | |  -> Tempo + Loki    |
              +-----------+ +----------+ +---------------------+

                       Cluster-side controllers:
                       - ArgoCD            (reconciles from Git)
                       - cert-manager      (mints certs)
                       - external-dns      (writes DNS records, optional)
                       - kube-prometheus-  (scrapes /metrics)
                         stack             (Prometheus, Grafana, Alertmanager)
                       - Loki + Promtail   (logs)
                       - OTel Collector    (traces)
                       - Kyverno           (verifyImages, labels)
                       - OpenCost          (allocates cost)
```

A description like that fits on one page and is enough for a junior engineer to recognize the system on Tuesday morning. The diagram is intentionally not specific to a cloud — it is the local-mode shape, and the cloud-mode shape differs only in where the persistent storage and the DNS records live.

The composition has three structural properties worth naming explicitly.

**Property 1 — every cross-component edge is an open protocol.** The application talks to Postgres via the wire protocol on port 5432. It talks to Vault via HTTPS via the Vault Agent sidecar. It exports metrics via HTTP `/metrics` (Prometheus exposition format). It emits OpenTelemetry traces via OTLP/gRPC to the Collector. Every one of those is documented in a publicly available specification; every one of those has an open-source implementation; every one of those can be swapped for an alternative implementation without rewriting the application. The discipline is not "use these specific tools" — it is "wire components through documented protocols, so the tools can be replaced when they become inadequate".

**Property 2 — the cluster is reconciled, not imperatively configured.** No human runs `kubectl apply` against this cluster after the first day. Every manifest is in Git; ArgoCD reads the Git repo every few minutes and reconciles the cluster's state toward the Git state. The state of the cluster *is* the state of the Git repo. If the cluster drifts (someone runs `kubectl edit` to test a fix), ArgoCD detects the drift and either reverts it or surfaces it as an out-of-sync condition that a human must address. The discipline is GitOps; the cluster is not authoritative.

**Property 3 — the application's image is a unit, not a snowflake.** The image is signed. The image has an SBOM. The image's vulnerabilities have been scanned. The image's source is reproducible from the commit SHA. The image is admitted to the cluster only after Kyverno verifies the signature. The pipeline that produced the image is itself stored in Git and is itself reproducible. The discipline is supply-chain security; the image is the unit at which the discipline operates.

If any of those three properties is missing, the cluster is incomplete. If the protocols are not open, the cluster is locked into a vendor; if the cluster is not reconciled, the cluster is a snowflake; if the image is not a unit, the supply chain is uninspectable. The capstone asks you to demonstrate all three, end to end, on one working cluster.

---

## 2. The bootstrap order

The cluster installs in a specific order. The order is not arbitrary, and it is not the order the components appear in marketing material. It is the order driven by the dependency graph — which components need which other components running before they can start.

The full order, with explanation:

### Phase 0 — the cluster control plane

`kind create cluster` (local mode) or `terraform apply` against the cloud provider (cloud mode). This produces a Kubernetes API server, a scheduler, a controller manager, and at least one worker node. The control plane is the precondition for everything else.

Reading material: the kind quickstart at <https://kind.sigs.k8s.io/docs/user/quick-start/> for the local path; the Civo or Oracle Cloud free-tier quickstart for the cloud path.

### Phase 1 — the GitOps controller

ArgoCD is installed before anything else. The reason is recursive: after ArgoCD is installed, ArgoCD installs everything else. The two manifests that go into the cluster from the bootstrap script are (a) the ArgoCD install and (b) the App-of-Apps `Application` CRD that points at the `gitops/` directory in the repository. Everything after this is one of two things — either ArgoCD applying a manifest, or a controller that ArgoCD installed reconciling its own resources.

The bootstrap script applies these two manifests with `kubectl apply` (or with the Helm + Terraform providers from W5). This is the only `kubectl apply` a human runs against the cluster. From this point on, the human's interaction with the cluster is a Git push.

Reading material: the ArgoCD *Getting Started* page at <https://argo-cd.readthedocs.io/en/stable/getting_started/> and the *Cluster Bootstrapping* page at <https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/>.

### Phase 2 — the CRDs

Most platform components install Custom Resource Definitions before they install the controllers that consume those CRDs. cert-manager installs `Certificate`, `Issuer`, `ClusterIssuer`. The kube-prometheus-stack installs `ServiceMonitor`, `PodMonitor`, `PrometheusRule`. Kyverno installs `ClusterPolicy`, `Policy`. OpenCost installs nothing CRD-shaped (it reads from Prometheus).

ArgoCD's *sync waves* are the mechanism that orders CRD application before resource application. The CRD chart goes into sync wave 0; the resources that consume the CRD go into sync wave 5 or later. ArgoCD applies wave-0 resources first, waits for them to become healthy, then applies wave-5 resources. The two-phase apply is necessary because a `Certificate` resource cannot be created until the `Certificate` CRD has been registered.

Reading material: <https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/>.

### Phase 3 — the infrastructure controllers

In sync wave 5, ArgoCD installs:

- **ingress-nginx** — the ingress controller that terminates TLS and routes traffic to Services.
- **cert-manager** — the controller that mints certificates from a `ClusterIssuer`. For the local path, the `ClusterIssuer` is self-signed; for the cloud path, it is Let's Encrypt's ACME.
- **external-dns** (cloud path only) — the controller that creates DNS records when Ingress objects are created.

These three are mutually independent — ingress-nginx does not depend on cert-manager and vice versa. They install in parallel.

Reading material: ingress-nginx docs at <https://kubernetes.github.io/ingress-nginx/deploy/> and cert-manager docs at <https://cert-manager.io/docs/installation/helm/>.

### Phase 4 — the observability stack

In sync wave 10, the kube-prometheus-stack installs Prometheus, Grafana, Alertmanager, kube-state-metrics, node-exporter, and the Prometheus Operator that manages them. After it is healthy, Loki and Promtail install (sync wave 12), then the OpenTelemetry Collector (sync wave 14).

Why this order. Loki and the OTel Collector each expose a `/metrics` endpoint that Prometheus scrapes; if you install them before Prometheus, the metrics are simply not collected for the first few minutes. That is not a failure mode that blocks anything, but it is asymmetric debugging — you find yourself wondering why Grafana has no data for the first ten minutes, then it appears, and the cause is install-order. Avoid it by installing Prometheus first.

Reading material: the kube-prometheus-stack values at <https://github.com/prometheus-community/helm-charts/blob/main/charts/kube-prometheus-stack/values.yaml>.

### Phase 5 — the security stack

In sync wave 15, Vault installs. In sync wave 16, Kyverno installs. In sync wave 17, the Kyverno `ClusterPolicy` for `verifyImages` and the Kyverno `ClusterPolicy` for required cost-labels install.

The order matters here in a stricter sense than for observability: the Kyverno policies refuse to admit pods that fail their rules. If the policies install before the application's own pods, the application's pods must already satisfy the policies, which means the application must already be signed and labeled correctly. This is intentional — the policies should be on before the workload arrives.

Reading material: Vault Helm at <https://developer.hashicorp.com/vault/docs/platform/k8s/helm> and Kyverno install at <https://kyverno.io/docs/installation/methods/>.

### Phase 6 — the cost stack

OpenCost installs in sync wave 20, after Prometheus is healthy (because OpenCost reads from Prometheus). The Grafana dashboard for cost installs alongside; it depends on Grafana being up.

Reading material: OpenCost Helm at <https://github.com/opencost/opencost-helm-chart>.

### Phase 7 — the application

In sync wave 30, the application installs. The Postgres StatefulSet, the FastAPI Deployment, the Service, the Ingress, the ServiceMonitor, the PodDisruptionBudget, the HorizontalPodAutoscaler. The Ingress's `tls` block references a `Certificate` resource; cert-manager (already running) sees it and mints the certificate; ingress-nginx (already running) sees the Ingress and starts routing; Prometheus (already running) sees the ServiceMonitor and starts scraping; Kyverno (already running) verifies the image signature on admission.

This is the moment the composition becomes visible. Every controller that was installed in phases 1-6 reacts to the application's manifests. No controller had to be installed in response to the application; the controllers were already there, waiting for resources to reconcile.

### Phase 8 — the smoke test

The bootstrap script makes a request to the application's public URL and confirms a 200 response. The response body contains a quote string. The cluster is up.

A complete bootstrap, on a developer machine with the prerequisites installed and a warm Docker layer cache, takes 15 to 20 minutes the first time and 10 to 12 minutes on subsequent rebuilds. That number is the *operational* number — it is how long disaster recovery takes when the cluster is gone and the repo is the only source of truth.

---

## 3. The repository layout

The repository that holds the capstone is structured as follows:

```
capstone/
├── README.md                       <-- the entry point
├── RUNBOOK.md                      <-- written in Lecture 3
├── Makefile                        <-- bootstrap / app-deploy / smoke / dr-rehearsal
├── .github/
│   └── workflows/
│       └── release.yaml            <-- the CI pipeline
├── app/                            <-- application source
│   ├── Dockerfile
│   ├── compose.yaml                <-- W3 local dev
│   ├── pyproject.toml
│   ├── src/
│   │   └── crunch_quotes/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       └── db.py
│   ├── tests/
│   │   └── test_main.py
│   └── frontend/
│       └── index.html
├── terraform/                      <-- W5 infra-as-code
│   ├── main.tf
│   ├── kind.tf                     <-- local profile
│   ├── civo.tf                     <-- cloud profile (commented out by default)
│   ├── argocd.tf                   <-- installs ArgoCD via Helm provider
│   └── outputs.tf
├── gitops/                         <-- W6 the source of cluster truth
│   ├── app-of-apps.yaml            <-- the root Application
│   └── apps/
│       ├── platform/
│       │   ├── ingress-nginx.yaml
│       │   ├── cert-manager.yaml
│       │   ├── kube-prometheus-stack.yaml
│       │   ├── loki.yaml
│       │   ├── otel-collector.yaml
│       │   ├── vault.yaml
│       │   ├── kyverno.yaml
│       │   └── opencost.yaml
│       ├── policies/
│       │   ├── verify-images.yaml  <-- Kyverno verifyImages
│       │   └── require-cost-labels.yaml
│       └── app/
│           ├── crunch-quotes.yaml  <-- the application Application
│           └── overlays/
│               ├── kind/
│               └── civo/
├── kustomize/                      <-- W7 manifests, by overlay
│   └── crunch-quotes/
│       ├── base/
│       │   ├── deployment.yaml
│       │   ├── service.yaml
│       │   ├── ingress.yaml
│       │   ├── hpa.yaml
│       │   ├── pdb.yaml
│       │   ├── servicemonitor.yaml
│       │   ├── configmap.yaml
│       │   ├── postgres.yaml
│       │   └── kustomization.yaml
│       └── overlays/
│           ├── kind/
│           │   └── kustomization.yaml
│           └── civo/
│               └── kustomization.yaml
├── observability/                  <-- W9 dashboards and rules
│   ├── grafana-dashboards/
│   │   ├── crunch-quotes-rps.json
│   │   ├── crunch-quotes-latency.json
│   │   └── crunch-quotes-cost.json
│   └── prometheus-rules/
│       └── crunch-quotes-slo.yaml
├── secrets/                        <-- W10 secrets material
│   ├── .sops.yaml
│   ├── vault-policy.hcl
│   └── postgres-creds.enc.yaml     <-- SOPS-encrypted; never plain
└── docs/
    ├── architecture.md
    ├── bootstrap.md
    └── decisions/                  <-- ADRs
        ├── 0001-pick-argocd-over-flux.md
        ├── 0002-use-kyverno-for-image-verification.md
        └── 0003-vault-dev-mode-for-kind-path.md
```

Three structural rules govern the layout.

**Rule 1 — every concern is its own directory.** The application source is in `app/`. The infrastructure is in `terraform/`. The GitOps source of truth is in `gitops/`. The Kubernetes manifests are in `kustomize/`. The observability config is in `observability/`. The secrets are in `secrets/`. The decisions are in `docs/decisions/`. A successor reading the repo for the first time can find any single concern in under a minute because the directory names mean what they say.

**Rule 2 — ArgoCD reads only from `gitops/`.** No `Application` CRD in `gitops/` references a directory outside `gitops/`. The Kustomize overlays under `gitops/apps/app/overlays/` reference the manifests in `kustomize/crunch-quotes/`, but they do so through a Kustomize `bases:` reference, not through ArgoCD. The separation matters because it lets an engineer change a Kustomize manifest without touching the GitOps directory; ArgoCD will re-render and re-apply.

**Rule 3 — decisions are recorded.** The `docs/decisions/` directory holds Architecture Decision Records (ADRs) in the standard format: title, status, context, decision, consequences. ADR-0001 records why ArgoCD was chosen over Flux; ADR-0002 records why Kyverno was chosen over OPA Gatekeeper; ADR-0003 records why Vault runs in dev mode on the kind path. The ADRs are short — 200 to 400 words each — and they are what a successor reads when they ask "why is it this way and not the other way". A repo without ADRs is a repo whose decisions are not auditable.

The reference layout draws from a few canonical sources. The `gitops/apps/` shape is the App-of-Apps pattern from <https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/>. The `kustomize/<app>/base|overlays/` shape is from <https://kubectl.docs.kubernetes.io/references/kustomize/glossary/>. The `docs/decisions/` shape is from the Architecture Decision Records site at <https://adr.github.io/>. None of this is invention; it is composition of standards.

---

## 4. The principles that make a repository operable

Three principles, drawn from the layout above, that you should be able to articulate when defending the capstone's structure.

### Principle 1 — readability over cleverness

The directory names use the most boring possible words. `app/` not `service/`. `terraform/` not `infra/`. `gitops/` not `argo/`. `kustomize/` not `manifests/` or `k8s/`. A successor encountering the repo with no context can guess what is in each directory; that is the entire point. Clever names are a tax the successor pays.

### Principle 2 — one source of truth per concern

The Postgres password lives in `secrets/postgres-creds.enc.yaml` and nowhere else. The application's image tag lives in `kustomize/crunch-quotes/base/deployment.yaml` (overridden per-environment in the overlays). The cluster's CRDs live in `gitops/apps/platform/`. Any duplication is a future bug — the day the duplicate diverges from the original, the system is wrong and someone has to debug which copy is authoritative. Refuse duplication.

### Principle 3 — every operational action is in `Makefile` or in the GitHub Actions workflow

A human operating the cluster runs `make bootstrap`, `make smoke`, `make destroy`. They do not type long `helm install` commands. They do not type long `kubectl apply` commands. The actions are named, scripted, and stored in version control. The discipline is not laziness — it is reproducibility. The action a human can type once they can type a hundred times; the action that lives in `Makefile` runs identically every time, and a new engineer learns the operational surface by reading the `Makefile`.

---

## 5. What we will build over the next six days

The capstone is one repository. The repository builds in five exercises:

- **Exercise 1 (Tuesday morning)** — the cluster bootstrap. Terraform creates the kind cluster, applies ArgoCD, applies the App-of-Apps. The cluster is empty but reconciling.
- **Exercise 2 (Tuesday afternoon)** — the application and its CI. The FastAPI source, the Dockerfile, the Compose, the GitHub Actions workflow. The image is signed and pushed; the SBOM is generated; the Trivy scan passes.
- **Exercise 3 (Thursday)** — the platform install. ingress-nginx, cert-manager, kube-prometheus-stack, Loki, OTel Collector. Configured via `gitops/apps/platform/` and reconciled by ArgoCD.
- **Exercise 4 (Friday morning)** — the supply-chain and cost wiring. Vault, the Kyverno verifyImages policy, OpenCost, the FinOps label policy.
- **Exercise 5 (Friday afternoon)** — the smoke test. The end-to-end test that hits the application's URL and verifies the response, the metrics, the trace, the cost attribution.

The mini-project on Sunday composes the five exercises into one repository, adds the runbook and the disaster-recovery plan, and runs the rebuild rehearsal.

---

## 6. The cultural argument for the order

A reflexive question at this point: why does the order matter so much. The cluster is small, the install is twenty minutes, you could just install things in any order and reorder them when something fails.

The answer is operational rather than technical. A cluster that installs in a documented, deterministic order is a cluster a new engineer can bring up. A cluster that "just works if you do these things in the right order, which we have written down somewhere" is a cluster that takes a week of pairing to bring up. The discipline of writing down the order — and of the bootstrap script that encodes the order — is the discipline of making the cluster operable by someone other than the person who built it.

This is the same argument as the W11 argument about cost reports: the work is not the tool. The tool installs in twenty minutes. The work is the artifact that makes the tool's installation reproducible. The artifact is what survives the original author.

A platform engineer's career is, in the long run, the artifacts they leave behind. The capstone is the smallest, most honest version of that artifact. The order is part of the artifact.

---

## 7. Pre-reading for Exercise 1

Before tomorrow's exercise, read:

- The ArgoCD *Getting Started* page: <https://argo-cd.readthedocs.io/en/stable/getting_started/>. About 15 minutes.
- The *Cluster Bootstrapping* page: <https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/>. About 20 minutes.
- The kind quickstart: <https://kind.sigs.k8s.io/docs/user/quick-start/>. About 10 minutes.
- The Terraform `tehcyx/kind` provider docs: <https://registry.terraform.io/providers/tehcyx/kind/latest/docs>. About 10 minutes.

Total pre-reading: about one hour. The exercise itself is two hours. By Wednesday morning the cluster is bootstrapped and empty; the application arrives Thursday.

Onward.
