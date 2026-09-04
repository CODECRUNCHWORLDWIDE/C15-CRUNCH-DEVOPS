# C15 · Crunch DevOps

> A free, open-source **12-week DevOps / SRE track**. From your first Dockerfile to a real application deployed on Kubernetes with CI/CD, monitoring, alerting, secrets, and an incident-response runbook you'd actually use at 3 AM.

[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)
[![Docker · K8s · Terraform · CI/CD](https://img.shields.io/badge/stack-Docker_·_K8s_·_Terraform_·_CI/CD-2563EB.svg)](#stack)
[![Built in the open](https://img.shields.io/badge/built-in%20the%20open-2563EB.svg)](https://github.com/CODE-CRUNCH-CLUB)

C15 is the **operations counterpart to the Python tracks.** If you've built something in C1, C16, or C5 and want it on the internet — operating reliably, observable, recoverable when it breaks — this is where you learn that work.

The track is vendor-aware but vendor-balanced. We use a managed Kubernetes (DigitalOcean by default; AWS / GCP equivalents documented), Terraform, GitHub Actions, Prometheus, Grafana, Loki. Total course cost on cloud bills: < $30 USD over 12 weeks if you tear down nightly.

---

## Standards & equivalency

> C15 stands in for a university's DevOps and continuous-delivery course, and for the automated-testing half of its software quality-assurance course.

**University equivalent.** Two of them, and the claim is not equally strong against both. **DevOps and Continuous Delivery** — `CEN 4083`, `CS 4273`, `CSYE 7220`. Coverage: **full**. **Software Testing and Quality Assurance** — `CEN 4072`, `CS 4239`, `CS 40800`. Coverage: **partial**.

Partial has a precise meaning here, and it is not "most of it". C15 teaches testing where it bites — as an automated gate inside a delivery pipeline, so a failing test stops a release instead of being noticed a week later — and it assesses that. What it does not teach is **test design as a subject**. A university section of `CEN 4072`, `CS 4239` or `CS 40800` spends weeks on how you decide *which* tests to write: equivalence partitioning, boundary-value analysis, formal statement and branch coverage criteria, mutation testing. C15 writes a suite, sets a line-coverage threshold in a workflow file, and moves on to what happens when the gate goes red. Those two rows are marked `lighter` in the table below, declared again at the end of this section, and recorded in the ledger's `stillToAdd`.

C15 carries no credit, no transcript entry, no accreditation and no proctored exam. The equivalence is one of **content and skill**: the outcomes below are taught here at the same depth or deeper except where a row says otherwise, and every one of them is assessed. What a registrar records is not something an open repository can give you.

| University outcome | Where this course teaches it | Depth |
| --- | --- | --- |
| **DevOps** — explain what a container is in terms of the operating-system mechanisms underneath it, and package an application as an image | [Week 01](curriculum/week-01-what-is-a-container/) | deeper |
| **DevOps** — build production-quality images: layer caching, multi-stage builds, minimal bases, a non-root runtime user | [Week 02](curriculum/week-02-dockerfiles-that-dont-suck/) | deeper |
| **DevOps** — compose a multi-service application and configure it from its environment rather than its source | [Week 03](curriculum/week-03-docker-compose-12-factor/) | same |
| **DevOps** — build a continuous-integration pipeline that lints, tests and builds on every change | [Week 04](curriculum/week-04-github-actions/) | same |
| **DevOps** — continuous delivery: publish a versioned, traceable artifact and deploy it on merge without a human typing a push command | [Week 04](curriculum/week-04-github-actions/) | deeper |
| **DevOps** — provision infrastructure declaratively with infrastructure as code, including state, modules and a remote backend | [Week 05](curriculum/week-05-terraform-fundamentals/) | same |
| **DevOps** — configuration management and immutable infrastructure: bake a machine image rather than patching a running host | [Week 06](curriculum/week-06-gitops-and-immutable-infra/) | same |
| **DevOps** — drive deployment from a versioned description of the desired state, and reconcile drift automatically | [Week 06](curriculum/week-06-gitops-and-immutable-infra/) | deeper |
| **DevOps** — orchestrate containers on a cluster, and explain the orchestrator's architecture and its reconciliation model | [Week 07](curriculum/week-07-kubernetes-from-first-principles/) | deeper |
| **DevOps** — release without taking the service down: rolling updates, readiness and liveness probes, rollback | [Week 07](curriculum/week-07-kubernetes-from-first-principles/) | same |
| **DevOps** — deploy onto a managed cloud platform, and evaluate managed against self-managed on burden, cost, control and lock-in | [Week 08](curriculum/week-08-managed-kubernetes-and-addons/) | same |
| **DevOps** — monitor a running system: collect metrics, logs and traces, build dashboards, and route alerts | [Week 09](curriculum/week-09-observability-prometheus-grafana-loki-otel/) | deeper |
| **DevOps** — define service-level indicators, objectives and an error budget, and alert on the budget rather than on the symptom | [Week 09](curriculum/week-09-observability-prometheus-grafana-loki-otel/) | deeper |
| **DevOps** — manage secrets: keep credentials out of source control, out of images, and rotatable without a redeploy | [Week 10](curriculum/week-10-secrets-and-supply-chain/) | deeper |
| **DevOps** — secure the delivery pipeline itself: artifact signing, provenance, a bill of materials, and admission control | [Week 10](curriculum/week-10-secrets-and-supply-chain/) | deeper |
| **DevOps** — reason about what the deployed system costs to run, and attribute that to a workload and a team | [Week 11](curriculum/week-11-cost-and-finops/) | deeper |
| **DevOps** — diagnose a fault in a deployed system from what the system itself emits, without a debugger and without guessing | [Week 07](curriculum/week-07-kubernetes-from-first-principles/) | deeper |
| **DevOps** — integrate the whole toolchain into one end-to-end delivery pipeline for a working application, and document its operation | [Week 12](curriculum/week-12-capstone-production-grade-deploy/) | deeper |
| **Testing and QA** — write automated tests for a unit of code with a test framework, and run them from a command that is written down | [Week 04](curriculum/week-04-github-actions/) | same |
| **Testing and QA** — automate the quality gate: a failing test blocks the artifact, and the block is enforced by the build rather than by a person | [Week 04](curriculum/week-04-github-actions/) | deeper |
| **Testing and QA** — measure code coverage and hold the build to a threshold | [Week 04](curriculum/week-04-github-actions/) | same |
| **Testing and QA** — static analysis and linting as part of the same gate | [Week 04](curriculum/week-04-github-actions/) | same |
| **Testing and QA** — integration and system testing of an assembled system, end to end, against a running deployment | [Week 12](curriculum/week-12-capstone-production-grade-deploy/) | same |
| **Testing and QA** — security and vulnerability testing of the artifact under test, with a severity threshold that fails the build | [Week 02](curriculum/week-02-dockerfiles-that-dont-suck/) | deeper |
| **Testing and QA** — defect diagnosis: reproduce a failure, localise the fault from real output, repair it, and confirm the repair | [Week 07](curriculum/week-07-kubernetes-from-first-principles/) | deeper |
| **Testing and QA** — reviews and inspections: read an artifact somebody else wrote and deliver a judgement on it | [Week 08](curriculum/week-08-managed-kubernetes-and-addons/) | same |
| **Testing and QA** — test design from a specification: equivalence partitioning, boundary-value analysis, and the written test plan that comes out of them | [Week 04](curriculum/week-04-github-actions/) | lighter |
| **Testing and QA** — formal coverage criteria beyond a line percentage, and mutation testing as a way to measure whether the suite is any good | [Week 04](curriculum/week-04-github-actions/) | lighter |

Every row above points at a week that **assigns work** on that outcome — an exercise, a challenge, a quiz item, a homework problem or a mini-project — not merely a week that mentions it.

**The industry bar.** What an employer expects of somebody paid to operate systems, and where this course makes the learner do it. Two rows below say plainly what C15 does *not* have, and name what stands in its place, because a green row that is not true is worse than a red one.

| What the job expects | Where this course does it |
| --- | --- |
| Work lands as a commit in a repository you own, not a file on your desktop | [`curriculum/week-01-what-is-a-container/mini-project/README.md`](curriculum/week-01-what-is-a-container/mini-project/README.md) ends by pushing and tagging `v1.0`, and every week after it ends the same way; the twelve mini-projects accumulate into one portfolio repository |
| You read code you did not write and form a judgement on it | [`curriculum/week-07-kubernetes-from-first-principles/challenges/challenge-01-debug-a-broken-deployment.md`](curriculum/week-07-kubernetes-from-first-principles/challenges/challenge-01-debug-a-broken-deployment.md) — five Deployments somebody else broke — and [`curriculum/week-08-managed-kubernetes-and-addons/challenges/challenge-02-debug-a-stuck-argocd-sync.md`](curriculum/week-08-managed-kubernetes-and-addons/challenges/challenge-02-debug-a-stuck-argocd-sync.md) |
| Tests exist, and the command to run them is written down | [`curriculum/week-04-github-actions/exercises/exercise-01-first-real-pipeline.md`](curriculum/week-04-github-actions/exercises/exercise-01-first-real-pipeline.md) — the learner writes `test_app.py`, runs `pytest -q` locally, then the same command becomes a required job in the workflow; [`curriculum/week-04-github-actions/mini-project/README.md`](curriculum/week-04-github-actions/mini-project/README.md) adds `--cov-fail-under=70`. **C15 ships no test files of its own.** This repository is teaching material, all prose; the suite lives in the learner's repository, which is where a pipeline can fail on it |
| You read the real error instead of guessing | C15 has **no section called `Common bugs to catch`**. Its equivalent is inline and it is real output: every exercise prints the captured result beside the command as an `# Expect:` line, and the Week 07 challenge above is five failures diagnosed from an actual `CrashLoopBackOff`, an empty endpoint list, and a readiness probe that never goes ready |
| Tooling is used the way a team uses it — a linter, a test run and a build on every change, in CI | [`curriculum/week-04-github-actions/`](curriculum/week-04-github-actions/), and then again in the capstone's single release workflow |
| Dependencies are pinned and isolated, and the build is reproducible next quarter | [`curriculum/week-02-dockerfiles-that-dont-suck/lecture-notes/02-layer-caching-multistage-distroless.md`](curriculum/week-02-dockerfiles-that-dont-suck/lecture-notes/02-layer-caching-multistage-distroless.md) — lockfiles, base images pinned by digest, cache mounts kept out of the shipped image |
| The output is portfolio-grade: it runs from a clean clone by following the README | [`curriculum/week-12-capstone-production-grade-deploy/README.md`](curriculum/week-12-capstone-production-grade-deploy/README.md) — a bootstrap command, a smoke test, and a timed destroy-and-rebuild rehearsal that proves the README is complete |
| Deliverables that are not code — a runbook, a right-sizing recommendation, an incident write-up — are still held to a published standard | [`curriculum/week-11-cost-and-finops/challenges/README.md`](curriculum/week-11-cost-and-finops/challenges/README.md) publishes the rubric before the work is submitted, and weights the write-up above the code volume |
| The professional task is named, not implied | the `Industry` row of the `## Standards this week meets` block in each of the twelve week READMEs |

**Beyond both bars.** Clearing the two floors is entry, not success. Open any of these and check it in under a minute.

| What we add | Which bar it beats | Where it lives |
| --- | --- | --- |
| A container built by hand from `unshare`, `chroot`, a rootfs tarball and a cgroup write — before Docker is installed at all, so the tool is something you can read rather than something you have to trust | university | [`curriculum/week-01-what-is-a-container/exercises/exercise-01-build-a-container-by-hand.md`](curriculum/week-01-what-is-a-container/exercises/exercise-01-build-a-container-by-hand.md) |
| Every quiz carries its own answer key, folded under the questions and published with them, giving the reasoning rather than the letter | both | [`curriculum/week-01-what-is-a-container/quiz.md`](curriculum/week-01-what-is-a-container/quiz.md) |
| Worked solutions for the cluster weeks that print the expected output and, next to it, the diagnostic question to ask when your output diverges from it | both | [`curriculum/week-07-kubernetes-from-first-principles/exercises/SOLUTIONS.md`](curriculum/week-07-kubernetes-from-first-principles/exercises/SOLUTIONS.md) |
| A supply-chain week that goes well past "scan your image": SLSA levels, keyless signing, a transparency log, SBOM diffing, and an admission policy that refuses an unsigned image | both | [`curriculum/week-10-secrets-and-supply-chain/`](curriculum/week-10-secrets-and-supply-chain/) |
| A whole week on what the deployed system costs to run — unit economics, allocation by label, anomaly detection written as code — which neither university outcome set asks for | university | [`curriculum/week-11-cost-and-finops/`](curriculum/week-11-cost-and-finops/) |
| The learner finishes holding a public repository with an operations runbook and a timed rebuild-from-scratch rehearsal, instead of a grade only a registrar can see | both | [`curriculum/week-12-capstone-production-grade-deploy/lecture-notes/03-operating-the-cluster-and-the-runbook.md`](curriculum/week-12-capstone-production-grade-deploy/lecture-notes/03-operating-the-cluster-and-the-runbook.md) |

**Gaps we declare.** Against `CEN 4083`, `CS 4273` and `CSYE 7220` there is no outcome C15 does not teach and assess. Against `CEN 4072`, `CS 4239` and `CS 40800` the gap is test design as a subject — equivalence partitioning, boundary-value analysis, formal coverage criteria beyond a line percentage, and mutation testing — which is why that claim is `partial` and not `full`; a learner who needs those should treat C15 as the pipeline half of the course and read a testing text for the other half. Three further things are honestly short of the framework rather than of the university: the folded `Under the hood` treatment appears in one lecture note only, [`curriculum/week-01-what-is-a-container/lecture-notes/02-from-tarball-to-image-the-oci-stack.md`](curriculum/week-01-what-is-a-container/lecture-notes/02-from-tarball-to-image-the-oci-stack.md), rather than throughout; the homework problems have no published answers, while all eleven quizzes and the Week 07 to Week 11 exercise sets do; and three of Week 12's five exercises are indexed in [`curriculum/week-12-capstone-production-grade-deploy/exercises/README.md`](curriculum/week-12-capstone-production-grade-deploy/exercises/README.md) but are not yet written.

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
