# Week 11 — Resources

All resources listed here are free at the time of writing (May 2026). Where a paid product is mentioned, it is identified as such and a free equivalent is named. The order is curated, not alphabetical; read top to bottom for a coherent path through the material.

---

## Primary sources — read these first

- **OpenCost — project home.** <https://www.opencost.io/>. The CNCF-incubating, Apache-2.0 open-source project that this week is built around. Start with the *Introduction* page; the *Installation* page is the basis for Exercise 1; the *API* page documents the `/allocation` and `/assets` endpoints we script against.
- **OpenCost — GitHub.** <https://github.com/opencost/opencost>. The source. The `docs/` directory is more current than the website in places. Look at `docs/integrations/aws-pricing.md` to understand the cloud-provider price-fetching logic.
- **OpenCost Helm chart.** <https://github.com/opencost/opencost-helm-chart>. The chart we install in Exercise 1. The `values.yaml` is the single source of truth for what is configurable.
- **FinOps Foundation — framework.** <https://www.finops.org/framework/>. Read the *Principles* page, then the three phases (*Inform*, *Optimize*, *Operate*), then the *Capabilities* list. The framework is licensed CC BY 4.0; you can quote it freely as long as you cite it.
- **FinOps Foundation — FOCUS specification.** <https://focus.finops.org/>. The FinOps Open Cost and Usage Specification — a standardized schema for cloud billing data. The 1.x specification is stable. Even if your cloud bill is not in FOCUS format today, the schema names the columns you should be thinking in.
- **AWS Pricing Calculator.** <https://calculator.aws/>. Free, no login. Build an estimate, save a shareable URL, share it in pull request reviews. Exercise 4 walks through this.
- **GCP Pricing Calculator.** <https://cloud.google.com/products/calculator>. The GCP analogue. The interface is slightly different; the discipline is the same.

---

## OpenCost — deeper reading

- **OpenCost API reference.** <https://www.opencost.io/docs/api>. The full shape of every endpoint response. Our exercises hit `/allocation` and `/assets`; for production deployments `/cloudCost` and `/savings` matter too.
- **OpenCost specification.** <https://github.com/opencost/opencost/blob/develop/spec/opencost-specv01.md>. The CNCF specification document. Read this if you want to write a downstream tool that consumes OpenCost data — it pins the data model.
- **OpenCost talks from KubeCon.** The 2023 and 2024 KubeCon Europe and North America events each had OpenCost project-update talks. Search the CNCF YouTube channel for "OpenCost" — most are 25 to 40 minutes, free, and the project maintainers walk through what changed in each release.
- **CNCF project page.** <https://www.cncf.io/projects/opencost/>. The CNCF page tracks the project's incubation status, governance, and graduation criteria.

---

## Kubecost (the paid SaaS) — vendor context

- **Kubecost — product home.** <https://www.kubecost.com/>. Read this to understand the commercial product built on top of OpenCost. Useful for the "OpenCost vs Kubecost" judgement exercise in Lecture 2.
- **Kubecost pricing.** <https://www.kubecost.com/pricing/>. The free, paid, and enterprise tiers as of the 2026 review. The free tier is functionally OpenCost plus a UI; the paid tiers add multi-cluster aggregation and longer retention.
- **Kubecost vs OpenCost — official comparison.** <https://docs.kubecost.com/architecture/opencost>. The vendor's own statement of what features are in each. Read it critically — vendors are paid to draw the line where they would like the line.

---

## FinOps Foundation — deeper reading

- **FinOps Foundation — principles (full text).** <https://www.finops.org/framework/principles/>. The six principles, expanded. The most-quoted single page in the framework.
- **FinOps Foundation — phases.** <https://www.finops.org/framework/phases/>. Inform, Optimize, Operate. The diagram on this page is reproduced everywhere; understand each phase's outputs.
- **FinOps Foundation — personas.** <https://www.finops.org/framework/personas/>. Engineer, finance, leadership. The framework's insistence that FinOps is a multi-persona discipline (not "finance does it") is the framework's central claim.
- **FinOps Foundation — capabilities.** <https://www.finops.org/framework/capabilities/>. A list of practices a mature FinOps team performs. Read this as a checklist for an organization's self-assessment.
- **FinOps Foundation — Open Source.** <https://www.finops.org/community/open-source/>. The Foundation lists OpenCost, FOCUS, and a handful of other open-source projects it supports. The list grows; check the current page.
- **FinOps Certified Practitioner (FOCP).** <https://learn.finops.org/path/finops-certified-practitioner>. The certification's coursework page. As of the 2026 review window, the coursework is free; the certification exam is currently free for first-time individual attempts (confirm at registration — the Foundation's policy has shifted historically). Read the syllabus even if you do not sit for the exam — it overlaps closely with this week's material.
- **State of FinOps — annual report.** <https://www.finops.org/insights/state-of-finops/>. Free, published annually. The 2024 edition surveyed ~1,200 organizations; the report is the closest thing to industry benchmark data on cost-discipline maturity.

---

## Cloud pricing — official references

- **AWS pricing — overview.** <https://aws.amazon.com/pricing/>. The top of the AWS pricing pyramid. Every service has its own pricing page underneath.
- **AWS EC2 pricing.** <https://aws.amazon.com/ec2/pricing/>. On-demand, reserved (1-year, 3-year, all upfront, partial upfront, no upfront), spot. Read the page once end-to-end; it is the model every other AWS service follows.
- **AWS Savings Plans.** <https://aws.amazon.com/savingsplans/>. The successor to Reserved Instances for compute. Compute Savings Plans cover EC2, Fargate, and Lambda. Read the *Compute* page; the *EC2* page is more restrictive.
- **AWS data transfer pricing.** <https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer>. The single page that explains why your network bill is what it is. Note the asymmetry: inbound is free, cross-zone is not, internet-out is the most expensive.
- **GCP pricing — overview.** <https://cloud.google.com/pricing>. The GCP analogue.
- **GCP Committed Use Discounts.** <https://cloud.google.com/compute/docs/instances/signing-up-committed-use-discounts>. GCP's reserved-equivalent. Spend-based commits or resource-based commits.
- **GCP Spot VMs.** <https://cloud.google.com/compute/docs/instances/spot>. Successor to GCP's older "Preemptible VMs". Same idea, modern interface.
- **Azure pricing — overview.** <https://azure.microsoft.com/en-us/pricing/>. Included for completeness; this week's exercises use AWS / GCP examples but Azure follows the same structure (on-demand, reserved, spot).
- **Azure Pricing Calculator.** <https://azure.microsoft.com/en-us/pricing/calculator/>. The Azure analogue.

---

## CNCF — context

- **CNCF — cost engineering landscape.** <https://landscape.cncf.io/>. Filter by category. OpenCost is in the *Continuous Integration & Delivery* / *Observability and Analysis* sections depending on the view. Browsing the landscape is how you learn what the rest of the cost-engineering toolspace looks like (Karpenter, Vertical Pod Autoscaler, Goldilocks, KubeCost — many overlap with this week).
- **Karpenter.** <https://karpenter.sh/>. AWS-led open-source node-autoprovisioning project. Adjacent to FinOps because it can directly reduce compute waste by choosing more right-sized nodes. C15 covers Karpenter conceptually in Week 12; it is mentioned here for orientation.
- **Vertical Pod Autoscaler.** <https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler>. Kubernetes-native right-sizing. Reads pod usage and suggests (or applies) updated requests. Covered conceptually in Lecture 3 of this week.
- **Goldilocks.** <https://github.com/FairwindsOps/goldilocks>. A free tool from Fairwinds that wraps VPA and produces a per-namespace right-sizing dashboard. Free for the basic install; the paid Fairwinds Insights wraps multiple Fairwinds open-source tools.

---

## Books and long-form reading

- **Cloud FinOps (O'Reilly, 2nd ed.).** J.R. Storment, Mike Fuller. The book that defined the discipline. Out via O'Reilly's online platform (subscription required) — many libraries provide free O'Reilly access. The 2nd edition (2023) is current; the 1st edition (2019) predates much of the OpenCost-era tooling.
- **The Economics of Cloud Computing (free article).** The CNCF blog has a 2023 "Economics of Cloud Native" post that summarizes the core mental model in ~3,000 words. <https://www.cncf.io/blog/>. Search for "FinOps" or "Economics".
- **Corey Quinn — Last Week in AWS.** <https://www.lastweekinaws.com/>. A free weekly newsletter on AWS cost and culture. The blog has free long-form posts; the newsletter is the easy way to subscribe to ongoing context.
- **GCP cost optimization handbook.** <https://cloud.google.com/architecture/framework/cost-optimization>. Google Cloud's official cost-optimization architecture-framework chapter. Vendor-authored but free and substantive.
- **AWS Well-Architected — Cost Optimization pillar.** <https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html>. The same idea from AWS. Vendor-authored, free, substantive.

---

## Prometheus and observability — refreshers from Week 9

- **Prometheus — query basics.** <https://prometheus.io/docs/prometheus/latest/querying/basics/>. Refresher. OpenCost uses Prometheus as its data source for resource-usage observation; if you cannot read a PromQL query you cannot verify OpenCost's math.
- **kube-state-metrics.** <https://github.com/kubernetes/kube-state-metrics>. The exporter that turns Kubernetes object state (Deployments, Pods, Nodes, Namespaces, Labels) into Prometheus metrics. OpenCost cross-joins kube-state-metrics output against pod-level usage to attribute cost.
- **kube-prometheus-stack chart.** <https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack>. The Helm chart that installs Prometheus, Grafana, kube-state-metrics, and node-exporter together. Installed in Exercise 1.

---

## Anomaly detection and statistics

- **Anomaly detection — a primer.** <https://en.wikipedia.org/wiki/Anomaly_detection>. The Wikipedia article is more substantive than most introductory blog posts. Read the *Statistical methods* section.
- **Z-score primer.** <https://en.wikipedia.org/wiki/Standard_score>. Refresher on the two-standard-deviations rule we use in Exercise 3.
- **Time series anomaly detection — Twitter's algorithm (open source).** <https://github.com/twitter/AnomalyDetection>. R package, but the underlying *S-H-ESD* algorithm is documented and reusable. Beyond this week's scope; included for orientation.

---

## Adjacent open-source tools — for context, not required this week

- **OpenInfraQuote.** <https://github.com/terraform-cost-estimation/openinfraquote>. Open-source Terraform cost estimator. Adjacent to FinOps — instead of measuring running cost, it estimates planned cost from Terraform plans.
- **Infracost (free tier and paid).** <https://www.infracost.io/>. Terraform / OpenTofu cost estimator with a free open-source CLI and a paid SaaS for team features. The CLI is the relevant free piece.
- **kubectl-cost.** <https://github.com/kubecost/kubectl-cost>. A kubectl plugin from Kubecost that wraps the OpenCost / Kubecost API into ergonomic CLI commands. Free; works against OpenCost as well as Kubecost.
- **CloudHealth, CloudCheckr, Apptio Cloudability.** Paid SaaS cost-management tools. Mentioned for context; we do not use them this week. They are typically priced at a percentage of cloud spend.

---

## Cited in lectures and exercises

The lectures and exercises this week link out to specific docs pages. The complete list, with stable URLs:

- OpenCost installation: <https://www.opencost.io/docs/installation/install>
- OpenCost configuration reference: <https://www.opencost.io/docs/configuration/configuration>
- OpenCost cost model: <https://github.com/opencost/opencost/blob/develop/docs/cost-model.md>
- OpenCost custom pricing: <https://github.com/opencost/opencost/blob/develop/docs/custom-pricing.md>
- FinOps Foundation framework (root): <https://www.finops.org/framework/>
- FinOps Foundation FOCUS spec: <https://focus.finops.org/focus-specification/>
- AWS Pricing Calculator (root): <https://calculator.aws/>
- GCP Pricing Calculator (root): <https://cloud.google.com/products/calculator>
- AWS EC2 instance pricing: <https://aws.amazon.com/ec2/pricing/on-demand/>
- AWS data transfer pricing: <https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer>
- GCP Compute Engine pricing: <https://cloud.google.com/compute/all-pricing>
- GCP network pricing: <https://cloud.google.com/vpc/network-pricing>
- Kyverno cluster policies: <https://kyverno.io/docs/writing-policies/>
- Vertical Pod Autoscaler: <https://github.com/kubernetes/autoscaler/blob/master/vertical-pod-autoscaler/README.md>
- kube-state-metrics metrics list: <https://github.com/kubernetes/kube-state-metrics/tree/main/docs/metrics>
- Prometheus PromQL: <https://prometheus.io/docs/prometheus/latest/querying/basics/>

---

## What to skip this week

- **Closed-source vendor demos.** Cost-management SaaS vendors (Apptio, Vantage, CloudHealth, Spot.io) routinely book demos with engineering teams. The demos are useful exposure if you have time; they are not required and they will not show you anything you do not get from OpenCost plus a Friday afternoon. Defer.
- **The deep specification of FOCUS v1.x.** The spec is a 60-page document. Read the introduction and the column-name table; defer the full normative section to a working week when you are actually wiring a billing-data pipeline.
- **The full kube-prometheus-stack chart values.** The chart's `values.yaml` is ~3,500 lines. The exercises pin the values they need. Do not try to read the whole thing.

That is the week. Open the README, then Lecture 1, and begin.
