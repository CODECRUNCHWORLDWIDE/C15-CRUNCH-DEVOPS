# Exercise 3 — Remote State on Spaces with the Two-Phase Bootstrap

**Goal.** Bootstrap a DigitalOcean Spaces bucket to hold Terraform state. Migrate an existing local state into it. Confirm state locking works. Tear down all managed resources, but leave the Spaces bucket in place for the mini-project later this week.

**Estimated time.** 90 minutes (60 min building and migrating, 20 min testing locks, 10 min writing up).

**Cost.** About $1.00. The Spaces bucket is $5/month; we keep it for the rest of the week so prorate $1.00.

---

## Why we are doing this

Local state is fine for learning, dangerous for anything else. The state file contains secrets, it tracks the full shape of your infrastructure, and it is the only thing standing between "I can recover from this" and "I have to import every resource by hand." Remote state — on Spaces, S3, GCS, or Terraform Cloud — fixes the four things local state is bad at: sharing across a team, encryption at rest, locking against concurrent writes, and surviving the loss of a workstation.

This exercise builds the canonical two-phase shape from Lecture 2 Section 12 — a `bootstrap/` directory that creates the Spaces bucket with a local state, and a real working directory that uses the bucket as its backend.

---

## Setup

### Working directory

```bash
mkdir -p ~/c15/week-05/ex-03-remote-state
cd ~/c15/week-05/ex-03-remote-state
git init -b main
gh repo create c15-week-05-ex03-$USER --public --source=. --remote=origin
```

### Generate Spaces credentials

The Spaces backend is S3-compatible. It needs an **access key** and **secret**, separate from your DigitalOcean API token. Generate them at <https://cloud.digitalocean.com/account/api/tokens> in the "Spaces Keys" section. The page returns the secret exactly once — copy it.

Export both:

```bash
export AWS_ACCESS_KEY_ID=DO00...........................
export AWS_SECRET_ACCESS_KEY=................................................
```

(The `s3` backend reads `AWS_*` environment variables even when talking to DigitalOcean. This is the SDK's convention.)

### `.gitignore`

Same as Exercise 1. Copy it.

---

## Phase 1 — Bootstrap: create the Spaces bucket

The bootstrap configuration lives in `bootstrap/`. It uses a **local backend** to create the bucket; once the bucket exists, future runs of the real working directory use it.

```bash
mkdir bootstrap
cd bootstrap
```

### `bootstrap/versions.tf`

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

No `backend` block. We are deliberately using the default local backend for the bootstrap.

### `bootstrap/providers.tf`

```hcl
provider "digitalocean" {
  token             = var.do_token
  spaces_access_id  = var.spaces_access_id
  spaces_secret_key = var.spaces_secret_key
}
```

The DigitalOcean provider needs both the API token and the Spaces keys when it manages Spaces resources.

### `bootstrap/variables.tf`

```hcl
variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "spaces_access_id" {
  description = "DigitalOcean Spaces access key ID"
  type        = string
  sensitive   = true
}

variable "spaces_secret_key" {
  description = "DigitalOcean Spaces secret access key"
  type        = string
  sensitive   = true
}

variable "region" {
  description = "DigitalOcean region for the Spaces bucket"
  type        = string
  default     = "nyc3"
}

variable "bucket_name" {
  description = "Name of the Spaces bucket to create (must be globally unique)"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]{3,63}$", var.bucket_name))
    error_message = "bucket_name must be 3-63 chars, lowercase alphanumeric and hyphens only."
  }
}
```

Three sensitive variables, two with sensible defaults.

### `bootstrap/main.tf`

```hcl
resource "digitalocean_spaces_bucket" "tfstate" {
  name   = var.bucket_name
  region = var.region
  acl    = "private"

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }
}
```

One resource. Three things to notice:

- **`acl = "private"`.** The bucket holds state, which holds secrets. Public is wrong.
- **`versioning { enabled = true }`.** Every write to state creates a new version. Recover from a bad apply by restoring the previous version.
- **`lifecycle { prevent_destroy = true }`.** A guard. Terraform refuses to `destroy` this bucket. Removing the bucket while real state is in flight would be catastrophic.

### `bootstrap/outputs.tf`

```hcl
output "bucket_name" {
  description = "The bucket's name"
  value       = digitalocean_spaces_bucket.tfstate.name
}

output "bucket_region" {
  description = "The bucket's region"
  value       = digitalocean_spaces_bucket.tfstate.region
}

output "endpoint" {
  description = "S3-compatible endpoint URL for this bucket's region"
  value       = "https://${digitalocean_spaces_bucket.tfstate.region}.digitaloceanspaces.com"
}
```

### `bootstrap/terraform.tfvars`

```hcl
bucket_name = "c15-w05-tfstate-jeanstephane"
region      = "nyc3"
```

**Replace `jeanstephane` with your own handle.** Spaces bucket names are globally unique across all DigitalOcean customers.

The `do_token`, `spaces_access_id`, and `spaces_secret_key` variables are read from `TF_VAR_*` environment variables; do not put them in `terraform.tfvars` (which would commit them).

### Run the bootstrap

```bash
export TF_VAR_do_token=$TF_VAR_do_token  # already set from Ex 1
export TF_VAR_spaces_access_id=$AWS_ACCESS_KEY_ID
export TF_VAR_spaces_secret_key=$AWS_SECRET_ACCESS_KEY

terraform init
terraform fmt -recursive
terraform validate
terraform plan -out=plan.tfplan
terraform apply plan.tfplan
```

Expected:

```
Apply complete! Resources: 1 added, 0 changed, 0 destroyed.

Outputs:
bucket_name = "c15-w05-tfstate-jeanstephane"
bucket_region = "nyc3"
endpoint = "https://nyc3.digitaloceanspaces.com"
```

The bucket exists. Confirm:

```bash
doctl spaces ls
# Name                              Region  Created
# c15-w05-tfstate-jeanstephane      nyc3    2026-05-13T...
```

State for the bootstrap itself is in `bootstrap/terraform.tfstate`. Do not commit it; do not delete it either — you may want to manage the bucket later.

```bash
cd ..
```

---

## Phase 2 — Real working directory with remote backend

```bash
mkdir realwork
cd realwork
```

### `realwork/versions.tf`

```hcl
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.40"
    }
  }

  backend "s3" {
    # configured at init time via -backend-config=backend.hcl
  }
}
```

The `backend "s3" {}` block is intentionally empty. We pass the configuration on the CLI.

### `realwork/backend.hcl`

```hcl
bucket                      = "c15-w05-tfstate-jeanstephane"
key                         = "ex-03/terraform.tfstate"
region                      = "us-east-1"
endpoints                   = { s3 = "https://nyc3.digitaloceanspaces.com" }
skip_credentials_validation = true
skip_metadata_api_check     = true
skip_region_validation      = true
skip_requesting_account_id  = true
use_path_style              = true
use_lockfile                = true
```

Ten arguments. The first three are the obvious ones. The four `skip_*` and `use_path_style` are how you tell the AWS S3 SDK "this is not AWS." The `use_lockfile = true` (Terraform 1.10+) enables native S3-compatible locking via a `.tflock` object next to the state file.

Replace `jeanstephane` with your own handle.

### `realwork/providers.tf`, `variables.tf`, `main.tf`, `outputs.tf`

Copy the same files from Exercise 2 (the flat-root version, not the modular one — we want a small surface for this exercise). Specifically:

- `providers.tf`: the `provider "digitalocean"` block, token only.
- `variables.tf`: `do_token`, `region`, `droplet_size`, `ssh_public_key_path`.
- `main.tf`: the SSH key + one droplet, no modules.
- `outputs.tf`: `droplet_id`, `droplet_ipv4`, `ssh_command`.

### Initialize with the backend config

```bash
terraform init -backend-config=backend.hcl
```

Expected:

```
Initializing the backend...

Successfully configured the backend "s3"! Terraform will automatically
use this backend unless the backend configuration changes.

Initializing provider plugins...
- Reusing previous version of digitalocean/digitalocean from the dependency lock file
- Installing digitalocean/digitalocean v2.45.0...

Terraform has been successfully initialized!
```

Notice no `terraform.tfstate` in the current directory. The state is in Spaces.

### Apply

```bash
terraform fmt -recursive
terraform validate
terraform plan -out=plan.tfplan
terraform apply plan.tfplan
```

After 60-90 seconds, the droplet exists. Confirm state is in the bucket:

```bash
doctl spaces object list c15-w05-tfstate-jeanstephane
# ex-03/terraform.tfstate         4123 B   2026-05-13T...
# ex-03/terraform.tfstate.tflock  73 B     2026-05-13T...  (if you ran apply just now)
```

The `.tflock` object lives briefly while a lock is held; it disappears after the apply completes.

```bash
terraform state list
# digitalocean_droplet.hello
# digitalocean_ssh_key.default
```

Same result as Exercise 1, but the state is in a bucket, encrypted at rest, locked during writes.

---

## Phase 3 — Test the lock

Open a second terminal window. In the first, start a long-running apply by making a change that forces a slow replacement:

Terminal 1:

```bash
# Edit main.tf and add a tag:
# tags = ["c15-week-05", "ex03", "lock-test"]

terraform plan -out=plan.tfplan
terraform apply plan.tfplan
# Acquiring state lock. This may take a few moments...
# (apply is now running for the next 5-10 seconds)
```

In Terminal 2, immediately try another apply:

Terminal 2:

```bash
cd ~/c15/week-05/ex-03-remote-state/realwork
terraform plan
# Acquiring state lock. This may take a few moments...
# ╷
# │ Error: Error acquiring the state lock
# │
# │ Lock Info:
# │   ID:        a7b3-f1d2-...
# │   Path:      ex-03/terraform.tfstate
# │   Operation: OperationTypePlan
# │   Who:       jeanstephane@workstation
# │   Version:   1.13.x
# │   Created:   2026-05-13 19:12:45.123 UTC
# │   Info:
# ╵
```

Two parallel applies cannot race. The second one fails fast with a clear error pointing to the holder of the lock. Wait for Terminal 1 to finish; rerun Terminal 2; it succeeds.

> **Status panel — remote state**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  REMOTE STATE: c15-w05-tfstate-jeanstephane         │
> │                                                     │
> │  Endpoint:       nyc3.digitaloceanspaces.com        │
> │  Bucket:         c15-w05-tfstate-jeanstephane       │
> │  Key:            ex-03/terraform.tfstate            │
> │  Versioning:     enabled                            │
> │  Locking:        enabled (use_lockfile=true)        │
> │  Encryption:     server-side (SSE-S3)               │
> │  Size:           4.1 KB                              │
> │  Versions:       3                                  │
> │  Current serial: 4                                  │
> └─────────────────────────────────────────────────────┘
> ```

---

## Phase 4 — Destroy the droplet, keep the bucket

```bash
terraform destroy -auto-approve
# Destroy complete! Resources: 2 destroyed.

doctl compute droplet list
# (empty)

doctl spaces object list c15-w05-tfstate-jeanstephane
# ex-03/terraform.tfstate    240 B  (the destroyed state is still in the bucket; that is intentional)
```

The bucket and the (now-mostly-empty) state file in it remain. The mini-project later this week will use the same bucket, with a different `key`, to store its state. The `prevent_destroy = true` on the bucket itself in the `bootstrap/` directory keeps you from accidentally destroying it.

---

## Phase 5 — Read the state file from the bucket

Sanity check: download the state file from Spaces and look at it.

```bash
doctl spaces object download c15-w05-tfstate-jeanstephane \
  ex-03/terraform.tfstate \
  /tmp/state.json

cat /tmp/state.json | jq '{serial, lineage, resources_count: (.resources | length)}'
# {
#   "serial": 5,
#   "lineage": "af3c8b21-...",
#   "resources_count": 0
# }

rm /tmp/state.json  # do not leave state files lying around
```

The state file is empty of resources (destroy succeeded), the serial is at 5 (you wrote five times: apply, change tags, apply, destroy plan, destroy apply), and the lineage UUID is constant for the lifetime of this state.

---

## Acceptance

- [ ] `bootstrap/` directory with the four canonical files plus `terraform.tfvars`.
- [ ] `realwork/` directory with `backend.hcl` and the four canonical files.
- [ ] `terraform init -backend-config=backend.hcl` succeeded.
- [ ] No `terraform.tfstate` in `realwork/` after `apply`.
- [ ] `doctl spaces object list <bucket>` shows the state file in the bucket.
- [ ] You triggered a state-lock error from a second shell and read the lock-info output.
- [ ] You destroyed the droplet; the bucket remains.
- [ ] The repo's last commit is pushed to GitHub.
- [ ] The bucket exists in the DigitalOcean dashboard, with versioning enabled and ACL set to private.

---

## Write-up

Append to `RUN.md`:

1. **What the bootstrap solves.** Two sentences: why a separate `bootstrap/` directory rather than putting the bucket in the same configuration as the droplet.
2. **The `prevent_destroy = true` lifecycle hook.** One sentence: when you remove it and when you do not.
3. **The state-lock error you saw.** One sentence: who held the lock, what would happen if there were no lock (think: two parallel applies writing different state versions).

```bash
git add RUN.md bootstrap/ realwork/
git commit -m "feat: remote state on DigitalOcean Spaces with locking"
git push -u origin main
```

---

## Carrying forward

**Do not destroy the bucket.** The mini-project for this week uses the same bucket. Leave it. Sunday's cleanup destroys both the bucket and everything that uses it; until then, the bucket is part of your week-05 infrastructure.

```bash
doctl spaces ls
# c15-w05-tfstate-jeanstephane    nyc3    (still here)
```

---

*Next: the weekly challenge, then the mini-project.*
