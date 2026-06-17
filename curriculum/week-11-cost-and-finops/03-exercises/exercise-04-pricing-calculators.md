# Exercise 4 — The pricing-calculator workflow

**Estimated time:** 30 minutes.
**Prerequisite reading:** Lecture 1, section 2.

The goal of this exercise is to build the muscle of pricing an architecture *before* deploying it. The AWS and GCP pricing calculators are free, browser-based, and produce shareable estimate URLs. The discipline of including a calculator URL in every architecture proposal is the single highest-leverage habit on the FinOps calendar.

We do not stand up cloud accounts. We use the calculators as design tools.

---

## Part A — Price a workload in AWS

Open <https://calculator.aws/> in a browser. No login required.

The workload to price:

> A FastAPI service running on Amazon EKS in `us-east-1`. 6 replicas of a pod requesting 500m CPU and 1 GiB memory each. Backed by an Amazon RDS for PostgreSQL `db.t4g.medium` Single-AZ instance with 100 GiB of gp3 storage. Exposed via an Application Load Balancer. Average data egress to the internet of 500 GB / month. The cluster is on-demand `m6i.large` instances; assume 3 instances suffice. No reserved-instance commitments.

Click *Configure* in the AWS Pricing Calculator. Add the following line items:

1. **Amazon EC2** (3 x m6i.large, us-east-1, on-demand, Linux, 730 hours).
2. **Amazon EKS** (1 cluster, us-east-1, 730 hours — the $0.10/hour control-plane fee).
3. **Application Load Balancer** (1 ALB, us-east-1, 730 hours, ~25 new connections/sec, 1 KB request size).
4. **Amazon RDS for PostgreSQL** (db.t4g.medium, Single-AZ, us-east-1, 730 hours, 100 GiB gp3).
5. **AWS Data Transfer** (500 GB out to internet from us-east-1).

After adding the line items, click *Save and view summary*. The calculator computes a monthly total. Copy the *Share* URL. As of May 2026, you should arrive at a monthly figure in the rough range of $400 to $550 (the exact number moves as AWS updates pricing).

Note the line-item shares:

- The EC2 instances are typically the largest line.
- The EKS control-plane fee is a fixed $73/month — small but a real line.
- The ALB has both a per-hour and per-LCU component.
- The RDS instance, including storage, is typically the second- or third-largest line.
- The egress is small in absolute terms but is the line that scales badly if traffic grows.

Save the share URL. You will paste it into `SOLUTIONS.md`.

---

## Part B — Price the same workload in GCP

Open <https://cloud.google.com/products/calculator>. No login required.

Recreate the same workload on GCP Cloud equivalents:

1. **Compute Engine** (3 x n2-standard-2, us-central1, on-demand, Linux, 730 hours).
2. **GKE** (1 cluster, us-central1, 730 hours — GKE Standard has a $0.10/hour cluster-management fee on the first cluster, free after that; the free first-cluster credit may apply, mark it accordingly).
3. **Cloud Load Balancing** (1 Application Load Balancer, US, ~25 new connections/sec).
4. **Cloud SQL for PostgreSQL** (db-custom-2-4096 or similar, us-central1, 100 GiB SSD).
5. **Network egress** (500 GB to internet from us-central1 to worldwide).

Save the share URL. Note the differences from AWS:

- GCP's per-vCPU pricing is similar to AWS but the exact instance shapes are different (`n2-standard-2` is 2 vCPU / 8 GiB; the closest AWS equivalent is `m6i.large` at 2 vCPU / 8 GiB).
- GCP's load balancer has a different pricing model (per-rule, per-forwarding-rule).
- GCP's network egress to the internet is similar in shape but the per-GB rate is slightly different.
- GCP Cloud SQL is more expensive per vCPU than RDS, but the storage is cheaper per GB.

The two estimates should be in the same order of magnitude, typically within 20 percent of each other.

---

## Part C — Reflect on the gap

The AWS and GCP estimates differ. Some of the gap is real (different instance shapes, different load-balancer pricing, different egress rates). Some of the gap is calculator imprecision (the load balancer's per-LCU usage is hard to predict accurately at design time).

Real-world experience: the calculator's number is typically accurate to within plus-or-minus 20 to 30 percent of what the actual bill will be after a month of production traffic. The discrepancy comes from:

- **Network usage** — almost always higher than predicted at design time.
- **Storage growth** — almost always higher than predicted at design time, because retention windows lengthen and data volumes grow.
- **Idle and unused resources** — the calculator assumes you turn things off when you do not need them; in practice teams leave them on.

The discipline: use the calculator number for design conversations, but adjust the budget by 20 to 30 percent upward. A workload the calculator says will cost $500/month is budgeted at $625/month. The team rebuilds the calculator estimate quarterly against actual usage; the discrepancy informs the next forecast.

---

## Part D — A small architectural choice

The same workload, with one architectural change: move the RDS PostgreSQL to **Aurora PostgreSQL Serverless v2** with a minimum of 0.5 ACU and a maximum of 4 ACU. Cost the change in the AWS Pricing Calculator.

Aurora Serverless v2 has a different pricing model: per ACU-hour ($0.12/ACU-hour as of May 2026), scaling between the minimum and maximum based on demand. A workload averaging 1 ACU pays for 730 ACU-hours / month, or roughly $88 / month. A workload averaging 4 ACU pays $350 / month.

The trade-off discussion to record in `SOLUTIONS.md`:

- Aurora Serverless v2 scales to zero traffic without paying full price for an idle instance.
- It does not literally scale to zero — the minimum is 0.5 ACU (~$44/month).
- For a bursty workload, the cost can be lower than a fixed-size RDS.
- For a steady-state workload, the cost is typically higher.

The discipline: name the workload's traffic pattern, then pick the modality. A staging environment with no traffic on weekends is a Serverless candidate. A production workload with steady 24/7 traffic is a fixed-size candidate.

---

## Part E — Checkpoint

Paste into `SOLUTIONS.md`:

1. The AWS Pricing Calculator share URL from Part A.
2. The GCP Pricing Calculator share URL from Part B.
3. A short paragraph naming the three largest line items in each, and whether the absolute total figures from AWS and GCP are within 20 percent of each other.
4. A short paragraph from Part D — under what traffic pattern would Aurora Serverless v2 be cheaper than the fixed-size RDS, and under what pattern would it be more expensive?

---

## Reading

- AWS Pricing Calculator (root): <https://calculator.aws/>
- AWS EC2 on-demand pricing: <https://aws.amazon.com/ec2/pricing/on-demand/>
- AWS data transfer pricing: <https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer>
- AWS Aurora pricing: <https://aws.amazon.com/rds/aurora/pricing/>
- GCP Pricing Calculator (root): <https://cloud.google.com/products/calculator>
- GCP Compute Engine pricing: <https://cloud.google.com/compute/all-pricing>
- GCP Cloud SQL pricing: <https://cloud.google.com/sql/pricing>

You are done with the exercises. Continue to `challenges/` and `mini-project/`.
