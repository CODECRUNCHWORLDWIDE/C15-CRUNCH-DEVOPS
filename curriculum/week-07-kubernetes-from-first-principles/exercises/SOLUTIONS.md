# Week 7 — Exercise Solutions

Worked answers, expected output, and the diagnostic questions to ask when your output diverges. Try each exercise yourself first; check the solution only when you are stuck for more than 10 minutes. The point is not "did you get the right output" but "do you understand why the output is what it is."

---

## Exercise 1 — Bootstrap a Cluster

### Phase 7, write-up questions

**Q1 — List the eight pods running in `kube-system` after cluster bring-up. Name what each one does in one sentence.**

| Pod | What it does |
|-----|--------------|
| `kube-apiserver-...` | Serves the cluster's REST API. Every read and every write goes through it. |
| `etcd-...` | The cluster's database. Strongly-consistent KV store; the only stateful control-plane component. |
| `kube-scheduler-...` | Picks a node for every unscheduled pod. |
| `kube-controller-manager-...` | Runs the built-in controllers (Deployment, ReplicaSet, Job, EndpointSlice, ...). |
| `kube-proxy-...` (DaemonSet) | Programs iptables on each node so Service virtual IPs are load-balanced. |
| `kindnet-...` (DaemonSet) | The CNI plugin. Assigns pod IPs and provides cluster networking. |
| `coredns-...` (2 replicas) | Cluster DNS. Resolves `service-name.namespace.svc.cluster.local` to Service IPs. |
| `local-path-provisioner-...` | `kind`-specific. Provisions PersistentVolumes from `hostPath` on the node. |

If you saw a different list, your `kind` cluster is on a different image or has additional add-ons. The names above are the defaults for `kindest/node:v1.31.0`.

**Q2 — What is the role of `/etc/kubernetes/manifests/` inside the `kind` node? Why does it exist?**

It is the **static pod manifest directory**. The kubelet watches this directory at startup; for every YAML file it finds, it runs the described pod *without* going through the API server. This is how the API server itself starts — the kubelet starts before the API server is available, reads `kube-apiserver.yaml`, and starts the API server as a container. Once the API server is up, the rest of the cluster boots normally. Static pods solve the chicken-and-egg problem of "you cannot post to the API server to start the API server."

**Q3 — When you ran `kubectl get pods -n kube-system --v=8`, what HTTP path did `kubectl` GET?**

`GET /api/v1/namespaces/kube-system/pods?limit=500`. The shape is `/<group>/<version>/namespaces/<ns>/<resource>`. The core group has no group name, so its prefix is `/api/v1/` (other groups are at `/apis/<group>/<version>/`). The `limit=500` is `kubectl`'s default page size.

**Q4 — What happened to the bare Pod `hello` when you deleted it? What happened to a Deployment-managed pod when you deleted it? Name the architectural difference in one sentence.**

The bare pod was deleted and did not come back. The Deployment-managed pod was deleted and a new pod with a different name (the Deployment's ReplicaSet creates pods with random suffixes) was created within seconds. The architectural difference: **a Deployment has a controller running a reconciliation loop that ensures the number of replicas matches the spec; a bare pod has no controller**.

**Q5 — What is the relationship between a Deployment, a ReplicaSet, and a Pod, in terms of `ownerReferences`?**

The Deployment owns one or more ReplicaSets (one per template hash; only one is "current" at a time). Each ReplicaSet owns N pods. The chain is reified in `metadata.ownerReferences` on each child: a pod's `ownerReferences[0]` points at its ReplicaSet; the ReplicaSet's `ownerReferences[0]` points at the Deployment. Deleting an owner cascades to the children via the **garbage collector**: when you `kubectl delete deployment/hello`, the Deployment is deleted first; the GC then deletes the ReplicaSet (now an orphan); the GC then deletes the pods.

You can see this:

```bash
kubectl get pod hello-7d4f-aaa -o jsonpath='{.metadata.ownerReferences}' | jq
```

```json
[
  {
    "apiVersion": "apps/v1",
    "kind": "ReplicaSet",
    "name": "hello-7d4f",
    "uid": "...",
    "controller": true,
    "blockOwnerDeletion": true
  }
]
```

---

## Exercise 2 — `kubectl` Fluency

### Phase 8, write-up questions

**Q1 — What is the difference between `kubectl create -f` and `kubectl apply -f` semantically?**

`kubectl create -f` is "**create** this object; fail if it already exists." It is not idempotent — re-running it on a file that produced an object returns `AlreadyExists`.

`kubectl apply -f` is "**make the cluster's state match** this object; create if absent, patch if present." It is idempotent. Internally, `apply` stores the last-applied configuration in an annotation (`kubectl.kubernetes.io/last-applied-configuration`) on the object; subsequent applies compute a three-way merge between (a) the last-applied annotation, (b) the live state, (c) the new YAML. The result is patched in.

This makes `apply` safe to run from CI on every commit, regardless of whether the resource exists.

**Q2 — Give two cases where `-o jsonpath` is the right tool, and one case where `-o json | jq` is better.**

JSONPath is right when:

1. You want one or a few fields and the structure is simple. `kubectl get pod foo -o jsonpath='{.status.podIP}'` is shorter and faster than piping to `jq`.
2. You are writing a script that should work without external dependencies. `jsonpath` is built into `kubectl`; `jq` is a separate install. Bash scripts that target many environments prefer `jsonpath`.

`jq` is better when:

1. You want to transform the output (compute fields, filter, group). For example, "list every pod and the sum of its CPU requests across containers" is awkward in `jsonpath` but natural in `jq`.

**Q3 — You see a pod in `ImagePullBackOff`. List the `kubectl` commands you run, in order, to diagnose the root cause.**

```bash
kubectl get pods                          # confirm the state
kubectl describe pod <name>               # READ THE EVENTS section
# Events will say things like "Failed to pull image ...":
#   - check the image reference for typos
#   - check the registry's access (private image without an imagePullSecret)
#   - check the network (can the node reach the registry?)
```

If `describe` doesn't tell you what you need:

```bash
kubectl get events -n <ns> --sort-by='.lastTimestamp' | tail -20  # cluster-wide events
kubectl logs <name> --previous                                    # if it ever ran
```

If the image reference is correct and the registry is reachable, the issue is usually authentication: the pod's namespace lacks the `imagePullSecret` for the registry, or the secret is wrong.

**Q4 — Write a one-line `kubectl get` command that prints the name and node for every pod in every namespace.**

```bash
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\t"}{.spec.nodeName}{"\n"}{end}'
```

Or, using `jq`:

```bash
kubectl get pods -A -o json | jq -r '.items[] | "\(.metadata.namespace)/\(.metadata.name)\t\(.spec.nodeName)"'
```

Both produce a tab-separated list. The `jsonpath` version is the no-external-deps choice; the `jq` version is more readable.

**Q5 — What is the difference between `kubectl logs pod-name` and `kubectl logs pod-name --previous`? When do you need each?**

`kubectl logs pod-name` returns the logs of the *current* container in the pod. If the container has restarted, this is the logs of the new instance — which has been running for whatever time has elapsed since the restart, often a few seconds.

`kubectl logs pod-name --previous` returns the logs of the *previous* container (the one that exited and was restarted). This is what you want when a pod is in `CrashLoopBackOff`: the current container is freshly-started and has nothing interesting yet; the *previous* container is the one that crashed, and its logs hold the cause.

The mental rule: **when a pod has restarted, you want `--previous`**. When it has not, the default suffices.

---

## Exercise 3 — Deploy a Stateless App

### The 10-step walkthrough — what you should have seen

**Step 1 (apply)** — output exactly as shown in the manifest. If a resource shows `unchanged`, you already applied; if anything errors, fix it and reapply.

**Step 2 (pods come up)** — three pods, transitioning Pending → ContainerCreating → Running, then READY=0/1 → 1/1 after the readiness probe passes (a few seconds after Running). Total elapsed: 10-15 seconds.

**Step 3 (kubectl get all)** — expected output (your hashes will differ):

```
NAME                         READY   STATUS    RESTARTS   AGE
pod/hello-5d4f7c98c-aaa      1/1     Running   0          30s
pod/hello-5d4f7c98c-bbb      1/1     Running   0          30s
pod/hello-5d4f7c98c-ccc      1/1     Running   0          30s

NAME            TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
service/hello   ClusterIP   10.96.196.137   <none>        80/TCP    30s

NAME                    READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/hello   3/3     3            3           30s

NAME                               DESIRED   CURRENT   READY   AGE
replicaset.apps/hello-5d4f7c98c    3         3         3       30s
```

If your Deployment shows `0/3` ready, the readiness probe is failing. Check `kubectl describe pod` for the probe's events.

**Step 4 (EndpointSlice)** — three endpoints, all `ready: true`. Each endpoint maps to one of the three pod IPs.

If you see fewer than three endpoints, one or more pods are not ready (readiness probe failing); investigate with `kubectl describe pod`.

If you see *zero* endpoints, the Service's selector does not match the pods' labels. Common cause: typo in the selector. Compare `kubectl get svc hello -o yaml | grep -A2 selector` with `kubectl get pods --show-labels`.

**Step 5 (env vars)** — all four variables should be present:

```
LOG_LEVEL=info
GREETING=Welcome to C15 Week 7 — Kubernetes from First Principles
API_KEY=fake-api-key-rotate-before-prod
DATABASE_URL=postgres://fake:fake@db.ex03.svc.cluster.local:5432/hello
```

If `LOG_LEVEL` or `GREETING` is missing, the ConfigMap is not being applied correctly; check `kubectl get cm hello-config -o yaml`.

**Step 6 (port-forward + curl)** — the nginx welcome page. If you see "connection refused," the port-forward did not bind; check that another process is not using port 8080 on your laptop.

**Step 7 (rolling update)** — `kubectl rollout status` should show the roll progressing pod-by-pod. Total roll time: about 30 seconds. During the roll, `kubectl get pods` shows up to 4 pods (3 desired + maxSurge=1).

**Step 8 (rollback)** — the rollback uses the same algorithm in reverse. `kubectl rollout history deployment/hello` will show two revisions; `--revision=N` on `kubectl rollout history` shows what was in each.

**Step 9 (self-heal)** — when you force-delete all three pods, the ReplicaSet's reconciliation loop notices `actual=0, desired=3` and creates three new pods. The new pods have new names (different random suffixes). Time-to-recovery: about 5-10 seconds.

**Step 10 (tear down)** — the namespace deletion cascades. `kubectl get ns ex03` returns `NotFound` once cleanup completes (usually within 10 seconds).

### Phase 11, write-up questions

**Q1 — The `selector` in the Service and the `selector.matchLabels` in the Deployment both contain `app: hello`. What happens if you change the Deployment's selector but not the Service's? What happens the other way around?**

If you change the Deployment's selector and not the Service's: the API server will reject the change to the Deployment, because **the Deployment's selector is immutable** since 1.16. To "change" it, you delete the Deployment and recreate it.

If you change the Service's selector and not the Deployment's: the Service's endpoints recompute. If the new selector matches the existing pods, nothing happens (the endpoints are the same). If it matches a different set of pods (or none), the endpoints shift; clients of the Service see traffic routed to different pods (or none).

The Service's selector being mutable is the *feature* that makes blue-green and canary deploys possible: you can switch the Service from `version: v1` to `version: v2` instantly, and traffic shifts.

**Q2 — The readiness probe and the liveness probe both call HTTP GET / on port `http`. Why does the project distinguish them, given they call the same endpoint? What is the operational difference between a readiness failure and a liveness failure?**

They are **different actions** with **different consequences**:

- **Readiness failure** → the pod is *removed from the Service's endpoint list*. It is still alive; it is still running; it is just not in the load-balancing pool. When readiness recovers, the pod is added back. This is the right action for "I am temporarily overloaded; don't send me more for a moment."
- **Liveness failure** → the *container is restarted*. The pod's IP may or may not change (it does not change in Kubernetes; the same Pod is reused with a new container instance), but the container is killed and a new one is started. This is the right action for "I am wedged; only a restart will recover me."

Calling the same endpoint is fine *as long as the endpoint is sensitive to both conditions*. For real applications you often want separate endpoints: `/healthz` for liveness (just "is the process responsive") and `/readyz` for readiness ("are my downstream dependencies reachable"). We use `/` here because nginx serves a 200 on `/` and we are not writing the application code.

**Q3 — When you ran `kubectl set image` in Step 7, which controller(s) did the work? Trace the chain from your `kubectl` invocation to the new pod being Running.**

1. **`kubectl`** computes a PATCH to the Deployment's `spec.template.spec.containers[0].image` field and sends it to the API server.
2. **API server** authenticates, authorizes, validates, mutates, persists to etcd, notifies watchers.
3. **Deployment controller** sees the watch event; computes that `spec.template`'s hash has changed; creates a new ReplicaSet with the new template hash; sets `replicas: 0` on it initially.
4. **Deployment controller** scales the new ReplicaSet from 0→1 (subject to `maxSurge=1`).
5. **ReplicaSet controller** sees the new ReplicaSet wants 1 pod; creates a pod from the new template (with owner reference back to the ReplicaSet).
6. **Scheduler** sees the new unscheduled pod; picks a node; writes the binding.
7. **kubelet** on the bound node sees the binding (via its watch filtered by `nodeName`); pulls the new image; starts the container.
8. **kubelet** runs the readiness probe; once it passes, marks the pod ready and reports the new container status.
9. **EndpointSlice controller** sees the new ready pod; adds it to the Service's EndpointSlice.
10. **kube-proxy** sees the EndpointSlice update; reprograms iptables to include the new pod.
11. **Deployment controller** sees the new ReplicaSet has 1 ready pod; scales the old ReplicaSet from 3→2.
12. ReplicaSet controller deletes a pod; loop repeats two more times.

Three controllers (Deployment, ReplicaSet, EndpointSlice), the scheduler, and kubelet/kube-proxy on each node. You patched one field; the rest is the cluster's machinery.

**Q4 — In Step 9, you deleted all three pods. Three new ones appeared. Name the controller that created the new ones, and the level-triggered property of the reconciliation loop that made this work without any per-event handling.**

The **ReplicaSet controller** created the new pods. Its reconciliation loop is **level-triggered**: it does not handle individual "pod was deleted" events; it just compares the current pod count (filtered by selector) to the desired replica count, and acts on the diff. When you deleted three pods, the next loop saw `actual=0, desired=3` and created three pods. If you had deleted one pod, the next loop would have seen `actual=2, desired=3` and created one pod. The same code path handles every case; there is no per-event state machine.

This is why Kubernetes controllers are robust: missed events do not matter, because the controller looks at the current state on every loop. If the cluster restarts (or the controller crashes), the controller catches up by simply running the loop.

**Q5 — The Secret has values like "fake-api-key-rotate-before-prod". In a real deploy, where would the real values come from? Name two acceptable sources and one unacceptable source.**

Acceptable:

- **A secrets manager** (HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault) — the External Secrets Operator (or similar) pulls the value at runtime and creates the Secret in the cluster.
- **An encrypted form in git** — SealedSecrets or SOPS-encrypted YAML. The encrypted form is committed; the cluster (or the GitOps controller) decrypts on apply. The key for decryption never leaves the cluster.

Unacceptable:

- **Plaintext in git** — the value is exposed forever in the commit history. Even if you "rotate" the secret later, the old value lives in `git log`. This is the most common mistake new teams make.

---

## How to use these solutions

These solutions are designed to be **read after attempting**. The wrong order is "read the solution, then do the exercise" — that builds the *appearance* of understanding without the substance. The right order is:

1. Attempt the exercise.
2. Get stuck for at most 10 minutes.
3. Read the relevant section of the solution.
4. Go back to the exercise and finish it with the understanding the solution gave you.

If you find yourself reaching for the solution on every step, the prerequisites are wrong — go back to the lecture notes and re-read until the model is clear. The exercises are doable; the solutions are a backstop, not the path.

---

*If you find errors in this material, please open an issue or send a PR.*
