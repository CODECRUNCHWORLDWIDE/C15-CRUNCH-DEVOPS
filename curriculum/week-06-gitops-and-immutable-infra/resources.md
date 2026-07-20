# Week 6 — Resources

Every resource on this page is **free** and **publicly accessible**. No paywalled books. If a link 404s, please open an issue.

## Required reading (work it into your week)

- **OpenGitOps — "Principles"** — the four-principle definition the CNCF working group ratified in 2021. Read end to end before Monday. Twenty minutes; foundational: <https://opengitops.dev/>.
- **Weaveworks — "Guide to GitOps"** — the canonical introduction by the team that coined the term. Skim before Lecture 2: <https://www.weave.works/technologies/gitops/>.
- **Argo CD — "Getting Started"** — the install-and-reconcile walkthrough. Do it before Wednesday's exercise; it will save you forty minutes: <https://argo-cd.readthedocs.io/en/stable/getting_started/>.
- **Flux — "Get Started with Flux"** — the parallel walkthrough. Do it before Thursday's exercise: <https://fluxcd.io/flux/get-started/>.
- **HashiCorp Packer — "Introduction"** — the two-page primer that makes the model click. Read before Monday's lecture: <https://developer.hashicorp.com/packer/intro>.
- **HashiCorp Packer — "Build an Image"** — the canonical tutorial. The DigitalOcean variant is the one we use this week: <https://developer.hashicorp.com/packer/tutorials/docker-get-started>.
- **Kelsey Hightower — "GitOps" (2018 keynote)** — the talk that crystallized the discipline. ~30 minutes; everything since is footnotes: <https://www.youtube.com/results?search_query=kelsey+hightower+gitops>.

## The specs (skim, don't memorize)

- **Argo CD — `Application` CRD reference** — every field on the resource you spend the most time editing in an Argo shop: <https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/#applications>.
- **Argo CD — `ApplicationSet` CRD reference** — the templated variant for "the same app across ten clusters" or "every app in this folder": <https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/>.
- **Argo CD — sync waves, sync hooks, sync options** — the order-of-operations primitives. Read once; refer back when a sync misbehaves: <https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/>.
- **Flux — `GitRepository` reference** — the source-controller's primary resource: <https://fluxcd.io/flux/components/source/gitrepositories/>.
- **Flux — `Kustomization` reference** — the kustomize-controller's primary resource: <https://fluxcd.io/flux/components/kustomize/kustomizations/>.
- **Flux — `HelmRelease` reference** — the helm-controller's primary resource: <https://fluxcd.io/flux/components/helm/helmreleases/>.
- **Flux — `OCIRepository` reference** — the 2.4+ shape for pulling manifests from an OCI registry instead of a git remote: <https://fluxcd.io/flux/components/source/ocirepositories/>.
- **Packer — HCL configuration spec** — every block, every field. The reference you keep open in a tab while writing a `*.pkr.hcl`: <https://developer.hashicorp.com/packer/docs/templates/hcl_templates>.
- **Packer — provisioner reference** — `shell`, `file`, `ansible`, `chef`, `puppet`. We use only `shell` and `file` this week: <https://developer.hashicorp.com/packer/docs/provisioners>.

## Official tool docs

- **`packer init`** — what gets downloaded, where it goes, the `.packer.d/` cache: <https://developer.hashicorp.com/packer/docs/commands/init>.
- **`packer fmt`** — the formatter; same shape as `terraform fmt`. Run it on every save: <https://developer.hashicorp.com/packer/docs/commands/fmt>.
- **`packer validate`** — static validation; runs in CI, fast, no API calls: <https://developer.hashicorp.com/packer/docs/commands/validate>.
- **`packer inspect`** — print the parsed configuration; useful when a variable interpolation is hiding from you: <https://developer.hashicorp.com/packer/docs/commands/inspect>.
- **`packer build`** — the only command that produces an artifact. The `-on-error=ask` flag is the one you reach for when a provisioner fails and you want to SSH into the still-running build droplet to debug: <https://developer.hashicorp.com/packer/docs/commands/build>.
- **`argocd app sync`** — manually trigger a sync. Useful when you have just merged a change and do not want to wait for the poll cycle: <https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_sync/>.
- **`argocd app diff`** — show the difference between the desired and live state. Read this before every manual sync: <https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_diff/>.
- **`flux reconcile`** — manually trigger a reconciliation. The Flux equivalent of `argocd app sync`: <https://fluxcd.io/flux/cmd/flux_reconcile/>.
- **`flux get sources git`** — the Flux equivalent of "where are we in the source pull cycle": <https://fluxcd.io/flux/cmd/flux_get_sources_git/>.

## Free books, write-ups, and reference repos

- **"GitOps Cookbook" — by Natale Vinto and Alex Soto, free on the Red Hat site** — short, recipe-format. The chapters on Argo CD and Flux side by side are the cleanest free comparison: <https://developers.redhat.com/e-books/gitops-cookbook>.
- **"GitOps and Kubernetes" — Manning sample chapters** — the first three chapters are free on the Manning site and cover the principles, the pull model, and the shape of an Argo CD config repo: <https://www.manning.com/books/gitops-and-kubernetes>.
- **`argoproj/argocd-example-apps`** — the canonical example config repo for Argo CD. Read its `README.md` and one of the `guestbook/` apps; the shape is what your config repo should look like: <https://github.com/argoproj/argocd-example-apps>.
- **`fluxcd/flux2-kustomize-helm-example`** — the canonical example config repo for Flux. Same shape as the Argo example, different filenames: <https://github.com/fluxcd/flux2-kustomize-helm-example>.
- **`hashicorp/packer-plugin-digitalocean`** — the Packer plugin for DigitalOcean. The `examples/` directory has working `*.pkr.hcl` files for the exact build we do in Exercise 1: <https://github.com/hashicorp/packer-plugin-digitalocean>.
- **OpenGitOps repo** — the source for opengitops.dev; the `principles/` directory holds the canonical text. Forking-allowed; many config repos use this as their `README.md` boilerplate: <https://github.com/open-gitops>.

## Talks and videos (free, no signup)

- **"GitOps: The Path to a Fully-Automated CI/CD Pipeline" — Alexis Richardson** (~35 min). The talk that named the discipline. The Q&A at the end is where the rebuild-vs-patch question gets a clean answer: <https://www.youtube.com/results?search_query=alexis+richardson+gitops>.
- **"Argo CD in Production" — Jesse Suen** (~40 min). The Argo project lead walking through a production-grade install. The fifteen-minute section on RBAC and `Project` resources is the one you will rewatch: <https://www.youtube.com/results?search_query=jesse+suen+argocd+production>.
- **"Flux v2: The Next Generation of GitOps" — Stefan Prodan** (~30 min). The Flux maintainer explaining the four-controller decomposition. After this you understand why Flux feels different from Argo: <https://www.youtube.com/results?search_query=stefan+prodan+flux+v2>.
- **"Packer Patterns for Production" — community talk** (~25 min). The shape of a real Packer build in a CI pipeline, including the "build once, promote across environments" pattern: <https://www.youtube.com/results?search_query=packer+production+patterns>.
- **"Cattle, not pets" — Bill Baker** (~20 min, 2012). The talk that gave the industry the cattle-not-pets framing. We will argue in Lecture 1 that the framing is dated; watching the original talk first makes that argument more interesting: <https://www.youtube.com/results?search_query=bill+baker+cattle+not+pets>.

## Open-source GitOps repos worth reading

You will learn more from one hour reading other people's config repos than from three hours of tutorials. Pick one and just read it:

- **`stefanprodan/gitops-istio`** — a complete GitOps setup with Flux, Istio, and a flagged deployment. Read for the `clusters/` and `apps/` layout: <https://github.com/stefanprodan/gitops-istio>.
- **`argoproj/argo-cd/manifests/`** — Argo CD's own manifests, deployed by Argo CD. The "self-bootstrapping" pattern is the simplest form of *app of apps*: <https://github.com/argoproj/argo-cd/tree/master/manifests>.
- **`fluxcd/flux2/manifests/`** — the equivalent for Flux: Flux's own manifests, deployed by Flux: <https://github.com/fluxcd/flux2/tree/main/manifests>.
- **`cloudposse/argocd-platform`** — a large, opinionated config repo. Read the `apps/` directory for the *app of apps* shape and the `projects/` directory for the RBAC model: <https://github.com/cloudposse/argocd-platform>.

## Argo CD vs Flux comparison reading

- **"Argo CD vs Flux: A Comparison" — CNCF blog (2023)** — the canonical side-by-side. Read end to end before Thursday: <https://www.cncf.io/blog/2023/01/30/argo-cd-vs-flux/>.
- **"How we chose Argo CD over Flux" — multiple team write-ups on Medium and team blogs** — search for the phrase and read three. The pattern: teams that want a UI pick Argo; teams that want composability pick Flux; teams that wanted both end up running both.
- **"How we chose Flux over Argo CD" — same shape, opposite conclusion.** The two together inform the Thursday exercise's write-up.

## Packer-specific (this week's image tool)

- **DigitalOcean Packer plugin docs** — every argument on the `digitalocean` builder: <https://developer.hashicorp.com/packer/integrations/digitalocean/digitalocean>.
- **DigitalOcean — "Creating a Custom Image"** — the manual procedure for what Packer automates. Useful to see the underlying API once: <https://docs.digitalocean.com/products/images/custom-images/>.
- **Packer — "Variables and Locals" tutorial** — the same shape as Terraform variables; this is the page that makes them click: <https://developer.hashicorp.com/packer/docs/templates/hcl_templates/variables>.
- **Packer — "Provisioning with Ansible"** — if you already write Ansible playbooks, Packer's `ansible` provisioner lets you bake them into an image. We do not use it this week; bookmark for later: <https://developer.hashicorp.com/packer/docs/provisioners/ansible/ansible>.

## Image automation (the GitOps-meets-CI seam)

- **Argo CD Image Updater** — the controller that watches a registry and bumps the image tag in your config repo automatically: <https://argocd-image-updater.readthedocs.io/>.
- **Flux Image Reflector + Image Automation** — the two-controller Flux equivalent. The reflector watches the registry; the automation writes the bump back to git: <https://fluxcd.io/flux/components/image/>.
- **The "promote on green" pattern** — promote an image from `dev` to `staging` to `prod` only after the dev cluster is healthy. Written up well in the Flux docs: <https://fluxcd.io/flux/use-cases/gh-actions-auto-pr/>.

## Secrets in a GitOps repo

- **Sealed Secrets** — encrypt a `Secret` resource into a `SealedSecret` that can be committed to git. The cluster-side controller decrypts on apply: <https://sealed-secrets.netlify.app/>.
- **SOPS — Mozilla's secret operations tool** — encrypts arbitrary YAML/JSON with KMS, age, or PGP. The Flux SOPS integration is first-class; the Argo CD integration is via a plugin: <https://github.com/getsops/sops>.
- **External Secrets Operator** — read secrets at runtime from Vault, AWS Secrets Manager, GCP Secret Manager. The third option for "secrets in GitOps" (alongside sealed-secrets and SOPS): <https://external-secrets.io/>.

## Tools you'll install this week

| Tool | Install | Purpose |
|------|---------|---------|
| `packer` | `brew install packer` or HashiCorp's binary (`packer -version` must show 1.11+) | The image-baking engine |
| `kind` | `brew install kind` | Kubernetes in Docker — local cluster for the exercises |
| `kubectl` | `brew install kubectl` | The Kubernetes CLI |
| `argocd` | `brew install argocd` | The Argo CD CLI |
| `flux` | `brew install fluxcd/tap/flux` | The Flux CLI |
| `kustomize` | `brew install kustomize` (or use the `kubectl kustomize` built-in) | Manifest patching, used by both Argo and Flux |
| `kubeseal` | `brew install kubeseal` | The Sealed Secrets CLI (for the stretch exercise on encrypted secrets) |
| `sops` | `brew install sops` | Mozilla's secret operations tool |
| `gh` | `brew install gh` | GitHub CLI — needed to create the config repo from the terminal |

## Glossary cheat sheet

Keep this open in a tab.

| Term | Plain English |
|------|---------------|
| **Mutable infrastructure** | A server you SSH into and `apt upgrade`; a configuration you `vim /etc/...` and reload. |
| **Immutable infrastructure** | A server you replace, never modify in place. Patches mean a new image, a new instance, and a destroy of the old one. |
| **GitOps** | The pattern where a controller in the target environment pulls desired state from a git repo on a clock and reconciles drift. |
| **Push model (of deploys)** | CI runs the deploy. CI needs credentials to the target environment. Audit trail lives in CI logs. |
| **Pull model (of deploys)** | A controller in the target environment polls a git repo and applies changes. CI only needs git push. |
| **Config repo** | The git repo holding the desired state of the cluster / environment. Distinct from the application source repo. |
| **Argo CD** | A pull-model GitOps controller for Kubernetes with a UI, a CLI, and an opinionated `Application` CRD. Created by Intuit; in CNCF since 2020. |
| **Flux** | A pull-model GitOps controller for Kubernetes, decomposed into four controllers. Created by Weaveworks; in CNCF since 2019. |
| **`Application` (Argo)** | The Argo CD CRD that says "this directory in this repo at this revision should be applied to this cluster." |
| **`Kustomization` (Flux)** | The Flux CRD that says the same thing in a different shape. |
| **`GitRepository` (Flux)** | The Flux CRD that defines a source: a git remote, a branch or tag, a poll interval. |
| **Sync wave** | An Argo CD ordering primitive: resources in wave 1 apply before resources in wave 2. |
| **Reconciliation loop** | The poll-diff-apply cycle a GitOps controller runs continuously. |
| **Drift** | When the live state of the cluster differs from the desired state in the config repo. |
| **Self-heal** | A controller setting that auto-corrects drift without a human pressing sync. |
| **Prune** | A controller setting that deletes resources from the cluster that are no longer in the config repo. |
| **Packer** | HashiCorp's image-baking tool. Produces VM / container / cloud images from a declarative HCL config. |
| **Snapshot** | DigitalOcean's term for a custom image you have baked. Snapshots are billed at $0.05 / GB / month. |
| **Build droplet** | The transient droplet Packer spins up to run provisioners against, then snapshots and destroys. |
| **`source` block (Packer)** | The Packer block that declares what cloud / format the artifact will be. |
| **`build` block (Packer)** | The Packer block that declares which sources to use and which provisioners to run. |
| **App of apps** | Argo CD pattern where one `Application` resource manages many other `Application` resources. |
| **Bootstrap (Flux)** | The `flux bootstrap` command that installs Flux into a cluster *and* commits the install manifests back to the config repo, so Flux manages itself. |

---

*If a link 404s, please [open an issue](https://github.com/CODE-CRUNCH-CLUB) so we can replace it.*
