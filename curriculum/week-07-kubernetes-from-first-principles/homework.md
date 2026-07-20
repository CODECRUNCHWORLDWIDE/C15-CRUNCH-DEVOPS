# Week 7 Homework

Six problems, ~5 hours total. Commit each in your week-07 repo.

---

## Problem 1 — Annotate a real-world Deployment (40 min)

Pick a published Deployment manifest from one of these well-known config repos:

- **`kubernetes/examples`** — `guestbook-go/`, `mysql-wordpress-pd/`: <https://github.com/kubernetes/examples>.
- **`argoproj/argocd-example-apps`** — `guestbook/`, `helm-guestbook/`: <https://github.com/argoproj/argocd-example-apps>.
- **`prometheus-community/helm-charts`** — `charts/prometheus/templates/`: <https://github.com/prometheus-community/helm-charts>.
- **`grafana/grafana`** — `deploy/kubernetes/`: <https://github.com/grafana/grafana>.

Copy the Deployment YAML into `notes/annotated-deployment/`. For **every field** on the Deployment (and any referenced Service, ConfigMap, or Secret), add a YAML comment that explains:

1. *What* this field does in one phrase.
2. *Why* it is set this way (a default, a security choice, a performance tuning).
3. *What would break* if you removed it or changed it.

**Acceptance.** `notes/annotated-deployment/` contains the original YAML and the annotated copy, plus a `README.md` naming the source URL and the commit SHA you read. The annotated file has at least 30 comment lines distributed across the fields.

---

## Problem 2 — Diff a `kubectl create` vs `kubectl apply` cluster (40 min)

Do the same simple thing two ways and compare:

```bash
# Approach A — imperative
kubectl create deployment app-a --image=nginx --replicas=2 --port=80
kubectl expose deployment app-a --port=80

# Approach B — declarative
cat > app-b.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-b
spec:
  replicas: 2
  selector: { matchLabels: { app: app-b } }
  template:
    metadata: { labels: { app: app-b } }
    spec:
      containers:
        - name: app
          image: nginx
          ports: [{ containerPort: 80 }]
---
apiVersion: v1
kind: Service
metadata: { name: app-b }
spec:
  selector: { app: app-b }
  ports: [{ port: 80, targetPort: 80 }]
EOF
kubectl apply -f app-b.yaml
```

Now compare:

```bash
kubectl get deployment app-a -o yaml > /tmp/app-a.yaml
kubectl get deployment app-b -o yaml > /tmp/app-b.yaml
diff /tmp/app-a.yaml /tmp/app-b.yaml
```

The differences are interesting. The imperative `kubectl create` deployment will lack the `kubectl.kubernetes.io/last-applied-configuration` annotation; the declarative one will have it. Other differences may include `progressDeadlineSeconds`, `revisionHistoryLimit`, default selectors.

**Acceptance.** `notes/imperative-vs-declarative.md` contains:

- The `diff` output (redacted).
- An explanation of every difference you saw.
- A one-paragraph argument for why the declarative shape is the production default.

Clean up:

```bash
kubectl delete deployment app-a app-b
kubectl delete service app-a app-b
```

---

## Problem 3 — Build a 5-resource manifest from scratch (60 min)

Without copying from the lecture notes or the Exercise 3 manifest, write a YAML file `notes/from-scratch/manifest.yaml` containing:

1. A `Namespace`.
2. A `ConfigMap` with two keys.
3. A `Secret` with one key.
4. A `Deployment` (3 replicas, rolling update, readiness + liveness probes) running `nginxinc/nginx-unprivileged:1.27-alpine`.
5. A `Service` of type `ClusterIP` selecting the Deployment's pods.

The Deployment must read both the ConfigMap and the Secret as environment variables via `envFrom`.

Apply with `kubectl apply --dry-run=client -f manifest.yaml` (must pass), then `kubectl apply --dry-run=server -f manifest.yaml` (must pass), then `kubectl apply -f manifest.yaml` (must succeed).

Verify:

```bash
kubectl -n <your-namespace> get all
kubectl -n <your-namespace> get endpointslice  # the Service should have 3 endpoints
kubectl -n <your-namespace> exec deploy/<name> -- env | grep -E '<your-keys>'
```

**Acceptance.** `notes/from-scratch/manifest.yaml` exists, passes both dry-runs, applies cleanly, and produces 3 endpoints. `notes/from-scratch/README.md` contains the commands and expected output.

If you find yourself reaching for Exercise 3's YAML to copy, write the manifest in a different *order* than Exercise 3 (e.g., write the Service first), or use different field names (e.g., a different `app` label value). The point is to internalize the structure.

---

## Problem 4 — Read the kubelet's source (45 min)

Read **`pkg/kubelet/kubelet.go`** from the Kubernetes source tree, specifically the `syncPod()` function. The function is about 200 lines; you do not need to understand every branch, only the overall flow.

Source: <https://github.com/kubernetes/kubernetes/blob/master/pkg/kubelet/kubelet.go>.

Write `notes/kubelet-sync-pod.md` answering:

1. What inputs does `syncPod()` take? (Look at the parameters.)
2. What is the overall sequence: probe the pod, pull images, start containers, run probes — list the steps `syncPod` actually performs in the order it performs them.
3. How does `syncPod` know whether it should start a container, restart it, or leave it alone? (Hint: it computes a *desired* set of actions and compares to the current container state.)
4. What is the role of the `SyncResult` return value? Who consumes it?
5. After reading the function, what new question do you have about kubelet's behavior? (Write the question; you do not need to answer it.)

Aim for one paragraph per question. Resist the urge to read a blog post that summarizes the kubelet; the point is to read source.

**Acceptance.** `notes/kubelet-sync-pod.md` has answers to all five questions, written in your own words. The file links to the specific commit of `kubelet.go` you read (paste a permalink with the commit SHA).

---

## Problem 5 — Reproduce a real Kubernetes failure (45 min)

Pick **one** of the following well-documented Kubernetes failure modes and reproduce it on your `kind` cluster. Document what you saw.

**Option A — `CrashLoopBackOff` from a config error.** Write a Deployment with a container that reads a required env var, and *don't* set the env var. The container exits 1 on every start; the cluster restarts with exponential backoff. Capture the `kubectl get pods` output as `RESTARTS` climbs from 0 to 4 over ~2 minutes. Note the time between restarts (it doubles).

**Option B — `OOMKilled`.** Write a Deployment with a `memory.limit` of 32Mi and a container that allocates 100Mi. The pod is OOM-killed by the kernel; the container's `lastState.terminated.reason` is `OOMKilled`. Use `stress-ng` or a small Python script that allocates a list.

**Option C — `Evicted` due to disk pressure.** Fill the `kind` node's disk above the eviction threshold (the node will mark itself `DiskPressure=True`); pods will be evicted in priority order. (This one is harder to reproduce; do it if you are confident.)

**Acceptance.** `notes/reproduced-failure.md` contains:

- The option you picked and why.
- The YAML you applied.
- The `kubectl describe pod` output showing the failure mode (redacted).
- The events that named the cause.
- A one-paragraph reflection on *what would have alerted you to this in production* — which observability signal (a metric, a log line, a Kubernetes event) would have fired first?

---

## Problem 6 — Read a CNCF talk and write a one-page response (60 min)

Pick one of these talks and watch it end to end:

- **"Kubernetes Origins" — Brendan Burns** (~30 min): <https://www.youtube.com/results?search_query=brendan+burns+kubernetes+origins>.
- **"Life of a Packet through Kubernetes" — Michael Rubin** (~35 min): <https://www.youtube.com/results?search_query=life+of+a+packet+kubernetes>.
- **"How the Kubernetes Scheduler Works" — Daniel Smith** (~30 min): <https://www.youtube.com/results?search_query=kubernetes+scheduler+how+it+works>.

Take notes while watching. Then write `notes/talk-response.md` (about one page) covering:

1. **Three things I did not know before** — facts from the talk that surprised you.
2. **One thing the speaker said that I would push back on** — even a small disagreement. (If you genuinely agreed with every word, pick the *strongest* claim and articulate where it could go wrong.)
3. **One thing I will look up after the talk** — a follow-up topic the speaker referenced but did not fully cover. Write the search query you would use.
4. **One sentence: what is the talk's central thesis?** Compress the whole 30 minutes into one sentence.

Aim for ~500 words. The point is to practice *active* listening to technical talks; this is a skill you will use forever in this industry.

**Acceptance.** `notes/talk-response.md` exists, names the talk and the speaker, and answers all four prompts.

---

## How to submit

Each problem produces a folder or a file in `notes/`. Commit them as you go:

```bash
git add notes/
git commit -m "homework: problem N — <title>"
```

End-of-week, push everything to `origin/main`. Add a `notes/README.md` that links to each problem's folder.

```bash
git push -u origin main
```

The homework is not graded the way exercises are graded; it is the seed of a portfolio. Future-you reading these notes in 2027 will be glad you wrote them down.
