# Lecture 3 — Operating the Cluster and Writing the Runbook

> *A runbook is what a senior engineer leaves behind so that a junior engineer can be the on-call. It is the single most undervalued artifact in the discipline.*

The first two lectures covered the composition (what to build) and the GitOps shape (how to organize the build). Today's lecture is about the next thing — the work that happens *after* the cluster is built. Operating it. Watching it. Recovering it when it fails. Handing it to a successor.

The lecture is the conceptual setup for Sunday's mini-project. We will cover three things, in order. **First**, the dashboard tour — what an operator looks at when they first sit down in front of the cluster, where each signal lives, what each signal means. **Second**, the seven failure modes — the most common ways the capstone breaks, what each one looks like from the dashboards, and what to do about it. **Third**, the runbook discipline — how to write a runbook that survives the original author, with a template you will fill in for the capstone.

By the end of the lecture you should be able to write the runbook for the capstone. The mini-project will ask you to do so.

---

## 1. The dashboard tour

When you sit down in front of an unfamiliar cluster at 9 AM on a Monday, the first question is not "what is broken". The first question is "what should be running, and is it running". The dashboard tour is the practiced order of looking at the cluster's standing signals.

The capstone has six dashboards. In the order an operator opens them on a normal day:

### 1.1 ArgoCD — is everything synced

The ArgoCD UI at `https://argocd.local` (or the cloud equivalent). The Applications view shows every reconciled component with one of four statuses: *Synced and Healthy* (green), *Synced and Progressing* (blue, transiently), *OutOfSync* (orange), *Degraded* (red). The default state of a healthy cluster is fifteen green Applications. Anything else is the first thing to investigate.

What "OutOfSync" usually means: Git was just updated and ArgoCD has not yet applied; or a controller modified a field ArgoCD also manages, producing a drift ArgoCD cannot decide how to resolve. The first case is benign and resolves in three minutes. The second case is a configuration issue — usually fixed by adding the field to ArgoCD's `ignoreDifferences`.

What "Degraded" usually means: a controller is reporting a not-ready condition. cert-manager is reporting that a `Certificate` failed to issue (often: the DNS name does not yet resolve; for the local kind path, this is normal until you have an `/etc/hosts` entry). ingress-nginx is reporting that no backend exists. Postgres is reporting that the persistent volume claim is still pending. Each has its own debug path; the ArgoCD UI surfaces the underlying Kubernetes events that explain what is failing.

### 1.2 Grafana — the standing dashboards

The Grafana UI at `https://grafana.local`. Three dashboards are pinned, in this order:

**Dashboard A — Cluster overview.** The kube-prometheus-stack ships this one. It shows node CPU, node memory, pod count by namespace, control-plane health. A healthy cluster has node CPU under 60 percent and node memory under 70 percent at idle. A cluster sitting at 90 percent on either is a cluster a few minutes from a problem; investigate before the problem arrives.

**Dashboard B — Application overview.** Custom-built for the capstone. Three panels:
- Request rate (`rate(http_requests_total{app="crunch-quotes"}[5m])`). The baseline; spikes mean something happened.
- P95 latency (`histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{app="crunch-quotes"}[5m]))`). The SLO target is 100ms; the alert fires at 300ms.
- Error rate (`rate(http_requests_total{app="crunch-quotes",status=~"5.."}[5m]) / rate(http_requests_total{app="crunch-quotes"}[5m])`). The SLO target is below 0.1 percent; the alert fires at 1 percent.

The three together are the *Golden Signals* from the Google SRE book, minus saturation (which lives on the cluster-overview dashboard). A glance answers "is the application healthy", and a five-second glance is the right operational cadence.

**Dashboard C — Cost.** The OpenCost data, surfaced as a Grafana panel. Two numbers: total cluster cost (last 24 hours) and unit cost (cluster cost divided by request count, expressed as dollars per million requests). The unit cost is the W11 unit-economics metric, materialized.

### 1.3 ArgoCD events log — what reconciled recently

The ArgoCD events log shows the last 100 reconciliation events. Useful for two reasons. First, on a normal day, the log is empty (nothing changed); on a day something changed, the log shows what changed and when. Second, when investigating an incident, the log is the first place to ask "did something deploy right before the incident started" — the answer is usually "yes" and the next step is to find the commit.

### 1.4 Prometheus rules — what alerts are firing

The Prometheus Alertmanager UI at `https://prometheus.local/alerts`. On a normal day, no alerts are firing. On a day an alert is firing, the alert name tells you which SLO is breached and which dashboard to open. The capstone has three alerts:

- `CrunchQuotesHighErrorRate` — error rate above 1 percent for 5 minutes.
- `CrunchQuotesHighLatency` — P95 latency above 300ms for 5 minutes.
- `CrunchQuotesDown` — no successful requests in the last 2 minutes.

The Alertmanager is configured to fire silently this week (no email or Slack integration); the capstone documents the integration as a stretch goal. The discipline of *defining* the alerts is the discipline; the discipline of *routing* them is the next layer.

### 1.5 Loki — recent logs

The Loki interface, via Grafana's data-source view. The default query is `{namespace="app"}` showing all application logs from the last 15 minutes. Useful for "what is the application saying right now". Loki's strength is its label-based filtering; the application logs are tagged by pod name, container name, and namespace, and any of those can filter the view.

### 1.6 Tempo — recent traces

The Tempo interface, also via Grafana. Recent traces from the application. Each trace is a tree of spans — the incoming HTTP request, the database query, any internal function calls the application instrumented. Useful for "why was this specific request slow" — open the slowest trace from the last hour and see which span took the time. The OpenTelemetry Python SDK auto-instruments most operations; you rarely have to add manual spans.

---

## 2. The seven failure modes

Every cluster has a small number of failure modes that account for the majority of incidents. The capstone is no exception. The seven below cover, in our experience operating clusters of similar shape, more than 80 percent of real incidents. Knowing them and their signatures shortens the time to diagnosis from "open every dashboard" to "I have seen this before, here is what to check".

### Failure mode 1 — the image will not pull

Symptom: the pod is stuck in `ImagePullBackOff` or `ErrImagePull`. `kubectl describe pod` shows the registry rejecting the pull.

Most common cause: the image tag does not exist in the registry. Usually because CI failed to push (the workflow's push step errored out, the engineer did not notice) or the tag in the Kustomize manifest typo'd a digit. Run `crane manifest <image>:<tag>` to check whether the image exists at the tag.

Second most common cause: the registry requires authentication and the cluster's `imagePullSecrets` is wrong or missing. The capstone's local registry is anonymous; the cloud registry uses a `kubernetes.io/dockerconfigjson` secret.

Resolution: fix CI, retag, or fix the secret. The pod retries on its own; no `kubectl delete pod` is needed (but it is fine if you do it).

### Failure mode 2 — the certificate is not issued

Symptom: the ingress returns a TLS error in the browser. `kubectl describe certificate` shows the cert-manager challenge failed.

Most common cause (local path): the self-signed `ClusterIssuer` was never created, or was created with a mistyped name. cert-manager cannot find an issuer matching the `Certificate`'s reference.

Most common cause (cloud path): the ACME challenge cannot reach the cluster from the public internet. Usually because the DNS record points at the wrong IP, or because the ingress controller is not yet serving on the public IP.

Resolution: check `kubectl describe certificaterequest` for the underlying error message. cert-manager's logs (`kubectl logs -n cert-manager -l app=cert-manager`) are verbose and helpful.

### Failure mode 3 — the application crashes on start

Symptom: the application pod restarts repeatedly (`CrashLoopBackOff`). `kubectl logs <pod> --previous` shows a stack trace.

Most common cause: the application cannot reach the database. The Postgres pod is not yet ready, or the database password is wrong, or the database connection string is wrong.

Second most common cause: a required environment variable is missing. The application reads the database password from a Vault-injected file or from a Secret-derived environment variable; if either is missing, the application exits.

Resolution: check the application logs; check the Vault Agent injector logs (`kubectl logs <pod> -c vault-agent`); check the Secret exists (`kubectl get secret -n app`).

### Failure mode 4 — the metrics are not being scraped

Symptom: the Grafana dashboard shows "no data". `kubectl get servicemonitor -n app` shows the ServiceMonitor exists. The `/metrics` endpoint on the application returns metrics when curl'd from inside the cluster.

Most common cause: the ServiceMonitor's selector does not match the Service's labels. The Prometheus Operator silently ignores ServiceMonitors that select nothing.

Second most common cause: the ServiceMonitor is in a namespace the Prometheus Operator is not watching. Prometheus's `serviceMonitorSelector` and `serviceMonitorNamespaceSelector` together determine which ServiceMonitors are picked up; default values are restrictive.

Resolution: check Prometheus's targets page (`https://prometheus.local/targets`); if the application is not in the list, the ServiceMonitor is not being seen. Fix the selector or the Prometheus configuration.

### Failure mode 5 — the Kyverno policy refuses the pod

Symptom: a `kubectl apply` (or an ArgoCD sync) refuses with `admission webhook "validate.kyverno.svc-fail" denied the request`. The error message names the policy.

Most common cause: the image is not signed and the `verifyImages` policy is enforced. CI failed to sign, or the image tag is from before the policy was installed.

Second most common cause: the pod is missing one of the required labels (`team`, `cost-center`, `environment`, `owner`) and the `require-cost-labels` policy is enforced.

Resolution: sign the image (in CI), or add the labels (in the manifest), and re-apply. Do not disable the policy as a workaround — the policy is correct; the pod is wrong.

### Failure mode 6 — the cluster is out of resources

Symptom: pods stuck in `Pending` state. `kubectl describe pod` shows the scheduler cannot find a node with enough CPU or memory.

Most common cause: too many workloads are running, or the application's `requests` are too high. For the kind cluster, this is rare; for the cloud path, it depends on the node pool size.

Resolution (kind): scale down other workloads, or restart the cluster with a larger node configuration. Resolution (cloud): scale up the node pool, or reduce the workload's requests.

### Failure mode 7 — ArgoCD is itself out of sync

Symptom: ArgoCD is not reconciling. The UI shows the last sync timestamp is hours old. The argocd-application-controller pod is in `CrashLoopBackOff`.

Most common cause: the ArgoCD pod itself has been evicted (resource pressure) or has lost connection to its Redis. Less commonly, the Git repository credentials have expired (if you are using SSH keys with a short-lived token).

Resolution: `kubectl get pods -n argocd` to see the state; `kubectl logs -n argocd <pod>` for the specific error. Restart the pod if needed. If the Redis is down, restart that too.

---

## 3. The runbook discipline

A runbook is the document a successor reads to operate the cluster. Not the documentation that explains why the cluster is shaped the way it is (that is in `docs/decisions/`). Not the README that explains how to bring the cluster up from scratch (that is in `README.md`). The runbook is the document that explains what to do when something is broken at 2 AM.

The runbook has three sections:

### Section 1 — the dashboard tour

A copy-paste from section 1 above, with the URLs filled in. The runbook is opened by an engineer who has never seen the cluster before; the first thing they need is a map. The map is the URLs and a one-line description of each.

The temptation is to write the dashboard tour as prose. Resist; it should be a table. Engineers at 2 AM read tables better than prose.

### Section 2 — the seven failure modes (or however many the cluster has)

For each failure mode, three subsections:

- **Symptom.** What the operator sees. Specific. "The grafana dashboard shows 'no data'", not "the metrics are wrong".
- **Diagnosis.** What to run and what to look for. Specific commands. "`kubectl get servicemonitor -n app`" and "look at the `selector.matchLabels` field".
- **Resolution.** What to do. Concrete steps, not "fix the configuration". If the resolution requires a Git change, name the file and the field.

The runbook does not solve novel failures. The runbook solves the repeated failures, which are the bulk of all failures. The engineer who hits a novel failure is on their own; that is what senior engineers exist for.

### Section 3 — the disaster-recovery plan

What to do if the cluster is gone. The exact sequence of commands. The expected timing. The data-recovery story (which for the capstone is "the data does not survive a disaster; we accept this in the README"). The known failure points in the recovery (the first time you run `kind create cluster --config kind.yaml`, kind may pull images; this can take 5 to 10 minutes the first time and is a normal pause).

The disaster-recovery plan is the section the rubric weighs most heavily. The reason is empirical: the difference between teams that recover from a cluster loss in an hour and teams that take three days is, almost entirely, whether the disaster-recovery plan was written down before the disaster.

---

## 4. The runbook template (which you will fill in for the capstone)

```markdown
# RUNBOOK — crunch-quotes capstone cluster

> Read this before touching anything. Refresh as the cluster changes.

## Dashboard tour

| URL                    | What it shows                                    | When to look                        |
| ---------------------- | ------------------------------------------------ | ----------------------------------- |
| https://argocd.local   | ArgoCD Applications, sync status                 | First. Always first.                |
| https://grafana.local  | Cluster overview, application Golden Signals, cost | Second. Pinned dashboards.       |
| https://prometheus.local | Targets, rules, active alerts                  | When an alert is firing.            |
| ...                    | ...                                              | ...                                 |

## Failure modes

### FM1 — image pull fails

**Symptom.** ...
**Diagnosis.** ...
**Resolution.** ...

### FM2 — certificate not issued

...

### FM3 — application crashes on start

...

### FM4 — metrics not scraped

...

### FM5 — Kyverno policy refuses pod

...

### FM6 — cluster out of resources

...

### FM7 — ArgoCD not reconciling

...

## Disaster recovery

### When this plan applies

The cluster is gone (kind cluster deleted; cloud cluster destroyed). The Git repository is intact. We are rebuilding.

### What survives, what does not

- Source code: survives (in Git).
- Manifests: survive (in Git).
- Secrets (encrypted): survive (in Git).
- Signing keys: depend on whether they were keyless (re-derivable from OIDC) or stored (must be backed up separately).
- Postgres data: **does not survive**. The PVC is local-disk-backed on kind; cluster deletion deletes the disk. Cloud clusters with managed Postgres would survive.

### Rebuild sequence

1. `make bootstrap` — runs Terraform, creates the kind cluster, installs ArgoCD, applies the App-of-Apps. ~12 minutes.
2. Wait for ArgoCD to reconcile every Application to Synced/Healthy. ~5 minutes after step 1.
3. `make smoke` — runs the end-to-end smoke test. ~2 minutes.

### Expected total time

20 minutes on a warm Docker layer cache. 30 minutes on a cold cache (first run after a fresh machine boot or `docker system prune`).

### Known failure points in recovery

- The first `kind create cluster` after a `kind delete cluster` sometimes leaves a stale network namespace. If `kind create cluster` errors with "network in use", run `docker network prune -f` and retry.
- cert-manager's first reconciliation occasionally races the issuer creation; the first `Certificate` shows `False` for 30 to 60 seconds. Wait two minutes before debugging.
- Vault in dev mode regenerates its root token every boot. The token is read from the Vault pod's logs by the capstone's bootstrap script; the script handles this automatically.

## Contact

The capstone is a learning artifact; no on-call rotation. If this were a real cluster, this section would list the team's on-call rotation, the escalation policy, and the link to the team's incident-response runbook.
```

---

## 5. The cultural argument for the runbook

A reflexive question: why a runbook for a cluster nobody else will operate. The capstone is a learning artifact. You will tear it down at the end of the week. You will not have a successor.

The answer is rehearsal. The discipline of writing the runbook *now*, when the stakes are zero and the cluster is small, is the discipline you will need *later*, when the stakes are real and the cluster is large. The runbook is hard to write the first time and easy the tenth time; you want the first time to be when the cost of writing it badly is just a learning experience.

The second answer is humility. The runbook makes the gaps in your understanding visible. You will sit down to write FM3, the application-crashes-on-start failure mode, and realize you do not remember exactly which environment variables the application reads. You will check; you will find one you have forgotten about; you will update the manifest. The runbook is the activity that reveals what you did not know you did not know. Writing it is the cheapest education in your own cluster.

The third answer is the artifact. The cluster you operate becomes the runbook you wrote. A senior platform engineer's reputation is, in large part, the runbooks they have written. The runbook outlives the cluster; the cluster outlives the engineer; the engineer's career outlives both. The runbook is what compounds.

---

## 6. The remaining work this week

- **Saturday afternoon.** Write a first draft of the runbook based on the template above. ~90 minutes.
- **Sunday morning.** Run `make dr-rehearsal`. Destroy the cluster. Rebuild it. Time the rebuild. Note any failure points; update the runbook's section 3 accordingly. ~45 minutes for the rehearsal, ~45 minutes for the runbook update.
- **Sunday afternoon.** Final read-through of the runbook. Hand it to a friend (a willing classmate, a study partner, anyone who has not seen the cluster) and ask them to follow it cold. Note where they get stuck; revise. ~60 minutes.
- **Sunday evening.** Submit.

That last activity — *hand the runbook to someone who has not seen the cluster* — is the single most useful thing you can do this weekend. The runbook is a piece of writing whose audience is a stranger; you cannot evaluate its quality without a stranger. The friend does not need to be a Kubernetes expert; the friend's confusion is the runbook's bugs.

---

## 7. The end of the week, the end of the track

This is the last lecture in C15. There are exercises after this and a mini-project after the exercises and a final exam after the mini-project, but the conceptual scaffolding ends here. From here forward, the work is integration — composing the eleven prior weeks into the capstone, writing the runbook, running the rehearsal, submitting.

The track has tried, across twelve weeks, to make one argument: that the discipline of operating a Kubernetes cluster is the discipline of producing a small number of artifacts — a repository, a runbook, a CI pipeline, a dashboard — and revising them as the cluster's needs evolve. The artifacts are small. The discipline of producing them, revising them, and handing them off is the entire career.

The capstone is your first version of that discipline. It is not the last. The next version is the cluster you join after this. The version after that is the cluster you build for your first team. Each iteration is the same shape; each iteration adds one layer of competence that compounds.

Welcome to the discipline.

Onward.
