# Challenge 1 — Scheduled scale-down for staging environments

**Difficulty:** Medium.
**Estimated time:** 3 to 4 hours.

The setup: the `team-analytics` namespace is labeled `environment: staging`. The Deployments in it run 24/7 and idle most of the time. The cost of running them off-hours is, in aggregate, a real share of the bill at most organizations — Lecture 1 estimated 70 to 80 percent of a staging environment's spend is off-hours.

The challenge: build a system that scales every Deployment in any namespace labeled `environment: staging` to zero replicas every weekday at 7pm local time, and scales them back to their previous replica count every weekday at 8am. Weekends remain scaled-down.

This is the canonical "turn it off when nobody is using it" intervention. Done well, it cuts staging cost by 70 to 80 percent.

---

## Requirements

Your implementation must:

1. **Scale down** at a configurable time (default 19:00). Scale every Deployment in any namespace labeled `environment: staging` to 0 replicas.
2. **Scale up** at a configurable time (default 08:00 weekdays only). Restore each Deployment to its prior replica count.
3. **Remember** the prior replica count. A Deployment that was at 4 replicas before scale-down should return to 4 replicas, not to 1.
4. **Skip weekends** in the scale-up. Saturday and Sunday remain scaled-down.
5. **Handle namespace exclusions.** A namespace can opt out by carrying the label `finops.staging-schedule: "exempt"`.
6. **Log** every scale event to stdout in a structured format. The log line must include namespace, deployment, action (`scale-down` or `scale-up`), prior-replicas, new-replicas, and timestamp.
7. **Be idempotent.** Running the scale-down twice in the same window is a no-op.
8. **Run on the cluster as a CronJob.** Not as a hand-run script.

You may use any language. Python is the recommended choice for symmetry with the other Week 11 scripts; Go is acceptable. Shell is discouraged because the prior-replica-count bookkeeping is error-prone in shell.

---

## Design considerations

Read these before you start coding.

**Where to store the prior replica count.** Three options:

1. **Annotation on the Deployment.** Easy to read and write; survives across scale events. Recommended for a first implementation. Choose a stable annotation key, e.g. `finops.staging-schedule/prior-replicas`.
2. **ConfigMap in the namespace.** Centralizes state but requires the scale-up job to find and parse the ConfigMap; more code.
3. **External database.** Overkill for this problem. Avoid.

**RBAC.** The CronJob's ServiceAccount needs permission to `get`, `list`, `patch`, and `update` Deployments cluster-wide, and to `list` and `get` Namespaces. The least-privilege ClusterRole shape:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: finops-staging-schedule
rules:
  - apiGroups: [""]
    resources: ["namespaces"]
    verbs: ["get", "list"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "patch", "update"]
  - apiGroups: ["apps"]
    resources: ["deployments/scale"]
    verbs: ["get", "update", "patch"]
```

**Failure modes.** Consider:

- The scale-down runs but the scale-up fails (cluster API server unavailable, ServiceAccount token expired). Result: the staging environment stays down past 8am. Mitigation: the CronJob retries on failure; an alert fires when a scheduled scale-up does not complete.
- A Deployment is created at, say, 2am — between scale-down and scale-up. The next scale-down sees it; the prior-replica-count annotation has never been written. Decision: treat absent-annotation as "leave alone" or as "scale down with default prior=1". The first is safer.
- A developer manually scales a Deployment back up at 9pm. The next scale-down at 7pm the following day sees a non-zero replica count. Decision: respect the developer's action, scale down again, and re-record the new replica count as the prior.
- DST transitions. The CronJob schedule is in UTC. Spell out which local time you mean and adjust.

**Observability.** The system you build is itself a workload. Plan for:

- A way to query "did the scheduled job run today and did it succeed". The CronJob's status fields (`lastScheduleTime`, `lastSuccessfulTime`) are the standard.
- A way to manually trigger scale-up out of cycle. Document a `kubectl create job --from cronjob/finops-staging-scaleup manual-scaleup` pattern.
- Pod logs that a human can grep when investigating a complaint.

---

## Suggested implementation outline

Two CronJobs, one for each direction. Each CronJob runs a Python container that uses the `kubernetes` Python client (or, to avoid pip dependencies, raw HTTP against the API server via the in-cluster ServiceAccount token — the Week 11 sample code style).

```python
# scaledown.py (sketch — type hints throughout)

from __future__ import annotations
import json, os, sys
import urllib.request
from typing import Any

ANNOTATION_KEY: str = "finops.staging-schedule/prior-replicas"

def list_staging_namespaces() -> list[str]: ...
def list_deployments_in_namespace(ns: str) -> list[dict[str, Any]]: ...
def scale_deployment(ns: str, name: str, replicas: int) -> None: ...
def patch_annotation(ns: str, name: str, key: str, value: str) -> None: ...

def scale_down() -> int:
    for ns in list_staging_namespaces():
        if namespace_is_exempt(ns):
            continue
        for d in list_deployments_in_namespace(ns):
            current_replicas: int = d["spec"]["replicas"]
            if current_replicas == 0:
                continue  # idempotent: already scaled down
            patch_annotation(ns, d["metadata"]["name"],
                             ANNOTATION_KEY, str(current_replicas))
            scale_deployment(ns, d["metadata"]["name"], 0)
            log_event("scale-down", ns, d["metadata"]["name"],
                      prior=current_replicas, new=0)
    return 0
```

The scale-up direction is symmetrical: read the annotation, scale to that value, clear the annotation.

---

## Stretch goals

If you finish the core implementation with time to spare:

- **PreEvictionHook style.** Before scaling down, send a Slack notification listing the Deployments that will be scaled. Give the team a 10-minute window to cancel by setting the `finops.staging-schedule: "exempt"` label.
- **Per-namespace schedules.** Allow a namespace to override the default schedule via annotations on the namespace itself (e.g., `finops.staging-schedule/scaledown: "20:00"`).
- **Cost attribution.** After a week, query OpenCost to compute the actual cost savings. Did the scheduled scale-down cut the namespace's cost by the predicted 70 percent.

---

## Write-up requirements

In your submission write-up:

1. Diagram or describe the system's components: CronJobs, ServiceAccount, ClusterRole, the Python container, annotation conventions.
2. Name the three biggest failure modes and how your implementation handles each.
3. Estimate the cost savings on a real 5-namespace staging environment running 24/7 at ~$8,000 / month. Show your work.
4. Note one thing you would do differently in a second implementation.

---

## Reading

- Kubernetes CronJob spec: <https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/>
- Kubernetes API server access from a pod: <https://kubernetes.io/docs/tasks/run-application/access-api-from-pod/>
- ServiceAccount and RBAC: <https://kubernetes.io/docs/concepts/security/service-accounts/>
- OpenCost daily-cost queries (for verification): <https://www.opencost.io/docs/api>
