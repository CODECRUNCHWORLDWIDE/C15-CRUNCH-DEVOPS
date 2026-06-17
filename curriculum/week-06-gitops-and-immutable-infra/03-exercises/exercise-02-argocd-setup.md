# Exercise 2 — Install Argo CD on a `kind` Cluster and Reconcile a Small App

**Goal.** Provision a local `kind` cluster. Install Argo CD on it. Create a small config repo containing one app (an `nginx` Deployment + Service + Ingress, or your Week 4 image — your choice). Define an `Application` CR pointing Argo at the config repo. Watch the sync happen. Drift the cluster deliberately by running `kubectl delete`. Watch Argo reconcile. Read the events; explain what you saw.

**Estimated time.** 90 minutes (45 min setup, 30 min running and inspecting, 15 min writing up).

**Cost.** $0.00 (entirely local; `kind` runs in Docker).

---

## Why we are doing this

Lecture 2 gave you the model: a controller in the cluster, a config repo, a pull loop. This exercise is the keystrokes. By the end you will have an opinion about every field on the Argo `Application` resource, you will have seen the controller correct drift on a live cluster, and you will have a config repo that is the seed of the mini-project.

---

## Setup

### Working directory

```bash
mkdir -p ~/c15/week-06/ex-02-argocd
cd ~/c15/week-06/ex-02-argocd
git init -b main
gh repo create c15-week-06-ex02-$USER --public --source=. --remote=origin
```

The actual *config repo* is a separate repo we create below. This working directory is for your write-up and any local scripts.

### Verify your tools

```bash
kind version              # 0.24+
kubectl version --client  # 1.30+
argocd version --client   # 2.13+
docker info | head -1     # must succeed
```

If `docker info` fails, start Docker Desktop (or Colima, or Podman). `kind` brings up a Kubernetes cluster *inside Docker*; without a container runtime, none of this works.

---

## Phase 1 — Create the `kind` cluster

We need a small cluster with an ingress controller pre-configured. The Argo CD docs recommend a specific `kind` config that exposes port 80 and 443; we use that.

`kind-config.yaml`:

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: argocd-lab
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
        hostPort: 8080
        protocol: TCP
      - containerPort: 443
        hostPort: 8443
        protocol: TCP
```

Create the cluster:

```bash
kind create cluster --config kind-config.yaml
# Creating cluster "argocd-lab" ...
#  ✓ Ensuring node image (kindest/node:v1.31.0)
#  ✓ Preparing nodes
#  ✓ Writing configuration
#  ✓ Starting control-plane
#  ✓ Installing CNI
#  ✓ Installing StorageClass
# Set kubectl context to "kind-argocd-lab"
```

Confirm:

```bash
kubectl cluster-info --context kind-argocd-lab
# Kubernetes control plane is running at https://127.0.0.1:62313
# CoreDNS is running at https://127.0.0.1:62313/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy

kubectl get nodes
# NAME                       STATUS   ROLES           AGE   VERSION
# argocd-lab-control-plane   Ready    control-plane   58s   v1.31.0
```

---

## Phase 2 — Install ingress-nginx

The Argo CD UI is reachable via port-forward, but we install ingress-nginx anyway because the demo app will use it.

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.2/deploy/static/provider/kind/deploy.yaml

kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
```

This takes about 60 seconds. The `wait` command blocks until the controller is ready.

---

## Phase 3 — Install Argo CD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.13.0/manifests/install.yaml
```

The manifest defines the `argocd` namespace's contents: the `argocd-server` Deployment, the `argocd-repo-server` Deployment, the `argocd-application-controller` StatefulSet, the `argocd-redis` Deployment, the `argocd-dex-server` Deployment (for SSO; we ignore), and several Services and ConfigMaps.

Wait for everything to be ready:

```bash
kubectl wait --namespace argocd \
  --for=condition=available deployment --all \
  --timeout=180s

kubectl get pods -n argocd
# NAME                                                READY   STATUS    RESTARTS   AGE
# argocd-application-controller-0                     1/1     Running   0          2m
# argocd-applicationset-controller-7c9f5b4f5c-d7v2n   1/1     Running   0          2m
# argocd-dex-server-7c9b6c8d4f-8x9p2                  1/1     Running   0          2m
# argocd-notifications-controller-7d9f5c4c5f-lk4qr    1/1     Running   0          2m
# argocd-redis-7d9c5b4c8d-x7m4p                       1/1     Running   0          2m
# argocd-repo-server-7c9d8b5c4f-4q2v8                 1/1     Running   0          2m
# argocd-server-7c5b4c8d4f-q8t6n                      1/1     Running   0          2m
```

Get the admin password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
# <a one-time password — copy it>
```

Port-forward to the UI:

```bash
kubectl port-forward -n argocd svc/argocd-server 8090:443 &
```

Open `https://localhost:8090` in a browser. The certificate is self-signed; accept the warning. Log in as `admin` with the password you just decoded.

Also log in from the CLI:

```bash
argocd login localhost:8090 --username admin --password '<the password>' --insecure
# 'admin:login' logged in successfully
# Context 'localhost:8090' updated
```

The `--insecure` flag is because of the self-signed cert in the lab; production Argo uses real TLS.

---

## Phase 4 — Create the config repo

A new GitHub repo distinct from the working directory above:

```bash
mkdir -p ~/c15/week-06/config-repo
cd ~/c15/week-06/config-repo
git init -b main
gh repo create c15-week-06-config-$USER --public --source=. --remote=origin
```

Create the layout from Lecture 2 Section 14:

```bash
mkdir -p apps/hello bootstrap clusters/lab infrastructure
```

### `apps/hello/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hello
  template:
    metadata:
      labels:
        app: hello
    spec:
      containers:
        - name: hello
          image: nginxdemos/hello:plain-text
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              cpu: 100m
              memory: 64Mi
```

### `apps/hello/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: hello
spec:
  type: ClusterIP
  selector:
    app: hello
  ports:
    - port: 80
      targetPort: 80
```

### `apps/hello/ingress.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hello
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:
    - host: hello.localtest.me
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: hello
                port:
                  number: 80
```

The hostname `hello.localtest.me` is a public DNS name that resolves to `127.0.0.1` for any subdomain — convenient for local labs. Try it: `dig hello.localtest.me +short` returns `127.0.0.1`.

### `apps/hello/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
  - ingress.yaml
```

Commit and push:

```bash
git add apps/
git commit -m "feat: hello app manifests"
git push -u origin main
```

---

## Phase 5 — Tell Argo about the app

Back in the working directory (`~/c15/week-06/ex-02-argocd`):

`application-hello.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: hello
  namespace: argocd
spec:
  project: default

  source:
    repoURL: https://github.com/<you>/c15-week-06-config-<you>
    targetRevision: main
    path: apps/hello

  destination:
    server: https://kubernetes.default.svc
    namespace: hello

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

Apply it:

```bash
kubectl apply -f application-hello.yaml -n argocd
# application.argoproj.io/hello created
```

Watch Argo discover the source, compute the diff, and apply:

```bash
argocd app get hello
# Name:               hello
# Project:            default
# Server:             https://kubernetes.default.svc
# Namespace:          hello
# URL:                https://localhost:8090/applications/hello
# Repo:               https://github.com/.../c15-week-06-config-...
# Target:             main
# Path:               apps/hello
# SyncWindow:         Sync Allowed
# Sync Policy:        Automated (Prune)
# Sync Status:        Synced to main (4c2f1ab)
# Health Status:      Healthy
```

Confirm the resources are in the cluster:

```bash
kubectl get all -n hello
# NAME                         READY   STATUS    RESTARTS   AGE
# pod/hello-7c9f5b4f5c-d7v2n   1/1     Running   0          45s
# pod/hello-7c9f5b4f5c-8x9p2   1/1     Running   0          45s
#
# NAME            TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
# service/hello   ClusterIP   10.96.x.y       <none>        80/TCP    45s
#
# NAME                    READY   UP-TO-DATE   AVAILABLE   AGE
# deployment.apps/hello   2/2     2            2           45s
```

Confirm it serves from the ingress:

```bash
curl -H "Host: hello.localtest.me" http://localhost:8080/
# Server address: 10.244.0.x:80
# Server name: hello-7c9f5b4f5c-d7v2n
# Date: 13/May/2026:14:32:08 +0000
# URI: /
# Request ID: xxxxxxxx
```

The Argo CD UI now shows `hello` with a green sync status and a tree view.

> **Status panel — Argo CD lab**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  ARGO CD — c15-w06-ex02                             │
> │                                                     │
> │  Cluster: kind-argocd-lab     Argo: 2.13.0          │
> │  Applications:  1 / 1 healthy                       │
> │                                                     │
> │  hello                                              │
> │    Sync:   Synced to main @ 4c2f1ab                 │
> │    Health: Healthy (2 / 2 replicas ready)           │
> │    Last sync: 47 s ago                              │
> │    Policy:  prune=true selfHeal=true                │
> └─────────────────────────────────────────────────────┘
> ```

---

## Phase 6 — Drift the cluster, watch Argo reconcile

The point of the pull model is that drift is automatically corrected. Let's see it.

### Drift 1: delete a pod

```bash
kubectl delete pod -n hello -l app=hello
# pod "hello-7c9f5b4f5c-d7v2n" deleted
# pod "hello-7c9f5b4f5c-8x9p2" deleted

kubectl get pods -n hello -w
# (within 2 seconds, two new pods appear and become Running)
```

The Deployment controller (a built-in Kubernetes controller) recreates the pods. This is *not* Argo doing it — pod recreation is the Deployment's job. But notice that Argo's sync status stays `Synced`: the Deployment resource itself never changed.

### Drift 2: delete the Service

```bash
kubectl delete svc hello -n hello
# service "hello" deleted

argocd app get hello
# Sync Status: OutOfSync from main (4c2f1ab)
# Health Status: Healthy   (the Deployment is still healthy)
```

Wait up to three minutes for Argo to poll (or trigger a sync manually with `argocd app sync hello`). Then:

```bash
kubectl get svc -n hello
# NAME    TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)   AGE
# hello   ClusterIP   10.96.x.z    <none>        80/TCP    5s
```

The Service is back. Argo detected drift, applied the manifest from the repo. The audit trail in the UI shows a "sync" event with a timestamp.

### Drift 3: change a replica count

```bash
kubectl scale deployment hello -n hello --replicas=5
# deployment.apps/hello scaled

kubectl get deployment hello -n hello
# NAME    READY   UP-TO-DATE   AVAILABLE   AGE
# hello   5/5     5            5           10m
```

The Deployment now has 5 replicas. But the manifest says 2. Wait for Argo to reconcile:

```bash
sleep 180
kubectl get deployment hello -n hello
# NAME    READY   UP-TO-DATE   AVAILABLE   AGE
# hello   2/2     2            2           13m
```

Argo scaled it back to 2. The `selfHeal: true` policy did its job.

### Drift 4: change something in the repo

Edit `apps/hello/deployment.yaml` in the config repo: change `replicas: 2` to `replicas: 3`. Commit and push:

```bash
cd ~/c15/week-06/config-repo
# (edit the file)
git add apps/hello/deployment.yaml
git commit -m "feat(hello): scale to 3 replicas"
git push
```

Watch the cluster:

```bash
kubectl get deployment hello -n hello -w
# (within ~3 minutes, replicas goes 2 → 3)
```

The forward-direction sync. Same loop; different trigger.

---

## Phase 7 — Roll back

The repo's `git log` is the deployment history. The Argo `app history` is the cluster's view of it:

```bash
argocd app history hello
# ID  DATE                              REVISION
# 0   2026-05-13 14:32:08 -0400 EDT     4c2f1ab (HEAD~1)
# 1   2026-05-13 14:48:22 -0400 EDT     a91d34b (HEAD)
```

Roll back the cluster to revision `0`:

```bash
argocd app rollback hello 0
# Rollback 'hello' to history ID 0

kubectl get deployment hello -n hello
# NAME    READY   UP-TO-DATE   AVAILABLE   AGE
# hello   2/2     2            2           17m
```

The cluster is back to 2 replicas, **but the repo still says 3**. The next reconciliation will pull the repo's `3` again, because `selfHeal: true`. The proper rollback is to revert the *commit* in the repo:

```bash
cd ~/c15/week-06/config-repo
git revert HEAD --no-edit
git push
```

Now the repo says 2 and the cluster will stay at 2. The "rollback in the UI" is a temporary measure; the rollback in git is the durable one. This is the rule: **the repo is the truth.**

---

## Phase 8 — Write up

In `~/c15/week-06/ex-02-argocd/`, create `README.md` with:

1. Your `kind` and Argo versions, your config repo URL.
2. A description of the four drifts you induced (pod delete, service delete, manual scale, repo edit) and what happened in each.
3. A reflection on `selfHeal: true` vs `selfHeal: false`: which would you use in a dev cluster, which in prod, which in a lab where you want manual `kubectl` changes to survive long enough to inspect.
4. A copy of `application-hello.yaml`.
5. A screenshot or terminal capture of `argocd app get hello` after the final sync.

Commit and push.

---

## What you should be able to do now

- Install Argo CD on a fresh `kind` cluster from memory in under fifteen minutes.
- Read an `Application` CR and predict, field by field, what the controller will do.
- Use `argocd app get`, `argocd app diff`, `argocd app sync`, `argocd app history`, `argocd app rollback`.
- Trigger drift in the cluster and observe Argo correcting it.
- Roll back through git (durable) and through the Argo UI (temporary), and explain the difference.

---

## Cleanup

The `kind` cluster is free but consumes RAM. Stop the port-forward and delete:

```bash
# stop the port-forward (find the PID)
kill %1   # if you started it with `&` in this shell

kind delete cluster --name argocd-lab
# Deleting cluster "argocd-lab" ...
```

Keep the config repo; Exercise 3 and the mini-project use it.

---

## Stretch goals

- Add a second app to the config repo (`apps/api/`). Add a second `Application` for it. Watch both syncs.
- Convert the two `Application` resources into one `ApplicationSet` with a git-directory generator that picks up everything under `apps/`. Add a third app without writing a new `Application` and confirm it is reconciled.
- Install `argo-rollouts` in the same cluster. Convert the `hello` Deployment into a `Rollout` with a canary strategy. Trigger a canary by changing the image tag.
- Install `argocd-image-updater`. Configure it to watch GHCR for your Week 4 image. Confirm that a new tag pushed to GHCR results in a PR (or a direct commit, depending on config) to the config repo.

---

*If you find errors in this material, please open an issue or send a PR.*
