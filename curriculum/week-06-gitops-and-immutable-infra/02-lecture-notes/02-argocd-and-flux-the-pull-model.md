# Lecture 2 — Argo CD and Flux: The Pull Model

> **Outcome:** You can articulate the four OpenGitOps principles, name the two reference implementations (Argo CD and Flux), describe the operational properties the pull model gives you that the push model does not, and read a real Argo `Application` or Flux `Kustomization` resource and predict what the controller will do next. You can decide, for a given team, which of Argo CD and Flux to install, and defend that choice in writing.

Lecture 1 made the case for *what* an artifact should look like (immutable, baked once, never patched in place). Lecture 2 makes the case for *how* the artifact gets into production. The thesis is short: a controller in the target environment, polling a git repo and reconciling, is operationally stronger than a CI pipeline pushing changes when an engineer presses merge. The lecture has three halves. The first (Sections 1-4) is the GitOps thesis itself — push vs pull, the four OpenGitOps principles, what each principle gives you. The second (Sections 5-9) is Argo CD: the file shape, the CRDs, the CLI, the *app of apps* pattern. The third (Sections 10-14) is Flux: the four-controller decomposition, the CRDs, the `flux bootstrap` discipline, and a head-to-head comparison with Argo. We close with the config repo layout you will use this week and the three failure modes you must know.

---

## 1. Push vs pull, the operational primer

The conventional CI/CD shape, the one you built in Week 4, is *push-based*. A merge to `main` triggers a CI workflow; the workflow has credentials to the target environment; the workflow runs `kubectl apply` or `ssh ... && docker pull` or `terraform apply -auto-approve`; the workflow's logs are the audit trail. The trust boundary lives at the CI runner: anyone who can push to `main` (transitively, anyone who can compromise the CI system) can change production.

The GitOps shape is *pull-based*. A controller running inside the target environment polls a git repo on a fixed interval (Argo: every three minutes by default; Flux: every minute by default). When the controller observes a new commit, it computes the diff between the desired state (the commit) and the live state (the cluster), and it applies the diff. The trust boundary lives at the controller: the CI pipeline only ever does `git push`; it has no credentials to the cluster, the cloud, or the database. The cluster's credentials never leave the cluster.

> **Status panel — credentials inventory, push vs pull**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  PUSH MODEL — what CI must hold                     │
> │                                                     │
> │  - kubeconfig for the prod cluster                  │
> │  - DigitalOcean API token (or AWS keys, etc.)       │
> │  - Image registry pull/push credentials             │
> │  - Database admin credentials (for migrations)      │
> │  - SSH keys for any droplets                        │
> │                                                     │
> │  Blast radius if CI is compromised:                 │
> │  - full prod cluster, full cloud account,           │
> │    full database, every server's root shell         │
> └─────────────────────────────────────────────────────┘
>
> ┌─────────────────────────────────────────────────────┐
> │  PULL MODEL — what CI must hold                     │
> │                                                     │
> │  - git push permission to the config repo           │
> │                                                     │
> │  Blast radius if CI is compromised:                 │
> │  - one git repo. Branch protection + human review   │
> │    in the merge queue is the second wall.           │
> └─────────────────────────────────────────────────────┘
> ```

This is a real argument, not a marketing one. The 2018 Tesla / Kubernetes-dashboard incident (the cluster was compromised, the credentials inside it leaked) and the 2020 SolarWinds incident (the CI / build system was compromised, downstream artifacts inherited the compromise) both demonstrate the cost of holding credentials in places where they do not need to be. The pull model is *defense in depth*: each layer holds only the credentials it needs to do its one job.

---

## 2. The four OpenGitOps principles

The CNCF GitOps Working Group ratified four principles in 2021. They are short, they fit on a wallet card, and they do most of the heavy lifting of defining what GitOps actually is:

1. **Declarative.** The desired state of the system is expressed declaratively. Not "run this script"; rather "this is what the system should look like." Kubernetes manifests, Terraform configurations, Packer HCL — all declarative.
2. **Versioned and immutable.** The declarative description is versioned and stored in a way that enforces immutability and a full audit trail. In practice: git, with branch protection, signed commits if you can.
3. **Pulled automatically.** Approved changes are automatically applied to the system. A merge to `main` (or to whatever branch your environment tracks) is the *only* thing that triggers a change. No human runs `kubectl apply`; no CI pipeline runs `terraform apply -auto-approve`.
4. **Continuously reconciled.** Software agents ensure correctness and alert on divergence. The reconciler runs forever; it does not "deploy and forget." If someone manually deletes a resource, the reconciler puts it back (or pages, depending on configuration).

The principles are intentionally implementation-neutral. Argo CD satisfies them; Flux satisfies them; the small reconciler we write in the mini-project for the non-Kubernetes droplet satisfies them. Anything that does the four things is "doing GitOps"; anything that does fewer than four is doing something else (which may still be useful, but is not GitOps).

The principle most teams compromise on first is #4. They install Argo CD with `selfHeal: false`, which means Argo will detect drift but not correct it. The justification is usually "we want a human in the loop." The cost is that the cluster slowly accumulates state that diverges from the repo, and the human-in-the-loop check is never quite as careful as you wanted it to be. Section 7 of this lecture covers when `selfHeal: false` is the right call; the short answer is "for non-prod environments where the drift is informative, never for prod."

---

## 3. What "continuously reconciled" buys you that "deploy on merge" does not

A push-based system runs at merge time and not again. A pull-based system runs at merge time *and every poll interval forever*. The four operational consequences:

- **Drift correction.** If someone runs `kubectl delete deployment foo` against the cluster directly, the controller will recreate the deployment on the next poll. Drift cannot accumulate; it heals.
- **Disaster recovery from git alone.** If your cluster is destroyed (the underlying VM is lost, the namespace is deleted, the control plane fails), you can recreate it: provision a new cluster, install the controller, point it at the config repo, wait. The config repo is the source of truth for the cluster's complete state. No state lives only in the cluster.
- **Audit by `git log`.** Every change to production is a commit. Every commit has an author, a timestamp, a message, and (with signed commits) a verifiable signature. The audit trail is what git already gives you for free.
- **The "what is running in prod right now" question is unambiguous.** Run `git show main:apps/myapp/deployment.yaml`. That is what is running. If it is not, your controller is broken; that itself is a paging event.

The fourth point is the underrated one. In a push-based system, "what is running in prod" requires querying the cluster: `kubectl get deployment myapp -o yaml`. The reply might match the repo, or it might have drifted because someone ran a manual `kubectl edit`. You do not know without comparing. In a pull-based system with self-heal on, the cluster cannot drift from the repo for more than one poll interval, so the question reduces to "what is in the repo."

---

## 4. Where GitOps does not apply

Two cases:

- **Pure data plane operations.** Restarting a process, draining a node, taking a snapshot of a volume — these are *operations*, not *configurations*. GitOps controllers do not (and should not) try to manage them. You do them imperatively, through `kubectl` or `doctl` or whatever your platform exposes.
- **State that is genuinely runtime.** A queue length. A cache warm-up. A running process's open file descriptors. None of these are in git, because none of them belong in git. The principle is that *desired configuration* is in git; *runtime state* is in the cluster and its data services.

The corollary: if you find yourself trying to put runtime state in git, you have made a category error. Put the desired *shape* of the system in git (3 replicas, this image, this resource limit, this environment variable). The runtime state (which 3 pods, which IP each got, which one was elected leader) is the cluster's business.

---

## 5. Argo CD — what it is

Argo CD is a GitOps controller for Kubernetes. It was created at Intuit in 2018 and donated to the CNCF (where it is a Graduated project as of 2022). The 2.x line is stable; the 2.13 release is what we install this week. The Argo CD model:

- One controller (a Deployment in the `argocd` namespace) that polls one or more git repos.
- A web UI for visualizing sync status, diffing live vs desired, triggering manual syncs, and rolling back.
- A CLI (`argocd`) for the same operations from a terminal.
- A handful of CRDs: `Application` (the most important), `ApplicationSet` (templated multi-cluster / multi-app variants), `AppProject` (RBAC and source restrictions).

Argo's bias is toward being *batteries-included*. The UI is part of the product, not an optional dashboard you bolt on. The `Application` CRD is opinionated: one source repo (or a multi-source variant since 2.6), one target cluster, one set of sync options. If your shape matches the opinion, Argo is the path of least resistance.

---

## 6. The Argo `Application` CRD

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: hello
  namespace: argocd
spec:
  project: default

  source:
    repoURL: https://github.com/<you>/c15-w06-config
    targetRevision: main
    path: apps/hello

  destination:
    server: https://kubernetes.default.svc
    namespace: hello

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - ServerSideApply=true
```

Six fields do most of the work. Read them top to bottom:

- **`project: default`** — every Argo `Application` belongs to an `AppProject`. The `default` project is created on install and allows any source repo and any destination; in real production, you create per-team or per-environment projects and restrict them. We use `default` for the lab.
- **`source`** — *where* the manifests live. A git URL, a revision (branch, tag, or SHA), a path within the repo. Argo polls this source on a clock.
- **`destination`** — *where* the manifests get applied. The cluster's API server URL and a namespace. For Argo running inside the cluster it manages, the URL `https://kubernetes.default.svc` is the cluster's own API.
- **`syncPolicy.automated.prune: true`** — if a manifest is removed from the source repo, Argo deletes it from the cluster on the next sync. Without this, Argo only adds and updates, never deletes; orphan resources accumulate.
- **`syncPolicy.automated.selfHeal: true`** — if the live state drifts from the source, Argo corrects it automatically. Without this, Argo only reports drift; a human must press sync.
- **`syncOptions.ServerSideApply=true`** — use Kubernetes's server-side apply semantics. The 2.10+ default; correct for new apps.

The `Application` resource itself lives in the `argocd` namespace (the controller's home), even though the resources it manages live in `hello`. This is a common source of confusion the first time you do it; the rule is: the `Application` is *about* the app, but it *belongs to* Argo.

---

## 7. `selfHeal` and `prune` — when to leave them off

The two safety toggles you will spend the most time thinking about:

- **`selfHeal: true`** says "if the cluster drifts from the repo, correct it." In production, this is correct. In a lab where you are deliberately running experiments against the cluster, `selfHeal: false` is what you want so that your manual `kubectl` calls survive long enough to inspect.
- **`prune: true`** says "if a resource is removed from the repo, delete it from the cluster." In production, this is correct. The footgun is that `kubectl delete -k` against the wrong directory in the repo, merged, can delete production. The mitigations are branch protection on `main`, a code review requirement, and per-environment overlays (so a delete in `overlays/dev` only affects dev). For lab work, `prune: false` is sometimes set so a careless commit does not nuke the cluster.

A reasonable default for a new install:

| Environment | `selfHeal` | `prune` |
|-------------|-----------|---------|
| Local lab (`kind`) | false | false |
| Dev cluster | true | true |
| Staging cluster | true | true |
| Prod cluster | true | true, but with a `Sync window` blocking changes outside business hours |

The "off in prod" position has no good defenders. Every team that has run with self-heal off has lost time to "the controller said it was synced but the cluster wasn't" incidents. Turn it on.

---

## 8. The Argo CLI and the UI

```bash
argocd login <argocd-server>
argocd app list
argocd app get hello
argocd app diff hello
argocd app sync hello
argocd app history hello
argocd app rollback hello <revision>
```

Seven commands cover 95% of day-to-day Argo operations. The `argocd app diff hello` command is the one you run before every manual sync — it prints the diff between the live state and the desired state in clear `diff` format, including resource kinds, names, and the specific fields that changed. The `argocd app history hello` command lists every revision Argo has ever synced for this app; `rollback` to any of them.

The UI is at `https://localhost:8080` after you `kubectl port-forward svc/argocd-server -n argocd 8080:443`. The login is the `admin` user and the password is a one-time value stored in the `argocd-initial-admin-secret` Secret (`kubectl get secret -n argocd argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d`). Rotate it on first login.

The UI is *useful*. It shows the live state of every resource Argo manages, color-coded by sync status. The graph view (the "tree" tab) shows the parent-child relationships (a Deployment has ReplicaSets, which have Pods). For incident response, the UI is faster than `kubectl` because you do not have to remember which resource to query first.

---

## 9. The *app of apps* pattern

A real cluster has more than one application. The Argo pattern for managing many apps is "app of apps": you write one `Application` that points at a directory containing many other `Application` resources, and that bootstrap `Application` is what you create by hand. Everything else is in git.

```yaml
# bootstrap/root.yaml (the only Application you kubectl apply)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/<you>/c15-w06-config
    targetRevision: main
    path: bootstrap/apps        # contains many Application YAMLs
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

`bootstrap/apps/` contains one YAML per managed app. Each YAML is an `Application`. The root `Application` syncs *those YAMLs into the cluster*, which causes Argo to create the per-app `Application` resources, which causes Argo to sync the per-app sources. The whole tree boots from one `kubectl apply`.

The modern alternative is `ApplicationSet`, a templated multi-instance version that can generate `Application` resources from a list, a cluster generator, a git directory, or a matrix combination. `ApplicationSet` is what you reach for when "an `Application` per environment per service" would otherwise be 50 hand-written YAMLs. We do not use it this week (one cluster, one app, no need), but you should know it exists.

---

## 10. Flux — what it is

Flux is the other reference implementation. It was created at Weaveworks (the company that coined "GitOps") in 2017; v1 was retired in 2022; v2 is the only Flux to learn in 2026. Flux is a Graduated CNCF project as of 2024.

Flux's architectural bias is the opposite of Argo's: where Argo is one controller with one CRD, Flux is *four* controllers with several CRDs each. The four:

- **source-controller** — watches `GitRepository`, `OCIRepository`, `HelmRepository`, and `Bucket` resources. Pulls the source. Produces an in-cluster artifact (a tarball, stored on the controller's filesystem or in an internal storage class).
- **kustomize-controller** — watches `Kustomization` resources. Reads the artifact produced by source-controller. Runs `kustomize build` against it. Applies the result.
- **helm-controller** — watches `HelmRelease` resources. Renders a Helm chart and applies it.
- **notification-controller** — watches `Alert` and `Provider` resources. Sends notifications to Slack, MS Teams, GitHub, PagerDuty, etc., when reconciliations succeed or fail.

The split is the design philosophy: each controller does one thing, the CRDs that pertain to it stay with it, the controllers communicate by reading each other's status fields. This is more *Kubernetes-native* than Argo's monolith — and it is what makes Flux feel "lower-level" or "closer to the metal" to people switching from Argo. Same outcomes; smaller, sharper pieces.

---

## 11. The Flux CRDs

```yaml
# GitRepository — source-controller watches this
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: hello
  namespace: flux-system
spec:
  interval: 1m
  url: https://github.com/<you>/c15-w06-config
  ref:
    branch: main
```

```yaml
# Kustomization — kustomize-controller watches this
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: hello
  namespace: flux-system
spec:
  interval: 5m
  sourceRef:
    kind: GitRepository
    name: hello
  path: ./apps/hello
  prune: true
  wait: true
  targetNamespace: hello
```

Two resources instead of Argo's one. Read them together:

- The `GitRepository` says "every minute, pull this branch of this repo and store the contents as an artifact." It does not apply anything.
- The `Kustomization` says "every five minutes, take the artifact named `hello` and apply it to the cluster at the path `./apps/hello`, into the `hello` namespace, with prune on."

The decomposition has a clear payoff: you can have one `GitRepository` and ten `Kustomization` resources all pointing at the same source but applying different paths. The source-pull cost is paid once.

The `HelmRelease` CRD has the same shape but references a Helm chart:

```yaml
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: hello
  namespace: flux-system
spec:
  interval: 5m
  chart:
    spec:
      chart: ./charts/hello
      sourceRef:
        kind: GitRepository
        name: hello
  values:
    replicaCount: 2
```

The `OCIRepository` CRD (2.4+) is the new shape: instead of git, the source is an OCI artifact in a registry. The motivation is that OCI registries are robust, content-addressable, and many teams already have a registry they trust. We do not use it this week.

---

## 12. `flux bootstrap` — the install command

```bash
flux bootstrap github \
  --owner=<you> \
  --repository=c15-w06-config \
  --branch=main \
  --path=clusters/lab \
  --personal
```

This single command does five things:

1. Installs Flux into the cluster (creates the `flux-system` namespace, deploys the four controllers).
2. Creates a GitHub repo (or uses an existing one named `c15-w06-config`).
3. Adds the Flux install manifests to the repo at `clusters/lab/flux-system/`.
4. Creates a `GitRepository` and `Kustomization` pointing the cluster at that path.
5. Generates a deploy key and adds it to the repo as a deploy key with read-only access.

After `flux bootstrap`, *Flux is managing itself from the repo*. If you commit a change to `clusters/lab/flux-system/gotk-components.yaml`, Flux will apply it on the next reconciliation, including upgrading its own controllers. This is the "self-bootstrapping" property and it is delightful the first time you do it.

The Argo equivalent — Argo CD managing its own install via an `Application` — is possible but not the default. With Flux, it is the *only* shape.

---

## 13. Argo CD vs Flux — the head-to-head

A team-by-team decision. The honest summary:

| Dimension | Argo CD | Flux |
|-----------|---------|------|
| UI | First-class, batteries-included | None (separate `weave-gitops` or `headlamp` dashboard) |
| CLI | `argocd` (well-developed) | `flux` (well-developed) |
| Number of controllers | 1 (monolithic) | 4 (decomposed) |
| Resource model | `Application`, `ApplicationSet`, `AppProject` | `GitRepository`, `Kustomization`, `HelmRelease`, `OCIRepository`, plus image automation and notification CRDs |
| Multi-cluster | First-class via `ApplicationSet` cluster generators | First-class via the cluster-API integration or multiple Flux installs |
| Helm | Native, via `Application` referencing a chart | Native, via `HelmRelease` |
| Image automation | Argo CD Image Updater (separate project) | Flux Image Reflector + Image Automation (built-in CRDs) |
| Notifications | Argo CD Notifications (built-in but separate config) | notification-controller (one of the four core controllers) |
| RBAC | `AppProject` and a SSO bolt-on | Native Kubernetes RBAC on every CRD |
| Self-bootstrap | Possible but manual | Default via `flux bootstrap` |
| Audience | Teams who want a CD product feel | Teams who want CNCF-native composability |

The pop choice for new installs in 2026:

- A team with **one cluster, one app, no SSO, a small ops crew** picks Argo CD because the UI gets them productive in a day.
- A team with **many clusters, many apps, deep Kubernetes RBAC discipline, a culture of "every concern is its own controller"** picks Flux because the decomposition aligns with how they think.
- A team that wants **both** ends up running both — Argo for the human-facing CD UI, Flux for the platform-team-facing cluster bootstrap. This is more common than you would think; it is not a contradiction.

We install both this week (Argo on one `kind` cluster, Flux on another) precisely so you have direct experience with each. The exercises do not pick a winner; the write-up at the end of Exercise 3 is where you pick yours.

---

## 14. The config repo layout

Both Argo and Flux assume a config repo. The standard layout has converged:

```
config-repo/
├── README.md
├── apps/
│   ├── hello/
│   │   ├── kustomization.yaml
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── ingress.yaml
│   └── api/
│       ├── kustomization.yaml
│       ├── deployment.yaml
│       └── service.yaml
├── infrastructure/
│   ├── kustomization.yaml
│   ├── cert-manager.yaml
│   ├── ingress-nginx.yaml
│   └── sealed-secrets.yaml
├── clusters/
│   ├── lab/
│   │   ├── kustomization.yaml
│   │   ├── apps.yaml          # references apps/
│   │   └── infrastructure.yaml # references infrastructure/
│   └── prod/
│       └── (same shape, different values)
└── bootstrap/
    └── root.yaml   # the only thing you kubectl apply by hand
```

Four directories. Each has a clear job:

- **`apps/`** holds application manifests. One subdirectory per app.
- **`infrastructure/`** holds cluster-wide infrastructure (cert-manager, ingress, secrets controllers). Separate from `apps/` because the lifecycle is different: apps deploy weekly, infrastructure deploys monthly.
- **`clusters/`** holds per-cluster *compositions*: which apps and which infrastructure go on which cluster. The same app can be referenced from `clusters/lab/` and `clusters/prod/` with different overlays.
- **`bootstrap/`** holds the one `Application` (Argo) or `Kustomization` (Flux) you create by hand to start the loop.

This layout is in the Argo example repo (`argoproj/argocd-example-apps`), the Flux example repo (`fluxcd/flux2-kustomize-helm-example`), and most production config repos. Adopt it; do not invent a custom one.

---

## 15. The three GitOps failure modes

You will hit each at least once.

**Stale source.** The controller cannot pull from the repo. The cause is almost always credentials: a deploy key was rotated, a PAT expired, a network policy was tightened. Symptom: the `GitRepository` (Flux) or `Application` (Argo) shows a `LastTransitionTime` that is hours or days old, with an error message about authentication or DNS. Fix: rotate the credential, re-bootstrap if needed. The runbook is one page; write it on Friday of this week.

**Stuck reconciliation.** The source pulled fine, the diff was computed, the apply is in progress, and it stays in progress. Cause: a resource is being deleted but a finalizer is blocking the deletion (a `PersistentVolumeClaim` with a finalizer that the storage provisioner has not cleared, a `Namespace` with stuck pods). Symptom: the `Kustomization` or `Application` is in `Progressing` forever; `kubectl describe` on the stuck resource shows finalizers. Fix: identify the finalizer, remove it manually (after understanding why it is there), let the reconciliation complete.

**Divergent state.** The cluster has drifted from the repo, the controller has detected it, and `selfHeal` is off (or the drift is in a field that Argo/Flux is configured to ignore). Symptom: the app's status is `OutOfSync` and a manual `argocd app sync` is required. Fix: either correct the drift (sync) or update the config to match reality (commit). The decision rule: if the live state is wrong, sync; if the live state is correct and the repo is wrong, commit. Never ignore.

---

## 16. Closing — the bridge to the exercises

You now have, at a model level, both halves of the GitOps pattern: an immutable artifact (Packer-baked, Lecture 1) and a pull-based reconciler (Argo or Flux, this lecture). Exercise 1 wires up Packer. Exercises 2 and 3 install Argo and Flux on a `kind` cluster and reconcile a small app against each. The mini-project at the end of the week takes both ideas and applies them to the Week 5 droplet — which is not Kubernetes, but the GitOps pattern works there too, as long as you write the reconciler.

The reconciler in the mini-project is about 80 lines of Python; it polls the config repo, computes the desired Packer snapshot ID, calls `terraform apply` if the desired and live differ, and exits. Five minutes later, `cron` runs it again. That is GitOps in 80 lines. The point of installing Argo and Flux first is so you recognize what the 80 lines are doing — they are the same loop, just smaller.

---

*If you find errors in this material, please open an issue or send a PR.*
