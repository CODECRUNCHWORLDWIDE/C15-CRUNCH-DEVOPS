# Exercise 1 — Your First Real Pipeline

**Goal.** Write, push, and run a `.github/workflows/ci.yml` that lints, tests, and caches dependencies for a small Python repo. Confirm the first run is green. Confirm the second run is *faster*. Read the timing waterfall in the Actions UI and identify what the cache saved you.

**Estimated time.** 90 minutes (45 min building, 30 min running and inspecting, 15 min writing up).

---

## Why we are doing this

Lecture 1 gave you the file shape. This exercise gives you the keystrokes: every key you wrote about, you will now type, in a real repo, with a real CI run on real GitHub-hosted runners. By the end you will have an opinion about every field — which ones you set on every workflow, which ones you reach for only sometimes, and which ones you copy-pasted from a 2021 tutorial and never used again.

---

## Setup

### Working directory

```bash
mkdir -p ~/c15/week-04/ex-01-first-pipeline
cd ~/c15/week-04/ex-01-first-pipeline
git init -b main
gh repo create c15-week-04-ex01-$USER --public --source=. --remote=origin
```

(If `gh` is not installed: `brew install gh && gh auth login`.)

### Verify Actions is enabled on the repo

```bash
gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/actions/permissions \
  | jq '{enabled, allowed_actions}'
```

Expect `enabled: true`. If it returns `enabled: false`, enable Actions on the repo's Settings page.

### The application

Create the bare minimum Python service we will lint and test:

`pyproject.toml`:

```toml
[project]
name = "c15-w04-ex01"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["flask==3.0.3"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

`requirements.txt`:

```text
flask==3.0.3
```

`requirements-dev.txt`:

```text
-r requirements.txt
ruff==0.5.6
pytest==8.3.2
pytest-cov==5.0.0
```

`app/__init__.py` (empty file).

`app/main.py`:

```python
from flask import Flask

app = Flask(__name__)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/add/<int:a>/<int:b>")
def add(a: int, b: int) -> dict:
    return {"sum": a + b}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

`tests/__init__.py` (empty file).

`tests/test_main.py`:

```python
from app.main import app


def test_healthz():
    client = app.test_client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json == {"ok": True}


def test_add():
    client = app.test_client()
    resp = client.get("/add/2/3")
    assert resp.status_code == 200
    assert resp.json == {"sum": 5}
```

`.gitignore`:

```text
__pycache__/
*.pyc
.venv/
.coverage
.pytest_cache/
.ruff_cache/
```

Verify locally before pushing:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

Both commands should be green.

---

## Step 1 — The smallest correct workflow (10 min)

Create `.github/workflows/ci.yml`:

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  ci:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: pytest -q
```

Commit and push:

```bash
git add .
git commit -m "exercise 01 — first real pipeline"
git push -u origin main
```

Watch the run:

```bash
gh run watch
```

Expect a green run in ~60 seconds. If it is red, click through to the Actions tab and read the failing step.

---

## Step 2 — Add caching (15 min)

Replace the `setup-python` step with the cache-enabled form:

```yaml
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
          cache-dependency-path: requirements*.txt
```

The `cache: pip` shortcut wires `actions/cache@v4` for you, using `requirements*.txt` as the cache key.

Commit and push. Watch the run. The first post-cache run will be roughly the same speed as before (the cache is being *written*, not read). The next run will be noticeably faster.

Make a trivial change (add a blank line to `README.md`) and push again. This third run should restore the pip cache. In the run UI, expand the "Set up Python" step and look for the `Cache restored successfully` line. Note the wall-clock time of the `pip install` step on run 1 vs run 3.

Record those numbers in `notes/cache-timing.md`:

```text
Run 1 (no cache):    pip install took X seconds
Run 2 (cache write): pip install took Y seconds
Run 3 (cache read):  pip install took Z seconds
```

Expect Z to be 40–80% faster than X.

---

## Step 3 — Split into named jobs (15 min)

Decompose the single `ci` job into three: `lint`, `test`, and a placeholder `build`. The shape:

```yaml
jobs:
  lint:
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
          cache-dependency-path: requirements*.txt
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .

  test:
    runs-on: ubuntu-24.04
    needs: [lint]
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
          cache-dependency-path: requirements*.txt
      - run: pip install -r requirements-dev.txt
      - run: pytest -q --cov=app --cov-report=term

  build:
    runs-on: ubuntu-24.04
    needs: [test]
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - run: echo "build placeholder — exercise 03 will fill this in"
```

Commit and push. In the Actions UI, look at the workflow graph: `lint → test → build`, three boxes connected by arrows. That is the DAG you wrote.

Now break the lint deliberately: add a long line to `app/main.py`:

```python
def too_long():  # noqa
    return "this is a deliberately overlong line that should trip ruff's E501 line-length check ………………………"
```

Push. Watch the run. The `lint` job goes red; the `test` and `build` jobs are marked *skipped* with the explanation "Dependent jobs failed." That is the `needs:` contract: a failing dependency short-circuits the rest.

Fix the line. Push again. All three jobs go green.

---

## Step 4 — Read the timing waterfall (15 min)

Open one of the green runs in the Actions UI. Click the `test` job. Note the timing of each step:

```
┌─────────────────────────────────────────────────────┐
│  JOB — test                                         │
│                                                     │
│  Set up job                       2.1 s             │
│  Checkout                         1.3 s             │
│  Set up Python                    6.4 s   (cache!)  │
│  pip install                      4.7 s   (cache!)  │
│  pytest                           3.8 s             │
│  Post Set up Python               0.1 s             │
│  Complete job                     0.2 s             │
│  ─────────────────────────────────────────          │
│  Total                            18.6 s            │
└─────────────────────────────────────────────────────┘
```

Identify:

1. Which step takes the most time?
2. What would the run cost if `cache: pip` were removed? (Compare run 1's `pip install` time from Step 2.)
3. What would the run cost if `needs: [lint]` were removed? (Hint: lint and test would run in parallel, total wall-clock would drop to `max(lint, test)`.)

Record the answers in `notes/timing.md`.

---

## Step 5 — Add the `pull_request` trigger and run a real PR (15 min)

Already have `on: pull_request:` from Step 1. Now exercise it:

```bash
git checkout -b feature/break-something
# Edit something trivial in app/main.py
git commit -am "PR test — exercise 01"
git push -u origin feature/break-something
gh pr create --fill
```

Open the PR in the browser. The same three jobs run, but now they show on the PR's checks tab. Note:

- The workflow file that runs is the one on the **base** branch (`main`), not the PR's branch.
- The `concurrency:` block ensures pushing a new commit to the PR cancels the previous CI run on that branch.

Push another commit to the PR branch:

```bash
git commit --allow-empty -m "trigger another run"
git push
```

In the Actions UI, look for the *cancelled* status on the previous run. That cancellation saved you 60 runner-seconds. Multiply by your team's PR churn rate.

Merge the PR. The `push: branches: [main]` trigger runs `ci.yml` once more on `main`. The end state is the merge commit on `main` and a green check.

Close out:

```bash
git checkout main && git pull
git branch -D feature/break-something
```

---

## Step 6 — Deliberate cache invalidation (10 min)

Add a real dependency. Edit `requirements.txt`:

```text
flask==3.0.3
requests==2.32.3
```

Push. Watch the run. The cache key (hashed from `requirements*.txt`) has changed, so the cache misses. The `pip install` step now takes the full cold-cache time again. After the run completes, a new cache entry is written under the new key.

Push another trivial change. The cache hits the new key. `pip install` is fast again.

Record in `notes/cache-invalidation.md`:

```text
Before requirements change:  cache key = Linux-pip-abc123…
After requirements change:   cache key = Linux-pip-def456…
Cold-cache pip install:      X seconds
Warm-cache pip install:      Y seconds
```

This is the keying contract: **hash the inputs that should invalidate the cache, and only those inputs.** Hashing `*.py` would invalidate the cache on every code edit, which is wrong. Hashing only `requirements*.txt` invalidates only when the dependency set changes, which is right.

---

## Step 7 — Pin actions by SHA (10 min)

Install `ratchet`:

```bash
brew install ratchet || go install github.com/sethvargo/ratchet@latest
```

Run it against your workflow:

```bash
ratchet pin .github/workflows/ci.yml
```

The file now has every `uses:` line rewritten to a Git SHA with a comment:

```yaml
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.2.2
- uses: actions/setup-python@39cd14951b08e74b54015e9e001cdefcf80e669f  # v5.1.1
```

Commit. Push. The run is identical; the workflow is now reproducible to the bit.

Add `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "weekly" }
```

Commit. Dependabot will now open a PR every Sunday with action updates.

---

## Acceptance checklist

- [ ] `ci.yml` exists with `name`, `on`, `permissions`, `concurrency`, and three jobs.
- [ ] Top-level `permissions: contents: read`.
- [ ] `concurrency: cancel-in-progress: true`.
- [ ] `setup-python` step uses `cache: pip`.
- [ ] Three jobs: `lint`, `test`, `build`. `test` `needs: [lint]`; `build` `needs: [test]`.
- [ ] Every job has `timeout-minutes:` set.
- [ ] The repo has at least 5 green runs in the Actions tab.
- [ ] At least one demonstration that cancelling kicked in (a cancelled run from a force-push on the PR branch).
- [ ] `ratchet pin` has been run; every `uses:` is a Git SHA.
- [ ] `.github/dependabot.yml` exists with the `github-actions` ecosystem.
- [ ] `notes/cache-timing.md`, `notes/timing.md`, `notes/cache-invalidation.md` exist with measured numbers.

---

## Reflection questions

1. The `concurrency:` block cancelled an earlier run. What would have happened if you set `cancel-in-progress: false` instead? Which shape is right for a CI workflow, and which for a deploy workflow? Why?
2. The cache key is `${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}`. Walk through a scenario where you change a Python source file (not a requirements file) and explain whether the cache hits, in one sentence.
3. The `needs:` block made the failed lint short-circuit the rest. Is there ever a case where you want `test` to run even when `lint` failed? Name one and explain.

Write 2–3 sentences each in `notes/reflection.md`.

---

## What this exercise reps

The reading skill — what a `ci.yml` should look like — is one rep. The writing skill — typing it from scratch — is a different rep. The diagnostic skill — reading the timing waterfall, identifying the cache hit / miss, recognizing the `cancelled` status — is the third rep and the one that pays off the most. Every subsequent exercise builds on these three reps; they should feel automatic by Friday.

When done, push the repo and continue to [Exercise 2 — Matrix Builds](./exercise-02-matrix-builds.md).
