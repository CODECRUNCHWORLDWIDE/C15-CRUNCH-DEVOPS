# Week 4 — GitHub Actions Beyond Hello-World

> *A green check on the latest commit is the cheapest form of trust we have. Earn it on every push, or stop putting it in the README.*

Welcome to Week 4 of **C15 · Crunch DevOps**. Week 1 told you what a container is. Week 2 made you build one well. Week 3 made you wire several of them into a stack that comes up with one command. Week 4 is where that stack stops needing your laptop — where every push runs the same lint, the same tests, the same image build, on a clean Ubuntu runner you do not own, and where a merge to `main` ships an image to a registry without anyone typing `docker push`.

We focus this week on **GitHub Actions** the way you will use it on a real team. Not the "hello-world.yml" tutorial that runs `echo` and tells you CI is easy — but the actual machine you will live inside for the rest of your career: triggers, jobs, matrices, caches, reusable workflows, OIDC into a cloud, registry pushes, release tags, and the rules of taste that separate a 90-second pipeline from a 14-minute one. By Sunday you will have a CI/CD pipeline for the Week 3 stack that runs lint and matrix tests on every PR, builds and pushes a multi-arch image to GHCR on merge, and cuts a release on a version tag — all from one `.github/workflows/` directory, all green, all reproducible.

Week 3's mini-project gave you a one-command local environment. Week 4's mini-project gives you a **one-merge-to-`main`** path from source to a tagged image in a public registry, signed by the runner, traceable by SHA. That is the difference between "we have CI" and "we have a delivery pipeline."

---

## Learning objectives

By the end of this week, you will be able to:

- **Read** any `.github/workflows/*.yml` file and explain, line by line, the trigger, the jobs, the matrix, the runner, every `uses:` reference (action + version), every `with:` input, and every `secrets:`/`permissions:` declaration — and predict what would change in behavior if you removed any one of them.
- **Write** a multi-job workflow for a real repo that lints, tests across a `{Python} x {3.11, 3.12, 3.13}` matrix, builds a Docker image with BuildKit cache, and uploads the image as an artifact — under five minutes wall-clock on a cold cache and under ninety seconds on a warm one.
- **Distinguish** the four GitHub Actions trigger families (`push`, `pull_request`, `workflow_dispatch`, `workflow_call`) and the three job-level dependency primitives (`needs:`, `if:`, `concurrency:`) without looking them up.
- **Apply** the principle of least privilege to every workflow: top-level `permissions: contents: read`, scoped up only on the jobs that need it (`packages: write` for GHCR, `id-token: write` for OIDC), and never the default `write-all`.
- **Author** a reusable workflow (`workflow_call`) plus a composite action, and consume both from a second workflow with `uses: ./.github/workflows/...` and `uses: ./.github/actions/...` — the two reuse primitives every team eventually needs and that most repos get wrong.
- **Configure** OIDC federation from GitHub Actions into AWS (or Azure, or GCP) with no long-lived cloud credentials in repo secrets — the modern, correct shape of "CI deploys to cloud."
- **Diagnose** a flaky or slow pipeline: read the Actions UI timing breakdown, identify the longest job, the longest step within it, the cache-hit ratio, and the action that needs replacing.
- **Defend** the choice of self-hosted vs GitHub-hosted runners, of `act` vs `nektos/act` for local debugging, of `pull_request` vs `pull_request_target`, and of a monolithic vs decomposed workflow file for a given project.

---

## Prerequisites

This week assumes you have completed **Weeks 1, 2, and 3 of C15** and pushed all three mini-projects to public GitHub repos. Specifically:

- You have a GitHub account, a personal `gh` CLI install (`brew install gh` / `apt install gh`), and `gh auth status` returns `Logged in`.
- You can build a multi-stage Dockerfile and bring up a `compose.yaml` stack locally without referring to last week's notes.
- You understand semantic versioning well enough to know why `v1`, `v1.2`, and `v1.2.3` tags coexist on actions like `actions/checkout`.
- You have at least one repo of your own with a `Dockerfile` and a test suite — Week 3's mini-project is the canonical choice. If it is not pushed yet, push it now.

We use the modern **GitHub-hosted Ubuntu 24.04 runners** (`ubuntu-24.04`) and the **GitHub Actions schema as of 2026**. The two things that recently changed and matter this week: (a) **`GITHUB_TOKEN` permissions default to read-only** for new repos created after early 2023; (b) **OIDC** is now the default-recommended way to authenticate from Actions to any cloud — long-lived `AWS_ACCESS_KEY_ID` in repo secrets is a smell, not a pattern.

---

## Topics covered

- The Actions execution model: workflow → jobs → steps. Where each level runs, what gets a fresh VM, and what does not.
- Triggers: `push`, `pull_request`, `pull_request_target`, `workflow_dispatch`, `workflow_call`, `schedule`, and the `release` event. When to reach for each.
- Runners: GitHub-hosted (`ubuntu-24.04`, `windows-2022`, `macos-14`), self-hosted, and the "large runners" tier. The cost/throughput tradeoff.
- The `GITHUB_TOKEN` and `permissions:` — what the token can do by default, how to lock it down, and how to scope it up by job.
- Matrix builds: scalar, multi-dim, `include:`, `exclude:`, `fail-fast`, `max-parallel`. The cost-per-cell math.
- Caching: `actions/cache@v4`, the keying strategy that actually works, BuildKit's `--cache-from=gha`, and the cache-eviction policy you do not control.
- Marketplace actions: the `uses: owner/repo@vN.N.N` syntax, the difference between major-tag and digest pinning, and the `dependabot` config that keeps them current.
- Reusable workflows (`workflow_call`) and composite actions: the two primitives for DRY, what each does well, what each does badly.
- Secrets and variables: repo / environment / organization scope, the deploy-environment gate (manual approvals), and the rules for what should be a `secret` vs a `var`.
- OIDC federation: the trust chain (GitHub → cloud IdP → cloud IAM role), the `id-token: write` permission, and the `aws-actions/configure-aws-credentials@v4` shape that ships in real production.
- Docker builds in CI: `docker/setup-buildx-action`, `docker/build-push-action`, multi-arch with `linux/amd64,linux/arm64`, GHCR pushes, image attestation.
- Concurrency: `concurrency: { group, cancel-in-progress }` — the two-line idiom that prevents a queue of doomed builds.
- The Actions UI: the timing waterfall, the `Re-run failed jobs` button, the annotated log lines, and the `Download log archive` for offline forensics.
- CI anti-patterns: `pull_request_target` with `checkout` of the PR branch (the script-kiddie's RCE), unpinned `@main` action references, secrets in workflow logs, "if it fails, re-run" culture.

---

## Weekly schedule

The schedule below adds up to approximately **36 hours**. As always, total is what matters.

| Day       | Focus                                                       | Lectures | Exercises | Challenges | Quiz/Read | Homework | Mini-Project | Self-Study | Daily Total |
|-----------|-------------------------------------------------------------|---------:|----------:|-----------:|----------:|---------:|-------------:|-----------:|------------:|
| Monday    | Workflow / job / matrix / cache (Lecture 1)                 |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Tuesday   | Reusable workflows, deploy on merge (Lecture 2)             |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Wednesday | Matrix builds in anger (Exercise 2)                         |    1h    |    2h     |     1h     |    0.5h   |   1h     |     1h       |    0.5h    |     7h      |
| Thursday  | Deploy on merge, OIDC, GHCR (Exercise 3)                    |    1h    |    1h     |     1h     |    0.5h   |   1h     |     2h       |    0.5h    |     7h      |
| Friday    | Mini-project — full pipeline for Week 3 stack               |    0h    |    0h     |     1h     |    0.5h   |   1h     |     3h       |    0.5h    |     6h      |
| Saturday  | Challenge — build and push multi-arch image to GHCR         |    0h    |    0h     |     1h     |    0h     |   1h     |     1h       |    0h      |     3h      |
| Sunday    | Quiz, write the README, retro                               |    0h    |    0h     |     0h     |    0.5h   |   0h     |     0h       |    0h      |     0.5h    |
| **Total** |                                                             | **6h**   | **7h**    | **4h**     | **3h**    | **6h**   | **7h**       | **2.5h**   | **35.5h**   |

---

## How to navigate this week

| File | What's inside |
|------|---------------|
| [README.md](./README.md) | This overview (you are here) |
| [resources.md](./resources.md) | Curated readings: GitHub Actions docs, OIDC patterns, free books |
| [lecture-notes/01-workflows-jobs-matrix-cache.md](./lecture-notes/01-workflows-jobs-matrix-cache.md) | The Actions execution model, triggers, jobs, matrices, caching |
| [lecture-notes/02-reusable-workflows-and-deploy-on-merge.md](./lecture-notes/02-reusable-workflows-and-deploy-on-merge.md) | Reusable workflows, composite actions, OIDC, GHCR pushes |
| [exercises/README.md](./exercises/README.md) | Index of hands-on drills |
| [exercises/exercise-01-first-real-pipeline.md](./exercises/exercise-01-first-real-pipeline.md) | Lint + test + cache for a real Python repo |
| [exercises/exercise-02-matrix-builds.md](./exercises/exercise-02-matrix-builds.md) | A 3-Python x 2-OS test matrix with include/exclude |
| [exercises/exercise-03-deploy-on-merge.md](./exercises/exercise-03-deploy-on-merge.md) | Build and push to GHCR on merge to `main`, tag a release |
| [challenges/README.md](./challenges/README.md) | Index of weekly challenges |
| [challenges/challenge-01-build-and-push-to-ghcr.md](./challenges/challenge-01-build-and-push-to-ghcr.md) | Multi-arch image to GHCR with cache and attestation |
| [quiz.md](./quiz.md) | 10 multiple-choice questions |
| [homework.md](./homework.md) | Six practice problems |
| [mini-project/README.md](./mini-project/README.md) | CI pipeline for the Week 3 stack: lint → matrix test → build → push → release |

---

## Stretch goals

If you finish early and want to push further:

- Read the entire **GitHub Actions workflow syntax** reference end to end at <https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions>. It is shorter than it looks, and once you have read it you stop guessing what `if:` accepts.
- Rewrite one of your existing workflows to use **OIDC** into a sandbox AWS account (free tier). Delete every long-lived `AWS_ACCESS_KEY_ID` secret from the repo. Confirm the workflow still deploys.
- Read the source of `actions/checkout` at <https://github.com/actions/checkout> — start with `src/git-source-provider.ts`. You will see exactly what `fetch-depth: 0` costs you and why `persist-credentials: false` matters on `pull_request_target`.
- Install **`act`** (<https://github.com/nektos/act>) and run one of your workflows locally before pushing. Note the three things `act` does not emulate (the GitHub-hosted runner image flavor, the OIDC issuer, the GHCR token) and design around them.
- Read the post-mortem of the **2024 PyPI compromise that started with a typosquatted action** at <https://blog.pypi.org/posts/2024-07-12-incident-report-supply-chain/>. The lesson is the same as in every other supply-chain incident: pin by digest, scope your `permissions:`, review your `uses:` line as carefully as a license header.

---

## Up next

Continue to **Week 5 — Kubernetes Without the Helm Chart Yet** once you have shipped your Week 4 mini-project. Week 5 takes the image your CI pipeline now pushes to GHCR every merge, and runs it on a real Kubernetes cluster — first `kind`, then a managed one — with raw manifests and a clear-eyed view of what a Deployment actually is before any chart wraps it.

---

*If you find errors in this material, please open an issue or send a PR. Future learners will thank you.*
