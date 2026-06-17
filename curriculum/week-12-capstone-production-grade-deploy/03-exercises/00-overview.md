# Week 12 — Exercises

Five exercises, in order. Each is a focused integration step that you can complete in 60 to 120 minutes. The exercises compose into the capstone mini-project on Sunday; complete them in sequence.

| #  | Title                                                    | Estimated time | File                                            |
|----|----------------------------------------------------------|----------------|-------------------------------------------------|
| 1  | Cluster bootstrap: kind + Terraform + ArgoCD            | 90 min         | `exercise-01-cluster-bootstrap.md`              |
| 2  | The application and its CI pipeline                     | 120 min        | `exercise-02-app-and-ci.md`                     |
| 3  | The platform install: ingress, certs, observability     | 120 min        | `exercise-03-platform-install.md`               |
| 4  | Supply-chain and cost wiring                            | 90 min         | `exercise-04-supply-chain-and-cost.md`          |
| 5  | The end-to-end smoke test                               | 60 min         | `exercise-05-smoke-test.md`                     |

When each exercise completes, paste the checkpoint output into `SOLUTIONS.md`. The mini-project on Sunday composes the five into one repository.

## Files in this directory

- `kind-w12.yaml` — kind cluster configuration.
- `manifests-app-of-apps.yaml` — root ArgoCD `Application`.
- `manifests-platform-apps.yaml` — platform-component `Application`s.
- `manifests-app.yaml` — base manifests for the application.
- `manifests-kyverno-policies.yaml` — Kyverno `ClusterPolicy` objects.
- `smoke_test.py` — end-to-end smoke test (Exercise 5).
- `capstone_audit.py` — read-only cluster audit (used by the mini-project).
- `slo_report.py` — SLO compliance reporter (used by the mini-project).
- `SOLUTIONS.md` — your checkpoint outputs go here.
