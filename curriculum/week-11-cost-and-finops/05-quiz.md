# Week 11 — Quiz

Twenty questions. Two passes:

- **First pass (closed-book).** No reference material. Estimated 20 minutes. Score yourself.
- **Second pass (open-book).** With access to the lectures, the OpenCost docs, the FinOps Foundation site, and the AWS / GCP pricing calculators. For each question you got wrong on the first pass, write the correct answer and cite the source. Estimated 30 minutes.

Submit both passes. The grader rewards engagement with the source material as much as the right answer.

---

## Multiple choice (12 questions)

**1.** A Kubernetes `Secret` object is:

- A. Encrypted at rest by Kubernetes.
- B. Encrypted in flight by the API server.
- C. Base64-encoded but not encrypted; encryption-at-rest requires separate cluster configuration.
- D. Stored only in the pod's memory and never persisted.

**2.** Which of the following is the canonical FinOps unit-economics metric for a SaaS API business?

- A. Total cloud spend per month.
- B. Cost per request.
- C. Number of running pods.
- D. CPU utilization across the cluster.

**3.** The three biggest waste sources in a typical Kubernetes-driven cloud bill, per Lecture 1, are:

- A. Over-provisioned compute, idle resources, egress charges.
- B. Storage growth, control-plane fees, log retention.
- C. Reserved-instance over-commits, spot interruptions, NAT gateways.
- D. Container images, image registries, registry egress.

**4.** Which OpenCost endpoint returns per-workload cost broken down by namespace?

- A. `/metrics`.
- B. `/healthz`.
- C. `/allocation`.
- D. `/audit`.

**5.** OpenCost's `cpuEfficiency` field on an allocation entry represents:

- A. The fraction of node CPU consumed by the pod.
- B. The fraction of the pod's CPU request that was actually used.
- C. The cost per CPU core-hour.
- D. The CPU credit balance on a burstable instance.

**6.** The FinOps Foundation framework defines three phases. They are, in order:

- A. Detect, Investigate, Remediate.
- B. Inform, Optimize, Operate.
- C. Plan, Build, Run.
- D. Measure, Manage, Monitor.

**7.** A spot instance, in any major cloud, is best suited to which workload?

- A. A stateful primary Postgres database.
- B. A stateless web tier behind a load balancer.
- C. The Kubernetes control plane.
- D. An etcd cluster member.

**8.** Which of the following is NOT a typical cost-allocation label in the team-standard label policy from this week?

- A. `team`.
- B. `cost-center`.
- C. `environment`.
- D. `replicas`.

**9.** The "autoscaler runaway" cost anomaly pattern most commonly results from:

- A. A scheduled deploy.
- B. A loss of the metric source the HPA uses, causing the HPA to scale to its maximum.
- C. A node-pool exhaustion event.
- D. An RBAC misconfiguration.

**10.** Which of the following is true about Kubecost vs OpenCost?

- A. OpenCost is paid; Kubecost is free.
- B. Kubecost the SaaS is built on top of OpenCost; the open-source Kubecost free tier is functionally OpenCost plus a UI.
- C. They are unrelated projects.
- D. OpenCost runs only on AWS; Kubecost runs anywhere.

**11.** Which statistical rule is most appropriate for catching a slow cost drift (5 percent per day over a month) that never crosses a single-day percent-change threshold?

- A. Percent-change against the previous day.
- B. Percent-change against the previous month.
- C. Z-score against a 14-day rolling mean.
- D. Median across the full year.

**12.** The AWS Pricing Calculator at <https://calculator.aws/> is:

- A. A paid product.
- B. Free to use, requires AWS account login.
- C. Free to use, no login required, produces shareable estimate URLs.
- D. An internal AWS-employee-only tool.

---

## Short answer (5 questions)

**13.** In two or three sentences, describe the difference between a *cost* and an *efficiency* in OpenCost's data model.

**14.** Lecture 2 names two famous cost-anomaly patterns: the autoscaler runaway and the log-pipe explosion. Pick one. Describe (a) the cause, (b) the cost shape (which OpenCost field rises), (c) one technical control that prevents recurrence.

**15.** The team-standard label policy enforces four labels on every production Pod. Name them. For each, give a one-sentence justification of why that label is required and not optional.

**16.** Lecture 3 describes "showback before chargeback" as a recommended adoption pattern. In your own words, explain why an organization should run showback for at least a quarter before introducing chargeback.

**17.** A team is considering moving its CI/CD build runners from on-demand EC2 to spot. Describe (a) two reasons spot is a good fit for build runners, (b) one architectural change the team must make to tolerate spot interruptions, (c) the rough expected cost savings as a percentage of the current bill.

---

## Calculation (3 questions)

**18.** A Deployment has 5 replicas, each requesting 1000m CPU and 2Gi memory. OpenCost reports the workload's monthly cost as $420 and its `cpuEfficiency: 0.18`, `ramEfficiency: 0.32`. Using the conservative (lower) efficiency, what is the approximate monthly recoverable waste if the workload is right-sized?

**19.** A workload's daily cost for the last 14 days is: 12, 11, 13, 12, 14, 12, 11, 12, 13, 12, 11, 12, 13, 28 dollars. Compute (a) the mean of the first 13 days, (b) the standard deviation of the first 13 days, (c) the z-score of day 14, (d) whether day 14 fires the z-score rule with a threshold of 2.0.

**20.** A staging environment running 24/7 costs $8,000 / month. The team wants to scale every Deployment in it to zero on weekday evenings (7pm to 8am local time) and all weekend. (a) What fraction of the week is "off-hours" under that schedule? (b) Assuming compute scales linearly with running hours and is the only cost component, what is the new monthly cost? (c) What is the absolute monthly saving?

---

## Grading

- Multiple choice: 1 point each, 12 points.
- Short answer: 2 points each, 10 points.
- Calculation: 3 points each, 9 points.

Total: 31 points. Pass: 20. Distinction: 26.

Answer key in `quiz.answers.md` (created by the instructor at grading; do not check it in alongside your submission). For each calculation, show your work.

---

## Citations expected on second pass

A strong second pass cites specific sources for the answers. Examples:

- For Q1: cite Kubernetes documentation at <https://kubernetes.io/docs/concepts/configuration/secret/>.
- For Q6: cite <https://www.finops.org/framework/phases/>.
- For Q9: cite Lecture 2, section 4.3 of this week.
- For Q11: cite <https://en.wikipedia.org/wiki/Standard_score>.
- For Q12: cite <https://calculator.aws/>.

The grader looks for an engaged second pass — wrong answers with cited corrections score above blank or unimproved second-pass answers.
