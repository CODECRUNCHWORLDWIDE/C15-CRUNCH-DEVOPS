# Exercise 3 — Flux on a Parallel `kind` Cluster; the Side-by-Side Comparison

**Goal.** Provision a second `kind` cluster. Install Flux on it via `flux bootstrap`. Point it at the same config repo from Exercise 2. Watch the same `hello` app reconcile, with Flux's four-controller decomposition. Drift the cluster the same four ways. Then write a one-page comparison of Argo CD and Flux, picking one for the mini-project and defending the choice.

**Estimated time.** 90 minutes (45 min Flux setup, 30 min drift testing, 15 min write-up).

**Cost.** $0.00 (entirely local).

---

## Why we are doing this

Lecture 2 gave you the two reference implementations side by side at a model level. Exercise 2 gave you Argo CD. This exercise gives you Flux. By the end you will have direct hands-on with both and an opinion about which one fits which team. The mini-project that closes the week uses whichever you pick.

---

## Setup

### Working directory

```bash
mkdir -p ~/c15/week-06/ex-03-flux
cd ~/c15/week-06/ex-03-flux
git init -b main
gh repo create c15-week-06-ex03-$USER --public --source=. --remote=origin
```

### Verify your tools

```bash
flux --version
# flux version 2.4.0

gh auth status
# Logged in to github.com as <you>

kind version
# 0.24.x
```

If `flux` is missing, install it: `brew install fluxcd/tap/flux` on macOS, `curl -s https://fluxcd.io/install.sh | sudo bash` on Linux.

---

## Phase 1 — Create a parallel `kind` cluster

We give this cluster different host ports so it can run alongside the Argo cluster if you still have it up:

`kind-config.yaml`:

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: flux-lab
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
    extraPortMappings:
      - containerPort: 80
        hostPort: 8081
        protocol: TCP
      - containerPort: 443
        hostPort: 8444
        protocol: TCP
```

```bash
kind create cluster --config kind-config.yaml
# Set kubectl context to "kind-flux-lab"
```

Install ingress-nginx:

```bash
kubectl apply --context kind-flux-lab \
  -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.2/deploy/static/provider/kind/deploy.yaml

kubectl wait --context kind-flux-lab --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
```

---

## Phase 2 — `flux bootstrap`

The single command:

```bash
export GITHUB_TOKEN=$(gh auth token)

flux bootstrap github \
  --owner=<your-github-handle> \
  --repository=c15-week-06-config-$USER \
  --branch=main \
  --path=clusters/flux-lab \
  --personal
```

The `--personal` flag means the repo is owned by your user (not an org). The `--path` flag is where Flux will write its own install manifests inside the repo. The token in `GITHUB_TOKEN` is used to create a deploy key and push the install manifests.

What happens in sequence:

1. Flux checks that the cluster is reachable.
2. Flux installs its four controllers into the `flux-system` namespace.
3. Flux clones the config repo locally.
4. Flux writes `clusters/flux-lab/flux-system/gotk-components.yaml` (its own install manifest) and `clusters/flux-lab/flux-system/gotk-sync.yaml` (a `GitRepository` and `Kustomization` pointing back at this path) to the repo.
5. Flux pushes the changes.
6. Flux generates a deploy key with read-only access and adds it to the repo.
7. Flux creates a Secret in the cluster containing the deploy key's private half.
8. The just-installed Flux controllers begin reconciling, pulling their own install from the path Flux just wrote.

Output (abridged):

```
► connecting to github.com
► cloning branch "main" from Git repository "https://github.com/.../c15-week-06-config-..."
► generating component manifests
✔ generated component manifests
✔ committed component manifests to "main" ("a72cd91 ...")
► pushing component manifests to "https://github.com/.../c15-week-06-config-..."
✔ installed components
✔ reconciled components
► determining if source secret "flux-system/flux-system" exists
✔ generated source secret
✔ public key: "ecdsa-sha2-nistp384 AAAA..."
✔ configured deploy key "flux-system-main-flux-system-./clusters/flux-lab"
► generating sync manifests
✔ generated sync manifests
✔ committed sync manifests to "main" ("c4f1d8a ...")
► pushing sync manifests to "https://github.com/.../c15-week-06-config-..."
✔ reconciled sync configuration
◎ waiting for Kustomization "flux-system/flux-system" to be reconciled
✔ Kustomization reconciled successfully
► confirming components are healthy
✔ helm-controller: deployment ready
✔ kustomize-controller: deployment ready
✔ notification-controller: deployment ready
✔ source-controller: deployment ready
✔ all components are healthy
```

Confirm:

```bash
kubectl get pods -n flux-system
# NAME                                       READY   STATUS    RESTARTS   AGE
# helm-controller-7c9f5b4f5c-d7v2n           1/1     Running   0          2m
# kustomize-controller-7c9d8b5c4f-4q2v8      1/1     Running   0          2m
# notification-controller-7d9f5c4c5f-lk4qr   1/1     Running   0          2m
# source-controller-7c5b4c8d4f-q8t6n         1/1     Running   0          2m
```

Four controllers, one per CRD family. The decomposition is real.

Pull the latest from the config repo locally so you see what Flux wrote:

```bash
cd ~/c15/week-06/config-repo
git pull
ls clusters/flux-lab/flux-system/
# gotk-components.yaml
# gotk-sync.yaml
# kustomization.yaml
```

Read `gotk-sync.yaml`:

```yaml
---
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: flux-system
  namespace: flux-system
spec:
  interval: 1m0s
  ref:
    branch: main
  secretRef:
    name: flux-system
  url: ssh://git@github.com/<you>/c15-week-06-config-<you>
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: flux-system
  namespace: flux-system
spec:
  interval: 10m0s
  path: ./clusters/flux-lab
  prune: true
  sourceRef:
    kind: GitRepository
    name: flux-system
```

Two CRDs — the `GitRepository` (source) and the `Kustomization` (apply target). The `Kustomization` points back at `./clusters/flux-lab`, which is where these manifests themselves live. **Flux is managing itself from the repo.** This is the self-bootstrapping property.

---

## Phase 3 — Add the `hello` app under Flux

We re-use the `apps/hello/` manifests from Exercise 2's config repo (we are pointed at the same repo, after all). But we need a `Kustomization` resource that tells Flux to apply that path.

`clusters/flux-lab/apps.yaml`:

```yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: hello
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./apps/hello
  prune: true
  wait: true
  targetNamespace: hello
```

Commit and push:

```bash
cd ~/c15/week-06/config-repo
git add clusters/flux-lab/apps.yaml
git commit -m "feat(flux-lab): add hello kustomization"
git push
```

Wait for Flux to pick it up (the `GitRepository` polls every minute; the bootstrap `Kustomization` reconciles every ten minutes — for testing, trigger it manually):

```bash
flux reconcile source git flux-system
# ► annotating GitRepository flux-system in flux-system namespace
# ✔ GitRepository annotated
# ◎ waiting for GitRepository reconciliation
# ✔ fetched revision main@sha1:91c4f8d...

flux reconcile kustomization flux-system
# ► annotating Kustomization flux-system in flux-system namespace
# ✔ Kustomization annotated
# ◎ waiting for Kustomization reconciliation
# ✔ applied revision main@sha1:91c4f8d...
```

The cascading reconciliation: Flux re-pulls the source, sees a new `Kustomization` (`hello`), applies it, which (because `hello`'s `Kustomization` was just created and immediately reconciled) applies the `hello` namespace + Deployment + Service + Ingress.

Confirm:

```bash
flux get kustomizations
# NAME            REVISION                 SUSPENDED   READY   MESSAGE
# flux-system     main@sha1:91c4f8d2...    False       True    Applied revision: main@sha1:91c4f8d2...
# hello           main@sha1:91c4f8d2...    False       True    Applied revision: main@sha1:91c4f8d2...

kubectl get all -n hello
# (the same set of resources Argo deployed in Exercise 2)

curl -H "Host: hello.localtest.me" http://localhost:8081/
# (the same nginxdemos/hello output)
```

> **Status panel — Flux lab**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  FLUX — c15-w06-ex03                                │
> │                                                     │
> │  Cluster: kind-flux-lab        Flux: 2.4.0          │
> │  Controllers: 4 / 4 healthy                         │
> │    source-controller        ready                   │
> │    kustomize-controller     ready                   │
> │    helm-controller          ready                   │
> │    notification-controller  ready                   │
> │                                                     │
> │  Sources: 1 (GitRepository flux-system)             │
> │  Kustomizations: 2 (flux-system + hello)            │
> │  Last sync: 47 s ago                                │
> │                                                     │
> │  hello                                              │
> │    Sync:   Ready @ 91c4f8d                          │
> │    Health: 2 / 2 pods ready                         │
> │    Prune:  true                                     │
> └─────────────────────────────────────────────────────┘
> ```

---

## Phase 4 — Drift the cluster, watch Flux reconcile

The same four drifts from Exercise 2:

### Drift 1: delete a pod

```bash
kubectl delete pod -n hello -l app=hello
# (within seconds, Deployment recreates them)
```

The Deployment controller does this; Flux is not involved. Same as Argo.

### Drift 2: delete the Service

```bash
kubectl delete svc hello -n hello
# service "hello" deleted

flux get kustomizations
# NAME      REVISION                 SUSPENDED   READY   MESSAGE
# hello     main@sha1:91c4f8d2...    False       True    Applied revision: main@sha1:91c4f8d2...
```

Wait up to five minutes (the `Kustomization`'s `interval: 5m`) or trigger manually:

```bash
flux reconcile kustomization hello

kubectl get svc -n hello
# NAME    TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)   AGE
# hello   ClusterIP   10.96.x.z    <none>        80/TCP    5s
```

Restored. Same outcome as Argo, different controller.

### Drift 3: change replica count

```bash
kubectl scale deployment hello -n hello --replicas=5
# deployment.apps/hello scaled

# wait for the next reconciliation (or trigger it)
flux reconcile kustomization hello

kubectl get deployment hello -n hello
# NAME    READY   UP-TO-DATE   AVAILABLE   AGE
# hello   2/2     2            2           14m
```

Restored. Note that Flux's `Kustomization` does *not* have a separate `selfHeal` toggle; reconciling-against-drift is the default behavior, and you turn it off (if at all) by changing the `interval` to something long or by adding the `spec.suspend: true` field.

### Drift 4: change the repo

Same as Exercise 2 — edit `apps/hello/deployment.yaml` to `replicas: 3`, commit, push, wait. Flux pulls within a minute, applies within five.

```bash
cd ~/c15/week-06/config-repo
# edit replicas to 3
git add apps/hello/deployment.yaml
git commit -m "feat(hello): scale to 3 replicas"
git push

# trigger manually if impatient
flux reconcile source git flux-system
flux reconcile kustomization hello

kubectl get deployment hello -n hello
# hello   3/3   3   3   16m
```

Forward sync. Same shape as Argo; different CLI.

---

## Phase 5 — Notifications

Flux's notification-controller is one of the four. Add a Slack (or Discord, or GitHub) notification for sync events.

We will use GitHub: every successful reconciliation will post a commit status against the source SHA in the config repo. This is the audit checkpoint.

`clusters/flux-lab/notifications.yaml`:

```yaml
apiVersion: notification.toolkit.fluxcd.io/v1beta3
kind: Provider
metadata:
  name: github
  namespace: flux-system
spec:
  type: github
  address: https://github.com/<you>/c15-week-06-config-<you>
  secretRef:
    name: github-token
---
apiVersion: notification.toolkit.fluxcd.io/v1beta3
kind: Alert
metadata:
  name: github-reconciler
  namespace: flux-system
spec:
  providerRef:
    name: github
  eventSeverity: info
  eventSources:
    - kind: Kustomization
      name: '*'
    - kind: GitRepository
      name: '*'
```

The `Provider` references a Secret containing a GitHub PAT with `repo:status` scope. Create the secret:

```bash
gh auth refresh -s repo --hostname github.com
PAT=$(gh auth token)

kubectl create secret generic github-token \
  -n flux-system \
  --from-literal=token=$PAT
```

Commit the provider/alert:

```bash
cd ~/c15/week-06/config-repo
git add clusters/flux-lab/notifications.yaml
git commit -m "feat(flux-lab): github commit status notifications"
git push
```

Within one minute, Flux will reconcile, and the next sync will post a commit status against the SHA in GitHub. Visit `https://github.com/<you>/c15-week-06-config-<you>/commits/main` — you should see a green check next to the latest commit, with "flux/flux-system" or similar as the check name.

This is the GitOps audit trail rendered visible: every commit on `main` has a check confirming the cluster reconciled to it.

---

## Phase 6 — The comparison write-up

In your working directory, write `README.md` with a head-to-head:

### Template

```markdown
# Argo CD vs Flux — My Notes

## Setup time

- Argo CD: ____ minutes (from `kind create cluster` to first sync)
- Flux:    ____ minutes (from `kind create cluster` to first sync)

## Resource model

- Argo's `Application` is one CRD that wraps source + destination + sync.
- Flux's `GitRepository + Kustomization` is two CRDs: source separate from apply.

## Drift correction shape

- Argo: `selfHeal: true` is a toggle; default off in the docs.
- Flux: drift correction is the default behavior; you turn it off by suspending.

## UI

- Argo: ____
- Flux: ____

## CLI

- `argocd app get hello` vs `flux get kustomization hello`.
- `argocd app sync hello` vs `flux reconcile kustomization hello`.
- The two CLIs are about equally featureful; the Argo CLI is slightly more discoverable
  because `argocd app` is a clear noun. The Flux CLI has more nouns
  (`flux get kustomization`, `flux get source git`, ...) but they map cleanly to the CRDs.

## Notifications

- Argo: argocd-notifications, configured separately, semi-batteries-included.
- Flux: notification-controller is one of the four core controllers.

## Self-bootstrap

- Argo: possible (Argo managing its own install via an Application) but not the default.
- Flux: `flux bootstrap` is the *only* shape; Flux always manages itself from the repo.

## Pick one for the mini-project

I am picking ____ because ____.

## Three things I would change about my pick

1.
2.
3.
```

The write-up is graded on the **defense of the pick**, not on which one you picked. Both are defensible. The mini-project will work with either.

---

## What you should be able to do now

- Install Flux on a fresh `kind` cluster via `flux bootstrap` in under fifteen minutes.
- Read a `GitRepository` and a `Kustomization` and predict, field by field, what each controller will do.
- Use `flux get`, `flux reconcile`, `flux suspend`, `flux resume`.
- Trigger drift in the cluster and observe Flux correcting it.
- Configure a notification provider and an alert; confirm the commit status appears in GitHub.
- Articulate the trade-offs between Argo CD and Flux for a given team profile.

---

## Cleanup

```bash
kind delete cluster --name flux-lab
# Deleting cluster "flux-lab" ...
```

Keep the config repo. The mini-project uses it.

If you also still have the Argo cluster:

```bash
kind delete cluster --name argocd-lab
```

---

## Stretch goals

- Add an `OCIRepository` source pointed at a tag in GHCR. Use it as the `sourceRef` for a `Kustomization`. Confirm Flux can pull manifests from an OCI registry instead of git.
- Install `Image Reflector + Image Automation Controllers`. Configure them to watch GHCR for your Week 4 image. Confirm that a new tag pushed to GHCR results in a commit back to the config repo bumping the image reference.
- Install Flagger on the same cluster. Define a canary `Canary` resource for the `hello` Deployment. Trigger a canary by changing the image. (This is the Flux equivalent of Argo Rollouts.)
- Run Argo and Flux side by side on the *same* cluster, each managing a different `Kustomization`. The two controllers should not fight; if they do, the cause is overlapping resource selectors. Diagnose.

---

*If you find errors in this material, please open an issue or send a PR.*
