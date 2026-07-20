# Exercise 2 — Modules, Variables, and Outputs

**Goal.** Refactor Exercise 1's flat root module into a small reusable `web-droplet` module. Call it twice from the root with `for_each`, parameterize it with typed-and-validated variables, expose its outputs, and confirm the rename moves cleanly through state with a `moved` block. Then destroy.

**Estimated time.** 90 minutes.

**Cost.** About $0.10 (two droplets for fifteen minutes).

---

## Why we are doing this

Exercise 1 left you with a single resource in a single root. That works for one droplet. The moment you want two — or you want the same shape in `dev` and `prod`, or in `nyc3` and `fra1` — copy-paste is the wrong answer. A module is the right answer. This exercise turns a flat root into the canonical four-file module shape from Lecture 2, then refactors the existing state into the new shape **without recreating the droplet**.

---

## Setup

### Working directory

Copy your Exercise 1 repo as a starting point:

```bash
cp -r ~/c15/week-05/ex-01-first-resource ~/c15/week-05/ex-02-modules
cd ~/c15/week-05/ex-02-modules

# clear the old state and lock; we are starting fresh init
rm -f terraform.tfstate terraform.tfstate.backup plan.tfplan
rm -rf .terraform/

git init -b main
gh repo create c15-week-05-ex02-$USER --public --source=. --remote=origin
```

### Verify credentials still work

```bash
echo "${TF_VAR_do_token:0:8}..."
# dop_v1_a...

doctl account get
# ok
```

---

## Phase 1 — Apply the flat configuration (so we have state to refactor)

The lecture's `moved` block pattern requires existing state. Let's first apply the Exercise 1 configuration once, so we have something to refactor.

```bash
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out=plan.tfplan
terraform apply plan.tfplan
```

After 60 seconds, you have one droplet. Confirm:

```bash
terraform state list
# digitalocean_droplet.hello
# digitalocean_ssh_key.default

terraform output droplet_ipv4
# "157.245.110.42"
```

Do **not** destroy. The next phase refactors this state without destroying the droplet.

---

## Phase 2 — Extract the module

Create the module directory:

```bash
mkdir -p modules/web-droplet
```

### `modules/web-droplet/versions.tf`

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

### `modules/web-droplet/variables.tf`

```hcl
variable "name" {
  description = "Droplet name (will be combined with the prefix)"
  type        = string

  validation {
    condition     = length(var.name) > 0 && length(var.name) <= 64
    error_message = "name must be 1-64 characters."
  }
}

variable "name_prefix" {
  description = "Prefix applied to all resource names in this module"
  type        = string
  default     = "c15-w05"
}

variable "region" {
  description = "DigitalOcean region slug"
  type        = string

  validation {
    condition     = can(regex("^[a-z]{3}[0-9]$", var.region))
    error_message = "region must be a three-letter, one-digit region slug (e.g. nyc3)."
  }
}

variable "size" {
  description = "DigitalOcean droplet size slug"
  type        = string
  default     = "s-1vcpu-1gb"
}

variable "image" {
  description = "Droplet image slug"
  type        = string
  default     = "ubuntu-24-04-x64"
}

variable "ssh_key_ids" {
  description = "List of SSH key IDs to install on the droplet"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to the droplet"
  type        = list(string)
  default     = []
}
```

Seven variables. Two with validations, four with defaults, one required (`ssh_key_ids`).

### `modules/web-droplet/main.tf`

```hcl
resource "digitalocean_droplet" "this" {
  name     = "${var.name_prefix}-${var.name}"
  image    = var.image
  region   = var.region
  size     = var.size
  ssh_keys = var.ssh_key_ids

  tags = concat(var.tags, ["managed-by:terraform"])

  lifecycle {
    create_before_destroy = true
  }
}
```

One resource. Notice the resource's local name is `this` — convention for "the one resource this module is built around."

### `modules/web-droplet/outputs.tf`

```hcl
output "id" {
  description = "Droplet ID"
  value       = digitalocean_droplet.this.id
}

output "ipv4_address" {
  description = "Public IPv4 address of the droplet"
  value       = digitalocean_droplet.this.ipv4_address
}

output "region" {
  description = "Region the droplet was created in"
  value       = digitalocean_droplet.this.region
}
```

Three outputs.

---

## Phase 3 — Rewrite the root module to call `web-droplet`

Replace `main.tf` in the **root** module with:

```hcl
resource "digitalocean_ssh_key" "default" {
  name       = "c15-week-05-ex02"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

module "hello" {
  source = "./modules/web-droplet"

  name        = "hello"
  region      = var.region
  size        = var.droplet_size
  ssh_key_ids = [digitalocean_ssh_key.default.id]
  tags        = ["ex02"]
}
```

Update `outputs.tf` in the root to reference the module's outputs:

```hcl
output "droplet_id" {
  description = "DigitalOcean droplet ID"
  value       = module.hello.id
}

output "droplet_ipv4" {
  description = "Public IPv4 address of the droplet"
  value       = module.hello.ipv4_address
}

output "ssh_command" {
  description = "Ready-to-paste SSH command"
  value       = "ssh root@${module.hello.ipv4_address}"
}
```

Run `terraform plan` now — without `moved` blocks:

```bash
terraform init
terraform plan
```

You should see a plan like:

```
Plan: 1 to add, 0 to change, 1 to destroy.
```

That is the wrong answer. Terraform sees `digitalocean_droplet.hello` in state (no longer in configuration) and decides to destroy it. It also sees `module.hello.digitalocean_droplet.this` in configuration (no state) and decides to create it. **The droplet is the same droplet** — same image, same SSH key, same region. We just moved its state address.

Do not apply that plan. Press Ctrl+C if needed, or just do not type `yes`.

---

## Phase 4 — Add the `moved` block

Edit the root `main.tf` and add a `moved` block at the top:

```hcl
moved {
  from = digitalocean_droplet.hello
  to   = module.hello.digitalocean_droplet.this
}

resource "digitalocean_ssh_key" "default" {
  name       = "c15-week-05-ex02"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

module "hello" {
  source = "./modules/web-droplet"

  name        = "hello"
  region      = var.region
  size        = var.droplet_size
  ssh_key_ids = [digitalocean_ssh_key.default.id]
  tags        = ["ex02"]
}
```

Plan again:

```bash
terraform plan -out=plan.tfplan
```

Expected:

```
Terraform will perform the following actions:

  # digitalocean_droplet.hello has moved to module.hello.digitalocean_droplet.this
    resource "digitalocean_droplet" "this" {
        id   = "423897123"
        name = "hello-terraform"
        # (rest unchanged)
    }

Plan: 0 to add, 0 to change, 0 to destroy.
```

**Zero destroys.** Terraform updates the state's resource address from `digitalocean_droplet.hello` to `module.hello.digitalocean_droplet.this` without touching the cloud. Apply:

```bash
terraform apply plan.tfplan
```

Confirm:

```bash
terraform state list
# digitalocean_ssh_key.default
# module.hello.digitalocean_droplet.this
```

The droplet's state address has changed; the droplet itself has not.

> **Status panel — refactor**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  REFACTOR: flat root -> module                       │
> │                                                     │
> │  Resources before:   2 (root)                        │
> │  Resources after:    2 (1 root + 1 module)           │
> │  Destroyed:          0                               │
> │  Created:            0                               │
> │  Address changes:    1 (digitalocean_droplet.hello) │
> │                                                     │
> │  Droplet IP:         157.245.110.42 (unchanged)     │
> │  Droplet ID:         423897123       (unchanged)    │
> │  Apply time:         3 s                             │
> └─────────────────────────────────────────────────────┘
> ```

---

## Phase 5 — Use `for_each` to deploy two droplets

Now the payoff. Edit the root `main.tf` and replace the single `module "hello"` block with a `for_each` over a list of names:

```hcl
moved {
  from = module.hello.digitalocean_droplet.this
  to   = module.web["hello"].digitalocean_droplet.this
}

resource "digitalocean_ssh_key" "default" {
  name       = "c15-week-05-ex02"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

module "web" {
  for_each = toset(["hello", "world"])
  source   = "./modules/web-droplet"

  name        = each.key
  region      = var.region
  size        = var.droplet_size
  ssh_key_ids = [digitalocean_ssh_key.default.id]
  tags        = ["ex02"]
}
```

Replace the root `outputs.tf` with:

```hcl
output "droplet_ips" {
  description = "Public IPv4 addresses of all web droplets, by name"
  value       = { for k, m in module.web : k => m.ipv4_address }
}

output "ssh_commands" {
  description = "Ready-to-paste SSH commands, by name"
  value       = { for k, m in module.web : k => "ssh root@${m.ipv4_address}" }
}
```

Plan:

```bash
terraform plan -out=plan.tfplan
```

Expected:

```
Terraform will perform the following actions:

  # module.hello.digitalocean_droplet.this has moved to module.web["hello"].digitalocean_droplet.this
    resource "digitalocean_droplet" "this" {
        id   = "423897123"
        # (unchanged)
    }

  # module.web["world"].digitalocean_droplet.this will be created
  + resource "digitalocean_droplet" "this" {
      + name   = "c15-w05-world"
      + image  = "ubuntu-24-04-x64"
      + region = "nyc3"
      + size   = "s-1vcpu-1gb"
      # ...
    }

Plan: 1 to add, 0 to change, 0 to destroy.
```

One move, one create, zero destroys. The existing `hello` droplet is preserved; a new `world` droplet is created alongside it. Apply:

```bash
terraform apply plan.tfplan
```

Confirm:

```bash
terraform state list
# digitalocean_ssh_key.default
# module.web["hello"].digitalocean_droplet.this
# module.web["world"].digitalocean_droplet.this

terraform output ssh_commands
# {
#   "hello" = "ssh root@157.245.110.42"
#   "world" = "ssh root@157.245.111.55"
# }
```

You have two droplets, both managed by the same module instance, both addressable by name.

---

## Phase 6 — Destroy

```bash
terraform destroy
# Plan: 0 to add, 0 to change, 3 to destroy.
# yes
```

Sixty seconds later:

```bash
doctl compute droplet list
# (empty)
```

---

## Cleanup the `moved` blocks

After everyone on the team (in this case, just you) has run `terraform apply` past the moves, the `moved` blocks become noise. Delete them:

```hcl
# delete these from main.tf:
# moved {
#   from = digitalocean_droplet.hello
#   to   = module.hello.digitalocean_droplet.this
# }
# moved {
#   from = module.hello.digitalocean_droplet.this
#   to   = module.web["hello"].digitalocean_droplet.this
# }
```

The state has long since been migrated; the blocks are tracking nothing.

```bash
git add modules/ main.tf outputs.tf
git commit -m "feat: extract web-droplet module; deploy two droplets with for_each"
git push -u origin main
```

---

## Acceptance

- [ ] `modules/web-droplet/{versions,variables,main,outputs}.tf` all present.
- [ ] At least two `validation` blocks in the module's `variables.tf`.
- [ ] At least three `output` blocks in the module's `outputs.tf`.
- [ ] The root module calls the child module with `for_each`.
- [ ] You ran a `terraform plan` that showed **zero destroys** on the move from flat to module.
- [ ] You ran a `terraform plan` that showed **one create, zero destroys** on the move from one droplet to two.
- [ ] The `for_each` output map (`droplet_ips`) has two keys.
- [ ] You ran `terraform destroy` and `doctl compute droplet list` returns empty.
- [ ] The `moved` blocks are deleted (or kept with a TODO to delete next sprint).
- [ ] The repo's last commit is on `main` and pushed to GitHub.

---

## Write-up

Append the following to `RUN.md`:

1. **The `moved` block in your own words.** Two sentences: what is it for; what would have happened on the refactor without it.
2. **`for_each` vs `count` for this case.** One sentence: why `for_each` over `count` for a list of names.
3. **One thing about the module that you would change before publishing it.** One sentence; the answer is somewhere in the lecture's "Anti-patterns specific to modules" section.

```bash
git add RUN.md
git commit -m "docs: write-up for ex-02"
git push
```

---

*Next: Exercise 3 — Remote State on Spaces with the Two-Phase Bootstrap.*
