# Exercise 2 — `kubectl` Fluency: `get`, `describe`, `explain`, jsonpath, and the Four Flavours of Object Access

**Goal.** Become fluent in `kubectl`. By the end you will be able to read any resource's structure (via `kubectl explain`), inspect a live resource (via `kubectl get -o yaml`), diagnose problems (via `kubectl describe`), extract specific fields from many resources at once (via `kubectl get -o jsonpath`), and distinguish the four flavours of object access (`run`, `create`, `apply`, `apply --server-side`).

**Estimated time.** 90 minutes (60 min hands-on, 30 min writing up).

**Cost.** $0.00 (entirely local; reuses the `c15-w07-lab` cluster from Exercise 1).

---

## Why we are doing this

`kubectl` is the lingua franca of Kubernetes. The four commands you will use most often — `get`, `describe`, `explain`, `apply` — cover 95% of what an operator does in their first year. The 5% that is left is the difference between an engineer who feels at home in the cluster and one who copies recipes from Stack Overflow. This exercise gets you to the 95%.

The pattern of the exercise is *narrow but deep*: a small number of commands, each one practiced enough times that the muscle memory forms.

---

## Setup

Make sure the cluster from Exercise 1 is up:

```bash
kubectl cluster-info --context kind-c15-w07-lab
# if this errors, run: kind create cluster --config kind-config.yaml
```

Working directory:

```bash
mkdir -p ~/c15/week-07/ex-02-kubectl
cd ~/c15/week-07/ex-02-kubectl
```

---

## Phase 1 — `kubectl get`

The read command. Start broad:

```bash
kubectl get pods
# No resources found in default namespace.
```

(Empty if you ran Exercise 1's Phase 8 cleanup; otherwise some leftover pods.)

Create a test Deployment so you have something to read:

```bash
kubectl create deployment hello --image=nginx --replicas=3 --port=80
# deployment.apps/hello created
```

Wait a few seconds, then:

```bash
kubectl get pods
# NAME                     READY   STATUS    RESTARTS   AGE
# hello-7d4f-aaa           1/1     Running   0          12s
# hello-7d4f-bbb           1/1     Running   0          12s
# hello-7d4f-ccc           1/1     Running   0          12s
```

### The output formatters

`-o wide` adds columns:

```bash
kubectl get pods -o wide
# NAME             READY   STATUS    ... IP           NODE                        NOMINATED NODE   READINESS GATES
# hello-7d4f-aaa   1/1     Running       10.244.0.5   c15-w07-lab-control-plane   <none>           <none>
```

`-o yaml` gives the full object:

```bash
kubectl get pod hello-7d4f-aaa -o yaml | head -60
```

`-o json` gives JSON (useful with `jq`):

```bash
kubectl get pods -o json | jq '.items[0].metadata.name'
# "hello-7d4f-aaa"
```

`-o name` gives just the resource references (great for piping):

```bash
kubectl get pods -o name
# pod/hello-7d4f-aaa
# pod/hello-7d4f-bbb
# pod/hello-7d4f-ccc

kubectl get pods -o name | xargs kubectl describe
# (describe all three pods)
```

### Across namespaces

```bash
kubectl get pods --all-namespaces       # everything everywhere
kubectl get pods -A                     # short form
kubectl get pods -n kube-system         # one namespace
```

### Filtering

By label:

```bash
kubectl get pods -l app=hello                # equality
kubectl get pods -l 'app in (hello, world)'  # set-based
kubectl get pods -l 'app=hello,version!=v0'  # multiple conditions (AND)
```

By field:

```bash
kubectl get pods --field-selector status.phase=Running
kubectl get pods --field-selector spec.nodeName=c15-w07-lab-control-plane
```

Field selectors are restricted to a small set of fields (the API server has to support them); the most commonly useful are `status.phase`, `spec.nodeName`, and `metadata.name`.

### Watching

```bash
kubectl get pods -w
# (streams updates; Ctrl-C to stop)
```

We used this in Exercise 1. Keep it in your reflexes; whenever you do something that should produce a pod, run `kubectl get pods -w` in another terminal first.

---

## Phase 2 — `kubectl describe`

The diagnose command. `describe` shows the object's spec plus the *events* the cluster has emitted about it.

```bash
kubectl describe pod hello-7d4f-aaa
```

Read the output top to bottom. You will see (sections may vary):

- **`Name:` / `Namespace:` / `Labels:`** — identifiers and labels.
- **`Status:`** — `Running` or whatever.
- **`IP:`** — the pod's cluster IP.
- **`Containers:`** — for each container, the image, state, last state (if any restarts), ready, and resource requests/limits.
- **`Conditions:`** — `PodScheduled`, `ContainersReady`, `Initialized`, `Ready` — each with a `True` / `False`.
- **`Volumes:`** — volumes mounted into the pod.
- **`Events:`** — the events the cluster emitted about this pod, in chronological order.

The **Events** section is the most important. It tells you the story of the pod's life: scheduled, image pulled, container created, container started. When something is wrong, the events will say so.

Force an error:

```bash
kubectl set image deployment/hello hello=nginx:does-not-exist
# deployment.apps/hello image updated

kubectl get pods
# NAME                     READY   STATUS             RESTARTS   AGE
# hello-7d4f-aaa           1/1     Running            0          5m
# hello-7d4f-bbb           1/1     Running            0          5m
# hello-7d4f-ccc           1/1     Running            0          5m
# hello-9a8b-xxx           0/1     ImagePullBackOff   0          12s
```

A new pod is in `ImagePullBackOff`. Describe it:

```bash
kubectl describe pod hello-9a8b-xxx
```

Scroll to **Events**:

```
Events:
  Type     Reason          Age   From               Message
  ----     ------          ----  ----               -------
  Normal   Scheduled       30s   default-scheduler  Successfully assigned default/hello-9a8b-xxx to c15-w07-lab-control-plane
  Normal   Pulling         28s   kubelet            Pulling image "nginx:does-not-exist"
  Warning  Failed          27s   kubelet            Failed to pull image "nginx:does-not-exist": ... not found
  Warning  Failed          27s   kubelet            Error: ErrImagePull
  Normal   BackOff         15s   kubelet            Back-off pulling image "nginx:does-not-exist"
  Warning  Failed          15s   kubelet            Error: ImagePullBackOff
```

The events say exactly what is wrong. Read them top to bottom; the cluster is verbose. **This is the single most important `kubectl` skill: when something is broken, your first command is `kubectl describe`, and your first action is reading the events.**

Roll back:

```bash
kubectl rollout undo deployment/hello
# deployment.apps/hello rolled back

kubectl get pods
# (the bad pod is gone; the three old ones remain)
```

---

## Phase 3 — `kubectl explain`

The man-page command. Every resource has a `spec` schema; `kubectl explain` documents it from the cluster itself (no Internet required).

Start at the top:

```bash
kubectl explain pod
```

```
KIND:       Pod
VERSION:    v1

DESCRIPTION:
    Pod is a collection of containers that can run on a host. ...

FIELDS:
  apiVersion <string>
  kind <string>
  metadata <ObjectMeta>
  spec <PodSpec>
  status <PodStatus>
```

Drill into a sub-field with dotted notation:

```bash
kubectl explain pod.spec
```

```
FIELDS:
  activeDeadlineSeconds <integer>
  affinity <Affinity>
  containers <[]Container> -required-
  dnsConfig <PodDNSConfig>
  ...
```

Drill further:

```bash
kubectl explain pod.spec.containers
```

You will see every field on a container, with its type and description. Keep drilling:

```bash
kubectl explain pod.spec.containers.livenessProbe
kubectl explain pod.spec.containers.livenessProbe.httpGet
```

**The `--recursive` flag** prints the entire sub-tree at once:

```bash
kubectl explain pod.spec --recursive | head -40
```

This is the fastest way to see "what fields can I set on this resource." When you are writing a YAML and unsure if a field exists, `kubectl explain` is the answer; an Internet search is the second answer; an Internet search is wrong about as often as `kubectl explain` is.

Try it for the resources you will use in Exercise 3 and the mini-project:

```bash
kubectl explain deployment.spec.strategy
kubectl explain deployment.spec.strategy.rollingUpdate
kubectl explain service.spec.ports
kubectl explain service.spec.selector
kubectl explain configmap
kubectl explain secret
```

---

## Phase 4 — `kubectl get -o jsonpath`

The extract command. Once you can read a resource as YAML, you want to pull *just one field* out of it. The two formatters for this:

- **`-o jsonpath`** — JSONPath expressions; built into `kubectl`; works without `jq`.
- **`-o json | jq ...`** — full JSON; requires `jq`; more expressive.

We will practice both, with a preference for jsonpath when it suffices.

### Pull one field

```bash
kubectl get pod hello-7d4f-aaa -o jsonpath='{.status.podIP}'
# 10.244.0.5
```

(No newline at the end; add `;echo` if you want one for shell readability.)

### Pull one field across many resources

```bash
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.podIP}{"\n"}{end}'
# hello-7d4f-aaa   10.244.0.5
# hello-7d4f-bbb   10.244.0.7
# hello-7d4f-ccc   10.244.0.9
```

The `range .items[*]` iterates; the `{end}` closes; everything in between is the row template. This is the pattern for "get me a tab-separated list of pods and their IPs," which you will need often.

### A few standard jsonpath recipes

**List pod names and their nodes**:

```bash
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{"\t"}{.spec.nodeName}{"\n"}{end}'
```

**Find pods whose containers are not Ready**:

```bash
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[*].ready}{"\n"}{end}'
```

**Get the image of the first container of every pod**:

```bash
kubectl get pods -o jsonpath='{.items[*].spec.containers[0].image}'
# nginx nginx nginx
```

**Get every container's image across the cluster (deduped)**:

```bash
kubectl get pods -A -o jsonpath='{.items[*].spec.containers[*].image}' | tr ' ' '\n' | sort -u
```

### The `-o json | jq` alternative

When jsonpath gets unwieldy, `jq` is more expressive:

```bash
kubectl get pods -o json | jq '.items[] | {name: .metadata.name, ip: .status.podIP, node: .spec.nodeName}'
```

```json
{
  "name": "hello-7d4f-aaa",
  "ip": "10.244.0.5",
  "node": "c15-w07-lab-control-plane"
}
{...}
```

`jq` has filters, transformations, and a small functional language. Worth learning once; useful forever. We will not require it for this week — every output here can be done in jsonpath — but practice both.

---

## Phase 5 — The four flavours of object access

Kubernetes supports four shapes for creating or modifying objects. Knowing which to use when is part of fluency.

### Flavour 1 — Imperative command (`kubectl run`, `kubectl create deployment`, `kubectl expose`)

```bash
kubectl run debug --image=busybox --rm -it -- sh
# (drops you into a shell in a one-off pod; the pod is deleted on exit)

kubectl create deployment hello --image=nginx --replicas=3
# (the form we used above)

kubectl expose deployment hello --port=80 --target-port=80 --type=ClusterIP
# (creates a Service of the same name selecting on app=hello)
```

**When to use**: debugging, lab work, and the rare one-off task. **When not to use**: production. There is no manifest to commit, no GitOps reconciliation, no audit trail.

### Flavour 2 — Imperative object configuration (`kubectl create -f file.yaml`, `kubectl replace -f file.yaml`)

```bash
cat > pod.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: hello-bare
  labels:
    app: hello-bare
spec:
  containers:
    - name: hello
      image: nginx
EOF

kubectl create -f pod.yaml
# pod/hello-bare created

# To modify, use kubectl replace (which is full replace, not patch):
# 1. edit pod.yaml
# 2. kubectl replace -f pod.yaml
```

**When to use**: rarely. The `create -f` semantics are "create this object; fail if it already exists." For most use cases, `apply` is better.

### Flavour 3 — Declarative apply (`kubectl apply -f file.yaml`)

```bash
kubectl apply -f pod.yaml
# pod/hello-bare configured (or "created" the first time, "unchanged" if no diff)
```

`apply` is **idempotent**: running it twice produces the same end state as running it once. Internally, it computes a three-way merge between the previous applied configuration (stored in an annotation on the object), the live state, and the new YAML. The result is patched in.

**When to use**: every production deploy. The annotation that stores the previous-applied state is the basis for `kubectl diff`, `kubectl apply --prune`, and a lot of higher-level tooling (Argo CD, Flux).

### Flavour 4 — Server-side apply (`kubectl apply --server-side -f file.yaml`)

```bash
kubectl apply --server-side -f pod.yaml
# pod/hello-bare serverside-applied
```

Server-side apply moves the three-way merge into the API server. Each field has a *manager* (the client that last set it); subsequent applies from a different manager either conflict (and require `--force-conflicts`) or are silently respected (in advanced cases). This is the post-2022 default for new tooling; Argo CD 2.10+ uses it by default.

**When to use**: when multiple controllers might touch the same object. The default for new code in 2026.

### The deprecation trail

The `kubectl create` and `kubectl replace` shapes are not deprecated, but they are not the production default. The pattern you should adopt:

- **Labs / debugging**: imperative commands (`kubectl run`, `kubectl create deployment`).
- **Personal projects**: `kubectl apply -f manifests/`.
- **CI / production**: `kubectl apply --server-side -f manifests/`. Or, more often, a GitOps controller that does the apply for you (Argo CD, Flux).

---

## Phase 6 — `kubectl logs` and `kubectl exec`

The two commands for "what is happening inside the pod." Used heavily in debugging.

### Logs

```bash
kubectl logs hello-7d4f-aaa
# (the container's stdout/stderr since it started)

kubectl logs hello-7d4f-aaa -f
# follow (streaming)

kubectl logs hello-7d4f-aaa --previous
# the logs from the PREVIOUS container in this pod
# (useful after a restart; the current container has just started, the interesting logs are from the dead container)

kubectl logs hello-7d4f-aaa --tail=50
# last 50 lines only

kubectl logs hello-7d4f-aaa --since=10m
# last 10 minutes
```

For multi-container pods, specify which container:

```bash
kubectl logs my-pod -c my-container
```

For a Deployment (across all replicas):

```bash
kubectl logs deployment/hello --tail=20 --all-containers
```

### Exec

```bash
kubectl exec hello-7d4f-aaa -- ls /usr/share/nginx/html
# 50x.html
# index.html

kubectl exec -it hello-7d4f-aaa -- sh
# (interactive shell inside the container)
```

**Use `exec` sparingly**. If you find yourself `exec`-ing into pods regularly, your observability is wrong. Logs, metrics, and traces should answer most "what is the pod doing" questions; `exec` is the last resort.

---

## Phase 7 — A diagnostic walk-through

Let's deliberately break something and walk through the diagnosis.

```bash
kubectl create deployment broken --image=nginx --replicas=2 --port=80
kubectl set image deployment/broken nginx=nginx:does-not-exist
```

Wait 30 seconds. Then:

```bash
kubectl get pods
# NAME                       READY   STATUS             RESTARTS   AGE
# broken-aaa-xxx             1/1     Running            0          45s
# broken-aaa-yyy             1/1     Running            0          45s
# broken-bbb-zzz             0/1     ImagePullBackOff   0          15s
```

**Step 1 — `describe` the Deployment**:

```bash
kubectl describe deployment broken | tail -20
```

You will see the rollout is stuck (`MinimumReplicasAvailable=True` but `Progressing=False` with `ProgressDeadlineExceeded` after a while).

**Step 2 — `describe` the new ReplicaSet**:

```bash
kubectl get rs -l app=broken
# NAME             DESIRED   CURRENT   READY   AGE
# broken-aaa       2         2         2       1m
# broken-bbb       1         1         0       30s

kubectl describe rs broken-bbb-...
```

Events will say "replica creation failed" or similar.

**Step 3 — `describe` the failing pod**:

```bash
kubectl describe pod broken-bbb-zzz
```

Events will say `ImagePullBackOff`. Cause identified.

**Step 4 — fix and roll forward**:

```bash
kubectl rollout undo deployment/broken
# or:
kubectl set image deployment/broken nginx=nginx:1.27

kubectl rollout status deployment/broken
# Waiting for deployment "broken" rollout to finish: 1 of 2 updated replicas are available...
# deployment "broken" successfully rolled out
```

Cleanup:

```bash
kubectl delete deployment broken
kubectl delete deployment hello
kubectl delete pod hello-bare
```

The pattern — *describe the top-level object, drill into its children, find the root cause in events* — is what you do for **every** stuck thing in Kubernetes. The objects change; the pattern does not.

---

## Phase 8 — Write up what you learned

Create `notes.md` in `~/c15/week-07/ex-02-kubectl/`. Answer:

1. **What is the difference between `kubectl create -f` and `kubectl apply -f` semantically?** (Hint: idempotence, the previous-applied annotation.)
2. **Give two cases where `-o jsonpath` is the right tool, and one case where `-o json | jq` is better.**
3. **You see a pod in `ImagePullBackOff`. List the `kubectl` commands you run, in order, to diagnose the root cause.**
4. **Write a one-line `kubectl get` command that prints the name and node for every pod in every namespace.**
5. **What is the difference between `kubectl logs pod-name` and `kubectl logs pod-name --previous`? When do you need each?**

Aim for one paragraph per question. Save your answers and your favorite `kubectl` recipes; you will reuse them in the mini-project and in Week 8.

---

## Acceptance

- [ ] You can read a resource's YAML representation with `-o yaml` and identify `apiVersion`, `kind`, `metadata`, `spec`, and `status`.
- [ ] You have run `kubectl describe` on a healthy pod and a broken pod and read the events.
- [ ] You have used `kubectl explain` to look up at least three resource fields without consulting the Internet.
- [ ] You have written at least one `-o jsonpath` expression that uses `range`.
- [ ] You have created a workload with each of the four flavours (imperative command, imperative `create -f`, declarative `apply -f`, server-side `apply --server-side -f`).
- [ ] `notes.md` answers the five questions in Phase 8.

---

## Common errors

- **`error: the server doesn't have a resource type "po"`** — you typed `kubectl get po` against a server that did not recognize the short name. Use the long form (`kubectl get pods`) or check your kubeconfig context.
- **`error: unable to parse "..." as either a key/value pair or a literal string`** — a stray space or unquoted special character in `-o jsonpath`. Quote the entire expression.
- **`error: container hello-bare is in waiting state and has not started yet`** — `kubectl logs` on a pod whose container has not started. Wait a few seconds; or run `kubectl describe pod` to see why it has not started.

---

*If you find errors in this material, please open an issue or send a PR.*
