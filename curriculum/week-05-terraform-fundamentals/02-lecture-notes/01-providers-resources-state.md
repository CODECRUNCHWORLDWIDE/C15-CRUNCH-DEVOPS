# Lecture 1 — Providers, Resources, and the State File

> **Outcome:** You can read any `*.tf` file in a real repo, name every top-level block, every meta-argument worth knowing, every lifecycle option, and predict what `terraform plan` would print if any one of them were changed. You can write a small configuration that provisions a real resource on DigitalOcean, brings it up with `terraform apply`, and returns the bill to zero with `terraform destroy`. You can describe the state file in three sentences and explain why it is the most important and most under-respected file in the repo.

A Terraform configuration is a **declaration of a desired graph**. It says: *here are the cloud resources that should exist; here is how they relate; here is the provider I want you to use to talk to each cloud's API; here is where I want the record of what you did to live.* Terraform is not magic. Every block in the file maps to a deterministic operation: read the configuration, read the state, ask each provider what the real world looks like, compute the diff, print it as a plan, and — if you say `yes` — execute the diff. This lecture walks through the file shape you will read and write in the next eight weeks of the course, in roughly the order you will write the blocks in a real file.

We use **Terraform 1.9+** (the current stable major in 2026 is 1.13; everything in this week's notes works on 1.9 and later) and the **DigitalOcean provider 2.40+**. Two recent changes matter all week: (a) the `import` block (Terraform 1.5+) is now the right way to adopt an existing resource into state, replacing `terraform import` on the CLI; (b) the `moved` block (1.1+) is the right way to refactor resource addresses, replacing `terraform state mv`. Section 14 covers both.

---

## 1. The shortest correct configuration

Before any of the blocks, here is the smallest `main.tf` that actually does something useful:

```hcl
terraform {
  required_version = ">= 1.9.0"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.40"
    }
  }
}

provider "digitalocean" {
  token = var.do_token
}

variable "do_token" {
  type      = string
  sensitive = true
}

resource "digitalocean_ssh_key" "default" {
  name       = "c15-week-05"
  public_key = file("~/.ssh/id_ed25519.pub")
}
```

Four blocks. It will register your SSH key with DigitalOcean and nothing else. It is also incomplete in five different ways — no `backend`, no `output`, no `locals`, no `lifecycle`, no `tflint` lint pass — every one of which we will add over the next 400 lines. But it is the right starting point: every block you add from here is an **explicit choice** to make the configuration more reproducible, more testable, more reviewable, or easier to operate.

Note what is *not* in that file: no `terraform.tfstate` (Terraform creates it on the first `apply`), no `.terraform/` directory (created by `terraform init`), no `.terraform.lock.hcl` (created and updated by `terraform init`). Each one of those is an artifact of the run, not of the configuration. The configuration is the four blocks above; everything else is what Terraform produces when it executes the configuration.

---

## 2. Where these files live, and what Terraform does with them

A Terraform configuration lives in a directory. Every `.tf` file in that directory is part of the same configuration: Terraform concatenates them at parse time. The filenames are convention, not contract:

| File | What convention says it contains |
|------|----------------------------------|
| `main.tf` | The primary resources and module calls |
| `variables.tf` | All `variable` blocks |
| `outputs.tf` | All `output` blocks |
| `versions.tf` | The `terraform` block (`required_version`, `required_providers`) |
| `providers.tf` | All `provider` blocks |
| `locals.tf` | All `locals` blocks (only if numerous) |
| `data.tf` | All `data` blocks (only if numerous) |

Terraform does not care about these names. You can put everything in `everything.tf` and it parses the same way. The convention exists for the humans reading the diff; please honor it. The one exception is `versions.tf` — when you publish a module, every other tool in the ecosystem (`terraform-docs`, `tflint`, `tfsec`) assumes the `terraform` block lives in that file.

A directory may have any number of `.tf` files, but they all share one namespace. You cannot declare `resource "digitalocean_droplet" "web"` in both `main.tf` and `extra.tf`; the second one is a parse error. The `.terraform/` directory and `terraform.tfstate` are produced by Terraform; the `.tfvars` files (covered in Lecture 2) hold variable values.

> **Status panel — configuration inventory**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  DIRECTORY: ~/c15/week-05/mini-project              │
> │                                                     │
> │  Files in config:    5                              │
> │  - versions.tf      terraform block, providers      │
> │  - providers.tf     provider config (DO, Cloudflare)│
> │  - variables.tf     7 variables, 3 sensitive        │
> │  - main.tf          1 module call, 2 data sources   │
> │  - outputs.tf       4 outputs                       │
> │                                                     │
> │  Files Terraform produces (gitignored):             │
> │  - .terraform/      provider plugins (~80 MB)       │
> │  - terraform.tfstate  (only on local backend)       │
> │                                                     │
> │  Files Terraform produces (commit):                 │
> │  - .terraform.lock.hcl  provider checksums          │
> └─────────────────────────────────────────────────────┘
> ```

---

## 3. The six top-level block types

A Terraform configuration has, at most, **six top-level block types you will use regularly**. There are more in the schema (`check`, `import`, `moved`, `removed`) but the six below cover 99% of real files:

| Block | What it declares |
|-------|------------------|
| `terraform` | Required CLI version, required providers, the state backend |
| `provider` | A configured provider instance (one per cloud, or one per alias) |
| `variable` | An input parameter to this module |
| `resource` | A managed cloud object Terraform should create / update / destroy |
| `data` | A read-only lookup against a provider |
| `output` | A value this module exposes to its caller (or to the CLI) |

There are also `locals` (a single block that defines named expressions), `module` (a call to another module — Lecture 2), and the meta blocks (`moved`, `import`, `removed`). We get to those in Lecture 2 and Section 14. The two HCL footguns to know about now: (a) **block labels are positional and quoted** — `resource "digitalocean_droplet" "web" { ... }` has two labels (the type, then the local name), both required; (b) **HCL does not have a `null` literal in resource arguments** — to omit an optional argument, leave the line out; to explicitly say "no value," use `null` (lowercase, unquoted, exactly once in your career).

---

## 4. The `terraform` block

```hcl
terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.40"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }

  backend "s3" {
    # configured in backend.hcl (Section 12)
  }
}
```

Three sub-blocks. They are not optional in any non-toy project, even though Terraform will not complain if you omit them.

### 4.1 `required_version`

A constraint on the Terraform CLI itself. Always set it. The right shape is `>= 1.9.0, < 2.0.0` — pin the major, set a floor on the minor and patch. If a teammate runs `terraform 1.8.5` against your module, Terraform refuses to plan rather than silently using a missing feature.

### 4.2 `required_providers`

A constraint on each provider, with two fields: `source` (the registry namespace, `<org>/<name>`) and `version` (a version constraint). The `~> 2.40` constraint means "any 2.40.x or 2.41.x or ..., but not 3.0.0" — the equivalent of `>= 2.40, < 3.0` for the major version. Terraform writes the resolved versions to `.terraform.lock.hcl`, which you **must commit**. The lock file pins every provider to an exact version and SHA256, which is what makes `terraform init` reproducible across teammates and CI runners.

### 4.3 `backend`

Where state lives. Default is `local` — `terraform.tfstate` in the current directory. We will switch to `s3` (with a DigitalOcean Spaces endpoint) in Lecture 2 Section 12 and Exercise 3. For now, know that the `backend` block has a special restriction: **it cannot reference variables**. The backend is resolved before variables are loaded, which is why the partial-configuration pattern (an empty `backend "s3" {}` block, plus a `-backend-config=backend.hcl` flag on `terraform init`) is the only way to parameterize a backend across environments.

---

## 5. The `provider` block

```hcl
provider "digitalocean" {
  token             = var.do_token
  spaces_access_id  = var.spaces_access_id
  spaces_secret_key = var.spaces_secret_key
}
```

A provider block configures one instance of a provider. The block label (`"digitalocean"`) is the provider's **local name**, which must match a key in `required_providers`. If you have two AWS accounts (a common shape), you use `alias`:

```hcl
provider "aws" {
  region = "us-east-1"
  alias  = "us"
}

provider "aws" {
  region = "eu-west-1"
  alias  = "eu"
}

resource "aws_s3_bucket" "logs_us" {
  provider = aws.us
  bucket   = "logs-us-${var.account_id}"
}
```

The `provider = aws.us` argument on the resource is how you select the aliased provider. Without it, the resource uses the unaliased (default) provider — if there is no default, Terraform errors out.

> **Credentials hierarchy.** Most providers resolve credentials in this order: (1) arguments on the `provider` block, (2) environment variables (`DIGITALOCEAN_TOKEN`, `AWS_ACCESS_KEY_ID`, etc.), (3) shared credentials files (`~/.aws/credentials`), (4) instance metadata (on cloud-hosted runners). The argument is the lowest-friction choice for local dev; environment variables are the right shape for CI; instance metadata is the right shape for a Terraform job running inside the cloud you are provisioning. **Never put a real token in `provider {}` arguments and commit it.**

---

## 6. The `variable` block

```hcl
variable "do_token" {
  description = "DigitalOcean API token with read/write scope"
  type        = string
  sensitive   = true
}

variable "region" {
  description = "DigitalOcean region slug (e.g. nyc3, fra1)"
  type        = string
  default     = "nyc3"

  validation {
    condition     = contains(["nyc1", "nyc3", "sfo3", "fra1", "ams3", "sgp1", "blr1", "lon1", "syd1", "tor1"], var.region)
    error_message = "region must be a valid DigitalOcean region slug."
  }
}

variable "droplet_size" {
  description = "DigitalOcean droplet size slug"
  type        = string
  default     = "s-1vcpu-1gb"
}
```

A `variable` block declares an **input** to this module. The four fields you will use:

- `description` — what this variable is, in one sentence. Show up in `terraform plan` output. Always fill it in.
- `type` — `string`, `number`, `bool`, `list(...)`, `map(...)`, `object({ ... })`, `tuple([...])`, `set(...)`, or `any`. Always declare a type; the deprecated implicit `string` default is a footgun.
- `default` — if present, the variable is optional; if absent, the variable is required at plan time.
- `sensitive` — if `true`, Terraform redacts the value in plan/apply output. Use it on every credential.

The `validation` block is the underappreciated feature: it lets you enforce a constraint at plan time, before any API call. The example above will refuse to plan if `region` is set to `nyc7`.

### 6.1 Where variables get their values

Terraform reads variables from, in increasing precedence:

1. Defaults in the `variable` block.
2. Environment variables: `TF_VAR_<name>` (so `TF_VAR_do_token` populates `var.do_token`).
3. `terraform.tfvars` (auto-loaded).
4. `*.auto.tfvars` (auto-loaded; alphabetical order).
5. `-var-file=<file>` flags (in order).
6. `-var '<name>=<value>'` flags (in order).

The right shape for a real project: secrets in environment variables (`export TF_VAR_do_token=$(...)`), non-secret configuration in a `dev.tfvars` / `prod.tfvars` file passed via `-var-file=`. We use this shape in Exercise 1.

---

## 7. The `resource` block

This is the block. Every other block exists to support this one.

```hcl
resource "digitalocean_droplet" "web" {
  name     = "web-${var.environment}-01"
  image    = "ubuntu-24-04-x64"
  region   = var.region
  size     = var.droplet_size
  ssh_keys = [digitalocean_ssh_key.default.id]

  user_data = templatefile("${path.module}/cloud-init.yaml", {
    image_ref = var.image_ref
    db_url    = var.db_url
  })

  tags = ["c15-week-05", var.environment]

  lifecycle {
    create_before_destroy = true
    ignore_changes        = [image]
  }
}
```

The block has two labels: the **type** (`digitalocean_droplet`) and the **local name** (`web`). Together they form the resource's address: `digitalocean_droplet.web`. That address is how you reference this resource from other resources, from outputs, and from the CLI (`terraform plan -target=digitalocean_droplet.web`).

### 7.1 Arguments

The arguments inside a `resource` block come from the provider's schema. The DigitalOcean provider's droplet resource has about thirty arguments; you set the ones you need. Required arguments are documented per resource; the rest have provider-side defaults. If you set an argument the provider does not recognize, Terraform errors at `validate` time. If you forget a required one, the error is the same.

### 7.2 The four `lifecycle` meta-arguments

Every resource block can have a `lifecycle` block with up to four arguments:

| Argument | What it does | When to use it |
|----------|--------------|----------------|
| `create_before_destroy = true` | When the resource must be replaced, create the new one first, then destroy the old. | When destroy-then-create would cause downtime (load balancers, DNS records). |
| `prevent_destroy = true` | Refuse to `terraform destroy` this resource until the lifecycle block is changed. | Production databases, the bucket that holds your state. |
| `ignore_changes = [<arg1>, <arg2>]` | Do not consider drift on these arguments when planning. | Arguments that an external tool (a deploy pipeline) modifies outside Terraform. |
| `replace_triggered_by = [<ref1>]` | Force this resource to be replaced when the referenced resource changes. | A droplet that should be replaced when its cloud-init template changes. |

The `ignore_changes = [image]` in the example above is the canonical shape for a droplet whose image is updated by your CI/CD pipeline outside Terraform: you tell Terraform to provision the initial image, but not to fight CI/CD on every plan.

### 7.3 `count` vs `for_each`

Two ways to create multiple instances of one resource:

```hcl
# count: one resource, indexed [0..N-1]
resource "digitalocean_droplet" "worker" {
  count    = var.worker_count
  name     = "worker-${count.index}"
  image    = "ubuntu-24-04-x64"
  region   = var.region
  size     = "s-1vcpu-2gb"
  ssh_keys = [digitalocean_ssh_key.default.id]
}

# for_each: one resource per key in a map or set
resource "digitalocean_droplet" "worker" {
  for_each = toset(["us-east", "eu-west", "ap-south"])
  name     = "worker-${each.key}"
  image    = "ubuntu-24-04-x64"
  region   = each.key == "us-east" ? "nyc3" : each.key == "eu-west" ? "fra1" : "blr1"
  size     = "s-1vcpu-2gb"
  ssh_keys = [digitalocean_ssh_key.default.id]
}
```

`count` is the right tool when the instances are interchangeable and you only care about the number. `for_each` is the right tool when each instance has a stable identity (a region, a tenant, a customer). The difference is operational: if you have `count = 3` and you remove the middle one, Terraform destroys instances 1 and 2 and recreates them with the new indices; if you have `for_each = toset(["a", "b", "c"])` and you remove `"b"`, Terraform destroys only `"b"`. Always reach for `for_each` first; only fall back to `count` when the instances have no natural key.

---

## 8. The `data` block

```hcl
data "digitalocean_image" "ubuntu_lts" {
  slug = "ubuntu-24-04-x64"
}

data "digitalocean_ssh_key" "existing" {
  name = "my-workstation"
}

resource "digitalocean_droplet" "web" {
  image    = data.digitalocean_image.ubuntu_lts.id
  ssh_keys = [data.digitalocean_ssh_key.existing.id]
  # ...
}
```

A `data` block is a **read-only lookup**: "give me the latest Ubuntu image ID," "give me the ID of the SSH key I uploaded last year." It runs at plan time, against the provider's API. It does not create or modify anything.

The rule for when to use a data source: when the value would otherwise be a hardcoded string in your configuration, and the source of truth is the cloud's API. The Ubuntu image slug rarely changes, but the underlying ID does, and the data source resolves the slug to the current ID every plan. The SSH key name is yours, but the ID is DigitalOcean's, and the data source closes that loop.

The implicit ordering a data source introduces: it runs before any resource that depends on it. If `resource.web.image` references `data.digitalocean_image.ubuntu_lts.id`, the data source runs first. This is usually what you want; it is occasionally what surprises you (when the data source's query depends on a resource that does not exist yet, you get a chicken-and-egg error and have to split into two applies).

---

## 9. The `output` block

```hcl
output "droplet_ipv4" {
  description = "Public IPv4 address of the web droplet"
  value       = digitalocean_droplet.web.ipv4_address
}

output "ssh_command" {
  description = "Ready-to-paste SSH command to reach the droplet"
  value       = "ssh root@${digitalocean_droplet.web.ipv4_address}"
}

output "db_url" {
  description = "Postgres connection string"
  value       = "postgres://${digitalocean_database_user.app.name}:${digitalocean_database_user.app.password}@${digitalocean_database_cluster.pg.host}:${digitalocean_database_cluster.pg.port}/${digitalocean_database_db.app.name}"
  sensitive   = true
}
```

Outputs serve three purposes:

1. **Print values to a human after apply.** `terraform apply` prints all outputs at the end.
2. **Expose values to other tools.** `terraform output -json` is consumed by everything from Ansible to a Makefile.
3. **Expose values from a child module to its parent.** A module that does not declare outputs is a module that cannot be used.

The `sensitive = true` flag is required when the output contains a secret. Terraform refuses to print sensitive values without it; the value is still in state, but it is not in the apply output.

---

## 10. The state file

This is the file that distinguishes Terraform from every shell-script-driven IaC tool you have used. Read this section twice.

`terraform.tfstate` is a JSON document that records, for every resource Terraform manages, three things: **the resource's address** (e.g. `digitalocean_droplet.web`), **the cloud provider's identifier for it** (e.g. droplet ID `423897123`), and **a snapshot of every attribute the provider returned the last time Terraform read or wrote it**. The state file is how Terraform turns a desired-graph specification into a deterministic set of API calls: it diffs the configuration against the state, computes a plan, and the plan only contains the changes needed to make state match configuration.

### 10.1 What is in the state file

A representative single-resource entry:

```json
{
  "resources": [
    {
      "mode": "managed",
      "type": "digitalocean_droplet",
      "name": "web",
      "provider": "provider[\"registry.terraform.io/digitalocean/digitalocean\"]",
      "instances": [
        {
          "schema_version": 1,
          "attributes": {
            "id": "423897123",
            "name": "web-prod-01",
            "image": "ubuntu-24-04-x64",
            "region": "nyc3",
            "size": "s-1vcpu-1gb",
            "ipv4_address": "157.245.110.42",
            "ipv4_address_private": "10.108.0.5",
            "...": "..."
          },
          "sensitive_attributes": []
        }
      ]
    }
  ]
}
```

Three takeaways:

1. **The state file contains every attribute the provider returned.** That includes the droplet's password if you set one, the database's connection string with embedded credentials, the private key of a generated SSH keypair. **State files are secrets.** Treat them like the secret they are.
2. **The state file's `instances` array is what `count` and `for_each` use to track identity.** Removing an instance does not delete the resource until the next plan-apply.
3. **The provider name and version are recorded.** If you change provider versions, Terraform may need to migrate state; the lock file pins the version that wrote the state, and `terraform init` handles the upgrade path.

### 10.2 Why the state file is sensitive

Re-read the previous paragraph. The state file contains secrets. It also contains the entire shape of your infrastructure, which is itself sensitive (it tells an attacker what to attack). The right shape:

- **Never commit `terraform.tfstate` to git.** Add it to `.gitignore` before your first `terraform apply`.
- **Encrypt it at rest.** The backends we use this week (DigitalOcean Spaces with server-side encryption; AWS S3 with SSE-S3 or SSE-KMS) do this for you. The default `local` backend does not.
- **Lock it during writes.** Two `terraform apply` runs against the same state file race in unpredictable ways. The `s3` backend uses DynamoDB for locking; the `gcs` backend uses native object locks; Terraform Cloud uses its own mutex.
- **Audit access to it.** Anyone who can read your state file can read your secrets.

### 10.3 The seven `terraform state` subcommands

You will reach for these in the field. Memorize the three at the top:

| Subcommand | What it does | When to use it |
|------------|--------------|----------------|
| `terraform state list` | Print every resource address in state. | First debug step on a misbehaving module. |
| `terraform state show <addr>` | Print every attribute of one resource as Terraform sees it. | "Why is plan saying this attribute drifted?" |
| `terraform state mv <src> <dst>` | Rename a resource's address in state. | Refactoring (prefer the `moved` block in 1.1+). |
| `terraform state rm <addr>` | Remove a resource from state without destroying it. | Adopted-then-disowned resources; rare. |
| `terraform state pull` | Print the entire state file to stdout. | Forensics; piped to `jq`. |
| `terraform state push <file>` | Replace the remote state with a local file. | Recovery from a corrupted remote; rare and dangerous. |
| `terraform state replace-provider <old> <new>` | Re-key state when the provider's source address changes. | The 2023 BSL relicense; OpenTofu migrations. |

The first three are 90% of what you will need. The last four are for situations where you should also be paged.

---

## 11. The plan-apply cycle in detail

```
┌──────────────┐    1. read .tf files
│ Configuration│ ───────────────────┐
└──────────────┘                    │
                                    ▼
                            ┌───────────────┐
                            │   terraform   │
                            │   internal    │
                            │   graph       │
                            └───────┬───────┘
                                    │
┌──────────────┐    2. read state   │
│  State file  │ ───────────────────┤
└──────────────┘                    │
                                    ▼
┌──────────────┐    3. refresh      ┌──────────┐
│   Provider   │ ◄──────────────────│  plan    │
│   APIs       │ ─── 4. real state ─►          │
└──────────────┘                    └────┬─────┘
                                         │
                                         ▼
                                ┌─────────────────┐
                                │  diff printed   │
                                │  on stdout      │
                                └────────┬────────┘
                                         │ 5. you say yes
                                         ▼
                                ┌─────────────────┐
                                │  apply: API     │
                                │  calls + state  │
                                │  writes         │
                                └─────────────────┘
```

Five phases:

1. **Parse.** Terraform reads every `.tf` file in the working directory, builds a graph from references, validates the schema.
2. **Read state.** Terraform reads the state file (local or remote) and loads the resource instances.
3. **Refresh.** For every resource in state, Terraform calls the provider's "read" API to get the current attributes. This is the slow phase. The `-refresh=false` flag skips it (do not use it for production plans).
4. **Diff.** Terraform compares configuration to refreshed state, produces a plan: create / update / replace / destroy for every resource.
5. **Apply.** If you confirm (or if you ran `terraform apply -auto-approve`), Terraform walks the plan and makes the API calls, writing each result back to state.

The plan-apply discipline that distinguishes "I ran terraform" from "I shipped infrastructure":

```bash
terraform fmt -recursive
terraform validate
terraform plan -out=plan.tfplan
# read the plan. read it twice.
terraform apply plan.tfplan
```

The `-out=plan.tfplan` saves the plan to a file. `terraform apply plan.tfplan` applies *exactly that plan*, not a freshly-computed one. This eliminates the race where the world changes between plan and apply. Every production deploy in the field uses this shape; every CI pipeline uses it. The two-step (plan, then approve, then apply-from-file) is the right shape for any change that matters.

---

## 12. The two-phase bootstrap

The chicken-and-egg of remote state: you want state in a cloud bucket, but you cannot use Terraform to create that bucket if Terraform needs the bucket to track the bucket.

The two-phase shape:

```
PHASE 1: bootstrap                PHASE 2: iterate
──────────────────────            ──────────────────
Local backend (default)           Remote backend (s3 → Spaces)
  └─ creates the Spaces bucket    State lives in the bucket
  └─ creates a state-lock table   Lock lives next to the state
  └─ terraform.tfstate on disk    No tfstate on local disk
  └─ commit nothing               Commit .terraform.lock.hcl
                                  Migrate phase-1 state into the bucket
```

The mechanics:

1. In a directory called `bootstrap/`, write a configuration with `backend "local" {}` (or omit the `backend` block). Create the Spaces bucket and the lock object. `terraform apply`. State file is local; you commit nothing.
2. In the real working directory, write your real configuration with `backend "s3" { ... }` pointing at the Spaces bucket the bootstrap created. `terraform init`. Terraform sees an existing local state in `bootstrap/` (no — different directory; you copy state in only if you want the bootstrap-created resources tracked here too, which you usually don't).
3. Every subsequent change to the real configuration runs against the remote backend.

The `bootstrap/` directory's own state lives on disk and on whichever workstation you ran it from. You almost never modify it; the bucket and lock table are extremely stable. The lecture in Lecture 2 Section 12 covers the exact backend block; Exercise 3 walks through the migration.

---

## 13. The `import` block (Terraform 1.5+)

When a resource already exists in your cloud account and you want Terraform to manage it without destroying and recreating it:

```hcl
import {
  to = digitalocean_droplet.legacy
  id = "423897123"
}

resource "digitalocean_droplet" "legacy" {
  name   = "legacy-web"
  image  = "ubuntu-22-04-x64"
  region = "nyc3"
  size   = "s-1vcpu-1gb"
  # ... the rest of the attributes, matching the existing droplet
}
```

On the next `terraform plan`, Terraform reads the existing droplet's attributes, writes them into state under the address `digitalocean_droplet.legacy`, and reports the plan as "no changes" (assuming your `resource` block matches the real droplet's configuration). If the block does not match, Terraform reports the differences as a plan, and the next apply will update the real droplet to match your configuration.

The `import` block is the 1.5+ replacement for `terraform import <addr> <id>` on the CLI. It is declarative, it lives in git, and it is reviewable.

---

## 14. The `moved` block (Terraform 1.1+)

When you rename a resource (the local name, not the cloud-side name):

```hcl
# Before:
resource "digitalocean_droplet" "web" { ... }

# After:
moved {
  from = digitalocean_droplet.web
  to   = digitalocean_droplet.frontend
}

resource "digitalocean_droplet" "frontend" { ... }
```

On the next `terraform plan`, Terraform sees the `moved` block and updates the state's address from `web` to `frontend` without destroying or recreating the droplet. It is the replacement for `terraform state mv` on the CLI; it is declarative, it lives in git, and it is reviewable.

You can delete the `moved` block once everyone on the team has run `terraform apply` at least once with it present. Many teams leave them in for two release cycles, then delete them in a "remove `moved` blocks" PR.

---

## 15. Anti-patterns

The patterns that distinguish Terraform from `terraform init && terraform apply`:

- **`local-exec` for things that should be a resource.** A `null_resource` with a `local-exec` that runs `aws s3 cp` is not Terraform; it is a shell script that pretends. If the provider has the resource, use the resource.
- **`null_resource` as a hammer.** `null_resource` exists for the genuine case where there is no provider resource. If you reach for it in the first month, you are using it wrong.
- **Secrets in `.tf` files.** Even gitignored. Use environment variables or a secrets manager and `data` blocks. Future-you will commit something they shouldn't.
- **`terraform.tfstate` in git.** The most common cause of state corruption in the wild. Add it to `.gitignore` on day one.
- **`latest` provider versions.** Pin to a major in `required_providers`. The lock file pins the patch. Unpinned providers will break your build the day a major version ships.
- **One giant root module.** A root with 300 resources will take ninety seconds to plan and you will stop reading the diff. Split by lifecycle (network rarely changes; apps change weekly).
- **`-target=` as a normal workflow.** The `-target` flag exists for emergencies. If you `apply -target` because the full plan is too slow, the problem is the module, not the flag.
- **`terraform refresh` as a fix.** `terraform refresh` is now `terraform plan -refresh-only` (since 1.0). It updates state from real-world; it does not change real-world. If you reach for it as a fix, the fix is somewhere else.

---

## What we covered

A Terraform configuration is a graph of `resource` and `data` blocks, configured by `variable` and `provider` blocks, with the contract pinned by the `terraform` block. The state file is a JSON snapshot of everything Terraform thinks the world looks like; it is sensitive and lives in a remote backend in any non-toy project. The plan-apply cycle is five phases and one discipline (`-out=plan.tfplan`). The 1.5+ `import` block and the 1.1+ `moved` block are the declarative replacements for state surgery.

Tomorrow's lecture takes this single-module configuration and decomposes it into modules, with the same six block types reused as variables and outputs across module boundaries. Then we wire it up to a real remote backend and bootstrap our way into a working setup we can iterate on for the rest of the week.

---

*Next: Lecture 2 — Modules, Variables, Outputs, and the Two-Phase Bootstrap.*
