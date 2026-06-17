# Lecture 3 — The Core Objects and How They Compose

> **Outcome:** You can write the YAML for a stateless web application from scratch — Deployment + Service + ConfigMap + Secret — without an example to copy from. You can explain why the `Service`'s selector is decoupled from the `Deployment`'s template, and why that decoupling is the single best design choice in the project. You can identify labels and selectors in any YAML you read, and you can predict which pods a Service will route to from its selector. You can describe the four fields every Kubernetes object has (`apiVersion`, `kind`, `metadata`, `spec`) and the field that controllers set (`status`).

The Kubernetes object model is small. Most of what you do day-to-day involves about a dozen resource kinds. By the end of this lecture you will recognize all of them, you will know what fields they have, and you will know how they compose into a running application. The whole point of this lecture is to **demystify the YAML**: there are no magic incantations, only a small grammar applied repeatedly.

The lecture has four parts. Part 1 (Sections 1-3) is the shape every object shares. Part 2 (Sections 4-7) is the workload-side composition: Pod → ReplicaSet → Deployment. Part 3 (Sections 8-10) is the service-side composition: Service → Endpoints → DNS. Part 4 (Sections 11-13) is configuration and binding: ConfigMap, Secret, and the labels-and-selectors mechanism that ties everything together.

---

## 1. The four fields every object has

Every Kubernetes object — every Pod, every Deployment, every Service, every Secret, every CRD-defined resource — has exactly four top-level fields:

```yaml
apiVersion: <string>      # which group + version of the API
kind: <string>            # the resource type
metadata: <object>        # name, namespace, labels, annotations
spec: <object>            # the desired state (you write this)
# status: <object>        # the actual state (the controller writes this)
```

`apiVersion` and `kind` together name the resource type. `metadata` carries the identifiers and the labels. `spec` is your desired state. `status` is the controller's report on the actual state — you do **not** write it; the controller does. Trying to set `status` from `kubectl apply` is a category error; the API server may even reject it depending on the resource.

The four fields are the same for every resource. The grammar is fractal: once you can read one resource, you can read all of them. The differences live in what is inside `spec`.

> **A subtle exception: `ConfigMap` and `Secret` don't have `spec`.** They have `data` and `stringData` instead, because they are pure key-value containers — there is no "controller computing a status" for them. This is the one place the four-field rule has an exception, and it is a useful one to know.

---

## 2. `apiVersion`

The `apiVersion` field has the shape `<group>/<version>` (or just `<version>` for the core group, which has an empty group name). Examples:

- `v1` — the *core* group (Pods, Services, ConfigMaps, Secrets, Namespaces, Nodes, PersistentVolumes).
- `apps/v1` — the *apps* group (Deployments, ReplicaSets, StatefulSets, DaemonSets).
- `batch/v1` — Jobs, CronJobs.
- `networking.k8s.io/v1` — NetworkPolicy, Ingress.
- `rbac.authorization.k8s.io/v1` — Role, RoleBinding, ClusterRole, ClusterRoleBinding.
- `apiextensions.k8s.io/v1` — CustomResourceDefinition.

The version part (`v1`, `v1beta1`, `v1alpha1`) signals stability. `v1` is stable; the API is frozen and will be supported indefinitely. `v1beta1` is beta — the API is unlikely to change in incompatible ways but it can. `v1alpha1` is alpha — the API can change at any time, may be disabled by default, and is meant for testing. **In 2026, prefer `v1` for everything you write**; if a resource only has `v1beta1`, you live with it.

The grouped APIs (`apps`, `batch`, `networking.k8s.io`) were introduced in 1.6 to keep the core group small. New resources go into a group; the core group is effectively frozen.

You will rarely write `apiVersion` from scratch. The standard pattern is to look at an example, or `kubectl explain <resource>` to see the version your cluster supports.

---

## 3. `metadata` — name, namespace, labels, annotations

The metadata block carries identifiers and free-form key-value strings. The fields you set:

```yaml
metadata:
  name: hello                       # unique within (kind, namespace)
  namespace: default                # the namespace (default if omitted)
  labels:                            # key-value strings; selectors query them
    app: hello
    tier: frontend
    version: v1
  annotations:                       # key-value strings; not selectable
    description: "the hello service"
    deploy-by: "alice@example.com"
```

`name` is the object's identifier. It must be unique within a (`namespace`, `kind`) pair: you can have a Pod named `hello` and a Service named `hello` in the same namespace; you cannot have two Pods named `hello` in the same namespace.

`namespace` is the soft-tenancy boundary. Most resources are namespaced (Pods, Deployments, Services, ConfigMaps, Secrets, ...); some are cluster-scoped (Nodes, PersistentVolumes, Namespaces themselves, ClusterRoles, CRDs). Default is `default` if omitted.

**`labels` vs `annotations`** — the single most important distinction in `metadata`:

- **Labels** are queryable. Selectors run against labels. The cluster uses labels to wire Services to Pods, Deployments to ReplicaSets, ReplicaSets to Pods. Labels should be short, structured, and used.
- **Annotations** are not queryable. They are key-value strings that *humans* read or that *tools* read. The build commit SHA, the operator's email, the deploy timestamp, a description — all annotations. The cluster does nothing with them.

The convention: if you might ever want to select on a value, it is a **label**. If it is informational, it is an **annotation**. When in doubt, default to annotation — adding a label has consequences (selectors might pick it up unexpectedly), adding an annotation has none.

---

## 4. The Pod

A **Pod** is the unit of scheduling. It is a wrapper around one or more containers that share a network namespace and (optionally) a set of volumes. The pod is what the scheduler places on a node; the containers are what the runtime starts inside the pod's namespace.

The minimal Pod YAML:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: hello
  labels:
    app: hello
spec:
  containers:
    - name: hello
      image: ghcr.io/example/hello:v1
      ports:
        - containerPort: 8080
```

That is a complete, valid Pod. It runs one container; the container is `ghcr.io/example/hello:v1`; the container listens on port 8080 inside the pod's network namespace.

Three things to internalize about Pods:

1. **A Pod is not a container.** A Pod is a wrapper around one or more containers. The wrapper has its own IP, its own network namespace, its own (optional) shared volumes. The containers inside the wrapper share those resources.
2. **You almost never write a bare Pod.** Pods are not self-healing — if the pod dies, nothing brings it back. The shape you write is a `Deployment` (or `StatefulSet`, or `Job`, or `DaemonSet`), and the controller creates Pods from a template. The only place bare Pods are appropriate is debugging (a quick `kubectl run --rm -it busybox -- sh` for a 30-second session).
3. **A multi-container Pod is rare but useful.** The canonical use case is a **sidecar**: a main container plus a helper container (log shipper, metrics exporter, certificate refresher). The two containers share the network namespace, so the sidecar can talk to the main on `localhost`. Multi-container Pods are powerful and easy to overuse; the default should be one container per Pod.

The full Pod spec is dense. The fields you will encounter most often:

| Field | Meaning |
|-------|---------|
| `containers[].name` | A name unique within the pod |
| `containers[].image` | The OCI image reference |
| `containers[].imagePullPolicy` | When to pull (`Always`, `IfNotPresent`, `Never`) |
| `containers[].ports[]` | Declared ports (informational; does not open them) |
| `containers[].env[]` | Environment variables |
| `containers[].envFrom[]` | Bulk env from ConfigMap or Secret |
| `containers[].volumeMounts[]` | Where volumes are mounted in this container |
| `containers[].resources.requests` | Minimum CPU/memory the pod needs (scheduling input) |
| `containers[].resources.limits` | Maximum CPU/memory the pod gets (eviction input) |
| `containers[].readinessProbe` | "Should this pod receive traffic?" |
| `containers[].livenessProbe` | "Is this pod still alive?" |
| `containers[].startupProbe` | A probe that gates the other two during a slow startup |
| `volumes[]` | Volumes defined at the pod level, mounted into containers |
| `restartPolicy` | `Always` (default for Deployments), `OnFailure`, `Never` |
| `serviceAccountName` | The identity the pod's containers use to talk to the API server |
| `nodeSelector` / `affinity` / `tolerations` | Scheduling hints |

The Pod spec has more fields. `kubectl explain pod.spec` lists every one. We will not enumerate them; we will use them as we need them in the exercises.

---

## 5. The ReplicaSet

A **ReplicaSet** is a controller that keeps N copies of a Pod template running. You almost never write a ReplicaSet by hand; you write a Deployment, and the Deployment creates a ReplicaSet for you. But understanding the ReplicaSet makes the Deployment legible.

```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: hello-rs
spec:
  replicas: 3
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
          image: ghcr.io/example/hello:v1
```

The interesting fields:

- **`replicas`** — how many pods the controller should maintain.
- **`selector`** — how the controller identifies "its" pods. The selector matches labels.
- **`template`** — the Pod template. When the controller needs to create a new pod, it copies this template, sets `metadata.ownerReferences` to point at the ReplicaSet, and creates the pod.

**Crucially**, the `template.metadata.labels` must include all the labels in the `selector`. If they do not, the ReplicaSet creates pods, then immediately stops "owning" them (because the selector does not match), then creates more pods to replace them, *forever*. This is a foot-gun the API server now rejects (since 1.16); the rule is enforced.

The ReplicaSet's reconciliation loop:

```
for {
    desired   := watch the ReplicaSet
    matching  := list pods where labels match selector
    diff      := len(matching) vs desired.replicas

    if diff < 0: create pods from template (with owner reference)
    if diff > 0: delete pods (preferring not-Ready ones)

    update status.replicas, status.readyReplicas
}
```

That is the whole controller. The same pattern shape — list desired, list actual, diff, act, update status — is what every controller in the cluster does.

When you `kubectl get pods` and see pods named `hello-rs-abc12-xyz9`, the `abc12` is the ReplicaSet's name hash and `xyz9` is the pod's random suffix. The ReplicaSet owns the pods; when you delete the ReplicaSet, the pods are deleted too (via the `ownerReferences` mechanism).

---

## 6. The Deployment

A **Deployment** is a controller that manages ReplicaSets to roll a new pod template forward and back. It is the resource you actually write for stateless apps.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello
  labels:
    app: hello
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
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
          image: ghcr.io/example/hello:v1
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 2
            periodSeconds: 3
```

The Deployment's reconciliation loop:

1. Watch the Deployment.
2. Compute the hash of the current `spec.template`. If a ReplicaSet exists with that hash, use it; otherwise create a new ReplicaSet.
3. Scale the new ReplicaSet up while scaling the old ReplicaSet down, subject to `maxSurge` (how many extra pods are allowed during a roll) and `maxUnavailable` (how many fewer pods are allowed during a roll).
4. When the new ReplicaSet has reached the desired replica count and the old ReplicaSet has reached zero, the roll is complete.

The shape `maxSurge: 1, maxUnavailable: 0` means: never have fewer than `replicas` pods ready, allow one extra pod during the roll. For `replicas: 3`, this gives a 4-pod peak; the roll is paced one pod at a time. For high-traffic services, this is the default to start from.

When you `kubectl apply` a Deployment with a new image, the controller:

1. Sees the spec.template hash has changed.
2. Creates a new ReplicaSet (`hello-<new-hash>`) with `replicas: 0` initially.
3. Scales the new ReplicaSet from 0 → 1; the new ReplicaSet creates a new pod.
4. Waits for the new pod's `readinessProbe` to pass.
5. Once ready, scales the old ReplicaSet from 3 → 2.
6. Waits for the deletion to settle.
7. Scales the new ReplicaSet from 1 → 2; waits.
8. Scales the old from 2 → 1; waits.
9. Scales the new from 2 → 3; waits.
10. Scales the old from 1 → 0. Done.

The whole sequence takes maybe 30 seconds for a small app. **Rollback** is `kubectl rollout undo deployment/hello`, which scales the old ReplicaSet back up and the new one down using the same algorithm.

> **Status panel — a Deployment in mid-roll**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  DEPLOYMENT — hello (rolling from v1 to v2)         │
> │                                                     │
> │  Desired replicas:           3                      │
> │  Updated replicas (v2):      2  (2 ready)           │
> │  Old replicas (v1):          1  (1 ready)           │
> │  Total ready:                3  (>= desired)        │
> │  Surge in flight:            0  (<= maxSurge=1)     │
> │                                                     │
> │  Status: Progressing                                │
> │  Last transition: 12 s ago                          │
> │  Expected completion: in ~10 s                      │
> └─────────────────────────────────────────────────────┘
> ```

You can watch this with `kubectl rollout status deployment/hello`. It blocks until the roll is done; if the roll stalls (e.g., the new ReplicaSet cannot produce a ready pod), the command times out with a non-zero exit. CI pipelines use this as the deploy gate.

---

## 7. Other workload controllers (for context)

A Deployment is for **stateless** workloads — replicas are interchangeable, any pod can serve any request. Other workload controllers exist for other shapes:

- **`StatefulSet`** — like a Deployment, but with **stable identity** (pod names are `myapp-0`, `myapp-1`, `myapp-2`, not random hashes), **stable persistent volumes** (each pod gets its own PVC), and **ordered rollout** (pod 0 is created first, then 1, then 2; rollouts roll the last-created down first). For databases, queues, anything stateful. We do not write a StatefulSet this week (Postgres in the mini-project runs as a single-replica Deployment for simplicity; we will revisit this in Week 10 with operators).
- **`DaemonSet`** — runs exactly one pod per node (or per labeled subset of nodes). For node-level agents: log shippers, metrics agents, network plugins, CSI drivers. The cluster's own `kindnet` runs as a DaemonSet.
- **`Job`** — runs a pod (or several) to completion. The pod runs, exits 0, and the Job is `Complete`. For batch processing, database migrations, one-shot tasks.
- **`CronJob`** — creates a Job on a schedule. The cluster's cron.

We will use `Deployment` and `Service` exhaustively this week; we will use `Job` briefly in the mini-project (a one-shot Postgres migration); we will not write a `StatefulSet`, `DaemonSet`, or `CronJob` in Week 7.

---

## 8. The Service

A **Service** is a stable virtual IP that selects a set of pods by label. The Service is the binding between "clients that want to reach my pods" and "the actual pods, which come and go."

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
      targetPort: 8080
      protocol: TCP
```

What this YAML says:

- **`type: ClusterIP`** — the Service is reachable inside the cluster on a virtual IP. The other types are `NodePort` (exposed on every node's IP at a fixed port), `LoadBalancer` (provisions a cloud load balancer; we will use this in Week 8), and `ExternalName` (a DNS CNAME; rarely useful).
- **`selector: {app: hello}`** — the Service routes to pods with label `app=hello`. Any pod with that label, in this namespace, is in scope. This is decoupled from the Deployment; the Service does not know or care about the Deployment.
- **`ports[]`** — the port to expose on the Service (`port`) and the port to connect to on the pod (`targetPort`). The cluster handles the translation.

When you create this Service, the cluster:

1. Assigns it a `ClusterIP` from the cluster's service CIDR (e.g., `10.96.42.17`).
2. Registers a DNS name: `hello.default.svc.cluster.local` (and the short forms `hello.default` and just `hello` from within the same namespace).
3. The Endpoints / EndpointSlice controller computes the list of pod IPs matching the selector and writes it to an EndpointSlice resource.
4. kube-proxy on every node reads the EndpointSlice and programs iptables rules so that traffic to `10.96.42.17:80` is DNAT'd to one of the matching pod IPs on port 8080.

From inside the cluster, a client connects to `http://hello/` (or `http://hello.default:80/`) and the connection lands on one of the pods. If the pod set changes (a pod dies, a new one is created), the EndpointSlice updates within seconds and kube-proxy reprograms; the client sees a brief connection failure on a dead pod, retries, and lands on a healthy one.

**The Service's selector is the API surface of the binding.** This is the design choice that makes Kubernetes composable. The Deployment produces pods labeled `app=hello`; the Service selects pods labeled `app=hello`. The two are completely independent — you can change the Deployment without touching the Service, you can change the Service without touching the Deployment, and you can have *two* Deployments (a v1 and a v2 canary) producing pods that the same Service routes to. The label-selector mechanism is what makes blue-green and canary deploys possible.

---

## 9. Endpoints / EndpointSlice

You almost never write an Endpoints or EndpointSlice resource by hand; the cluster computes them. But it is worth seeing what they look like so the abstraction is not magic.

```
$ kubectl get endpointslice -l kubernetes.io/service-name=hello -o yaml
apiVersion: discovery.k8s.io/v1
kind: EndpointSlice
metadata:
  name: hello-abc12
  labels:
    kubernetes.io/service-name: hello
endpoints:
  - addresses: ["10.244.0.5"]
    conditions:
      ready: true
    targetRef:
      kind: Pod
      name: hello-7d4f-x1
  - addresses: ["10.244.0.7"]
    conditions:
      ready: true
    targetRef:
      kind: Pod
      name: hello-7d4f-y2
  - addresses: ["10.244.0.9"]
    conditions:
      ready: false
    targetRef:
      kind: Pod
      name: hello-7d4f-z3
ports:
  - name: ""
    port: 8080
    protocol: TCP
```

Three pod IPs; the third one is `ready: false` (its readiness probe is failing); kube-proxy will *not* include it in the load-balancing pool. When the probe starts passing, the controller updates the EndpointSlice, and kube-proxy reprograms.

`EndpointSlice` is the post-1.21 replacement for the older `Endpoints` resource. They store the same information; `EndpointSlice` shards the list across multiple objects so it scales to thousands of pods per Service. For our purposes they are interchangeable; you may see either in `kubectl get`.

The Endpoints / EndpointSlice is where the readiness probe pays for itself: a pod that is `Running` but `not Ready` is *in the cluster* but *out of the Service*. The Service does not send traffic to it. This is exactly the property you want during a slow startup: the pod takes 20 seconds to warm a cache; the readiness probe fails for 20 seconds; the Service routes around it; the pod becomes ready; traffic flows. No 502s during startup, no human intervention.

---

## 10. Headless services (for context)

A Service with `clusterIP: None` is a **headless** service: there is no virtual IP, no kube-proxy plumbing. The cluster still maintains the EndpointSlice, and DNS returns one A record per ready pod. Clients do their own load balancing.

This is the right shape for stateful workloads where clients need to address individual pods by name. For example, a StatefulSet running a database cluster: each pod has a stable name (`db-0`, `db-1`, `db-2`), and clients need to connect to specific pods (not "any pod in the set"). A headless Service exposes `db-0.db.default.svc.cluster.local` as a DNS name resolving to `db-0`'s IP.

We will not use headless services this week. Mentioned for completeness because you will encounter them as soon as you touch StatefulSets in Week 10.

---

## 11. ConfigMap

A **ConfigMap** is a key-value blob stored in etcd. Its purpose is to inject configuration into pods without baking the configuration into the container image.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hello-config
data:
  LOG_LEVEL: info
  GREETING: "Welcome to C15 Week 7"
  config.yaml: |
    server:
      port: 8080
      timeout: 30s
    features:
      experimental_caching: false
```

The `data` field is a map of string-to-string. The values can be simple (`info`) or multi-line (the `config.yaml` block is a YAML scalar containing more YAML, which the pod will treat as a single file).

A pod consumes a ConfigMap in three shapes:

1. **As environment variables** (individual keys):
   ```yaml
   env:
     - name: LOG_LEVEL
       valueFrom:
         configMapKeyRef:
           name: hello-config
           key: LOG_LEVEL
   ```
2. **As environment variables** (all keys at once):
   ```yaml
   envFrom:
     - configMapRef:
         name: hello-config
   ```
   Every key becomes an environment variable with the same name.
3. **As a mounted file**:
   ```yaml
   # inside containers[]:
   volumeMounts:
     - name: config-volume
       mountPath: /etc/hello
   # at pod.spec level (sibling of containers):
   volumes:
     - name: config-volume
       configMap:
         name: hello-config
   ```
   Each key in the ConfigMap becomes a file at `/etc/hello/<key>`; the file's content is the value. So `/etc/hello/config.yaml` contains the multi-line YAML block above.

**The gotcha**: updating a ConfigMap does **not** restart pods that use it. If you change `LOG_LEVEL` from `info` to `debug`, existing pods continue to see `info` in their env vars (env vars are set at pod start; the env var values are a snapshot). For *mounted files*, the cluster does eventually propagate the update (within 30-60 seconds, asynchronously), but the application has to detect the file change and reload its config. Many apps do not.

The 2026 conventions for "I changed the config; how do I make the pods notice":

- **Rolling deploy** — trigger a Deployment rollout (`kubectl rollout restart deployment/hello`). The pods restart and pick up the new config. This is the most reliable approach.
- **Annotate the Deployment with the ConfigMap's hash** — your CI or `helm` computes the SHA of the ConfigMap and writes it as an annotation on the Deployment's `spec.template.metadata.annotations`. A changed ConfigMap → changed hash → changed template → automatic rollout. This is what `helm` does by default; if you write YAML by hand, you build it yourself or you use `kustomize`'s `configMapGenerator`.

---

## 12. Secret

A **Secret** is a key-value blob, *very similar* to a ConfigMap, with these differences:

1. **Values are base64-encoded on the wire** (not a security feature; a byte-safety feature so you can store binary data and YAML-incompatible characters).
2. **Encryption-at-rest in etcd** is opt-in via the API server's encryption provider. Without it, secrets are *not encrypted* — they are base64-encoded, which is trivially reversible.
3. **Tighter RBAC by convention** — most clusters restrict `get secrets` more aggressively than `get configmaps`. The `secret` is a hint to operators, not a security guarantee.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: hello-secret
type: Opaque
stringData:
  DATABASE_PASSWORD: "fake-password-please-rotate"
  api_key: "fake-api-key"
```

`stringData` is the convenience field that lets you write plaintext values; the cluster base64-encodes them on the way into etcd. The actual stored representation uses the `data` field with already-encoded values:

```yaml
data:
  DATABASE_PASSWORD: ZmFrZS1wYXNzd29yZC1wbGVhc2Utcm90YXRl
  api_key: ZmFrZS1hcGkta2V5
```

Both shapes are valid; `stringData` is what you write, `data` is what you see when you `kubectl get secret -o yaml`.

The pod consumes a Secret the same way it consumes a ConfigMap:

```yaml
envFrom:
  - secretRef:
      name: hello-secret
```

or:

```yaml
env:
  - name: DATABASE_PASSWORD
    valueFrom:
      secretKeyRef:
        name: hello-secret
        key: DATABASE_PASSWORD
```

or as mounted files.

**The honest version of Secret's security model**: it is *better than a hardcoded value in the image*, it is *worse than an external secret manager*. The standard production patterns (covered in Week 6 homework Problem 6) are:

- **Sealed Secrets** — encrypt the Secret at rest in the repo; the cluster decrypts on apply.
- **SOPS** — encrypt the file with a key managed elsewhere; the GitOps controller decrypts.
- **External Secrets Operator** — pull from Vault or AWS Secrets Manager at runtime; no secret in the repo.

For this week's exercises, we will use plain Secrets with fake values. Real production deployments use one of the three patterns above.

---

## 13. Labels and selectors — the binding mechanism

Labels are key-value strings on objects' metadata. Selectors are queries against labels. The two together are how Kubernetes wires its objects to each other.

A few examples of selectors in different objects:

- **Service** selects Pods: `spec.selector: {app: hello}` — the Service routes to all Pods labeled `app=hello`.
- **Deployment** selects Pods (via the ReplicaSet's selector): `spec.selector.matchLabels: {app: hello}` — the Deployment owns all Pods labeled `app=hello`.
- **NetworkPolicy** selects Pods: `spec.podSelector.matchLabels: {app: hello}` — the policy applies to all Pods labeled `app=hello`.
- **PodAffinity** / **NodeSelector** — the scheduler uses selectors to pick nodes for pods.

The selector syntax has two flavors:

- **`matchLabels`** — equality on multiple keys (AND semantics):
  ```yaml
  matchLabels:
    app: hello
    tier: frontend
  ```
  matches pods with both `app=hello` AND `tier=frontend`.

- **`matchExpressions`** — set-based:
  ```yaml
  matchExpressions:
    - {key: app, operator: In, values: [hello, world]}
    - {key: tier, operator: NotIn, values: [batch]}
    - {key: experimental, operator: DoesNotExist}
  ```
  matches pods with `app ∈ {hello, world}` AND `tier ∉ {batch}` AND no `experimental` label.

You can combine them; the Service's `spec.selector` only supports `matchLabels` (historical), but most other resources support both.

**The three failure modes of label-based binding** — memorize these; they cause 90% of "Service has no endpoints" incidents:

1. **Selector and Pod labels don't match.** The Deployment's template labels `app: hello` but the Service's selector is `app: helloo` (typo). The Service has zero endpoints; clients see connection refused. Diagnostic: `kubectl get svc hello -o yaml | grep selector` and `kubectl get pods --show-labels` and compare.
2. **The label is missing on the pod.** You added a new container to the pod but forgot to copy the labels from the existing template. The new pods have no labels; nothing selects them. Diagnostic: same as #1.
3. **Two services with overlapping selectors.** Two Services both select `app: hello`; both have endpoints; both are "correct"; client traffic is randomly split between them. Diagnostic: `kubectl get svc -A -o wide` and look for duplicate selectors.

The label-selector mechanism is one of the project's most beautiful design choices. It is also where most beginner mistakes happen. Read the labels on your pods. Read the selectors on your Services. The wiring is in plain sight; the skill is reading it.

---

## 14. Putting it together — a complete stateless app

Here is a complete, correct YAML for a stateless web app. Read it top to bottom; every field should be familiar.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hello-config
  labels:
    app: hello
data:
  LOG_LEVEL: info
  GREETING: "Welcome to C15 Week 7"
---
apiVersion: v1
kind: Secret
metadata:
  name: hello-secret
  labels:
    app: hello
type: Opaque
stringData:
  API_KEY: "fake-api-key-rotate-before-prod"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello
  labels:
    app: hello
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
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
          image: ghcr.io/example/hello:v1
          ports:
            - name: http
              containerPort: 8080
          envFrom:
            - configMapRef:
                name: hello-config
            - secretRef:
                name: hello-secret
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
          readinessProbe:
            httpGet:
              path: /healthz
              port: http
            initialDelaySeconds: 2
            periodSeconds: 3
          livenessProbe:
            httpGet:
              path: /healthz
              port: http
            initialDelaySeconds: 10
            periodSeconds: 10
            failureThreshold: 3
---
apiVersion: v1
kind: Service
metadata:
  name: hello
  labels:
    app: hello
spec:
  type: ClusterIP
  selector:
    app: hello
  ports:
    - name: http
      port: 80
      targetPort: http
      protocol: TCP
```

Trace the wiring:

- The **ConfigMap** and **Secret** carry configuration.
- The **Deployment** creates three pods. The pods are labeled `app: hello`. The pods consume the ConfigMap and Secret via `envFrom`. The pods declare `containerPort: 8080` named `http`.
- The **Service** selects pods with `app: hello` and forwards port 80 → `http` (which is `containerPort: 8080`).

Apply with `kubectl apply -f hello.yaml`. The cluster:

1. Stores the four resources in etcd.
2. The Deployment controller creates a ReplicaSet.
3. The ReplicaSet controller creates three pods.
4. The scheduler binds each pod to a node.
5. Each kubelet starts the container, runs the probes.
6. Once a pod's readiness probe passes, the EndpointSlice controller adds the pod's IP to the Service's EndpointSlice.
7. kube-proxy on every node programs iptables.

Within about 15 seconds of `kubectl apply`, the Service has three endpoints and is serving traffic. You did not run anything imperative; you described the desired state, the cluster converged.

This is the shape of every stateless app you will ever deploy on Kubernetes. The mini-project for this week adds Postgres (a second Deployment + Service) and nginx (a third Deployment + Service acting as a reverse proxy) — three copies of this same shape, wired together by Service names.

---

## 15. Three anti-patterns from this lecture

**Anti-pattern 1 — putting too much in `matchLabels`.** The `selector` on a Deployment is *immutable* after the Deployment is created. If you label your pods `app: hello, version: v1, region: us-east, owner: alice`, and you put all four in the selector, you cannot ever change *any* of them on the pods. You also cannot do a blue-green deploy where the new pods have `version: v2`. The rule: **selectors should have the minimum number of labels needed to identify the workload**. Usually one: `app: hello`. Use other labels (`version`, `region`, `owner`) on the pods for *informational* purposes and for *secondary* selectors (e.g., a separate Service that routes to `app: hello, version: v2` for the canary).

**Anti-pattern 2 — updating a ConfigMap and expecting pods to reload.** ConfigMaps as environment variables are snapshot-at-pod-start; updating the ConfigMap does *not* update running pods. ConfigMaps as mounted files are propagated, but most apps do not detect the change. The reliable shape is: change the ConfigMap, then `kubectl rollout restart deployment/<name>`. Or use a tool (`kustomize`, `helm`) that hashes the ConfigMap into the Deployment's template, so a changed ConfigMap automatically triggers a rollout.

**Anti-pattern 3 — `imagePullPolicy: Always` on a `:latest` tag.** Both halves are wrong. The `:latest` tag is mutable; tomorrow's `:latest` is not today's `:latest`; you cannot rollback. The `imagePullPolicy: Always` makes every pod restart re-pull, which is slow and rate-limited at scale. The correct shape: pin to a content-addressed tag (`:v1.2.3` or a SHA) and let `imagePullPolicy: IfNotPresent` (the default for non-`:latest` tags) do the right thing. The Week 4 image build wrote a commit-SHA tag for exactly this reason.

---

## 16. Closing — the week ahead

You now have the language to talk to the cluster. The exercises this week (`kubectl` fluency, deploying a stateless app, debugging a broken one, writing probes) are the keystrokes for using that language. The mini-project (a three-tier app: nginx → Python API → Postgres on `kind`) is the synthesis.

Next week we move the same three-tier app off `kind` and onto a managed cluster on DigitalOcean (DOKS), with a real ingress controller and TLS via cert-manager. The cluster will be bigger; the YAML you write will be the same. That is the value of having learned the model first: the YAML is portable across every Kubernetes cluster you will ever touch.

---

*If you find errors in this material, please open an issue or send a PR.*
