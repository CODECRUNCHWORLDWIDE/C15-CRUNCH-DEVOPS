# Week 12 — Capstone: A Production-Grade Kubernetes Deploy

> *Eleven weeks of theory only pays off when the eleven pieces sit on one cluster and work together. This week is the work of making them sit there.*

Welcome to Week 12 of **C15 · Crunch DevOps** — the final week. The eleven weeks that came before each addressed one slice of the modern deployment stack: a container, an image, a compose file, a CI pipeline, an infrastructure-as-code module, a GitOps controller, a Kubernetes manifest, an ingress and a certificate, an observability stack, a supply-chain control, a cost report. Each was useful on its own. None of them, taken alone, is what a competent platform engineer ships. What gets shipped is the *composition* — the cluster on which all eleven sit together, the application that flows through all of them in sequence, the documentation that lets someone else operate the result on a Tuesday morning when the first engineer is on vacation.

This week is that composition. The deliverable is one working, publicly accessible application running on a Kubernetes cluster you can hand to a stranger. It is small — a Python FastAPI service backed by Postgres, with a static HTML frontend — and it is deliberately small, because the difficulty is not in the application; it is in everything around the application. The application's source is forty lines. The pipeline that ships it, the cluster that runs it, the controllers that watch it, the secrets it consumes, the certificate it presents, the metrics it exports, the signature on its image, the SBOM that travels with it, the cost report that attributes it — that is the work of the week, and the work of the career.

We will spend the week stitching the previous eleven weeks together in the order they appear in the deployment pipeline. **Monday** is the cluster — `kind` plus the cloud-equivalent path, the network model, the namespaces, the resource quotas, what gets installed and in what order. **Tuesday** is the application and its CI — the Dockerfile (W1-2), the Compose for local dev (W3), the GitHub Actions workflow that builds, tests, scans, signs, and pushes the image (W4 + W10). **Wednesday** is the infrastructure — the Terraform module that provisions the cluster, the ArgoCD bootstrap, the App-of-Apps pattern (W5 + W6). **Thursday** is the platform — the ingress controller, cert-manager, external-dns, the Kubernetes manifests for the application (W7 + W8). **Friday** is the observability — the kube-prometheus-stack, Grafana dashboards, Loki for logs, OpenTelemetry traces, the SLO definitions, the alerts (W9). **Saturday** is the security and the cost — Vault for runtime secrets, SOPS for Git-stored secrets, cosign verification at admission, OpenCost dashboards, FinOps labels (W10 + W11). **Sunday** is the polish — the runbook, the smoke test, the disaster-recovery rehearsal, the README that explains how to take it down and put it back up.

By Sunday evening, you have a cluster running an application that someone on the public internet can reach by a DNS name, served over HTTPS with a real (or local-CA) certificate, with the image signed and the signature verified at admission, with Prometheus scraping it, Loki collecting its logs, OpenTelemetry collecting its traces, OpenCost reporting its cost, ArgoCD reconciling it from Git, and a one-page runbook that tells the next engineer how to operate it. That is what a junior platform engineer should be able to produce on their own. The intent of C15 is that you can.

This week's sidebar — the schedule below — doubles as a wrap-up of the whole track. Each day re-encounters one previous week and integrates its output into the capstone. Use the wrap-up as a self-assessment: if a day's integration feels easy, the underlying week landed; if it feels hard, the underlying week is where to revisit.

---

## Track wrap-up — the twelve weeks of C15 in one page

| Week | Topic                                                              | Week-12 integration                                                                                |
| ---- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| W1   | What is a container — namespaces, cgroups, OCI                     | We run the app as a container; the OCI image is the unit of deploy                                  |
| W2   | Dockerfiles that do not suck — multi-stage, distroless, non-root   | The capstone Dockerfile is multi-stage, distroless-based, non-root, with `HEALTHCHECK`              |
| W3   | Docker Compose and the 12-factor app                               | `compose.yaml` for local dev runs the same image + Postgres; env via 12-factor config               |
| W4   | GitHub Actions CI                                                  | The workflow builds, tests, scans, signs, and pushes on every PR and on `main`                       |
| W5   | Terraform fundamentals                                             | A Terraform module provisions the cluster (kind or cloud), the registry, and ArgoCD               |
| W6   | GitOps and immutable infrastructure                                | ArgoCD App-of-Apps reconciles the cluster from `gitops/` in this repo; no `kubectl apply` by humans |
| W7   | Kubernetes from first principles                                   | Deployment, Service, ConfigMap, Secret, HPA, PDB — written by hand, reviewed line by line          |
| W8   | Managed Kubernetes and add-ons                                     | ingress-nginx + cert-manager + external-dns (or a /etc/hosts equivalent for kind)                  |
| W9   | Observability — Prometheus, Grafana, Loki, OpenTelemetry           | The app exports metrics, ships logs to Loki, emits traces to an OTel collector                      |
| W10  | Secrets and supply chain — Vault, SOPS, cosign, SBOM, Trivy        | Vault runs in the cluster; SOPS for Git secrets; cosign verify at admission; Trivy on PR           |
| W11  | Cost and FinOps — OpenCost, labels, anomaly detection              | OpenCost reports cost by team label; the Kyverno label policy is on by default                     |
| W12  | Capstone — assemble all eleven                                     | This week                                                                                            |

The integration column is also the checklist. If your capstone is missing any one of those rows on Sunday, you have a week-N gap to address.

---

## Learning objectives

By the end of this week, you will be able to:

- **Compose** all eleven prior weeks' outputs into a single, working, public-accessible application. Not in the abstract — actually composed, running, reachable, observable. The composition is the objective; the eleven prior weeks were preparation.
- **Reason** about the order of operations for a cluster bootstrap. Why Terraform precedes ArgoCD, why ArgoCD precedes everything else, why ingress precedes cert-manager, why kube-prometheus-stack must be installed before OpenCost (because OpenCost reads from Prometheus). Reason about what happens when the order is wrong and how a real platform team writes a bootstrap that is idempotent under partial failure.
- **Design** a GitOps repository layout that an operator can read and operate. The `gitops/` directory has a specific shape — App-of-Apps at the root, an `apps/` directory per concern (`platform/`, `monitoring/`, `app/`), each app pointing at a chart or a Kustomize overlay in a deterministic location. The layout is the README.
- **Stitch** the application's CI/CD into a verifiable supply chain end to end. Source commit → GitHub Actions build → Trivy scan → Cosign sign → registry push → ArgoCD pulls → Cosign verify (admission) → image runs. Each arrow is a control point and each control point either passes the artifact or stops the pipeline. Operate the stitch in practice, not as a slide.
- **Write** the runbook a successor will read at 2 AM. Three sections — *the dashboard tour* (where to look first), *the seven common failure modes* (what they look like and what to do), *the disaster-recovery plan* (how to rebuild the cluster from this repo if it is gone). The runbook is the artifact a junior engineer can be handed to operate the system without the original author.
- **Demonstrate** the observability triangle on a real workload. Metrics in Prometheus, logs in Loki, traces in OpenTelemetry, all queryable on Grafana, all answering the question "why was this request slow" from three angles. The three together are observability; any one alone is monitoring.
- **Apply** the supply-chain controls from Week 10 to a workload that is actually shipping. Cosign verification at admission, SBOM generation in CI, vulnerability scanning gated on critical severity, secrets sourced from Vault or sealed with SOPS. The controls are not theatre this week; the workload pulls a real image, the image was signed by a real key, and the cluster refuses to run an unsigned image.
- **Operate** a cost-attribution report on a workload that is actually running. OpenCost is installed, the FinOps labels are enforced by Kyverno, the workload appears in the allocation report under the correct team, and a Grafana panel divides the workload's cost by its request count to produce a unit-cost dashboard.
- **Tear down** the cluster, push the state of the world to Git, and bring it back up. The reverse exercise — destroy everything, rebuild from the repository — is the verification that the bootstrap is in fact reproducible. A bootstrap that has never been re-run is a bootstrap with bugs that have not yet been observed.
- **Critique** the capstone honestly. The deliverable will have weaknesses; the rubric grades the diagnosis of those weaknesses as highly as the implementation of the strengths. A capstone whose author can name its three biggest weaknesses is a capstone whose author has earned the certificate.

---

## Prerequisites

This week assumes you have completed **Weeks 1-11 of C15** and have running outputs from at least the mini-projects of W8 (managed Kubernetes), W9 (observability), W10 (supply chain), and W11 (cost). The capstone re-uses code and config patterns from those weeks; you will copy and adapt rather than rebuild from scratch.

Tooling — verify each one is on `PATH`:

```bash
docker --version
kind version
kubectl version --client
helm version --short
terraform version
argocd version --client
cosign version
trivy --version
sops --version
gh --version
python3 --version
```

Versions that the manifests in this week's `exercises/` are tested against (May 2026):

- Kubernetes **1.31+** (kind 0.24+ pulls 1.31 by default; the manifests use `apps/v1`, `networking.k8s.io/v1`, `policy/v1`, `autoscaling/v2`, `cert-manager.io/v1`, `argoproj.io/v1alpha1`, `kyverno.io/v1`, `monitoring.coreos.com/v1`).
- Helm **3.14+**.
- Terraform **1.9+** with the `kind` provider (`tehcyx/kind`) for the local path or the `aws`/`google` providers for the cloud path.
- ArgoCD **2.12+**.
- Cosign **2.4+**.
- Trivy **0.55+**.
- SOPS **3.9+**.
- Python **3.11+**.

You will need **8 GB of free RAM** to run the full capstone on `kind`. The cluster fits in 6 GB but the build steps (image build, Trivy scan, push) plus the IDE plus the browser plus the docker daemon adds up. If you have less, the README in `exercises/00-cluster-bootstrap/` describes a slim profile that disables OpenTelemetry-Collector and Loki and leaves Prometheus + OpenCost as the only observability stack — the capstone grades to the full stack but the slim profile passes for the integration test.

You do **not** need a paid cloud account. The capstone runs in two equivalent modes:

1. **Local mode** — kind cluster, ingress on localhost via `kubectl port-forward` or `kind`'s `extraPortMappings`, cert-manager with a self-signed `ClusterIssuer`, image registry is a local registry the kind cluster talks to. This is the default and what the manifests assume.
2. **Cloud-free-tier mode** — Civo Kubernetes (free $250 credit for new accounts), Oracle Cloud always-free (one Arm VM is enough for a single-node k3s), or an AWS Free Tier EKS (the control plane is no longer free but t3.micro nodes are, for one year). The Terraform module has a `civo` profile in `terraform/`. Use this only if you specifically want a public URL on the open internet.

The local mode is the path the rubric grades against. The cloud mode is enrichment.

---

## Topics covered

- **The capstone application.** A FastAPI service called `crunch-quotes` that returns a quote from a Postgres table. The application is small on purpose; the work is around it. The service exposes `/health`, `/quote`, and `/metrics`. The Postgres is a single-replica StatefulSet with a PersistentVolumeClaim. The frontend is a static HTML page served from the same pod that fetches a quote on load.
- **The cluster bootstrap order.** A specific sequence: Terraform creates the cluster and the registry; ArgoCD is installed as the first workload; ArgoCD installs the kube-prometheus-stack, ingress-nginx, cert-manager, Vault, Kyverno, OpenCost in that order; the application is the last manifest applied. The order is not arbitrary — each layer depends on the one before, and the order is what an idempotent bootstrap script encodes.
- **The GitOps repo layout.** A single repository (`gitops/`) at the root of the project holds the App-of-Apps. The root app points at `apps/`, which contains one Application CRD per platform component and the application itself. The Kustomize overlays under `apps/<name>/overlays/<env>/` hold env-specific values. The pattern is canonical ArgoCD; we follow it without invention.
- **The CI pipeline.** A single `.github/workflows/release.yaml` that runs on every PR and on every push to `main`. On PR: build, unit test, Trivy scan, cosign attest-without-push (smoke test). On `main`: build, unit test, Trivy scan, cosign sign and push, SBOM attach, ArgoCD auto-sync picks up the new tag. The workflow is the integration of W4 and W10 in one file.
- **The signed image and the verified admission.** The Kyverno policy `verifyImages` checks that every image in the `app` namespace has a cosign signature from the team's public key. Unsigned images are refused. The verification is online — Kyverno calls cosign via the `verifyImages` mechanism — and the failure is a `Forbidden` from the admission webhook. We exercise this in Exercise 4 by deliberately deploying an unsigned image and observing the rejection.
- **The ingress, the certificate, the DNS.** Ingress-nginx terminates TLS. Cert-manager mints the certificate. For the local kind path we use a self-signed `ClusterIssuer` (the certificate's CA is trusted locally only). For the cloud path we use Let's Encrypt's ACME issuer. External-dns is optional on the cloud path; on the kind path the DNS is `/etc/hosts` and the manifests document the entry.
- **The observability triangle.** Prometheus scrapes the FastAPI `/metrics` endpoint. Loki collects logs via the Promtail DaemonSet. The OpenTelemetry Collector receives traces from the application's OTel SDK and forwards them to a backend (Tempo, Jaeger, or the local-mode logging exporter for visibility-without-storage). All three are reachable from a single Grafana with three data sources. We define one SLO and one alert on it.
- **The cost panel.** OpenCost reports the application's cost. A Grafana panel divides the cost by the request count from Prometheus to produce a unit-cost number — `dollars per million requests` — which is the unit metric for this service. The panel is the W11 unit-economics dashboard, materialized.
- **The secrets path.** Vault runs in the cluster (dev mode for the kind path; production-mode for the cloud path). The application reads its Postgres password from a Vault static secret via the Vault Agent injector. The Vault token is rotated. SOPS encrypts any secret that lives in Git (e.g., the Vault unseal keys for the dev path). No plaintext secret is committed.
- **The cost-label policy.** Kyverno enforces the `team`, `cost-center`, `environment`, `owner` labels on every pod in the `app` namespace. A deployment without the four labels is refused. The policy is the W11 label policy, ported into the capstone.
- **The runbook.** Three sections, written by you: the dashboard tour, the seven failure modes, the disaster-recovery plan. The runbook is the artifact the rubric weights most heavily — it is the surface that a successor will read first.
- **The disaster-recovery rehearsal.** Sunday morning, you destroy the cluster (`kind delete cluster`) and rebuild it (`make bootstrap`). Time the rebuild. The rebuild time is a real operational number — if it is under 20 minutes, the cluster is reproducible; if it is over an hour, the cluster has snowflakes that the bootstrap did not capture.
- **The handover.** The final deliverable is a Git repository that another C15 graduate could clone and operate. Not "operate eventually" — operate within an hour, by reading the README and the runbook. The repository is the certificate.

---

## Schedule

| Day       | Focus                                                                       | Files                                                                            |
| --------- | --------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Monday    | Lecture 1 — The composition, the bootstrap order, the repository layout      | `lecture-notes/01-composition-and-bootstrap-order.md`                            |
| Tuesday   | Exercise 1 — The cluster bootstrap; Exercise 2 — The application and its CI | `exercises/exercise-01-cluster-bootstrap.md`, `exercise-02-app-and-ci.md`        |
| Wednesday | Lecture 2 — The GitOps layout and the App-of-Apps pattern                   | `lecture-notes/02-gitops-and-app-of-apps.md`                                     |
| Thursday  | Exercise 3 — Platform install (ingress, cert-manager, observability)        | `exercises/exercise-03-platform-install.md`                                      |
| Friday    | Exercise 4 — Supply-chain and cost wiring; Exercise 5 — Smoke test          | `exercises/exercise-04-supply-chain-and-cost.md`, `exercise-05-smoke-test.md`    |
| Saturday  | Lecture 3 — Operating the cluster; the runbook                              | `lecture-notes/03-operating-the-cluster-and-the-runbook.md`                      |
| Sunday    | Challenges, final exam, mini-project / capstone — write the runbook, DR drill | `challenges/`, `quiz.md`, `mini-project/README.md`                               |

---

## How to run this week

The repository root for the capstone is `mini-project/capstone/`. The expected workflow:

```bash
cd mini-project/capstone
make bootstrap            # creates the kind cluster, installs ArgoCD, applies the App-of-Apps
make app-deploy           # tags the application image, pushes, waits for ArgoCD to sync
make smoke                # runs the end-to-end smoke test
make observability        # opens Grafana, Prometheus, OpenCost in browser tabs
make dr-rehearsal         # destroys the cluster, rebuilds it, times the rebuild
make destroy              # tears everything down
```

The `Makefile` is in `mini-project/capstone/Makefile`. Every command is reproducible from a clean machine with the prerequisites installed.

The exercises in `exercises/` are smaller — each is a single integration step you can complete in 60 to 90 minutes. Complete them in order; the capstone composes them in `mini-project/capstone/` on Sunday.

---

## Deliverables

By Sunday evening, submit:

1. **The capstone repository.** Either a fork of a starter you create from `mini-project/capstone/`, or the same directory pushed as a Git repo. The repository must contain: the application source, the Dockerfile, the Compose, the CI workflow, the Terraform module, the GitOps directory, the Kubernetes manifests, the observability config, the Vault and SOPS material, the cost-label policy, the runbook, the disaster-recovery plan, and a top-level README that walks a stranger through bringing the cluster up.
2. **The five exercises completed.** Each has a checkpoint; paste the checkpoint output into `exercises/SOLUTIONS.md`.
3. **One challenge completed.** The two challenges are deeper than the exercises and are graded with a rubric (see `challenges/README.md`).
4. **The final exam.** Twenty questions; `quiz.md`. The exam spans all twelve weeks — it is the cumulative C15 exam.
5. **The homework.** Three items in `homework.md` — a track retrospective, a project plan for production hardening, and a 10-minute talk on the discipline of operating a Kubernetes cluster.
6. **The runbook.** The single most important deliverable. `mini-project/capstone/RUNBOOK.md`. Three sections — dashboard tour, seven failure modes, disaster-recovery plan. The rubric weights the runbook at 30 percent of the capstone grade.

---

## A note on tone, and on the end of C15

This is the last week of the track. The temptation, on the last week, is to add. Add a service mesh; add a multi-cluster fleet; add an ML pipeline; add a chaos-engineering harness. Resist all of it. The discipline of the capstone is finishing — closing the loop on the eleven weeks you already did, producing the artifact that operationalizes them.

A platform engineer's career is, in practice, a sequence of artifacts of exactly this shape. A cluster. A repository. A runbook. A small set of services. Each iteration adds one layer; each layer is in service of the layer above. The artifact at the end of one quarter is the artifact someone else operates the next quarter. The discipline is in the handover. The skill is in the artifact that survives the handover.

Your capstone, this week, is the smallest, most honest version of that artifact. Build it as if you will be handing it to a successor on Monday. Because, in the disposition of the discipline, you will.

Onward — and welcome, on Sunday evening, to the end of C15.
