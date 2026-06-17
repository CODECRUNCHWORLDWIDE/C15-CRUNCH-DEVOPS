# Exercise 2 — Matrix Builds

**Goal.** Fan the `test` job out across three Python versions and two operating systems. Use `include:` to add a coverage-only cell. Use `exclude:` to skip one combination. Watch six (then five) jobs run in parallel. Read the run cost and decide whether the matrix is worth it.

**Estimated time.** 90 minutes (40 min building, 30 min experimenting and reading the UI, 20 min writing it up).

---

## Why we are doing this

The single-job `test` from Exercise 1 tested *your* development setup — one Python version on one OS. A matrix tests every combination of inputs your code claims to support. If your `pyproject.toml` says `requires-python = ">=3.11"`, you owe it to your users to actually run the tests on 3.11, 3.12, and 3.13. If your README says "Linux and macOS," you owe it to your users to run on both.

Matrices are also the most common source of "the pipeline is too slow" complaints. By the end of this exercise you will know exactly how much a matrix costs and how to trim one that has gotten out of hand.

---

## Setup

Continue from Exercise 1, or start fresh:

```bash
mkdir -p ~/c15/week-04/ex-02-matrix
cd ~/c15/week-04/ex-02-matrix
git init -b main
gh repo create c15-week-04-ex02-$USER --public --source=. --remote=origin
```

Copy your Exercise 1 source files (`pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `app/`, `tests/`, `.gitignore`). Verify locally:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

Green.

---

## Step 1 — The scalar matrix (10 min)

Create `.github/workflows/ci.yml`:

```yaml
name: ci

on:
  push:    { branches: [main] }
  pull_request: { branches: [main] }

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    runs-on: ubuntu-24.04
    timeout-minutes: 10
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
          cache-dependency-path: requirements*.txt
      - run: pip install -r requirements-dev.txt
      - run: pytest -q
```

Commit and push. In the Actions UI you will see one workflow run that contains **three** jobs in parallel: `test (3.11)`, `test (3.12)`, `test (3.13)`. The job names come from the matrix values automatically.

```
┌─────────────────────────────────────────────────────┐
│  WORKFLOW — ci  /  run #1                           │
│                                                     │
│  test (3.11)         green   28 s                   │
│  test (3.12)         green   29 s                   │
│  test (3.13)         green   30 s                   │
│  ─────────────────────────────────────────          │
│  Total wall-clock                30 s               │
│  Total runner-minutes              1.5 min          │
└─────────────────────────────────────────────────────┘
```

Three jobs running in parallel finish in about the same wall-clock as one job. The runner-minute cost is 3x.

---

## Step 2 — The two-dimensional matrix (15 min)

Add the OS dimension. Edit the workflow:

```yaml
  test:
    runs-on: ${{ matrix.os }}
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        python: ["3.11", "3.12", "3.13"]
        os: [ubuntu-24.04, macos-14]
```

Commit and push. Now you have **six** jobs:

```
test (3.11, ubuntu-24.04)
test (3.12, ubuntu-24.04)
test (3.13, ubuntu-24.04)
test (3.11, macos-14)
test (3.12, macos-14)
test (3.13, macos-14)
```

In the run UI, note:

1. macOS runners start slower (the VM is "cold"); first-time setup can take 60+ seconds before your first step runs.
2. macOS runners cost roughly **10x** the runner-minutes of Linux on private repos. (Public repos are free, but the cost on private is real.)
3. The wall-clock is now bounded by the slowest cell, not the slowest *Linux* cell.

This is the moment to ask: **does our code actually depend on macOS-specific behavior?** For a Flask service that runs in a Linux container, the answer is "no" — testing on macOS in CI is mostly testing the Python interpreter, which the Python core team already tests. Drop macOS unless you ship a CLI that users install on a Mac.

We will keep it for this exercise to feel the cost.

---

## Step 3 — `exclude:` to trim (10 min)

We do not need to test Python 3.11 on macOS — it is an old combination and our code does not depend on it. Trim:

```yaml
    strategy:
      fail-fast: false
      matrix:
        python: ["3.11", "3.12", "3.13"]
        os: [ubuntu-24.04, macos-14]
        exclude:
          - python: "3.11"
            os: macos-14
```

Five jobs now run instead of six. The `exclude:` block removes the specified cells from the product.

Push and verify. In `notes/matrix-cells.md`, write out the full 3×2 product and circle the one that `exclude:` removes. This is the muscle memory you want: read the file, predict the cells, see them in the UI.

---

## Step 4 — `include:` to extend with extra parameters (15 min)

Add a coverage-only cell using `include:`. Coverage takes longer than a plain test run; we do not want to run it on every cell. We do want to run it on at least one — the most common deployment target.

```yaml
    strategy:
      fail-fast: false
      matrix:
        python: ["3.11", "3.12", "3.13"]
        os: [ubuntu-24.04, macos-14]
        include:
          - python: "3.13"
            os: ubuntu-24.04
            run-coverage: true
        exclude:
          - python: "3.11"
            os: macos-14
```

Update the steps to use the new parameter:

```yaml
      - run: pytest -q --cov=app --cov-report=term --cov-report=xml
        if: matrix.run-coverage == true

      - run: pytest -q
        if: matrix.run-coverage != true
```

This is the **classic `include:` pattern**: extend one existing cell with an extra parameter rather than adding a brand-new cell to the product. The 3.13/ubuntu cell now has `run-coverage: true`, while the other four cells have `run-coverage: ""` (the default for an unspecified matrix var). The `if:` guards split the steps.

Push and verify. The Actions UI shows one cell taking slightly longer (the coverage run); the others are at baseline.

---

## Step 5 — `fail-fast: true` vs `false` (10 min)

Right now `fail-fast: false` means a failure in one cell does *not* cancel the others. Flip it:

```yaml
    strategy:
      fail-fast: true
      matrix:
        # ... as before
```

Introduce a deliberate failure on one Python version. Edit `tests/test_main.py`:

```python
import sys


def test_dialect():
    # Fails on 3.11; passes on 3.12 and 3.13.
    if sys.version_info < (3, 12):
        assert False, "intentional failure on 3.11"
```

Push. Watch the Actions UI:

- `test (3.11, ubuntu-24.04)` runs and fails.
- The other cells — even ones already in flight — are cancelled.
- The Actions UI shows them as `cancelled`, not `failed`.

That is `fail-fast: true`. It saves runner-minutes when you have a structural failure (the kind that breaks every cell). It hides information when you have a per-cell failure (the kind that only breaks one Python version, which is exactly what a matrix is for).

Revert to `fail-fast: false`, push, and verify all five cells run to completion. Note that 3.11 still fails; the other four run and report green.

Now fix the test (delete `test_dialect`). Push. Five green cells.

In `notes/fail-fast.md`, answer: in what situation is `fail-fast: true` the right call, and in what situation is `false` the right call? Two sentences each.

---

## Step 6 — Read the cost (15 min)

In the Actions UI, open one of the runs from Step 5 (the all-green one). Note the runner-minute cost of each cell. The Actions UI does not show this directly on public repos, but you can compute it: each cell ran for `X` seconds; on a private repo, the cost would be:

- Linux: `X * 0.008` USD per minute
- macOS: `X * 0.08` USD per minute (10x multiplier)

For our five cells:

| Cell | Time | Linux cost | macOS cost |
|------|------|-----------:|-----------:|
| 3.11/ubuntu | 30 s | $0.004 | — |
| 3.12/ubuntu | 32 s | $0.004 | — |
| 3.13/ubuntu (coverage) | 38 s | $0.005 | — |
| 3.12/macos | 95 s | — | $0.127 |
| 3.13/macos | 95 s | — | $0.127 |
| **Total per push** |  | **$0.013** | **$0.254** |

Per push, the macOS half of the matrix costs **20x** what the Linux half costs. On a 30-PR-per-day repo, that is $7.62/day for macOS coverage that does not catch real bugs in a Flask service. Trim or accept; do not pretend it is free.

Record the table in `notes/cost.md` with your real measured timings.

---

## Step 7 — Conditional matrix expansion (15 min)

You may want a *short* matrix on PRs and a *full* matrix on `main`. The pattern uses `fromJSON` and `inputs:`:

```yaml
on:
  pull_request: { branches: [main] }
  push:         { branches: [main] }

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        python: ${{ fromJSON(github.event_name == 'pull_request' && '["3.13"]' || '["3.11","3.12","3.13"]') }}
        os: ${{ fromJSON(github.event_name == 'pull_request' && '["ubuntu-24.04"]' || '["ubuntu-24.04","macos-14"]') }}
```

On a PR, this runs **one** cell (`3.13/ubuntu`). On a push to `main`, it runs the full matrix.

This is the "fast PRs, thorough main" pattern. It is controversial — some teams insist that "test exactly what runs on main" is the only acceptable shape, and a PR that lacks matrix coverage may merge a 3.11-only bug. Defensible counterargument: a 3.11-only bug will show up on `main`'s post-merge build immediately, and you can revert. Pick the policy that matches your team's appetite for "merge then revert" vs "wait then merge."

For this exercise, leave the conditional in place and push. Verify the PR build runs one cell and the post-merge build runs five.

---

## Step 8 — Pin and Dependabot (10 min)

As in Exercise 1:

```bash
ratchet pin .github/workflows/ci.yml
```

Add `.github/dependabot.yml` if you have not already.

Push. Verify the run still succeeds.

---

## Acceptance checklist

- [ ] `ci.yml` declares a 2D matrix over `python` and `os`.
- [ ] `include:` adds a `run-coverage: true` parameter on exactly one cell.
- [ ] `exclude:` removes the `3.11/macos-14` combination.
- [ ] `fail-fast: false`.
- [ ] At least one PR run shows the short matrix (1 cell) and at least one `main` run shows the full matrix (5 cells).
- [ ] `notes/matrix-cells.md` enumerates the cells and circles the excluded one.
- [ ] `notes/fail-fast.md` answers the two-scenario question.
- [ ] `notes/cost.md` contains a measured cost table.
- [ ] Every `uses:` is SHA-pinned.

---

## Reflection questions

1. The five-cell matrix takes ~95 seconds wall-clock but ~3.3 runner-minutes. Explain the difference in one sentence and identify the constraint that determines each.
2. The `include:` cell adds `run-coverage: true` to an existing combination. What is the difference between using `include:` this way vs using `if: matrix.python == '3.13' && matrix.os == 'ubuntu-24.04'` on the coverage step? Which one is more readable?
3. The `exclude:` block removes 3.11/macos. What is a single-line change that would also remove 3.13/macos without restructuring the matrix? (Hint: there is more than one right answer.)
4. The conditional-matrix pattern with `fromJSON` is powerful but the YAML is ugly. Name an alternative pattern (covered in Lecture 2) that achieves the same "small matrix on PRs, full matrix on main" effect without the `fromJSON` ternary.

Write 2–3 sentences each in `notes/reflection.md`.

---

## What this exercise reps

The matrix is the most-used and most-overused feature in GitHub Actions. Every junior engineer adds a matrix; every senior engineer trims one. By the end of this exercise you have written one, expanded it with `include:`, trimmed it with `exclude:`, switched `fail-fast:`, measured its cost, and made it conditional. You will not need to re-learn any of those moves; you will reach for the right one on the day the bill arrives.

When done, push the repo and continue to [Exercise 3 — Deploy on Merge](./exercise-03-deploy-on-merge.md).
