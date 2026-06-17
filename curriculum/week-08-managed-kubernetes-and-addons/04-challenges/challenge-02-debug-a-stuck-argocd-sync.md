# Challenge 2 — Debug a Stuck ArgoCD Sync

**Time:** 90 minutes.
**Cost:** $0.00.
**Prerequisite:** Exercise 3 complete; ArgoCD installed on the `w08` kind cluster.

---

## The setup

Below are five broken ArgoCD `Application` manifests. Each one will sit in some failed state when applied: `OutOfSync`, `Degraded`, `Unknown`, stuck `Progressing`, or simply refuse to be admitted. For each:

1. Apply the manifest. Observe how it fails.
2. Diagnose the cause using `argocd app get`, `kubectl describe`, and the ArgoCD UI.
3. Fix it (write the corrected manifest).
4. Verify the fix lands and the Application becomes `Synced` and `Healthy`.

Use only the cluster's own output (no Google search) to diagnose at least three of the five. The point is to internalize the diagnostic flow.

---

## Application 1 — Stuck `Unknown` from a bad repo URL

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: broken-1
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps-DOES-NOT-EXIST.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: broken-1
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

**Diagnostic prompt:**

1. Apply this. Run `argocd app get broken-1`. What does the status section say?
2. The error message is in `status.conditions`. What does it tell you?
3. The fix is one line. What is it?

---

## Application 2 — Refuses admission (bad project reference)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: broken-2
  namespace: argocd
spec:
  project: nonexistent-project
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: broken-2
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

**Diagnostic prompt:**

1. Apply this. What does `kubectl apply -f` say?
2. Does the Application appear in `argocd app list`? In what state?
3. Where does the cluster store the validation error? (Hint: check `kubectl describe app broken-2 -n argocd`.)
4. Two fixes are valid. Name both.

---

## Application 3 — Stuck `Progressing` forever (missing CRD)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: broken-3
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: helm-guestbook
    helm:
      values: |
        replicaCount: 1
  destination:
    server: https://kubernetes.default.svc
    namespace: broken-3
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

This one applies cleanly and Helm renders the chart, but the chart includes a resource of a kind your cluster does not know about (assume the chart is augmented with a `ScaledObject` from KEDA). Without KEDA's CRDs installed, what happens?

**Diagnostic prompt:**

1. The Application would show `Progressing` with `Status: Sync error: resource ScaledObject.keda.sh/v1alpha1 is not supported`. Where in `argocd app get broken-3` does this appear?
2. What are the three valid fixes for "the cluster does not have a CRD I need"?
3. Of the three, which is the right pattern for production?

*Note: you can simulate this by editing the example chart to include a CR for a non-installed CRD; or accept the diagnostic exercise as written without reproducing it on your cluster.*

---

## Application 4 — `Synced` but `Degraded` (workload bug, not ArgoCD bug)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: broken-4
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: broken-4
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

To produce the broken state, after the Application reaches `Synced` and `Healthy`, manually edit the `guestbook-ui` Deployment in namespace `broken-4` to reference an image that does not exist (`kubectl set image deployment/guestbook-ui guestbook-ui=nonexistent-image:bad`). Note that `selfHeal` is on — so ArgoCD will revert your manual change within a few minutes. To make the failure stick, change the image in a *forked* repo and re-point the Application.

**Diagnostic prompt:**

1. With the bad image, the Pod is `ImagePullBackOff`. The Deployment's status is `Progressing` then `Degraded`. The Application's `health.status` is `Degraded`. Where does ArgoCD show *which* resource is the source of the degraded state?
2. What is the `kubectl` command you run to confirm the diagnosis?
3. Once you fix the image in Git, what does ArgoCD do? In what order?

---

## Application 5 — Sync passes but `Service` has no endpoints (label mismatch)

Take Application 1 (the working version) and modify the `guestbook-ui` Service's `selector` to be `app: typoed-name` instead of `app: guestbook-ui`. The Deployment still labels its pods `app: guestbook-ui`. Apply.

**Diagnostic prompt:**

1. The Service exists. The pods exist and are Ready. Yet `kubectl exec` into another pod and `curl http://guestbook-ui` fails. What is `kubectl get endpoints` or `kubectl get endpointslice` showing?
2. Where is the bug — in the Pod, the Deployment, or the Service?
3. What is the diagnostic command that confirms the label mismatch? (Hint: `kubectl get pods --show-labels` is half of the answer.)
4. The fix is one line. What is it?

This bug is the most common Service bug in the world. You will see it 50+ times in your career. Memorize the diagnostic.

---

## What to write up

Create `challenges/notes-c02.md` with one section per Application:

### For each Application:

1. **The symptom you observed** — copy the relevant `argocd app get` output and the `kubectl get` output.
2. **The diagnostic question that pointed at the cause** — which observation, in which command's output, gave you the lead?
3. **The fix** — the corrected YAML (or the diff against the broken version).
4. **The verification** — the command and output that confirms the fix worked.

### At the end:

A one-paragraph reflection: **what is the common diagnostic shape across all five?** The expected answer references the reconciliation-loop mental model from Week 7: in every case, the cluster knows what is wrong; the skill is reading it.

---

## Acceptance criteria

The challenge is complete when:

- You have diagnosed and fixed at least 4 of the 5.
- Your write-up names the symptom, the diagnostic, and the fix for each.
- The reflection paragraph at the end identifies the common shape ("the cluster tells you; the skill is reading it") in your own words.

The fifth (the one you cannot diagnose) is the one to dwell on. Why could you not diagnose it? Was it a missing concept, a missing flag, a missing tool? That is the seed of next week's learning.

---

## Hints (use only after sincere attempts)

- For Application 1: `argocd app get broken-1` shows the `Sync` condition with the actual error from the Git fetch. The fix is changing the repoURL to a repo that exists.
- For Application 2: `kubectl apply` returns the admission webhook's validation error. Both fixes are valid: create the project first (`argocd proj create nonexistent-project ...`), or change the Application to use `project: default`.
- For Application 3: the three fixes are (a) install the CRD first via a separate Application with a lower sync-wave annotation, (b) use ArgoCD's `IgnoreExtraneous` option, (c) replace the resource with one whose CRD is installed. For production, (a) is the right pattern.
- For Application 4: `argocd app get broken-4` shows per-resource health. The Deployment will be `Degraded`; click into it (or `kubectl describe deployment guestbook-ui`) to see "ImagePullBackOff" in the pod events. Fix the image reference in Git; ArgoCD will sync, the Deployment will roll back, the pods will pull successfully.
- For Application 5: `kubectl get endpointslice -n broken-5` will show 0 endpoints for the `guestbook-ui` Service. The fix is to change the Service's selector to match the Pod's `app: guestbook-ui` label.
