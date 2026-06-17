# Lecture 2 — The Control Plane and the API Server

> **Outcome:** You can sketch the Kubernetes architecture on a whiteboard, label every control-plane component (API server, etcd, scheduler, controller manager, cloud-controller-manager) and every node component (kubelet, kube-proxy, container runtime, CNI), and name what each one stores, watches, and writes. You can explain why the API server is the single point of truth in the cluster — no other component talks to etcd directly — and you can name the four shapes of object access (`kubectl get`, watch, list, patch) that every controller in the cluster uses. You can articulate the reconciliation loop in three sentences and recognize it in `kubectl get -w` output.

The Kubernetes architecture is a database with a reconciliation loop bolted onto every row. That sentence is the single most useful mental model for the rest of the project; the rest of the lecture is what each word in that sentence means.

The lecture has three parts. Part 1 (Sections 1-5) is the control plane: the API server, etcd, the scheduler, the controller manager, and the cloud controller manager. Part 2 (Sections 6-9) is the data plane: the kubelet, kube-proxy, the container runtime, and CNI. Part 3 (Sections 10-14) is how the parts compose: the lifecycle of a `kubectl apply`, the reconciliation loop, the watch mechanism, and three anti-patterns that come from misunderstanding the architecture.

---

## 1. The architecture in one diagram

Memorize this shape:

```
┌──────────────────────────────────────────────────────────────┐
│                       CONTROL PLANE                          │
│                                                              │
│   ┌─────────────────┐         ┌───────────────────────┐     │
│   │  kube-apiserver │ ──────► │        etcd           │     │
│   │  (HTTPS / REST) │ ◄────── │  (KV store, watches)  │     │
│   └─────────────────┘         └───────────────────────┘     │
│        ▲    ▲    ▲                                          │
│        │    │    │                                          │
│        │    │    └──────────► kube-scheduler                │
│        │    │                  (picks node for pods)        │
│        │    │                                               │
│        │    └─────────────► kube-controller-manager         │
│        │                     (Deployment, ReplicaSet,       │
│        │                      Job, EndpointSlice, ...)      │
│        │                                                    │
│        └────────────────► cloud-controller-manager          │
│                            (LoadBalancer, Node, Route       │
│                             — only on cloud-backed K8s)     │
└──────────┬───────────────────────────────────────────────────┘
           │ HTTPS  (every node's kubelet logs in here)
           │
   ┌───────┴────────────────────────────────────────────┐
   │                  WORKER NODE                       │
   │                                                    │
   │   ┌──────────┐   ┌────────────┐   ┌────────────┐  │
   │   │ kubelet  │──►│  CRI       │──►│ containerd │  │
   │   │          │   │  (gRPC)    │   │ (runtime)  │  │
   │   └──────────┘   └────────────┘   └────────────┘  │
   │        │                                          │
   │        │ HTTPS (watch + status update)            │
   │        ▼                                          │
   │   ┌──────────┐   ┌────────────────────────────┐  │
   │   │kube-proxy│──►│ iptables / IPVS / nftables │  │
   │   └──────────┘   └────────────────────────────┘  │
   │                                                    │
   │   CNI plugin: kindnetd / Calico / Cilium ...       │
   └────────────────────────────────────────────────────┘
```

The shape has two halves. The control plane decides; the data plane executes. The arrows are *all* HTTPS to the API server. **Nothing talks to etcd directly except the API server**. This single rule is the most important architectural invariant in the project; we will return to it three times in this lecture.

---

## 2. The API server

`kube-apiserver` is a stateless Go binary that exposes an HTTPS REST API. Every other component in the cluster — the scheduler, every controller, every kubelet, every `kubectl` invocation — is a client of the API server. The API server itself is the only process that reads or writes etcd.

What the API server does, in order of decreasing relevance to your daily life:

1. **Serves the REST API.** Every Kubernetes resource has a path (`/api/v1/pods`, `/apis/apps/v1/deployments`, `/apis/networking.k8s.io/v1/ingresses`). The standard verbs are `GET` (list / get), `POST` (create), `PUT` (replace), `PATCH` (modify a subset of fields), `DELETE` (delete). The `WATCH` verb is the killer feature: clients can hold open a long-lived HTTP connection and receive incremental updates whenever a matched resource changes. Every controller in the cluster uses watch.
2. **Authenticates and authorizes every request.** Authentication: who is the caller? (TLS client certs, bearer tokens, OIDC). Authorization: are they allowed to do this? (RBAC by default; ABAC and webhook authorizers also supported). The default `kind` cluster uses a self-signed CA and gives `kubectl` admin-equivalent permissions; production clusters do not.
3. **Validates the resource.** A `Pod` with no `containers` field, or with an invalid `image:` value, is rejected at the API server before it ever reaches etcd. Validation is via the OpenAPI schema embedded in the API server itself, plus optional **admission webhooks** (custom validators you can register).
4. **Mutates the resource.** Some defaulters and admission controllers *modify* the resource on the way in (the `ServiceAccount` admission controller injects the default service account token; the `DefaultTolerationSeconds` controller sets a default toleration). Mutation happens after validation, before persistence.
5. **Persists to etcd.** The accepted resource is written to etcd at a path keyed by the resource's kind and name. The write is a transaction; if etcd is unavailable, the write fails.
6. **Notifies watchers.** Anyone watching the resource's path is notified. The notification is *not* a "diff"; it is the new state of the resource plus an `EventType` (`ADDED`, `MODIFIED`, `DELETED`).

The API server is stateless: you can run multiple API servers behind a load balancer and they share no state with each other except via etcd. This is how HA control planes work — three API servers in front of a three-node etcd cluster, and you can lose any one of either set without the cluster going down.

> **Status panel — API server's role in the cluster**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  API SERVER — the single source of truth            │
> │                                                     │
> │  Reads etcd:        yes (and only the API server)   │
> │  Writes etcd:       yes (and only the API server)   │
> │  Serves REST:       yes, on HTTPS :6443             │
> │  Serves watch:      yes, long-lived HTTP            │
> │  Authenticates:     yes, every request              │
> │  Authorizes:        yes, via RBAC by default        │
> │  Stateless:         yes — restart drops zero state  │
> │  HA-able:           yes — N copies behind an LB     │
> │                                                     │
> │  If it is down:     the cluster is down for         │
> │                     deploys, reads, status updates  │
> │                     (existing pods keep running)    │
> └─────────────────────────────────────────────────────┘
> ```

The last line is the saving grace and the trap: when the API server is down, *existing workloads keep running* (because the kubelet has cached the pod specs locally and `containerd` keeps running the containers), but you cannot deploy anything new, cannot read cluster state, and cannot scale. A cluster with a dead API server is a cluster you cannot operate. The cluster is *available to its users* and *unavailable to its operators*.

---

## 3. etcd

etcd is a strongly-consistent, distributed key-value store. It is the only stateful component in the Kubernetes control plane. Kubernetes treats it as a flat KV store with a watch API; every cluster resource is one key (e.g., `/registry/pods/default/hello-abc123`) and one value (the serialized resource).

Three properties of etcd that matter for Kubernetes:

1. **Strong consistency.** Writes are linearizable; a write returns only after a quorum of etcd nodes has acknowledged it. This is what makes the API server's "transaction" semantics possible.
2. **Watch.** A client can register a watch on a key prefix and receive incremental updates as keys are created, modified, or deleted. This is what the API server uses to notify *its* clients about resource changes.
3. **Compaction.** etcd retains a history of revisions; old revisions are *compacted* on a schedule to keep the data store from growing without bound. Compaction is a routine maintenance task; in `kind` it just works; in production it is a known operational concern.

**etcd's failure modes are the cluster's failure modes.** If etcd loses quorum (in a 3-node cluster, 2 of the 3 nodes are down), writes fail; reads can be served from a single node but may be stale. Backing up etcd is the single most important thing you do as a cluster operator; restoring from an etcd backup is how you recover from a catastrophic control-plane failure. We do not cover etcd backup/restore in this week; it is a Week 11 (operations) topic.

For local clusters (`kind`, `minikube`, `k3d`), etcd is a single-node, embedded process. It is durable enough for development and laughably non-HA for production. Production clusters run a 3-node or 5-node etcd cluster on dedicated VMs; managed Kubernetes services (DOKS, GKE, EKS, AKS) hide the etcd cluster from you entirely.

> **The "only the API server talks to etcd" rule.** This rule looks innocent and is foundational. If a controller talked to etcd directly, it would bypass authentication, authorization, validation, mutation, and the schema. The API server is the contract layer; etcd is the storage layer. Many self-styled "extensions" of Kubernetes break this rule and pay for it forever. The contract is: *the API server is the API*.

---

## 4. The scheduler

`kube-scheduler` is a process that watches for pods in the `Pending` state — pods that have been created in the API server but have not yet had a `nodeName` assigned. For each pending pod, the scheduler picks a node and writes the binding (a PUT to the pod's `/binding` subresource). The kubelet on the chosen node sees the binding (via its own watch on the API server, filtered by `nodeName`) and starts the containers.

The scheduling algorithm runs in two phases:

- **Filter** — which nodes *could* run this pod? Built-in filters check resource requests (`PodFitsResources`), node taints (`PodToleratesNodeTaints`), node selectors (`PodFitsNodeSelector`), and many more. A pod that no node passes is stuck `Pending`.
- **Score** — of the eligible nodes, which one is *best*? Built-in scorers prefer least-loaded nodes (`LeastRequestedPriority`), spread across zones (`SelectorSpreadPriority`), affinity (`InterPodAffinityPriority`), and again many more.

The two phases together take milliseconds. The output is a single chosen node; the binding is written; the loop continues. The scheduler does **not** start the container; it does **not** allocate the IP; it does **not** mount the volumes. It just picks a node. Every other piece of pod startup is the kubelet's job.

**What the scheduler does not know.** The scheduler does not know whether your container will actually start successfully on the chosen node. It does not know whether the image will pull. It does not know whether the probes will pass. It schedules; the kubelet executes; the result is reported back via the pod's `status`. If the pod fails to start, the scheduler does not reschedule it on a different node by default — the pod stays bound to the failed node until you delete it or until a controller (Deployment) creates a new pod.

The scheduler is *replaceable*. Kubernetes ships with one default scheduler; you can run additional schedulers, and a pod can request a specific scheduler via `spec.schedulerName`. This is rare in practice; the default scheduler is good enough for the vast majority of workloads. Custom schedulers exist for specialized use cases (batch workloads with topology requirements, GPU-aware scheduling, gang scheduling) — we will not write one this week.

---

## 5. The controller manager and the cloud controller manager

`kube-controller-manager` is one process that runs many built-in controllers. Each controller is an independent reconciliation loop watching one or more resource types. The built-ins as of 1.31:

| Controller | What it does |
|------------|--------------|
| `Deployment` | Watches `Deployment` resources; creates and rolls `ReplicaSet`s |
| `ReplicaSet` | Watches `ReplicaSet` resources; ensures N pods match the template |
| `StatefulSet` | Like `ReplicaSet`, but with stable identity and ordered rollout |
| `DaemonSet` | Ensures one pod per node (or per labeled subset) |
| `Job` | Runs a pod to completion |
| `CronJob` | Creates `Job`s on a schedule |
| `Endpoint` / `EndpointSlice` | Computes the list of pod IPs for each Service |
| `Namespace` | Finalizes namespace deletion (cascades to all resources) |
| `ServiceAccount` | Creates default service accounts in each namespace |
| `Node` | Watches node heartbeats; marks nodes `NotReady` when missing |
| `PersistentVolume` | Binds claims to volumes |
| `HorizontalPodAutoscaler` | Adjusts replica count based on metrics |

Each one is, internally, a `for { watch(); diff(); reconcile(); }` loop. The same pattern is what you write when you write a custom controller (an operator). Reading the source of one built-in controller — we recommend `pkg/controller/deployment/` in the project repo — is the single best way to internalize the pattern.

`cloud-controller-manager` is the equivalent for cloud-provider-specific controllers (managing cloud load balancers for `LoadBalancer` services, registering nodes in the cloud's instance metadata, configuring cloud routes). On `kind` it does not run at all (no cloud); on DOKS, GKE, EKS, AKS, it is the bridge between the cluster and the cloud control plane. The split (in-tree controllers in `kube-controller-manager`, cloud-specific controllers in `cloud-controller-manager`) was made in 2018 to keep cloud-specific code out of the core project.

---

## 6. The kubelet

`kubelet` is a binary that runs on every node. Its job: watch the API server for pods bound to *this* node, run those pods' containers via the container runtime, and report status back. The kubelet is the *agent* that turns "the cluster has decided this pod runs here" into "the containers are running on this machine."

The kubelet's responsibilities, in order:

1. **Watch for pods bound to this node.** A standard Kubernetes watch, filtered by `spec.nodeName=<this-node>`.
2. **For each bound pod**: pull the images, set up the pod's network namespace (via CNI), set up the pod's volumes (via CSI for persistent volumes; emptyDir, configMap, secret volumes natively), start the containers (via CRI to the runtime).
3. **Run the probes.** Readiness, liveness, and startup probes are executed by the kubelet on a schedule. The results update the pod's `status.conditions` and `status.containerStatuses`, which are written back to the API server.
4. **Report node status.** Every 10 seconds (configurable), the kubelet updates the node's `status` with available CPU, memory, disk, and the `Ready` condition. This is the heartbeat the cluster uses to detect dead nodes.
5. **Handle volume operations.** The kubelet mounts and unmounts volumes for pods on this node.
6. **Garbage collect dead containers and unused images.** When a pod is deleted, the kubelet stops the containers and (eventually) deletes the disk space.

The kubelet does **not** talk to etcd; it talks to the API server, like every other component. It uses the same watch API; it pushes status updates via PATCH. The cluster looks the same from a kubelet's perspective as from `kubectl`'s perspective — both are clients of the API server.

The kubelet is also where most of the pod's *lifecycle* logic lives. The states a pod goes through (`Pending` → `ContainerCreating` → `Running` → `Succeeded` / `Failed`) are driven by the kubelet's state machine; the pod's `status` field is the kubelet's report on that state machine. When you `kubectl describe pod`, almost everything in the `Events:` section comes from the kubelet.

> **Status panel — kubelet's responsibilities**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  KUBELET — the node-local agent                     │
> │                                                     │
> │  Watches:         pods bound to this node           │
> │  Calls into:      container runtime (CRI)           │
> │                   CNI plugin (network)              │
> │                   CSI plugin (storage)              │
> │  Runs probes:     readiness, liveness, startup      │
> │  Reports:         pod status, node status           │
> │  Heartbeat:       every 10 seconds (default)        │
> │  Talks to etcd:   no (only API server)              │
> │                                                     │
> │  If it dies:      pods on this node keep running    │
> │                   (containerd is still up) but the  │
> │                   API server stops getting status,  │
> │                   and after ~5 min the node is      │
> │                   marked NotReady and the pods are  │
> │                   rescheduled elsewhere             │
> └─────────────────────────────────────────────────────┘
> ```

A subtle point: when the kubelet dies, the containers on the node *keep running* (containerd has its own state). But the kubelet is the *reporter* of state to the cluster; without it, the cluster believes the node is dead, and the pods get rescheduled. You end up with the containers running twice: once on the "dead" node, once on the new node. This is one of the operational gotchas of Kubernetes; the cluster prefers to have *more* than the desired count rather than *fewer*. (The eviction logic is the mitigation; it kills the original pods when the node finally comes back.)

---

## 7. kube-proxy

`kube-proxy` is the network plumbing for `Service` virtual IPs. It runs on every node, watches `Service` and `EndpointSlice` resources, and programs the node's packet-filter rules (`iptables` by default; `IPVS` and `nftables` are also supported) so that traffic to the Service's virtual IP is load-balanced across the Service's pod IPs.

The mechanism, concretely:

1. You create a Service: `apiVersion: v1, kind: Service, spec.selector: {app: hello}, spec.ports: [{port: 80, targetPort: 8080}]`.
2. The API server assigns the Service a `ClusterIP` (e.g., `10.96.42.17`) from the cluster's service CIDR.
3. The Endpoints / EndpointSlice controller computes the list of pod IPs matching the selector (e.g., `10.244.0.5`, `10.244.0.7`, `10.244.0.9` for three replicas).
4. `kube-proxy` on every node watches the EndpointSlice. When it changes, kube-proxy reprograms the node's iptables (or IPVS) rules.
5. The rule says, roughly: "packets destined for `10.96.42.17:80` should be DNAT'd to one of [`10.244.0.5:8080`, `10.244.0.7:8080`, `10.244.0.9:8080`], chosen randomly."
6. A pod on this node connects to `10.96.42.17:80`; iptables rewrites the destination on the fly; the connection lands on a real pod.

The whole mechanism is data-plane: there is no proxy process in the data path. The packets go directly from client pod to server pod, with iptables doing the address translation. This is fast — there is no extra hop, no buffering, no userspace process — and it is invisible to applications.

The `IPVS` mode is the same idea with a different mechanism (the Linux kernel's IP Virtual Server, which is faster at scale than iptables and supports more load-balancing modes). Production clusters at 1000+ services usually use IPVS; `kind` clusters use iptables. The difference is performance, not behavior.

**What kube-proxy does not do**: it does not load-balance across nodes (that is the Service's CNI-implementation concern), it does not handle ingress (that is the Ingress controller, which is a separate piece you install), and it does not encrypt traffic (that is the service mesh, which is a separate piece you install). kube-proxy is *only* the virtual-IP-to-pod-IP translation.

---

## 8. The container runtime (and CRI)

The kubelet runs containers by calling into a **container runtime** over the **Container Runtime Interface (CRI)**, a gRPC API. The runtime is a separate process; the kubelet is its client. The decoupling (kubelet ↔ CRI ↔ runtime) was introduced in 2016 to let the project support multiple runtimes without forking the kubelet.

The runtimes you encounter in 2026:

- **`containerd`** — the de facto standard. Originated as a Docker subproject; donated to CNCF in 2017. The runtime built into `kind`, the runtime used by most managed Kubernetes services, and the runtime you should pick if you are picking. About 30 MB of Go binary; minimal scope (pull images, start containers, that is most of it).
- **CRI-O** — a Red Hat-led alternative; runs OCI-compliant containers without the broader Docker daemon. Used in OpenShift; less common elsewhere.
- **`dockershim`** — the shim that let kubelet talk to the Docker daemon. Removed in Kubernetes 1.24 (April 2022); if you see documentation that mentions it, the documentation is at least four years old.
- **`gVisor`** — Google's userspace kernel for sandboxed containers. A drop-in alternative for workloads where the standard Linux kernel's container isolation is not strong enough; rare in practice.
- **`Kata Containers`** — VM-based isolation; each container in its own micro-VM. Similar use case to gVisor, different mechanism; rare in practice.

For this week, "container runtime" means **containerd**. The kubelet calls into containerd via CRI; containerd pulls the image, calls into `runc` (the OCI low-level runtime) to start the container. None of this is visible from the cluster's perspective — the abstraction works.

---

## 9. CNI — the network

The **Container Network Interface (CNI)** is the plugin contract for cluster networking. When the kubelet creates a pod, it calls into a CNI plugin to:

1. Allocate an IP address for the pod.
2. Configure the pod's network namespace (`eth0` interface, default route).
3. Wire up the pod's network to the rest of the cluster, so it can reach other pods and the API server.

CNI plugins you encounter:

- **`kindnetd`** — what `kind` ships with by default. Simple, fast, works for everything we do this week. Not the right pick for production.
- **Calico** — a full-featured CNI with network policies, BGP support, and a large operator deployment. Probably the most popular production CNI in 2026.
- **Cilium** — an eBPF-based CNI with network policies, service mesh, observability. The "modern" production pick; the project is in CNCF and has rapidly become a default.
- **Flannel** — a simpler older CNI; still maintained, still in use in some shops, less feature-rich than Calico or Cilium.
- **Weave Net** — used to be common; the project is in maintenance mode.

The choice of CNI matters for production (network policy support, encryption-in-transit, observability) and matters not at all for this week (`kindnetd` does what we need). What you should know is *that there is a CNI*, and *that the CNI is what assigns pod IPs and routes between them*. When a pod cannot reach another pod, the CNI is one of the first places to look.

---

## 10. The lifecycle of a `kubectl apply`

Putting all the components together: what happens when you run `kubectl apply -f deployment.yaml`?

```
You              kubectl              API server         etcd       controller-manager   scheduler    kubelet      containerd
 │                  │                     │                │                │                │            │              │
 │ apply -f         │                     │                │                │                │            │              │
 ├─────────────────►│                     │                │                │                │            │              │
 │                  │ POST /apis/apps/v1  │                │                │                │            │              │
 │                  │   /deployments      │                │                │                │            │              │
 │                  ├────────────────────►│                │                │                │            │              │
 │                  │                     │  authenticate  │                │                │            │              │
 │                  │                     │  authorize     │                │                │            │              │
 │                  │                     │  validate      │                │                │            │              │
 │                  │                     │  mutate        │                │                │            │              │
 │                  │                     │  PUT key       │                │                │            │              │
 │                  │                     ├───────────────►│                │                │            │              │
 │                  │                     │  ack           │                │                │            │              │
 │                  │                     │◄───────────────┤                │                │            │              │
 │                  │                     │  notify watch  │                │                │            │              │
 │                  │  HTTP 201           │  (deployment)  │                │                │            │              │
 │                  │◄────────────────────┼────────────────┼───────────────►│                │            │              │
 │                  │                     │                │                │  reconcile:    │            │              │
 │                  │                     │                │                │  create RS     │            │              │
 │                  │                     │  POST RS       │                │                │            │              │
 │                  │                     │◄───────────────┼────────────────┤                │            │              │
 │                  │                     │  (notify)      │                │                │            │              │
 │                  │                     │                │                │  reconcile:    │            │              │
 │                  │                     │                │                │  create pods   │            │              │
 │                  │                     │  POST pods     │                │                │            │              │
 │                  │                     │◄───────────────┼────────────────┤                │            │              │
 │                  │                     │  (notify)      │                │                │            │              │
 │                  │                     │                │                │                │ pending pod│              │
 │                  │                     │  PUT binding   │                │                ├───────────►│              │
 │                  │                     │◄───────────────┼────────────────┼────────────────┤            │              │
 │                  │                     │  (notify)      │                │                │            │              │
 │                  │                     │                │                │                │            │ watch sees   │
 │                  │                     │                │                │                │            │ pod bound    │
 │                  │                     │                │                │                │            │ to this node │
 │                  │                     │                │                │                │            ├─────────────►│
 │                  │                     │                │                │                │            │  pull image  │
 │                  │                     │                │                │                │            │  start ctr   │
 │                  │                     │                │                │                │            │◄─────────────┤
 │                  │                     │  PATCH status  │                │                │            │              │
 │                  │                     │◄───────────────┼────────────────┼────────────────┼────────────┤              │
```

Take a minute and trace each arrow. The diagram is dense; the steps are simple. The pattern that emerges:

- You write to the API server (POST a Deployment).
- The API server writes to etcd.
- etcd notifies watchers.
- A controller (Deployment) sees the watch event, decides to create a ReplicaSet, posts that to the API server.
- The API server writes to etcd; another watch event fires.
- The ReplicaSet controller sees it, decides to create pods, posts those.
- etcd notifies the scheduler; the scheduler picks a node, PUTs the binding.
- etcd notifies the kubelet on the bound node; the kubelet starts the containers.
- The kubelet PATCHes the pod's status; etcd notifies whoever cares.

Every step is a **write to the API server**, followed by a **notification to watchers**, followed by a **decision in some controller**. The cluster runs on watches; you can think of it as a giant pub-sub system where the API server is the broker.

---

## 11. The reconciliation loop, in one paragraph

A controller is a process that:

1. **Watches** a resource type via the API server's watch API.
2. **Compares** the desired state (the resource's `spec`) to the actual state (the resource's `status`, plus side-channel observations of the cluster).
3. **Acts** to reduce the difference: creates or modifies subordinate resources, posts status updates.

The loop runs *forever*. It runs on every change to the watched resource. It also runs periodically (every 30 seconds by default, configurable) as a safety net in case a watch event was missed. It is **level-triggered**, not edge-triggered: the controller looks at the current state, not at the change that produced it. This means the controller is resilient to missed events — even if you missed event N, the next run sees the current state including all changes through N.

The level-triggered design is one of the project's foundational decisions. It means controllers are easier to write (you do not need to maintain a per-change state machine), easier to test (the input is the current state, not a history), and easier to recover (a restarted controller sees the current state and converges, regardless of what happened while it was down).

> **Status panel — the reconciliation loop**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  RECONCILER PATTERN                                 │
> │                                                     │
> │  for {                                              │
> │      desired := watch.next() // or list every 30 s  │
> │      actual  := observeWorld()                      │
> │      diff    := compare(desired, actual)            │
> │      if diff != nil {                               │
> │          act(diff)                                  │
> │      }                                              │
> │      status := updateStatus(desired)                │
> │  }                                                  │
> │                                                     │
> │  Properties:                                        │
> │    - level-triggered (no missed-event bugs)         │
> │    - idempotent (act() can run twice safely)        │
> │    - eventually consistent (no transactional        │
> │      coordination between controllers)              │
> └─────────────────────────────────────────────────────┘
> ```

The loop is what makes Kubernetes self-healing. When you `kubectl delete pod hello-abc123`, the Deployment controller's next loop sees that the ReplicaSet has 2 pods (not 3), creates a new pod, the scheduler binds it, the kubelet starts it. The whole thing takes about 5 seconds. You did not write code to make this happen; the controller is shipped in the binary.

---

## 12. The watch mechanism

A watch is an HTTP request that does not close. The client makes a `GET` to `/api/v1/pods?watch=true&resourceVersion=12345`. The API server responds with `Transfer-Encoding: chunked` and starts streaming JSON objects, one per event:

```json
{"type": "ADDED", "object": {"kind": "Pod", "metadata": {"name": "hello-abc"}, ...}}
{"type": "MODIFIED", "object": {"kind": "Pod", "metadata": {"name": "hello-abc"}, ...}}
{"type": "DELETED", "object": {"kind": "Pod", "metadata": {"name": "hello-abc"}, ...}}
```

The `resourceVersion` parameter is the cursor. The API server starts streaming events *after* the given version. If the client disconnects and reconnects with the same `resourceVersion`, it resumes from where it left off. If the version is too old (compacted out of etcd), the server returns 410 Gone, and the client must re-list and start a new watch from the new latest version.

In practice, you do not write a watch by hand; you use a **client-go informer** (in Go) or the equivalent in the project's other client libraries (Python, JavaScript, Java). An informer does the watch, maintains a local cache of the resources it has seen, and calls a callback when something changes. Every Kubernetes controller — every built-in, every operator, every Argo CD reconciler — is built on top of an informer.

You can see watches with `kubectl get pods --watch` (or `-w`):

```
NAME          READY   STATUS     RESTARTS   AGE
hello-abc     0/1     Pending    0          0s
hello-abc     0/1     ContainerCreating   0   1s
hello-abc     0/1     Running    0          3s
hello-abc     1/1     Running    0          5s
```

Each row is a watch event. The kubectl client is holding an HTTP connection open to the API server; the API server streams the rows as they happen.

---

## 13. Three things this lecture makes possible

You now have the model for the rest of the course. Three concrete things that follow from this lecture:

1. **You can debug a pod stuck `Pending` without guessing.** `kubectl describe pod` shows the scheduler's events; the events say which filter the pod failed. The answer is in the cluster; the skill is reading it.
2. **You can defend the choice of *one* `kubectl apply` over many imperative commands.** The declarative apply produces the same end state whether you run it once, twice, or in CI on every commit. The cluster is level-triggered; your tooling should be too.
3. **You can read the source of a controller and understand it.** `pkg/controller/deployment/deployment_controller.go` in the Kubernetes repo is about 700 lines. Skim it after this lecture; you will recognize the watch, the reconcile, the diff. Reading one controller is worth ten tutorials on writing them.

---

## 14. Three anti-patterns from this lecture

**Anti-pattern 1 — talking to etcd directly.** You should never have to do this from application code. The only people who talk to etcd are: the API server, and humans during disaster recovery. If you find a tool or a tutorial that bypasses the API server to read or write etcd, treat it with extreme suspicion.

**Anti-pattern 2 — assuming the cluster's state matches what you posted.** You posted a Deployment with `replicas: 3`. The Deployment now exists in the API server. That is **not** the same as "three pods are running." The reconciliation loop takes time; the pods might be pulling, scheduling, crash-looping. The pattern: **post the desired state, then watch the actual state** (`kubectl rollout status deployment/hello`).

**Anti-pattern 3 — relying on edge-triggered behavior.** "I will scale up when CPU exceeds 80%." If you write that as "when CPU crosses 80%, scale up by 1," you have an edge-triggered controller, and it is fragile (missed events lead to missed scale-ups). The Kubernetes-idiomatic shape is "the desired replica count is a *function* of current CPU; reconcile toward it." The Horizontal Pod Autoscaler is the canonical example: it computes a target replica count from metrics, and adjusts the Deployment's `replicas` field. The Deployment controller does the rest.

---

## 15. Closing — the bridge to Lecture 3

You now know how the cluster works internally. You do not yet know how to compose its primitives into a working application. Lecture 3 is the core objects (Pod, ReplicaSet, Deployment, Service, ConfigMap, Secret) and the binding mechanism (labels and selectors) that ties them together. By the end of Lecture 3 you will be able to write the YAML for a stateless application from scratch — Deployment + Service + ConfigMap — without an example to copy from.

The control plane is the platform. The core objects are the language you use to talk to the platform. The next lecture is the language.

---

*If you find errors in this material, please open an issue or send a PR.*
