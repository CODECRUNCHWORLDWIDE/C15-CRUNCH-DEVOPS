# Week 4 Homework

Six problems, ~6 hours total. Commit each in your week-04 repo.

---

## Problem 1 — Annotate a real workflow (45 min)

Pick a real `.github/workflows/*.yml` from one of these open-source repos:

- **`kubernetes/kubernetes`** — any of the test workflows: <https://github.com/kubernetes/kubernetes/tree/master/.github/workflows>
- **`vercel/next.js`** — a frontend workflow with caching and matrix: <https://github.com/vercel/next.js/tree/canary/.github/workflows>
- **`hashicorp/terraform`** — the digest-pinning discipline is exemplary: <https://github.com/hashicorp/terraform/tree/main/.github/workflows>
- **`docker/build-push-action`** itself — the action's own CI: <https://github.com/docker/build-push-action/tree/master/.github/workflows>

Copy the file into `notes/annotated.workflow.yml`. For **every job**, **every `uses:` line**, and the top-level `permissions:`, `concurrency:`, and `on:` blocks, add a YAML comment that explains:

1. *What* this block does in one phrase.
2. *Why* it is structured this way (cache strategy, permission scope, concurrency choice).
3. *What would break* if you removed it.

**Acceptance.** `notes/annotated.workflow.yml` contains the file with at least 30 comment lines distributed across the top-level blocks and the jobs.

---

## Problem 2 — Permissions audit on three of your own repos (45 min)

Pick three of your own GitHub repos that have at least one workflow. (Use your Week 1, 2, 3 repos if needed; the C16 repos work too.) For each repo, run:

```bash
gh api repos/<owner>/<repo>/actions/permissions/workflow
```

Then read each workflow file and answer:

1. Does the workflow declare `permissions:` at the top? If not, what default is it inheriting?
2. Does any job declare `permissions:` with `write` scope? If so, which scope, and is the use justified?
3. Are there any jobs with implicit `write-all` that should be scoped down?
4. Are any `uses:` references pinned by SHA?

**Acceptance.** `notes/permissions-audit.md` contains:

- A table per repo: `workflow | top-level permissions | job-level escalations | sha-pinned? | suggested fixes`.
- A one-paragraph summary identifying the **single highest-impact change** across the three repos.

---

## Problem 3 — Build the slow pipeline, then the fast one (90 min)

Take your Exercise 1 starter repo. Write a second workflow `notes/slow.yml` that deliberately does **everything wrong** from a performance perspective:

- No caching.
- `python -m pip install --no-binary=:all:` (forces compile from source).
- The entire pipeline in one job, sequential.
- No `concurrency:` block.
- A 3-Python × 2-OS matrix even though the code only needs Linux + 3.13.
- `fail-fast: false`.
- An `npm install` step even though there is no Node code (just to feel the cost).

Run it. Record the wall-clock time and the total runner-minutes (the run UI shows the per-job timing; sum it).

Then write `notes/fast.yml` that is the optimal version:

- `cache: pip` shortcut.
- Three jobs (`lint`, `test`, `build`) with `needs:` ordering.
- One Python version on Linux.
- `concurrency:` cancelling earlier runs.
- BuildKit GHA cache on the `build` job.

Run it. Record the same numbers.

**Acceptance.** `notes/before-after.md` contains:

- The two workflow files (or links to them).
- A table: `metric | slow | fast | improvement`.
- A one-paragraph reflection on which optimization moved the needle most.

Target improvement: at least **5x** wall-clock improvement on a warm cache.

---

## Problem 4 — The composite-action vs reusable-workflow decision (60 min)

You have three Python repos in the C15 track (Week 1, 2, 3 mini-projects). Each has a `ci.yml` that runs roughly the same `lint + test + build` shape. You decide to DRY this up.

For each of the following pieces of shared logic, decide: **composite action**, **reusable workflow**, or **leave inline**?

1. The three-step "checkout, set up Python, install dev requirements" preamble that every job starts with.
2. The full `lint` job: checkout, setup, install, ruff check, ruff format check.
3. The full `lint + test + build` pipeline (multiple jobs with `needs:` between them).
4. A single step that posts a Slack message on failure.
5. A two-step "log in to GHCR, set up Buildx" preamble used by every image-pushing job.
6. The 12-step release pipeline (checkout, log in, set up qemu, set up buildx, meta, build-push, attest, gh-release).

For each, write one sentence justifying the choice.

**Acceptance.** `notes/reuse-decisions.md` contains the six decisions with one-sentence rationales.

(Reference answers, for self-grading after you commit:
1. Composite action — a few steps used inside many jobs.
2. Composite action — still steps, still inside one job.
3. Reusable workflow — multi-job DAG cannot live in a composite action.
4. Composite action.
5. Composite action.
6. Reusable workflow.)

---

## Problem 5 — OIDC into a sandbox cloud (90 min)

Set up OIDC federation from a GitHub Actions workflow into **one** of: AWS, Azure, or GCP. Use your free tier / trial.

The minimum acceptance bar:

1. In the cloud account: a single role (AWS IAM role / Azure App Registration / GCP service account) with a trust policy that allows only one specific workflow on one specific branch in your repo to assume it.
2. In the repo: a workflow file with `permissions: id-token: write` and the appropriate `configure-*-credentials` action.
3. A successful run that prints the assumed identity (`aws sts get-caller-identity` / `az account show` / `gcloud auth list`).
4. **Zero** long-lived cloud credentials in repo secrets. (`gh secret list` shows no `AWS_*` / `AZURE_*` / `GCP_*` keys.)

**Acceptance.** `notes/oidc.md` contains:

- The cloud trust-policy document (with the account ID redacted).
- The workflow file.
- The output of the identity-check step (redact the account ID).
- A two-sentence note on what the trust policy's `sub` claim restricts access to.

---

## Problem 6 — A hostile workflow (60 min)

A teammate sent you the following workflow. It works on their personal repo. List **every** anti-pattern it contains, then write a fixed version.

```yaml
name: ci
on: pull_request_target

permissions: write-all

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@main
        with:
          ref: ${{ github.event.pull_request.head.sha }}

      - run: |
          echo "$DEPLOY_TOKEN" > /tmp/token
          curl -sSL https://example.com/install.sh | bash
          npm install
        env:
          DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}

      - uses: docker/login-action@v1
        with:
          username: ${{ secrets.DOCKERHUB_USER }}
          password: ${{ secrets.DOCKERHUB_PASS }}

      - run: docker build -t myorg/app:latest .
      - run: docker push myorg/app:latest
```

**Acceptance.** `notes/hostile.md` contains:

- A numbered list of at least **10 anti-patterns** in this workflow, each with one sentence of explanation.
- A fixed workflow that addresses every one.
- A one-paragraph note identifying the **two anti-patterns most likely to cause an actual security incident** (vs. those that are merely smells).

---

## Time budget

| Problem | Time |
|--------:|-----:|
| 1 | 45 min |
| 2 | 45 min |
| 3 | 90 min |
| 4 | 60 min |
| 5 | 90 min |
| 6 | 60 min |
| **Total** | **~6 h 30 min** |

---

## Why this homework looks like this

Problems 1–2 drill the **reading** skill — recognizing what a real workflow says, what trade-offs it makes, and what one change would harden it most. You will review more workflows than you write in your career; reading them is the skill that scales.

Problems 3–4 drill the **performance and reuse** skills — the difference between "the pipeline works" and "the pipeline costs less than $5/day." Most teams' workflows are slow because nobody ever sat down with a timing waterfall. You will.

Problems 5–6 drill the **security** skills — OIDC instead of long-lived secrets, and the reflex to refuse a hostile `pull_request_target` workflow before it ships. The 2024–2025 wave of CI supply-chain incidents was all variations on one or both of these failures.

A junior engineer can write a `ci.yml`. A senior one can read someone else's `ci.yml`, name the four things wrong with it in two minutes, and fix the most important one in five — without breaking the team's ability to merge. This homework is the next rep of that second skill.

When done, push your week-04 repo and finish the [mini-project](./mini-project/README.md).
