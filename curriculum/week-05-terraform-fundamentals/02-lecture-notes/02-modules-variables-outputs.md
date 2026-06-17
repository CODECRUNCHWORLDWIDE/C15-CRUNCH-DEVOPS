# Lecture 2 — Modules, Variables, Outputs, and the Two-Phase Bootstrap

> **Outcome:** You can decompose a flat Terraform configuration into modules, design good variables (typed, validated, documented, with sensible defaults), expose good outputs (typed, documented, scoped for sensitivity), and bootstrap a remote backend so that state lives off your laptop. By the end of this lecture, you can read any module on the Terraform Registry and decide in five minutes whether to use it, fork it, or write your own.

Lecture 1 built one flat configuration in one directory. That is the right starting point and it is also where 80% of Terraform repos in the wild are stuck. The other 20% — the ones you can read in six months without crying — have factored their resources into **modules**, parameterized them with **variables**, exposed their contracts as **outputs**, and stored state **remotely** with locking and encryption. This lecture covers all four moves. It is the lecture that turns Terraform from "a tool I am running" into "a system I am operating."

We continue with **Terraform 1.9+** and the **DigitalOcean provider 2.40+**. The features this lecture leans on are: `for_each` on modules (1.0+), provider configurations passed to modules via `providers = { ... }`, the `optional()` modifier on object types (1.3+), and the `precondition`/`postcondition` blocks on `output` (1.2+). Section 12 (remote state) uses the `s3` backend pointed at DigitalOcean Spaces; the same pattern works on AWS S3 directly, on MinIO, on any S3-compatible store.

---

## 1. What a module actually is

A **module** is a directory of `.tf` files. That is the entire definition. Every Terraform configuration is a module: the directory you run `terraform` in is the **root module**, and any directory it references is a **child module**.

A child module is called from a parent with a `module` block:

```hcl
module "web" {
  source  = "./modules/web-droplet"
  version = "~> 1.0"  # only valid for registry sources

  region    = var.region
  image_ref = var.image_ref
  ssh_keys  = [digitalocean_ssh_key.default.id]
  db_url    = module.database.connection_string

  tags = ["c15-week-05", var.environment]
}
```

The module's `source` is where to find it. The arguments inside the block are the module's **inputs** — they map directly to the child module's `variable` blocks. The module's outputs are then accessible to the parent as `module.web.<output_name>`.

What a module is not:

- It is not a special file type. There is no `module.tf`.
- It is not a class or an object. Every call to a module creates a separate instance of every resource inside it; there is no shared state between calls.
- It is not free. Every module call costs a level of indirection in the plan output, a level of namespace in addresses, and a level of complexity in onboarding.

The right rule: extract a module the second time you would copy-paste the same five resources. Not the first; the first time, you do not yet know what the right boundary is. The second time, you do.

---

## 2. The four canonical module files

A well-formed module has four files. Other files (a `README.md`, an `examples/` directory, a `tests/` directory) are optional. The four files are not.

### 2.1 `versions.tf`

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
```

The `terraform` block. **A child module must not declare its own `backend`.** The root module owns the backend; child modules inherit it implicitly via the state file's tree structure.

### 2.2 `variables.tf`

```hcl
variable "region" {
  description = "DigitalOcean region slug"
  type        = string

  validation {
    condition     = can(regex("^[a-z]{3}[0-9]$", var.region))
    error_message = "region must be a three-letter, one-digit region slug (e.g. nyc3)."
  }
}

variable "image_ref" {
  description = "OCI image reference to run on the droplet (e.g. ghcr.io/me/app:v1.0.0)"
  type        = string
}

variable "ssh_keys" {
  description = "List of SSH key IDs to install on the droplet"
  type        = list(string)
}

variable "db_url" {
  description = "Postgres connection string"
  type        = string
  sensitive   = true
}

variable "tags" {
  description = "Tags to apply to all resources in this module"
  type        = list(string)
  default     = []
}

variable "droplet_size" {
  description = "DigitalOcean droplet size slug"
  type        = string
  default     = "s-1vcpu-1gb"
}
```

Every input the module takes. Every variable has a `description` and a `type`. Required variables have no `default`; optional variables have one. Sensitive variables are marked `sensitive = true`.

### 2.3 `main.tf`

The resources, data sources, and any local module calls. Whatever the module exists to manage.

### 2.4 `outputs.tf`

```hcl
output "droplet_id" {
  description = "DigitalOcean droplet ID"
  value       = digitalocean_droplet.this.id
}

output "ipv4_address" {
  description = "Public IPv4 address of the droplet"
  value       = digitalocean_droplet.this.ipv4_address
}

output "tags" {
  description = "Tags applied to all resources in this module"
  value       = var.tags
}
```

Every value the module exposes. The contract is "these are the values a caller can rely on; everything else is implementation detail." Treat outputs like a public API: do not break them in a minor version bump.

---

## 3. The `source` attribute

A module's `source` tells Terraform where to find it. Six shapes you will see:

| Shape | Example | When |
|-------|---------|------|
| Local path | `source = "./modules/web-droplet"` | Same repo, common case |
| Git over HTTPS | `source = "git::https://github.com/me/tf-modules.git//modules/web-droplet?ref=v1.2.0"` | Cross-repo, public or private |
| Git over SSH | `source = "git::git@github.com:me/tf-modules.git//modules/web-droplet?ref=v1.2.0"` | Cross-repo, private, SSH-keyed |
| Terraform Registry | `source = "terraform-aws-modules/vpc/aws"` and `version = "~> 5.0"` | Public, versioned, registry-hosted |
| HCP / private registry | `source = "app.terraform.io/<org>/<name>/<provider>"` and `version = "~> 1.0"` | Private, with the HCP / Enterprise stack |
| S3 / GCS / HTTP archive | `source = "s3::https://s3.amazonaws.com/.../module.zip"` | Air-gapped, vendored modules |

The two rules of taste:

1. **Always pin the version.** For local paths, that means "I trust this repo's git history." For everything else, that means a `version = "~> 1.2"` constraint (registry) or a `?ref=v1.2.0` argument (git) — never `?ref=main`, never an unconstrained registry version.
2. **Prefer local paths inside a repo, and registry/git sources across repos.** A team can refactor a local module by typing; a published module is a release.

---

## 4. Passing providers to modules

By default, a child module inherits the providers of its parent. When the parent has multiple aliased providers, you pass them explicitly:

```hcl
provider "aws" {
  region = "us-east-1"
  alias  = "us"
}

provider "aws" {
  region = "eu-west-1"
  alias  = "eu"
}

module "logs_us" {
  source = "./modules/logs-bucket"
  providers = {
    aws = aws.us
  }
}

module "logs_eu" {
  source = "./modules/logs-bucket"
  providers = {
    aws = aws.eu
  }
}
```

The child module declares `required_providers` in its `versions.tf` (just `aws`, no alias) and uses `aws_*` resources unqualified. The parent maps the aliased provider to the unqualified name. This is how you create the same set of resources across two regions in two parallel module calls.

A note on `for_each` providers (Terraform 1.5+): you can now write `for_each = var.regions` on a `provider` block, which gives you one provider per region without the alias-explosion of the pre-1.5 idiom. The module-side `providers =` mapping uses `aws.us` style references regardless of how the provider was declared.

---

## 5. The `count` and `for_each` meta-arguments on modules

A module can be called multiple times with `count` or `for_each`, just like a resource:

```hcl
module "worker_droplet" {
  for_each = toset(["us", "eu", "ap"])
  source   = "./modules/web-droplet"

  region     = each.key == "us" ? "nyc3" : each.key == "eu" ? "fra1" : "blr1"
  image_ref  = var.image_ref
  ssh_keys   = [digitalocean_ssh_key.default.id]
  db_url     = var.db_url
  tags       = ["worker", each.key]
}

output "worker_ips" {
  value = { for k, m in module.worker_droplet : k => m.ipv4_address }
}
```

The `for_each` on a module makes every resource inside that module instance get a `[us]`, `[eu]`, or `[ap]` suffix in its state address. The output above gathers each instance's `ipv4_address` into a map. The same rules from Lecture 1 apply: `for_each` over `count` unless the instances are truly interchangeable.

---

## 6. Designing good variables

The marks of a good variable:

1. **It has a `description`.** "What is this variable, in one sentence." If you cannot write a one-sentence description, the variable is wrong (it is doing two things or no things).
2. **It has a `type`.** Always. Even when the default would be `string`. Future-you reading the plan will thank present-you.
3. **It has a sensible default — or no default at all.** A default that "almost always works" is a footgun: the one team that needed to override it will not know they were supposed to. A required variable says "the caller must think about this." A default says "the caller may rely on this."
4. **It has a `validation` block where the type does not fully constrain the value.** A region slug is a string; the set of valid region slugs is small and known. Validate it.
5. **It is `sensitive = true` if it carries a secret.** Even if you do not think it will end up in an output, mark it. Terraform propagates sensitivity through expressions automatically; the only way to lose it is to start without it.

The marks of a bad variable:

- `variable "config" { type = any }`. The `any` type is an escape hatch; in a module, it is a smell. Use a typed `object({ ... })`.
- `variable "enabled" { type = bool; default = true }` paired with `count = var.enabled ? 1 : 0`. Two patterns are wrong here: the `enabled` flag (use module composition instead) and the `count` pattern (always reach for `for_each`).
- A variable named `cidr` with no validation. A `cidr` that should be `/16` and arrives as `/32` will compile and break in production. Validate at plan time.

### 6.1 Complex types

```hcl
variable "ingress_rules" {
  description = "Firewall ingress rules for the droplet"
  type = list(object({
    protocol         = string
    port_range       = string
    source_addresses = list(string)
    description      = optional(string, "")
  }))
  default = [
    {
      protocol         = "tcp"
      port_range       = "22"
      source_addresses = ["0.0.0.0/0", "::/0"]
      description      = "SSH"
    },
    {
      protocol         = "tcp"
      port_range       = "443"
      source_addresses = ["0.0.0.0/0", "::/0"]
      description      = "HTTPS"
    }
  ]
}
```

Three patterns to take from this:

- **`list(object({ ... }))` is the most useful complex type.** It models a table of records, which most cloud APIs use.
- **`optional(<type>, <default>)`** (Terraform 1.3+) is how you make a field in an object type optional. Use it instead of duplicating the variable.
- **Defaults can be complex.** A default that is itself a list of objects works; reach for it when there is a "reasonable starting point" the caller can override.

---

## 7. Designing good outputs

Outputs are the module's public API. The marks of a good output:

1. **It has a `description`.** Same rule as variables.
2. **It is named for what it is, not how it is computed.** `ipv4_address`, not `droplet_attribute_ipv4`. The caller does not care that you got it from `digitalocean_droplet.this.ipv4_address`.
3. **It is `sensitive = true` if its value carries a secret.** The `db_url` output above is sensitive. The `droplet_id` is not.
4. **It uses `precondition` / `postcondition` when there is an invariant worth enforcing.** (Terraform 1.2+.)

```hcl
output "droplet_ipv4" {
  description = "Public IPv4 address of the web droplet"
  value       = digitalocean_droplet.this.ipv4_address

  precondition {
    condition     = digitalocean_droplet.this.ipv4_address != ""
    error_message = "droplet did not receive a public IPv4 address; check droplet networking."
  }
}
```

The `precondition` block on an output runs at plan time. If it fails, the plan fails. This is how you encode invariants in your module that go beyond Terraform's type system — "this droplet should always have a public IPv4," "this database should always be in the same region as its droplet."

---

## 8. Locals: when to extract, when not to

```hcl
locals {
  name_prefix = "${var.environment}-${var.application}"

  common_tags = concat(
    var.tags,
    ["env:${var.environment}", "app:${var.application}", "managed-by:terraform"]
  )

  droplet_user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    image_ref   = var.image_ref
    db_url      = var.db_url
    log_drain   = var.log_drain
    name_prefix = local.name_prefix
  })
}
```

A `locals` block defines named expressions. The rule for when to extract:

- **A local is the right tool when a value is computed once and used in two or more places.** The `common_tags` above is used on every resource in the module.
- **A local is a smell when a value is used once.** Inlining the expression is clearer than naming it.
- **A local is the right tool when a complex expression has a name worth caring about.** `droplet_user_data` is the rendered cloud-init template; naming it makes the resource block that consumes it readable.

Locals also let you reference each other (one local can use another, as `local.name_prefix` does above). What they cannot do: be referenced from outside the module. If you want a parent module to consume a value, it is an `output`, not a `local`.

---

## 9. The `templatefile` function and cloud-init

The 70% of "I need to do something on the droplet right after it boots" cases are best handled with cloud-init. Cloud-init is a YAML file that Ubuntu (and most other distros) reads on first boot. Terraform renders it via the `templatefile` function:

`modules/web-droplet/cloud-init.yaml.tftpl`:

```yaml
#cloud-config
package_update: true
package_upgrade: true
packages:
  - docker.io
  - docker-compose-plugin
  - postgresql-client-16

write_files:
  - path: /etc/systemd/system/app.service
    content: |
      [Unit]
      Description=app
      After=docker.service
      Requires=docker.service

      [Service]
      Restart=always
      ExecStartPre=-/usr/bin/docker stop app
      ExecStartPre=-/usr/bin/docker rm app
      ExecStartPre=/usr/bin/docker pull ${image_ref}
      ExecStart=/usr/bin/docker run --rm --name app \
        -p 80:8000 \
        -e DATABASE_URL='${db_url}' \
        ${image_ref}

      [Install]
      WantedBy=multi-user.target

runcmd:
  - systemctl daemon-reload
  - systemctl enable app.service
  - systemctl start app.service
```

Three patterns to take from this:

- **`${image_ref}` and `${db_url}` are Terraform template interpolations.** They are replaced before cloud-init ever sees the file. The droplet's cloud-init runtime sees the resolved values.
- **The `.tftpl` extension is convention.** Terraform does not care about the extension; the convention helps editors (VS Code's Terraform plugin highlights it correctly).
- **Never put a real secret into a cloud-init file via `templatefile` if you can avoid it.** The rendered file is in the droplet's metadata, which is readable by the droplet's user. For real secrets, use a secrets manager and pull at boot, not bake into user data.

---

## 10. Designing a small module: `web-droplet`

Pulling everything from the previous nine sections together, here is the shape of the `web-droplet` module we use in this week's mini-project.

`modules/web-droplet/versions.tf`:

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
```

`modules/web-droplet/variables.tf`: seven variables — `region`, `size`, `image_ref`, `ssh_key_ids`, `db_url`, `name_prefix`, `tags`. Five required, two with defaults. `db_url` is sensitive.

`modules/web-droplet/main.tf`:

```hcl
locals {
  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    image_ref = var.image_ref
    db_url    = var.db_url
  })
}

resource "digitalocean_droplet" "this" {
  name      = "${var.name_prefix}-web"
  image     = "ubuntu-24-04-x64"
  region    = var.region
  size      = var.size
  ssh_keys  = var.ssh_key_ids
  user_data = local.user_data
  tags      = var.tags

  lifecycle {
    create_before_destroy = true
    ignore_changes        = [image]
  }
}

resource "digitalocean_firewall" "this" {
  name        = "${var.name_prefix}-web-fw"
  droplet_ids = [digitalocean_droplet.this.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}
```

`modules/web-droplet/outputs.tf`: three outputs — `droplet_id`, `ipv4_address`, `firewall_id`. None sensitive.

That is the module. About 80 lines of HCL. It does one thing: provision a droplet with a sensible firewall, running an OCI image fetched from a registry, talking to an external database. The root module that calls it is responsible for the database, the DNS records, and the TLS certificate; the `web-droplet` module is not.

---

## 11. Module versioning

If you publish a module (or share it across repos via git), version it.

The shape:

```bash
# in the module's repo
git tag -a v1.2.0 -m "feat: support optional reserved IP"
git push origin v1.2.0
```

Callers reference the version:

```hcl
module "web" {
  source  = "git::https://github.com/me/tf-modules.git//modules/web-droplet?ref=v1.2.0"
  # ...
}
```

The rules of semantic versioning apply to modules:

- **MAJOR (`v2.0.0`).** A breaking change to an input or output. Removing a variable; renaming an output; changing a variable's type in a way that breaks callers.
- **MINOR (`v1.3.0`).** A new feature. Adding an optional variable (with a default); adding an output; adding a resource that does not change existing resources.
- **PATCH (`v1.2.1`).** A bug fix or internal refactor with no caller-visible behavior change.

The `version = "~> 1.2"` constraint on a registry module is the semver shape: "any 1.x where x >= 2." When you bump to 2.0, callers must explicitly opt in.

---

## 12. Remote state in detail

Lecture 1 covered the state file. This section covers the **backend** that stores it.

The default backend is `local`: `terraform.tfstate` in the working directory. It works for solo learning; it fails everything else (no locking, no encryption at rest, no team sharing). The right shape for any real project is a **remote backend** — a cloud bucket (S3, GCS, Spaces, ABS) plus a lock mechanism.

### 12.1 The `s3` backend pointed at DigitalOcean Spaces

DigitalOcean Spaces is S3-compatible. The `s3` backend works against it with a couple of arguments to override the endpoint:

```hcl
terraform {
  backend "s3" {
    bucket                      = "c15-week-05-tfstate-jeanstephane"
    key                         = "mini-project/terraform.tfstate"
    region                      = "us-east-1"   # required by SDK; ignored by Spaces
    endpoints                   = { s3 = "https://nyc3.digitaloceanspaces.com" }
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    use_path_style              = true
  }
}
```

The seven `skip_*` and `use_path_style` arguments are how you tell the AWS S3 SDK to behave against a non-AWS S3. Yes, it is seven lines of "no, really, this is not AWS." Yes, it is annoying. Yes, it works.

State locking on a Spaces backend: as of 2026, Terraform 1.10+ supports native locking on the `s3` backend via the `use_lockfile = true` argument (a `.tflock` object next to the state). Earlier versions required a separate DynamoDB table for locking, which DigitalOcean does not provide. If you are on Terraform 1.9 (no native locking yet), the workaround is to discipline yourself to one `apply` at a time and trust the warning. Upgrading to 1.10+ is preferred.

### 12.2 The two-phase bootstrap, mechanically

Phase 1 — `bootstrap/`:

```
bootstrap/
├── versions.tf      # terraform { required_providers = ... }  (no backend block)
├── providers.tf     # provider "digitalocean" { token = var.do_token }
├── variables.tf     # var.do_token, var.region, var.bucket_name
├── main.tf          # digitalocean_spaces_bucket, digitalocean_spaces_bucket_object
└── outputs.tf       # spaces_endpoint, bucket_name
```

```bash
cd bootstrap/
terraform init
terraform plan -out=plan.tfplan
terraform apply plan.tfplan
# terraform.tfstate is now on local disk
# the Spaces bucket exists in DigitalOcean
```

Phase 2 — the real working directory:

```
mini-project/
├── versions.tf      # terraform { backend "s3" {} required_providers = ... }
├── providers.tf
├── variables.tf
├── main.tf          # module "database", module "web-droplet", module "dns"
├── outputs.tf
└── backend.hcl      # bucket = "...", key = "...", endpoints = { s3 = "..." }, ...
```

```bash
cd mini-project/
terraform init -backend-config=backend.hcl
# Terraform asks: "do you want to copy existing state to the new backend?"
# answer "no" — there is no existing state in this directory; we are starting fresh
terraform plan -out=plan.tfplan
terraform apply plan.tfplan
# state file is now in the Spaces bucket, not on local disk
```

The `bootstrap/` directory's own state lives on whichever workstation you ran it from. You commit the configuration to git; the state lives on disk and you do not commit it. The bucket and lock are stable; you almost never modify them after the first apply.

---

## 13. Refactoring with `moved` blocks

A real example. You started with one flat root module:

```hcl
# old layout
resource "digitalocean_droplet" "web" { ... }
resource "digitalocean_firewall" "web_fw" { ... }
```

You want to factor it into a `web-droplet` module:

```hcl
# new layout
module "web" {
  source = "./modules/web-droplet"
  # ...
}
```

The naive approach destroys the old resources and creates new ones — five minutes of downtime, a new public IP, and a database that suddenly cannot accept connections from the new IP. The right approach uses `moved` blocks:

```hcl
moved {
  from = digitalocean_droplet.web
  to   = module.web.digitalocean_droplet.this
}

moved {
  from = digitalocean_firewall.web_fw
  to   = module.web.digitalocean_firewall.this
}

module "web" {
  source = "./modules/web-droplet"
  # ...
}
```

On the next `terraform plan`, Terraform sees the `moved` blocks and reports "moved 2 resources; no changes." No destroy, no create, no downtime. The same droplet, same IP, same database connection, just at a new state address.

The `moved` blocks can be deleted in a follow-up PR after every collaborator has run `terraform apply` at least once. Many teams leave them for two release cycles, then delete them.

---

## 14. The Terraform Registry: reading other people's modules

The Terraform Registry (`registry.terraform.io`) hosts published modules. Reading one before deciding to use it is a half-hour skill that pays for itself every week of your career.

### 14.1 The half-hour audit

For any module you are considering, check, in order:

1. **`versions.tf`.** What Terraform version does it require? What providers, what versions?
2. **`variables.tf`.** How many required variables? Do they have descriptions? Do they have validations? Are sensitive variables marked sensitive?
3. **`outputs.tf`.** What does the module expose? Are sensitive outputs marked sensitive?
4. **`main.tf`** (or whatever file contains the resources). How many resources? Do they use `for_each` or `count`? Are the names sensible? Are there `lifecycle` blocks?
5. **`README.md`.** Is there an example call? Does the example reflect the current `variables.tf` (i.e., the README is maintained)?
6. **The repo's git history.** When was the last commit? When was the last tagged release? How many open issues? How many open PRs?

If steps 1-4 take more than fifteen minutes, the module is probably too complex for your use case. If steps 5-6 raise red flags (six months since the last commit, dozens of unanswered issues), use a different module.

### 14.2 The decision tree

```
                Do you need this functionality?
                /                       \
              no                         yes
              |                          |
            don't                        ▼
            install            Is there a module on the registry?
            it                  /                              \
                              no                                yes
                              |                                 |
                            write                               ▼
                            your                       Did your half-hour audit
                            own                        pass on the top candidate?
                                                       /              \
                                                     no                yes
                                                     |                 |
                                                    fork                ▼
                                                    it             Use it.
                                                    or              Pin the
                                                    write          version.
                                                    your own       Commit
                                                                   the lock.
```

---

## 15. CI for Terraform

A Terraform configuration in git is code; therefore it deserves CI. The minimum shape:

```yaml
# .github/workflows/terraform.yml
name: terraform
on:
  pull_request: { branches: [main] }
  push:         { branches: [main] }

permissions:
  contents: read
  id-token: write

jobs:
  validate:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.9.5"
      - run: terraform fmt -recursive -check
      - run: terraform init -backend=false
      - run: terraform validate
      - uses: terraform-linters/setup-tflint@v4
      - run: tflint --recursive
```

Five checks, all of them static (no API calls, no credentials needed): `fmt`, `init -backend=false`, `validate`, `tflint`. A PR that breaks any of them is a PR you should not merge. We do not run `plan` in CI in this lecture — that requires real credentials and a real backend, which is a Week 6 topic.

> **Status panel — CI for Terraform on a mini-project repo**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  REPO: c15-week-05-jeanstephane                     │
> │                                                     │
> │  Workflows:    1                                    │
> │  - terraform.yml  on: pull_request, push to main    │
> │                                                     │
> │  Checks: fmt, init -backend=false, validate, tflint │
> │  Average wall-clock: 47 s (cold), 22 s (warm)       │
> │                                                     │
> │  Last 7 days:  21 runs   green: 19   red: 2         │
> └─────────────────────────────────────────────────────┘
> ```

---

## 16. Testing modules with `terraform test`

As of Terraform 1.6, the `terraform test` command is the canonical way to test modules. A test file `tests/basic.tftest.hcl`:

```hcl
variables {
  region      = "nyc3"
  size        = "s-1vcpu-1gb"
  image_ref   = "ghcr.io/example/app:v1.0.0"
  ssh_key_ids = ["12345"]
  db_url      = "postgres://app:pass@db.example:5432/app"
  name_prefix = "test"
  tags        = ["test"]
}

run "plan_only" {
  command = plan

  assert {
    condition     = digitalocean_droplet.this.size == "s-1vcpu-1gb"
    error_message = "droplet size did not match input"
  }

  assert {
    condition     = length(digitalocean_firewall.this.inbound_rule) == 3
    error_message = "expected 3 inbound rules (22, 80, 443)"
  }
}
```

Run it with:

```bash
terraform test
```

The `command = plan` mode does not call the cloud — it stops at the plan stage and asserts against the planned values. There is also `command = apply` (the default), which provisions for real, asserts, and destroys; that mode is for integration tests, not unit tests.

The pattern: `command = plan` for every assertion that can be made against the plan; `command = apply` only when you need to confirm a real-world property (a droplet was reachable, a DNS record resolves).

---

## 17. Anti-patterns specific to modules

Patterns that show up in module code and not in flat-root code:

- **The "kitchen sink" module.** One module with seventy variables that does ten different things. Split it.
- **The "thin wrapper" module.** One module with three variables that calls one `aws_instance` resource. Inline it.
- **Hardcoded provider-version constraints.** A module that requires `provider = "~> 2.40"` (exact) breaks every caller the day the provider ships 2.41. Use floor-and-major: `>= 2.40, < 3.0`.
- **Module outputs that leak state.** Outputting an entire resource object (`value = digitalocean_droplet.this`) couples your callers to every attribute. Output only the attributes you intend to expose.
- **`source = "./modules/.../.../..."`** with deep relative paths. If you have three levels of `..` in a source, the layout is wrong.
- **Modules with their own `backend` block.** Forbidden; the root module owns the backend. If you put a `backend` in a child module, `terraform init` will warn and ignore it.
- **Modules that take a `providers = { ... }` map for no reason.** If your module uses only the default provider, do not declare a `required_providers` alias.

---

## What we covered

A module is a directory of `.tf` files with four canonical files (`versions.tf`, `variables.tf`, `main.tf`, `outputs.tf`). Good variables are typed, documented, validated, and sensitive when they carry secrets. Good outputs are named for what they are, marked sensitive when they leak, and (in Terraform 1.2+) gated with `precondition` blocks. Remote state lives in a backend with locking and encryption; the two-phase bootstrap is the pattern that gets you there. The `moved` block (1.1+) is how you refactor without recreating; the `import` block (1.5+) is how you adopt without recreating. CI for Terraform is five static checks; module-level testing is `terraform test`.

The mini-project for the week pulls all of this together: three modules (`database`, `web-droplet`, `dns`), one root module, one remote backend, one `terraform apply`. By Sunday, you will have a public URL serving an image your Week 4 CI pipeline pushed to GHCR — and you will have deleted it cleanly with `terraform destroy` and a calendar reminder.

---

*Next: Exercise 1 — Your First Real Resource on DigitalOcean.*
