# Week 8 Homework

Six problems, ~5 hours total. Commit each in your week-08 repo.

---

## Problem 1 — Compare managed Kubernetes pricing across three clouds (45 min)

Pick a hypothetical workload — a single-node cluster running 3 Deployments, each 2 replicas, each 200m CPU and 256Mi memory — and compute its monthly cost on:

1. **GKE Autopilot** (1 zonal cluster, us-central1, the free tier control plane plus pod-vCPU-seconds).
2. **GKE Standard** (1 zonal cluster, us-central1, control plane $73/mo plus a single `e2-medium` node).
3. **EKS** (1 cluster, us-east-2, control plane $73/mo plus a single `t3.small` node plus an NLB at $16/mo).
4. **AKS** (1 cluster, eastus, free control plane plus a single `Standard_B2s` node).

Use each provider's official pricing page (linked in `resources.md`).

Write `notes/cost-comparison.md` with:

- A table showing the four total monthly costs, broken down by line item.
- The cheapest option for this workload and by how much.
- A reflection: what changes the answer? (Hint: think about workload size; the answer differs dramatically for a 1-pod hobby project and for a 1000-pod enterprise app.)
- The full URLs of the pricing pages you used, dated.

Acceptance: `notes/cost-comparison.md` exists, has all four totals, and the reflection paragraph is in your own words.

---

## Problem 2 — Provision a real GKE Autopilot cluster (optional, ~$5, 60 min)

This problem is optional because it requires a GCP free trial credit (or ~$5 if you have used your trial). If you skip it, do Problem 2-Alternative below.

Provision an Autopilot cluster, apply the Exercise 1+2 manifests adapted from your Challenge 1 work, verify the application is reachable over HTTPS with a Let's Encrypt staging certificate, then tear down.

Write `notes/autopilot-real.md` with:

- The `gcloud container clusters create-auto` command you ran.
- The output of `kubectl get nodes` immediately after creation (empty) and after applying the first workload (one node).
- The `kubectl -n ingress-nginx get svc` output showing the `EXTERNAL-IP`.
- The `kubectl describe certificate` output showing the Let's Encrypt staging issuance.
- The `curl -v` output against your real public hostname (with `--insecure` because staging certs are not browser-trusted).
- The `gcloud container clusters delete` command and confirmation that the cluster is gone.

Acceptance: end-to-end working application on real Autopilot, torn down by submission.

### Problem 2-Alternative — Read three GKE Autopilot post-mortems (45 min)

If you do not want to provision a cluster, read three real-world write-ups of teams using GKE Autopilot in production. Suggestions:

- The **Google Cloud blog "GKE Autopilot" tag** has multiple customer case studies: <https://cloud.google.com/blog/products/containers-kubernetes>.
- **r/kubernetes** posts tagged "Autopilot" — Reddit threads where engineers describe their experience: <https://reddit.com/r/kubernetes/search?q=autopilot>.
- **GKE Autopilot vs Standard comparison posts** on Medium and Hashnode.

Pick three. Write `notes/autopilot-reading.md` with:

- The title, author, date, and URL of each piece.
- For each: the team's use case, the result, and one specific lesson they share.
- A synthesis paragraph: what is the common thread across all three?

Acceptance: three sources cited, summaries in your own words, synthesis paragraph at the end.

---

## Problem 3 — Write a Helm values file for ingress-nginx that covers three target clusters (60 min)

Write *one* Helm values file (or three, sharing a base) that, when applied with `--values`, produces:

1. A kind-compatible NGINX Ingress (hostPort, DaemonSet, nodeSelector — the Exercise 1 recipe).
2. A GKE-compatible NGINX Ingress (Service type LoadBalancer, default Deployment, no nodeSelector).
3. An EKS-compatible NGINX Ingress (Service type LoadBalancer, plus the AWS-specific annotation `service.beta.kubernetes.io/aws-load-balancer-type: "nlb"` to get an NLB instead of the legacy ELB).

The right pattern is three files: `base.yaml`, `kind.yaml`, `gke.yaml`, `eks.yaml`, each adding to base. Helm allows multiple `--values` flags; the last one wins on conflicts.

Write `notes/values-files/` containing:

- `base.yaml` — the common settings (resource requests, replica count, NGINX version pin).
- `kind.yaml` — the kind overrides.
- `gke.yaml` — the GKE overrides.
- `eks.yaml` — the EKS overrides.
- `README.md` — explaining what each file adds and how to apply each combination.

Acceptance: `helm install ... --values base.yaml --values <env>.yaml --dry-run --debug` succeeds for each environment (kind, gke, eks). You do not need to actually install on each cluster; the dry-run is the verification.

---

## Problem 4 — Install external-dns against a Cloudflare zone you own (90 min, requires a free Cloudflare account and a domain)

If you have a domain on Cloudflare (or can register one for $10/year), this problem is highly worthwhile. If not, skip it.

Provision a Cloudflare API token with `Zone.DNS:Edit` permission scoped to your domain. Install external-dns via Helm into the `w08` kind cluster. (external-dns works on kind for the *DNS-record-creation* side; the records will point at whatever IP your Ingress controller has, which on kind is your laptop's IP — useless for real traffic but valid for demonstrating the record-creation loop.)

Configure external-dns with the Cloudflare provider, a `txtOwnerId`, and `domainFilters=YOUR_DOMAIN.com`.

Update the Exercise 1 Ingress to use `external-dns.alpha.kubernetes.io/hostname: app.YOUR_DOMAIN.com`.

Verify in the Cloudflare dashboard that an A record and a TXT record were created.

Write `notes/external-dns/` containing:

- The Helm values file (with the Cloudflare API token *redacted*).
- Screenshots of the Cloudflare dashboard showing the records.
- A description of the TXT record's contents and what `txtOwnerId` does.

Acceptance: Cloudflare shows the expected records. The token is *not* in your committed write-up.

---

## Problem 5 — Configure Workload Identity for an Autopilot cluster (requires Problem 2's cluster, 60 min)

If you completed Problem 2 (real Autopilot cluster), extend it. If not, this problem becomes a paper exercise.

Create a GCP service account `app-gsa@PROJECT.iam.gserviceaccount.com`. Grant it `roles/storage.objectViewer` on a Cloud Storage bucket you create (call it `gs://YOUR_PROJECT-w08-test`; upload a small text file).

Bind a Kubernetes ServiceAccount `app-sa` in namespace `ex05` to the GSA via Workload Identity (the recipe from Lecture 2 Section 4.3 and Exercise 4 Section 6).

Deploy a Pod that uses the `app-sa` KSA and runs the `google/cloud-sdk:slim` image. Exec into it and run `gsutil cat gs://YOUR_PROJECT-w08-test/<file>`.

Write `notes/workload-identity.md` with:

- The four `gcloud` and `kubectl` commands you ran to set up the binding.
- The output of `kubectl get sa app-sa -o yaml` showing the `iam.gke.io/gcp-service-account` annotation.
- The `gcloud iam service-accounts get-iam-policy app-gsa@...` output showing the `roles/iam.workloadIdentityUser` binding to the KSA principal.
- The successful `gsutil cat` output from inside the pod.
- A reflection: how does this differ operationally from mounting a JSON key as a Secret? In what threat scenarios is Workload Identity strictly better?

If you skipped Problem 2: write up the paper version. The four commands, the YAML, and the reflection. The grader cares about the explanation, not the live demo.

---

## Problem 6 — Read the cert-manager source and the ArgoCD application-controller source (60 min)

Open the source of two of the four add-ons we installed this week and read enough to answer one specific question per project.

### Part A — cert-manager

Read `pkg/controller/certificates/issuing/issuing_controller.go` from the cert-manager source: <https://github.com/cert-manager/cert-manager/blob/master/pkg/controller/certificates/issuing/issuing_controller.go>.

Answer in `notes/source-reading.md`:

1. What is the `Sync` function's job? (Look for the function and trace what it does.)
2. What inputs does it take, and what outputs does it produce?
3. How does it know whether the Certificate has been issued, is being issued, or has failed?

One paragraph per question.

### Part B — ArgoCD

Read `controller/appcontroller.go` from the ArgoCD source: <https://github.com/argoproj/argo-cd/blob/master/controller/appcontroller.go>.

Answer in `notes/source-reading.md`:

1. The `processAppOperationQueueItem` function (or similar; the exact name may vary) is the per-Application reconciliation loop. What does it do on a single iteration?
2. How does the controller decide whether to sync, prune, or selfHeal?
3. What is the relationship between the application-controller and the repo-server (the other deployment in the ArgoCD namespace)?

One paragraph per question.

Acceptance: `notes/source-reading.md` answers all six questions in your own words, with permalinks (commit-SHA URLs) to the specific lines you read.

---

## How to submit

Each problem produces a folder or a file in `notes/`. Commit them as you go:

```bash
git add notes/
git commit -m "homework: problem N - <title>"
```

End-of-week, push to `origin/main` and add `notes/README.md` linking to each problem.

```bash
git push -u origin main
```

The homework is not graded the way exercises are graded; it is the seed of a portfolio. Future-you in 2027 will be glad you wrote down what you learned in 2026.

---

## Rubric (for self-assessment)

For each problem, ask yourself:

| Score | Criterion |
|-------|-----------|
| 4 | I did the work, wrote it up in my own words, and could re-explain it tomorrow without notes. |
| 3 | I did the work and wrote it up; I would need to re-read my notes to re-explain it. |
| 2 | I did the work but did not write it up clearly. |
| 1 | I read the problem but did not do the work. |

Aim for an average of 3+ across the six problems. Anything less means the material is not internalized.
