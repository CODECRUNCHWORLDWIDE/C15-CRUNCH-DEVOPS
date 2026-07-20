# Week 6 — GitOps and Immutable Infrastructure

> *Mutable state is the enemy. The configuration in `main` is the truth, the controller in the cluster is the witness, and the engineer at the keyboard is — at last — out of the hot path.*

Welcome to Week 6 of **C15 · Crunch DevOps**. Week 1 explained what a container is. Week 2 made you build one well. Week 3 wired several of them together with `compose`. Week 4 made that stack ship itself to a registry on every merge to `main`. Week 5 turned a `terraform apply` into a real public-facing app on DigitalOcean — droplet, managed Postgres, domain, TLS — for about $6 of prorated cost. Week 6 is where you finally stop typing `terraform apply` by hand.

This week we focus on **two ideas that change how infrastructure feels to operate**: *immutable infrastructure* (you never SSH into a server to "fix it" — you rebuild the image and replace the server) and *GitOps* (the cluster pulls its desired state from a git repo on a clock, and any divergence is either reconciled automatically or paged loudly). The two ideas are siblings, not synonyms. Immutable infrastructure is about what an artifact looks like (a frozen image, never patched in place). GitOps is about how an artifact gets into production (a controller, not an engineer, executes the rollout). You will see both this week, and you will see why every production system worth running uses both.

We use **Packer 1.11+** to bake a droplet image once and reuse it on every boot; **Argo CD 2.13+** and **Flux 2.4+** to demonstrate the pull model on a `kind` cluster (because the real droplet from Week 5 is not Kubernetes — that comes in Week 7); and a small **config repo + controller** pattern that mirrors what Argo / Flux do, but adapted for the non-Kubernetes droplet you provisioned last week. By Sunday, a `git push` to your `config-repo` will trigger a reconciliation loop that pulls the new desired image tag, drains the old droplet, brings up a new one from the Packer-baked image, and updates DNS — without you running a single `terraform apply` on your laptop.

Week 5 gave you `terraform apply` for a real app. Week 6 gives you `git push` for a real app, and a controller that does the rest. That is the difference between "I can deploy" and "the system can deploy itself when the only input is a commit on `main`."

---

## Learning objectives

By the end of this week, you will be able to:

- **Explain** the difference between *mutable* and *immutable* infrastructure, name three operational problems mutable servers cause (configuration drift, snowflake hosts, irreproducible incidents), and describe the rebuild-vs-patch decision rule that immutable infrastructure forces on every operations team.
- **Build** a custom droplet image with Packer: an HCL `*.pkr.hcl` configuration that starts from an Ubuntu 24.04 base, installs Docker, pre-pulls your Week 4 image, and registers the resulting snapshot in your DigitalOcean account. `packer build` returns a snapshot ID that Terraform consumes; `packer fmt`, `packer validate`, and `packer inspect` are part of your CI before anything is built.
- **Distinguish** the *push* model of deployments (CI runs `kubectl apply` or `ssh ... && docker pull`) from the *pull* model (a controller running inside the target environment polls a git repo and reconciles), and name the four operational properties the pull model gives you that the push model does not (least-privilege CI, drift correction, audit trail in git, disaster recovery from the repo).
- **Operate** Argo CD 2.13+ on a local `kind` cluster: install the controller, point it at a config repo, define an `Application` CR, watch the sync happen, deliberately drift the cluster, watch Argo reconcile, and read the events that explain what happened.
- **Operate** Flux 2.4+ on the same `kind` cluster: install the controllers, bootstrap a `GitRepository` source, define a `Kustomization`, watch the same sync happen with a slightly different shape, and explain the four-controller decomposition that Flux uses (`source-controller`, `kustomize-controller`, `helm-controller`, `notification-controller`).
- **Defend** the choice between Argo CD and Flux for a given team profile (CD-product feel and UI vs CNCF-native composability), and the choice between the *app of apps* pattern in Argo and the *flux bootstrap* pattern in Flux for managing more than one application.
- **Apply** GitOps principles to non-Kubernetes infrastructure: the Week 5 droplet does not run Kubernetes, so the mini-project wires together a config repo, a tiny reconciler running on the droplet itself, and a `terraform apply` orchestrated by `tofu` or `tflocal` against the same Spaces backend.
- **Diagnose** the three common GitOps failures: a stale source (the controller cannot pull from the repo), a stuck reconciliation (the apply hangs in the cluster, neither succeeding nor failing), and a divergent state (the cluster differs from the repo and the controller cannot reconcile).
- **Build** a one-page rollback runbook for a GitOps deployment: how to roll forward when the new commit is broken, how to roll back when forward is not safe, and the three signals that distinguish the two.

---

## Prerequisites

This week assumes you have completed **Weeks 1, 2, 3, 4, and 5 of C15** and have all five mini-projects either still running or destroyed cleanly. Specifically:

- You have a working `terraform apply` from Week 5 that brings up a droplet + managed Postgres + domain + TLS on DigitalOcean. If you destroyed it on Sunday, bring it back up before Monday — Week 6 builds on it.
- You have a Spaces bucket from Exercise 3 of Week 5 holding remote state for the mini-project. We re-use it this week.
- You can build a multi-stage Dockerfile, push the image to GHCR with a tag, and the image is publicly readable (or you have a fine-grained PAT for private images).
- You have `kind` installed (`brew install kind` / `apt install kind`), `kubectl` installed, and `kind create cluster` works without an error on your laptop.
- You have Packer installed (`brew install packer` reports 1.11+).
- You can SSH into a Linux droplet, read `/var/log`, and check `systemctl status app.service` without panicking.

We use **Packer 1.11+** (the HCL2 syntax has been the default for years; the JSON syntax is deprecated and removed in 2.0), **Argo CD 2.13+** (the 2.x line is stable; the 2.13 release lands the rewritten UI and the new `ApplicationSet` shape), **Flux 2.4+** (the 2.x line uses the four-controller decomposition and is the only Flux you should learn in 2026 — Flux v1 has been EOL since 2022), and **`kind` 0.24+** for the local Kubernetes cluster.

If you are coming back to this week after a break, the two things that recently changed and matter this week: (a) Argo CD 2.10+ made *server-side apply* the default, which fixes a class of "I deleted a field manually and Argo will not put it back" bugs; (b) Flux 2.4 added native support for OCI artifacts as a `Source` kind, so you can host your manifests in GHCR alongside your application images.

---

## Topics covered

- Mutable vs immutable infrastructure: what each gives you, what each costs, the rebuild-vs-patch decision rule, and why "pets vs cattle" is the wrong framing in 2026.
- Packer: the HCL2 configuration shape, `source` blocks (DigitalOcean, AWS, GCP, QEMU), `build` blocks, provisioners (`shell`, `file`, `ansible`), post-processors, the `packer init` discipline, and how Packer-built images integrate with Terraform.
- The push vs pull model of deployments: where the trust boundary lives, who has credentials to the target environment, what the audit trail looks like, what disaster recovery looks like.
- GitOps as a pattern: the four principles (declarative description, versioned and immutable, pulled automatically, continuously reconciled) and the two reference implementations (Argo CD, Flux).
- Argo CD: the `Application` and `ApplicationSet` CRDs, the `argocd` CLI, the UI, the *app of apps* pattern, the sync waves and sync hooks, the project / role / RBAC model, the diff between server-side apply and client-side apply.
- Flux: the four controllers (`source-controller`, `kustomize-controller`, `helm-controller`, `notification-controller`), the `GitRepository`, `Kustomization`, `HelmRelease`, and `OCIRepository` CRDs, the `flux bootstrap` discipline, the Flux operator and notifications via `Alert` and `Provider`.
- The config repo pattern: the standard layout (`apps/`, `infrastructure/`, `clusters/`), the difference between *config* repos and *application source* repos, the per-environment overlay (`overlays/dev/`, `overlays/staging/`, `overlays/prod/`).
- Image automation in GitOps: Argo CD Image Updater, Flux Image Reflector + Image Automation, and the trade-off between automatic image bumps and the discipline of a human-reviewed PR.
- Sealed secrets and SOPS in a GitOps repo: the two patterns for "I want secrets in git" — encrypted-at-rest with `sealed-secrets` or `sops`, and the workflow for rotating a key without breaking reconciliation.
- Disaster recovery from a GitOps repo: rebuilding a cluster from the config repo in under thirty minutes, and the three things the repo must contain to make that possible (cluster bootstrap, infrastructure, applications).
- GitOps anti-patterns: imperative `kubectl apply` in a GitOps cluster, secrets in plaintext, "one giant `Application` for everything", the long-lived feature branch that never merges, the `prune: false` controller that accumulates orphan resources forever.

---

## Weekly schedule

The schedule below adds up to approximately **36 hours**. As always, total is what matters.

| Day       | Focus                                                        | Lectures | Exercises | Challenges | Quiz/Read | Homework | Mini-Project | Self-Study | Daily Total |
|-----------|--------------------------------------------------------------|---------:|----------:|-----------:|----------:|---------:|-------------:|-----------:|------------:|
| Monday    | Immutable infrastructure and Packer (Lecture 1)              |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Tuesday   | Argo CD and Flux: the pull model (Lecture 2)                 |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Wednesday | Argo CD on `kind` (Exercise 2)                               |    1h    |    2h     |     1h     |    0.5h   |   1h     |     1h       |    0.5h    |     7h      |
| Thursday  | Flux on `kind`; the comparison (Exercise 3)                  |    1h    |    1h     |     1h     |    0.5h   |   1h     |     2h       |    0.5h    |     7h      |
| Friday    | Mini-project — GitOps loop on the Week 5 droplet             |    0h    |    0h     |     1h     |    0.5h   |   1h     |     3h       |    0.5h    |     6h      |
| Saturday  | Challenge — "rebuild vs patch" runbook                       |    0h    |    0h     |     1h     |    0h     |   1h     |     1h       |    0h      |     3h      |
| Sunday    | Quiz, write the runbook, reconcile the bill                  |    0h    |    0h     |     0h     |    0.5h   |   0h     |     0h       |    0h      |     0.5h    |
| **Total** |                                                              | **6h**   | **7h**    | **4h**     | **3h**    | **6h**   | **7h**       | **2.5h**   | **35.5h**   |

---

## How to navigate this week

| File | What's inside |
|------|---------------|
| [README.md](./README.md) | This overview (you are here) |
| [resources.md](./resources.md) | Curated readings: Argo CD docs, Flux docs, Packer docs, GitOps Working Group |
| [lecture-notes/01-immutable-infrastructure-and-packer.md](./lecture-notes/01-immutable-infrastructure-and-packer.md) | The case for immutable infrastructure, the Packer file shape, the rebuild-vs-patch rule |
| [lecture-notes/02-argocd-and-flux-the-pull-model.md](./lecture-notes/02-argocd-and-flux-the-pull-model.md) | GitOps principles, Argo CD and Flux side by side, the config repo pattern |
| [exercises/README.md](./exercises/README.md) | Index of hands-on drills |
| [exercises/exercise-01-packer-image.md](./exercises/exercise-01-packer-image.md) | Bake a DigitalOcean droplet image with Packer that pre-pulls your Week 4 image |
| [exercises/exercise-02-argocd-setup.md](./exercises/exercise-02-argocd-setup.md) | Install Argo CD on a `kind` cluster and reconcile a small app from a config repo |
| [exercises/exercise-03-flux-vs-argo.md](./exercises/exercise-03-flux-vs-argo.md) | Install Flux on a parallel `kind` cluster; reconcile the same app; write up the comparison |
| [challenges/README.md](./challenges/README.md) | Index of weekly challenges |
| [challenges/challenge-01-rebuild-vs-patch.md](./challenges/challenge-01-rebuild-vs-patch.md) | A decision-rule runbook: when to rebuild, when to patch, when to do both |
| [quiz.md](./quiz.md) | 10 multiple-choice questions |
| [homework.md](./homework.md) | Six practice problems |
| [mini-project/README.md](./mini-project/README.md) | Convert the Week 5 Terraform setup to GitOps: changes to a config repo trigger automatic reconciliation |

---

## A note on cost

Week 6 keeps the Week 5 infrastructure running for the mini-project, which is the prorated remainder of the **$12 / two-week** total. The new spending this week is small:

```
┌─────────────────────────────────────────────────────┐
│  COST PANEL — Week 6 incremental spend              │
│                                                     │
│  Week 5 droplet + Postgres + Spaces      $6 / wk    │
│    (carried over from W5; no new cost)              │
│  Packer build droplets (transient,                  │
│    destroyed at end of each build)       ~$0.10     │
│  Custom snapshot storage in DO           $0.05 / GB │
│    (typical baked image: 4 GB → $0.20/mo)           │
│  kind cluster (local, no cloud cost)     $0.00      │
│                                                     │
│  Subtotal new spend this week:           ~$1.00     │
└─────────────────────────────────────────────────────┘
```

The two new line items are *Packer build droplets* (a small droplet that Packer brings up for the duration of each build, then destroys; you pay for the minutes it ran) and *custom snapshot storage* (DigitalOcean charges $0.05 per GB per month for snapshots; a baked image with Docker pre-installed is around 4 GB).

**Destroy at the end of the week if you are not continuing to Week 7.** The reminder is your friend; the bill that arrives because you forgot is not. The mini-project includes the destroy commands and a `doctl` audit at the end.

---

## Stretch goals

If you finish early and want to push further:

- Read the entire **OpenGitOps principles** document at <https://opengitops.dev/>. The four principles are short; the discussion of *why* each principle is the way it is takes about thirty minutes to read carefully. After this, you can articulate the GitOps thesis without saying the word "GitOps."
- Run **Argo CD against your real Week 5 droplet** without Kubernetes by using the `argocd-image-updater` shape pointed at a small reconciler script you write yourself (about 80 lines of Python or Go). This is what the mini-project does at a sketch level; the stretch is to harden it.
- Read the source of the **Flux source-controller** at <https://github.com/fluxcd/source-controller> — start with `internal/controller/gitrepository_controller.go`. You will see exactly what a reconciliation loop looks like in real Go code: a `Reconcile()` method, a `requeue` decision, a status update, an event. The kubebuilder pattern is the operator-writing pattern; reading one is worth ten tutorials on writing them.
- Install **`argo-rollouts`** on the same `kind` cluster after Exercise 2. Define a `Rollout` for the app you reconciled. Trigger a canary. Read the rollout controller's events. The progressive-delivery layer on top of GitOps is the thing teams reach for once the basic loop is working.
- Read the **2023 GitHub deploy-key blast-radius write-up** at <https://github.com/blog/> (search "deploy key") and decide whether your config repo should have a deploy key, a fine-grained PAT, or a GitHub App. The answer is "a GitHub App for the team, a deploy key for the lab"; defend that in your homework.

---

## Up next

Continue to **Week 7 — Kubernetes from First Principles** once you have shipped your Week 6 mini-project. Week 7 takes the `kind` cluster you have been running this week, picks it apart (pods, deployments, services, ingress, the control plane), and gives you the mental model that the Argo CD `Application` you reconciled against today actually depends on. Week 8 then moves you off `kind` to a managed cluster (DigitalOcean Kubernetes) and Week 9 layers Helm and operators on top.

A note on the order: we put GitOps before Kubernetes deliberately. The GitOps pattern is older than Kubernetes (the term `GitOps` is from 2017; Weaveworks coined it for the Kubernetes context, but the pattern — *git is the source of truth, a controller reconciles* — is what Puppet did in 2005 and what `chef-client` did in 2009). If you only ever see GitOps inside Kubernetes, you mistake the pattern for the implementation. By putting Packer and the droplet-side GitOps loop before Kubernetes, we make the pattern legible on its own.

---

*If you find errors in this material, please open an issue or send a PR. Future learners will thank you.*
