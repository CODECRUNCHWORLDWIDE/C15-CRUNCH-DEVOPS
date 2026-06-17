# Week 11 — Homework

Three homework items, due Sunday end-of-day. Each builds the muscle from a different angle. None require the kind cluster to be running.

---

## Homework 1 — Read and summarize the FinOps Foundation principles

**Estimated time:** 45 minutes.

Open <https://www.finops.org/framework/principles/> and read all six principles in full. For each principle, write:

- A one-sentence restatement in your own words.
- An example, drawn from any organization you have worked at or any case study you have read, of the principle being honored.
- An example, again drawn from real experience or a case study, of the principle being violated.

The output is six short paragraphs, one per principle. Submit as a Markdown document named `finops-principles-reflection.md`.

A good submission demonstrates that the principles have made contact with reality. The grader is not looking for a re-statement of the principles' text; the grader is looking for whether you can recognize them in the wild.

---

## Homework 2 — Architect a workload and price it

**Estimated time:** 90 minutes.

You are designing the infrastructure for a small B2B SaaS launching in three months. The product:

- A web application serving ~500 daily active users at launch, projected to grow to ~10,000 daily active users by month 12.
- A small REST API serving the web app, ~200 requests per second peak, ~50 average.
- A relational database holding customer data — projected ~50 GB at launch, growing to ~500 GB by month 12.
- An asynchronous job queue for sending email, processing exports, generating reports — ~10,000 jobs per day at launch.
- A blob store for user-uploaded files — projected ~100 GB at launch, growing to ~2 TB by month 12.

You are asked to pick a cloud (AWS, GCP, or Azure), design the architecture, and price it for month 1 and month 12.

Required deliverables:

1. **A short architecture description** (~500 words). Name every cloud service you will use. Justify the choice of compute platform (Kubernetes, serverless, traditional VMs), the choice of database (managed Postgres, MySQL, Aurora, Cloud SQL, etc.), and the choice of job queue (SQS, Cloud Tasks, RabbitMQ on Kubernetes, etc.).

2. **A pricing calculator URL** for month-1 spend. Use the AWS Pricing Calculator at <https://calculator.aws/> or the GCP Pricing Calculator at <https://cloud.google.com/products/calculator>. Save the share URL.

3. **A pricing calculator URL** for month-12 spend. Same calculator, updated for the projected growth. Save the share URL.

4. **A cost analysis** (~300 words). Identify the three largest line items in month 1. Identify the three largest in month 12. Identify the line item with the highest growth between month 1 and month 12. Reflect on whether the architecture you chose is the right shape for the projected growth, or whether you would re-architect at some point during year 1.

Submit as a Markdown document named `homework-architecture.md` with the calculator URLs inline.

The grader is looking for: an architecture that is plausible (could actually launch and serve customers), a pricing exercise that engaged seriously with the calculator (not a one-line item estimate), and a cost analysis that demonstrates you understand which numbers will scale alarmingly and which will not.

---

## Homework 3 — A 5-minute talk

**Estimated time:** 60 minutes (drafting and rehearsing).

Prepare a 5-minute talk you could deliver to a non-engineering audience (CFO, finance team, product manager) titled "What is FinOps and why is it not just accounting?". The talk must:

- Define FinOps in plain language.
- Name the three personas in the FinOps Foundation framework and explain why all three matter.
- Explain unit economics in non-technical terms (the cost-per-request, cost-per-active-user idea), with an analogy a finance person would find natural.
- Make the case for showback before chargeback.
- Close with one concrete next step the listener can take in their organization.

Submit the talk in two forms:

1. **A speaker outline** — bullet points, 1 to 2 pages. Submit as `homework-talk-outline.md`.
2. **A speaker script** — the words you would actually say, prose, ~700 to 900 words. Submit as `homework-talk-script.md`.

You do not need to record the talk. The exercise is in the drafting; the discipline of writing for a non-engineering audience is the discipline of converting technical insight into business insight. A senior engineer who cannot make this case in 5 minutes to a CFO is a senior engineer whose technical insights are stranded.

The grader is looking for: plain language, an absence of jargon, a clear ask at the end, and evidence that the talk was actually rehearsed (the script should sound spoken, not written).

---

## A note on AI assistance

You may use a language model (Claude, GPT, Gemini, etc.) to brainstorm and revise. You may not submit verbatim model output as your own work. The discipline of these homework items is in the thinking; the model is a sparring partner, not a ghostwriter.

If you use a model substantively, disclose it at the bottom of the relevant submission: "I used [model name] to brainstorm the structure of the talk; the script is my own writing." Disclosure does not lose points; non-disclosure does, if detected.

---

## Submission

Submit all three homework documents as a single archive or a folder in your homework repo. The grader will read in this order:

1. `finops-principles-reflection.md`
2. `homework-architecture.md`
3. `homework-talk-outline.md`
4. `homework-talk-script.md`

Allocate 60 minutes for first-pass drafting, then leave 12 to 24 hours before re-reading. The second-pass edit is where the homework becomes good.
