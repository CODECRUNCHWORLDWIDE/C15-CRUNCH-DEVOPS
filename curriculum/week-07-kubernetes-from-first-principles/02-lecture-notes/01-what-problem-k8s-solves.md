# Lecture 1 — What Problem Kubernetes Solves

> **Outcome:** You can defend, in one paragraph that does not use the word "orchestration," the problem Kubernetes was built to solve. You can sketch the four-step history (VMs → Docker → Docker Swarm → Kubernetes) on a whiteboard, name the dominant alternative at each step, and name what about Kubernetes won (and what about Docker Swarm and Mesos lost). You can name the five operational properties Kubernetes gives you — placement, restart, rolling updates, service discovery, configuration injection — and you can explain why a 2014 ops team had to write 30,000 lines of bash to get those properties and a 2026 ops team writes 30 lines of YAML.

The word "orchestration" is one of the worst pieces of jargon the cloud-native ecosystem produces. It is technically correct ("the coordination of multiple performers to a single composition," to borrow the musical metaphor) and it is operationally meaningless ("orchestration" tells you nothing about the problem you are solving). This lecture banishes the word and replaces it with five concrete operational problems and the order in which the industry solved them. By the end of the lecture you will be able to defend why Kubernetes won the 2014-2017 "container scheduler" race without saying "orchestration" once.

The lecture has three parts. Part 1 (Sections 1-4) is the history: what the industry was doing before containers, what Docker changed, and what Docker did not solve. Part 2 (Sections 5-8) is the five operational problems Kubernetes addresses and how each one looked in the pre-Kubernetes era. Part 3 (Sections 9-12) is the competitive landscape — Swarm, Mesos, Nomad, hand-rolled scripts — and a sober account of what Kubernetes won, what it lost, and what it still does poorly.

---

## 1. The world before containers (2005-2013)

In 2010, "production" looked roughly like this for a typical web company:

- A rack of physical servers in a colocation facility, or a small fleet of VMs at a cloud provider (AWS EC2 launched in 2006; by 2010, "the cloud" mostly meant EC2).
- Each server runs **one application**, configured with **Puppet** or **Chef** (the dominant configuration-management tools of the era; **Ansible** appeared in 2012 and won the mindshare battle a few years later).
- Deploys are done by SSH'ing into each server, running a deploy script, restarting the service. **Capistrano** (Ruby world) and **Fabric** (Python world) are the popular wrappers for "SSH into N hosts, run these commands."
- The application's dependencies are installed by `apt-get install` (or `yum install` on Red Hat shops) at provisioning time. The exact set of packages on a "production server" is a function of the Puppet manifest *plus every ad-hoc command run by an engineer at 3 AM* — a problem we covered last week as the mutable-infrastructure problem.

In this world, scaling out an application means buying more servers, running the same Puppet manifest against them, and hoping. *Hoping* is doing a lot of work in that sentence: hoping the new server's Linux kernel version is close enough, hoping the package versions in `apt-get install ruby` are close enough, hoping the network interface name is the same, hoping the disk layout is the same. The hope is misplaced often enough that "works on web-01, broken on web-03" was a normal incident shape.

> **Status panel — 2010-era production fleet**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  FLEET STATUS — 2010                                │
> │                                                     │
> │  Servers:        12 physical hosts in two racks     │
> │  Provisioning:   Puppet 2.6 + manual SSH            │
> │  Deploy tool:    Capistrano (per-app)               │
> │  Restart on crash:  monit / god / supervisord       │
> │  Service discovery: hand-edited /etc/hosts or DNS   │
> │  Rolling deploy:    write a bash script for it      │
> │  Load balancing:    nginx config, hand-edited       │
> │                                                     │
> │  Hours per release:  ~4-12, depending on luck       │
> │  Engineers required: 2 (deployer + on-call)         │
> └─────────────────────────────────────────────────────┘
> ```

The deploys took hours because every step was bespoke. The on-call engineer was needed because every step could fail in a different way. The two patterns the industry was reaching for — and that would crystallize as Docker and Kubernetes — were *package the application with all its dependencies* (Docker's answer) and *let the infrastructure decide where to run it* (Kubernetes's answer). Neither existed yet.

---

## 2. What Docker changed (2013-2015)

Docker 0.1 shipped in March 2013. The pitch was simple: take the Linux features that already existed for process isolation (**cgroups** for resource limits, **namespaces** for view isolation, **OverlayFS** for layered filesystems), wrap them in a CLI that any developer could use in 90 seconds, and ship the result with a registry (Docker Hub) so that images were *distributable*.

The two properties that mattered:

1. **Reproducibility.** A Docker image built from a Dockerfile produces the same bits on every machine that runs `docker build`. The image is content-addressed by a SHA-256 hash; the dependency set is frozen at build time. "Works on my machine" became "I will give you my machine in a 100 MB tarball."
2. **Portability.** A Docker image runs on any host with a Linux kernel and a Docker daemon. The same image runs on the developer laptop, on the CI runner, on the staging server, on the production server. The differences in those hosts — which Linux distribution, which kernel patch level, which `libc` version — stopped mattering for application-level concerns.

This was huge. The "works on my machine" problem had haunted ops for fifteen years. Docker solved it in two years of mainstream adoption. By 2015, "we use Docker" was a hiring filter; by 2017, it was an assumption.

What Docker did **not** solve:

- **Where do I run this image?** Docker by itself runs on one host. To run an image on twenty hosts, you need to SSH into twenty hosts and run `docker run` on each.
- **What happens when the container crashes?** Docker has a `--restart=always` flag, which restarts the container on the same host. If the host dies, the container does not come back.
- **How do I run an update?** "Stop the old container, start the new one" is one host. On twenty hosts, you need to write a bash script that does it gracefully — drain, swap, verify — without all twenty going down at once.
- **How do I find the running containers?** The container's IP changes every time it restarts. There is no DNS, no service registry, no virtual IP. You need to write one.
- **How do I pass configuration in?** Environment variables work for small inputs. For a large config file, you need to mount a volume — and the volume must be on every host that might run the container, which is another problem.

Each of these is a distinct operational concern. In the 2014-2017 era, every team that adopted Docker spent the next year **building each of these in-house**. Some did it well; most did it badly; almost all of them did the same work in parallel.

This is the gap Kubernetes filled. The whole rest of the lecture is, in some sense, a list of "what Docker did not solve, and what Kubernetes solves now."

---

## 3. The container-scheduler race (2014-2017)

Once "we should run containers across many hosts" was the consensus, the race was on for "and here is the tool that does it." The three serious entrants:

- **Docker Swarm** — Docker Inc.'s own answer, announced in late 2014 and integrated into the Docker daemon in 2016 ("Swarm mode"). The simplest model; the same CLI you used for one host now worked for N hosts. Best-in-class developer experience for the first 30 minutes; weakest at scale.
- **Apache Mesos + Marathon** — the older, more general scheduler (Mesos predated Docker; Twitter and Airbnb used it in 2011-2013) that gained a "container scheduler" persona via the Marathon framework. The two-level scheduler design (Mesos schedules resources to *frameworks*; frameworks schedule tasks within their share) was elegant but operationally complex. Lost the long-tail of midsize teams to Kubernetes because the operational complexity was not justified for fleets under 10,000 nodes.
- **Kubernetes** — Google's contribution, announced in mid-2014 (open-sourced from the internal Borg system; Brendan Burns, Joe Beda, and Craig McLuckie were the original team). Donated to the newly-formed Cloud Native Computing Foundation in 2015. By 2017, it had won.

The five things Kubernetes did that Swarm and Mesos did not, or did less well:

1. **A declarative API with reconciliation.** You describe the desired state ("3 replicas of this image, exposed on port 80"); a controller in the cluster makes it true. Swarm in 2015 was more imperative ("docker service create --replicas 3 ..."), and the reconciliation behavior was less precise. Mesos had reconciliation, but it lived in the framework, not the platform.
2. **The label-selector binding mechanism.** Pods are labeled (`app=hello`); Services select by label (`selector: app=hello`). The selector is decoupled from the deployment; you can run a canary by labeling some pods `version=v2` and pointing a separate Service at them. The pattern composes; it is one of the single best design choices in the project.
3. **A pluggable, well-versioned API.** The API is OpenAPI-described, every resource has an `apiVersion`, every resource has a `kind`, and the API is the *only* way into the cluster (`kubectl` is a thin client). CRDs (Custom Resource Definitions) let you extend the API surface without forking the project. The ecosystem of operators (the thousands of CRDs you can install) is downstream of this one decision.
4. **A first-class controller pattern.** Every built-in resource (Deployment, Service, Job, CronJob, StatefulSet, DaemonSet, ...) is a controller running the same reconciliation pattern. The pattern is fractal: you can write your own controllers (operators) that follow the same shape. Swarm had no equivalent abstraction; you used the features Docker shipped, and that was the menu.
5. **The community and the patience to build for a decade.** Kubernetes is not a project that "won" because it was technically dominant in 2015; many engineers preferred Swarm or Mesos at the time. It won because Google, Red Hat, CoreOS, IBM, and eventually every cloud provider committed to it as the standard for the next decade, and because the CNCF governance structure was credible enough that a Microsoft contributor and an AWS contributor could merge each other's pull requests without it feeling weird.

By 2017, "container scheduler" effectively meant Kubernetes. Swarm is still maintained and still good for small clusters; Mesos is still in use at a few large shops (Twitter shut down its Mesos cluster in 2020 in favor of Kubernetes, which was the symbolic end of the race). Nomad (HashiCorp, 2015) carved out a niche for "Kubernetes but simpler" and is the right pick for some teams; it is the minority answer.

---

## 4. The history in one paragraph

If a hiring manager asks "explain Kubernetes to me in one paragraph," this is the one you should be able to give:

> *Before 2013, deploying a web app meant SSH'ing into a fleet of servers and running a bash script. Docker (2013) made the application reproducible by packaging it with all its dependencies into an image. But Docker only ran on one host; to run an image on many hosts, you needed a scheduler. Kubernetes (2014, open-sourced from Google's Borg) is the scheduler that won the 2014-2017 race against Docker Swarm and Mesos. It works by giving you a declarative API ("I want 3 replicas of this image, exposed on port 80") and a set of controllers running on the cluster that converge the actual state to the desired state. The five operational problems it solves — placement, restart, rolling updates, service discovery, configuration injection — were each previously solved by hand-rolled scripts; Kubernetes solves them once, well, and for everyone.*

That paragraph is about 130 words. Memorize the shape, not the wording. The five operational problems are the rest of this lecture.

---

## 5. Problem 1 — Placement (which host runs this container?)

When you have one container and one host, "where does the container run?" is not a question. When you have a thousand containers and a hundred hosts, it is the question. Two hosts have spare CPU; one has a GPU; one is in a different rack; the container you are placing needs 2 GB of RAM and prefers a host in the same rack as the database it talks to. *Which host?*

The 2010-era answer was: the engineer picks. There was a spreadsheet (or, in better shops, a wiki page) that mapped applications to hosts. The engineer cross-referenced the wiki, picked a host, ran the deploy script. Placement was a human decision, performed once per application, refreshed whenever someone got around to it.

The Kubernetes answer is the **scheduler**: a process in the control plane that watches for pods in the `Pending` state, evaluates every node against the pod's requirements (resource requests, node selectors, affinity rules, taints and tolerations), and writes a `nodeName` field on the pod. The kubelet on the chosen node sees the binding, starts the containers, and reports back. The scheduling decision happens in milliseconds.

The scheduling algorithm has two phases: **filtering** (which nodes *could* run this pod?) and **scoring** (which of the eligible nodes is *best*?). The filter phase rejects nodes that violate hard constraints (insufficient CPU, GPU missing, taint not tolerated). The scoring phase ranks the survivors on soft preferences (least-loaded node, spread across zones, affinity to other workloads). The pod lands on the highest-scoring node. The full algorithm has 20+ filters and 10+ scorers and is configurable; the default behavior is good enough for 90% of cases.

> **Status panel — placement, before and after**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  PLACEMENT — 2010 vs 2026                           │
> │                                                     │
> │  2010:                                              │
> │    Decision-maker:  human, via wiki                 │
> │    Latency:         hours to days                   │
> │    Refresh rate:    never, after the first deploy   │
> │    Failure mode:    "the wiki is out of date"       │
> │                                                     │
> │  2026:                                              │
> │    Decision-maker:  kube-scheduler                  │
> │    Latency:         ~10 ms                          │
> │    Refresh rate:    on every pod creation           │
> │    Failure mode:    pod stuck "Pending" — easy to   │
> │                     diagnose with kubectl describe  │
> └─────────────────────────────────────────────────────┘
> ```

The win is not just latency; it is that **the placement decision is now machine-readable**. When a pod is stuck `Pending`, you can ask `kubectl describe pod <name>` and the scheduler tells you exactly why (insufficient memory on every node, no node tolerates the taint, no node matches the node selector). The diagnostic loop is minutes, not days.

---

## 6. Problem 2 — Restart (what happens when a container crashes?)

A process crashes. The 2010-era answer was a process supervisor (`monit`, `god`, `runit`, `upstart`, `systemd`). The supervisor restarted the process. If the host died, the supervisor died with it; the application was offline until the host was repaired.

The Kubernetes answer has three layers:

1. **Container restart** — the kubelet restarts a crashed container on the same node. This is the `restartPolicy` field on the pod (default: `Always`). The mechanism is built into the kubelet; it is fast (under a second) and free.
2. **Pod restart** — if the node dies, the kubelet on that node stops reporting to the API server. After a configurable grace period (5 minutes by default), the node is marked `NotReady` and the controllers reschedule the pods elsewhere. This is the second-order failure mode that monit/god could not handle.
3. **Replica restart** — a Deployment maintains N pods. If a pod is permanently broken (e.g., the container image is wrong), the Deployment notices the missing replica and creates a new one. The new one goes through scheduling, placement, container start. If it fails, the Deployment tries again. Pods are cattle.

The three layers compose. A crashed process is restarted in a second; a crashed host has its pods moved in 5 minutes; a broken deployment never has fewer pods than it should, period.

The cost is that "restarting" is no longer something you do explicitly. The cluster does it; if it does it badly, you debug the cluster. The `CrashLoopBackOff` state — a pod whose container keeps crashing and being restarted with an exponential backoff — is the most common pathological shape, and the first one we will debug in Exercise 1 and Challenge 1.

---

## 7. Problem 3 — Rolling updates (how do I deploy v2 without taking v1 down?)

The 2010-era rolling deploy was a bash script. Get a list of hosts; for each host: drain it from the load balancer, stop the old service, deploy the new version, start it, wait for the health check, return it to the load balancer, move on. The script was 50-200 lines per shop. Every shop wrote it. Most of them got the corner cases wrong (what if the health check returns true but the app is still warming up? what if the load balancer has stale state? what if the new version starts but the old version had outstanding connections?). The bug surface was enormous and the fixes were tribal.

The Kubernetes answer is the `Deployment` controller. You write:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: hello
  template:
    metadata:
      labels:
        app: hello
    spec:
      containers:
        - name: hello
          image: ghcr.io/example/hello:v1
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 2
            periodSeconds: 3
```

You change `:v1` to `:v2`. You run `kubectl apply -f deployment.yaml`. The Deployment controller does this:

1. Create one new pod from the v2 template (`maxSurge: 1` permits one extra pod beyond the 3 desired).
2. Wait for the new pod's `readinessProbe` to pass. Until then, the Service does not route traffic to it.
3. Once the new pod is ready, delete one of the v1 pods.
4. Loop until all three pods are v2.

`maxUnavailable: 0` guarantees that you never have fewer than 3 ready pods. `maxSurge: 1` bounds the extra resource cost during the roll. The whole sequence takes about 30 seconds for a normal app, completes without human intervention, and is *fully reversible* — `kubectl rollout undo deployment/hello` runs the same logic in reverse.

The 200-line bash script becomes a 25-line YAML. The corner cases are handled by code Google has been hardening since 2014. *This* is the operational property that converted teams to Kubernetes.

---

## 8. Problem 4 — Service discovery (how do clients find the pods?)

A pod's IP changes every time it restarts (or moves to a new node). If a client hardcodes the IP, the client breaks on every restart. The 2010-era answers were:

- **DNS, hand-edited** — write a script that re-writes `/etc/hosts` or a DNS zone file whenever a deploy happens. Cache invalidation problems are constant.
- **Service registry** — Consul (HashiCorp, 2014), etcd, or ZooKeeper. The app registers itself on start; clients query the registry. Works well, but you have to wire it into every app.
- **Load balancer in front of everything** — every service has an LB; clients talk to the LB's stable IP. Works, but every service costs an LB, and the LB itself needs management.

The Kubernetes answer is the **Service** resource. A Service is a stable virtual IP that selects pods by label. When you write:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: hello
spec:
  selector:
    app: hello
  ports:
    - port: 80
      targetPort: 8080
```

The cluster assigns a virtual IP (e.g., `10.96.42.17`) to the Service. Inside the cluster, any pod can connect to `10.96.42.17:80` and the connection is load-balanced across all pods labelled `app=hello`. Even better: the cluster registers a DNS name (`hello.default.svc.cluster.local`) that resolves to the virtual IP, so client code does not need to know the IP at all.

The mechanism is implemented by **kube-proxy** on each node, which programs `iptables` (or `IPVS`) rules that intercept traffic to `10.96.42.17:80` and DNAT it to one of the pod IPs. The list of pod IPs comes from the **EndpointSlice** resource, which a controller in the control plane keeps in sync with the pods matched by the Service's selector. When a pod is added, the EndpointSlice updates, kube-proxy reprograms iptables, the new pod starts receiving traffic — all within about 100 ms.

The whole pattern — virtual IP, label-based selection, automatic DNS, automatic iptables — is the single feature that made Kubernetes useful for production at large scale. Service discovery in 2010 was a project; in 2026 it is a 10-line YAML.

We will see the Service abstraction in detail in Lecture 3 and Exercise 3. The thing to internalize now is: **the virtual IP is stable; the pod IPs are not; the binding is by label**.

---

## 9. Problem 5 — Configuration and credential injection

The application needs configuration (a database URL, a feature flag, a log level) and credentials (a database password, an API key). In 2010, the answers were:

- **Environment variables** — for short, non-secret values. Set in the deploy script; visible in `ps`.
- **Configuration files** — for longer values. Templated by Puppet/Chef at provisioning time. Refreshing required a re-run of the configuration manager.
- **Secrets** — usually the same as configuration files, with file permissions set to `0600` and a prayer that no one ever read them. Vault (HashiCorp, 2015) gave a better answer; before Vault, the answer was "do not check the prod password into git." This rule was broken often.

The Kubernetes answer is **ConfigMap** (non-secret configuration) and **Secret** (secret configuration). Both are key-value blobs stored in etcd; both can be mounted into a pod as files or injected as environment variables. The relevant YAML shape:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hello-config
data:
  LOG_LEVEL: info
  GREETING: "Welcome to C15 Week 7"
---
apiVersion: v1
kind: Secret
metadata:
  name: hello-secret
type: Opaque
stringData:
  DATABASE_PASSWORD: "fake-password-please-rotate"
```

The pod references them:

```yaml
spec:
  containers:
    - name: hello
      image: ghcr.io/example/hello:v1
      envFrom:
        - configMapRef:
            name: hello-config
        - secretRef:
            name: hello-secret
```

The cluster injects every key from the ConfigMap and Secret as environment variables in the container. Updating the ConfigMap (e.g., changing `LOG_LEVEL` from `info` to `debug`) is one `kubectl apply` — though, importantly, the pod is **not** restarted automatically when the ConfigMap changes (this is a footgun we cover in Lecture 3).

The win is that configuration and secrets are now first-class cluster citizens: they are versioned in git (in a GitOps workflow — Week 6), they are accessible via the same RBAC system as everything else, and they are uniform across applications. Every pod gets its config the same way; you no longer write per-app boilerplate to read a config file.

The honest cost: **Secrets are base64-encoded by default, not encrypted**. The base64 is for byte-safety, not security. To get real encryption-at-rest, you enable the API server's encryption provider (Section 8 of `kubernetes.io`'s "Encrypting Secret Data at Rest"); to keep secrets out of git, you use Sealed Secrets or SOPS (covered in Week 6 homework Problem 6). The "Secret" name is a 2014 design decision that the project will not change for compatibility reasons.

---

## 10. The competitive landscape — what lost, and why

For each Kubernetes alternative, a fair epitaph:

**Docker Swarm.** The closest competitor. The same CLI you used for one container worked for many; you could `docker service create --replicas 3` and it just worked. What it never matched was the API surface (Swarm's API was less expressive), the extensibility (no CRD equivalent), and the ecosystem (no Argo, no Flux, no Prometheus operator). Swarm is still in the Docker CLI; the team that built it now works on Kubernetes at Mirantis. It is a fine choice for a 5-node cluster running 10 services; nobody picks it for a new project in 2026.

**Apache Mesos + Marathon.** The technically most ambitious; the operationally most complex. Mesos's two-level scheduler was elegant — a single cluster could run Spark jobs, Kafka brokers, web services, and batch workloads through different frameworks, each with its own scheduling logic. Kubernetes does this less elegantly (one scheduler for everything; CRDs and operators to specialize), but it is more accessible. Twitter shut down its Mesos cluster in 2020 in favor of Kubernetes; the symbolic end of the project's relevance for new deployments. Mesos is still developed (Apache project) but the community is small.

**Nomad (HashiCorp, 2015).** The conscious "Kubernetes but simpler" alternative. Nomad's binary is 80 MB and runs in one process; Kubernetes is dozens of binaries and gigabytes of dependencies. Nomad supports non-container workloads natively (VMs, Java JARs, raw exec). For a team that wants HashiCorp's whole stack (Vault, Consul, Nomad, Terraform), it is the coherent pick. The community is much smaller than Kubernetes's; the ecosystem is much shallower. The right answer for some teams, never the broad consensus.

**Hand-rolled scripts.** This is the option that won't die. Every five years there is a "we don't need Kubernetes for our 4 services" blog post; the post is correct in the small. The post is wrong in the large: the moment you have more than a handful of services, you start re-implementing the cluster's primitives — placement (a `hosts.yml` file), restart (a `systemd` unit), rolling deploy (a bash script), service discovery (Consul or DNS), config injection (more bash). At about 20 services and 5 hosts, the cost crosses Kubernetes's setup cost; at 50 services and 20 hosts, the hand-rolled answer is unmaintainable. The crossover happens faster than teams expect.

The 2026 verdict: **Kubernetes is the answer if you have more than a handful of services**. The teams that pick something else (Nomad, ECS, Cloud Run, fly.io) usually pick a *higher-level* abstraction, not a lower one. Going below Kubernetes is going back to 2013.

---

## 11. Where Kubernetes is still bad

A sober assessment, because pretending Kubernetes is good at everything is what produces the 200-page YAML files of doom you have seen on GitHub.

- **Onboarding.** A new engineer needs about three weeks to be productive in a Kubernetes shop. There is no shortcut; the conceptual surface is large. This week's purpose is to compress that to one week by giving the model first.
- **Stateful workloads.** Kubernetes was designed for stateless workloads; the `StatefulSet` resource exists but is the awkward cousin. Running Postgres or Kafka on Kubernetes is possible (operators help) but harder than running them on a VM with a managed-disk attached. We will see this in Week 10 (operators).
- **Cluster networking.** The Service abstraction is great until it isn't. Cross-cluster networking, multi-cluster service discovery, north-south traffic — these are still gaps the ecosystem is filling (Cilium Cluster Mesh, Istio, Linkerd, Gateway API). Production teams spend significant time on this. We touch ingress in Week 8.
- **The YAML.** YAML is a bad configuration language. Helm and Kustomize make it less bad. The Argo CD `ApplicationSet` and Flux's `Kustomization` make it less bad. CEL (Common Expression Language) for validation makes it less bad. The base case is still YAML with whitespace-sensitive lists. Live with it.
- **The blast radius of an incident.** When the API server is down, *everything* is down: you cannot deploy, cannot read state, cannot scale. The API server is the single point of failure in the cluster's control plane. HA control planes mitigate this; they do not remove it.

The honest version of "Kubernetes won" is "Kubernetes won the *centroid* of cluster orchestration; the tails are still open problems." This week is the centroid.

---

## 12. The bridge to Lecture 2

You now know what problem Kubernetes solves and why it won. You do not yet know how it works internally. Lecture 2 opens the control plane: the API server, etcd, the scheduler, the controller manager, the kubelet, kube-proxy. By the end of Lecture 2 you will be able to draw the architecture on a whiteboard from memory; by the end of Lecture 3 you will be able to write the YAML for any of the core objects without reaching for an example; by the end of the week you will have run all of it.

A note on the order. The reason we put Kubernetes after GitOps in C15 (last week was Week 6 on GitOps; this week is Week 7 on Kubernetes itself) is pedagogical: by the time you meet the Kubernetes control plane, you have already seen what *manages* it (Argo CD, Flux). The "what does this cluster look like to its operator?" question is answered before you meet "what is the cluster made of?". Many curricula reverse this order and produce engineers who can write a `Deployment` but cannot explain why a `Deployment` is the right granularity for a GitOps reconciliation loop. By doing GitOps first, you already know.

---

## 13. Three anti-patterns from this lecture

You will see these in the wild. Avoid each.

**Anti-pattern 1 — using `kubectl run` in production.** `kubectl run nginx --image=nginx` creates an imperative pod that is not managed by any controller. If the pod crashes, nobody restarts it. If the node dies, the pod is gone. `kubectl run` is fine for a 30-second debugging container; it is never the answer for "I want this service to keep running." The production shape is *always* a `Deployment` (or `StatefulSet`, or `Job`) declared in YAML.

**Anti-pattern 2 — hardcoding pod IPs in client code.** A pod's IP changes on every restart. If you read a pod's IP and put it in a config file, the config file becomes wrong the moment the pod restarts. The mechanism for "find the pods" is a **Service**, by name (`hello.default.svc.cluster.local`). If you find yourself reading pod IPs, you are working against the abstraction.

**Anti-pattern 3 — treating the cluster as a black box.** This is the one this week is built to prevent. If you only know `kubectl apply` and `kubectl get`, the first incident that does not match a tutorial will defeat you. Read `kubectl describe` output. Read `kubectl logs --previous`. Read the events the cluster emits (`kubectl get events --sort-by='.lastTimestamp'`). The cluster is verbose about what it is doing; the skill is reading the verbosity.

---

## 14. Closing — the five sentences

The five sentences that summarize this lecture, in case you are reviewing for the quiz:

1. Docker (2013) solved "package the application with all its dependencies"; it did not solve "run the package on a fleet of hosts."
2. Kubernetes (2014, from Borg) solved the fleet problem by giving you a declarative API and a set of controllers that converge the cluster to the declared state.
3. The five operational problems it addresses are: placement (the scheduler picks the host), restart (controllers maintain N replicas), rolling updates (the Deployment controller swaps versions safely), service discovery (Services are stable virtual IPs that select pods by label), and configuration injection (ConfigMaps and Secrets mount into pods).
4. Each of those was a hand-rolled bash script in 2010; each is a YAML resource in 2026.
5. The competitors (Swarm, Mesos, Nomad) each solved a subset; Kubernetes won because of the declarative API, the label-selector binding mechanism, the extensibility via CRDs, and a decade of community work.

The next lecture is the inside of the cluster.

---

*If you find errors in this material, please open an issue or send a PR.*
