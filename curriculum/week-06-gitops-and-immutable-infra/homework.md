# Week 6 Homework

Six problems, ~6 hours total. Commit each in your week-06 repo.

---

## Problem 1 — Annotate a real Argo CD `Application` (45 min)

Pick a real `Application` YAML (and any related `AppProject` or `ApplicationSet`) from one of these published config repos:

- **`argoproj/argocd-example-apps`** — the canonical Argo CD example repo. Read the `guestbook/`, `helm-guestbook/`, and `apps/` directories: <https://github.com/argoproj/argocd-example-apps>.
- **`cloudposse/argocd-platform`** — a large, opinionated platform repo. Read `projects/` and `applications/`: <https://github.com/cloudposse/argocd-platform>.
- **`stefanprodan/gitops-istio`** — Argo or Flux example with Istio (Argo is in one branch, Flux in another): <https://github.com/stefanprodan/gitops-istio>.

Copy the relevant YAML files into `notes/annotated-application/`. For **every field** on the `Application` (and `AppProject` and `ApplicationSet` if you picked those), add a YAML comment that explains:

1. *What* this field does in one phrase.
2. *Why* it is set this way (sync policy choice, source path, project restriction).
3. *What would break* if you removed it or changed it.

**Acceptance.** `notes/annotated-application/` contains the files with at least 25 comment lines distributed across the fields, plus a `README.md` naming the source and the commit SHA you read.

---

## Problem 2 — Reconcile audit against your config repo (45 min)

Pick the config repo you bootstrapped in Exercise 2 (and used in Exercise 3). Run, in order:

```bash
git log --oneline main | head -20
git log --pretty=format:'%h %an %s' --since="7 days ago" | wc -l

# In the Argo cluster (recreate if you've torn it down)
argocd app history hello
argocd app get hello -o json | jq '.status.health, .status.sync'

# In the Flux cluster (recreate if torn down)
flux get all -A
kubectl get events -n flux-system --sort-by='.lastTimestamp' | tail -20

# Reconcile diff
argocd app diff hello || true
```

Then read each output and answer:

1. How many commits in the last week of the config repo? How many of those were image-bump commits vs config-change commits?
2. Does Argo's history match the git log? Are there any *Argo* syncs that do not correspond to commits (which would suggest a manual sync)?
3. Are there any events in the Flux events log that indicate a failed reconciliation? If so, what was the root cause?
4. Does `argocd app diff` print anything? If yes, the cluster has drifted; explain how.

**Acceptance.** `notes/reconcile-audit.md` contains the answers, the redacted command output, and a one-paragraph reflection on what this audit changes about how you treat the config repo going forward.

---

## Problem 3 — Build the bad GitOps loop, then the good one (90 min)

Take your Exercise 2 config repo. Write a second branch `bad-gitops` that deliberately does **everything wrong** from a GitOps-taste perspective:

- A `kustomization.yaml` that uses `images:` to bump the image tag inline in every PR rather than via a `kustomize edit set image` or an automation tool.
- An `Application` with `selfHeal: false` and `prune: false`.
- A single giant `apps/everything.yaml` containing the Deployment, Service, Ingress, ConfigMap, Secret (in plaintext!), and an associated `HorizontalPodAutoscaler`.
- A README that says "to deploy, run `kubectl apply -f manifests/` against the cluster" — push-model documentation in a pull-model repo.
- An `imagePullPolicy: Always` on the Deployment with the image tag `latest`.

Then on `main`, leave the proper shape from Exercise 2 intact:

- Per-app directory under `apps/<app>/` with one resource per file.
- An `Application` with `selfHeal: true`, `prune: true`, `ServerSideApply=true`.
- Image tag pinned to an SHA.
- Secrets in `SealedSecret` form (or note "TODO: install sealed-secrets" if you have not yet).
- README documenting the *pull-model* workflow (commit, push, watch reconcile).

Diff the two branches. Count the YAML lines.

**Acceptance.** `notes/before-after-gitops.md` contains:

- A table: `metric | bad | good | improvement`. YAML line count, number of resources per file, audit-trail clarity (your subjective rating).
- A one-paragraph reflection on which fix moved the needle most.
- A copy of both branches in `notes/bad-gitops/` and `notes/good-gitops/` for the diff.

Target improvement: at least **3x** clearer audit trail (subjective; you justify the number).

---

## Problem 4 — Reconciliation-loop diagnosis (45 min)

Take your Exercise 2 cluster (recreate the `kind-argocd-lab` cluster if you have torn it down — it is 90 seconds with the same `kind-config.yaml`).

Cause a stuck reconciliation deliberately. Pick one:

- Add a `PersistentVolumeClaim` to the `hello` app's manifests. `kind` does not have a default storage provisioner; the PVC will be stuck `Pending` forever. The `Application` will be stuck `Progressing`.
- Add a `Job` with a busted `image:` (a typo in the registry name). The Job will be stuck pulling.
- Add a `Service` of `type: LoadBalancer`. Without a cloud LB provider, the Service stays `Pending`.

Run, in order:

```bash
argocd app get hello
kubectl get all -n hello
kubectl describe <stuck-resource> -n hello
kubectl get events -n hello --sort-by='.lastTimestamp' | tail -20
argocd app diff hello
```

Read each output and answer:

1. What does Argo's status say (`OutOfSync`, `Progressing`, `Healthy`, `Degraded`)? Why that one?
2. What does `kubectl describe` on the stuck resource say? What is the proximate cause?
3. Are there events in the namespace that point at the root cause?
4. What is the fix? (For each of the three scenarios above the fixes are different.)

Fix the stuck reconciliation by reverting the offending commit and watch Argo recover.

**Acceptance.** `notes/stuck-reconcile.md` contains the answers, the diagnostic outputs (redacted), and a paragraph naming the *symptom* and *cause* (per the C15 voice rule: distinguish them).

---

## Problem 5 — The `OCIRepository` source in Flux (60 min)

Flux 2.4+ supports OCI artifacts as sources. Practice it.

1. Build the OCI manifest bundle from your config repo's `apps/hello/` directory:

```bash
flux push artifact oci://ghcr.io/<you>/c15-w06-hello-manifests:v1 \
  --path=./apps/hello \
  --source="$(git config --get remote.origin.url)" \
  --revision="$(git rev-parse HEAD)"
```

(You will need a GHCR PAT with `write:packages` scope and `docker login ghcr.io`.)

2. In a fresh directory (`~/c15/week-06/hw-oci`), write a `Source` and `Kustomization` that consumes the OCI artifact:

```yaml
apiVersion: source.toolkit.fluxcd.io/v1beta2
kind: OCIRepository
metadata:
  name: hello-oci
  namespace: flux-system
spec:
  interval: 1m
  url: oci://ghcr.io/<you>/c15-w06-hello-manifests
  ref:
    tag: v1
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: hello-oci
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: OCIRepository
    name: hello-oci
  path: ./
  prune: true
  targetNamespace: hello
```

3. Apply against the Flux cluster. Watch Flux pull from GHCR (not from git) and reconcile.

4. Bump to `v2` (rebuild the artifact, push, update the `ref.tag`). Confirm Flux picks it up.

**Acceptance.** `notes/oci-source.md` contains the configuration, the `flux get sources oci` output (showing the artifact pulled), and a one-paragraph comparison of OCI-as-source vs git-as-source (when each is the right choice).

---

## Problem 6 — Choose your secrets strategy (60 min)

You will have secrets in your config repo eventually. The three contenders, in difficulty order:

- **Sealed Secrets** — encrypt a `Secret` into a `SealedSecret` that can be committed to git. The cluster-side controller decrypts on apply. Simplest install; only Kubernetes secrets.
- **SOPS** — encrypt arbitrary YAML / JSON files with KMS, age, or PGP. Flux integration is first-class; Argo via a plugin. More flexible; more setup.
- **External Secrets Operator** — read secrets at runtime from Vault, AWS Secrets Manager, GCP Secret Manager. The secrets never live in the repo at all. Best security; most operational overhead.

Pick **one**. Install it on the Flux cluster (re-create it if torn down — 90 seconds). Encrypt a fake `DATABASE_URL` value. Commit the encrypted form to the config repo. Watch Flux apply it as a real `Secret` in the cluster.

**Acceptance.** `notes/secrets-strategy.md` contains:

- Which option you chose and why.
- The full encrypted secret (no real secrets — use placeholder values).
- A one-paragraph comparison of the chosen option against the other two (security model, install complexity, blast radius of a leaked key).
- A rotation plan: how do you rotate the encryption key without breaking reconciliation? (This is the question every team eventually asks; have the answer ready.)

---

## How to submit

Each problem produces a folder or a file in `notes/`. Commit them as you go:

```bash
git add notes/
git commit -m "homework: problem N — <title>"
```

End-of-week, push everything to `origin/main`. Add a `notes/README.md` that links to each problem's folder.

```bash
git push -u origin main
```

The homework is not graded the way exercises are graded; it is the seed of a portfolio. Future-you reading these notes in 2027 will be glad you wrote them down.
