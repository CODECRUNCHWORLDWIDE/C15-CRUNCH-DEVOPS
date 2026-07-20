# Week 5 — Resources

Every resource on this page is **free** and **publicly accessible**. No paywalled books. If a link 404s, please open an issue.

## Required reading (work it into your week)

- **Terraform — "What is Terraform?" and "Install Terraform"** — the two pages that finally make the model click. Read both before Monday's lecture: <https://developer.hashicorp.com/terraform/intro> and <https://developer.hashicorp.com/terraform/install>.
- **HashiCorp Learn — "Get Started with Terraform"** — the canonical free tutorial track. The DigitalOcean variant is the one we use this week: <https://developer.hashicorp.com/terraform/tutorials/digitalocean-get-started>. (If you prefer AWS, GCP, or Azure tracks, all are free and structurally identical.)
- **Terraform configuration language — "Files and Directories"** — the canonical reference for what `.tf`, `.tfvars`, `.terraform.lock.hcl`, and `.terraform/` actually are. Return to this page weekly for the rest of your career: <https://developer.hashicorp.com/terraform/language/files>.
- **Terraform state — "State Overview"** — read end to end before Tuesday. The whole tool only makes sense after this page: <https://developer.hashicorp.com/terraform/language/state>.
- **Terraform "Modules" tutorial track** — the free HashiCorp Learn track on modules. Five hours of content; do it in three: <https://developer.hashicorp.com/terraform/tutorials/modules>.

## The specs (skim, don't memorize)

- **The `terraform` block** — `required_version`, `required_providers`, `backend`, `cloud`. Everything you put at the top of a module: <https://developer.hashicorp.com/terraform/language/terraform>.
- **Resources reference** — the `resource` block, `count`, `for_each`, `depends_on`, the four `lifecycle` meta-arguments: <https://developer.hashicorp.com/terraform/language/resources>.
- **Data sources reference** — when to read vs hardcode, the implicit ordering data sources introduce: <https://developer.hashicorp.com/terraform/language/data-sources>.
- **Variables reference** — types, validation, sensitivity, the precedence rules for `.tfvars` files and environment variables: <https://developer.hashicorp.com/terraform/language/values/variables>.
- **Outputs reference** — `sensitive`, `precondition`, the JSON shape consumers see: <https://developer.hashicorp.com/terraform/language/values/outputs>.
- **Locals reference** — when to extract and when not to: <https://developer.hashicorp.com/terraform/language/values/locals>.
- **Functions reference** — the full standard library of built-in functions, indexed: <https://developer.hashicorp.com/terraform/language/functions>.
- **Backend configuration** — the list of supported backends and the shape of each: <https://developer.hashicorp.com/terraform/language/backend>.
- **Provider configuration** — `alias`, `for_each` (1.5+), credentials resolution order: <https://developer.hashicorp.com/terraform/language/providers/configuration>.

## Official tool docs

- **`terraform init`** — what gets downloaded, where it goes (`.terraform/`), the `-backend-config=` flag, the `-upgrade` flag and what it really does: <https://developer.hashicorp.com/terraform/cli/commands/init>.
- **`terraform plan`** — every flag worth knowing, the `-out=plan.tfplan` discipline, `-refresh-only` for state-only changes: <https://developer.hashicorp.com/terraform/cli/commands/plan>.
- **`terraform apply`** — applying a saved plan vs running plan-on-the-fly, `-auto-approve` and when it is wrong, `-replace=` to taint a resource: <https://developer.hashicorp.com/terraform/cli/commands/apply>.
- **`terraform state`** — `list`, `show`, `mv`, `rm`, `pull`, `push`. The seven subcommands that distinguish "I know Terraform" from "I have used Terraform": <https://developer.hashicorp.com/terraform/cli/commands/state>.
- **`terraform fmt`** — the formatter; run it on every save. The 2-space-indent convention is not optional: <https://developer.hashicorp.com/terraform/cli/commands/fmt>.
- **`terraform validate`** — static validation; fast, no API calls, runs in CI: <https://developer.hashicorp.com/terraform/cli/commands/validate>.
- **`terraform test`** (1.6+) — the first-class testing command, `.tftest.hcl` files, assertions: <https://developer.hashicorp.com/terraform/cli/commands/test>.
- **`terraform import`** — adopting an existing resource into state without recreating it; the `import` block (1.5+) is the modern shape: <https://developer.hashicorp.com/terraform/cli/import>.

## Free books, write-ups, and reference repos

- **"Terraform: Up & Running" — sample chapters** — Yevgeniy Brikman's canonical book. The first three chapters are free on his publisher's site and cover state, modules, and the file shape: <https://www.terraformupandrunning.com/>.
- **HashiCorp Learn — "Terraform Cloud" track** — even if you do not plan to use Terraform Cloud, the section on remote state, locking, and runs is the cleanest free explanation of why those things matter: <https://developer.hashicorp.com/terraform/tutorials/cloud>.
- **`terraform-aws-modules/`** — the most-used set of community modules on the registry. Reading their `variables.tf` and `outputs.tf` files is the fastest way to learn what "good" looks like: <https://github.com/terraform-aws-modules>.
- **`gruntwork-io/terragrunt`** — a thin wrapper over Terraform that solves the "DRY across environments" problem; you may or may not use it, but the README's framing of the problem is excellent: <https://github.com/gruntwork-io/terragrunt>.
- **OpenTofu — the GPL fork of Terraform** — the community-governed alternative since the 2023 BSL relicense. Same CLI, same HCL, mostly the same providers. Read the FAQ once: <https://opentofu.org/docs/intro/whats-new/>.
- **`hashicorp/terraform` source** — the reference implementation. Start with `internal/terraform/context_plan.go` to see what `terraform plan` really does: <https://github.com/hashicorp/terraform>.

## Talks and videos (free, no signup)

- **"Terraform: From Hello-World to Production" — Yevgeniy Brikman** (~45 min). The talk that became the book; the section on modules vs root configurations is the cleanest 10 minutes of teaching on this topic: <https://www.youtube.com/results?search_query=brikman+terraform+production>.
- **"State is the hardest problem in Terraform" — Anton Babenko** (~30 min). The talk that taught the industry how to think about state migrations: <https://www.youtube.com/results?search_query=anton+babenko+terraform+state>.
- **"OpenTofu in 2026" — Roni Frantchi** (~25 min). Where the fork is, where it diverges, when to consider switching: <https://www.youtube.com/results?search_query=opentofu+state+of+the+fork>.

## Open-source Terraform repos worth reading

You will learn more from one hour reading other people's Terraform than from three hours of tutorials. Pick one and just read it:

- **`hashicorp/terraform-provider-digitalocean` examples/** — the provider's own examples, organized by resource. Start with `examples/load_balancer/` and `examples/kubernetes/`: <https://github.com/digitalocean/terraform-provider-digitalocean/tree/main/examples>.
- **`terraform-aws-modules/terraform-aws-vpc`** — the most-downloaded module on the registry. Read its `main.tf` and you understand `for_each` properly: <https://github.com/terraform-aws-modules/terraform-aws-vpc>.
- **`cloudposse/terraform-null-label`** — a module that does one thing (compute resource names) and does it well. Read it for the discipline of a single-purpose module: <https://github.com/cloudposse/terraform-null-label>.
- **`gruntwork-io/terraform-aws-eks`** — a large, opinionated module that wraps a complex resource (EKS). Read its `variables.tf` to learn how to write good variable validation: <https://github.com/gruntwork-io/terraform-aws-eks>.
- **`oracle/terraform-oci-base`** — clear `versions.tf`, clear module composition, clear `README.md`. Different cloud, same shape: <https://github.com/oracle/terraform-oci-base>.

## DigitalOcean-specific (this week's cloud)

- **DigitalOcean Terraform provider docs** — every resource, every data source, every argument: <https://registry.terraform.io/providers/digitalocean/digitalocean/latest/docs>.
- **DigitalOcean — "Generating a Personal Access Token"** — how we authenticate Terraform to your account; takes 90 seconds: <https://docs.digitalocean.com/reference/api/create-personal-access-token/>.
- **DigitalOcean — "An Introduction to DigitalOcean Spaces"** — the S3-compatible object store we use for remote state: <https://docs.digitalocean.com/products/spaces/>.
- **DigitalOcean — "Managed Databases Quickstart"** — what the managed Postgres tier is, what it costs, what it gives you over a self-hosted Postgres on a droplet: <https://docs.digitalocean.com/products/databases/postgresql/quickstart/>.
- **DigitalOcean — "Cloud-init on Droplets"** — the `user_data` we pass to the droplet to bootstrap Docker and pull the image: <https://docs.digitalocean.com/products/droplets/how-to/provide-user-data/>.

## Backends in real life

- **AWS S3 backend** — the most-used backend; canonical for any AWS-shop Terraform: <https://developer.hashicorp.com/terraform/language/backend/s3>.
- **DigitalOcean Spaces backend** — uses the `s3` backend with `endpoint = "<region>.digitaloceanspaces.com"`; the configuration we use this week. Documented in the same `s3` backend page above.
- **Terraform Cloud / HCP Terraform** — the hosted backend with built-in locking, encryption, run history, and a UI. Free tier is generous (500 resources): <https://developer.hashicorp.com/terraform/cloud-docs>.
- **GCS backend** — Google Cloud Storage; the GCP-shop equivalent of S3: <https://developer.hashicorp.com/terraform/language/backend/gcs>.
- **Azure RM backend** — Azure Storage; the Azure-shop equivalent: <https://developer.hashicorp.com/terraform/language/backend/azurerm>.

## Tools you'll install this week

| Tool | Install | Purpose |
|------|---------|---------|
| `terraform` | `brew install terraform` or HashiCorp's binary (`terraform -version` must show 1.9+) | The IaC engine |
| `tofu` (optional) | `brew install opentofu` | The GPL fork; identical CLI |
| `tflint` | `brew install tflint` | Static linter for HCL; catches typos, deprecated syntax, provider-specific issues |
| `tfsec` | `brew install tfsec` | Security scanner for Terraform; catches "public S3 bucket" before plan does |
| `terraform-docs` | `brew install terraform-docs` | Auto-generates the README's variables and outputs tables from your `.tf` files |
| `doctl` | `brew install doctl` | The DigitalOcean CLI; we use it to mint the API token, verify resources, and tail droplet logs |

## Glossary cheat sheet

Keep this open in a tab.

| Term | Plain English |
|------|---------------|
| **Configuration** | The `.tf` files in a directory. What you want the world to look like. |
| **State** | The `terraform.tfstate` file (local or remote). What Terraform thinks the world looks like. |
| **Plan** | The diff: what Terraform would do to make the state match the configuration. |
| **Apply** | The act of executing the plan. The only command that changes anything. |
| **Module** | A directory of `.tf` files that can be called from another module via `module "name" { source = "..." }`. Every directory is a module; the directory you run `terraform` in is the **root module**. |
| **Provider** | A plugin that knows how to talk to one API (AWS, DO, Cloudflare, GitHub). Downloaded by `terraform init`. |
| **Resource** | A managed object: a droplet, a DNS record, an S3 bucket. `resource "type" "name" { ... }`. |
| **Data source** | A read-only lookup: "give me the latest Ubuntu image ID." `data "type" "name" { ... }`. |
| **Backend** | Where the state file lives. `local` (default), `s3`, `gcs`, `remote` (Terraform Cloud). |
| **Workspace** | A named instance of state inside one backend. Most teams use directories instead. |
| **Lock file** | `.terraform.lock.hcl`. Pins provider versions and checksums. Commit it. |
| **`required_version`** | Constraint on the Terraform CLI version a module supports. |
| **`required_providers`** | Constraint on each provider's version and source address. |
| **Drift** | When the real world has changed from what state says. `terraform plan` detects it. |
| **Taint / replace** | Marking a resource for destroy-then-create on the next apply. `terraform apply -replace=...`. |
| **`moved` block** | The 1.1+ way to refactor resource addresses without running `terraform state mv`. |
| **`import` block** | The 1.5+ way to adopt an existing resource into state declaratively. |
| **Remote state** | State stored in a backend (S3, GCS, Spaces, Terraform Cloud) instead of locally. |
| **State locking** | A mutex on the state file. Prevents two `apply`s from racing. DynamoDB on S3; native on most other backends. |

---

*If a link 404s, please [open an issue](https://github.com/CODE-CRUNCH-CLUB) so we can replace it.*
