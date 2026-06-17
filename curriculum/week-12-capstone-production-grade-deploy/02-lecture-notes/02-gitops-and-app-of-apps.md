# Lecture 2 — The GitOps Layout and the App-of-Apps Pattern

> *Imperative `kubectl apply` is how you learn Kubernetes. Declarative GitOps is how you operate it. The capstone is the moment you stop doing the first and start doing the second.*

Yesterday's lecture covered the composition and the bootstrap order. Today's lecture goes one level deeper into the GitOps half of that composition — the specific Git repository shape that ArgoCD reads from, the App-of-Apps pattern that makes the shape recursive, and the operational consequences of running a cluster whose state lives in Git rather than in the heads of the engineers who built it.

The lecture is split into four parts. **First**, the GitOps principles — what they say, where they come from, why the discipline matters. **Second**, the App-of-Apps pattern in detail — how one root `Application` CRD reconciles a directory full of other `Application` CRDs, why this is recursive, and what the recursion buys. **Third**, the operational surface — what a human does when they want to change the cluster (answer: they push to Git, full stop), what they do when ArgoCD reports an out-of-sync condition, what they do when the cluster has drifted from Git. **Fourth**, the trade-offs — the things GitOps is bad at, the things it requires a team to give up, and the cases where you should not use it.

By the end of the lecture you should be able to defend the capstone's `gitops/` directory line by line, explain the App-of-Apps recursion in three sentences, and identify the moment a colleague reaches for `kubectl edit` as the moment to push back.

---

## 1. The GitOps principles

GitOps as a discipline is older than the term. The discipline is "the desired state of the system lives in a version-controlled source of truth, a controller continuously reconciles the running state toward the desired state, and humans interact with the source of truth rather than with the running state". The pattern existed for years before Weaveworks coined the term *GitOps* in 2017; what they added was the name and the brand. The CNCF's OpenGitOps working group later formalized the principles in <https://opengitops.dev/>, which is now the canonical reference.

The four principles, as stated by OpenGitOps:

1. **Declarative.** The desired state is expressed as data, not as a sequence of imperative operations. A Kubernetes manifest is declarative; a shell script is not. The system can be re-applied at any time and the result is the same.

2. **Versioned and immutable.** The desired state lives in a version control system (typically Git), and every state has an unambiguous version (a Git SHA). Old states can be retrieved; bad states can be reverted; the history is auditable.

3. **Pulled automatically.** The reconciliation is initiated by a controller running in or near the cluster, not by a push from a human or from CI. Push-based systems are vulnerable to credential leaks (any actor with write access to the cluster API can push). Pull-based systems centralize the credential inside the cluster boundary.

4. **Continuously reconciled.** The controller does not apply the state once and stop. It re-applies it on a schedule (every few minutes) and on every change to the source of truth. If the running state drifts (someone runs `kubectl edit`), the controller notices and either reverts the drift or surfaces it for human attention.

The four together produce a system with one specific property: the cluster's state is the source of truth's state, eventually consistent. If the source of truth says "the application should run with 3 replicas", the cluster has 3 replicas; if it does not yet, it will within a few minutes. The reverse is not true — if a human scales the Deployment to 5 replicas via `kubectl scale`, the cluster temporarily has 5, then ArgoCD reconciles back to 3, because the source of truth still says 3.

That asymmetry is what an engineer used to `kubectl apply` finds disorienting at first. The cluster ignores their local changes. The cluster is right to ignore their local changes — the cluster is reconciling to the source of truth, and the human's local change was not committed to the source of truth. To make the change stick, the engineer must commit the change to Git and let ArgoCD pick it up. The discipline rules out a category of "I'll just patch this real quick" actions that, on undisciplined clusters, gradually destroy operability.

---

## 2. The App-of-Apps pattern

ArgoCD's primitive is the `Application` CRD. An `Application` points at a Git repository (or a Helm chart, or a Kustomize overlay) and tells ArgoCD "make the cluster look like what this points to". A simple cluster might have one or two `Application`s — one for the platform, one for the application.

The capstone has, by the end of the week, more like fifteen `Application`s — one for ingress-nginx, one for cert-manager, one for the kube-prometheus-stack, one for Loki, one for the OTel Collector, one for Vault, one for Kyverno, one for the Kyverno policies, one for OpenCost, one for the application, one for each Kustomize overlay. Managing fifteen `Application` CRDs through `argocd app create` invocations would be tedious, error-prone, and outside the GitOps discipline (each invocation is an imperative action, not a declarative state).

The **App-of-Apps pattern** solves this. The pattern is recursive: one root `Application` points at a Git directory; that Git directory contains other `Application` CRDs; ArgoCD applies the root `Application`, which causes ArgoCD to discover the child `Application`s, which causes ArgoCD to apply them in turn. The cluster's entire GitOps surface is bootstrapped by applying one `Application`.

In the capstone, the root `Application` is `gitops/app-of-apps.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: app-of-apps
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/your-org/c15-capstone.git
    targetRevision: main
    path: gitops/apps
    directory:
      recurse: true
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

The `path: gitops/apps` plus `directory.recurse: true` tells ArgoCD to read every YAML file under `gitops/apps/` and apply it. The files under `gitops/apps/` are themselves `Application` CRDs that point at specific Helm charts and Kustomize directories — `gitops/apps/platform/ingress-nginx.yaml` points at the ingress-nginx Helm chart; `gitops/apps/app/crunch-quotes.yaml` points at the `kustomize/crunch-quotes/overlays/kind` directory of the same repository.

The recursion stops at depth 2. The pattern can go deeper — you can have an App-of-Apps that points at an App-of-Apps that points at a regular Application — but in practice, two levels are enough for a single cluster, and going deeper trades clarity for genericity.

The pattern's three operational properties:

**Property 1 — one Git push reconciles the whole cluster.** Add a new platform component? Add a `gitops/apps/platform/new-component.yaml` file, push to `main`, ArgoCD's next sync picks it up. No `argocd app create` invocation; no `kubectl apply` from a human. The cluster's surface grows by one new Application without anyone having to remember to invoke a creation command.

**Property 2 — the cluster is rebuildable from one commit.** Destroy the cluster (`kind delete cluster`), spin up a new one, apply ArgoCD plus the root `Application` to the new cluster, wait. The cluster comes back. The state of every controller, every CRD, every policy, every manifest is reconstructed from the Git repository at the current commit. This is the disaster-recovery property that the rubric grades against in `make dr-rehearsal`.

**Property 3 — the diff between desired and running is observable.** ArgoCD's UI shows every `Application`'s status — *Synced* (running matches Git), *OutOfSync* (Git changed and ArgoCD has not yet applied), *Missing* (the Git resource is not in the cluster), *Extra* (the cluster has a resource Git does not). The diff is a continuous, queryable property of the cluster. A disciplined team's standing dashboard includes an ArgoCD-status panel; out-of-sync over more than a few minutes is an alert.

---

## 3. The operational surface — what humans do

A team that operates a GitOps cluster does, in 95 percent of cases, exactly one thing to change the cluster: they open a pull request against the source-of-truth repository, get it reviewed, merge it. ArgoCD picks up the change and applies it. The team's interaction with `kubectl` is, in routine operation, read-only.

The five operational scenarios:

### Scenario 1 — change a manifest

An engineer wants to bump the application's replica count from 2 to 3. They edit `kustomize/crunch-quotes/base/deployment.yaml`, open a PR, get it reviewed, merge it. ArgoCD's next sync (within 3 minutes by default; the `syncPolicy.automated` setting tunes it) detects the change, applies the new manifest, the Deployment scales to 3 replicas. The engineer's interaction with the cluster was a Git push.

### Scenario 2 — roll out a new image

CI builds a new image on a `main` push, signs it, pushes it to the registry, and updates the image tag in `kustomize/crunch-quotes/base/deployment.yaml` (via a small script that opens a PR or commits directly, depending on the team's policy). ArgoCD detects the manifest change and rolls the Deployment to the new image. The progressive-delivery layer (if the cluster runs Argo Rollouts; the capstone does not, this is a stretch goal) handles canary or blue-green.

### Scenario 3 — investigate an OutOfSync condition

An engineer notices an `Application` showing `OutOfSync` in the ArgoCD UI. They click into it. ArgoCD shows the specific resources that differ between Git and the cluster. They look at the diff. Typical causes: a controller has set a field that ArgoCD does not manage (e.g., HPA setting `spec.replicas` on a Deployment, conflicting with the Deployment's own replica count); a hotfix was applied by `kubectl edit` and never committed back; a Helm chart's default values changed between chart versions. The engineer either commits the cluster-side state back to Git or sets ArgoCD to ignore the field that is supposed to be controller-managed.

### Scenario 4 — apply an emergency fix

The application is on fire at 2 AM. The engineer needs to scale up immediately. They have two options:

- **The disciplined path.** Edit the manifest, commit, push, wait three minutes for ArgoCD to apply. The 3-minute wait is real but it is bounded; the disciplined path scales as easily for the next emergency as for this one.
- **The break-glass path.** Run `kubectl scale deployment ... --replicas=10` directly. The cluster scales immediately. ArgoCD will detect the drift on its next sync and revert the change. The engineer must therefore either commit the change to Git (which they should have done in the first place) or temporarily suspend ArgoCD's `selfHeal` on this `Application` until the emergency is over.

A mature team's runbook documents both paths. The disciplined path is the default; the break-glass path is for the cases where 3 minutes is too long. The runbook also includes the post-incident step of committing the emergency change back to Git so that ArgoCD stops trying to undo it.

### Scenario 5 — replace ArgoCD

This is the long-horizon scenario. The team decides to switch from ArgoCD to Flux (or vice versa, or to some other reconciler). The work is in setting up the new reconciler against the same `gitops/` directory; the application manifests do not change, because the GitOps source of truth is the Git directory, not the reconciler. The switch is a few days of work and a careful cutover; the Git directory is portable across reconcilers.

That portability is the largest single argument for keeping the `gitops/` directory simple. The more `Application`-specific fields you put in it (ArgoCD `syncPolicy`, ArgoCD `hooks`, ArgoCD `ignoreDifferences`), the harder the migration to a non-ArgoCD reconciler. The capstone uses ArgoCD-specific fields where necessary but keeps the application manifests in a separate `kustomize/` directory that is reconciler-agnostic.

---

## 4. The trade-offs — what GitOps is bad at

GitOps is the right discipline for a long-lived cluster running production workloads. It is the wrong discipline, or at least a heavy-handed discipline, for several adjacent cases.

### Case 1 — short-lived experiment clusters

If you spin up a kind cluster, run a 20-minute experiment, and delete it, GitOps is overhead. The cluster does not have a successor. There is no future engineer who will be confused about the state. The experiment fits in your terminal history.

The capstone is, technically, this case — the local kind cluster gets destroyed at the end of the week. The capstone still uses GitOps because the *learning* is GitOps; the discipline is what is being practiced. In a non-pedagogical setting, an ephemeral cluster does not warrant the overhead.

### Case 2 — data-plane changes

GitOps is good at reconciling control-plane state — manifests, RBAC, CRDs, configuration. It is bad at reconciling data-plane state — the contents of a Postgres database, a Vault secret store, the data files in a PersistentVolume. The data plane needs its own discipline (backups, replication, migrations) and GitOps does not address it.

The capstone uses a single-replica Postgres with a PVC. The data plane is "what is in the PVC". If the cluster is destroyed, the PVC contents are gone (kind's PVCs are local-disk-backed and do not survive a `kind delete cluster`). The disaster-recovery rehearsal explicitly does not preserve data — that is a known limitation. Real production clusters need a backup-and-restore discipline; the capstone documents this gap in `RUNBOOK.md` rather than pretending to solve it.

### Case 3 — interactive debugging

When a pod is crashing, `kubectl logs`, `kubectl describe`, `kubectl exec`, `kubectl debug` are the right tools. GitOps does not replace them. A reflexive opposition to `kubectl` for any purpose is overcorrection; the rule is *do not use `kubectl` to change the cluster's state*, not *do not use `kubectl` at all*.

### Case 4 — secrets

GitOps wants the source of truth to be Git. Secrets do not belong in Git. The reconciliation: encrypt the secrets with SOPS (or with sealed-secrets, or with External Secrets Operator pulling from Vault) so that the Git-stored version is unreadable without a key, and the running version is decrypted by a controller. The capstone uses SOPS plus the Vault Agent injector; W10 covered the discipline.

The trade-off is real. SOPS adds a key-management problem (the age private key must be on every operator's laptop and in CI). Vault adds an unsealing problem (the dev mode bypasses it; the production mode demands a key-management story for the unseal keys). Neither is hard, but both require deliberate setup.

### Case 5 — multi-cluster fleets

The capstone is one cluster. Real platforms run dozens. ArgoCD has a multi-cluster mode (a single ArgoCD instance reconciling many clusters) and ArgoCD has a fleet pattern (one ArgoCD per cluster, all managed from a central Git directory). Each has trade-offs; the literature is large; the capstone does not address it. The next-step learning is at <https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-management/>.

---

## 5. The recursive bootstrap, one more time

The bootstrap, recursively:

1. `make bootstrap` runs Terraform.
2. Terraform creates the kind cluster.
3. Terraform installs ArgoCD via the Helm provider.
4. Terraform applies the root `Application` (`gitops/app-of-apps.yaml`) via the Kubernetes provider.
5. ArgoCD reconciles the root `Application`.
6. The root `Application` points at `gitops/apps/`, which contains many child `Application`s.
7. ArgoCD reconciles each child `Application` in turn, respecting sync waves.
8. Each child `Application` points at a Helm chart or a Kustomize directory, which ArgoCD applies to the cluster.
9. The cluster is now in its desired state.

After step 4, every subsequent action is the cluster reconciling itself. Step 4 is the last human action. From step 4 onward, the cluster operates the cluster.

That property — *the cluster operates the cluster* — is the operational gain GitOps delivers. The human's job becomes editing the source of truth and reviewing the resulting reconciliations. The cluster's job is the cluster's job. Each side does what it is good at.

---

## 6. The reading for Exercise 3

Before Thursday's exercise on the platform install, read:

- The `Application` CRD reference: <https://argo-cd.readthedocs.io/en/stable/operator-manual/argocd_cmd_ref/argocd_app_create/>. About 15 minutes.
- The kube-prometheus-stack chart README: <https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack>. About 20 minutes.
- The cert-manager installation guide: <https://cert-manager.io/docs/installation/helm/>. About 15 minutes.
- The ingress-nginx installation guide: <https://kubernetes.github.io/ingress-nginx/deploy/>. About 10 minutes.

Total pre-reading: about one hour. The exercise itself is two to three hours; you will be reading the chart values files alongside applying them.

---

## 7. The cultural argument for GitOps, one more time

A reflexive question, near the end of the lecture: "isn't this all a lot of ceremony for a small cluster". The cluster is small. The application is forty lines of Python. Why do we need a GitOps controller, a recursive Application CRD, a Kustomize overlay, a Helm chart, fifteen platform components.

The honest answer is that the small cluster doesn't need it. The small cluster could be a `docker-compose up` and a single VM and a static HTML page. The cluster needs none of this to *work*.

The cluster needs all of this to be *operable*. The minute the small cluster becomes large enough that a second engineer touches it, every shortcut you took to keep it small becomes a question that engineer has to ask. *Where do I change the replica count? Where is the secret? How do I roll out a new image? What happens if I run `kubectl apply` while the previous deploy is still rolling? What does this Helm chart's `values.yaml` even mean? Why does our cluster work the way it does?* The GitOps shape answers each of those questions before they are asked. The answers are in the Git directory; the engineer reads the directory and the answers appear.

The capstone is the rehearsal of this discipline at small scale, before the scale is large enough that the discipline is forced on you by circumstance. A career in platform engineering is, in large part, a career of being two to five years ahead of when the scale would force the discipline. The team that builds the discipline early is the team that does not, three years in, find itself rewriting from scratch.

You will rewrite plenty of things. You should not rewrite the cluster.

Onward — Thursday's exercise installs the platform.
