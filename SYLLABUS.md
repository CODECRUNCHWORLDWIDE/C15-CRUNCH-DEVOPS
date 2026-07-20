# C15 · Crunch DevOps — Full Syllabus

**12 weeks · ~432 hours full-time · ~36 hrs/week · C1 graduate → junior DevOps engineer / SRE**

The complete syllabus for the C15 DevOps track. Every week follows the standard Code Crunch layout (README, resources, lecture-notes, exercises, challenges, quiz, homework, mini-project).

---

## Who this is for

- You've completed **C1 · Code Crunch Convos** and can write a working Flask app.
- You've also taken **C14 · Crunch Linux** or have equivalent comfort in a terminal.
- You want to be able to **deploy and operate** the apps you build, not just write them.

If you've never used Git, never SSH'd into a server, and don't know what a shell is — start with C1 and C14 first.

---

## What you will be able to do at the end of 12 weeks

- **Containerize** any web app with a multi-stage Dockerfile that's small, fast, and reproducible.
- **Orchestrate** services locally with `docker compose` and at scale with Kubernetes (basic operations: deploy, scale, logs, rolling update, rollback).
- **Provision** real infrastructure with **Terraform** on at least one cloud (AWS, GCP, or DigitalOcean).
- **Build CI/CD pipelines** with GitHub Actions that test, build images, push them, and deploy on merge.
- **Configure observability**: structured logs to Loki, metrics to Prometheus, traces to Tempo/Jaeger, dashboards in Grafana.
- **Manage secrets** properly: avoid `.env` in production, use `sops`, HashiCorp Vault, or cloud secrets managers.
- **Diagnose production issues**: read logs, query metrics, follow traces, conduct a post-incident review.
- **Write infrastructure** the same way you write application code: in source control, reviewed, tested.
- **Ship the C16 capstone (`crunchwriter`)** — if you've also taken C16 — to production with full CI/CD and monitoring.

---

## Program at a glance

| Phase | Weeks | Outcome |
|-------|-------|---------|
| **Phase 1 — Containers & Local Orchestration** | 01 – 03 | Docker, Compose, the 12-factor app |
| **Phase 2 — CI/CD & Infrastructure as Code** | 04 – 06 | GitHub Actions, Terraform, immutable infrastructure |
| **Phase 3 — Kubernetes** | 07 – 09 | Pods, services, ingress, scaling, operators |
| **Phase 4 — Observability, Security, Capstone** | 10 – 12 | Logs / metrics / traces, secrets, deploy a real app |

---

## How the weekly load adds up

| Component | hrs/wk |
|-----------|------:|
| Lectures / readings | 6 |
| Hands-on exercises | 8 |
| Coding challenges | 4 |
| Quiz + readings | 3 |
| Homework problems | 6 |
| Mini-project | 7 |
| Self-study & review | 2 |
| **Total** | **36** |

---

## Weekly breakdown

### Phase 1 — Containers & Local Orchestration

#### Week 1 — What's a Container, Really?

Linux namespaces (PID, network, mount, user, UTS). cgroups. The OCI image spec. Building an image without Docker (using `buildah`). Why Docker won and what's emerging after it (containerd, Podman, nerdctl).

- **Mini-project:** Build a container manually with `unshare` and a tarball. No Docker. Then re-do it with Docker and compare.

#### Week 2 — Dockerfiles That Don't Suck

Layer caching, multi-stage builds, distroless and Alpine, scratch images. `.dockerignore`. Reproducibility. Image scanning with `trivy` or `grype`.

- **Mini-project:** Take a real Python web app (yours from C16, or a sample). Build it three ways: naïve, multi-stage, distroless. Compare image size, build speed, attack surface.

#### Week 3 — `docker compose` and the 12-Factor App

`compose.yml` syntax. Service discovery, volumes, networks, healthchecks, restart policies. The 12-factor principles. `.env` files done right.

- **Mini-project:** Local dev environment for a multi-service app (web + db + cache + worker). One command (`docker compose up`) starts everything with seed data.

---

### Phase 2 — CI/CD & Infrastructure as Code

#### Week 4 — GitHub Actions Beyond Hello-World

Workflows, jobs, matrix builds, caching, reusable workflows, secrets, OIDC for cloud, artifact handling, deploy-on-merge.

- **Mini-project:** A CI pipeline for a real repo: lint → test (matrix) → build image → push to GHCR → tag release.

#### Week 5 — Terraform Fundamentals

The state file. Providers, resources, modules. `plan` vs `apply`. Remote state. The two-phase strategy: bootstrap then iterate.

- **Mini-project:** Provision a small public-facing app on DigitalOcean (~$10/mo): a droplet, a managed Postgres, a domain, TLS. All in Terraform.

#### Week 6 — Immutable Infrastructure and GitOps

Why mutable state is the enemy. Packer for images. ArgoCD / Flux for GitOps. Pull-based vs push-based deploys.

- **Mini-project:** Convert your Week 5 setup to GitOps: changes to a config repo trigger reconciliation automatically.

---

### Phase 3 — Kubernetes

#### Week 7 — Kubernetes from First Principles

Pods, deployments, services, ingress. The control plane. `kubectl` essentials. Reading YAML without losing your mind.

- **Mini-project:** Deploy a stateless web app to a local `kind` (Kubernetes in Docker) cluster. Expose it via ingress. Update it with a rolling deploy.

#### Week 8 — Real Clusters and Storage

Managed Kubernetes (DigitalOcean Kubernetes, GKE, EKS) — costs, tradeoffs. Persistent volumes. StatefulSets. When NOT to run a database on Kubernetes.

- **Mini-project:** Move your Week 7 app to a managed cluster. Add a small stateful service (e.g., Redis). Add a backup job.

#### Week 9 — Operators, Helm, and the Ecosystem

`helm` for templating + releases. Custom resources and operators. Service mesh (Istio / Linkerd) at a high level — when to bother.

- **Mini-project:** Package your app as a Helm chart. Install Prometheus and Grafana via official Helm charts. Wire your app's metrics to the dashboard.

---

### Phase 4 — Observability, Security, Capstone

#### Week 10 — Observability: Logs, Metrics, Traces

Structured logging with `structlog` (Python). Metrics with `prometheus_client`. Distributed tracing with OpenTelemetry. The three pillars and how they fit together. Reading flamegraphs and trace timelines.

- **Mini-project:** Instrument your app with all three. Build a dashboard that answers: "Is the service healthy right now?" and "What was different the moment latency spiked?"

#### Week 11 — Security: Secrets, Supply Chain, Hardening

Storing secrets: `sops`, Vault, cloud KMS. Software supply chain: SBOMs, image signing (cosign), dependency pinning. Cluster hardening: PodSecurityStandards, network policies. RBAC.

- **Mini-project:** Audit your existing project. Find at least three security issues. Fix them. Document the audit and the fixes.

#### Week 12 — On-Call, Post-Mortems, and the Capstone

What an SRE actually does. SLO/SLI/SLA. Runbooks. Conducting a blameless post-mortem. Then: ship the real thing.

- **Capstone:** Deploy a real application (yours from C16 or one you choose) to production with: CI/CD, monitoring, alerting, runbooks, and a public URL. Then write a 5-page operations document.

---

## Skills progression chart

```text
W1  ─ namespaces, cgroups, OCI
W2  │ Dockerfile mastery
W3  ─ docker compose, 12-factor
W4  ─ GitHub Actions
W5  │ Terraform basics
W6  ─ GitOps, immutable infra
W7  ─ Kubernetes basics
W8  │ managed K8s, storage
W9  ─ Helm, operators
W10 ─ logs / metrics / traces
W11 │ secrets, supply chain
W12 ─ on-call + CAPSTONE
```

---

## Adapting the syllabus

- **Part-time (18 hrs/wk):** ~6 months.
- **Cohort study (9 hrs/wk):** ~1 year. Strongly recommended format — DevOps is harder alone because half the value is operating *real* services with peers paging each other.

---

## What this track depends on

- **C1 weeks 1–11** (Python, basic Flask, SQL, testing)
- **C14 · Crunch Linux** (or equivalent terminal proficiency)
- **C16 weeks 1–10 (recommended, not required)** — if you've built `crunchwriter` in C16, C15 lets you deploy it for real.

---

## What you won't learn (but should later)

- **Major cloud platform deep dives** (AWS in depth, GCP in depth) — we touch one cloud, you specialize after.
- **Networking at the BGP / data-center level** — out of scope.
- **Database administration in depth** — C10 in C1 touches it; for real DBA work, follow the [Postgres administration cookbook](https://www.postgresql.org/docs/current/admin.html) (free).
- **Distributed systems theory** — out of scope; we teach the operational reality, not the theory. Follow [MIT 6.824](https://pdos.csail.mit.edu/6.824/) (free, world-class) for the theory.

---

## License

GPL-3.0.
