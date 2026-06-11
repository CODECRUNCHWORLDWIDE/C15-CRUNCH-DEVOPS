# Week 7 — Resources

Every resource on this page is **free** and **publicly accessible**. If a link 404s, please open an issue.

## Required reading (work it into your week)

- **kubernetes.io — "What is Kubernetes?"** — the project's own one-page primer. Twelve minutes; the place to start. Read before Monday: <https://kubernetes.io/docs/concepts/overview/>.
- **kubernetes.io — "Kubernetes Components"** — the canonical diagram and one-paragraph description of every control-plane and node component. The mental model in one page. Read before Tuesday's lecture: <https://kubernetes.io/docs/concepts/overview/components/>.
- **kubernetes.io — "Cluster Architecture"** — slightly deeper than "Components"; covers nodes, control plane communication, and the leases-and-heartbeats mechanism the cluster uses to decide a node is dead: <https://kubernetes.io/docs/concepts/architecture/>.
- **kubernetes.io — "Working with Kubernetes Objects"** — `apiVersion`, `kind`, `metadata`, `spec`, `status`. The four fields every object has. Foundational: <https://kubernetes.io/docs/concepts/overview/working-with-objects/>.
- **kubernetes.io — "Pods"** — what a pod is, what it is not, why it is the unit of scheduling, the sidecar pattern: <https://kubernetes.io/docs/concepts/workloads/pods/>.
- **kubernetes.io — "Deployments"** — the rollout shape, `maxSurge` and `maxUnavailable`, the difference between a Deployment and the ReplicaSet it owns: <https://kubernetes.io/docs/concepts/workloads/controllers/deployment/>.
- **kubernetes.io — "Services"** — the four service types (`ClusterIP`, `NodePort`, `LoadBalancer`, `ExternalName`), the selector mechanism, the headless service: <https://kubernetes.io/docs/concepts/services-networking/service/>.
- **kubernetes.io — "Configure a Pod to Use a ConfigMap"** — the canonical walkthrough for the configuration injection pattern. Do it before Wednesday: <https://kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/>.
- **`kind` — "Quick Start"** — the install and "first cluster" walkthrough. Twelve minutes. Do it before Monday: <https://kind.sigs.k8s.io/docs/user/quick-start/>.

## The specs (skim, don't memorize)

- **Kubernetes API reference (v1.31)** — every field on every resource. The reference you keep open in a tab while writing YAML: <https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.31/>.
- **`kubectl` reference** — every flag on every command. The page you Cmd-F: <https://kubernetes.io/docs/reference/kubectl/>.
- **`kubectl` cheat sheet** — the project's own quick reference. Print it: <https://kubernetes.io/docs/reference/kubectl/quick-reference/>.
- **`kubectl explain`** — the man-page for any resource, accessible from the cluster itself. We use it heavily in Exercise 2: <https://kubernetes.io/docs/reference/kubectl/generated/kubectl_explain/>.
- **Pod lifecycle** — the state diagram for a pod (`Pending` → `Running` → `Succeeded` / `Failed`), plus the conditions (`Ready`, `Initialized`, `ContainersReady`, `PodScheduled`): <https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/>.
- **Service topology and `EndpointSlice`** — the post-1.21 replacement for the legacy `Endpoints` resource. Same idea, sharded for scale: <https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/>.
- **Labels and selectors** — the binding mechanism in detail; the difference between equality-based and set-based selectors: <https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/>.

## Official tool docs

- **`kubectl get`** — the read command. The `-o wide`, `-o yaml`, `-o jsonpath`, `--watch` flags are the ones you use most: <https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#get>.
- **`kubectl describe`** — the diagnose command. Returns the object plus the events the cluster has emitted about it. The first command you run when something is wrong: <https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#describe>.
- **`kubectl apply --server-side`** — the post-2022 production default. The diff-and-merge logic moves into the API server, so concurrent edits are reconciled correctly: <https://kubernetes.io/docs/reference/using-api/server-side-apply/>.
- **`kubectl logs`** — fetch logs for a container in a pod. The `-f` (follow), `--previous` (the *previous* container's logs, after a restart), and `--tail=N` flags are the ones you reach for: <https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#logs>.
- **`kubectl exec`** — open a shell in a container. Use sparingly; if you need it often, something is wrong with your tooling: <https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#exec>.
- **`kubectl port-forward`** — local-port forward to a pod or service. The right way to reach a `ClusterIP` service from your laptop without an Ingress: <https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#port-forward>.
- **`kind create cluster`** — bring up a cluster. The `--config` flag is what you use for any non-default shape: <https://kind.sigs.k8s.io/docs/user/quick-start/#creating-a-cluster>.
- **`kind load docker-image`** — load a locally-built image into the `kind` cluster's node so pods can pull it without a registry. The first time you need this, you will be glad it exists: <https://kind.sigs.k8s.io/docs/user/quick-start/#loading-an-image-into-your-cluster>.

## Free books, write-ups, and reference repos

- **"Kubernetes: Up & Running" (Burns, Beda, Hightower, Strebel) — early chapters free on O'Reilly trial** — three of the founding K8s engineers; the first three chapters cover the model end to end and are excellent. If you have a no-cost O'Reilly Online Learning trial through ACM, IEEE, or your university library, this is the first place to spend it: <https://www.oreilly.com/library/view/kubernetes-up-and/9781098110192/>.
- **"The Kubernetes Book" (Nigel Poulton) — the first edition is free on the author's site occasionally; check** — Poulton is a clear writer; the book is repetitive in good ways. Worth scanning the table of contents: <https://nigelpoulton.com/>.
- **CNCF — "Cloud Native Glossary"** — every term in the ecosystem, defined by the community. The "Pod", "Sidecar", "Operator", "Service Mesh" entries are the ones you re-read: <https://glossary.cncf.io/>.
- **`kubernetes/kubernetes` GitHub repo — `cmd/kube-apiserver/`** — the API server's `main()`. About 300 lines including the flag parsing. After this, the API server stops being magic: <https://github.com/kubernetes/kubernetes/tree/master/cmd/kube-apiserver>.
- **`kubernetes/kubernetes` — `pkg/controller/deployment/`** — the Deployment controller. The reconciliation loop you have been hearing about, in real Go: <https://github.com/kubernetes/kubernetes/tree/master/pkg/controller/deployment>.
- **`kubernetes/community` — design proposals** — the project's design archive. The "architecture" and "scheduling" subdirectories are full of foundational documents: <https://github.com/kubernetes/community/tree/master/contributors/design-proposals>.
- **Borg paper (Google, 2015)** — "Large-scale cluster management at Google with Borg." The system that produced Kubernetes; the paper that explains why the project's design is the way it is. 14 pages, free: <https://research.google/pubs/large-scale-cluster-management-at-google-with-borg/>.
- **Omega paper (Google, 2013)** — "Omega: flexible, scalable schedulers for large compute clusters." The intermediate system between Borg and Kubernetes. 12 pages, free: <https://research.google/pubs/omega-flexible-scalable-schedulers-for-large-compute-clusters/>.

## Talks and videos (free, no signup)

- **"Kubernetes Origins" — Brendan Burns** (~30 min) — one of the three Kubernetes founders telling the story of how the project started inside Google. The five minutes on why "the control plane is just a database" is the line that sticks: <https://www.youtube.com/results?search_query=brendan+burns+kubernetes+origins>.
- **"Kubernetes: The Documentary" — Honeypot.io, 2022** (~1 hour, two parts) — interviews with the founders and early contributors. The first part is the technical origins; the second is the CNCF politics. Worth all 60 minutes: <https://www.youtube.com/results?search_query=kubernetes+documentary+honeypot>.
- **"Life of a Packet through Kubernetes" — Michael Rubin (Google)** (~35 min) — the canonical talk on the data plane: how a request from the Internet reaches a pod, every hop, every translation. Watch *after* Lecture 2: <https://www.youtube.com/results?search_query=life+of+a+packet+kubernetes>.
- **"Kubernetes Architecture Explained" — TechWorld with Nana** (~40 min) — slower than the project talks, more diagrams. If the official "Components" page is too dense on the first pass, this video is the bridge: <https://www.youtube.com/results?search_query=techworld+with+nana+kubernetes+architecture>.
- **"How the Kubernetes Scheduler Works" — Daniel Smith (KubeCon)** (~30 min) — the scheduler's algorithm explained by one of its authors. Pre-requisite for any future scheduling-related debugging: <https://www.youtube.com/results?search_query=kubernetes+scheduler+how+it+works>.
- **"`kubectl`: A Day in the Life" — community talk** (~25 min) — the keystrokes you should use, the flags you should know, the patterns you should adopt. The 10 minutes on `-o jsonpath` is the segment that pays for itself: <https://www.youtube.com/results?search_query=kubectl+day+in+the+life>.
- **CNCF YouTube channel — KubeCon talks index** — the project's conference; every six months produces about 200 hours of free, expert-level content. The "100-level" track is the right starting point: <https://www.youtube.com/@cncf>.

## Local-cluster tools (we use `kind`; the others exist)

- **`kind` — the project we use this week** — Kubernetes IN Docker. The de facto upstream test target. Brings up in 60 seconds, multi-node configs are easy, the maintainer team is the K8s SIG-Testing folks: <https://kind.sigs.k8s.io/>.
- **`minikube` — the most beginner-friendly** — older project, more cloud-provider-flavored. Useful when you want a VM-based cluster (`minikube start --driver=kvm2`) and not a Docker-based one: <https://minikube.sigs.k8s.io/docs/>.
- **`k3d` — the K3s variant** — runs K3s (a stripped-down Kubernetes distribution from Rancher) inside Docker. Smaller, faster to start, missing some features. The right pick if you want to learn K3s specifically: <https://k3d.io/>.
- **`microk8s` — Canonical's variant** — a snap-installed Kubernetes on a Linux host. Different scope (it is a full distribution, not a local-test cluster), but worth knowing exists: <https://microk8s.io/>.

## YAML and `kustomize` (because every K8s manifest is YAML)

- **kubernetes.io — "Managing Resources"** — `kubectl apply`, `kubectl diff`, `kubectl prune`, and the conventions: <https://kubernetes.io/docs/concepts/cluster-administration/manage-deployment/>.
- **`kustomize` docs** — the YAML-overlay tool built into `kubectl`. The right way to manage per-environment differences without templating: <https://kustomize.io/>.
- **YAML 1.2 spec quick reference** — when you cannot remember whether `-` is a list element or a key, this is the page: <https://yaml.org/refcard.html>.

## API reference and `kubectl explain` discipline

- **`kubectl explain` for every resource you touch** — type `kubectl explain pod.spec.containers.livenessProbe` and read the output. This is the in-cluster API reference; it does not require an Internet connection: covered in Exercise 2.
- **`kubectl api-resources`** — the list of every resource type the API server knows about. Adding a CRD adds rows to this list; removing one removes rows: <https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#api-resources>.
- **`kubectl api-versions`** — the list of every API version the server serves. `v1`, `apps/v1`, `networking.k8s.io/v1` are the most common; deprecated versions appear here for one release before they are removed.

## The Kubernetes Enhancement Proposal (KEP) process

You will hear "KEP-1234" referenced in docs and issues. KEPs are how every new feature lands in Kubernetes; reading one is worth ten "what's new in 1.X" blog posts.

- **KEP repository** — the source: <https://github.com/kubernetes/enhancements/tree/master/keps>.
- **KEP-3257 (sidecar containers, GA in 1.29)** — a feature you will use within a year of starting on Kubernetes. The KEP is also a model of how to write a design doc: <https://github.com/kubernetes/enhancements/tree/master/keps/sig-node/753-sidecar-containers>.
- **KEP-2876 (CRD validation expression language, GA in 1.29)** — the feature that lets CRDs validate their own fields with CEL. The custom-resource ecosystem from Week 9 builds on it: <https://github.com/kubernetes/enhancements/tree/master/keps/sig-api-machinery/2876-crd-validation-expression-language>.

## Open-source manifests worth reading

You will learn more from one hour reading other people's Kubernetes manifests than from three hours of tutorials. Pick one and just read it:

- **`kubernetes-sigs/kind/examples/`** — the kind project's example configurations. Multi-node, multi-control-plane, custom kubelet args, ingress-ready: <https://github.com/kubernetes-sigs/kind/tree/main/examples>.
- **`kubernetes/examples`** — the project's example workloads. The `guestbook` directory is the *Hello, World* of Kubernetes; read it once for the pattern: <https://github.com/kubernetes/examples>.
- **`argoproj/argocd-example-apps`** — the Argo CD example repo (also used in Week 6 homework). The `guestbook` and `helm-guestbook` directories are clean, minimal apps: <https://github.com/argoproj/argocd-example-apps>.
- **`kelseyhightower/kubernetes-the-hard-way`** — the canonical "build a Kubernetes cluster from scratch" walkthrough. Long; do it once in your career; this week is not the right time, but bookmark it: <https://github.com/kelseyhightower/kubernetes-the-hard-way>.

## Tools you'll install this week

| Tool | Install | Purpose |
|------|---------|---------|
| `kind` | `brew install kind` (or `go install sigs.k8s.io/kind@latest`) | Kubernetes in Docker — local cluster for the exercises |
| `kubectl` | `brew install kubectl` (or `gcloud components install kubectl`) | The Kubernetes CLI |
| `docker` | Docker Desktop, Colima, or Podman with Docker compatibility | Container runtime — `kind` needs it |
| `jq` | `brew install jq` | JSON parser; we use it with `kubectl get -o json` heavily |
| `yq` | `brew install yq` | YAML parser; useful for inspecting manifests |
| `k9s` (optional) | `brew install k9s` | Terminal UI for Kubernetes; the stretch goal |

## Glossary cheat sheet

Keep this open in a tab. The first 15 entries are the ones you will encounter every day this week; the rest are reference.

| Term | Plain English |
|------|---------------|
| **Cluster** | A set of machines (the *nodes*) running Kubernetes, plus the control plane that manages them. |
| **Control plane** | The set of processes that make decisions about the cluster (API server, scheduler, controllers, etcd). |
| **Data plane** | The set of processes that run on each node and execute the control plane's decisions (kubelet, kube-proxy, container runtime). |
| **Node** | A machine in the cluster. Can be a physical server, a VM, or — in `kind` — a Docker container pretending to be a machine. |
| **API server** | The single front door to the cluster. Every read and every write goes through it. |
| **etcd** | The cluster's database. A strongly-consistent key-value store; the only stateful control-plane component. |
| **Scheduler** | The component that picks a node for each unscheduled pod. |
| **Controller manager** | The process that runs the built-in controllers (Deployment, ReplicaSet, Job, ...). |
| **kubelet** | The node-local agent. Talks to the API server; runs containers via the container runtime. |
| **kube-proxy** | The network plumbing on each node. Implements `Service` virtual IPs using `iptables` or `IPVS`. |
| **Pod** | The unit of scheduling. One or more containers that share a network namespace and a filesystem. |
| **Deployment** | The controller that rolls a `ReplicaSet` forward and backward. The shape you write for stateless apps. |
| **ReplicaSet** | The controller that keeps N copies of a pod template running. Almost always owned by a Deployment; rarely written by hand. |
| **Service** | A stable virtual IP that selects a set of pods by label. The cluster's service-discovery mechanism. |
| **Endpoints** / **EndpointSlice** | The list of pod IPs currently behind a Service. Computed automatically; you rarely look at it directly. |
| **ConfigMap** | A key-value blob mounted into a pod as files or environment variables. |
| **Secret** | A ConfigMap with a slightly different RBAC posture; base64-encoded in etcd by default (and encrypted-at-rest if you enable it). |
| **Namespace** | The cluster's soft tenancy boundary. Most resources are namespaced; some (`Node`, `PersistentVolume`) are not. |
| **Label** | A key-value string on an object. Used by selectors. Free-form; you choose the keys. |
| **Selector** | A query against labels. The mechanism that binds a Service to its pods, a Deployment to its pods, and so on. |
| **Reconciliation loop** | The pattern every Kubernetes controller follows: watch desired state, watch actual state, converge, repeat. |
| **Imperative command** | A `kubectl` call that does one thing once (`kubectl run`, `kubectl scale`). Fine for labs; anti-pattern in production. |
| **Declarative apply** | A `kubectl apply -f file.yaml` that converges the cluster toward the YAML's state. The production default. |
| **Server-side apply** | `kubectl apply --server-side`. The post-2022 default; the diff-and-merge logic lives in the API server. |
| **Readiness probe** | The cluster's check for "should this pod receive traffic?". Failing pulls the pod from the Service. |
| **Liveness probe** | The cluster's check for "is this pod still alive at all?". Failing restarts the container. |
| **Startup probe** | A probe that gates the readiness and liveness probes during a slow startup. Useful for JVM-flavored apps. |
| **CRD (CustomResourceDefinition)** | The mechanism for adding a new resource type to the cluster. The Argo `Application` from Week 6 is a CRD. |
| **CNI (Container Network Interface)** | The plugin contract for cluster networking. `kind` ships with `kindnetd`; production clusters use Calico, Cilium, or similar. |
| **CSI (Container Storage Interface)** | The plugin contract for cluster storage. Out of scope this week; relevant for stateful workloads. |
| **`kind`** | Kubernetes IN Docker. The local cluster tool we use this week. |

---

*If a link 404s, please [open an issue](https://github.com/CODECRUNCHWORLDWIDE) so we can replace it.*
