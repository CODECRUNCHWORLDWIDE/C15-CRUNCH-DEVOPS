# Mini-Project — A 3-Tier App on `kind`: nginx → Python API → Postgres

> Deploy a complete three-tier web application on a single `kind` cluster: an **nginx** reverse proxy in front of a **Python API**, both connected to a **Postgres** database. All workloads run as Kubernetes resources (Deployments, Services, ConfigMaps, Secrets, Jobs). The whole stack runs on your laptop, costs $0.00, and exercises every concept from the week's lectures.

This is the synthesis project for Week 7. By doing it, you will touch every primitive from Lecture 3 — Deployment, Service, ConfigMap, Secret, Job — in a stack that *also* needs the cross-tier wiring (DNS-based service discovery, labels-as-selectors, ConfigMap-as-env, Secret-as-env) to be correct. By Sunday you will have a folder of YAML you can `kubectl apply -f` and get a working three-tier app, and you will be able to defend every line of it.

**Estimated time.** 6 hours, spread across Friday-Saturday.

**Cost.** $0.00. Everything is local; the `kind` cluster from Exercises 1-3 is the substrate.

---

## What you will build

```
              ┌─────────────────────────────────────────────────┐
              │  laptop (kubectl port-forward svc/nginx 8080:80)│
              └─────────────────────┬───────────────────────────┘
                                    │ HTTP
                                    ▼
              ┌─────────────────────────────────────────────────┐
              │  kind cluster (single node, namespace `app`)    │
              │                                                 │
              │  ┌─────────────────┐                            │
              │  │  Service: nginx │  ClusterIP 10.96.x.x:80    │
              │  └────────┬────────┘                            │
              │           │ selects app=nginx                   │
              │           ▼                                     │
              │  ┌─────────────────┐                            │
              │  │  Deployment:    │  2 replicas                │
              │  │  nginx          │  reverse-proxy →           │
              │  │                 │  http://api.app.svc:8080   │
              │  └────────┬────────┘                            │
              │           │ outbound HTTP                       │
              │           ▼                                     │
              │  ┌─────────────────┐                            │
              │  │  Service: api   │  ClusterIP                 │
              │  └────────┬────────┘                            │
              │           │ selects app=api                     │
              │           ▼                                     │
              │  ┌─────────────────┐                            │
              │  │  Deployment:    │  2 replicas                │
              │  │  api (Python)   │  DB pool →                 │
              │  │                 │  db.app.svc:5432           │
              │  └────────┬────────┘                            │
              │           │ Postgres protocol                   │
              │           ▼                                     │
              │  ┌─────────────────┐                            │
              │  │  Service: db    │  ClusterIP                 │
              │  └────────┬────────┘                            │
              │           │ selects app=db                      │
              │           ▼                                     │
              │  ┌─────────────────┐                            │
              │  │  Deployment:    │  1 replica (single node,   │
              │  │  db (Postgres)  │  emptyDir volume — data    │
              │  │                 │  is lost on pod restart;   │
              │  │                 │  acceptable for the lab)   │
              │  └─────────────────┘                            │
              │                                                 │
              │  ┌─────────────────┐                            │
              │  │  Job: migrate   │  one-shot: creates the     │
              │  │                 │  schema in the db, then    │
              │  │                 │  exits 0                   │
              │  └─────────────────┘                            │
              └─────────────────────────────────────────────────┘
```

Three tiers, four Services, three Deployments, one Job, and the ConfigMaps and Secrets to wire them together. Every cross-tier connection is by **Service name** (DNS-based service discovery); no hardcoded pod IPs anywhere.

---

## Acceptance criteria

- [ ] All resources live in a single namespace, `app`.
- [ ] `kubectl -n app get deployments` shows three deployments (`nginx`, `api`, `db`) all with `READY=N/N`.
- [ ] `kubectl -n app get services` shows three Services (`nginx`, `api`, `db`).
- [ ] `kubectl -n app get jobs` shows the `migrate` job with `COMPLETIONS=1/1`.
- [ ] `kubectl -n app port-forward svc/nginx 8080:80` then `curl http://localhost:8080/api/items` returns a JSON list (initially empty or with one seed row from the migration).
- [ ] `curl -X POST http://localhost:8080/api/items -d '{"name": "test"}' -H 'Content-Type: application/json'` returns 201 and the row persists across `curl http://localhost:8080/api/items`.
- [ ] All YAML passes `kubectl apply --dry-run=client -f manifests/`.
- [ ] All YAML passes `kubectl apply --dry-run=server -f manifests/`.
- [ ] The api's Deployment has readiness and liveness probes that *work* (the readiness probe fails until the DB is reachable; you can verify by scaling `db` to 0 and watching the api pods go `not Ready`).
- [ ] The db's password is in a `Secret`, not a ConfigMap, not hardcoded in any Deployment.
- [ ] A `README.md` at the root of the mini-project documents: the architecture, the apply order, the verification steps, the teardown command.

---

## Build order

You will create about 12 YAML files in a `manifests/` directory plus an `api/` directory with the Python application source and Dockerfile.

```
mini-project/
├── manifests/
│   ├── 00-namespace.yaml
│   ├── 10-db-configmap.yaml
│   ├── 11-db-secret.yaml
│   ├── 12-db-deployment.yaml
│   ├── 13-db-service.yaml
│   ├── 20-migration-job.yaml
│   ├── 30-api-configmap.yaml
│   ├── 31-api-deployment.yaml
│   ├── 32-api-service.yaml
│   ├── 40-nginx-configmap.yaml
│   ├── 41-nginx-deployment.yaml
│   └── 42-nginx-service.yaml
├── api/
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
└── README.md
```

The numeric prefixes are *not* required by Kubernetes (the API server is order-insensitive for `apply`), but they make `kubectl apply -f manifests/` apply in a sensible order, which helps you read the cluster's events in the order things happened.

---

## Step 1 — Bring up the cluster (if not already up)

```bash
kubectl cluster-info --context kind-c15-w07-lab 2>/dev/null || \
  kind create cluster --config ../exercises/kind-config.yaml
```

(Reuse the `kind-config.yaml` from Exercise 1.)

---

## Step 2 — Namespace and DB

`manifests/00-namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: app
  labels:
    course: c15
    week: w07
    project: 3-tier
```

`manifests/10-db-configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: db-config
  namespace: app
data:
  POSTGRES_DB: appdb
  POSTGRES_USER: appuser
  # Note: POSTGRES_PASSWORD lives in the Secret, not here.
```

`manifests/11-db-secret.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
  namespace: app
type: Opaque
stringData:
  POSTGRES_PASSWORD: "labpassword-rotate-before-prod"
  # In a real deploy this would be set by Sealed Secrets / SOPS / ESO; see W6 HW6.
```

`manifests/12-db-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: db
  namespace: app
  labels: { app: db }
spec:
  replicas: 1
  strategy:
    type: Recreate
    # Recreate (not RollingUpdate) is the right strategy for a single-instance
    # stateful workload. Two Postgres pods cannot share an emptyDir.
  selector:
    matchLabels: { app: db }
  template:
    metadata:
      labels: { app: db }
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          ports:
            - { name: pg, containerPort: 5432 }
          envFrom:
            - configMapRef: { name: db-config }
            - secretRef:    { name: db-secret }
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
          readinessProbe:
            exec:
              command: ["pg_isready", "-U", "appuser", "-d", "appdb"]
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            exec:
              command: ["pg_isready", "-U", "appuser", "-d", "appdb"]
            initialDelaySeconds: 30
            periodSeconds: 10
            failureThreshold: 3
      volumes:
        - name: data
          emptyDir: {}
          # WARNING: emptyDir is wiped when the pod restarts. Data does not survive.
          # For the lab this is fine. For real workloads use a PersistentVolumeClaim.
```

`manifests/13-db-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: db
  namespace: app
spec:
  selector: { app: db }
  ports:
    - { name: pg, port: 5432, targetPort: pg }
```

---

## Step 3 — The Python API

Write a small FastAPI app under `api/`.

`api/app.py`:

```python
"""A small Python API backed by Postgres.

Endpoints:
    GET    /healthz       always 200 OK; for liveness
    GET    /readyz        200 if the DB is reachable, 503 otherwise; for readiness
    GET    /api/items     list all items
    POST   /api/items     create one item; body: {"name": "..."}
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


DB_HOST: str = os.environ.get("DB_HOST", "db.app.svc.cluster.local")
DB_PORT: int = int(os.environ.get("DB_PORT", "5432"))
DB_NAME: str = os.environ.get("DB_NAME", "appdb")
DB_USER: str = os.environ.get("DB_USER", "appuser")
DB_PASSWORD: str = os.environ.get("DB_PASSWORD", "")


def _dsn() -> str:
    return f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"


@contextmanager
def _conn() -> Iterator[psycopg.Connection]:
    """Open a fresh connection per request. Fine for a tiny lab; not for production."""
    with psycopg.connect(_dsn(), connect_timeout=2) as c:
        yield c


app = FastAPI(title="c15-w07-api")


class Item(BaseModel):
    id: int | None = None
    name: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"db not ready: {exc!s}")
    return {"status": "ready"}


@app.get("/api/items")
def list_items() -> list[Item]:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT id, name FROM items ORDER BY id")
        return [Item(id=row[0], name=row[1]) for row in cur.fetchall()]


@app.post("/api/items", status_code=201)
def create_item(item: Item) -> Item:
    with _conn() as c, c.cursor() as cur:
        cur.execute("INSERT INTO items (name) VALUES (%s) RETURNING id", (item.name,))
        new_id = cur.fetchone()[0]
        c.commit()
        return Item(id=new_id, name=item.name)
```

Verify it compiles:

```bash
python3 -m py_compile api/app.py
```

`api/requirements.txt`:

```text
fastapi==0.115.0
uvicorn[standard]==0.32.0
psycopg[binary]==3.2.3
pydantic==2.9.2
```

`api/Dockerfile`:

```dockerfile
FROM python:3.12-alpine
WORKDIR /app
RUN apk add --no-cache build-base postgresql-dev libpq
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py /app/app.py
USER 1000
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

Build and load into kind:

```bash
docker build -t c15-w07-api:dev ./api
kind load docker-image c15-w07-api:dev --name c15-w07-lab
```

---

## Step 4 — The migration Job

A one-shot Job that creates the `items` table.

`manifests/20-migration-job.yaml`:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: migrate
  namespace: app
spec:
  backoffLimit: 6
  template:
    metadata:
      labels: { app: migrate }
    spec:
      restartPolicy: OnFailure
      containers:
        - name: migrate
          image: postgres:16-alpine
          envFrom:
            - configMapRef: { name: db-config }
            - secretRef:    { name: db-secret }
          command:
            - sh
            - -c
            - |
              set -e
              # Wait for the db service to be ready
              until pg_isready -h db.app.svc.cluster.local -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
                echo "waiting for db..."
                sleep 2
              done
              PGPASSWORD="$POSTGRES_PASSWORD" psql \
                -h db.app.svc.cluster.local -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
              CREATE TABLE IF NOT EXISTS items (
                id   SERIAL PRIMARY KEY,
                name TEXT NOT NULL
              );
              INSERT INTO items (name) VALUES ('hello world')
                ON CONFLICT DO NOTHING;
              SQL
              echo "migration complete"
```

The `backoffLimit: 6` means the Job retries up to 6 times if the container exits non-zero. `restartPolicy: OnFailure` means a failed container restarts; a successful exit is final.

---

## Step 5 — The api Deployment and Service

`manifests/30-api-configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config
  namespace: app
data:
  DB_HOST: db.app.svc.cluster.local
  DB_PORT: "5432"
  DB_NAME: appdb
  DB_USER: appuser
  PORT: "8080"
```

`manifests/31-api-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: app
  labels: { app: api }
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate: { maxSurge: 1, maxUnavailable: 0 }
  selector:
    matchLabels: { app: api }
  template:
    metadata:
      labels: { app: api }
    spec:
      containers:
        - name: api
          image: c15-w07-api:dev
          imagePullPolicy: IfNotPresent   # load via kind load; do not pull
          ports:
            - { name: http, containerPort: 8080 }
          envFrom:
            - configMapRef: { name: api-config }
          env:
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-secret
                  key: POSTGRES_PASSWORD
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits:   { cpu: 500m, memory: 256Mi }
          readinessProbe:
            httpGet: { path: /readyz, port: http }
            initialDelaySeconds: 3
            periodSeconds: 3
            timeoutSeconds: 2
            failureThreshold: 3
          livenessProbe:
            httpGet: { path: /healthz, port: http }
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 2
            failureThreshold: 3
```

`manifests/32-api-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: app
spec:
  selector: { app: api }
  ports:
    - { name: http, port: 8080, targetPort: http }
```

---

## Step 6 — The nginx reverse proxy

`manifests/40-nginx-configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nginx-config
  namespace: app
data:
  default.conf: |
    server {
      listen 8080;
      server_name _;
      location /api/ {
        proxy_pass http://api.app.svc.cluster.local:8080/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      }
      location / {
        default_type text/plain;
        return 200 "C15 W07 3-tier app — try /api/items\n";
      }
    }
```

`manifests/41-nginx-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
  namespace: app
  labels: { app: nginx }
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate: { maxSurge: 1, maxUnavailable: 0 }
  selector:
    matchLabels: { app: nginx }
  template:
    metadata:
      labels: { app: nginx }
    spec:
      containers:
        - name: nginx
          image: nginxinc/nginx-unprivileged:1.27-alpine
          ports:
            - { name: http, containerPort: 8080 }
          volumeMounts:
            - name: conf
              mountPath: /etc/nginx/conf.d
          readinessProbe:
            httpGet: { path: /, port: http }
            initialDelaySeconds: 2
            periodSeconds: 3
          livenessProbe:
            httpGet: { path: /, port: http }
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
      volumes:
        - name: conf
          configMap:
            name: nginx-config
            items:
              - key: default.conf
                path: default.conf
```

`manifests/42-nginx-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx
  namespace: app
spec:
  selector: { app: nginx }
  ports:
    - { name: http, port: 80, targetPort: http }
```

---

## Step 7 — Apply, verify, exercise

```bash
# Dry-run client-side (catches YAML syntax errors)
kubectl apply --dry-run=client -f manifests/

# Dry-run server-side (catches schema errors; needs cluster connection)
kubectl apply --dry-run=server -f manifests/

# Apply for real
kubectl apply -f manifests/

# Watch the stack come up
kubectl -n app get pods -w
```

You should see:

1. The `db` pod transitions to `Ready` (about 10 seconds; the `pg_isready` probe is the gate).
2. The `migrate` Job's pod runs (about 5 seconds; it waits for `db`, then creates the schema, then exits 0).
3. The `api` pods transition to `Ready` (about 10 seconds; the `/readyz` probe is the gate, and it depends on the migration having created the `items` table).
4. The `nginx` pods transition to `Ready` (about 5 seconds).

Total time from `kubectl apply` to fully-ready stack: about 30 seconds.

Verify:

```bash
kubectl -n app get all
kubectl -n app get endpointslice  # every Service should have endpoints
kubectl -n app get jobs           # migrate should show 1/1 COMPLETIONS

# Port-forward and exercise
kubectl -n app port-forward svc/nginx 8080:80 &
sleep 2
curl -s http://localhost:8080/
curl -s http://localhost:8080/api/items | jq
curl -s -X POST http://localhost:8080/api/items \
  -H 'Content-Type: application/json' \
  -d '{"name": "C15 Week 7"}'
curl -s http://localhost:8080/api/items | jq

kill %1   # stop port-forward
```

You should see the GET return a JSON list including `"hello world"` (from the migration) and `"C15 Week 7"` (from the POST). The whole loop touches all three tiers: nginx → api → db.

---

## Step 8 — Break and recover, deliberately

The point of this step is to convince yourself the cluster's reconciliation is real.

### Scenario A — The db goes down

```bash
kubectl -n app scale deployment/db --replicas=0
sleep 5
kubectl -n app get pods -l app=api
# The api pods should be Running but READY=0/2 (the /readyz probe fails)
```

Watch the api's events:

```bash
kubectl -n app describe pod -l app=api | tail -30
```

You should see readiness probe failures. The api's Service has zero endpoints; if you try to `curl` through nginx, you get 502 (nginx cannot reach the api).

Bring db back:

```bash
kubectl -n app scale deployment/db --replicas=1
```

Within ~20 seconds the api pods are `Ready` again (waiting for db, then the next probe succeeds). The whole recovery is automatic — you did not restart the api pods, you did not touch nginx.

### Scenario B — Force a rolling update of the api

```bash
# Add a trivial annotation to force a roll (without changing the image)
kubectl -n app patch deployment/api --type=merge \
  -p '{"spec":{"template":{"metadata":{"annotations":{"force-roll":"'$(date +%s)'"}}}}}'
kubectl -n app rollout status deployment/api
```

Watch in another terminal:

```bash
kubectl -n app get pods -l app=api -w
```

You should see a new pod come up, become `Ready`, then an old one terminate; repeat once. The Service's endpoint list updates throughout — at any moment there are at least 2 ready endpoints (because `maxUnavailable: 0`).

### Scenario C — Delete the api Deployment and watch the cascade

```bash
kubectl -n app delete deployment/api
kubectl -n app get pods,rs -l app=api
```

The Deployment is deleted; the ReplicaSet is deleted; the pods are deleted. The api's Service still exists (you did not delete it) but has zero endpoints.

Re-apply to bring it back:

```bash
kubectl apply -f manifests/31-api-deployment.yaml
```

---

## Step 9 — Document and submit

Write `README.md` at the root of `mini-project/` containing:

- The architecture diagram (you can copy the ASCII one above, or draw your own).
- The apply order and the expected time-to-ready.
- The verification commands.
- The teardown command.
- A **post-mortem** of any wrinkles you hit during the build. (Examples: "I forgot to label the api pods correctly and the Service had no endpoints; here is how I diagnosed it." Future-you will thank you.)
- Acknowledgement that the `db` pod uses an `emptyDir` volume, what that means, and what you would change to make the data persistent (a `PersistentVolumeClaim` with a `StorageClass` — `kind`'s default is `standard` via the local-path provisioner).

Commit:

```bash
cd ~/c15/week-07/mini-project
git init -b main
git add manifests/ api/ README.md
git commit -m "mini-project: 3-tier app on kind"
gh repo create c15-week-07-mini-$USER --public --source=. --remote=origin
git push -u origin main
```

---

## Step 10 — Tear down

```bash
kubectl delete namespace app
# Cascade: every resource in the namespace is deleted, including the pods.

# Optional: delete the cluster
kind delete cluster --name c15-w07-lab
```

If you want to keep the cluster for Week 8 (we will use it briefly), do not delete it. If RAM is at a premium, delete it; bring-up is 60 seconds.

---

## Common errors

- **`Pod has unbound immediate PersistentVolumeClaims`** — you wrote a PVC and `kind`'s storage class did not bind. The `kind` defaults include the `standard` storage class via local-path-provisioner; if it is missing, install it from <https://kind.sigs.k8s.io/docs/user/local-registry/>.
- **`ImagePullBackOff` on the api** — you forgot to `kind load docker-image c15-w07-api:dev`. Without it, the cluster tries to pull from a registry that does not have this image.
- **`migrate` job stuck `Pending`** — the db is not ready yet. The migration container waits in a loop with `pg_isready`; give it 30 seconds.
- **`api` pods stuck `0/2 Ready`** — the readiness probe (`/readyz`) is failing because the db is unreachable, *or* the migration has not run yet (so the `items` table does not exist; `SELECT 1` would still succeed though, so it would be the connection that fails, not the table). Check `kubectl describe pod -l app=api`.
- **`502 Bad Gateway` from nginx** — the api Service has no endpoints (probably the api pods are not Ready). Trace upstream from nginx.

---

## Stretch goals

If you finish early:

1. **Replace `emptyDir` with a `PersistentVolumeClaim`.** Add a PVC of 1Gi, use `standard` storage class, mount it on the db. Verify data survives a pod restart (`kubectl delete pod -l app=db`).
2. **Add a third tier: a worker that polls a queue.** A simple Python script that polls a `tasks` table in the db and processes rows. Run it as a Deployment with 1 replica.
3. **Wire the api's image to a real registry.** Push `c15-w07-api:dev` to your GHCR registry; update the Deployment's image reference; verify the pull succeeds. (This is closer to how you would do it in Week 8.)
4. **Add network policies.** Write a `NetworkPolicy` that denies all ingress to `db` *except* from pods with `app: api` or `app: migrate`. Verify that an unrelated pod (`kubectl run busybox --image=busybox --rm -it -- sh`) cannot reach `db.app.svc.cluster.local:5432`. (Note: `kind`'s default CNI does not enforce NetworkPolicy; you need to install Calico or Cilium. This is a real stretch goal.)

---

## What you have done by the end

You have, with no cloud cost:

- Stood up a Kubernetes cluster.
- Deployed three services that talk to each other by DNS.
- Wired configuration via ConfigMap and secrets via Secret.
- Run a one-shot Job that depends on another service being up.
- Watched the cluster self-heal when you scaled the db to zero.
- Watched a rolling update happen without dropping traffic.

That is the entire Week 7 thesis: **the cluster runs reconciliation loops; your job is to write the desired state; the cluster does the rest**. The same YAML, with one cloud-specific change (the LoadBalancer Service), runs on DigitalOcean's managed Kubernetes — which is exactly what we do in Week 8.

---

*If you find errors in this material, please open an issue or send a PR.*
