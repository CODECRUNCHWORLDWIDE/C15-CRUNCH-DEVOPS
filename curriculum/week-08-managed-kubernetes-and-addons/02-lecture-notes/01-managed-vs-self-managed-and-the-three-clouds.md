# Lecture 1 — Managed vs Self-Managed, and the Three Clouds

> *Running etcd in production is a full-time job for someone who is good at distributed systems. Outsourcing that job to a cloud provider is, for almost every cluster you will ever run, the correct decision.*

In Week 7 you ran a `kind` cluster and inspected every component. The API server was a process you could `kubectl exec` into. etcd was a binary writing to a file on a Docker container's filesystem. The scheduler was a Go program with a 200-line main package. You saw the entire control plane because, on `kind`, it was visible.

The version of this conversation that happens in industry is: you do not see the control plane because you do not run the control plane. You log into the Google Cloud console, you press a button, and 90 seconds later you have a `kubectl` context pointing at a cluster whose API server, etcd, scheduler, and controller manager are operated, upgraded, and backed up by Google. You never SSH to those machines. You never apply a security patch to them. You never page yourself at 3 a.m. because etcd's WAL filled the disk. That is what "managed Kubernetes" is — and it is what almost every Kubernetes cluster running in production in 2026 is.

This lecture is about the decision: when to use a managed cluster, when to self-manage, and how the three big managed offerings (GKE, EKS, AKS) compare. We will spend a lot of pages on the trade-offs, because the decision matters and because the marketing on every cloud provider's home page is unhelpfully uniform. By the end you will be able to argue both sides, and you will know which side is correct for which kind of organization.

---

## 1. Why managed Kubernetes exists at all

In 2014 — the year Kubernetes was open-sourced — there was no managed Kubernetes service. If you wanted a cluster, you ran one. You installed the binaries, you ran etcd, you ran the API server, you wrote systemd units, you configured kubelet on every node. Google had an internal version (Borg) that they did not sell. AWS had ECS, which is not Kubernetes. Microsoft had no container service worth naming.

The reasons people ran their own clusters in 2014-2016 were necessity, not preference:

1. **There was nothing else.** The CNCF was new. The first managed offering — GKE — landed in late 2015 and was rough; the first EKS in mid-2018, the first AKS GA in mid-2018. Until then, you ran it yourself or you did not run Kubernetes.
2. **The audience was sophisticated.** The teams that picked Kubernetes in 2014 were the ones who could run etcd. The barrier to entry was high; the people who cleared it were SREs at Google, Box, Tigera, CoreOS — people who could write production distributed systems.
3. **The cluster was the product.** For platform teams selling Kubernetes-as-a-product to their internal developers (Box, Goldman Sachs, the original Kubeflow teams), the cluster was the artifact. Operating it was the job.

By 2026, none of those three reasons applies to most teams. Managed Kubernetes is mature, the audience is broad, and for almost every team the cluster is *infrastructure* — a thing the application runs on, not the thing the team ships. The default has flipped.

### The single line that explains it

> The reason managed Kubernetes won is **etcd**. Everything else in the control plane can be operated by a careful generalist. etcd cannot.

etcd is a distributed strongly-consistent key-value store. It is the only stateful component in the control plane. It uses the Raft consensus algorithm. Its operational footguns are subtle: WAL size limits, snapshot management, member replacement during a partition, defragmentation that must be done one member at a time, the cost of a failed-leader-during-snapshot that loses ~30 seconds of writes. A team running their own cluster needs at least one engineer who can answer the question "what happens when etcd hits its 8 GB default size limit?" in detail, with the runbook, in three minutes. Most teams do not have that engineer and should not need to.

A managed cluster has Google's etcd-on-call rotation. It is invisible to you because Google has decided it is not your problem.

### The cost calculation that decides it

For most teams, the managed-vs-self-managed decision is also a cost calculation, and the cost calculation almost always favors managed.

A back-of-envelope: if you self-manage a Kubernetes cluster that meets the same SLA as GKE (99.95% control plane availability), you need:

- 3 control-plane nodes (etcd quorum), each $50-200/month depending on size and region. Call it $300/month.
- Backup of etcd: incremental snapshots to cold storage. $10/month.
- Monitoring of the control plane: Prometheus + alerts on etcd lag, API server p99 latency, scheduler queue depth. $30/month if you buy a hosted monitoring service.
- One half of an engineer's time. At U.S. salaries, that is roughly $7,000-10,000/month fully loaded.

Total: $7,400-10,300/month.

GKE Autopilot's control plane is *free* for one zonal cluster (the free tier covers it). GKE Standard's control plane is $73/month. EKS is $73/month. AKS is $0/month on the basic tier. The compute (nodes, pods) is the same cost on either model. So the question is: are you paying $73-$0/month for the control plane, or $7,400/month plus the operational risk?

The answer for almost everyone, including teams that pride themselves on technical depth, is: **pay the $73**.

---

## 2. The four trade-off dimensions

The standard four-axis trade-off when picking managed vs self-managed:

### Dimension 1 — Operational burden

| | Managed | Self-managed |
|---|---|---|
| Control plane upgrades | Cloud provider does it, on a schedule you partially control | You do it, with a runbook, every quarter |
| etcd backup | Automatic, retained for 30+ days | You write the script, you test the restore |
| Security patches (control plane) | Automatic, often the same day as upstream release | You apply them within the team's SLA |
| Multi-zone HA | Automatic on GKE regional clusters | You design and operate it |
| Cluster autoscaler | Bundled and supported | You install and maintain it |

The asymmetry is severe. Self-managing is *not impossible* — Kubernetes has good documentation, and projects like `kops` and `kubespray` make it tractable — but the operational tax is real and it is paid every week.

### Dimension 2 — Cost

The control-plane cost differential is small in cloud-provider dollars and large in engineer-hours:

- GKE Autopilot: $0/month control plane (free tier), per-pod-vCPU-second pricing for compute. A small app might run for $5-20/month total.
- GKE Standard: $73/month control plane, standard VM pricing for nodes.
- EKS: $73/month control plane, standard EC2 pricing for nodes.
- AKS: $0/month control plane (free tier), standard VM pricing for nodes. Microsoft includes the control plane in the price of running it.
- DOKS (DigitalOcean Kubernetes Service): $0/month control plane, droplet pricing for nodes.
- Linode LKE: $0/month control plane, Linode pricing for nodes.
- Self-managed on three $50/month VMs: $150/month for the control plane plus your time.

The cost story is: for managed clusters, the control plane is a flat fee or free, and your bill scales with the workload. For self-managed, the cost is dominated by your time, not by the VMs.

### Dimension 3 — Control over the control plane

This is the dimension where self-managed wins, and it wins less often than its advocates think:

| Feature | Managed | Self-managed |
|---|---|---|
| Custom admission webhooks | Yes (you install them as workloads) | Yes |
| Custom kubelet flags | Limited; provider-specific | Yes, full control |
| Custom etcd tuning | No | Yes |
| Custom scheduler | Yes (you run a second scheduler) | Yes |
| Upgrade timing | Partially yours (maintenance windows, channel selection) | Fully yours |
| Version pinning | Limited; provider rolls minor versions on schedule | Fully yours |
| API server feature gates | Limited; provider-specific | Fully yours |
| Audit log configuration | Limited; provider-specific export | Fully yours |

The cases where the right column matters are: highly regulated industries with custom audit requirements, research clusters that need bleeding-edge feature gates, organizations with their own security baseline that diverges from provider defaults. These are a small fraction of all Kubernetes users.

### Dimension 4 — Lock-in

Lock-in is the dimension that is overrated by skeptics and underrated by advocates. The truth is in the middle.

**What is portable across all three clouds:**

- Every core API (`v1`, `apps/v1`, `batch/v1`, `networking.k8s.io/v1`). Your `Deployment`, `Service`, `Ingress`, `ConfigMap`, `Secret` manifests are unchanged.
- Every well-known CRD if you install the open-source operator (cert-manager, ArgoCD, NGINX Ingress). The portable add-ons.
- `kubectl`, `helm`, and every tool above the cluster API.

**What is *not* portable:**

- Annotations on `Service` and `Ingress` that drive provider-specific load balancers. `cloud.google.com/load-balancer-type: "Internal"` means nothing on AWS.
- Workload Identity vs IRSA vs AAD Workload Identity. Three completely different mechanisms for the same problem (pod-to-cloud authentication).
- Storage classes. The CSI driver names differ; the volume bindings may not be portable across clouds at all.
- Network policies that depend on provider-specific CNI features.
- Logging, monitoring, audit log shapes (each provider's "send logs to our log product" annotation is its own).

The way to manage lock-in is to **keep the manifest surface open-source-first**: NGINX Ingress, not the GKE Gateway. cert-manager, not Google-managed certificates. ArgoCD, not Cloud Deploy. external-dns, not Cloud DNS-as-the-only-option. The mini-project this week is structured to make this rule concrete.

---

## 3. The three clouds: GKE, EKS, AKS

There are more than three managed Kubernetes services (Linode LKE, DigitalOcean DOKS, Oracle OKE, IBM Cloud Kubernetes Service, OVH, Vultr, Civo, Scaleway, Akamai, and others), and they are all fine for what they are. But the three that dominate the market — GKE, EKS, AKS — are the ones you will encounter in industry, and they are the three this lecture covers in depth.

### 3.1 GKE — Google Kubernetes Engine

GKE is the oldest managed Kubernetes service and the one most aligned with the project's own conventions. Kubernetes was open-sourced by Google; the project's defaults are GKE's defaults; the project's PRs land on GKE first. If you want to learn Kubernetes by using a managed cluster, GKE is the cleanest path.

**The two modes:**

- **GKE Standard.** You manage node pools; Google manages the control plane. The mode most teams started on.
- **GKE Autopilot.** You manage pods; Google manages node pools too. The mode Google recommends in 2026 for greenfield projects.

**Cluster creation:**

```bash
# Autopilot - one command, no node-pool decisions
gcloud container clusters create-auto my-cluster \
  --region=us-central1 \
  --release-channel=regular

# Standard - more flags, more control
gcloud container clusters create my-cluster \
  --region=us-central1 \
  --release-channel=regular \
  --num-nodes=3 \
  --machine-type=e2-medium \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=10
```

**The IAM model:** Workload Identity. A Kubernetes ServiceAccount in the cluster is annotated with the email of a GCP service account; the GKE metadata server forges a token for the GCP SA when the pod calls a Google API. No long-lived JSON key. This is the cleanest pod-to-cloud IAM story of the three clouds; Lecture 2 covers it in detail.

**The networking model:** VPC-native by default since 2020. Pod IPs come from a secondary IP range in the cluster's subnet. Routes are not used; the VPC routes pod traffic natively. This is faster than the older route-based model and is the only mode that supports private clusters cleanly.

**The default ingress story:** GKE bundles a Gateway controller (the cloud-provider's implementation of the upstream Gateway API). You can also install NGINX Ingress; we will, because NGINX is portable.

**The free tier:** One zonal cluster's control plane is free indefinitely. This is the reason GKE is the canonical "try managed Kubernetes for $0" path.

### 3.2 EKS — Elastic Kubernetes Service

EKS is AWS's managed Kubernetes. It is more recent than GKE (GA in 2018), more enterprise-flavored (deep IAM integration, deeper VPC integration, deeper AWS-service integration), and more popular among AWS-native shops (which is most of the U.S. enterprise market).

**The two modes (rough analog to GKE's modes):**

- **EKS with managed node groups.** You define node groups (machine type, sizes, auto-scaling); AWS manages the EC2 instances behind them.
- **EKS with Fargate.** Pods schedule onto Fargate (AWS's serverless compute), one pod per Fargate "micro-VM". The rough analog to GKE Autopilot.

**Cluster creation (via `eksctl`, the de facto tool):**

```bash
# Managed node groups
eksctl create cluster \
  --name my-cluster \
  --region us-east-2 \
  --node-type t3.small \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 4

# Fargate
eksctl create cluster \
  --name my-cluster \
  --region us-east-2 \
  --fargate
```

**The IAM model:** IRSA — IAM Roles for ServiceAccounts. The cluster has an OIDC provider; you create an IAM role with a trust policy that names the cluster's OIDC issuer and a specific KSA; the pod's KSA is annotated with the role ARN; the AWS SDKs find the projected service account token and exchange it for short-lived AWS credentials. Different mechanism than Workload Identity, same outcome.

**The networking model:** AWS VPC-CNI by default — pod IPs are real ENI IPs in the VPC. This is the canonical "pods get VPC IPs" pattern; it makes security groups and VPC peering work naturally; it caps the number of pods per node at the ENI/IP density of the instance type.

**The default ingress story:** AWS Load Balancer Controller (the AWS-maintained controller) translates Ingress into ALB. NGINX Ingress works fine on EKS too; many teams pick it for the same portability reason.

**The cost story:** $73/month control plane plus standard EC2 pricing. No free tier on the control plane.

### 3.3 AKS — Azure Kubernetes Service

AKS is Microsoft's managed Kubernetes. It is the cheapest control plane of the three (free on the standard tier), it integrates deeply with Azure AD and the Microsoft enterprise stack, and it is the most popular managed Kubernetes in regulated-industry / Microsoft-shop environments.

**The mode (only one mainstream mode):**

- **AKS with node pools.** Standard managed node pools. AKS has a Virtual-Node feature (pods on Azure Container Instances) but it is less mainstream than EKS Fargate or GKE Autopilot.

**Cluster creation:**

```bash
az aks create \
  --resource-group my-rg \
  --name my-cluster \
  --location eastus \
  --node-count 2 \
  --node-vm-size Standard_B2s \
  --enable-managed-identity \
  --enable-workload-identity \
  --enable-oidc-issuer
```

**The IAM model:** Azure AD Workload Identity. The cluster runs an OIDC issuer; you federate an Azure AD application with the issuer; the pod's KSA is annotated with the AAD client ID. Different mechanism again; same outcome.

**The networking model:** Two options, kubenet (route-based, simpler) and Azure CNI (pods get VNet IPs). Most production clusters pick Azure CNI for the same reasons EKS picks VPC-CNI.

**The default ingress story:** Application Gateway Ingress Controller (the Azure-maintained controller) or NGINX Ingress. Same pattern as the other two clouds.

**The cost story:** Free control plane on the standard tier. Uptime SLA tier is $0.10/cluster/hour (~$73/month) for higher availability commitments.

---

## 4. The side-by-side cheat sheet

The table below is the cheat sheet you should print and put above your desk for the next year. The patterns are stable; the version numbers shift slightly each year.

| Feature | GKE | EKS | AKS |
|---------|-----|-----|-----|
| **Control plane cost** | Free (1 zonal cluster) or $73/mo | $73/mo | Free (standard) or $73/mo (uptime SLA) |
| **Serverless-pods mode** | GKE Autopilot | EKS Fargate | AKS Virtual-Node (less mainstream) |
| **Default node mode** | GKE Standard with node pools | Managed node groups | Node pools |
| **Cluster creation CLI** | `gcloud container clusters create[-auto]` | `eksctl create cluster` | `az aks create` |
| **Pod-to-cloud IAM** | Workload Identity (KSA -> GSA) | IRSA (KSA -> IAM Role) | AAD Workload Identity (KSA -> AAD app) |
| **Default networking** | VPC-native (since 2020) | AWS VPC-CNI (ENI per pod IP) | Azure CNI or kubenet |
| **Cluster autoscaler** | Built-in | Built-in | Built-in |
| **Provider-bundled ingress** | Gateway (GKE Gateway) | AWS Load Balancer Controller | App Gateway Ingress Controller |
| **Default storage class** | `standard-rwo` (Persistent Disk) | `gp2` / `gp3` (EBS) | `default` / `managed-csi` (Azure Disk) |
| **Free tier** | 1 zonal Autopilot or Standard cluster | None on control plane | Free on basic tier |
| **Maintenance windows** | Configurable, channel-based | Configurable | Configurable |
| **API audit logs** | Cloud Audit Logs (configurable) | CloudWatch | Azure Monitor |
| **Documentation depth** | Very deep; aligns with upstream | Very deep; AWS-flavored | Very deep; Microsoft-flavored |
| **Community share (2026)** | ~25% of managed K8s | ~50% of managed K8s | ~20% of managed K8s |

The "community share" line is approximate and varies by survey, but the order is stable: EKS leads on raw cluster count (because AWS leads the cloud market), GKE leads on technical alignment with upstream, AKS leads in Microsoft-shop environments.

---

## 5. When self-managed is actually correct

Self-managing Kubernetes is the right call when:

1. **You are the cloud provider.** Linode LKE, DOKS, Civo Kubernetes — these companies' Kubernetes services are themselves self-managed clusters they operate. If you are building infrastructure-as-a-service, you do it yourself.
2. **You have a hard data-residency requirement** that no managed offering meets. On-premise clusters at financial institutions, defense contractors, and some healthcare systems fall in this bucket. The Kubernetes-on-bare-metal pattern (`kubeadm`, `kops`, `kubespray`, Rancher) exists for these cases and is well-supported.
3. **Your team's primary product is the cluster.** Platform engineering teams that sell internal Kubernetes-as-a-service to their developers may pick self-managed for the same reason a database vendor picks self-managed for their product — operating the thing is the job.
4. **You have a custom kernel / scheduler / runtime requirement** that no managed offering supports. Research clusters, HPC clusters, GPU clusters with custom MIG configurations sometimes fall here.
5. **You are learning.** The cluster is a teaching artifact. This is the only reason every C15 student should self-manage at least once — Week 7 — and then move on.

Outside those five cases, self-managing in production is more expensive than the engineering hours it costs and less reliable than the managed offering it replaces. The "we want to control our own destiny" instinct is real, but the cost of controlling etcd's destiny is rarely worth what controlling it buys.

---

## 6. The migration story (managed-to-managed)

Once you accept that managed wins, the next question is: how locked in are you? The answer, when you keep the manifests open-source-first, is: not much. The patterns we will install in Lecture 3 — NGINX Ingress, cert-manager, ArgoCD — work on all three clouds and on `kind` and on bare metal. The vendor-specific glue is small and concentrated in a handful of well-known annotation patterns:

- `Service` of type `LoadBalancer`: the provider issues a load balancer. The annotations to *tune* that load balancer differ across providers; the bare resource is portable.
- Storage class names: differ across providers. The fix is to declare your own `StorageClass` resources and reference them by name; you redeclare per provider.
- Workload Identity / IRSA / AAD WI: differ entirely. The fix is to put the binding logic in a small adapter library (the cloud SDK does most of this for you in 2026) and treat the KSA-to-cloud-identity setup as bootstrap.

When the migration story is "redeclare a handful of StorageClasses and a handful of pod-to-cloud bindings", multi-cloud or cloud-to-cloud migration is tractable in days, not quarters. When the migration story is "rewrite the entire deploy pipeline because we built it on Cloud Run / ECS / Container Apps and now we want to leave", it is quarters. The choice to put workloads on a managed Kubernetes cluster — rather than on the cloud provider's higher-level container service — is itself a portability choice.

---

## 7. The decision flow

If you take one diagram out of this lecture, take this one:

```
                    Are you on a major cloud (GCP, AWS, Azure, DO, Linode)?
                          /                                       \
                       Yes                                         No  -- (on-prem, edge, etc.)
                        |                                           |
              Do you have a custom                       Use kubeadm / kops / Rancher;
              kernel / scheduler /                       you are in the
              data-residency req?                        self-managed bucket.
                  /          \
               Yes            No
                |              |
        Self-managed       Use managed.
        on bare metal      Pick the cloud you already use.
                                   |
                       Does the workload need
                       fine-grained node control
                       (GPU MIG, custom kubelet flags)?
                              /         \
                           Yes           No
                            |             |
                    GKE Standard /    Autopilot (GKE),
                    EKS managed       Fargate (EKS),
                    node groups /     standard node pool (AKS)
                    AKS node pools    -- the serverless-flavor
                                          variants if available
```

For a team starting on Kubernetes in 2026 with no custom requirements, the answer is almost always: **GKE Autopilot**, or, if your shop runs on AWS, **EKS with Fargate**, or, if your shop runs on Azure, **AKS with default node pools** (Azure has no Autopilot equivalent at GA quality yet).

---

## 8. What we will actually do this week

The lecture-to-practice arc:

- **Tuesday (Lecture 2):** GKE Autopilot in depth. The constraints, the node-pool model that Standard exposes and Autopilot hides, the cluster autoscaler, Workload Identity step-by-step.
- **Wednesday (Lecture 3):** The add-on stack. NGINX Ingress, cert-manager, external-dns, ArgoCD. Why these four are the canonical baseline.
- **Thursday / Friday (Exercises + mini-project):** Install all of it on `kind`. The same manifests would work on GKE Autopilot.
- **Saturday (sidebar):** Walk through what changes if you take the kind cluster's manifests and apply them to EKS or AKS. Usually: the `Service` type might switch from `ClusterIP` (kind, with Ingress doing the work) to `LoadBalancer` (managed cloud), a `StorageClass` might get a different name, and a Workload Identity binding might get rewritten as an IRSA trust relationship. That is it.

---

## 9. Common questions

**"If managed is better, why do all the tutorials show self-managed?"** Because tutorials are educational. Showing the control plane is the point of a tutorial; hiding it is the point of a managed cluster. Industry runs managed; tutorials show self-managed; both are correct in their own context.

**"Won't I miss out on understanding the cluster?"** No, because you spent Week 7 inspecting every component on `kind`. The mental model is yours. A managed cluster is the same Kubernetes; what changes is who pages whom when etcd's disk fills up.

**"What about a 'middle ground' like Rancher RKE2 or Talos?"** Both are excellent. They are still self-managed (you operate them), but with a much smaller operational footprint than `kubeadm` from scratch. They sit in the "I need on-prem or air-gap and I want operational sanity" bucket. Not relevant for greenfield cloud workloads.

**"Is the GKE Autopilot free tier really free?"** Yes. One zonal Autopilot cluster's control plane is free indefinitely as of May 2026. You pay only for pod-vCPU-seconds. A small workload runs for single-digit dollars per month. The free tier is the reason this week's optional cloud-side exercises pick GKE Autopilot — it is the only managed Kubernetes you can experiment with for $0 control-plane cost without time limits.

**"What about Knative / Cloud Run / ECS / Container Apps — should I just use those?"** Maybe. They are higher-level container services that hide Kubernetes entirely. They are great for stateless HTTP apps that fit their model. They are worse for anything that does not — stateful workloads, custom protocols, complex networking, long-running batch. The Kubernetes-via-managed-cluster pattern is the most portable middle ground. We teach it because it is the one that generalizes.

---

## 10. Closing — what to remember

Three things from this lecture:

1. **etcd is the reason managed Kubernetes wins.** Everything else can be hand-operated by a careful generalist; etcd cannot, and outsourcing etcd's operational burden is what you are paying for.
2. **The three big clouds (GKE, EKS, AKS) are 90% identical and 10% different.** The 90% is the Kubernetes API, the manifests, the `kubectl`. The 10% is provider-specific glue (load balancer annotations, IAM mechanism, storage class names). Keep the 90% open-source-first and the 10% will not lock you in.
3. **The default for greenfield is GKE Autopilot** (or EKS Fargate if you are on AWS; or AKS if you are on Azure). The default for "we have a real reason" is GKE Standard or EKS managed node groups or AKS standard pools. The default for "we have a regulatory requirement" is self-managed on bare metal. Pick the lowest-operational-burden option that meets the constraint.

Tuesday's lecture opens up GKE Autopilot specifically — the model, the constraints, the node-pool abstraction it hides, and the Workload Identity mechanism that is the cleanest pod-to-cloud IAM story on any cloud.

---

*Next: [Lecture 2 — GKE Autopilot, Node Pools, and Workload Identity](./02-gke-autopilot-node-pools-and-workload-identity.md).*
