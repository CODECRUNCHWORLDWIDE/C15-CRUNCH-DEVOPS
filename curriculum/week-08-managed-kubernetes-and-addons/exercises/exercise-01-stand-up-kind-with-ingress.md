# Exercise 1 — Stand Up `kind` with NGINX Ingress

**Time:** 60 minutes (10 min reading, 30 min hands-on, 20 min write-up).
**Cost:** $0.00 (entirely local).
**Cluster:** A new `kind` cluster created specifically for this week. We will recreate it; if you still have last week's, delete it now (`kind delete cluster --name w07`).

---

## Goal

Stand up a `kind` cluster configured so that an NGINX Ingress controller, installed via Helm, can receive traffic on `http://localhost:80` and `https://localhost:443`. This is the foundation for Exercises 2 and 3 and the mini-project.

After this exercise you should have:

- A `kind` cluster named `w08`, configured with `extraPortMappings` on 80, 443, and 30000-32767.
- The `kubernetes/ingress-nginx` Helm chart installed in the `ingress-nginx` namespace.
- A test Deployment + Service + Ingress that you can `curl http://app.localhost/` from your host and receive an HTML response from.

---

## Step 1 — Verify your tools

```bash
kind version
kubectl version --client
helm version --short
docker info | head -1
```

Expected output (versions may differ; the existence of each command is what matters):

```
kind v0.24.0 go1.22.4 darwin/arm64
Client Version: v1.31.0
v3.14.4+gabcde
Server Version: 25.0.5
```

If any one of the four is missing:

| Tool | Install |
|------|---------|
| `kind` | `brew install kind` |
| `kubectl` | `brew install kubectl` |
| `helm` | `brew install helm` |
| `docker` | Docker Desktop, Colima, or Podman with Docker compat |

---

## Step 2 — Write the kind config

`kind` configurations are YAML. Save this as `kind-w08.yaml` somewhere you will remember:

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: w08
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
        hostPort: 80
        protocol: TCP
      - containerPort: 443
        hostPort: 443
        protocol: TCP
```

What every line does:

- `kind: Cluster, apiVersion: kind.x-k8s.io/v1alpha4` — the `kind` config schema. The `v1alpha4` version is stable as of `kind` 0.20+; do not change it.
- `name: w08` — the cluster name. Used in `kubectl` context names and in `kind delete cluster --name w08`.
- `nodes` — the list of nodes. A single-node cluster has one entry, role `control-plane`.
- `kubeletExtraArgs.node-labels: "ingress-ready=true"` — adds a node label that the `ingress-nginx` chart uses to pin its Deployment to a node that has port 80/443 mapped to the host.
- `extraPortMappings` — forward host ports to container ports. Port 80 and 443 on your laptop will reach NGINX inside the kind container.

This config is the canonical "kind for ingress" config from the kind docs at <https://kind.sigs.k8s.io/docs/user/ingress/>. The only thing to think about is whether port 80 or 443 is already in use on your laptop. If you have another local web server running, stop it first or change the host ports to 8080 and 8443 and adjust the rest of this exercise.

---

## Step 3 — Create the cluster

```bash
kind create cluster --config kind-w08.yaml
```

This takes about 60-90 seconds. Watch the output; the last line should be:

```
Set kubectl context to "kind-w08"
```

Verify:

```bash
kubectl cluster-info --context kind-w08
kubectl get nodes
```

You should see one node, named `w08-control-plane`, in `Ready` state. If it is `NotReady`, wait 30 seconds and retry; the CNI takes a moment to initialize.

---

## Step 4 — Install NGINX Ingress with Helm

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.hostPort.enabled=true \
  --set controller.hostNetwork=true \
  --set controller.kind=DaemonSet \
  --set "controller.nodeSelector.ingress-ready=true" \
  --set "controller.tolerations[0].key=node-role.kubernetes.io/control-plane" \
  --set "controller.tolerations[0].operator=Equal" \
  --set "controller.tolerations[0].effect=NoSchedule" \
  --set controller.publishService.enabled=false \
  --set controller.service.type=ClusterIP
```

Flag-by-flag, for the kind-specific bits:

- `controller.hostPort.enabled=true` and `controller.hostNetwork=true` — NGINX binds to ports 80 and 443 on the host network namespace of the node (which, in `kind`, is the Docker container). Combined with the `extraPortMappings`, this forwards your laptop's port 80 to NGINX.
- `controller.kind=DaemonSet` — run one NGINX per node. In a single-node cluster, one pod. Important for kind because we have only one node.
- `controller.nodeSelector.ingress-ready=true` — pin to the node we labeled in the kind config.
- `controller.tolerations[...]` — tolerate the `NoSchedule` taint that `kind`'s control-plane node has by default. Without this, the DaemonSet's pods would not schedule.
- `controller.service.type=ClusterIP` — do not ask the cloud (there is no cloud) for a LoadBalancer. We are using the host port, not a Service IP.

Wait for the rollout:

```bash
kubectl -n ingress-nginx rollout status daemonset/ingress-nginx-controller --timeout=120s
```

You should see something like:

```
daemon set "ingress-nginx-controller" successfully rolled out
```

Verify the pod is running:

```bash
kubectl -n ingress-nginx get pods
```

One pod, status `Running`, ready `1/1`. If it is `Pending`, run `kubectl -n ingress-nginx describe pod ...` and read the events; the most likely cause is the node selector not matching (re-check the kind config).

---

## Step 5 — Verify NGINX is listening on the host port

```bash
curl -v http://localhost/
```

Expected: a `404 Not Found` from NGINX (because there is no Ingress yet) with the `Server: nginx` header in the response. The 404 is *the right answer*; it proves the request reached NGINX. A "connection refused" would mean the port-forwarding did not work.

---

## Step 6 — Deploy a test app

Save as `test-app.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ex01
  labels:
    week: w08
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello
  namespace: ex01
  labels:
    app: hello
spec:
  replicas: 1
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
          image: nginxinc/nginx-unprivileged:1.27-alpine
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
---
apiVersion: v1
kind: Service
metadata:
  name: hello
  namespace: ex01
spec:
  selector:
    app: hello
  ports:
    - port: 80
      targetPort: 8080
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hello
  namespace: ex01
spec:
  ingressClassName: nginx
  rules:
    - host: app.localhost
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

Apply:

```bash
kubectl apply -f test-app.yaml
```

Wait for the pod:

```bash
kubectl -n ex01 wait deploy/hello --for=condition=available --timeout=60s
```

Verify the Ingress has been picked up:

```bash
kubectl -n ex01 get ingress hello
```

You should see one row, with `CLASS: nginx`, `HOSTS: app.localhost`, `ADDRESS:` (may be empty on kind), `PORTS: 80`.

---

## Step 7 — Curl the app

`app.localhost` resolves to `127.0.0.1` on macOS, modern Linux (with systemd-resolved), and Windows 10+ (since the localhost-suffix RFC was widely adopted). If your platform does not, add `127.0.0.1 app.localhost` to your hosts file.

```bash
curl -v http://app.localhost/
```

Expected: a `200 OK` from the `nginxinc/nginx-unprivileged` image, returning its default welcome page. If you get `Host header required` or `404`, you reached NGINX but it did not match an Ingress; double-check the `Host:` header (`curl -H 'Host: app.localhost' http://localhost/` is equivalent).

If you get `connection refused`: port-forwarding is not working. Check `kubectl -n ingress-nginx get pods -o wide` to confirm the NGINX pod is on the node that has the port mapping; check `docker ps` to confirm Docker forwarded port 80 from the host into the kind container.

---

## Step 8 — Take note of the state for Exercise 2

Capture, for your write-up:

1. The output of `kubectl get nodes`.
2. The output of `kubectl -n ingress-nginx get all`.
3. The output of `kubectl -n ex01 get all,ingress`.
4. The first 5 lines of `curl -v http://app.localhost/`.

You will reference Exercise 1's state from Exercises 2 and 3. Do not tear down the cluster.

---

## Step 9 — What to write up

Create `exercises/notes-ex01.md` with:

- A one-paragraph summary: what runs in your cluster now, in your own words.
- Your `kind-w08.yaml` content (or a link to it in your repo).
- The four pieces of state from Step 8, as fenced code blocks.
- One question you still have about how NGINX Ingress works under the hood. (You do not need to answer it.)

The question is the practice. Active engagement with the tools you install is what turns "I followed a tutorial" into "I understand this and I can debug it."

---

## Troubleshooting (most likely to least likely)

1. **`Error: rendered manifests contain a resource that already exists`** — Helm is unhappy because something from a previous attempt is still around. Delete it: `helm uninstall -n ingress-nginx ingress-nginx; kubectl delete ns ingress-nginx`.
2. **The NGINX pod is stuck `Pending`** — the node selector or tolerations are wrong. Run `kubectl -n ingress-nginx describe pod ...` and read the events. Most likely the `ingress-ready=true` label is not on the node (verify with `kubectl get nodes --show-labels`).
3. **`curl: (7) Failed to connect to localhost port 80: Connection refused`** — port 80 is not forwarded into the container. Run `docker ps` and look at the kind cluster's port mapping; if `0.0.0.0:80->80` is not listed, the kind config did not apply.
4. **The NGINX pod is `CrashLoopBackOff`** — port 80 is already in use inside the container, or something else is wrong with the NGINX config. `kubectl -n ingress-nginx logs ...` tells the story.
5. **`app.localhost` does not resolve** — older operating system without localhost-suffix support. Add `127.0.0.1 app.localhost` to `/etc/hosts`.

---

## Cleanup (when you are ready to tear down the whole week)

```bash
kind delete cluster --name w08
```

This removes the cluster entirely; no state survives. For Exercises 2 and 3, leave the cluster running.
