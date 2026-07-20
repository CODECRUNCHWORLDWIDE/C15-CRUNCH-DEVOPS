# Challenge 01 — Debug Five Broken Deployments

**Goal.** Apply five Deployment manifests, each broken in a different way. Without using a search engine, identify the root cause of each failure and fix it. Use only `kubectl describe`, `kubectl get events`, `kubectl logs`, and the manifest you applied. You may use `kubectl explain`. The point is to demonstrate that **the cluster tells you what is wrong**, and the skill is reading it.

**Estimated time.** 2-3 hours (30 minutes per failure, with overhead).

**Cost.** $0.00 (entirely local on the `kind` cluster).

---

## Why we are doing this

Lecture 2 told you that the cluster is verbose; the kubelet, scheduler, and controllers emit events at every state transition. Lecture 3 told you that the label-selector mechanism has three failure modes and `kubectl describe` shows you each of them. This challenge is the practice. By the end you will have an internalized debug loop: *describe the pod, read the events, find the root cause, fix the manifest, watch the cluster recover*.

The five failures are drawn from real incidents (paraphrased). Each is a single-line mistake that produces a different symptom. The goal is not to fix the mistake; it is to *find* the mistake from the cluster's own output.

---

## Setup

```bash
mkdir -p ~/c15/week-07/challenge-01
cd ~/c15/week-07/challenge-01
kubectl create namespace debug-01
```

The challenges live in the `debug-01` namespace; tear down with `kubectl delete ns debug-01` when done.

For each broken manifest, save it as a `.yaml` file in your working directory. Apply it. Diagnose. Fix. Move on.

---

## Failure 1 — The pod is `Pending` forever

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: f1-app
  namespace: debug-01
spec:
  replicas: 1
  selector:
    matchLabels:
      app: f1-app
  template:
    metadata:
      labels:
        app: f1-app
    spec:
      containers:
        - name: app
          image: nginx:1.27-alpine
          resources:
            requests:
              cpu: "16"
              memory: "32Gi"
```

Apply it. Wait 60 seconds. Observe:

```bash
kubectl -n debug-01 get pods
```

The pod is stuck `Pending`. **Your job**: name the root cause in one sentence; name the `kubectl` command that revealed it; fix the manifest; show the fixed pod becoming `Running`.

> Hint: a pod whose containers cannot be scheduled is `Pending`. The scheduler emits events explaining why. Look at them.

---

## Failure 2 — The pod is in `CrashLoopBackOff`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: f2-app
  namespace: debug-01
spec:
  replicas: 1
  selector:
    matchLabels:
      app: f2-app
  template:
    metadata:
      labels:
        app: f2-app
    spec:
      containers:
        - name: app
          image: busybox:1.36
          command: ["/bin/sh"]
          args: ["-c", "echo hello && exit 1"]
```

Apply it. Observe:

```bash
kubectl -n debug-01 get pods
# Eventually: STATUS=CrashLoopBackOff, RESTARTS climbing
```

**Your job**: name the root cause; name the `kubectl` command that revealed it; explain why a `CrashLoopBackOff` is a *symptom* and not a *cause*; fix the manifest by making the container stay alive long enough to be useful; show the fixed pod with `RESTARTS=0` after 60 seconds.

> Hint: `kubectl logs --previous` is the command you want. The current container has just started; the *previous* container is the one that died, and its logs hold the cause.

---

## Failure 3 — The Service has no endpoints

```yaml
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: f3-app
  namespace: debug-01
spec:
  replicas: 2
  selector:
    matchLabels:
      app: f3-app
  template:
    metadata:
      labels:
        app: f3-app
    spec:
      containers:
        - name: app
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: f3-svc
  namespace: debug-01
spec:
  selector:
    app: f3-application
  ports:
    - port: 80
      targetPort: 80
```

Apply it. Verify the pods are running:

```bash
kubectl -n debug-01 get pods -l app=f3-app
# Two pods Running
```

Now check the Service:

```bash
kubectl -n debug-01 get endpointslice -l kubernetes.io/service-name=f3-svc
```

The Service has **no endpoints**, even though the pods are healthy. Try to curl:

```bash
kubectl -n debug-01 run curl-test --image=curlimages/curl -i --tty --rm -- sh
# inside the pod:
curl http://f3-svc:80/
# curl: (6) Could not resolve host: f3-svc
# or: curl: (7) Failed to connect to f3-svc port 80
```

**Your job**: name the root cause in one sentence; name the `kubectl` command that revealed it; fix the manifest; show the Service with two endpoints after the fix.

> Hint: Lecture 3 Section 13 names this as "failure mode #1." Read the Service's selector. Read the pods' labels. Compare.

---

## Failure 4 — The Deployment will not roll

```yaml
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: f4-config
  namespace: debug-01
data:
  GREETING: "Hello from v1"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: f4-app
  namespace: debug-01
spec:
  replicas: 1
  selector:
    matchLabels:
      app: f4-app
  template:
    metadata:
      labels:
        app: f4-app
    spec:
      containers:
        - name: app
          image: nginxinc/nginx-unprivileged:1.27-alpine
          ports:
            - containerPort: 8080
          envFrom:
            - configMapRef:
                name: f4-config
```

Apply it. Verify the pod is running and check the env:

```bash
kubectl -n debug-01 exec deploy/f4-app -- env | grep GREETING
# GREETING=Hello from v1
```

Now change the ConfigMap:

```bash
kubectl -n debug-01 patch configmap f4-config --type=merge -p '{"data":{"GREETING":"Hello from v2"}}'
```

Wait 60 seconds. Check the env again:

```bash
kubectl -n debug-01 exec deploy/f4-app -- env | grep GREETING
# GREETING=Hello from v1     <-- still v1!
```

The pod **did not pick up the new ConfigMap value**. The cluster did not roll the Deployment.

**Your job**: explain in one sentence *why* the pod did not pick up the change. (This is a category of failure the lecture covered explicitly — review Lecture 3 Section 11 if you are not sure.) Name two ways to fix this: a one-off manual fix, and a structural fix that prevents it from happening again.

> Hint: this is not a bug; it is a property of how ConfigMaps are injected as environment variables. The fix is conceptual, not a YAML edit.

---

## Failure 5 — The readiness probe is wrong

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: f5-app
  namespace: debug-01
spec:
  replicas: 3
  selector:
    matchLabels:
      app: f5-app
  template:
    metadata:
      labels:
        app: f5-app
    spec:
      containers:
        - name: app
          image: nginxinc/nginx-unprivileged:1.27-alpine
          ports:
            - name: http
              containerPort: 8080
          readinessProbe:
            httpGet:
              path: /readyz-please
              port: http
            initialDelaySeconds: 2
            periodSeconds: 3
            failureThreshold: 3
```

Apply it. Wait 60 seconds. Observe:

```bash
kubectl -n debug-01 get pods -l app=f5-app
# NAME           READY   STATUS    RESTARTS   AGE
# f5-app-aaa     0/1     Running   0          1m
# f5-app-bbb     0/1     Running   0          1m
# f5-app-ccc     0/1     Running   0          1m
```

The pods are `Running` but **not ready**. The Service (if you create one) has no endpoints; traffic does not flow.

**Your job**: identify the root cause from `kubectl describe pod`; explain *why* a pod can be `Running` but `not Ready`; fix the manifest; show the pods reaching `READY=1/1` after the fix.

> Hint: nginx's default config does not serve `/readyz-please`. The readiness probe is asking for an endpoint the app does not implement. The fix is either: change the probe to call a path that nginx does serve, or change the app's config to serve the probe's path.

---

## Cleanup

```bash
kubectl delete namespace debug-01
```

---

## Acceptance

For each of the five failures, your write-up (`notes.md` in `~/c15/week-07/challenge-01/`) must contain:

- The **root cause** in one sentence (the actual cause; not the symptom).
- The **`kubectl` command(s)** you used to identify the cause, in order.
- The **fix**: the diff (old YAML vs new YAML, or the conceptual fix for Failure 4).
- The **verification**: the command and expected output that confirms the fix worked.

Acceptance criteria:

- [ ] Five `notes` sections, one per failure, each following the four-part structure above.
- [ ] You did not use a search engine (or AI assistant) to find the answer. The whole point of the challenge is that **the cluster tells you what is wrong**; if you skipped that and went straight to Google, you skipped the challenge.
- [ ] All five fixed Deployments are running healthy in the `debug-01` namespace at the same time, with the Services that need endpoints having endpoints.
- [ ] Bonus: write a one-paragraph reflection at the end of `notes.md` on the **debug loop** you internalized. The loop should be reusable on Failure 6, which will come up in production sometime in the next year.

---

## The taxonomy of failures

By failure number, the category of bug:

| Failure | Category | Lecture reference |
|---------|----------|-------------------|
| 1 | Scheduling — unschedulable resource request | Lecture 1 Section 5 |
| 2 | Container exits — crash loop | Lecture 2 Section 6 |
| 3 | Label-selector mismatch — Service has no endpoints | Lecture 3 Section 13 |
| 4 | ConfigMap-update propagation — env vars are snapshot-at-start | Lecture 3 Section 11 |
| 5 | Probe configuration — pod Running but not Ready | Lecture 3 Section 4, Challenge 02 |

If you can name the category from the symptom, you have internalized the model. If not, re-read the referenced section.

---

## The taxonomy of fixes

Beyond fixing the specific YAML, classify each fix by its *generality*:

- **Local fix** — the manifest change is the right answer; no broader process change needed.
- **Process fix** — the manifest change works, but a process change (CI check, lint rule, template) would have prevented the bug in the first place. List the process change you would add.

For example, Failure 1 is fixable by editing the YAML, but a **process fix** is "add a CI check that rejects manifests with `cpu` requests > 8 unless the manifest is in a `large-workload` namespace." Failure 3 is fixable by editing the selector, but the **process fix** is "use a tool that lints selector-template consistency" (some Kubernetes-aware linters do this; `kube-linter` is one).

Add the process-fix proposal to each section of `notes.md`. The goal is to think one level above the immediate bug; engineers who do this become senior; engineers who do not stay at the same level forever.

---

*If you find errors in this material, please open an issue or send a PR.*
