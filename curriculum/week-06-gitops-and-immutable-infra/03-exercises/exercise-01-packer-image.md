# Exercise 1 — Bake a DigitalOcean Droplet Image with Packer

**Goal.** Write a Packer HCL configuration. Bake a custom DigitalOcean droplet image starting from `ubuntu-24-04-x64`, with Docker installed, your Week 4 image pre-pulled, and a systemd unit ready to run the app at first boot. Capture the snapshot ID. Use it (manually for now) to boot a droplet via Terraform and confirm the image works end to end.

**Estimated time.** 90 minutes (45 min building and iterating, 30 min running Packer end to end, 15 min writing up).

**Cost.** About $0.20 (one build droplet for ~5 minutes per build run, plus a 4 GB snapshot you keep through the mini-project).

---

## Why we are doing this

Lecture 1 made the case for immutable infrastructure and walked through the Packer file shape. This exercise is the keystrokes: every block you read about, you now type, and at the end you have a real snapshot ID that the next two exercises and the mini-project will consume. By the end you will have an opinion about every field — which ones you set on every build, which ones you reach for only sometimes, and which ones you copy-pasted from a 2024 blog post and never used again.

---

## Setup

### Working directory

```bash
mkdir -p ~/c15/week-06/ex-01-packer-image
cd ~/c15/week-06/ex-01-packer-image
git init -b main
gh repo create c15-week-06-ex01-$USER --public --source=. --remote=origin
```

### Verify your credentials

```bash
echo "${PKR_VAR_do_token:0:8}..."
# dop_v1_a... (your token's first eight chars — confirm it is set)

doctl account get
# email: yours; status: active

packer -version
# 1.11.x
```

If `PKR_VAR_do_token` is empty, export it. Packer reads it just like `TF_VAR_*`; the prefix is `PKR_VAR_` for Packer variables.

### The `.gitignore`

Create this **before** your first `packer build`. We do not want any `.pkrvars.hcl` files with secrets, nor the `packer_cache/` directory, in git.

`.gitignore`:

```gitignore
# Packer
packer_cache/
*.pkrvars.hcl
!example.pkrvars.hcl
crash.log
crash.*.log

# Editor
.vscode/
.idea/
*.swp
```

Note: we explicitly *un-ignore* `example.pkrvars.hcl` so we can commit a sanitized example for teammates.

```bash
git add .gitignore
git commit -m "chore: gitignore for packer"
```

---

## The configuration

We build the configuration in four files, in the order you would write them in a real project.

### `versions.pkr.hcl`

```hcl
packer {
  required_version = ">= 1.11.0, < 2.0.0"

  required_plugins {
    digitalocean = {
      version = "~> 1.5"
      source  = "github.com/digitalocean/digitalocean"
    }
  }
}
```

The contract. Future-you running `packer init` two years from now sees this file and knows: "I need Packer 1.11 or later, and the DigitalOcean plugin in the 1.5+ line."

### `variables.pkr.hcl`

```hcl
variable "do_token" {
  type        = string
  sensitive   = true
  description = "DigitalOcean API token with read/write scope"
}

variable "region" {
  type        = string
  default     = "nyc3"
  description = "DigitalOcean region for the build droplet and snapshot"
}

variable "build_droplet_size" {
  type        = string
  default     = "s-1vcpu-1gb"
  description = "Size of the transient build droplet"
}

variable "image_ref" {
  type        = string
  description = "OCI image reference to pre-pull (e.g. ghcr.io/you/repo:tag)"
}

variable "image_port" {
  type        = number
  default     = 8000
  description = "TCP port the application image listens on"
}

variable "snapshot_name_prefix" {
  type    = string
  default = "c15-w06-app"
}
```

Six variables. One secret (`do_token`), five with sensible defaults or no defaults (the image reference is required from the caller).

### `sources.pkr.hcl`

```hcl
locals {
  timestamp = formatdate("YYYYMMDD-hhmmss", timestamp())
}

source "digitalocean" "ubuntu" {
  api_token     = var.do_token
  image         = "ubuntu-24-04-x64"
  region        = var.region
  size          = var.build_droplet_size
  ssh_username  = "root"
  snapshot_name = "${var.snapshot_name_prefix}-${local.timestamp}"

  snapshot_regions = [var.region]

  # Tag the snapshot so doctl listings are filterable
  snapshot_description = "C15 Week 6 baked image; built at ${local.timestamp}"
}
```

A `locals` block computes a human-readable timestamp once per build. The source block declares the build droplet shape: Ubuntu 24.04, `s-1vcpu-1gb`, root SSH login (DigitalOcean Ubuntu images allow root SSH by default; Packer uses the SSH key it auto-generates per build).

### `build.pkr.hcl`

```hcl
build {
  name = "c15-w06-app"

  sources = ["source.digitalocean.ubuntu"]

  # Phase 1: wait for cloud-init to finish, install Docker
  provisioner "shell" {
    inline = [
      "echo '[packer] waiting for cloud-init...'",
      "cloud-init status --wait",
      "echo '[packer] cloud-init complete; updating apt...'",
      "DEBIAN_FRONTEND=noninteractive apt-get update -y",
      "DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io ca-certificates",
      "systemctl enable docker",
      "systemctl start docker",
      "docker --version",
    ]
  }

  # Phase 2: drop the systemd unit for the app
  provisioner "file" {
    content = templatefile("${path.root}/files/app.service.tftpl", {
      image_ref  = var.image_ref
      image_port = var.image_port
    })
    destination = "/etc/systemd/system/app.service"
  }

  # Phase 3: pre-pull the image, enable the service (but do not start —
  # the running droplet will need its environment variables from cloud-init)
  provisioner "shell" {
    inline = [
      "echo '[packer] pre-pulling ${var.image_ref}...'",
      "docker pull ${var.image_ref}",
      "systemctl daemon-reload",
      "systemctl enable app.service",
      "echo '[packer] done; build droplet will be snapshotted next'",
    ]
  }

  # Phase 4: a final shell to confirm the image is present
  provisioner "shell" {
    inline = [
      "docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}'",
      "systemctl is-enabled app.service",
    ]
  }
}
```

Four phases. The first installs Docker (with the cloud-init wait — without it, half your builds fail with a `dpkg` lock). The second drops the systemd unit. The third pre-pulls the image and enables (but does not start) the service. The fourth is a sanity check whose output you read in the build log.

### `files/app.service.tftpl`

```ini
[Unit]
Description=c15-w06 app
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=5
EnvironmentFile=-/etc/c15/app.env
ExecStartPre=-/usr/bin/docker stop app
ExecStartPre=-/usr/bin/docker rm app
ExecStartPre=/usr/bin/docker pull ${image_ref}
ExecStart=/usr/bin/docker run \
  --rm \
  --name app \
  --env-file=/etc/c15/app.env \
  -p ${image_port}:${image_port} \
  ${image_ref}

[Install]
WantedBy=multi-user.target
```

A systemd unit that runs the image. The `EnvironmentFile=-/etc/c15/app.env` line (with the leading `-`) reads environment variables from a file that may or may not exist; the running droplet writes that file from cloud-init `user_data` (containing `DATABASE_URL=postgres://...`). This separation is what keeps secrets out of the baked image.

```bash
mkdir -p files
# (paste the file content above into files/app.service.tftpl)
```

---

## Run it

### Initialize

```bash
packer init .
```

Output:

```
Installed plugin github.com/digitalocean/digitalocean v1.5.0 in ".../plugins/github.com/digitalocean/digitalocean/packer-plugin-digitalocean_v1.5.0_x5.0_darwin_arm64"
```

Plugin is cached in `~/.packer.d/plugins/`. Re-run safely.

### Format and validate

```bash
packer fmt -recursive .
packer validate .
```

`fmt` rewrites every `*.pkr.hcl` to canonical style. `validate` parses and type-checks. Both should be no-output, exit-0 commands on the first try; if `validate` complains, read the error carefully — Packer errors point at the file and line.

### Build

We pass the `image_ref` on the CLI because it changes per build. The token is in the environment.

```bash
packer build \
  -var "image_ref=ghcr.io/<your-handle>/<your-repo>:latest" \
  .
```

Expected output (abridged):

```
==> c15-w06-app.digitalocean.ubuntu: Creating temporary ssh key for droplet...
==> c15-w06-app.digitalocean.ubuntu: Creating droplet...
==> c15-w06-app.digitalocean.ubuntu: Waiting for droplet to become active...
==> c15-w06-app.digitalocean.ubuntu: Using SSH communicator to connect: 142.93.x.x
==> c15-w06-app.digitalocean.ubuntu: Waiting for SSH to become available...
==> c15-w06-app.digitalocean.ubuntu: Connected to SSH!
==> c15-w06-app.digitalocean.ubuntu: Provisioning with shell script: /var/folders/.../packer-shell...
    c15-w06-app.digitalocean.ubuntu: [packer] waiting for cloud-init...
    c15-w06-app.digitalocean.ubuntu: status: done
    c15-w06-app.digitalocean.ubuntu: [packer] cloud-init complete; updating apt...
    c15-w06-app.digitalocean.ubuntu: Reading package lists...
    c15-w06-app.digitalocean.ubuntu: Setting up docker.io ...
    c15-w06-app.digitalocean.ubuntu: Docker version 26.1.3, build ...
==> c15-w06-app.digitalocean.ubuntu: Uploading file to /etc/systemd/system/app.service
==> c15-w06-app.digitalocean.ubuntu: Provisioning with shell script: /var/folders/.../packer-shell...
    c15-w06-app.digitalocean.ubuntu: [packer] pre-pulling ghcr.io/...
    c15-w06-app.digitalocean.ubuntu: latest: Pulling from .../...
    c15-w06-app.digitalocean.ubuntu: Status: Downloaded newer image
==> c15-w06-app.digitalocean.ubuntu: Gracefully shutting down droplet...
==> c15-w06-app.digitalocean.ubuntu: Creating snapshot: c15-w06-app-20260513-140230
==> c15-w06-app.digitalocean.ubuntu: Waiting for snapshot to complete...
==> c15-w06-app.digitalocean.ubuntu: Destroying droplet...
==> c15-w06-app.digitalocean.ubuntu: Deleting temporary ssh key...
Build 'c15-w06-app.digitalocean.ubuntu' finished after 4 minutes 46 seconds.

==> Wait completed after 4 minutes 46 seconds

==> Builds finished. The artifacts of successful builds are:
--> c15-w06-app.digitalocean.ubuntu: A snapshot was created: 'c15-w06-app-20260513-140230' (ID: 156782341) in regions 'nyc3'
```

**Capture the snapshot ID.** Write it down. We use it in Exercise 2 and the mini-project. Also confirm the snapshot is in your account:

```bash
doctl compute snapshot list
# ID         Name                          Created at            Regions    Resource ID    Min Disk Size    Size      Type
# 156782341  c15-w06-app-20260513-140230   2026-05-13T14:07:42Z  [nyc3]                    25               4.13 GB   snapshot
```

> **Status panel — Packer build**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  PACKER BUILD — c15-w06-app                         │
> │                                                     │
> │  Phase                  Duration   Status           │
> │  ─────────────────────  ─────────  ────────────     │
> │  init                   8 s        ok               │
> │  validate               1 s        ok               │
> │  source droplet boot    42 s       ok               │
> │  cloud-init wait        15 s       ok               │
> │  apt-get install docker 28 s       ok               │
> │  systemd unit upload    2 s        ok               │
> │  docker pull image      54 s       ok               │
> │  snapshot create        2 m 12 s   ok               │
> │  build droplet destroy  6 s        ok               │
> │  ─────────────────────  ─────────  ────────────     │
> │  Total                  4 m 46 s   ok               │
> │                                                     │
> │  Artifact: snapshot ID 156782341 (4.1 GB)           │
> └─────────────────────────────────────────────────────┘
> ```

---

## Confirm the snapshot boots a working droplet

Take the snapshot ID and boot a droplet from it. We use `doctl` directly for speed; Terraform would also work.

```bash
doctl compute droplet create \
  c15-w06-ex01-smoke \
  --image 156782341 \
  --size s-1vcpu-1gb \
  --region nyc3 \
  --ssh-keys $(doctl compute ssh-key list --format ID --no-header | head -1) \
  --user-data-file user-data.yaml \
  --wait
```

Where `user-data.yaml` is:

```yaml
#cloud-config
write_files:
  - path: /etc/c15/app.env
    content: |
      DATABASE_URL=postgres://placeholder
      LOG_LEVEL=info
    permissions: '0600'

runcmd:
  - mkdir -p /etc/c15
  - systemctl start app.service
```

After about 60 seconds:

```bash
doctl compute droplet get c15-w06-ex01-smoke --format Name,PublicIPv4,Status
# Name                 Public IPv4       Status
# c15-w06-ex01-smoke   159.x.x.x         active

ssh root@159.x.x.x systemctl status app.service
# ● app.service - c15-w06 app
#      Loaded: loaded (/etc/systemd/system/app.service; enabled; preset: enabled)
#      Active: active (running) since Wed 2026-05-13 14:11:23 UTC; 30s ago

curl http://159.x.x.x:8000/
# (whatever your Week 4 app returns at /)
```

If `curl` succeeds, your image works end to end. Destroy the smoke-test droplet:

```bash
doctl compute droplet delete c15-w06-ex01-smoke --force
```

The snapshot stays. We need it in Exercise 2 and the mini-project.

---

## Inspect what is in the image

For a brief read of the artifact:

```bash
doctl compute snapshot get 156782341
# ID:           156782341
# Name:         c15-w06-app-20260513-140230
# Created at:   2026-05-13T14:07:42Z
# Regions:      [nyc3]
# Min Disk Size: 25
# Size:         4.13 GB
```

The 4 GB number is the snapshot size: Ubuntu 24.04 minimal + Docker + your pre-pulled image. The 25 GB is the *minimum disk* you can boot it onto — DigitalOcean's smallest droplet has a 25 GB disk.

---

## Iterate: build a second image

Suppose your Week 4 image rolls forward to a new tag (a new commit). Rebuild:

```bash
packer build \
  -var "image_ref=ghcr.io/<your-handle>/<your-repo>:v2" \
  .
```

You will get a new snapshot ID. The old one stays in your account; this is your rollback inventory. Snapshots cost $0.05 / GB / month, so keeping ten is about $2 / month — cheap insurance.

Confirm:

```bash
doctl compute snapshot list | grep c15-w06-app
# 156782341  c15-w06-app-20260513-140230 ...
# 156784912  c15-w06-app-20260513-145817 ...
```

Two snapshots. Either can boot. The one referenced in your config repo is "the current one."

---

## What you should be able to do now

- Explain every block in `versions.pkr.hcl`, `variables.pkr.hcl`, `sources.pkr.hcl`, and `build.pkr.hcl` line by line.
- Justify the `cloud-init status --wait` line. (Without it, half your builds fail.)
- Justify the four-phase shell-file-shell-shell shape. (Phase boundaries are where things go wrong; isolating them gives you readable failure modes.)
- Explain why secrets are not in the image. (Snapshots can leak; secrets baked into a snapshot have unbounded blast radius.)
- Re-run the build with a different `image_ref` value and produce a second snapshot.

---

## Commit and push

```bash
git add versions.pkr.hcl variables.pkr.hcl sources.pkr.hcl build.pkr.hcl files/
git add example.pkrvars.hcl   # a sanitized version of your var-file
git commit -m "feat: packer build for c15-w06 app image"
git push -u origin main
```

Add a `README.md` to the repo describing what the build does, what the snapshot ID convention is, and how to consume the snapshot in Terraform.

---

## Stretch goals

- Add a `tflint`-equivalent for Packer: install `packer-plugin-amazon-import` or use `packer inspect` in CI to verify the parsed config is sensible.
- Write a GitHub Actions workflow that runs `packer fmt -check`, `packer validate`, and (on push to `main` only, with secrets configured) `packer build`. Output the snapshot ID as a workflow output.
- Add a `post-processor "manifest"` block to the build that writes the snapshot ID to a JSON file. This is what a real CI pipeline reads to feed the next stage.
- Add a Sealed Secret or SOPS-encrypted file under `files/` containing a fake API key, decrypt at provision time via a `shell-local` provisioner, and bake the *decrypted* value into the image. Decide whether this is ever the right thing to do. (Hint: rarely. Document why.)

---

## Cleanup

Snapshots cost money. At the end of the week, delete them all:

```bash
doctl compute snapshot list | grep c15-w06-app | awk '{print $1}' | xargs -n1 doctl compute snapshot delete --force
```

Until then, keep at least the most recent one — the mini-project consumes it.

---

*If you find errors in this material, please open an issue or send a PR.*
