# Week 5 — Terraform Fundamentals

> *Infrastructure is a graph. Terraform is the only tool that ever asked the question that way and then answered it. Everything else in this track is downstream of that.*

Welcome to Week 5 of **C15 · Crunch DevOps**. Week 1 told you what a container is. Week 2 made you build one well. Week 3 wired several of them together. Week 4 made that stack ship itself to a registry on every merge. Week 5 is where the image you have been building stops running on your laptop and starts running on a server that did not exist on Monday and will not exist next Sunday unless `terraform apply` says so.

We focus this week on **Terraform 1.9+** the way you will use it on a real team. Not the "hello-world `null_resource`" tutorial that runs `local-exec` and tells you IaC is easy — but the actual machine you will live inside for the rest of your career: providers, resources, the state file, modules, variables, outputs, remote backends, the two-phase bootstrap, and the rules of taste that separate a `terraform plan` you trust from one you ignore. By Sunday you will have provisioned a real public-facing app on DigitalOcean for about $10 a month — droplet, managed Postgres, domain, TLS — entirely in Terraform, in a git repo, with remote state, with a `terraform destroy` that actually returns the bill to zero.

Week 4's mini-project gave you a green CI build that pushes images to GHCR every merge. Week 5's mini-project gives you a **`terraform apply` away** from those images running on a URL that resolves on the public internet. That is the difference between "we ship images" and "we run a service."

---

## Learning objectives

By the end of this week, you will be able to:

- **Read** any `*.tf` file in a real repo and explain, line by line, the `terraform` block (required version, required providers, backend), every `provider` block (alias, region, credentials source), every `resource` block (type, name, arguments, lifecycle), every `data` block, every `variable` and `output`, and predict what `terraform plan` would print if you changed any one of them.
- **Write** a small Terraform configuration that provisions a real cloud resource (a DigitalOcean droplet, an AWS S3 bucket, a Cloudflare DNS record), in under fifty lines, with `terraform init && terraform apply` returning cleanly and `terraform destroy` returning the resource count to zero.
- **Distinguish** the three Terraform execution modes you will actually use (`plan`, `apply`, `destroy`), the two state operations you will reach for (`terraform state list`, `terraform state mv`), and the one operation you should rarely reach for and always with a backup (`terraform state rm`).
- **Apply** the principle of least surprise to every configuration: explicit `required_version`, explicit `required_providers` with version constraints, explicit `backend` block, no `latest` provider versions, no resources outside modules in any non-toy project.
- **Author** a small module with `variables.tf`, `main.tf`, `outputs.tf`, and `versions.tf`; consume it from a root module with `source = "./modules/..."`; understand when to publish to the Terraform Registry and when to keep it private.
- **Configure** a remote state backend (DigitalOcean Spaces in this week's setup; S3 in the homework) with state locking and encryption, and execute the two-phase bootstrap (local state → create backend → migrate state) without losing a single resource.
- **Diagnose** a drifted plan, a tainted resource, a state file out of sync with reality, and the three flavors of provider error you will see in the first month (auth failure, rate limit, transient API 5xx).
- **Defend** the choice of Terraform vs OpenTofu, of a monolithic root vs split roots per environment, of remote state vs local state, and of `count` vs `for_each` for a given resource shape.

---

## Prerequisites

This week assumes you have completed **Weeks 1, 2, 3, and 4 of C15** and pushed all four mini-projects to public GitHub repos. Specifically:

- You have a GitHub account, a `gh` CLI install (`brew install gh` / `apt install gh`), and `gh auth status` returns `Logged in`.
- You can build a multi-stage Dockerfile and bring up a `compose.yaml` stack locally without referring to last week's notes.
- You have a working CI pipeline that pushes an image to `ghcr.io/<you>/<repo>` on every merge to `main`.
- You can SSH into a Linux server (C14 territory) and read `/var/log` without panicking.
- You have a payment method available for a small cloud bill (~$10 for the week; we destroy at the end).

We use **Terraform 1.9+** (the current stable major as of 2026 is 1.13; everything in this week's notes works on 1.9 and later) and the **DigitalOcean provider 2.40+**. The two things that recently changed and matter this week: (a) **`terraform test` is now a first-class command** since 1.6 and is the right place for module-level assertions; (b) **`moved` blocks** since 1.1 are how you refactor resource addresses without `terraform state mv` — they belong in the same commit as the rename.

If you prefer OpenTofu (the GPL fork), every command in this week's material is identical: replace `terraform` with `tofu` and the `.terraform.lock.hcl` filename with `.terraform.lock.hcl` (unchanged). The lecture notes call out the two small places where the two tools diverge in 2026.

---

## Topics covered

- The Terraform execution model: configuration → state → plan → apply. Where each artifact lives, what is on disk, what is in memory, what is in the backend.
- The `terraform` block: `required_version`, `required_providers`, `backend`. Why every non-toy module needs all three.
- Providers: the `provider` block, `alias`, `for_each` providers (Terraform 1.5+), credentials hierarchies (env var → shared file → backend role).
- Resources: the `resource` block, the `count` vs `for_each` choice, `depends_on`, `lifecycle { create_before_destroy, prevent_destroy, ignore_changes, replace_triggered_by }`.
- Data sources: `data "..." "..."` blocks, when to read vs hardcode, the implicit ordering they introduce.
- Variables: `variable` blocks, types (`string`, `number`, `bool`, `list`, `map`, `object`, `tuple`), validation, sensitivity, defaults vs required.
- Outputs: `output` blocks, sensitivity, the `terraform output -json` shape that other tools consume.
- Locals: the `locals` block, when a `local` is a smell (a value used in exactly one place) and when it is the right tool (a value derived from three variables and used in seven resources).
- The state file: what it contains, why it is sensitive, the difference between configuration and state, the rules for reading and writing it.
- Remote state: the `backend` block, state locking, encryption at rest, the two-phase bootstrap pattern.
- Modules: the `module` block, the `source` attribute (local path, Git, registry), the four standard files (`main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`), versioning a module.
- The Terraform Registry: published modules, the difference between official and community modules, how to read a module's `README.md` and `variables.tf` to know whether to use it.
- Workspaces: the built-in workspace feature, why most teams do not use it, and what they use instead (directory-per-environment).
- `terraform fmt`, `terraform validate`, `terraform plan -out=plan.tfplan`, `terraform apply plan.tfplan` — the four-command discipline that turns "I ran terraform" into "I shipped infrastructure."
- IaC anti-patterns: `local-exec` for anything that should be a resource, `null_resource` as a hammer, secrets in `.tf` files, `terraform.tfstate` in git, `latest` provider versions, "one giant root module" syndrome.

---

## Weekly schedule

The schedule below adds up to approximately **36 hours**. As always, total is what matters.

| Day       | Focus                                                       | Lectures | Exercises | Challenges | Quiz/Read | Homework | Mini-Project | Self-Study | Daily Total |
|-----------|-------------------------------------------------------------|---------:|----------:|-----------:|----------:|---------:|-------------:|-----------:|------------:|
| Monday    | Providers, resources, the state file (Lecture 1)            |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Tuesday   | Modules, variables, outputs (Lecture 2)                     |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Wednesday | Modules and variables in anger (Exercise 2)                 |    1h    |    2h     |     1h     |    0.5h   |   1h     |     1h       |    0.5h    |     7h      |
| Thursday  | Remote state, locking, two-phase bootstrap (Exercise 3)     |    1h    |    1h     |     1h     |    0.5h   |   1h     |     2h       |    0.5h    |     7h      |
| Friday    | Mini-project — droplet, Postgres, domain, TLS               |    0h    |    0h     |     1h     |    0.5h   |   1h     |     3h       |    0.5h    |     6h      |
| Saturday  | Challenge — deploy a real app on a real VPS                 |    0h    |    0h     |     1h     |    0h     |   1h     |     1h       |    0h      |     3h      |
| Sunday    | Quiz, write the README, destroy and reconcile the bill      |    0h    |    0h     |     0h     |    0.5h   |   0h     |     0h       |    0h      |     0.5h    |
| **Total** |                                                             | **6h**   | **7h**    | **4h**     | **3h**    | **6h**   | **7h**       | **2.5h**   | **35.5h**   |

---

## How to navigate this week

| File | What's inside |
|------|---------------|
| [README.md](./README.md) | This overview (you are here) |
| [resources.md](./resources.md) | Curated readings: Terraform docs, HashiCorp Learn free tutorials, OpenTofu, the registry |
| [lecture-notes/01-providers-resources-state.md](./lecture-notes/01-providers-resources-state.md) | The Terraform execution model, the `terraform` block, providers, resources, the state file |
| [lecture-notes/02-modules-variables-outputs.md](./lecture-notes/02-modules-variables-outputs.md) | Modules, variables, outputs, locals, the two-phase bootstrap, remote state |
| [exercises/README.md](./exercises/README.md) | Index of hands-on drills |
| [exercises/exercise-01-first-resource.md](./exercises/exercise-01-first-resource.md) | Your first real resource on DigitalOcean |
| [exercises/exercise-02-modules-and-vars.md](./exercises/exercise-02-modules-and-vars.md) | Refactor a flat root into a module with variables and outputs |
| [exercises/exercise-03-remote-state.md](./exercises/exercise-03-remote-state.md) | DigitalOcean Spaces backend, the two-phase bootstrap, state locking |
| [challenges/README.md](./challenges/README.md) | Index of weekly challenges |
| [challenges/challenge-01-deploy-a-real-app-on-vps.md](./challenges/challenge-01-deploy-a-real-app-on-vps.md) | Deploy your Week 4 image on a real VPS in Terraform |
| [quiz.md](./quiz.md) | 10 multiple-choice questions |
| [homework.md](./homework.md) | Six practice problems |
| [mini-project/README.md](./mini-project/README.md) | Droplet + managed Postgres + domain + TLS on DigitalOcean, fully in Terraform, ~$10/mo |

---

## A note on cost

This is the first week of C15 where you spend real money. The mini-project costs about **$10/month** if you leave it running, and we will leave it running through Week 6 (which is GitOps on top of this week's infrastructure). The cost breakdown:

```
┌─────────────────────────────────────────────────────┐
│  COST PANEL — Week 5 mini-project (DigitalOcean)    │
│                                                     │
│  Droplet (s-1vcpu-1gb, NYC3)         $6.00 / mo     │
│  Managed Postgres (db-s-1vcpu-1gb)   $15.00 / mo    │
│  Domain (we use a free .tk or your   $0.00 / mo     │
│    existing domain in DNS-only mode)                │
│  Spaces (1 GB, for remote state)     $5.00 / mo     │
│  TLS (Let's Encrypt via DO)          $0.00 / mo     │
│                                                     │
│  Subtotal:                           $26.00 / mo    │
│  Prorated for 14 days (W5+W6):       ~$12.00        │
└─────────────────────────────────────────────────────┘
```

The honest number is closer to $12 over the two-week run, not $10. The smaller Postgres tier (`db-s-1vcpu-1gb`) is $15/month, which is the cheapest managed Postgres on DigitalOcean as of 2026. If $12 is too much, the homework includes an "everything on one droplet" variant that costs $6/month flat — same Terraform shape, Postgres in a container on the droplet instead of a managed service. You learn the same things; you just do not learn what a managed database costs.

**Destroy at the end of the week if you are not continuing to Week 6 immediately.** Set a calendar reminder. `terraform destroy` returns the bill to zero in about ninety seconds, and the only state you will have lost is the toy data we seed for the project. The reminder is your friend; the bill that arrives because you forgot is not.

---

## Stretch goals

If you finish early and want to push further:

- Read the entire **Terraform CLI configuration reference** at <https://developer.hashicorp.com/terraform/cli/config/config-file>. It is shorter than it looks, and once you have read it you stop guessing what `TF_CLI_ARGS_apply` does and where credentials really live.
- Rewrite one of your existing `null_resource` blocks (you have one, even if you do not remember writing it) as a proper resource. Delete the `local-exec`. Confirm the configuration still converges.
- Read the source of the **DigitalOcean Terraform provider** at <https://github.com/digitalocean/terraform-provider-digitalocean> — start with `digitalocean/resource_digitalocean_droplet.go`. You will see exactly what Terraform's "create then read then plan" lifecycle looks like in real Go code.
- Install **OpenTofu** alongside Terraform (`brew install opentofu`) and run this week's mini-project on both. Note the three places where the two tools diverge (the `tofu state` aliases, the encryption-at-rest defaults, the registry namespace). Decide which you prefer.
- Read the post-mortem of the **2022 GitLab Terraform state leak** at <https://about.gitlab.com/blog/2022/01/27/postmortem-on-gitlab-com-incident/> (the lesson is the same as every state-file incident: state contains secrets, treat it like a secret, encrypt at rest, never commit it). The blameless framing is worth reading even if you skip the technical content.

---

## Up next

Continue to **Week 6 — Immutable Infrastructure and GitOps** once you have shipped your Week 5 mini-project. Week 6 takes the infrastructure your Terraform configuration now provisions, and wires it into a GitOps loop: a change to the config repo triggers reconciliation automatically, you stop typing `terraform apply` by hand, and the state of the world matches the state in `main` because a controller said so.

---

*If you find errors in this material, please open an issue or send a PR. Future learners will thank you.*
