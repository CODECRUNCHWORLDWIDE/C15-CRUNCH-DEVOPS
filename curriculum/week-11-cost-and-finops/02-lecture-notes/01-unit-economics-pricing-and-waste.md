# Lecture 1 — Unit Economics, Cloud Pricing, and the Three Waste Sources

> *Engineers will not respect a cost number they cannot reproduce. The job of the cost engineer is not to deliver the number; it is to deliver the number with the math beside it.*

Last week we made the cluster trustworthy. Images signed, secrets vaulted, SBOMs scanned. The artifacts that reach production now arrive with a paper trail. This week the question changes. It is no longer whether to trust what runs; it is what the running costs and whether that cost is the right cost.

The first reflex when someone says "cloud cost" is to look at the bill. It is a wrong reflex, not because the bill is wrong, but because the bill is too late and too coarse. By the time the bill arrives, the design decisions that produced the bill are weeks or months old; the engineers who made them have moved on to the next thing; the line items aggregate across so many workloads that even a forensic accountant could not unwind them. The bill is a result. We need the process that produces it.

This lecture is the conceptual setup for the week. We will cover three things, in order. **First**, the unit-economics mindset — how mature cost-aware organizations talk about cost not as a number but as a ratio. **Second**, the structure of cloud pricing — the three big buckets (compute, storage, network) and the three purchase modalities (on-demand, reserved / committed, spot / preemptible). **Third**, the three biggest waste sources in a typical Kubernetes-driven cloud bill and the queries that surface each one. By the end of the lecture you should be able to look at any cloud line item and (a) place it in the bucket, (b) name the modality, (c) guess which waste source it is most likely an example of.

We will install no software today. Tomorrow we install OpenCost. Today is the mental model that justifies why we are installing it.

---

## 1. The unit-economics mindset

A standard executive question, in any organization with a cloud bill: *did we spend more last month than the month before*. The standard answer arrives as a number — *we spent $402,000 last month, $381,000 the month before, an increase of 5.5 percent*. The number is true. The number is also, in isolation, almost useless. The natural follow-up question is *should we have spent more*, and the absolute-number framing does not answer it.

A better framing: *what did each dollar buy us*. If we spent $402,000 last month and processed 18 billion requests, the unit cost is $0.0000223 per request, or roughly $22.30 per million. If we spent $381,000 the previous month and processed 14 billion requests, the unit cost was $0.0000272, or $27.20 per million. Absolute spend went up; unit cost went down by 18 percent. The organization is more efficient, not less, despite a higher bill. That is the conversation an engineering leader wants to have.

The discipline is called **unit economics**. The pattern: divide cost by a business metric that scales with what the company does. The choice of metric is the design decision. For a typical SaaS the three primary candidates are:

- **Cost per request.** Useful for a high-volume API-shaped business. Easy to measure (most observability stacks already count requests). Less informative for a business whose user behavior varies (one user might issue 10 requests per session, another might issue 10,000).
- **Cost per active user.** Daily active user (DAU) and monthly active user (MAU). The closest to a business-meaningful metric. Harder to compute exactly — *active* is a definition question — but the ratio is what an investor or board member will ask about.
- **Cost per GB processed (or per equivalent throughput unit).** Useful for data-pipeline businesses, video streaming, file storage, analytics. The denominator is closer to the cost driver than for an API business.

The right choice is the metric whose denominator most closely tracks the cost driver of the workload. A video streaming platform should track cost per stream-hour or per GB delivered, not cost per request. A multi-tenant SaaS where each tenant runs their own workload should track cost per tenant. A messaging app should track cost per message delivered. The point is not that one metric is universally right; the point is that the team picks one and tracks it over time.

The mature pattern is to display two numbers side by side on the engineering-leadership dashboard: **absolute spend** (the bill number, the finance number) and **unit cost** (the engineering number). Spend can rise; unit cost should fall, or at least stay flat. The two together tell a story neither tells alone.

A real-world counterexample. A team optimized aggressively, cut the bill by 30 percent over six months, and was congratulated. Revenue had also fallen by 50 percent over the same period because the product was deprecated and traffic was draining away. The unit cost had doubled. The cost engineering had been a success against an irrelevant metric. The team did not lack data; it lacked unit-economics framing. This is not a hypothetical pattern; some version of it happens at every organization that does not track ratios.

Throughout this week we will build the cluster-side machinery to compute the numerator (cost). The denominator (the business metric) is a Prometheus counter the application emits — `requests_total`, `users_active`, `bytes_processed_total`, whatever the business actually cares about. Dividing one Prometheus series by another in Grafana is one line of PromQL. Doing it consistently, by team, by environment, over time, is the discipline.

---

## 2. The structure of cloud pricing

A cloud bill, in any provider, decomposes into three buckets. Understanding the three is the single largest lift in cost intuition.

### 2.1 Compute

Compute is the cost of running CPU and memory. It is almost always the largest single bucket, often 50 to 70 percent of the bill. The unit is **instance-hour** (or instance-second) at a per-instance rate that depends on the instance family, size, region, and operating system license (Windows instances are more expensive than Linux due to a Microsoft licensing pass-through).

The pricing is published. For AWS, every region's EC2 on-demand rate is on a single page at <https://aws.amazon.com/ec2/pricing/on-demand/>. For GCP, the equivalent is at <https://cloud.google.com/compute/all-pricing>. As of May 2026 the on-demand price for an AWS `m6i.large` (2 vCPU, 8 GiB, Linux, us-east-1) is approximately $0.096 per hour. The GCP equivalent — `n2-standard-2` — is approximately $0.0971 per hour in `us-central1`. These numbers move; do not memorize the value, memorize the pattern: roughly $0.05 to $0.10 per hour per vCPU for general-purpose instances in major US regions, with multipliers for memory-optimized, compute-optimized, GPU, and Windows licensing.

Kubernetes adds a layer. The nodes are EC2 instances (or GCE instances, or Azure VMs). The pods scheduled onto a node share the node's cost. OpenCost's central job is to allocate that node cost across the pods — typically by CPU-and-memory request, weighted by what each pod actually used. We will see the math in tomorrow's lecture.

Serverless (Lambda, Cloud Run, Cloud Functions) prices differently — per request and per GB-second of execution rather than per instance-hour. For a steady-state workload, instances are almost always cheaper than serverless; for a bursty or rarely-invoked workload, serverless is almost always cheaper. The crossover is typically at 20 to 30 percent average utilization; below that, serverless wins; above, instances win.

### 2.2 Storage

Storage is the cost of holding data at rest. It decomposes further:

- **Block storage** (EBS, Persistent Disk, Azure Disk). The disks attached to instances or claimed by Kubernetes PersistentVolumes. Priced per **GB-month**, typically $0.08 to $0.125 per GB-month for general-purpose SSD. The pricing varies by tier (HDD cheaper, NVMe more expensive) and by IOPS provisioned (provisioned-IOPS is dramatically more expensive than baseline).
- **Object storage** (S3, GCS, Azure Blob). The buckets. Priced per GB-month, typically $0.020 to $0.023 per GB-month for standard-tier in major US regions, falling to $0.001 to $0.004 per GB-month for archive tiers (Glacier, Coldline, Archive). The retrieval cost for archive tiers — what you pay to *read* the data back — is the line item that surprises every new user. Reading 10 TB out of S3 Glacier is cheap; reading it back urgently is expensive.
- **Database storage** (RDS, Cloud SQL, Aurora, Spanner). Priced per GB-month plus a managed-service premium. Aurora, for example, is roughly twice the per-GB cost of EBS gp3 for the same storage.

The pattern: storage is far cheaper per unit than compute. A single `m6i.large` running for a month costs $69. A terabyte of S3 standard storage costs $23. Storage waste is real but is usually dwarfed by compute waste in dollar terms. The exception is the team that left a stopped instance with a 16 TB EBS volume attached; we will see that in section 4.

### 2.3 Network

Network is the cost of moving data. It is the most under-modeled bucket at design time and the bucket with the most surprises in the bill.

The structure, for any major cloud, is roughly:

- **Inbound data transfer** (data into the cloud from the public internet). **Free**, in every major cloud, in every modern pricing model.
- **Outbound data transfer to the public internet.** Priced per GB. AWS: roughly $0.09 per GB for the first 10 TB per month, dropping to lower tiers above. GCP: similar shape, roughly $0.085 to $0.12 per GB depending on destination. The first 1 GB per month is typically free.
- **Cross-zone data transfer within a region.** AWS: $0.01 per GB in each direction (so $0.02 per GB round-trip). GCP charges per-GB between zones within a region as well. The number is small per GB and large per terabyte.
- **Cross-region data transfer.** Priced per GB. Higher than cross-zone, lower than to-internet. The pattern varies by provider; consult the page each provider publishes.
- **NAT Gateway / Cloud NAT charges.** Both AWS and GCP charge per-hour for the gateway itself ($0.045 per hour for AWS NAT Gateway) and per-GB for data processed through it ($0.045 per GB for AWS). The combined cost is often the single most surprising line item on a small cloud bill — engineers do not realize that the convenience of NAT carries a per-GB processing cost on top of the per-GB egress cost.
- **Load-balancer charges.** Per-hour for the load balancer (~$0.025 per hour for an AWS Application Load Balancer) plus per-LCU (Load Balancer Capacity Unit) for the throughput. Small in isolation; meaningful in aggregate when a team has a hundred ALBs.

Network is the cost-engineering wedge. A team that understands network costs designs differently from a team that does not. The differences: keeping traffic in-zone when possible (services scheduled co-located, gossip protocols zone-aware), avoiding NAT for high-volume egress (using VPC endpoints / private service connect for S3, GCS, KMS, and other AWS/GCP services), and being honest about how much data leaves the cloud (a logging pipeline that ships all logs to a third-party SaaS is an egress pipe; budget for it accordingly).

The full network-pricing page is the single most useful read of this week: AWS at <https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer>, GCP at <https://cloud.google.com/vpc/network-pricing>.

---

## 3. Purchase modalities

For a given service — typically compute, sometimes other services — clouds sell the same capacity in different modalities at different price points. The three primary ones:

### 3.1 On-demand

You pay the published per-hour rate. No commitment, no discount, no interruption. This is the default and the most expensive modality. New workloads typically launch on-demand; engineers do not commit until they understand the workload's steady-state shape.

### 3.2 Reserved instances / committed-use discounts / savings plans

You commit to a certain spend or to a certain capacity for one or three years, in exchange for a discount of roughly 30 to 55 percent off the on-demand price. The shapes:

- **AWS Reserved Instances** (legacy, still supported): commit to a specific instance type in a specific region for one or three years. Three sub-shapes: standard (deepest discount, least flexible), convertible (smaller discount, can be exchanged), and the family-flexible variants.
- **AWS Savings Plans** (current): commit to a dollar-per-hour spend on compute for one or three years. The **Compute Savings Plan** covers EC2, Fargate, and Lambda across regions and instance families. The **EC2 Instance Savings Plan** is restricted to one region and one instance family but offers a deeper discount.
- **GCP Committed Use Discounts**: commit to a level of vCPU and memory in a region for one or three years. GCP also offers a **flexible** CUD (spend-based) that mirrors AWS's Savings Plans.
- **Azure Reserved VM Instances** and **Azure Savings Plans for Compute**: equivalents on Azure.

The judgement: commit to your baseline, run on-demand above it. If you reliably consume 100 vCPU-hours of compute every hour of every day, commit to that 100 vCPU-hours; you will save 35 to 50 percent on that floor. The spike traffic above the baseline runs on-demand. The risk of over-committing is real — a commitment you do not consume is a sunk cost.

### 3.3 Spot / preemptible

The cloud sells unsold capacity at a deep discount (typically 60 to 90 percent off on-demand). The catch is that the cloud can reclaim the capacity at minutes of notice when an on-demand customer wants it. The instance is interrupted; the workload must be designed to handle the interruption.

The suitability matrix:

- **Stateless, idempotent workloads** — batch jobs, training jobs, web tier behind a load balancer, build runners. Excellent spot candidates. Set the maximum number of replicas, accept that some will die unexpectedly, the load balancer routes around them.
- **Stateful primary databases, single-writer leaders, stuck-in-the-middle services** — not spot. The interruption cost is too high.
- **Stateful services with a leader-election protocol and quick recovery** — sometimes spot, depending on recovery time. A Kafka broker with 3-second recovery is a spot candidate; a Kafka broker with 5-minute recovery is not.

On Kubernetes, the typical pattern is mixed-mode node pools: an on-demand pool and a spot pool. Workloads tolerate spot via node-selector or affinity; critical workloads are pinned to on-demand. Karpenter (AWS) and the GKE node-pool autoscaler can each schedule across pools automatically.

The pricing reference: AWS spot pricing at <https://aws.amazon.com/ec2/spot/pricing/>; GCP Spot at <https://cloud.google.com/spot-vms#pricing>.

---

## 4. The three biggest waste sources

A canvassing of real cloud bills, by the FinOps Foundation and by independent analysts (Flexera's *State of the Cloud* annual report, the FinOps Foundation's *State of FinOps* annual report), consistently identifies three categories of waste that together account for most of the recoverable spend. They are:

### 4.1 Over-provisioned compute

The single largest source of waste in most Kubernetes-driven bills. A pod has its CPU and memory requests set in the Deployment spec. The cluster scheduler reserves that capacity on a node; the cluster autoscaler keeps the node around to satisfy the reservation. The pod, in production, uses much less than it requested. The difference is paid-for and unused.

A concrete example. A Deployment specifies `requests: {cpu: 1000m, memory: 2Gi}` for the workload. In production over a 14-day window, the pod's P95 CPU usage is 200m and P95 memory is 600Mi. The pod is **reserving** 800m of CPU and 1.4 GiB of memory it never uses. If the cluster has 10 such pods, the cluster is over-provisioned by 8 vCPU and 14 GiB of memory — roughly two `m6i.large` instances, or about $140 per month at on-demand pricing.

The detection: query Prometheus for `kube_pod_container_resource_requests` (from kube-state-metrics) versus `container_cpu_usage_seconds_total` and `container_memory_working_set_bytes` (from cAdvisor). OpenCost does this aggregation in its `efficiency` field on each allocation. A workload with `cpuEfficiency: 0.2` is using 20 percent of what it reserved. The over-provision waste is `(1 - efficiency) * cost`.

The fix is right-sizing: reduce the requests to match observed usage with a comfortable margin (typically observed P95 * 1.3 for the new request). The discipline is unglamorous and the savings are real. A team that right-sizes once and never again will recover 20 to 40 percent of compute cost on the first pass. The right-sizing exercise is Exercise 2.

The Kubernetes-native tool to automate this is the **Vertical Pod Autoscaler (VPA)** at <https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler>. VPA observes usage and either suggests (`updateMode: Off`, recommendation-only) or applies (`updateMode: Auto`) updated requests. In recommendation mode it is safe to run in production; in auto mode it restarts pods on resize, which most stateful workloads cannot tolerate.

### 4.2 Idle resources

The second-largest source of waste. Resources that are running, billing, and serving zero purpose. The catalog:

- **Staging and dev environments left on overnight and on weekends.** A staging cluster that mirrors production at half-scale, running 24/7, costs half of production. If staging is only used during business hours in one time zone (40 hours per week of a 168-hour week), the off-hours running is 76 percent of the cluster's cost — pure waste. The fix is scheduled scale-down: a CronJob that scales every Deployment in the staging namespace to zero at 7pm and back to its previous replica count at 8am. We do this in Challenge 1.
- **Orphaned PersistentVolumes.** A PV with `reclaimPolicy: Retain` (the default for most StorageClasses) is not deleted when its PersistentVolumeClaim is deleted. The PV stays. The underlying EBS / PD volume stays. The bill stays. After a year, a typical cluster has dozens of these. The detection: `kubectl get pv -A` and filter for `STATUS: Released`. The fix is `reclaimPolicy: Delete` on dev-tier StorageClasses, and a quarterly audit on prod-tier StorageClasses where Retain is legitimate.
- **Unused load balancers.** A Service of type `LoadBalancer` provisions a cloud load balancer. Delete the Service and the LB usually gets cleaned up — but only if the cluster's cloud-controller-manager is healthy and the Service has not been orphaned by a namespace deletion that left dangling cloud resources. AWS Application Load Balancers cost ~$18 per month per instance, plus per-LCU charges. A dozen orphaned ALBs is a real number.
- **Stopped instances with attached storage.** AWS does not bill for a stopped EC2 instance's compute, but it does bill for its attached EBS volumes. A team that "saves money" by stopping instead of terminating an instance ends up paying for the storage indefinitely. The fix: terminate, or snapshot then terminate.

Idle resources are the easiest waste to detect (the resource simply has zero workload metrics for an extended period) and often the hardest to remove politically (someone is convinced they will need it again). The discipline is to delete and let the owner re-provision if they need it. The discipline survives only if the owner is fast at re-provisioning, which requires Infrastructure as Code, which is Week 5 of this course.

### 4.3 Egress charges

The third source, and the one teams least expect at design time. The pattern: a service is built, runs locally fine, runs in the cloud fine, ships to production fine. Three months later the cloud bill shows a $30,000 line item for data transfer that did not exist at launch. Investigation reveals that the service writes its application logs to a SaaS log-aggregator. Each log line is small; the volume is high; the per-GB egress cost compounds.

The pattern repeats in many guises:

- **Logs shipped to a third-party SaaS** (Datadog, Splunk, etc.) — egress per byte.
- **Metrics scraped by a hosted Prometheus** (Grafana Cloud, Chronosphere) — egress per byte.
- **Backups copied to another cloud or another region.**
- **API calls between services in different zones** (the chatty microservice problem at zone-crossing scale).
- **Public-facing CDN with a high cache-miss ratio** — every miss is an egress hop from origin.

The detection: AWS Cost Explorer or GCP Billing reports broken down by *service*. The data-transfer line item is its own line; if it is the top three by spend, investigate. The OpenCost equivalent is the network-cost portion of an allocation, which OpenCost estimates from pod-level network metrics if available (the `networkCost` field).

The fix is design-driven, not configuration-driven. Move the log aggregator into the same VPC as the workload. Use a VPC endpoint for S3 instead of egressing through NAT. Add an in-region cache in front of the origin. None of these are kubectl commands; they are architecture changes. The point of cost engineering is to make the cost visible early so the architecture is designed for it.

---

## 5. A worked example

Let us walk through a small worked example. A FastAPI service running on AWS in `us-east-1`. The Deployment manifest:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: example-api
  namespace: example
spec:
  replicas: 4
  selector:
    matchLabels:
      app: example-api
  template:
    metadata:
      labels:
        app: example-api
        team: platform
        cost-center: cc-1234
        environment: production
    spec:
      containers:
      - name: api
        image: ghcr.io/example/api:1.2.3
        resources:
          requests:
            cpu: 1000m
            memory: 2Gi
          limits:
            cpu: 2000m
            memory: 4Gi
```

The service is scheduled on `m6i.large` nodes (2 vCPU, 8 GiB) at an on-demand price of approximately $0.096 per hour, or $70 per month. The 4 replicas each request 1 vCPU and 2 GiB; on `m6i.large`, that is roughly half a node per replica, so the 4 replicas reserve 2 full nodes of capacity, or roughly $140 per month in compute.

OpenCost, after a week, reports the workload's `cpuEfficiency: 0.18` and `ramEfficiency: 0.31` — observed CPU is 18 percent of requested, memory is 31 percent. The minimum-required compute, if requests were set to observed-P95 * 1.3, would be ~234m CPU and ~830Mi memory per replica. The 4 replicas would fit on a single `m6i.large` with capacity to spare. The over-provision waste is approximately $70 per month per replica, or $280 per month total — assuming the workload scales linearly with replicas, which it does because the load balancer is round-robin and replicas are stateless.

The right-sizing recommendation, in document form:

> **Workload:** `example-api` in namespace `example`, owned by team `platform`.
> **Current requests:** `cpu: 1000m, memory: 2Gi` per replica, 4 replicas.
> **Observed P95 usage:** `cpu: 180m, memory: 640Mi`.
> **Recommended requests:** `cpu: 250m, memory: 850Mi` per replica.
> **Replicas:** unchanged at 4 (load is comfortably handled at this replica count).
> **Expected savings:** ~$280 / month, based on the reduction from 2 nodes to 1 node of reserved capacity.
> **Blast radius:** the workload, only. No upstream consumers see a change. The HPA's autoscaling boundary moves down with the new requests; if the workload genuinely needs more, HPA will scale.
> **Rollback plan:** `kubectl rollout undo deployment/example-api -n example` reverts to the previous ReplicaSet within ~30 seconds.

A document of this shape is the right-sizing artifact. The team's SRE or platform lead reviews it; the workload's owner signs off; the change is applied. We will produce one ourselves in Exercise 2.

---

## 6. A note on storage and on the price of *not* having a discipline

One more pattern worth naming before we close, because it shows up at every organization once and is rarely flagged in the standard waste-source catalog. Call it **the snapshot graveyard**. The team enables EBS snapshots — or persistent-disk snapshots, in GCP — for backup. The snapshots are cheap individually. The retention policy is set to "keep forever" or to a very long retention. After three years the snapshot account holds tens of thousands of snapshots. The line item is a single number on the bill; nobody owns it; nobody knows which snapshot is from which volume; nobody dares delete any of them because some of them might still matter.

The cost shape is unique. Each snapshot is small — maybe a few cents per month. The aggregate is large. The fix is unglamorous: a quarterly snapshot review, automated tagging at snapshot creation (so each snapshot knows what it is and who owns it), and a retention policy enforced by lifecycle rules on the snapshot bucket. The pattern is mentioned here for completeness; it is a real category of waste in real organizations, even though it sits in the "storage" bucket of section 2 and not in the "three primary waste sources" of section 4.

A related pattern is the **log retention overrun**. Teams enable a log aggregator — CloudWatch Logs, Cloud Logging, a third-party SaaS — and set the retention to "default", which is often 90 days or "never expire". Over time the log volume grows; the per-GB-month storage charge compounds. A single team's logs from three years ago, on a per-day-per-namespace breakdown, can run into thousands of dollars per month if nobody set a retention. Fix: a retention policy of 30 days for application logs (with longer retention for audit logs in a separate, smaller stream) is the default that catches most cases. The discipline of separating audit logs from application logs is, itself, a cost-engineering exercise. Audit logs are small and must persist; application logs are large and rarely matter after a week. Co-mingling forces a single retention that is either too long or too short.

The two patterns share a structure with the three primary waste sources: a small per-unit cost that compounds because nobody is watching the aggregate. Cost engineering, at its heart, is the discipline of watching the aggregates so the per-unit charges do not surprise you.

---

## 7. Where this leaves us

Three pieces are now in place. We know the framing — unit economics, the ratio over the number. We know the structure of cloud cost — compute, storage, network, and the three modalities. We know the waste sources — over-provisioned compute, idle resources, egress, plus the snapshot and log-retention patterns from section 6. What we do not yet have is the *tool* — the thing that ingests usage data, joins it against pricing data, and produces per-namespace and per-label cost reports we can act on.

That tool is OpenCost. Tomorrow we install it, point it at a workload, and read its allocation responses. By Wednesday we will be querying it for right-sizing data. By Friday we will be reasoning about cost culture using the FinOps Foundation framework. By Sunday you will have written your own anomaly detector and your own right-sizing recommendation.

The discipline of cost engineering is not, in the end, technically hard. It is a discipline of consistent measurement, attribution, and review. The technical pieces — OpenCost, kube-state-metrics, Prometheus — are small. The discipline is large. It is the long pole.

Read tomorrow's exercise. Install OpenCost. Read the allocation API. We meet again Wednesday for Lecture 2.
