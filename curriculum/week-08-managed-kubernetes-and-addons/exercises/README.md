# Week 8 — Exercises

Four exercises, ~7 hours total. Do them in order; Exercise 2 depends on Exercise 1, Exercise 3 depends on Exercises 1 and 2.

| # | Title | Estimated time | Depends on |
|---|-------|----------------|------------|
| 1 | [Stand up kind with NGINX Ingress](./exercise-01-stand-up-kind-with-ingress.md) | 60 min | A working Docker setup |
| 2 | [Install cert-manager and issue a certificate](./exercise-02-install-cert-manager-and-issue-a-cert.md) | 75 min | Exercise 1 |
| 3 | [Bootstrap ArgoCD and sync an app](./exercise-03-bootstrap-argocd.md) | 90 min | Exercises 1 and 2 |
| 4 | [GKE Autopilot dry-run (manifest + commands)](./exercise-04-gke-autopilot-dry-run.yaml) | 60 min | None (no cluster required) |

Solutions and walkthroughs are in [SOLUTIONS.md](./SOLUTIONS.md). The expected commands, expected outputs, and diagnostic questions to ask when things diverge are all there.

## Voice rules for your write-ups

- Every exercise asks you to capture some commands and their output. Redact secrets and IP addresses; we do not need to see your Cloudflare API token in a screenshot.
- Quote command output as a fenced code block. Do not paraphrase.
- When the cluster reports an error, copy the entire error message, not just the first line. The first line is usually a generic summary; the cause is in lines 3-10.

## After all four exercises

You should have:

- A `kind` cluster with NGINX Ingress installed and exposed on host ports 80/443.
- cert-manager installed, a `selfsigned` `ClusterIssuer`, and at least one `Certificate` resource that issued successfully.
- ArgoCD installed, an admin password you have changed, and one `Application` that is `Synced` and `Healthy`.
- A short markdown file (`exercises/notes.md`) summarizing each exercise's outcome in your own words. This is the artifact you point at when describing this week's work in a portfolio.

If any one of the four is not in that state by Friday morning, stop and debug; the mini-project depends on all of them.
