# C15 · Crunch DevOps

> A free, open-source **12-week DevOps / SRE track**. From your first Dockerfile to a real application deployed on Kubernetes with CI/CD, monitoring, alerting, secrets, and an incident-response runbook you'd actually use at 3 AM.

[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)
[![Docker · K8s · Terraform · CI/CD](https://img.shields.io/badge/stack-Docker_·_K8s_·_Terraform_·_CI/CD-2563EB.svg)](#stack)
[![Built in the open](https://img.shields.io/badge/built-in%20the%20open-2563EB.svg)](https://github.com/CODE-CRUNCH-CLUB)

C15 is the **operations counterpart to the Python tracks.** If you've built something in C1, C16, or C5 and want it on the internet — operating reliably, observable, recoverable when it breaks — this is where you learn that work.

The track is vendor-aware but vendor-balanced. We use a managed Kubernetes (DigitalOcean by default; AWS / GCP equivalents documented), Terraform, GitHub Actions, Prometheus, Grafana, Loki. Total course cost on cloud bills: < $30 USD over 12 weeks if you tear down nightly.

---

## Pathway summary

- **Full-time:** 12 weeks · ~36 hrs/week · ~432 hours
- **Working-engineer pace:** 6 months · ~18 hrs/week
- **Evening / cohort study:** 1 year · ~9 hrs/week — *the recommended pace.* Half the value of DevOps is on-call experience, which compresses badly.

See [`SYLLABUS.md`](SYLLABUS.md) for the full 12-week breakdown.

---

## What you will be able to do at the end of 12 weeks

- **Containerize** any web app with a multi-stage Dockerfile that's small, fast, and reproducible.
- **Orchestrate** services locally with `docker compose` and at scale with Kubernetes.
- **Provision** real infrastructure with Terraform on at least one cloud.
- **Build CI/CD pipelines** with GitHub Actions that test, build images, push, and deploy on merge.
- **Configure observability**: structured logs to Loki, metrics to Prometheus, traces to Tempo / Jaeger, dashboards in Grafana.
- **Manage secrets** properly — `sops`, Vault, cloud KMS — never `.env` in production.
- **Diagnose production issues**: read logs, query metrics, follow traces, write a post-mortem.
- **Write infrastructure** the same way you write application code: source control, reviewed, tested.
- **Ship** a real C16-style application to production with full CI/CD and monitoring.

---

## Who this is for

- **C1 + C14 graduate** ready to operate what they build.
- **Backend engineer** ready to stop tossing things over a wall to ops.
- **Self-taught developer** preparing for SRE / Platform / DevOps roles.
- **C16 graduate** with a deployable web app and no operations experience.

Not for: pure beginners (do [C1](../C1-Code-Crunch-Convos/) and [C14](../C14-CRUNCH-LINUX/) first), nor people who want a cloud-vendor certification course (we touch one cloud; vendor certs are paid and out of scope here).

---

## Prerequisites

- **C1 Weeks 1–11** (Python, basic Flask, SQL, testing).
- **C14 · Crunch Linux** completed *or* equivalent comfort with bash, ssh, file permissions, services.
- **Strongly recommended:** **C16 Weeks 1–10** so you have a real application to deploy in the capstone.
- A credit card (for the cloud free tiers / small VPS — total spend < $30 USD if tearing down nightly).

---

## What you ship

By the end of the 12 weeks, your `crunch-devops-portfolio-<yourhandle>` GitHub repo contains:

1. A **hand-built container** from `unshare` and a tarball, then re-done with Docker (Week 1).
2. **Three Dockerfile variants** of one app — naïve, multi-stage, distroless — with size and security comparisons (Week 2).
3. A **`docker compose` local dev environment** for a multi-service app, one-command spin-up (Week 3).
4. A **GitHub Actions pipeline** for a real repo: lint → test (matrix) → build image → push → tag (Week 4).
5. A **Terraform-provisioned** small app on DigitalOcean (~$10/mo) with a domain, TLS, and managed Postgres (Week 5).
6. **GitOps** (ArgoCD / Flux) for the Week-5 setup (Week 6).
7. A **stateless app on a `kind` cluster** with a rolling deploy (Week 7).
8. The **same app on a managed Kubernetes cluster** with persistent volumes (Week 8).
9. A **Helm chart** for the app + Prometheus + Grafana via charts (Week 9).
10. **Full observability** — logs to Loki, metrics to Prometheus, traces to Tempo, dashboards in Grafana (Week 10).
11. A **security audit** of your own setup: three issues found, three issues fixed, documented (Week 11).
12. **Capstone:** a real application deployed end-to-end with CI/CD, monitoring, alerting, runbooks, and a written 5-page operations document (Week 12).

---

## Tools (all free / open-source / low-cost)

| Tool | Role |
|------|------|
| **Docker · BuildKit** | Containers |
| **docker compose** | Local multi-service |
| **GitHub Actions** | CI/CD (free for public repos) |
| **Terraform** | IaC |
| **DigitalOcean Kubernetes** *(default)* — or **EKS / GKE / AKS** | Managed K8s |
| **kind / k3d** | Local K8s |
| **Helm · Kustomize** | Templating |
| **ArgoCD · Flux** | GitOps |
| **Prometheus · Grafana · Loki · Tempo · Alertmanager** | Observability stack |
| **sops · Vault · cloud KMS** | Secrets |
| **cosign · syft · grype · trivy · pip-audit** | Supply-chain security |
| **structlog · OpenTelemetry SDK (Python)** | App-side observability |

Cloud spend estimate: ~$30 USD over 12 weeks if you tear down resources nightly. We document the tear-down commands at the end of every relevant week.

---

## Next track after C15

- **C18 · Crunch GCP / C19 · Crunch AWS** (Tier 2 Labs) — for cloud-specialist depth.
- **C22 · Crunch Mesh** (Tier 2 Labs) — for distributed-systems depth.
- **[C6 · Cybersecurity Crunch](../C6-CYBERSECURITY-CRUNCH/)** — to harden what you've deployed.

---

## License

GPL-3.0.

---

*C15 is part of the Code Crunch open-source curriculum.* [Master catalog ↗](../MASTER-CURRICULUM.md) · [Brand family ↗](../../assets/brand/BRAND-FAMILY.md)
