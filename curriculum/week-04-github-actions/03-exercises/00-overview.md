# Week 4 — Exercises

Three drills, in order. Each builds on the previous one. Total: ~5 hours of hands-on, plus another hour of reading the run logs in the Actions UI.

| # | File | Time | What you'll build |
|---|------|------|-------------------|
| 1 | [exercise-01-first-real-pipeline.md](./exercise-01-first-real-pipeline.md) | 90 min | A real `ci.yml` that lints, tests, and caches for a Python repo |
| 2 | [exercise-02-matrix-builds.md](./exercise-02-matrix-builds.md) | 90 min | A 3-Python × 2-OS test matrix with `include:` / `exclude:` |
| 3 | [exercise-03-deploy-on-merge.md](./exercise-03-deploy-on-merge.md) | 120 min | Build and push a multi-arch image to GHCR on merge to `main`, tag a release |

Push every exercise to its own folder in a public repo (`c15-week-04-<yourhandle>/ex-01/`, `ex-02/`, `ex-03/`) so a reviewer can inspect the workflow files, the run history, and the resulting image.
