# Lecture 1 — Workflows, Jobs, Matrices, and the Cache

> **Outcome:** You can read any `.github/workflows/*.yml` file in a real repo, name every top-level key, every trigger, every job-level field worth knowing, and predict what would change if any one of them were removed. You can write a multi-job workflow that lints, runs a test matrix across multiple Python versions, caches dependencies, and finishes a cold run in under five minutes and a warm one in under ninety seconds.

A GitHub Actions workflow is a **declaration of a pipeline**. It says: *when this event happens on this repo, run these jobs on these runners with these permissions; cache what is worth caching; fail fast where it makes sense; and never expose more privilege than the job needs.* Actions is not magic. Every key in the file maps to a deterministic API call against the GitHub Actions service; every value is either a literal, a context expression (`${{ ... }}`), or a structured sub-block. This lecture walks through the file shape you will read and write in the next nine weeks of the course, in roughly the order you will write the keys in a real file.

We use the **GitHub-hosted Ubuntu 24.04 runner** (`ubuntu-24.04`) and the **GitHub Actions workflow schema as of 2026**. Two recent changes matter all week: (a) the `GITHUB_TOKEN` defaults to **read-only** for repos created after early 2023, which is correct; (b) **OIDC** has replaced long-lived cloud credentials in every documented example. If you see `AWS_ACCESS_KEY_ID` in a 2021 tutorial, mentally replace it with the `id-token: write` permission and a `configure-aws-credentials@v4` step — Section 14 of Lecture 2 walks through this.

---

## 1. The shortest correct workflow

Before any of the keys, here is the smallest `.github/workflows/ci.yml` that actually does something useful:

```yaml
name: ci
on: push

jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - run: echo "hello from $GITHUB_SHA"
```

Six keys. It will run on every push, on every branch, for every commit. It will check out the repo and print a string. It is also wrong in about five different ways — no `permissions:`, no version on the runner's OS that you control, the action is pinned by major tag instead of digest, no `concurrency:`, no `if:` guard — every one of which we will fix over the next 400 lines. But it is the right starting point: every key you add from here is an **explicit choice** to make the pipeline faster, safer, more observable, or easier to operate.

Note what is *not* in that file: no `env:` block, no `permissions:`, no `concurrency:`. Each one of those is "use the default," and the defaults are reasonable for a personal project. They are *not* reasonable for a public repo with merge access to production, which is what this lecture prepares you to write.

---

## 2. Where this file lives, and what GitHub does with it

A workflow file lives in your repo at `.github/workflows/<anything>.yml`. The filename is free; the directory is not. GitHub Actions watches that directory on every push and `pull_request` event for the default branch and for the branch of the event. Adding a workflow is a Git change — commit, push, done. There is no "register the workflow" step.

A repo may have any number of workflow files. They are independent. Each one is its own state machine. The Actions UI groups runs by workflow name (the `name:` key, falling back to the filename), and the `gh run list` CLI does the same. If you split one big pipeline into three files — `ci.yml`, `release.yml`, `nightly.yml` — you get three rows in the UI, which is usually what you want.

> **Status panel — workflow inventory**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  REPO: codecrunch/crunchwriter                      │
> │                                                     │
> │  Workflows:    3                                    │
> │  - ci.yml       on: pull_request, push to main      │
> │  - release.yml  on: push tags v*                    │
> │  - nightly.yml  on: schedule cron 17 4 * * *        │
> │                                                     │
> │  Last 24h:    52 runs   green: 49   red: 3          │
> │  Cache size:  3.4 GB / 10 GB (34%)                  │
> └─────────────────────────────────────────────────────┘
> ```

---

## 3. The six top-level keys

A workflow has, at most, **six top-level keys you will use regularly**. There are more in the schema (`run-name`, `defaults`, the deprecated `concurrency` at workflow level alias) but six cover 99% of real files:

| Key | What it declares |
|-----|------------------|
| `name` | Human-readable workflow name, shown in the Actions UI |
| `on` | The events that trigger this workflow |
| `permissions` | Default `GITHUB_TOKEN` scopes for every job |
| `env` | Workflow-level environment variables, inherited by all jobs |
| `concurrency` | Concurrency group + cancel-in-progress policy |
| `jobs` | The set of jobs to run. The point of the file. |

The file is YAML, parsed with permissive type coercion. The two YAML footguns to know about now: (a) **`on: push` and `on: { push }` mean different things** — the first is a string, the second a mapping; both are valid, but only the mapping form lets you add filters. (b) **A `true` value inside `on:` is a string** — `on: { release: { types: [published] } }` is fine, `on: { push: true }` is not. When in doubt, `actionlint` will tell you.

---

## 4. `name` — the workflow name in the UI

```yaml
name: ci
```

`name` sets the workflow name shown in the Actions UI and in commit-status checks. If you omit it, GitHub uses the file path (`.github/workflows/ci.yml`). Always set it explicitly; the filename is a path, not a label.

The `run-name:` key (separate from `name:`) lets you set the per-run name dynamically:

```yaml
run-name: "ci for ${{ github.head_ref || github.ref_name }} by @${{ github.actor }}"
```

This makes the Actions UI list runs as `ci for feature/oidc by @jeanstephane` instead of `Update README.md` (the commit message). On any repo with more than three contributors, it pays for itself in five minutes of search.

---

## 5. `on` — the trigger

`on` declares the events that fire this workflow. You will use four families regularly:

### 5.1 `push`

```yaml
on:
  push:
    branches: [main, "release/*"]
    paths-ignore: ["docs/**", "**/*.md"]
    tags: ["v*"]
```

Filters are AND-ed. The above runs on a push to `main` or any `release/*` branch that does **not** touch only docs, plus on any tag matching `v*`. The `paths-ignore:` filter is your single biggest cost-saver on a docs-heavy repo. The `tags:` filter is how you wire a release pipeline (Section 11).

### 5.2 `pull_request`

```yaml
on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened, ready_for_review]
```

Runs on every PR opened against `main`. The default `types:` is `[opened, synchronize, reopened]`, which means a draft-to-ready transition does **not** re-trigger. If you gate "run the slow tests when ready for review," add `ready_for_review` explicitly.

> **Critical safety note.** `pull_request` runs in the context of the *base* repo with the `GITHUB_TOKEN` scoped to **read-only on the head ref**. That is what makes it safe to run untrusted PR code. Its sibling `pull_request_target` runs in the *base* repo's context with the *base* repo's secrets — which is what makes it the most common source of Actions RCE. Lecture 2 Section 13 covers this in detail. For now: if a workflow runs untrusted code from a PR, use `pull_request`, not `pull_request_target`.

### 5.3 `workflow_dispatch`

```yaml
on:
  workflow_dispatch:
    inputs:
      environment:
        description: "Deploy target"
        required: true
        type: choice
        options: [staging, production]
      ref:
        description: "Git ref to deploy"
        required: false
        type: string
        default: ""
```

Adds a "Run workflow" button to the Actions UI and a `gh workflow run ci.yml --field environment=staging` invocation to the CLI. Useful for: manual deploys, on-demand maintenance jobs, anything you want to gate on a human.

### 5.4 `workflow_call` and `schedule`

`workflow_call` makes the workflow callable from another workflow. We cover it in Lecture 2 Section 4 — it is half of "DRY across workflows."

`schedule` takes a cron expression in UTC:

```yaml
on:
  schedule:
    - cron: "17 4 * * *"   # 04:17 UTC every day
```

Use schedules for nightly builds, daily dependency-update PRs, weekly security scans. Two things to know: (a) scheduled workflows run on the **default branch only**; (b) GitHub will silently disable a `schedule:` workflow after **60 days of repo inactivity**. The first time that bit you, you learned to put a `workflow_dispatch:` next to every `schedule:` so you can hand-fire it after vacation.

---

## 6. `permissions` — least privilege, in two lines

```yaml
permissions:
  contents: read
```

The single most important block in your workflow. The `GITHUB_TOKEN` is the auto-provisioned credential every workflow run gets; `permissions:` declares what it is allowed to do. Without it, repos created **before March 2023** default to `write-all`, which means a compromised action can rewrite your branches. Repos created after default to `read`, which is correct.

Always set it at workflow level. Scope it up at job level when needed:

```yaml
permissions:
  contents: read

jobs:
  test:
    # inherits contents: read

  release:
    permissions:
      contents: write     # to push a tag
      packages: write     # to push to GHCR
      id-token: write     # to mint an OIDC token for AWS
```

The complete list of scopes (15 of them, as of 2026) is in the docs at <https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication#permissions-for-the-github_token>. The ones you will set repeatedly: `contents`, `pull-requests`, `issues`, `packages`, `id-token`, `attestations`, `pages`.

> **Rule of thumb.** If you cannot articulate, in one sentence, why a job has `contents: write` instead of `contents: read`, it does not get `contents: write`.

---

## 7. `env` — workflow-level environment variables

```yaml
env:
  PYTHON_VERSION: "3.13"
  COVERAGE_MINIMUM: "85"
```

Workflow-level `env:` is inherited by every job and every step. Useful for the values that should be one-source-of-truth across the file: a Python version, a Node version, a project name, a region.

Job-level `env:` overrides workflow-level for that job. Step-level `env:` overrides both for that step. Step-level `env:` is the right shape for one-off needs like `env: { LOG_LEVEL: DEBUG }` on a debugging step.

What does *not* go in `env:`: secrets. Secrets go in `secrets.<NAME>` via `${{ secrets.NAME }}`, never in plaintext. If you put a secret in `env:` and that variable shows up in a log line, it leaks.

---

## 8. `concurrency` — the two-line queue manager

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

The two lines that turn "every push queues another five-minute run, the queue grows, you wait twelve minutes for the latest" into "every push cancels the previous run, the latest commit is the only one running." On a busy repo this saves you an hour a week and a small fortune in runner minutes.

The `group:` key is a string; you choose the grouping. The two patterns you will see most often:

- `group: ${{ github.workflow }}-${{ github.ref }}` — one run at a time per branch (per workflow). Cancel earlier runs on the same branch.
- `group: deploy-${{ github.event.inputs.environment }}` — one deploy at a time per environment, queued. Set `cancel-in-progress: false` so an in-flight deploy is *not* cancelled — let it finish, then run the next.

If you set `cancel-in-progress: false`, runs queue rather than cancel. That is the correct shape for deploys, where mid-deploy cancellation can leave production half-flipped.

---

## 9. `jobs` — the heart of the file

`jobs` is a mapping whose keys are **job IDs** and whose values are job definitions. The job ID is what `needs:` references; the `name:` inside the job is the human-readable label in the UI.

A job definition has, in practice, about **a dozen fields worth knowing**. The schema defines more — `defaults`, `services`, `container`, `outputs`, `strategy` — but the dozen below cover 90% of real files.

### 9.1 `runs-on` — pick the runner

```yaml
jobs:
  test:
    runs-on: ubuntu-24.04
```

`runs-on` is the runner the job executes on. Pin to a specific version (`ubuntu-24.04`) rather than the floating label (`ubuntu-latest`). The floating label changes every six months — `ubuntu-latest` was `20.04` until late 2022, then `22.04` until late 2024, then `24.04`. Your CI will silently change behavior on the day GitHub rolls the label. Pin.

GitHub-hosted runner options as of 2026:

| Label | Spec | Notes |
|-------|------|-------|
| `ubuntu-24.04` | 4 vCPU, 16 GB RAM, 14 GB SSD | Default Linux choice |
| `ubuntu-22.04` | 4 vCPU, 16 GB RAM, 14 GB SSD | Still supported, transitioning out |
| `windows-2022` | 4 vCPU, 16 GB RAM, 14 GB SSD | For Windows-only build steps |
| `macos-14` | 3 vCPU, 7 GB RAM, 14 GB SSD | Apple Silicon; only OS that builds iOS/Mac binaries |
| `ubuntu-24.04-arm` | 4 vCPU, 16 GB RAM, 14 GB SSD | ARM64 Linux runners (free for public repos as of 2025) |

You can also `runs-on:` a self-hosted runner — `[self-hosted, linux, gpu]` matches on labels. We do not use self-hosted runners this week.

### 9.2 `needs` — order jobs

```yaml
jobs:
  lint:
    runs-on: ubuntu-24.04
    steps: [ ... ]

  test:
    runs-on: ubuntu-24.04
    needs: [lint]
    steps: [ ... ]

  build-image:
    runs-on: ubuntu-24.04
    needs: [lint, test]
    steps: [ ... ]
```

`needs:` is the only way to order jobs. Without it, every job in the file runs in parallel. The right shape for most pipelines is a DAG: a fan-out of fast jobs (`lint`, `unit-test`), a fan-in to the slow ones (`integration-test`, `build-image`), and a single terminal job (`deploy`, `release`).

`needs:` waits for **success** by default. To run a job even when a dependency failed, add `if: always()` or `if: failure()` (Section 9.4).

### 9.3 `strategy.matrix` — fan one job into many

```yaml
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      max-parallel: 6
      matrix:
        python: ["3.11", "3.12", "3.13"]
        os: [ubuntu-24.04, macos-14]
        include:
          - python: "3.13"
            os: ubuntu-24.04
            coverage: true
        exclude:
          - python: "3.11"
            os: macos-14
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python }}" }
      - run: pytest
```

The above runs **five** jobs: `3.11/ubuntu`, `3.12/ubuntu`, `3.13/ubuntu`, `3.12/macos`, `3.13/macos` — the 3×2 product minus the one exclude. The single `include` adds `coverage: true` only on the `3.13/ubuntu` cell.

`fail-fast: true` (the default) cancels the other matrix cells as soon as one fails. Set `false` when you want full diagnostic coverage — which is almost always what you want on a test matrix. `max-parallel: 6` caps concurrency. Useful when each cell hits a rate-limited external service.

> **Cost math, briefly.** A 3×3×2 matrix is 18 jobs. At 5 minutes each on a 4-vCPU runner, that is 90 minutes of compute per push. On a private repo billed at $0.008/min for Linux, that is $0.72 per push. On a 50-PR-per-day team, that is **$18/day** just on this one workflow. Build the matrix that catches the bugs you actually see, not the one that maximizes confidence.

### 9.4 `if` — guard a job (or step)

```yaml
jobs:
  deploy:
    needs: [test, build-image]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-24.04
    steps: [ ... ]
```

`if:` takes a GitHub Actions expression. Common patterns:

- `if: github.ref == 'refs/heads/main'` — only on `main`
- `if: github.event_name == 'pull_request'` — only on PRs
- `if: startsWith(github.ref, 'refs/tags/v')` — only on `v*` tags
- `if: github.actor != 'dependabot[bot]'` — skip dependabot
- `if: success()` (default for steps), `if: failure()`, `if: always()` — control failure semantics
- `if: contains(github.event.head_commit.message, '[ci skip]')` — honor the convention

The full expression language is at <https://docs.github.com/en/actions/reference/context-and-expression-syntax-for-github-actions>. Two footguns: (a) the `${{ }}` braces are *optional* at the top of `if:` but required inside string contexts, so `if: ${{ github.ref == 'refs/heads/main' }}` and `if: github.ref == 'refs/heads/main'` both work but mix them at your peril; (b) the `==` operator is string equality, *not* boolean — `if: github.event.pull_request.draft == false` does what you mean only because `false` is interpreted as `'false'`.

### 9.5 `timeout-minutes`

```yaml
jobs:
  test:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
```

Default is **360** minutes (6 hours). That default is wrong for every reasonable job. Set an explicit `timeout-minutes:` matching the 90th-percentile runtime plus 50%. A flaky test that hangs will otherwise burn an hour of your compute quota before GitHub force-kills the job.

### 9.6 `steps` — the work

```yaml
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip

      - name: Install
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Lint
        run: ruff check .

      - name: Test
        run: pytest -q --cov=app --cov-report=xml

      - name: Upload coverage
        if: matrix.coverage == true
        uses: codecov/codecov-action@v4
```

A step is either a **`uses:` step** (call an action) or a **`run:` step** (run a shell command). The two cannot mix. Each step is a `name:` (optional but always set it), the action or command, optional `with:`, optional `env:`, optional `if:`, optional `id:`.

The `id:` on a step lets later steps reference its outputs via `${{ steps.<id>.outputs.<key> }}`. That is the primitive for "use the tag generated by metadata-action as the image tag in the next step."

---

## 10. `uses:` — calling an action

```yaml
- uses: actions/checkout@v4
```

`uses:` is the action reference. Four shapes:

1. **Marketplace by major tag** — `actions/checkout@v4`. The convention. Major tag floats forward to the latest minor/patch. Most readable.
2. **Marketplace by exact version** — `actions/checkout@v4.2.2`. Reproducible to the minor.
3. **Marketplace by digest** — `actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11`. Bit-for-bit reproducible. **The security-best choice.**
4. **Local action** — `uses: ./.github/actions/setup-python-with-cache`. Calls an action defined in this repo.

The supply-chain-security position is: **pin every action by digest**, then use Dependabot or `ratchet` to keep the digests current. Major-tag pinning means a maintainer who pushes a malicious commit to `v4` can pivot into every workflow that uses them. Digest pinning means you only run what you signed off on.

In this lecture's examples we use major-tag pinning for readability. In the mini-project you will run `ratchet pin` to convert every `@v4` to a `@<sha>` with a comment.

---

## 11. Caching with `actions/cache`

```yaml
- name: Restore pip cache
  id: pip-cache
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

The keying strategy that actually works:

- `key:` is the exact-match key. Include OS + tool + a hash of the dependency manifest. If the manifest changes, the key changes, the cache misses, and the next run installs fresh and writes a new cache entry.
- `restore-keys:` is the fallback chain. If the exact key misses, GitHub matches `restore-keys:` as a prefix and restores the most recent matching entry. The job then installs only what changed. This is what makes a "warm cache" warm.

Three rules:

1. **Hash the lockfile, not the manifest.** `hashFiles('**/poetry.lock')` is reproducible; `hashFiles('**/requirements.txt')` is reproducible only if you pin every transitive. Lockfiles are reproducible. Use them.
2. **The cache is scoped by branch.** A PR's cache cannot fall back to `main`'s cache by default — *except* via `restore-keys:` and the cross-branch fallback rule (cache reads see `main` and the PR's base ref, but not arbitrary branches). On a first push to a new branch you will see one cold build, then warm thereafter.
3. **The cache is 10 GB per repo, evicted LRU.** Cache entries older than 7 days are also evicted. If your cache is hot for two days and cold on Monday, that is why. Either accept it or push a no-op commit on Sunday night.

Many `setup-*` actions have a `cache:` shortcut (`actions/setup-python@v5` with `cache: pip` or `actions/setup-node@v4` with `cache: pnpm`) that wraps `actions/cache@v4` for you. Use the shortcut; it is well-tested and gets the keying right.

> **Status panel — cache report**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  CACHE — actions/cache@v4                           │
> │                                                     │
> │  Job:        test (python 3.13)                     │
> │  Key:        Linux-pip-2d4a8c1f...                  │
> │  Match:      hit (exact)                            │
> │  Bytes:      218 MB restored in 6.2 s               │
> │  Saved time: ~80 s (vs cold install)                │
> └─────────────────────────────────────────────────────┘
> ```

### 11.1 Caching the Docker build

`actions/cache` is the right primitive for pip / npm / cargo. For Docker, the convention is **BuildKit's GHA backend**:

```yaml
- uses: docker/setup-buildx-action@v3
- uses: docker/build-push-action@v6
  with:
    context: .
    push: false
    tags: app:ci-${{ github.sha }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

`type=gha` plugs BuildKit straight into the same Actions cache backend as `actions/cache`, but exposes a layer-aware API. `mode=max` exports every intermediate layer to the cache (slow to write the first time, very fast on every subsequent run). `mode=min` exports only the final layer; use when the build is mostly dynamic.

The first cold build of a serious Python image runs about 90 seconds. With `cache-from=gha,mode=max`, the second run drops to 12 seconds. That difference compounds across every push.

---

## 12. Contexts and expressions, briefly

```yaml
- run: echo "Built ${{ github.repository }} @ ${{ github.sha }}"
- run: echo "Triggered by ${{ github.actor }} on ${{ github.event_name }}"
```

GitHub Actions exposes about a dozen **contexts** — `github`, `env`, `vars`, `secrets`, `inputs`, `needs`, `steps`, `job`, `runner`, `matrix`, `strategy`, `jobs` — interpolated via `${{ context.path }}`.

The five you will use most:

| Context | Shape | Example |
|---------|-------|---------|
| `github` | The event payload + repo metadata | `${{ github.ref }}`, `${{ github.event.pull_request.number }}` |
| `secrets` | Repo / environment / org secrets | `${{ secrets.DEPLOY_TOKEN }}` |
| `vars` | Non-secret variables | `${{ vars.STAGING_URL }}` |
| `matrix` | The current matrix cell's values | `${{ matrix.python }}` |
| `steps` | Outputs from previous steps in this job | `${{ steps.meta.outputs.tags }}` |

Expression functions worth knowing: `contains()`, `startsWith()`, `endsWith()`, `format()`, `fromJSON()`, `toJSON()`, `hashFiles()`, `success()`, `failure()`, `always()`, `cancelled()`.

---

## 13. Job outputs — passing data between jobs

```yaml
jobs:
  decide:
    runs-on: ubuntu-24.04
    outputs:
      changed-app:    ${{ steps.changes.outputs.app }}
      changed-infra:  ${{ steps.changes.outputs.infra }}
    steps:
      - uses: actions/checkout@v4
      - id: changes
        uses: dorny/paths-filter@v3
        with:
          filters: |
            app:    'app/**'
            infra:  'terraform/**'

  test-app:
    needs: [decide]
    if: needs.decide.outputs.changed-app == 'true'
    runs-on: ubuntu-24.04
    steps: [ ... ]
```

Job outputs are the only way to pass data from job A to job B. Each output is a string. You set them from a step's outputs, expose them at the `outputs:` block of the job, and reference them from a downstream job as `needs.<jobid>.outputs.<key>`.

The pattern above is the **monorepo savings idiom**: a fast `decide` job uses `dorny/paths-filter` to compute "did the app change?" and "did infra change?", then conditional `if:` guards on each downstream job skip the ones whose code did not move. On a 10-job pipeline in a monorepo, this often turns 15-minute runs into 2-minute ones.

---

## 14. Step outputs — the same, one scope down

Within a job, steps pass data via outputs:

```yaml
- id: meta
  run: |
    echo "tag=v$(date -u +%Y%m%d)-${GITHUB_SHA::7}" >> "$GITHUB_OUTPUT"

- run: echo "image tag will be ${{ steps.meta.outputs.tag }}"
```

`$GITHUB_OUTPUT` is a magic file path the runner writes step outputs to. Writing `key=value` lines to it makes them available as `${{ steps.<id>.outputs.<key> }}` in later steps.

This replaces the **deprecated** `::set-output::` syntax you may still find in old tutorials. If you see `::set-output name=foo::bar`, that is the 2022 form; it works but is on the deprecation list. Use `$GITHUB_OUTPUT`.

---

## 15. A real-world workflow, fully annotated

```yaml
# .github/workflows/ci.yml
name: ci
run-name: "ci for ${{ github.head_ref || github.ref_name }} by @${{ github.actor }}"

on:
  push:
    branches: [main]
    paths-ignore: ["docs/**", "**/*.md"]
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened, ready_for_review]

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  PYTHON_VERSION: "3.13"

jobs:
  lint:
    name: lint
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: pip
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .

  test:
    name: test (${{ matrix.python }})
    runs-on: ubuntu-24.04
    needs: [lint]
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        python: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
          cache: pip
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest -q --cov=app --cov-report=term

  build:
    name: build image
    runs-on: ubuntu-24.04
    needs: [test]
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: false
          tags: app:ci-${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

Line-by-line:

- `name:`, `run-name:` — readable in the UI.
- `on:` — runs on push to `main` (skipping doc-only changes), and on every relevant PR event against `main`.
- `permissions: contents: read` — least privilege at the top.
- `concurrency:` — newest commit on a branch cancels older runs.
- `env:` — single source of truth for the Python version of the lint job.
- `jobs.lint` — fast first; if lint fails, nothing else runs (because `test` and `build` both `needs:` upstream).
- `jobs.test` — matrix of 3 Python versions, `fail-fast: false` so you see all failures.
- `jobs.build` — runs after tests pass, builds a single image, no push (this is the CI workflow, not the release one).

This file is roughly 50 lines. It is also production-grade for a small Python service. Lecture 2 takes it further: reusable workflows, OIDC, GHCR push on merge, multi-arch, release-tag automation.

---

## 16. Anti-patterns to refuse on sight

- **`runs-on: ubuntu-latest`** — pin the OS. (Section 9.1.)
- **`@v4` everywhere with no Dependabot config** — pin by digest or pin by major + Dependabot. Not "pin by major and never look at it again."
- **`permissions: write-all`** — there is no realistic workflow that needs this. Scope down.
- **A 6-hour `timeout-minutes:` default** — set it. (Section 9.5.)
- **`pull_request_target` with `actions/checkout` of the PR ref** — RCE. Lecture 2 Section 13.
- **Secrets echoed into logs** — `run: echo "$DEPLOY_TOKEN"` is a leak.
- **Re-run-until-green** — flaky tests are a symptom of a real bug. Re-running is a culture failure, not a fix.
- **A 600-line single workflow file** — split into `ci.yml`, `release.yml`, `nightly.yml`. The Actions UI is row-per-workflow; one row is unreadable.

---

## 17. What you should have, by the end of this lecture

A `.github/workflows/ci.yml` in your Week 3 mini-project repo that:

- Triggers on `push` to `main` and on `pull_request` against `main`.
- Has `permissions: contents: read` at the top.
- Has `concurrency:` cancelling earlier runs on the same branch.
- Runs `lint`, then a matrix `test`, then a `build` job.
- Caches `pip` and the Docker layer cache via `type=gha`.
- Sets `timeout-minutes:` on every job.
- Comes back green on its first push.

Exercise 1 will walk you through writing exactly that file from scratch on a fresh repo, in 45 minutes. Lecture 2 will take it the rest of the way — to the version that pushes a multi-arch image to GHCR on merge to `main` and cuts a release on a `v*` tag, with OIDC into a sandbox cloud and zero long-lived credentials anywhere in the repo.

The discipline that turns a personal CI yaml into a production pipeline is the same discipline you applied to Compose last week: **explicit choices over defaults; least privilege over convenience; reproducible artifacts over "works on my machine."** Actions is just the surface where you write those choices down.
