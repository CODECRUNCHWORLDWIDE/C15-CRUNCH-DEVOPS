# Lecture 2 — GKE Autopilot, Node Pools, and Workload Identity

> *A node pool is a template for a fleet of identical VMs. Autopilot is the mode where Google decides the template for you. Workload Identity is what lets a pod call a Google API without a key on disk. Three concepts, one lecture, and the operational shape of GKE for the rest of your career.*

Yesterday's lecture argued the case for managed Kubernetes and laid out the three big clouds. Today we open the inside of one of them — GKE — and look at the three concepts that determine what it actually feels like to operate a cluster on it: the Autopilot-vs-Standard split, the node-pool abstraction (and why Autopilot hides it), and Workload Identity. These three are also the three places where the experience of operating GKE diverges most from operating a `kind` cluster, so understanding them is what bridges Week 7 to the rest of this course.

We will use GKE as the example throughout, but every concept has a direct analog on EKS and AKS, called out in sidebars. The mental shape is portable.

---

## 1. Autopilot vs Standard — the actual difference

Both modes run the same Kubernetes. Both expose the same API server, the same `kubectl`, the same YAML. What differs is where the boundary of "Google's responsibility" sits.

| | GKE Standard | GKE Autopilot |
|---|---|---|
| Who runs the control plane | Google | Google |
| Who runs etcd | Google | Google |
| Who runs the nodes | You (you pick the machine type, the size, the count) | Google (Google picks the machine type and resizes the node pool automatically) |
| Who scales the cluster | You (with the cluster autoscaler enabled or via manual `gcloud` calls) | Google (transparent; you do not see node-pool resizes) |
| Who pays for what | Per-node VM hours plus a small control-plane fee | Per-pod-vCPU-second plus per-pod-memory-second |
| What manifests look like | Everything works | Most things work; some restrictions (see Section 3) |
| Default security posture | Standard Kubernetes defaults plus GKE hardening | Tighter: PodSecurity Standards "restricted" by default, no privileged pods, no `hostPath` |
| Where the bin-packing decision happens | In your head, when you size the node pool | In Google's scheduler, on every pod admission |

The single-paragraph summary: Standard is GKE with a managed control plane and self-operated nodes; Autopilot is GKE with a managed control plane and *also* a managed data plane. Standard is what 2020-era GKE users grew up on; Autopilot is what 2026-era greenfield projects pick.

### Why Autopilot exists at all

The argument for Autopilot is the same as the argument for managed Kubernetes itself, applied one layer down. Operating nodes is a job. Picking the right machine type for a workload is a job. Resizing the node pool when traffic spikes is a job. Draining nodes before an OS upgrade is a job. Every one of these jobs can be done badly, and most teams have at least one outage in their history attributable to nodes-related operational mistakes.

Autopilot's pitch is: hand all of those jobs to Google. You define what the pod wants (CPU requests, memory requests); Google picks a node big enough, schedules the pod, and bills you for the pod, not the node. If your traffic spikes and you suddenly need 50 pods, Google provisions whatever node count is required. If your traffic drops and you only need 3 pods, Google drains and removes nodes. You never write a node-pool config and you never see a node-pool resize event.

### Why Autopilot is not always right

The cases where Standard wins:

1. **You need a specific node type.** GPU nodes with specific MIG configurations, ARM nodes for testing, nodes with custom kernel parameters. Autopilot supports Compute Classes (a curated set of node profiles) but does not let you bring your own.
2. **You need DaemonSets that need privileged access.** Autopilot disallows privileged pods by default. A node-level agent (a custom logging shipper, a custom network monitor) that needs `hostPath` access or `privileged: true` will not run on Autopilot without an explicit Google-side allowlist.
3. **Your bin-packing is unusual.** If you have 200-replica DaemonSets, or pods that pin to specific machine types via complex `nodeSelector` rules, Autopilot's scheduler may make worse decisions than you would. Rare; relevant for a small number of large customers.
4. **You want absolute predictability of node count and shape.** Some compliance frameworks require "we have N machines doing X" as the level of detail in the audit. Autopilot abstracts this away.

In practice, **for a new app in 2026, default to Autopilot**. Move to Standard only when one of the four reasons above bites.

---

## 2. The actual cluster-creation commands

The `gcloud` commands matter; you should be able to read them. Memorizing every flag is unnecessary; knowing what the flags do is essential.

### 2.1 GKE Autopilot — the minimal command

```bash
gcloud container clusters create-auto my-cluster \
  --region=us-central1 \
  --release-channel=regular
```

Two flags worth understanding:

- `--region=us-central1` — regional cluster. Autopilot is always regional (three-zone HA control plane). This is one of the things you get for free with Autopilot.
- `--release-channel=regular` — which channel Google ships minor versions on. `rapid` (latest minor, lowest stability), `regular` (recommended default), `stable` (slowest, most conservative), `extended` (paid, longest support). For a learning cluster, `regular` is right.

The cluster takes about 90 seconds to provision. After it returns you have a `kubectl` context (added to your `~/.kube/config` by `gcloud`) and you can `kubectl get nodes` — but the result will be empty until you submit a pod, because Autopilot does not pre-provision nodes.

### 2.2 GKE Autopilot — a more realistic command

```bash
gcloud container clusters create-auto my-cluster \
  --region=us-central1 \
  --release-channel=regular \
  --network=default \
  --subnetwork=default \
  --enable-master-authorized-networks \
  --master-authorized-networks=$(curl -s ifconfig.me)/32 \
  --enable-private-nodes \
  --enable-workload-identity \
  --labels=env=dev,team=c15-week08
```

Flags worth understanding:

- `--enable-master-authorized-networks` and `--master-authorized-networks=...` — restrict who can reach the API server. The default Autopilot cluster exposes the API server to the public Internet (with TLS and IAM auth, but still public); pinning the authorized network to your IP is the correct production posture.
- `--enable-private-nodes` — nodes do not have public IPs. They reach the Internet via Cloud NAT, which you would have configured. For a learning cluster this is optional; for a production cluster it is the baseline.
- `--enable-workload-identity` — turn on Workload Identity (we cover this in Section 4). On Autopilot this is on by default; the flag is harmless.
- `--labels=env=dev,team=c15-week08` — labels on the *GCP* resource, not on Kubernetes resources. Useful for billing and inventory.

### 2.3 GKE Standard — the equivalent

```bash
gcloud container clusters create my-cluster \
  --region=us-central1 \
  --release-channel=regular \
  --num-nodes=2 \
  --machine-type=e2-medium \
  --enable-autoscaling --min-nodes=1 --max-nodes=5 \
  --enable-autorepair \
  --enable-autoupgrade \
  --workload-pool=my-project.svc.id.goog
```

The differences from Autopilot:

- `--num-nodes=2` and `--machine-type=e2-medium` — you size the node pool. Two `e2-medium` VMs (2 vCPU, 4 GB RAM each) is a sensible learning-cluster size.
- `--enable-autoscaling --min-nodes=1 --max-nodes=5` — turn on the cluster autoscaler for this node pool, with these bounds. Without this flag, the cluster is fixed at `--num-nodes`.
- `--enable-autorepair --enable-autoupgrade` — let Google replace a sick node and let Google upgrade nodes during maintenance windows. Both default on for new Standard clusters; the explicit flags make it visible.
- `--workload-pool=my-project.svc.id.goog` — opt into Workload Identity. On Standard this is opt-in (Autopilot has it on by default).

### 2.4 The EKS equivalent (sidebar)

```bash
eksctl create cluster \
  --name my-cluster \
  --region us-east-2 \
  --node-type t3.small \
  --nodes 2 \
  --nodes-min 1 \
  --nodes-max 5 \
  --with-oidc \
  --managed
```

Flags worth noting:

- `--managed` — managed node groups (the "AWS operates the EC2 instances" mode), not self-managed node groups.
- `--with-oidc` — turn on the OIDC provider that IRSA depends on. Opt-in on EKS; required for the IAM-to-KSA binding pattern.
- `--fargate` (alternative) — replace the managed node group with EKS Fargate, which is the closest analog to GKE Autopilot. One pod per Fargate task; you pay per pod-vCPU-second.

### 2.5 The AKS equivalent (sidebar)

```bash
az aks create \
  --resource-group my-rg \
  --name my-cluster \
  --location eastus \
  --node-count 2 \
  --node-vm-size Standard_B2s \
  --enable-cluster-autoscaler \
  --min-count 1 --max-count 5 \
  --enable-managed-identity \
  --enable-workload-identity \
  --enable-oidc-issuer \
  --network-plugin azure
```

Flags worth noting:

- `--enable-managed-identity` — use an Azure-managed identity for the cluster control plane (no service principal secret).
- `--enable-workload-identity` and `--enable-oidc-issuer` — turn on AAD Workload Identity. Opt-in on AKS as of May 2026; default-on is on Microsoft's roadmap.
- `--network-plugin azure` — Azure CNI (pods get VNet IPs). `kubenet` is the other option (route-based, simpler, less flexible).

---

## 3. Autopilot's constraints — what does not work

Autopilot's "Google manages the nodes too" model comes with rules. These rules exist so Google's scheduler can do its job (bin-packing pods onto auto-provisioned nodes) without surprises. The rules also exist so Autopilot's security baseline can be tighter than Standard's.

The full list is in Google's docs at <https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview#unsupported>; the ones you will hit in this course:

### 3.1 No `hostPath` volumes

A `hostPath` volume mounts a path from the node into the pod. On Autopilot, the node is ephemeral (Google may replace it under you), so a `hostPath` is meaningless. Autopilot rejects pods with `hostPath` volumes.

The workaround: use a `PersistentVolume` (backed by a CSI driver) for anything that needs cross-pod persistence, or an `emptyDir` for anything ephemeral that should die with the pod.

### 3.2 No privileged pods by default

The PodSecurity Standard "restricted" profile applies to all namespaces by default. This means: no `privileged: true`, no host networking, no `capabilities.add` beyond a small whitelist, no `runAsUser: 0` for most images.

The workaround: for a small number of system-level workloads that genuinely need privileged access (a node-level GPU driver, a node-level network plugin), Google has an "AllowlistedV2" annotation that lets specific pods bypass restrictions. For application workloads, you should never need this.

### 3.3 No custom `nodeSelector` / `nodeAffinity` outside the GKE Compute Classes

Autopilot picks the node for you. You can request a *class* of node — `gke-spot` for spot-priced nodes, `Performance` / `Balanced` / `Scale-Out` for different machine families — but you cannot say "put me on `n2-standard-32`". Compute Classes are the only legal `nodeSelector` axis on Autopilot.

This is a feature, not a bug: it means your manifests are not coupled to specific machine SKUs.

### 3.4 No DaemonSets that need privileged access

Plain DaemonSets work fine. DaemonSets that need privileged access — most of the "I'll install my own CNI" or "I'll install my own logging shipper" use cases — do not work on Autopilot, because the privileged-pod restriction applies to them too. Google's bundled equivalents (Cloud Logging agent, Cloud Monitoring agent) are present.

### 3.5 Minimum pod resources

Autopilot enforces minimum CPU and memory requests on every pod (currently 250m CPU and 512Mi memory, varying by Compute Class). Pods below the minimum are bumped up automatically and you are billed for the minimum. This prevents "I will run 100 nginx pods each requesting 1m CPU" cost-pathology games.

### 3.6 What this means for the mini-project

The mini-project this week is designed so it runs on both Autopilot and `kind`. The manifests therefore:

- Use no `hostPath` volumes.
- Have no `privileged: true` containers.
- Use only the default `nodeSelector` (none).
- Request 100m CPU and 128Mi memory per container — under the Autopilot minimum, so Autopilot will bump them to its minimum, but the manifest does not depend on this.

Same YAML, both clusters. The portability claim is concrete.

---

## 4. Workload Identity — the GCP IAM-to-KSA binding

This is the single most useful piece of plumbing GKE provides, and the single piece of plumbing students most often skip on the way to "I just want my pod to call BigQuery." Skipping it leads to JSON keys checked into Secrets, which leads to outages, which leads to remediation projects. Learn it once, never write a JSON key again.

### 4.1 The problem

A pod in your cluster needs to call a Google API — list objects in a Cloud Storage bucket, write to BigQuery, publish to Pub/Sub. The Google API requires an authenticated identity. The pod is a Linux process running in a container running in a pod; it has no GCP identity by default.

The bad answers:

1. **Embed a service-account JSON key in the container image.** The image is immutable; the key is now permanently on disk; if the image leaks, the key leaks; rotation requires rebuilding the image.
2. **Mount a JSON key as a Secret.** The key is on disk on the node; cluster admins can read it; rotation requires re-creating the Secret and restarting the pod.
3. **Use Application Default Credentials backed by the node's service account.** Every pod on that node has the same identity — `least-privilege` at the pod level is impossible.

All three patterns are real, all three were how teams did it before ~2019, and all three are how you find a "hold my JSON key" Secret in someone else's cluster today.

### 4.2 The good answer: Workload Identity

Workload Identity binds a Kubernetes ServiceAccount (KSA) to a GCP IAM service account (GSA). The mechanism, in three sentences:

1. The pod runs with a specific KSA.
2. The KSA is annotated with the email of a specific GSA.
3. When the pod calls a Google API, the Google client library hits the metadata server, which checks the binding, and returns a short-lived token for the GSA. No JSON key. No long-lived secret. Rotation is automatic (tokens last 1 hour).

The IAM glue makes this work safely: the GSA has an IAM policy with the role `roles/iam.workloadIdentityUser` granted to the principal `serviceAccount:<project>.svc.id.goog[<namespace>/<ksa-name>]`. Only the bound KSA in the bound namespace can mint tokens for that GSA. Any other KSA — even a malicious one — cannot.

### 4.3 The actual recipe

Assume:

- GCP project: `my-project`
- GKE cluster: `my-cluster` in `us-central1`, with Workload Identity enabled
- Kubernetes namespace: `app`
- Kubernetes ServiceAccount: `app-sa`
- GCP service account: `app-gsa@my-project.iam.gserviceaccount.com`
- The pod needs to read from a bucket named `gs://my-bucket`.

```bash
# 1. Create the GCP service account
gcloud iam service-accounts create app-gsa \
  --project=my-project

# 2. Grant the GSA permission on the bucket
gsutil iam ch \
  serviceAccount:app-gsa@my-project.iam.gserviceaccount.com:objectViewer \
  gs://my-bucket

# 3. Bind the KSA to the GSA via Workload Identity
gcloud iam service-accounts add-iam-policy-binding \
  app-gsa@my-project.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member=serviceAccount:my-project.svc.id.goog[app/app-sa]

# 4. Create the KSA in the cluster and annotate it
kubectl create namespace app
kubectl create serviceaccount app-sa --namespace=app
kubectl annotate serviceaccount app-sa \
  --namespace=app \
  iam.gke.io/gcp-service-account=app-gsa@my-project.iam.gserviceaccount.com
```

That is the entire setup. From this point on, any pod in namespace `app` that has `spec.serviceAccountName: app-sa` will be able to call Google APIs as the `app-gsa` GSA — and no other GSA.

### 4.4 The Deployment manifest that consumes it

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bucket-reader
  namespace: app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bucket-reader
  template:
    metadata:
      labels:
        app: bucket-reader
    spec:
      serviceAccountName: app-sa   # the KSA bound to app-gsa
      containers:
        - name: app
          image: gcr.io/my-project/bucket-reader:1.0
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              memory: "256Mi"
```

The application code does not change. The Google client libraries (Python, Go, Java, Node) detect Workload Identity automatically. No JSON key. No environment variable pointing at a key path. The pod simply runs and `storage.Client()` works.

### 4.5 How it actually works under the hood

This part is optional, but if you want to understand what is happening:

1. The pod tries to call `storage.googleapis.com`.
2. The Google client library hits the GCE metadata server at `169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token` to get a token.
3. On a Workload-Identity-enabled GKE node, the GKE metadata server (a per-node proxy) intercepts that request, inspects which pod made the request, looks up the KSA the pod is using, looks up the `iam.gke.io/gcp-service-account` annotation on the KSA, and exchanges the pod's projected service account token for a GSA token via STS (Security Token Service).
4. The token is returned to the client library. The library uses it to call `storage.googleapis.com` as the GSA.
5. The token expires in about an hour. The library refreshes it automatically.

The trust relationship is enforced by GCP's IAM service: an STS token exchange request from a KSA that is not bound to the GSA fails with a 403. There is no shared secret; everything is short-lived and audited.

### 4.6 Sidebar: IRSA on EKS

The AWS equivalent works similarly with different plumbing:

1. The cluster has an OIDC issuer (the URL is on the cluster's API server).
2. You create an IAM role with a trust policy that names the cluster's OIDC issuer and a specific KSA path (e.g., `system:serviceaccount:app:app-sa`).
3. You annotate the KSA with `eks.amazonaws.com/role-arn: arn:aws:iam::<account>:role/<role-name>`.
4. The pod's KSA token is mounted as a projected service account token; the AWS SDK detects it (`AWS_WEB_IDENTITY_TOKEN_FILE` is set on the pod) and exchanges it for short-lived AWS credentials via `sts:AssumeRoleWithWebIdentity`.

The shape is identical. The mechanism is different. Same outcome.

### 4.7 Sidebar: AAD Workload Identity on AKS

Microsoft's version is similar:

1. The cluster has an OIDC issuer (turned on by `--enable-oidc-issuer`).
2. You create an Azure AD application and a federated identity credential that names the cluster's OIDC issuer and a specific KSA.
3. You annotate the KSA with `azure.workload.identity/client-id: <aad-app-client-id>`.
4. The pod's KSA token is exchanged for an AAD token via the AAD STS.

Same pattern, third mechanism.

The three providers landed on the same architectural answer (OIDC trust + KSA-token exchange) for the same problem. The shape is the cluster-security baseline for 2026; expect it to be the way you authenticate every pod to every cloud API for the rest of this decade.

---

## 5. Node pools (on Standard) and why Autopilot hides them

A node pool is a group of nodes that share a machine type, a disk size, a Kubernetes version, a set of labels, and a set of taints. On GKE Standard, EKS managed node groups, and AKS node pools, you create at least one and you may create several.

Why several? Three reasons:

1. **Heterogeneity.** Some workloads need GPU nodes; some need ARM nodes; some need spot/preemptible nodes for cost. One node pool per workload type, and `nodeSelector` to pin pods to the right pool.
2. **Isolation.** Sensitive workloads on a tainted node pool that only they tolerate; everyone else on the default pool.
3. **Upgrade staging.** Upgrade the canary pool, observe, then upgrade the rest.

The shape of a GKE Standard node pool, in `gcloud`:

```bash
gcloud container node-pools create gpu-pool \
  --cluster=my-cluster \
  --region=us-central1 \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --num-nodes=0 \
  --enable-autoscaling --min-nodes=0 --max-nodes=10 \
  --node-taints=workload=gpu:NoSchedule \
  --node-labels=workload=gpu
```

A pod that wants this pool then has:

```yaml
spec:
  nodeSelector:
    workload: gpu
  tolerations:
    - key: workload
      operator: Equal
      value: gpu
      effect: NoSchedule
```

Without the toleration, the pod cannot schedule on the GPU pool (taint repels it). Without the `nodeSelector`, the pod could schedule on either pool. Together, they pin GPU pods to GPU nodes and keep non-GPU pods off them.

Autopilot hides this entire mental model. You ask for a GPU pod (via a Compute Class or via the `cloud.google.com/gke-accelerator` annotation), and Google's scheduler finds or provisions an appropriate node. There is no node pool you can `gcloud` at. There is no taint you set. The same outcome (GPU pod on GPU node, non-GPU pod off it) without the per-pool plumbing.

For production teams running heterogeneous fleets at scale, the lack of explicit node pools is the most common reason to pick Standard over Autopilot.

---

## 6. The cluster autoscaler — and HPA, and VPA

Three different autoscalers, three different jobs, often run together, often confused:

| Controller | What it watches | What it does |
|---|---|---|
| **Horizontal Pod Autoscaler (HPA)** | A metric (CPU, memory, custom) per pod in a Deployment | Adjusts `spec.replicas` of the Deployment up or down |
| **Vertical Pod Autoscaler (VPA)** | Observed CPU and memory of pods | Recommends or applies new `resources.requests` (with restart) |
| **Cluster Autoscaler (CA)** | Pending pods that cannot schedule due to insufficient node capacity | Adds nodes (and removes underutilized nodes) |

The interactions:

- HPA wants more pods, the new pods cannot schedule (no node has room), the cluster autoscaler observes the pending pods and adds a node, the pods schedule. End-to-end latency: 30s-3min depending on the cloud (node provisioning is the slow step).
- HPA scales down, pods are removed, the node is underutilized, the cluster autoscaler removes the node. End-to-end latency: 10-15 minutes (the CA waits to be sure utilization is stable before removing).
- VPA changes a pod's resource requests, the pod restarts with new requests, the cluster autoscaler may add or remove nodes to fit the new shape.

On GKE Autopilot, the cluster autoscaler is invisible. You do not configure it; Google has its own equivalent that adds and removes nodes transparently. On GKE Standard, EKS, and AKS, you turn the cluster autoscaler on with a flag (we did, in Section 2.3 and 2.5 above).

The HPA is the same controller everywhere — it is built into Kubernetes. We will write one in the mini-project.

---

## 7. The PodDisruptionBudget (PDB) — operationally important

A PDB is a small resource that caps how many pods of a Deployment can be voluntarily disrupted (e.g., during a node drain) at one time. Without a PDB, the cluster autoscaler — or a manual `kubectl drain` for a node upgrade — can remove all your pods at once.

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: app-pdb
  namespace: app
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: my-app
```

This says: at least 1 pod with label `app: my-app` must remain available at all times during voluntary disruptions. The cluster autoscaler reads this and waits to drain a node until the PDB would still be satisfied after the drain.

On a managed cluster with the cluster autoscaler aggressively adding and removing nodes, the PDB is the difference between a smooth scale-down and a brief outage every time a node is rotated. You should write one for every production Deployment with more than one replica.

---

## 8. Common pitfalls

Three real failures from real clusters that I have seen this year:

1. **A pod with no resource requests on Autopilot.** Autopilot enforces defaults, but the defaults may not match what your app needs. A pod with `requests: {}` gets the Autopilot minimum (250m CPU, 512Mi memory) and you are billed for that, regardless of what the pod actually uses. Always write explicit resource requests on Autopilot.
2. **Workload Identity set up on the GSA side but the KSA missing the annotation.** Symptom: the pod gets a 403 from Google APIs and the error message is opaque ("permission denied"). The fix is to check the KSA's annotations (`kubectl get sa app-sa -o yaml | grep iam.gke.io`) and the GSA's IAM bindings (`gcloud iam service-accounts get-iam-policy ...`) and verify both sides of the binding.
3. **No PDB plus the cluster autoscaler doing a node-pool consolidation.** The autoscaler drains a node where two of your three replicas live; for ~90 seconds you are at one replica; if a request lands during the gap, latency or error rate spikes. A PDB with `minAvailable: 2` would have prevented this.

The first two are GKE-specific; the third is universal across managed clouds.

---

## 9. The mental model you should leave with

GKE Autopilot is "Kubernetes where Google operates the nodes too, and bills you per pod, with tighter security defaults." That sentence covers 90% of what you need to know.

GKE Standard adds the node-pool model back, which you need if your workloads are heterogeneous or you want explicit control over machine types and scaling behavior. Most greenfield teams in 2026 do not need it.

Workload Identity is the GCP pattern for pod-to-cloud IAM without keys. It is the cluster-security baseline. Learn it once; never write a JSON key into a Secret again. EKS's IRSA and AKS's AAD Workload Identity are the same idea with different plumbing.

Node pools and the cluster autoscaler are operational primitives you will encounter the moment you leave Autopilot. The HPA you will use everywhere. The PDB you will write for every multi-replica production Deployment.

Tomorrow's lecture is about what you actually install on top of a managed cluster (or any Kubernetes cluster, including `kind`) to make it useful for serving real traffic: NGINX Ingress, cert-manager, external-dns, ArgoCD. The "what comes after the cluster is created" stack.

---

*Next: [Lecture 3 — The Add-On Stack: Ingress, Certs, DNS, ArgoCD](./03-the-add-on-stack-ingress-certs-dns-argocd.md).*

*Previous: [Lecture 1 — Managed vs Self-Managed, and the Three Clouds](./01-managed-vs-self-managed-and-the-three-clouds.md).*
