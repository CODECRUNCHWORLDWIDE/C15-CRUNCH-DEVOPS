# Exercise 3 — Bootstrap ArgoCD and Sync an App

**Time:** 90 minutes (20 min reading, 60 min hands-on, 10 min write-up).
**Cost:** $0.00.
**Prerequisite:** Exercises 1 and 2 complete; the `w08` kind cluster is running with NGINX Ingress and cert-manager.

---

## Goal

Install ArgoCD on the `w08` kind cluster. Configure its admin password. Point it at a public Git repo. Watch ArgoCD reconcile a sample app. Demonstrate auto-sync, drift detection (`selfHeal`), and pruning.

After this exercise you should have:

- ArgoCD installed in the `argocd` namespace, all pods Running.
- A new admin password (not the auto-generated one).
- An `Application` named `hello-argo` syncing from `https://github.com/argoproj/argocd-example-apps` (path `guestbook/`) into namespace `hello-argo`.
- A demonstration of `selfHeal` by editing a resource by hand and watching ArgoCD revert it.
- A demonstration of `prune` by removing a resource from Git (or pointing at a different commit) and watching ArgoCD delete it.

---

## Step 1 — Install ArgoCD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

This applies the project's static manifests. About 50 resources land: Deployments (server, repo-server, application-controller, dex, redis, notifications-controller, applicationset-controller), ServiceAccounts, RBAC, ConfigMaps, Services, CRDs.

Wait for the rollouts. The application-controller and the server are the two you most need running:

```bash
kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=180s
kubectl -n argocd rollout status deployment/argocd-server --timeout=180s
kubectl -n argocd rollout status deployment/argocd-repo-server --timeout=180s
```

Verify pods are Ready:

```bash
kubectl -n argocd get pods
```

You should see roughly six Deployments / StatefulSets, each with status `Running` and `Ready: 1/1`. Two minutes is normal for first install.

---

## Step 2 — Get the admin password and log in

The admin password on first install is auto-generated and stored in a Secret:

```bash
INITIAL_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d)
echo "Initial admin password: $INITIAL_PASSWORD"
```

In a separate terminal, port-forward the UI:

```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443
```

In a browser, open `https://localhost:8080`. Accept the self-signed certificate warning (ArgoCD's UI uses a self-signed cert by default; in production you would put it behind an Ingress with a cert-manager-issued certificate, which is the mini-project pattern).

Log in as `admin` with the initial password.

You should see the ArgoCD UI with no Applications listed.

---

## Step 3 — Change the admin password

The auto-generated password lives in a Kubernetes Secret. Anyone with `kubectl` access to the `argocd` namespace can read it. The first thing every ArgoCD operator does is change it.

Install the ArgoCD CLI if you have not:

```bash
brew install argocd
```

Log in with the CLI:

```bash
argocd login localhost:8080 --insecure --username admin --password "$INITIAL_PASSWORD"
```

Change the password:

```bash
argocd account update-password \
  --current-password "$INITIAL_PASSWORD" \
  --new-password "your-new-strong-password"
```

After this, delete the initial-admin Secret so it cannot be used to reset the password without your involvement:

```bash
kubectl -n argocd delete secret argocd-initial-admin-secret
```

In production you would also disable the admin user entirely and use SSO. For this exercise, the password change is enough.

---

## Step 4 — Create an Application that syncs the guestbook

The ArgoCD-example-apps repo has been the canonical "first ArgoCD app" since 2019. The `guestbook` directory contains a Deployment + Service for a small redis-backed guestbook app.

Save as `hello-argo-app.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: hello-argo
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: hello-argo
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

Apply:

```bash
kubectl apply -f hello-argo-app.yaml
```

Within ~10 seconds ArgoCD detects the new Application, clones the repo, and starts applying. Watch:

```bash
kubectl get application hello-argo -n argocd -o jsonpath='{.status.sync.status}{"  "}{.status.health.status}{"\n"}'
```

Run that command every few seconds. You should see the sync progress: `OutOfSync  Missing` → `Synced  Progressing` → `Synced  Healthy`.

In the UI, the `hello-argo` Application card lights up green. Click into it to see the resource tree: Application → guestbook-ui Deployment → ReplicaSet → Pod, plus a Service.

Verify the workload directly:

```bash
kubectl -n hello-argo get all
```

---

## Step 5 — Demonstrate `selfHeal`

`selfHeal: true` means ArgoCD reverts any change made to a resource it owns. Make a change:

```bash
kubectl -n hello-argo scale deployment guestbook-ui --replicas=5
kubectl -n hello-argo get deployment guestbook-ui
```

Wait 30 seconds. Check again:

```bash
kubectl -n hello-argo get deployment guestbook-ui
```

ArgoCD has reverted the replica count back to whatever Git says (which is `1`). Drift detected, drift corrected, no human in the loop.

In the UI, the timeline of the Application shows a "Sync" event with a "diff" entry for the replica change.

---

## Step 6 — Demonstrate `prune` (gentle version)

`prune: true` means a resource removed from Git is removed from the cluster. To demonstrate without forking the repo, change the `targetRevision` to a commit that has fewer resources.

Edit the Application to point at a specific historical commit (one that does not have, say, the Service):

```bash
kubectl patch application hello-argo -n argocd --type=merge -p '{
  "spec": {
    "source": {
      "targetRevision": "<some-older-commit-sha>"
    }
  }
}'
```

The repo's actual history will determine which commit to use; in practice the simpler demo is to **manually delete a resource** and watch ArgoCD recreate it (`selfHeal`), or to **fork the repo** and remove a file.

For a fast version of the prune demo, fork the repo on GitHub, change the Application's `repoURL` to your fork, delete a file (say, `service.yaml`), commit, and watch ArgoCD remove the Service from the cluster. This is the closest analog to the real-world GitOps loop.

---

## Step 7 — Inspect the live ArgoCD state

Useful ArgoCD CLI commands to know:

```bash
# List all applications
argocd app list

# Detail on one application
argocd app get hello-argo

# Force a sync (bypasses the 3-minute polling interval)
argocd app sync hello-argo

# Show the diff between Git and the cluster
argocd app diff hello-argo

# Show the sync history (last 10 syncs)
argocd app history hello-argo

# Roll back to a previous sync
argocd app rollback hello-argo <history-id>
```

The `argocd app diff` command is the most useful day-to-day. Run it before you push a change to Git; it shows what ArgoCD will do once the change lands.

---

## Step 8 — Optional: expose ArgoCD behind the NGINX Ingress

Right now the ArgoCD UI is reachable only via `kubectl port-forward`. For practice, expose it via the same NGINX Ingress + cert-manager stack from Exercises 1 and 2.

Save as `argocd-ingress.yaml`:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: argocd-tls
  namespace: argocd
spec:
  secretName: argocd-tls
  issuerRef:
    kind: ClusterIssuer
    name: selfsigned
  commonName: argocd.localhost
  dnsNames:
    - argocd.localhost
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: argocd
  namespace: argocd
  annotations:
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    nginx.ingress.kubernetes.io/ssl-passthrough: "true"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - argocd.localhost
      secretName: argocd-tls
  rules:
    - host: argocd.localhost
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: argocd-server
                port:
                  number: 443
```

Two annotations are notable:

- `nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"` — the upstream (ArgoCD server) speaks HTTPS, not HTTP. NGINX needs to know.
- `nginx.ingress.kubernetes.io/ssl-passthrough: "true"` — pass through the TLS handshake to ArgoCD directly. ArgoCD's server has its own TLS; we are not terminating TLS at NGINX. (You could also terminate at NGINX with `--insecure` on the ArgoCD server; the passthrough is cleaner.)

For ssl-passthrough to work, NGINX needs to be installed with `--set controller.extraArgs.enable-ssl-passthrough=true`. If you did not include that flag in Exercise 1, run:

```bash
helm upgrade ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --reuse-values \
  --set controller.extraArgs.enable-ssl-passthrough=true
```

Apply the Ingress:

```bash
kubectl apply -f argocd-ingress.yaml
```

Visit `https://argocd.localhost/` in a browser. Same UI, same login, but now reachable via the Ingress instead of port-forward.

---

## Step 9 — What to write up

Create `exercises/notes-ex03.md` with:

- A one-paragraph summary: what ArgoCD now does in your cluster.
- The output of `argocd app list` and `argocd app get hello-argo`.
- A description of what `selfHeal` did when you ran the scale command in Step 5, in your own words.
- A reflection: in a team setting, what changes would you require before turning `automated: prune: true` on for production Applications? (Hint: a code review, a signed commit, branch protection rules, sync waves.)
- One question you still have about ArgoCD. (You do not need to answer it.)

---

## Troubleshooting

1. **Pods stuck `Pending`** — usually a resource-request issue on a tight cluster. `kubectl -n argocd describe pod ...` and read the events.
2. **`argocd login` rejects the password** — make sure you used `--insecure` (the ArgoCD UI cert is self-signed) and the port-forward is still running.
3. **Application stuck `Progressing`** — describe the application (`argocd app get hello-argo`) and read the per-resource health status. Usually one resource (a Pod that is `CrashLoopBackOff`, a Service whose endpoints did not register) is the bottleneck.
4. **`selfHeal` not working** — check that `syncPolicy.automated.selfHeal: true` is set. Without it, ArgoCD detects drift but does not act on it; you would see the Application marked `OutOfSync` until a manual sync.
5. **The ssl-passthrough Ingress shows 404** — the `enable-ssl-passthrough` flag was not added to the NGINX Ingress controller. Run the `helm upgrade` command in Step 8.

---

## What you should leave with

ArgoCD is the cluster's "watch Git, converge" reconciliation loop layered on top of the Kubernetes API's own reconciliation loops. The pattern is fractal: ArgoCD watches Git → Git's contents become `kubectl apply` calls → those calls update etcd → built-in controllers (Deployment, ReplicaSet, etc.) reconcile from etcd → the cluster's actual state matches the desired state. At every layer, the same shape — declared desire, controller, converge — appears.

The mini-project this week ties ArgoCD, NGINX Ingress, cert-manager, and a small application together. By Sunday you will have a Git repo, ArgoCD pointed at it, and a deploy loop that consists entirely of `git push`.

Exercise 4 (the GKE Autopilot dry-run) is optional and can be done at your desk without a cluster; it covers the commands you would run if you had a cloud trial credit.
