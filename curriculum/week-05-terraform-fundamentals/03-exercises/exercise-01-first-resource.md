# Exercise 1 — Your First Real Resource on DigitalOcean

**Goal.** Write, run, and destroy a Terraform configuration that provisions a single droplet on DigitalOcean. Confirm the droplet boots, SSH in once, then bring it back down. Read the state file. Read the plan. Understand every key in the configuration.

**Estimated time.** 90 minutes (45 min building, 30 min running and inspecting, 15 min writing up).

**Cost.** About $0.05 (a $6/month droplet for fifteen minutes plus a few API calls).

---

## Why we are doing this

Lecture 1 gave you the file shape. This exercise gives you the keystrokes: every block you read about, you will now type, in a real configuration, with a real `terraform apply` against a real cloud account. By the end you will have an opinion about every field — which ones you set on every configuration, which ones you reach for only sometimes, and which ones you copy-pasted from a 2022 tutorial and never used again.

---

## Setup

### Working directory

```bash
mkdir -p ~/c15/week-05/ex-01-first-resource
cd ~/c15/week-05/ex-01-first-resource
git init -b main
gh repo create c15-week-05-ex01-$USER --public --source=. --remote=origin
```

(If `gh` is not installed: `brew install gh && gh auth login`.)

### Verify your credentials

```bash
echo "${TF_VAR_do_token:0:8}..."
# dop_v1_a... (your token's first eight chars — confirm it is set)

doctl account get
# email: yours; status: active
```

If `TF_VAR_do_token` is empty, your shell did not inherit it. Run `export TF_VAR_do_token=...` again or add it to your shell rc file before continuing.

### The `.gitignore`

Create this **before** your first `terraform apply`. Forgetting is a footgun; a committed `terraform.tfstate` containing secrets is a "git filter-branch your repo's history" remediation.

`.gitignore`:

```gitignore
# Terraform
.terraform/
.terraform.lock.hcl.bak
*.tfstate
*.tfstate.*
*.tfplan
crash.log
crash.*.log

# Local overrides
*.auto.tfvars
override.tf
override.tf.json
*_override.tf
*_override.tf.json

# Editor
.vscode/
.idea/
*.swp
```

Note: `.terraform.lock.hcl` (the lock file itself) is **not** in this list. Commit the lock file. It is the pinned-providers manifest; without it, your teammates may get different provider versions.

```bash
git add .gitignore
git commit -m "chore: gitignore for terraform"
```

---

## The configuration

We build the configuration in four files, in the order you would write them in a real project.

### `versions.tf`

```hcl
terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.40"
    }
  }
}
```

This is the contract. Future-you running `terraform init` two years from now sees this file and knows: "I need Terraform 1.9 or later, and a DigitalOcean provider in the 2.40+ line."

### `providers.tf`

```hcl
provider "digitalocean" {
  token = var.do_token
}
```

The `digitalocean` provider reads its token from the variable. We do not put a real token here.

### `variables.tf`

```hcl
variable "do_token" {
  description = "DigitalOcean API token with read/write scope"
  type        = string
  sensitive   = true
}

variable "region" {
  description = "DigitalOcean region slug"
  type        = string
  default     = "nyc3"
}

variable "droplet_size" {
  description = "DigitalOcean droplet size slug"
  type        = string
  default     = "s-1vcpu-1gb"
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key to install on the droplet"
  type        = string
  default     = "~/.ssh/id_ed25519.pub"
}
```

Four variables: one secret (`do_token`), three with sensible defaults. The token is `sensitive = true` so Terraform redacts it in output.

### `main.tf`

```hcl
resource "digitalocean_ssh_key" "default" {
  name       = "c15-week-05-ex01-${terraform.workspace}"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

resource "digitalocean_droplet" "hello" {
  name     = "hello-terraform"
  image    = "ubuntu-24-04-x64"
  region   = var.region
  size     = var.droplet_size
  ssh_keys = [digitalocean_ssh_key.default.id]

  tags = ["c15-week-05", "ex01"]

  lifecycle {
    create_before_destroy = true
  }
}
```

Two resources. The SSH key is registered (or referenced if it already exists at that name; we use a workspace-scoped name to avoid collisions if you run this on two machines). The droplet boots with that SSH key.

### `outputs.tf`

```hcl
output "droplet_id" {
  description = "DigitalOcean droplet ID"
  value       = digitalocean_droplet.hello.id
}

output "droplet_ipv4" {
  description = "Public IPv4 address of the droplet"
  value       = digitalocean_droplet.hello.ipv4_address
}

output "ssh_command" {
  description = "Ready-to-paste SSH command to reach the droplet"
  value       = "ssh root@${digitalocean_droplet.hello.ipv4_address}"
}

output "droplet_region" {
  description = "Region where the droplet was created"
  value       = digitalocean_droplet.hello.region
}
```

Four outputs. The `ssh_command` is the kind of small convenience that makes a Terraform module pleasant: after `apply`, the next thing you want to do is SSH in, and the output gives you the exact command to paste.

---

## Run it

### Initialize

```bash
terraform init
```

Expected:

```
Initializing the backend...

Initializing provider plugins...
- Finding digitalocean/digitalocean versions matching "~> 2.40"...
- Installing digitalocean/digitalocean v2.45.0...
- Installed digitalocean/digitalocean v2.45.0 (signed by HashiCorp)

Terraform has been successfully initialized!
```

A `.terraform/` directory and a `.terraform.lock.hcl` file now exist.

```bash
ls -la
# .terraform/             (gitignored)
# .terraform.lock.hcl     (commit)
# .gitignore
# main.tf
# outputs.tf
# providers.tf
# variables.tf
# versions.tf
```

Commit the lock file:

```bash
git add .terraform.lock.hcl versions.tf providers.tf variables.tf main.tf outputs.tf
git commit -m "feat: initial droplet configuration"
```

### Format and validate

```bash
terraform fmt -recursive
terraform validate
# Success! The configuration is valid.
```

If `fmt` rewrites any files, re-stage and amend; HCL formatting is not optional.

### Plan

```bash
terraform plan -out=plan.tfplan
```

Expected:

```
Terraform used the selected providers to generate the following execution plan.
Resource actions are indicated with the following symbols:
  + create

Terraform will perform the following actions:

  # digitalocean_droplet.hello will be created
  + resource "digitalocean_droplet" "hello" {
      + backups          = false
      + created_at       = (known after apply)
      + disk             = (known after apply)
      + id               = (known after apply)
      + image            = "ubuntu-24-04-x64"
      + ipv4_address     = (known after apply)
      + ipv4_address_private = (known after apply)
      + locked           = (known after apply)
      + memory           = (known after apply)
      + name             = "hello-terraform"
      + price_hourly     = (known after apply)
      + price_monthly    = (known after apply)
      + region           = "nyc3"
      + size             = "s-1vcpu-1gb"
      + ssh_keys         = (known after apply)
      + status           = (known after apply)
      + tags             = ["c15-week-05", "ex01"]
      + urn              = (known after apply)
      + vcpus            = (known after apply)
      + volume_ids       = (known after apply)
    }

  # digitalocean_ssh_key.default will be created
  + resource "digitalocean_ssh_key" "default" {
      + fingerprint = (known after apply)
      + id          = (known after apply)
      + name        = "c15-week-05-ex01-default"
      + public_key  = "ssh-ed25519 AAAA..."
    }

Plan: 2 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + droplet_id     = (known after apply)
  + droplet_ipv4   = (known after apply)
  + droplet_region = "nyc3"
  + ssh_command    = (known after apply)
```

**Read the plan.** Read it twice. The plan is the moment when you confirm Terraform is about to do what you think it is about to do. Every value marked `(known after apply)` is a value the cloud will return — Terraform will record it in state, but cannot predict it locally.

### Apply

```bash
terraform apply plan.tfplan
```

This takes 60-90 seconds. The droplet provisions, Terraform records its attributes, the apply completes:

```
digitalocean_ssh_key.default: Creating...
digitalocean_ssh_key.default: Creation complete after 2s [id=12345678]
digitalocean_droplet.hello: Creating...
digitalocean_droplet.hello: Still creating... [10s elapsed]
digitalocean_droplet.hello: Still creating... [20s elapsed]
digitalocean_droplet.hello: Still creating... [30s elapsed]
digitalocean_droplet.hello: Still creating... [40s elapsed]
digitalocean_droplet.hello: Still creating... [50s elapsed]
digitalocean_droplet.hello: Still creating... [60s elapsed]
digitalocean_droplet.hello: Creation complete after 64s [id=423897123]

Apply complete! Resources: 2 added, 0 changed, 0 destroyed.

Outputs:

droplet_id = "423897123"
droplet_ipv4 = "157.245.110.42"
droplet_region = "nyc3"
ssh_command = "ssh root@157.245.110.42"
```

Paste the `ssh_command`:

```bash
ssh root@157.245.110.42
# (accept the host key)
# root@hello-terraform:~#
```

You are in. Confirm with:

```bash
hostnamectl
# Static hostname: hello-terraform
# Operating System: Ubuntu 24.04.x LTS
# Kernel: Linux 6.8.x

exit
```

---

## Read the state file

```bash
ls -la terraform.tfstate
# -rw-r--r-- ... terraform.tfstate

terraform state list
# digitalocean_droplet.hello
# digitalocean_ssh_key.default

terraform state show digitalocean_droplet.hello
# (prints every attribute Terraform has for the droplet, including its
# public IPv4, private IPv4, region, size, ssh_keys, ...)
```

Now read the raw state file once. **Do not commit it.** This is a learning exercise; in production, you never look at the raw file directly.

```bash
cat terraform.tfstate | jq '.resources[] | {type, name, instance_count: (.instances | length)}'
# {
#   "type": "digitalocean_droplet",
#   "name": "hello",
#   "instance_count": 1
# }
# {
#   "type": "digitalocean_ssh_key",
#   "name": "default",
#   "instance_count": 1
# }
```

The state file is JSON. Every resource you manage is in `resources[]`. The `instances[]` array per resource is what `count` and `for_each` use to track identity.

> **Status panel — state file**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  STATE: ~/c15/week-05/ex-01-first-resource          │
> │                                                     │
> │  Backend:    local (terraform.tfstate)              │
> │  Lineage:    af3c8b21-...  (UUID; constant)         │
> │  Serial:     2             (incremented on writes)  │
> │  Resources:  2                                      │
> │  - digitalocean_droplet.hello                       │
> │  - digitalocean_ssh_key.default                     │
> │  Sensitive:  0  (no sensitive attributes captured)  │
> │  Size:       4.1 KB                                 │
> └─────────────────────────────────────────────────────┘
> ```

---

## Make a change and re-plan

Edit `main.tf` and change the droplet's `tags` from `["c15-week-05", "ex01"]` to `["c15-week-05", "ex01", "exploration"]`. Save.

```bash
terraform plan -out=plan.tfplan
```

Expected (abridged):

```
Terraform will perform the following actions:

  # digitalocean_droplet.hello will be updated in-place
  ~ resource "digitalocean_droplet" "hello" {
        id   = "423897123"
        name = "hello-terraform"
      ~ tags = [
            "c15-week-05",
            "ex01",
          + "exploration",
        ]
    }

Plan: 0 to add, 1 to change, 0 to destroy.
```

The `~` indicates an in-place update. The plan shows exactly what will change. Apply it:

```bash
terraform apply plan.tfplan
# 1 to change.
```

The serial number in your state file just incremented (from 2 to 3, probably). Every write to state increments it.

---

## Destroy

The exercise is over. Bring the bill back to zero.

```bash
terraform destroy
```

Expected:

```
Terraform will perform the following actions:

  # digitalocean_droplet.hello will be destroyed
  - resource "digitalocean_droplet" "hello" {
      - id   = "423897123" -> null
      # ...
    }

  # digitalocean_ssh_key.default will be destroyed
  - resource "digitalocean_ssh_key" "default" {
      - id   = "12345678" -> null
      # ...
    }

Plan: 0 to add, 0 to change, 2 to destroy.

Do you really want to destroy all resources?
  Terraform will destroy all your managed infrastructure, as shown above.
  There is no undo. Only 'yes' will be accepted to confirm.

  Enter a value: yes
```

Type `yes`. Sixty seconds later:

```
digitalocean_droplet.hello: Destroying... [id=423897123]
digitalocean_droplet.hello: Destruction complete after 8s
digitalocean_ssh_key.default: Destroying... [id=12345678]
digitalocean_ssh_key.default: Destruction complete after 1s

Destroy complete! Resources: 2 destroyed.
```

Confirm:

```bash
doctl compute droplet list
# (empty)

terraform state list
# (empty)
```

---

## Acceptance

- [ ] `versions.tf`, `providers.tf`, `variables.tf`, `main.tf`, `outputs.tf` all present.
- [ ] `.gitignore` excludes `terraform.tfstate`, `*.tfplan`, `.terraform/`.
- [ ] `.terraform.lock.hcl` is committed.
- [ ] `terraform fmt -check` returns 0.
- [ ] `terraform validate` returns 0.
- [ ] You ran `terraform apply` with a saved plan file (`apply plan.tfplan`).
- [ ] You SSHed into the droplet at least once and confirmed it was Ubuntu 24.04.
- [ ] You modified the configuration and saw an in-place `~ update` plan.
- [ ] You ran `terraform destroy` and `doctl compute droplet list` returns empty.
- [ ] The repo's last commit is on `main` and pushed to GitHub.

---

## Write-up

Append a `RUN.md` to your repo. Three sections, one paragraph each:

1. **What I did.** A brief narrative of the plan-apply-modify-destroy cycle.
2. **What surprised me.** One thing about Terraform's behavior that did not match your prior assumption (the `(known after apply)` placeholders? the serial-number increment? the formatting rule that puts `=` at the same column?).
3. **What I would change for production.** One sentence: what is wrong with this configuration if you were going to operate it for real? (Hint: the answer is in the lecture's "Anti-patterns" section.)

```bash
git add RUN.md
git commit -m "docs: write-up for ex-01"
git push -u origin main
```

---

*Next: Exercise 2 — Modules, Variables, and Outputs.*
