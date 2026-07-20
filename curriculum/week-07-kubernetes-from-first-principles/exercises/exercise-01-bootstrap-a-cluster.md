# Exercise 1 — Bootstrap a `kind` Cluster and Inspect Every Component

**Goal.** Bring up a single-node `kind` cluster on your laptop, inspect every control-plane and data-plane component, and tear it down cleanly. By the end you will have run `kubectl get` against every standard resource and you will have a concrete mental picture of the architecture described in Lecture 2.

**Estimated time.** 60 minutes (15 min setup, 30 min inspection, 15 min writing up).

**Cost.** $0.00 (entirely local; `kind` runs in Docker).

---

## Why we are doing this

Lecture 2 told you the architecture. This exercise puts your hands on it. Every component you read about — the API server, etcd, the scheduler, the controller manager, the kubelet, kube-proxy — is a real Linux process inside a Docker container, and you can see it with `docker exec` and `kubectl get`. The point is to remove the magic.

---

## Setup

### Working directory

```bash
mkdir -p ~/c15/week-07/ex-01-bootstrap
cd ~/c15/week-07/ex-01-bootstrap
```

We will produce a few small files (a kind config, some notes); keep them in this directory. You may commit them to a per-exercise repo or to a weekly repo — your choice.

### Verify your tools

```bash
kind version              # 0.24+
kubectl version --client  # 1.31+
docker info | head -1     # must succeed
```

If `docker info` fails: start Docker Desktop (or Colima, or Podman). `kind` brings up a Kubernetes cluster inside Docker; without a container runtime, the cluster will not start.

---

## Phase 1 — Create the cluster

Write a minimal cluster config:

`kind-config.yaml`:

```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: c15-w07-lab
nodes:
  - role: control-plane
    image: kindest/node:v1.31.0
```

This is a single-node cluster (the control plane and the worker run on the same node — fine for local development; not fine for production). The `image:` field pins to a specific Kubernetes version; without it, `kind` would use its default, which is 1.31+ on `kind` 0.24+ anyway.

Create the cluster:

```bash
kind create cluster --config kind-config.yaml
```

Expected output:

```
Creating cluster "c15-w07-lab" ...
 ✓ Ensuring node image (kindest/node:v1.31.0)
 ✓ Preparing nodes
 ✓ Writing configuration
 ✓ Starting control-plane
 ✓ Installing CNI
 ✓ Installing StorageClass
Set kubectl context to "kind-c15-w07-lab"
```

The first run pulls the node image (~1.5 GB) from `kindest`; subsequent runs are faster. The whole bring-up takes 60-90 seconds on a modern laptop.

Confirm the cluster is up:

```bash
kubectl cluster-info --context kind-c15-w07-lab
# Kubernetes control plane is running at https://127.0.0.1:NNNNN
# CoreDNS is running at https://127.0.0.1:NNNNN/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy

kubectl get nodes
# NAME                        STATUS   ROLES           AGE   VERSION
# c15-w07-lab-control-plane   Ready    control-plane   45s   v1.31.0

kubectl get nodes -o wide
# (includes INTERNAL-IP, OS-IMAGE, KERNEL-VERSION, CONTAINER-RUNTIME)
```

You now have a working Kubernetes cluster on your laptop. The next phases are inspection.

---

## Phase 2 — Inspect the control plane (from outside)

The control plane components run as static pods on the `kind` node. Static pods are pods the kubelet runs from local manifest files on disk, not from the API server — they bootstrap the cluster before the API server is even available.

List them:

```bash
kubectl -n kube-system get pods
```

Expected (your hashes will differ):

```
NAME                                                READY   STATUS    RESTARTS   AGE
coredns-...                                         1/1     Running   0          1m
coredns-...                                         1/1     Running   0          1m
etcd-c15-w07-lab-control-plane                      1/1     Running   0          1m
kindnet-...                                         1/1     Running   0          1m
kube-apiserver-c15-w07-lab-control-plane            1/1     Running   0          1m
kube-controller-manager-c15-w07-lab-control-plane   1/1     Running   0          1m
kube-proxy-...                                      1/1     Running   0          1m
kube-scheduler-c15-w07-lab-control-plane            1/1     Running   0          1m
local-path-provisioner-...                          1/1     Running   0          1m
```

Pick out the components from Lecture 2:

- **`kube-apiserver-c15-w07-lab-control-plane`** — the API server.
- **`etcd-c15-w07-lab-control-plane`** — etcd.
- **`kube-scheduler-c15-w07-lab-control-plane`** — the scheduler.
- **`kube-controller-manager-c15-w07-lab-control-plane`** — the controller manager.
- **`kube-proxy-...`** — kube-proxy (runs as a DaemonSet, one pod per node).
- **`kindnet-...`** — the CNI plugin (`kind`'s default; runs as a DaemonSet).
- **`coredns-...`** — DNS for the cluster.
- **`local-path-provisioner-...`** — a simple storage provisioner (gives us PersistentVolume support).

Inspect the API server's command line:

```bash
kubectl -n kube-system describe pod kube-apiserver-c15-w07-lab-control-plane | head -60
```

You will see the binary path and an absolute *forest* of flags: `--advertise-address`, `--allow-privileged`, `--client-ca-file`, `--enable-admission-plugins`, `--etcd-servers`, `--service-cluster-ip-range`, and many more. The `--etcd-servers` flag is the one to notice: it is **the only place anything talks to etcd**. The API server is the bridge; everything else goes through the API.

Inspect etcd:

```bash
kubectl -n kube-system describe pod etcd-c15-w07-lab-control-plane | head -40
```

etcd's flags include `--data-dir=/var/lib/etcd` (where the data lives), `--listen-client-urls` (the HTTPS endpoints it serves), and `--listen-peer-urls` (peer-to-peer for HA; in `kind` there is only one etcd, so this is unused but still configured).

---

## Phase 3 — Inspect the control plane (from inside)

`kind` runs each "node" as a Docker container. You can `docker exec` into the node to see what is running there.

Find the container name:

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep c15-w07-lab
# c15-w07-lab-control-plane   kindest/node:v1.31.0   Up 5 minutes
```

Open a shell:

```bash
docker exec -it c15-w07-lab-control-plane bash
```

You are now inside the "node" — a Docker container that is acting as a Kubernetes node. Look at what is running:

```bash
ps auxf | head -40
```

You will see (among other things):

- **`/usr/local/bin/containerd`** — the container runtime, running as a system process.
- **`/usr/bin/kubelet ...`** — the kubelet, also a system process. Notice its flags: `--config`, `--container-runtime-endpoint`, `--node-ip`, `--node-labels`.
- The static-pod containers running inside containerd (kube-apiserver, etcd, kube-scheduler, kube-controller-manager, etc.).

Note carefully: **the kubelet and containerd are system processes (running directly on the node), but the API server, etcd, scheduler, and controller manager are inside containers**. This is the bootstrap chicken-and-egg solved by static pods — the kubelet starts first, reads its local manifest directory, starts the API server and etcd as containers, and only then is the cluster's normal scheduling loop available.

Look at the static pod manifests:

```bash
ls /etc/kubernetes/manifests/
# etcd.yaml
# kube-apiserver.yaml
# kube-controller-manager.yaml
# kube-scheduler.yaml

cat /etc/kubernetes/manifests/etcd.yaml
```

These four YAML files are what the kubelet reads at startup. They are static — the kubelet does not get them from the API server (which does not exist yet at boot). The kubelet starts the containers described in these manifests; once etcd and the API server are up, the cluster can boot the rest of itself.

Exit the container:

```bash
exit
```

---

## Phase 4 — Inspect every standard resource

Back on your laptop, run `kubectl api-resources` to see every resource the API server knows about:

```bash
kubectl api-resources | head -30
```

Expected (truncated):

```
NAME              SHORTNAMES   APIVERSION   NAMESPACED   KIND
bindings                       v1           true         Binding
componentstatuses cs           v1           false        ComponentStatus
configmaps        cm           v1           true         ConfigMap
endpoints         ep           v1           true         Endpoints
events            ev           v1           true         Event
limitranges       limits       v1           true         LimitRange
namespaces        ns           v1           false        Namespace
nodes             no           v1           false        Node
persistentvolumeclaims  pvc    v1           true         PersistentVolumeClaim
persistentvolumes pv          v1           false        PersistentVolume
pods              po           v1           true         Pod
podtemplates                   v1           true         PodTemplate
replicationcontrollers rc      v1           true         ReplicationController
resourcequotas    quota        v1           true         ResourceQuota
secrets                        v1           true         Secret
serviceaccounts   sa           v1           true         ServiceAccount
services          svc          v1           true         Service
...
```

Three columns to internalize:

- **`SHORTNAMES`** — abbreviations you can use in commands (`kubectl get cm` for ConfigMaps, `kubectl get po` for Pods, `kubectl get svc` for Services, `kubectl get deploy` for Deployments).
- **`APIVERSION`** — the group/version we covered in Lecture 3. `v1` is the core group; `apps/v1`, `batch/v1`, `networking.k8s.io/v1` are the grouped APIs.
- **`NAMESPACED`** — whether the resource lives inside a namespace (most) or is cluster-scoped (Nodes, PersistentVolumes, Namespaces themselves, ClusterRoles, CRDs).

List a few things:

```bash
kubectl get namespaces
# NAME                 STATUS   AGE
# default              Active   5m
# kube-node-lease      Active   5m
# kube-public          Active   5m
# kube-system          Active   5m
# local-path-storage   Active   5m

kubectl get all --all-namespaces
# (every pod, service, deployment, daemonset, replicaset, statefulset, job in every namespace;
#  notice the kube-system namespace has most of the cluster's plumbing)
```

The four built-in namespaces:

- **`default`** — where your stuff goes if you do not specify a namespace.
- **`kube-system`** — the cluster's own components.
- **`kube-public`** — readable by everyone (including unauthenticated users); used for cluster-public data.
- **`kube-node-lease`** — used internally for node heartbeats (one Lease object per node).
- **`local-path-storage`** — `kind`-specific; the local-path storage provisioner.

---

## Phase 5 — See the API server's HTTPS calls

The `--v=8` flag on `kubectl` prints every HTTP call the client makes. Try it:

```bash
kubectl get pods -n kube-system --v=8 2>&1 | head -50
```

You will see lines like:

```
GET https://127.0.0.1:NNNNN/api/v1/namespaces/kube-system/pods?limit=500
Response Headers: ...
Response Body: { "kind": "PodList", "apiVersion": "v1", ... }
```

This is the truth of `kubectl`: it is a thin HTTPS client. Every command you run is one or more HTTPS requests to the API server. The same API is available to any program — your CI scripts, custom controllers, observability tools, GitOps reconcilers (Week 6). `kubectl` is one client among many.

Find the API server endpoint:

```bash
kubectl cluster-info | grep "control plane"
# Kubernetes control plane is running at https://127.0.0.1:NNNNN
```

You can `curl` it directly (you need the cluster's auth):

```bash
TOKEN=$(kubectl create token default)
curl -sk -H "Authorization: Bearer $TOKEN" https://127.0.0.1:NNNNN/healthz
# ok
```

(You may need to grant the `default` service account some permissions to do this; the `/healthz` endpoint is anonymous, so the above should work without RBAC.)

---

## Phase 6 — Watch the cluster react

Open two terminals. In Terminal 1:

```bash
kubectl get pods --all-namespaces -w
```

The `-w` flag streams updates. Leave it running.

In Terminal 2:

```bash
kubectl run hello --image=nginx --port=80
# pod/hello created
```

Watch Terminal 1. You will see:

```
default   hello   0/1   Pending             0   0s
default   hello   0/1   ContainerCreating   0   1s
default   hello   1/1   Running             0   4s
```

Three state transitions in 4 seconds. This is the cluster's reconciliation loop firing:

1. Pod created → API server stores it → scheduler picks a node → status: `Pending`.
2. Scheduler binds the pod to the node → kubelet sees the binding → starts pulling the image → status: `ContainerCreating`.
3. Image pulled → container started → readiness probe (none defined; defaults to ready) → status: `Running`.

Delete the pod:

```bash
kubectl delete pod hello
# pod "hello" deleted
```

In Terminal 1 you see:

```
default   hello   1/1   Terminating   0   30s
default   hello   0/1   Terminating   0   30s
default   hello   0/1   Terminating   0   30s
```

Then the pod is gone. **It does not come back.** This is because `kubectl run` created a *bare* pod, with no controller above it. The pod's death is final.

Now do the right thing — create a Deployment:

```bash
kubectl create deployment hello --image=nginx --port=80 --replicas=2
# deployment.apps/hello created
```

Watch Terminal 1:

```
default   hello-7df45-x   0/1   Pending             0   0s
default   hello-7df45-x   0/1   ContainerCreating   0   1s
default   hello-7df45-x   1/1   Running             0   4s
default   hello-7df45-y   0/1   Pending             0   0s
default   hello-7df45-y   0/1   ContainerCreating   0   1s
default   hello-7df45-y   1/1   Running             0   3s
```

Two pods. Delete one:

```bash
kubectl delete pod hello-7df45-x
```

Watch Terminal 1:

```
default   hello-7df45-x   1/1   Terminating          0   1m
default   hello-7df45-z   0/1   Pending              0   0s
default   hello-7df45-z   0/1   ContainerCreating    0   1s
default   hello-7df45-z   1/1   Running              0   3s
```

The deleted pod went away; the Deployment's reconciliation loop saw a missing replica; a new pod was created. **You did not write code to make this happen.** The Deployment controller did the work.

Stop the watch in Terminal 1 with Ctrl-C. Delete the Deployment:

```bash
kubectl delete deployment hello
# deployment.apps "hello" deleted
```

The Deployment is deleted; the ReplicaSet (which was owned by the Deployment) is deleted; the pods (owned by the ReplicaSet) are deleted. The `ownerReferences` mechanism handles the cascade.

---

## Phase 7 — Write up what you saw

Create `notes.md` in `~/c15/week-07/ex-01-bootstrap/`. Answer:

1. **List the eight pods running in `kube-system` after cluster bring-up. Name what each one does in one sentence.**
2. **What is the role of `/etc/kubernetes/manifests/` inside the `kind` node? Why does it exist?**
3. **When you ran `kubectl get pods -n kube-system --v=8`, what HTTP path did `kubectl` GET?**
4. **What happened to the bare Pod `hello` when you deleted it? What happened to a Deployment-managed pod when you deleted it? Name the architectural difference in one sentence.**
5. **What is the relationship between a Deployment, a ReplicaSet, and a Pod, in terms of `ownerReferences`?**

Aim for one paragraph per question. The point is to put your understanding in your own words; you will re-read these notes when something breaks in Week 8 or 9, and you will be glad you wrote them.

---

## Phase 8 — Tear down

You can leave the cluster running for the next exercise (we will reuse the same `c15-w07-lab` cluster). Or, if you want to start clean each time:

```bash
kind delete cluster --name c15-w07-lab
# Deleting cluster "c15-w07-lab" ...
# Deleted nodes: ["c15-w07-lab-control-plane"]
```

Bring-up is 60-90 seconds; tear-down is 10 seconds. The penalty for "delete and recreate" is small enough that you should do it whenever you want a clean slate.

---

## Acceptance

- [ ] `kubectl cluster-info` returns a healthy control-plane URL.
- [ ] `kubectl get nodes` shows one `Ready` node named `c15-w07-lab-control-plane`.
- [ ] `kubectl -n kube-system get pods` shows the eight control-plane / data-plane pods listed in Phase 2.
- [ ] You have run `kubectl --v=8` and seen the HTTPS requests.
- [ ] You have watched `kubectl get pods -w` while creating and deleting workloads.
- [ ] `notes.md` answers the five questions in Phase 7.

---

## Common errors

- **`Cannot connect to the Docker daemon`** — Docker is not running. Start Docker Desktop (or `colima start`, or your Podman daemon).
- **`failed to create cluster: node already exists`** — a previous `kind` cluster with the same name is still around. Run `kind delete cluster --name c15-w07-lab` and retry.
- **`error: error loading config file ... no such host`** — `kubectl` is pointing at a stale kubeconfig context. Run `kubectl config use-context kind-c15-w07-lab`.
- **`The connection to the server was refused`** — the cluster is not up yet, or the kubeconfig is wrong. Wait 30 seconds; if the error persists, `kind delete cluster --name c15-w07-lab` and recreate.

---

*If you find errors in this material, please open an issue or send a PR.*
