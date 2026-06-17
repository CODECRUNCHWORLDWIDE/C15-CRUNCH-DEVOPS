# Week 8 Mini-Project — A Small App on kind, with the Full Add-On Stack, Deployed via ArgoCD, Portable to GKE Autopilot

**Time:** ~7 hours (~6h building, ~1h write-up).
**Cost:** $0.00 (kind path); $0.05-$0.20 if you optionally also deploy to a real GKE Autopilot cluster for an hour.
**Prerequisites:** All four exercises complete. The `w08` kind cluster is running with NGINX Ingress, cert-manager, and ArgoCD installed.

---

## What you are building

A small two-component application — a Python web API and a static frontend — deployed to a kind cluster, fronted by NGINX Ingress, secured with a cert-manager-issued certificate, and reconciled from a Git repo by ArgoCD. The same manifests are valid on GKE Autopilot with only the three differences from Lecture 3 Section 8 (the Ingress controller's Service type, the ClusterIssuer name, and the StorageClass — but we use no PersistentVolumes here, so the StorageClass row drops out).

The point is not the application; the application is deliberately small. The point is the **operational pattern**: a cluster, an Ingress, a certificate, a Git repo, ArgoCD, a deploy.

When you finish, your deliverable is a Git repo (`c15-week08-mini-project`) that anyone can clone, point at any Kubernetes cluster of any flavor, install via ArgoCD, and reach a working HTTPS endpoint.

---

## The application

A two-tier app:

1. **`api`** — a Python (FastAPI or similar; we provide a minimal version) HTTP service on port 8080. Endpoints:
   - `GET /api/health` — returns `{"status":"ok"}`. Used by readiness and liveness probes.
   - `GET /api/hello?name=X` — returns `{"greeting":"Hello, X"}`. The one feature.
   - `GET /api/info` — returns `{"version":"1.0","cluster":"<env var CLUSTER_NAME>"}`. Reads from a ConfigMap-injected env var.

2. **`web`** — a static frontend served by NGINX. A single `index.html` that fetches `/api/hello?name=Kubernetes` and renders the greeting. Plus a small CSS file. The whole frontend is ~50 lines.

The Ingress routes `/api/*` to the `api` Service and `/` (everything else) to the `web` Service. One hostname, two backends.

---

## Architecture

```
                  +----------------------------------+
                  |   Browser at https://app.localhost
                  +-----------------+----------------+
                                    |
                                    | HTTPS (TLS terminated at NGINX)
                                    v
                  +-----------------+----------------+
                  |   kind cluster, ports 80/443 mapped
                  |   to the host                    |
                  |                                  |
                  |  +--------------------------+    |
                  |  | NGINX Ingress Controller |    |
                  |  | reads `Ingress` resource |    |
                  |  +-------+--------+---------+    |
                  |          |        |              |
                  |          v        v              |
                  |   +-----------+ +--------+       |
                  |   | Service:  | | Service:       |
                  |   |  web      | |  api  |       |
                  |   +-----+-----+ +---+----+       |
                  |         |           |            |
                  |         v           v            |
                  |   +-----------+ +-----------+    |
                  |   |  web Pods | |  api Pods |    |
                  |   |  (nginx)  | |  (Python) |    |
                  |   +-----------+ +-----------+    |
                  |                                  |
                  |  cert-manager: Certificate ->    |
                  |   Secret (app-tls)               |
                  |                                  |
                  |  ArgoCD: Application -> watches  |
                  |   Git repo                       |
                  +----------------------------------+
                                    ^
                                    |
                                    | watches main branch
                                    |
                  +----------------------------------+
                  |   Git repo: github.com/YOU/c15-w08-mini
                  |   path: manifests/                |
                  +----------------------------------+
```

---

## Required deliverables

A Git repo containing:

```
c15-week08-mini-project/
├── README.md                          - description of the project
├── app/
│   ├── api/                           - the Python API source
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── requirements.txt
│   └── web/                           - the static frontend source
│       ├── Dockerfile
│       ├── index.html
│       └── style.css
├── manifests/                          - what ArgoCD applies
│   ├── 00-namespace.yaml
│   ├── 10-configmap.yaml
│   ├── 20-api-deployment.yaml
│   ├── 21-api-service.yaml
│   ├── 30-web-deployment.yaml
│   ├── 31-web-service.yaml
│   ├── 40-certificate.yaml             - on kind: selfsigned; on GKE: omit, use Ingress annotation
│   ├── 50-ingress.yaml
│   └── 60-pdb.yaml
├── overlays/
│   ├── kind/                           - overrides for kind
│   │   ├── cluster-issuer.yaml         - selfsigned ClusterIssuer
│   │   └── kustomization.yaml
│   └── autopilot/                      - overrides for GKE Autopilot
│       ├── cluster-issuer.yaml         - letsencrypt-staging ClusterIssuer
│       └── kustomization.yaml
├── argocd/
│   ├── application.yaml                - the ArgoCD Application for the kind path
│   └── application-autopilot.yaml      - the ArgoCD Application for the Autopilot path
└── notes.md                            - your write-up
```

The exact structure can vary; the *property* that matters is: one set of workload manifests, two environment overlays, two ArgoCD Application resources.

---

## Starter code

The starter code below is everything you need to begin. Copy it into your repo, replace the placeholder fields, push to a public Git repo, and point ArgoCD at it.

### `app/api/main.py`

```python
"""Tiny FastAPI service for the Week 8 mini-project.

Endpoints:
- GET /api/health   - liveness/readiness probe target
- GET /api/hello    - the one feature
- GET /api/info     - returns env-var-driven cluster info
"""

from __future__ import annotations

import os
from typing import Dict

from fastapi import FastAPI

app = FastAPI(title="c15-w08-api", version="1.0")


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def hello(name: str = "world") -> Dict[str, str]:
    return {"greeting": f"Hello, {name}"}


@app.get("/api/info")
def info() -> Dict[str, str]:
    return {
        "version": "1.0",
        "cluster": os.environ.get("CLUSTER_NAME", "unknown"),
    }
```

### `app/api/requirements.txt`

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
```

### `app/api/Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Run as a non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app /app
USER app

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### `app/web/index.html`

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>C15 Week 8 Mini-Project</title>
    <link rel="stylesheet" href="/style.css" />
  </head>
  <body>
    <main>
      <h1>Hello from the cluster.</h1>
      <p id="greeting">Loading...</p>
      <p id="info"></p>
    </main>
    <script>
      fetch("/api/hello?name=Kubernetes")
        .then((r) => r.json())
        .then((d) => (document.getElementById("greeting").textContent = d.greeting));
      fetch("/api/info")
        .then((r) => r.json())
        .then((d) => (document.getElementById("info").textContent =
          "API version " + d.version + " on cluster " + d.cluster));
    </script>
  </body>
</html>
```

### `app/web/style.css`

```css
body {
  font-family: system-ui, -apple-system, sans-serif;
  max-width: 40rem;
  margin: 2rem auto;
  padding: 0 1rem;
  color: #222;
  background: #fafafa;
}
h1 { font-size: 1.6rem; }
p  { color: #555; }
```

### `app/web/Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1
FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY index.html /usr/share/nginx/html/index.html
COPY style.css  /usr/share/nginx/html/style.css

EXPOSE 8080
```

### `manifests/00-namespace.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: w08-mini
  labels:
    week: w08
    project: mini
```

### `manifests/10-configmap.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: w08-mini
data:
  CLUSTER_NAME: "kind-w08"
  LOG_LEVEL: "info"
```

### `manifests/20-api-deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: w08-mini
  labels:
    app: api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: ghcr.io/YOUR_GITHUB_USERNAME/c15-w08-api:1.0
          ports:
            - containerPort: 8080
          envFrom:
            - configMapRef:
                name: app-config
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              memory: "256Mi"
          readinessProbe:
            httpGet:
              path: /api/health
              port: 8080
            initialDelaySeconds: 2
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /api/health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 30
```

### `manifests/21-api-service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: w08-mini
spec:
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 8080
```

### `manifests/30-web-deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  namespace: w08-mini
  labels:
    app: web
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
        - name: web
          image: ghcr.io/YOUR_GITHUB_USERNAME/c15-w08-web:1.0
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: "50m"
              memory: "64Mi"
            limits:
              memory: "128Mi"
          readinessProbe:
            httpGet:
              path: /
              port: 8080
            initialDelaySeconds: 1
            periodSeconds: 5
```

### `manifests/31-web-service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web
  namespace: w08-mini
spec:
  selector:
    app: web
  ports:
    - port: 80
      targetPort: 8080
```

### `manifests/40-certificate.yaml` (kind path; on GKE use the Ingress annotation instead)

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: app-tls
  namespace: w08-mini
spec:
  secretName: app-tls
  issuerRef:
    kind: ClusterIssuer
    name: selfsigned
  commonName: app.localhost
  dnsNames:
    - app.localhost
```

### `manifests/50-ingress.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app
  namespace: w08-mini
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - app.localhost
      secretName: app-tls
  rules:
    - host: app.localhost
      http:
        paths:
          - path: /api/
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 80
          - path: /
            pathType: Prefix
            backend:
              service:
                name: web
                port:
                  number: 80
```

### `manifests/60-pdb.yaml`

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
  namespace: w08-mini
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: api
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web-pdb
  namespace: w08-mini
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: web
```

### `overlays/kind/cluster-issuer.yaml`

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned
spec:
  selfSigned: {}
```

### `overlays/autopilot/cluster-issuer.yaml`

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: ops@YOUR_DOMAIN.com
    privateKeySecretRef:
      name: letsencrypt-staging-account
    solvers:
      - http01:
          ingress:
            ingressClassName: nginx
```

### `argocd/application.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: w08-mini
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_GITHUB_USERNAME/c15-week08-mini-project.git
    targetRevision: main
    path: manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: w08-mini
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

---

## Build and ship

### Step 1 — Build and push the images

```bash
# Log in to GHCR
echo $GHCR_PAT | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# Build the api image
cd app/api
docker build -t ghcr.io/YOUR_GITHUB_USERNAME/c15-w08-api:1.0 .
docker push ghcr.io/YOUR_GITHUB_USERNAME/c15-w08-api:1.0

# Build the web image
cd ../web
docker build -t ghcr.io/YOUR_GITHUB_USERNAME/c15-w08-web:1.0 .
docker push ghcr.io/YOUR_GITHUB_USERNAME/c15-w08-web:1.0
```

For kind specifically, if you would rather not push to GHCR for every iteration, `kind load docker-image` will load a locally-built image into the kind cluster. The `imagePullPolicy: IfNotPresent` is the default for tagged images, so the cluster will use the loaded image.

```bash
# Alternative: load into kind directly
kind load docker-image ghcr.io/YOUR_GITHUB_USERNAME/c15-w08-api:1.0 --name w08
kind load docker-image ghcr.io/YOUR_GITHUB_USERNAME/c15-w08-web:1.0 --name w08
```

### Step 2 — Commit and push the repo

```bash
cd c15-week08-mini-project
git init
git add .
git commit -m "Initial commit: mini-project starter"
gh repo create c15-week08-mini-project --public --source=. --push
```

Or use the GitHub web UI to create the repo and push.

### Step 3 — Apply the cluster-issuer (kind path)

```bash
kubectl apply -f overlays/kind/cluster-issuer.yaml
```

### Step 4 — Apply the ArgoCD Application

```bash
kubectl apply -f argocd/application.yaml
```

Watch ArgoCD sync:

```bash
kubectl get application w08-mini -n argocd -w
# Press Ctrl-C when status is Synced + Healthy
```

### Step 5 — Verify the application

```bash
# The cert should issue
kubectl -n w08-mini wait certificate/app-tls --for=condition=Ready --timeout=60s

# The deployments should be available
kubectl -n w08-mini get deploy,svc,ingress,pdb

# Browse the app
curl -v --insecure https://app.localhost/
curl -v --insecure https://app.localhost/api/hello?name=Mini-Project
curl -v --insecure https://app.localhost/api/info
```

The `/` endpoint returns the HTML; `/api/hello` returns `{"greeting":"Hello, Mini-Project"}`; `/api/info` returns `{"version":"1.0","cluster":"kind-w08"}`.

### Step 6 — Demonstrate the GitOps loop

Make a change in Git:

1. Edit `manifests/10-configmap.yaml`. Change `CLUSTER_NAME` to `"kind-w08-v2"`.
2. Commit and push.

Within 3 minutes ArgoCD detects the change, applies the new ConfigMap, and rolls the `api` Deployment so it picks up the new env var. Verify:

```bash
curl --insecure https://app.localhost/api/info
# {"version":"1.0","cluster":"kind-w08-v2"}
```

Note: env vars from a ConfigMap are snapshot at pod start. ArgoCD will not automatically restart your pods when the ConfigMap changes. To make the ConfigMap change propagate, either:

- Annotate the Deployment with a hash of the ConfigMap (Helm and Kustomize both do this automatically; you would do it by hand without them), or
- Run `kubectl -n w08-mini rollout restart deployment/api` after the ConfigMap is applied.

The mini-project's grading rubric expects you to *notice* this and to document the right pattern, not necessarily to implement Helm-style hashing.

---

## Rubric

The mini-project is graded on a 0-20 scale. Self-assess honestly.

| Category | Points | Criterion |
|----------|--------|-----------|
| Manifests apply cleanly | 3 | `kubectl apply --dry-run=server -f manifests/` produces no errors |
| Application is reachable | 3 | `curl https://app.localhost/` returns HTML; `/api/hello` returns JSON |
| TLS is working | 2 | Certificate Ready=True; NGINX serves the cert |
| ArgoCD is syncing | 3 | Application is Synced + Healthy; a Git change reflects within 3 min |
| `selfHeal` works | 2 | Manually editing the Deployment reverts within a sync cycle |
| Portability is real | 2 | The `overlays/autopilot/` directory contains a working ClusterIssuer + any other Autopilot-specific overrides; a written walk-through claims (and you believe) it would work on Autopilot |
| Repo structure is clean | 2 | The repo follows the structure above (or a justified variant); a stranger could clone and reproduce |
| `notes.md` is substantive | 3 | One paragraph per stage of the build; one reflection paragraph at the end |

The 4-point ceiling for a category is reserved for "exceeded the brief" cases (you added a useful feature that was not required, you wrote a working OpenAPI spec for the API, you added a CI job that builds the images on push). Aim for an honest 16+; do not pad.

---

## Stretch goals

If you have time:

- **Deploy to a real GKE Autopilot cluster.** Use the `overlays/autopilot/` overlay; create a second ArgoCD Application; point it at the same Git repo but a different `destination.server` (you would need to register the Autopilot cluster with ArgoCD first via `argocd cluster add`).
- **Add a CI workflow.** A GitHub Actions workflow that, on push to main, builds the two images, tags with the commit SHA, pushes to GHCR, and updates the Deployments' image tags in `manifests/` via a `git commit` from CI. This closes the loop from "code change" to "deployed" without anyone running `docker build` on a laptop.
- **Add an HPA.** A HorizontalPodAutoscaler for the `api` Deployment that targets 70% CPU. Test it by hitting `/api/hello` in a loop and watching the replica count grow.
- **Add a `NetworkPolicy`.** A default-deny network policy in the `w08-mini` namespace, plus explicit allow rules for `web -> api` and for `ingress-nginx -> web/api`. Demonstrates the principle of least-privilege at the network layer.
- **Write the second README at `mini-project/AUTOPILOT-NOTES.md`** describing the changes you made (or would make) to deploy the same repo to a real Autopilot cluster.

The mini-project is a portfolio piece. The repo you produce this week is the artifact you point at when describing your Kubernetes work for the next two years.

---

## Cleanup

When you are done with the week:

```bash
# Remove the ArgoCD Application (will also prune the workload because prune=true)
kubectl delete application w08-mini -n argocd

# Tear down the cluster
kind delete cluster --name w08
```

If you provisioned a GKE Autopilot cluster, also:

```bash
gcloud container clusters delete w08-autopilot --region us-central1 --quiet
```

Tear down on Sunday. Forgetting costs $5-20/month per Autopilot cluster.
