# Lecture 3 — The FinOps Foundation Framework and the Practice of Cost Culture

> *Tools without culture are a dashboard nobody reads. Culture without tools is a policy nobody can comply with. The job is both.*

We have spent the first half of the week on the technical machinery. We can install OpenCost. We can read its allocation API. We can aggregate by namespace and by label. We can flag a cost anomaly with two lines of statistics. Today we step up a level and ask the harder question: how does an engineering organization actually *use* this machinery to change behavior. The answer is the discipline of FinOps, and the canonical articulation of the discipline is the FinOps Foundation framework.

The FinOps Foundation is a Linux Foundation project at <https://www.finops.org/>. It is a vendor-neutral, non-profit body that maintains a framework, a certification, and a community of practice. The framework is licensed CC BY 4.0 — quotable and re-usable. The certification (FinOps Certified Practitioner, FOCP) is the discipline's entry credential and is currently free for individual first-time exam attempts at the time of this writing, with free coursework that overlaps closely with this week's material. The Foundation also stewards FOCUS (FinOps Open Cost and Usage Specification) — a standardized schema for cloud billing data, free at <https://focus.finops.org/>.

Today we cover three things. **First**, the framework itself — the six principles, the three phases, the personas, and the capabilities. **Second**, the practical patterns that work and the ones that do not. **Third**, the muscle the team has to build for the discipline to outlast the original advocate.

By the end of the lecture you should be able to describe the framework's structure to a colleague, identify what phase of the framework your hypothetical team is in, and identify the smallest sustainable next intervention. You should also be able to read a vendor's pitch deck critically — every cost-management SaaS describes itself as helping with FinOps, and the framework is the lens through which you sort the substance from the marketing.

---

## 1. The framework

### 1.1 The six principles

The framework opens with six principles. Read in full at <https://www.finops.org/framework/principles/>; summarized here.

**1. Teams need to collaborate.** Cost is a shared concern across engineering, finance, and leadership. The framework's central anti-pattern is the organization where finance owns "the bill" and engineering owns "the cluster" and the two never meet. The fix is structural — a regular forum where the personas talk to each other and the numbers go on the screen.

**2. Decisions are driven by the business value of cloud.** Cost is not minimized; it is optimized against value. A workload that costs $50,000 per month and produces $5,000,000 of revenue is cheap. A workload that costs $5,000 per month and produces nothing is expensive. The framing matters because the wrong framing — minimize the bill — produces stupid optimizations.

**3. Everyone takes ownership of their cloud usage.** Not a centralized cost team chasing engineers; engineers seeing their workload's cost and acting on it. The framework's strongest single empirical claim: the largest cost reductions come from giving the engineer their workload's cost, on a cadence they can act on, with permission to act. We will return to this.

**4. FinOps reports should be accessible and timely.** Daily, weekly, with the cost broken down by workload and team. Not a quarterly report from finance to the CFO; a weekly digest to the engineer whose name is on the workload's `owner` label.

**5. A centralized team drives FinOps.** A central team (typically 1 to 5 people, depending on org size) builds the tooling, the reports, the training, the policies. The central team's job is *enablement*, not enforcement. Engineering teams act on their cost; the central team makes acting on it easy.

**6. Take advantage of the variable cost model of the cloud.** The point of cloud is that capacity scales up and down with demand. A workload that runs at a fixed size 24/7 is not using the variable model. The principle is a counter to the engineering instinct to over-provision for peak — instead, scale.

The six principles are the philosophy. The next layer — phases — is the practice.

### 1.2 The three phases

The framework describes a maturity progression with three phases: **Inform**, **Optimize**, **Operate**. The phases are circular, not strictly sequential — a mature organization is constantly in all three for different workloads — but the progression of a team's *initial* adoption tends to follow them in order. Read in full at <https://www.finops.org/framework/phases/>.

#### Inform

Make cost visible.

The Inform phase is the prerequisite for everything else. The team cannot optimize what it cannot see. The Inform phase's outputs:

- **Cost allocation.** The bill broken down by team, environment, workload. Achieved through tag policies (cloud-side) and label policies (Kubernetes-side). Surfaced through tools (OpenCost, Kubecost, native cloud cost-management consoles, third-party SaaS).
- **Budgeting and forecasting.** Each team has a monthly budget. Forecasts project the actual spend against the budget. Alerts fire when forecast spend exceeds the budget.
- **Benchmarking and unit economics.** Cost per request, cost per user, cost per GB processed. Tracked over time. Available to engineering leadership.

The Inform phase is the longest single phase for most organizations, because the cultural work is in this phase. The technical pieces — install OpenCost, write a label policy — are weeks of work. The cultural work — getting every team to look at their cost report, getting finance to share the consolidated view, building the muscle of weekly review — is months to years. A team that has been "doing FinOps for a year" has typically been doing the Inform phase for a year.

#### Optimize

Reduce cost.

Once the cost is visible, the team can act on it. The Optimize phase's outputs:

- **Right-sizing.** Reduce over-provisioned compute, storage, network. The OpenCost efficiency report drives the work. Discussed in Lecture 1, exercised in Exercise 2.
- **Rate optimization.** Reserved instances, savings plans, committed-use discounts. Buy commitments against your steady-state baseline. Run on-demand and spot above it.
- **Workload optimization.** Architectural changes that reduce cost: caching to reduce egress, scheduling to reduce off-hours cost, code optimization to reduce compute.
- **Eliminate waste.** Idle resources, orphaned volumes, unused load balancers. The list from Lecture 1, section 4.2.

The Optimize phase produces dollar reductions on a quarterly cadence. The work is not glamorous; the savings compound.

#### Operate

Keep cost optimized.

The optimizations from the previous phase are easily undone. A new team joins, ignores the label policy, runs an always-on staging environment, deploys a workload at 10x the request it needs. Six months later the gains are erased. The Operate phase prevents this.

Operate-phase outputs:

- **Policy.** Admission controllers enforce label policies, request ranges, log-level constraints. Engineers cannot deploy workloads that violate the team standard.
- **Automation.** Right-sizing, scale-down, anomaly detection run as scheduled jobs. The discipline does not depend on a person remembering.
- **Education.** New engineers learn the team's cost standards as part of onboarding. The senior engineers carry the muscle memory.
- **Continuous improvement.** The cycle repeats — anomalies, right-sizing, audits, the ongoing maintenance of the cost discipline.

A team in the Operate phase is sustainable. A team that has done the work of Inform and Optimize but not Operate will regress within 12 to 18 months.

### 1.3 The personas

The framework names three personas: **engineer**, **finance**, **leadership**.

The engineer owns the workload. The engineer can change the workload's cost. The engineer's question is "how do I keep my workload performing without overspending". The engineer's tool is the cost report scoped to their workload.

Finance owns the budget. Finance pays the bill. Finance's question is "are we forecasting accurately and are commitments paying off". Finance's tool is the consolidated bill and the commit-utilization report.

Leadership owns the strategy. Leadership's question is "are we getting the business value from cloud spend, and is the unit economics improving". Leadership's tool is the unit-cost dashboard and the executive summary.

The framework's insistence on three personas is the framework's central organizational claim: FinOps is not "the finance team's problem". The three personas have to collaborate, on cadence, with shared data. The framework's third principle ("everyone takes ownership") is the corollary.

### 1.4 The capabilities

The framework catalogs ~25 capabilities a mature FinOps team performs. The full list is at <https://www.finops.org/framework/capabilities/>; the categories:

- **Understanding cloud usage and cost** — data ingestion, allocation, anomaly management.
- **Performance tracking and benchmarking** — forecasting, KPI tracking, unit economics.
- **Real-time decision making** — measurement against budgets, automated alerts.
- **Rate optimization** — commitment management, savings plans.
- **Workload optimization** — right-sizing, scaling, scheduling.
- **Organizational alignment** — chargeback, showback, governance.
- **Cloud policy and governance** — tag policies, budget enforcement.

A self-assessment against the capabilities list is a useful Q1 exercise for any engineering organization. The result is rarely flattering — a typical organization scores well on 2 or 3, partially on 8 to 10, and not at all on the remaining. The point of the assessment is not to score well; the point is to choose the next two capabilities to invest in.

---

## 2. FOCUS — the data standard

The other major Foundation deliverable is FOCUS — the FinOps Open Cost and Usage Specification at <https://focus.finops.org/>. FOCUS is to cloud billing data what OpenTelemetry is to observability data — a vendor-neutral specification of the column names and semantics that a billing export should have.

Why a standard. Every cloud's billing export is shaped differently. AWS's Cost and Usage Report (CUR) has columns named one way; GCP's Billing Export has columns named another way; Azure's Cost Management has a third shape. A multi-cloud organization wires three different ETL pipelines to get to a common shape. FOCUS is the proposed common shape; if every cloud emits FOCUS, the ETL pipeline collapses.

As of May 2026, FOCUS 1.x is stable. AWS, GCP, Azure, and Oracle have all committed to FOCUS-compliant exports; the actual coverage as of the 2026 review is partial — AWS and GCP have FOCUS-format exports available, Azure is in preview, Oracle is in development. The specification covers, roughly, 50 column names and definitions across billing categories.

Even if your cloud bill is not in FOCUS format today, the schema names the columns you should be thinking in. The exercise of mapping your current bill to the FOCUS column names is, in itself, a useful Inform-phase exercise.

We do not script against FOCUS this week. Mention it as a forward-looking specification; expect to see it land as the standard in 2027 to 2028.

---

## 3. Patterns that work and patterns that do not

The framework is the theory. The practice is messier. A canvassing of FinOps adoption stories, from the Foundation's case-study library and from independent reporting, suggests a set of patterns.

### 3.1 What works

**Showback before chargeback.** Showback is the practice of showing each team their cost without billing them for it. Chargeback is the practice of charging the team's budget for their cost. Every successful adoption starts with showback for at least one quarter. Teams need to see the number, understand the number, dispute the number, and trust the number before the number can have budget consequences. Starting with chargeback produces defensiveness and finger-pointing; showback produces curiosity.

**Per-engineer cost ownership.** The strongest single intervention. Each workload has an `owner` label. The owner gets a weekly cost report. The owner has permission to right-size, scale-down, and delete. The owner sees the cost change after they act. The feedback loop is short enough that the muscle builds.

**A weekly cost-review forum.** A 30-minute meeting, once a week, between engineering leadership, the FinOps central team, and rotating engineering team representatives. Agenda: anomalies, savings opportunities, upcoming launches. Held with the cost dashboard on screen.

**Per-pull-request cost estimates.** A CI step that runs Infracost or OpenInfraQuote on every infrastructure PR. The PR shows the estimated monthly cost change. The reviewer sees it. The discussion that follows is about the cost. The discipline becomes part of code review.

**Right-sizing as a routine.** A quarterly right-sizing audit, run by the central team, that produces a list of over-provisioned workloads and routes each to its owner. The owner reviews and applies the change. The audit is automated; the review is human.

**Spot for build infrastructure.** CI/CD runners are stateless, idempotent, interruption-tolerant. Running them on spot saves 60 to 90 percent on what is typically a 5 to 15 percent share of the bill. The savings are real and the risk is low.

### 3.2 What does not work

**A consolidated dashboard nobody owns.** A FinOps dashboard built by the central team, deployed to a Grafana instance, and assumed to be read by engineers. Nobody reads it. The discipline does not improve.

**Cost as a bonus metric.** Tying engineer bonuses to cost reductions. Produces bad incentives — engineers de-provision aggressively to hit the bonus, the system becomes unreliable, the cost reduction is unwound the following quarter. The framework's principle on business value is the corrective.

**Buying a cost SaaS without policy.** A team buys Apptio Cloudability or Vantage, expects the tool to fix the cost problem, and is surprised when nothing changes. The tools surface data; the data does not change behavior; the behavior changes only when policy and culture change. The tool is a quarter of the work.

**Centralized cost veto.** A FinOps team that has to approve every workload's resource requests. Becomes a bottleneck within months; engineering teams route around it; the team's authority erodes. The framework's structure — central team enables, engineering team owns — is the prophylactic.

**Optimization without measurement.** Right-sizing all workloads at once based on a one-time audit, without continuous measurement. The savings are real; six months later, growth has eroded them. The Operate phase is the difference.

---

## 4. The FinOps Certified Practitioner certification

The Foundation's flagship certification is the FinOps Certified Practitioner (FOCP) at <https://learn.finops.org/path/finops-certified-practitioner>. It is a multiple-choice exam covering the framework, the practice, and basic vocabulary.

As of the May 2026 review, the certification's standing:

- **Coursework: free.** The Foundation publishes the full course material at no cost. Several hours of video, reading, and self-assessment. Adequate for a learner with this week's content already absorbed.
- **Exam: currently free for individual first-time attempts.** The Foundation's policy has shifted over the years. Confirm at registration. The exam is currently delivered via the Foundation's learning platform.
- **Validity: three years.** The credential expires; continuing education or re-examination renews it.
- **Recognition: the discipline's entry credential.** Common on FinOps-team job descriptions. Not load-bearing for hiring (a candidate's actual practice matters more), but expected at the senior level.

Recommend the FOCP coursework as the next-step reading after this week, regardless of whether the learner sits for the exam. The coursework's coverage of the framework is more thorough than this lecture's; the practical chapters complement the technical work we have done.

The Foundation also offers a **FinOps Certified Engineer (FOCE)** — newer, more technical, focused on the engineer persona's work specifically. The FOCE coursework is also free; the exam fee varies.

---

## 5. Building the muscle

The framework is necessary; it is not sufficient. The muscle the team has to build is the muscle of consistent, small, ongoing review. The technical pieces — OpenCost, kube-state-metrics, Prometheus, the Python anomaly script — are the easy half. The hard half is the human practice.

A short list of mechanisms that build the muscle:

**A weekly engineering cost email.** Per team, per Monday morning. The previous week's cost, the week-over-week change, the top three workloads by cost, the top three by efficiency ratio (most-over-provisioned). A link to the OpenCost UI for drill-down. Five-minute read; lands before the engineer opens their IDE.

**A monthly leadership cost review.** Engineering leadership, the FinOps central team, finance. 60 minutes. The previous month's spend, unit-economic trends, anomalies and their resolutions, upcoming launches and their cost forecasts.

**A quarterly strategic review.** Engineering leadership, finance, executive leadership. Half a day. The framework's three phases, where the organization is, what the next investments are. Re-evaluation of commitments. Discussion of the next year's growth assumptions.

**An onboarding module.** New engineers learn the cost discipline in their first week. The team's label policy, the cost-report cadence, the right-sizing playbook, the OpenCost UI tour. Twenty minutes of self-paced video, a short quiz, a TODO to right-size at least one workload in the first month.

**A retrospective when a cost anomaly is missed.** When the team learns of a cost anomaly only at month-end, the post-mortem is the same shape as the post-mortem for a missed availability incident. What was the signal. Was the signal monitored. Was the threshold right. Was the on-call response timely. The discipline of treating cost like reliability is the long-pole shift.

The muscle takes 12 to 18 months to build and 3 to 6 months of inattention to lose. The advocate's job is to make the muscle structural — embedded in the tooling, the policies, the meetings — so that it survives the advocate's eventual departure.

---

## 6. A note on AI/ML workloads

A digression worth flagging. The framework was last refreshed in 2024 with explicit AI/ML cost guidance. GPU workloads break a number of the assumptions in classical FinOps practice:

- **GPU cost is dominated by reservation, not utilization.** A reserved GPU costs the same whether it runs at 5 percent or 95 percent utilization. The right-sizing math we used in Lecture 1 does not directly apply; the question is whether the GPU is reserved at all, not how much of it is used.
- **Training-cost amortization.** A training run produces a model. The model is used for inference for months. The cost-per-inference must amortize the training cost across the inference volume. This is unit economics with a twist.
- **Inference batching and right-sizing.** Smaller models, quantization, batching, caching — all are cost levers specific to AI workloads. None are covered by classical FinOps tooling.
- **Egress for model artifacts.** Distributing a large model across regions can move terabytes. The egress cost is meaningful.

This week's exercises do not touch GPU workloads — they are stateless web tier and batch CPU jobs. C17 (Crunch LLMOps) returns to this in depth. The FinOps Foundation has a dedicated AI Working Group at <https://www.finops.org/community/working-groups/> with current guidance.

---

## 7. Where we have arrived

We have, by the end of this week, the technical machinery and the conceptual framework. We can install OpenCost. We can attribute cost. We can detect anomalies. We can articulate the framework that turns the data into a practice. We have read or surveyed the canonical sources — the Foundation framework, the FOCUS specification, the OpenCost project documentation, the cloud-provider pricing pages, the AWS and GCP pricing calculators.

What we cannot do, in a single week, is build the muscle. The muscle is a 12-to-18-month project for a small team and a multi-year project for a large one. The point of this week is to give you the vocabulary, the tools, and the early reps so you can start when you encounter a team where the discipline is missing.

The cluster from Week 9 is observable. From Week 10, it is trustworthy. From this week, it is accountable. The arc of the second half of C15 — observability, security, cost — is the arc from "the cluster runs" to "the cluster runs in a way you can defend in front of executives, regulators, and customers". That is the arc of operational maturity.

Next week the arc continues: Week 12 is Karpenter, node autoprovisioning, and the cluster's autonomous responses to demand. The cluster begins to take care of itself.

Read tomorrow's exercises. Bring the OpenCost responses. We will reason about real numbers, on a real cluster, on Sunday.
