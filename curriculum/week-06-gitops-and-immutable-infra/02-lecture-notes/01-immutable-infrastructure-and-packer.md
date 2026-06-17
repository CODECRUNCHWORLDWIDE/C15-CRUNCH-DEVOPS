# Lecture 1 — Immutable Infrastructure and Packer

> **Outcome:** You can defend the choice of immutable over mutable infrastructure in three sentences, name the four operational problems mutable servers cause, and write a Packer HCL configuration that bakes a DigitalOcean droplet image starting from `ubuntu-24-04-x64`, installs Docker, pre-pulls a known image tag from GHCR, and registers the resulting snapshot in your DigitalOcean account. You can explain how `packer init`, `packer fmt`, `packer validate`, and `packer build` map onto `terraform init`, `terraform fmt`, `terraform validate`, and `terraform apply`, and where the two tools diverge.

Mutable state is the enemy. That sentence is the thesis of Week 6, and it is doing a lot of work. We unpack it slowly across this lecture and the next, but the short version is: every operational problem you will encounter in the next eight weeks of this course can be reduced to "two engineers, two months apart, made the same server look different, and neither of them remembered what they did." Immutable infrastructure removes the possibility of that class of error by removing the possibility of *modifying* the server in the first place. Packer is the tool that makes immutable infrastructure cheap enough to use on every change.

This lecture has two halves. The first half (Sections 1-6) is the case for immutable infrastructure: what it is, what it costs, what it gives you, and the rebuild-vs-patch decision rule it forces on every operations team. The second half (Sections 7-14) is the Packer file shape: the `packer` block, `source` blocks, `build` blocks, provisioners, the `packer init / fmt / validate / build` discipline, and the integration with Terraform you will use all week. We close with three anti-patterns and a status panel for the Packer build cycle.

---

## 1. What "mutable" means

A mutable server is one you can SSH into and change. That sentence is short and almost tautological, and yet it conceals every bad operational habit of the 2005-2015 era: configuration drift, snowflake hosts, "it works on the prod box but not the staging box," the runbook step that begins "first, log in to the bastion and...", the post-mortem that ends with "we are not sure what state the disk was in." Each of those failure modes traces back to the same root: the server you operate today is a function not just of its current configuration files, but of *every command run against it since the day it was provisioned*. You cannot reproduce its state from the configuration alone, because the configuration was not the only thing that touched it.

> **Status panel — mutable host inventory (the bad shape)**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  FLEET STATUS — pets-not-cattle.example.com         │
> │                                                     │
> │  web-01    Ubuntu 20.04   uptime: 847 d   ?         │
> │  web-02    Ubuntu 22.04   uptime: 412 d   ?         │
> │  web-03    Ubuntu 22.04   uptime: 88 d    ?         │
> │  db-01     Ubuntu 18.04   uptime: 1623 d  ?         │
> │                                                     │
> │  Last full audit: never                             │
> │  Configuration drift: unknown                       │
> │  Reproducible from IaC?  no                         │
> └─────────────────────────────────────────────────────┘
> ```

Notice what you cannot say about that fleet: you cannot say whether `web-01` and `web-02` have the same packages installed, whether `db-01`'s `postgresql.conf` matches what is in the IaC repo, whether anyone has SSH'd into `web-03` in the last week and what they did. The state is in the disks, and the disks do not version themselves. The disk on `db-01` has had 1623 days of accumulated decisions baked into it; the only way to know what is on it is to read every file.

The conventional name for this shape was "pets, not cattle," coined by Bill Baker in 2012. The framing was useful at the time (servers as pets: you name them, you care for them individually, you mourn them; servers as cattle: you number them, you cull them ruthlessly, you replace them on a schedule). It is dated in 2026 — the actual distinction is not how attached you are to a server, it is whether the server's state is *derived* from configuration (immutable) or *accumulated* through operation (mutable). Pets and cattle are a metaphor about emotional attachment; immutable and mutable is a fact about how state flows.

---

## 2. What "immutable" means

An immutable server is one you never modify in place. To "patch" it, you build a new image, boot a new instance from that image, drain traffic from the old instance, and destroy the old instance. The disk on a running immutable server is *read-only with respect to configuration*: the running application can write to `/var/lib/myapp/` and `/var/log/`, but the binaries in `/usr/local/bin`, the systemd units in `/etc/systemd/system`, and the OS packages in `/var/lib/dpkg/` are exactly what the image baked at build time. Nothing the running server does changes the configuration; the next instance booted from the same image is bit-identical at boot.

This is not a new idea. It is what every cloud function platform (AWS Lambda, GCP Cloud Functions, Cloudflare Workers) does at the function level. It is what every container does at the application level (the image is read-only; container-local writes go to a writable overlay that is destroyed when the container exits). What is new — or what *was* new in 2013, when Netflix popularized it for VMs — is doing it for the whole virtual machine. You bake an image once. You boot it many times. You patch by rebaking, never by `apt upgrade`.

The four operational properties this gives you are the entire reason the rest of this week exists:

1. **Configuration is reproducible.** The state of a running server is a deterministic function of its image + cloud-init data. If you destroy the server and bring up a new one, the new one is identical to the old one *at boot*. (The application's runtime state is separate; we handle that with managed databases and external object storage.)
2. **Rollback is `boot the old image`.** Forward and back are symmetric operations: you build image v2, boot v2, drain v1, destroy v1; if v2 is bad, you boot v1, drain v2, destroy v2. The cost of rollback is the cost of one boot.
3. **No "what state is this server in?" question.** The image ID and the cloud-init data fully describe the server. Both are in git. The question is answered before you ask it.
4. **Configuration drift is not a thing.** You cannot drift from configuration if the configuration cannot be modified at runtime. The only way state changes is by rebooting from a different image.

> **Status panel — immutable fleet (the good shape)**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  FLEET STATUS — c15-w06-mini-project                │
> │                                                     │
> │  Image:   snap-abc123  (baked 2026-05-13 14:02 UTC) │
> │  Replicas:  1 / 1 running   uptime: 4 h 17 m        │
> │  Drift:     0 fields differ from config repo        │
> │  Last boot: 2026-05-13 14:18 UTC                    │
> │  Last patch: rebuild snap-abc123 from cfg @ 4c2f1   │
> │  Audit trail: 3 commits in config-repo this week    │
> └─────────────────────────────────────────────────────┘
> ```

The last line is the giveaway: every change to the running fleet is a commit in the config repo. The audit trail is the git log. There is no "Alice logged in and ran apt upgrade" event because there is no Alice with SSH access to do that.

---

## 3. The cost of immutability

Immutability is not free. The four costs you pay:

- **Build time.** Every change to the OS image — a security patch to `openssl`, a new Docker version, a new pre-pulled application image — requires a Packer run. A simple Ubuntu-plus-Docker-plus-pull build takes 4 to 8 minutes on DigitalOcean. You pay this cost on every change, and you pay it before the change reaches production.
- **Storage cost.** Every snapshot you keep costs $0.05 per GB per month on DigitalOcean (other clouds have similar pricing). A typical baked image is 3-5 GB. If you keep the last twenty images, you pay about $4 per month for the back catalogue. This is cheap; you should not optimize it away. The back catalogue *is* your rollback inventory.
- **Image-update latency.** When a critical security CVE drops, you cannot `apt upgrade` your fleet in five minutes. You must (a) rebuild the image, (b) test the new image, (c) roll the fleet to the new image. This is hours, not minutes. The mitigation is having a fast build pipeline and a fast roll mechanism — both of which we wire up this week.
- **Mental model cost.** Immutable infrastructure is a different way to think about operations. The thing you are accustomed to doing (SSH in, fix it) is now wrong. The replacement (commit the fix to the config repo, watch the controller reconcile) is correct but feels slower the first time. It stops feeling slow about two weeks in.

The honest case for paying these costs is in Section 2's four properties: you pay build time and storage cost to buy reproducibility, fast rollback, no drift, and an audit trail in git. Every team that has run mutable infrastructure for more than two years will tell you the trade is correct. Every team that has *only* run mutable infrastructure will tell you it is over-engineering until the day they have an incident they cannot reproduce.

---

## 4. The rebuild-vs-patch decision rule

The hardest habit to break is the urge to SSH into a running server and "just fix" something. Immutable infrastructure does not literally prevent you from doing this — you have root, the machine is running, you can do whatever you want. The discipline is that *you do not*. The rule that replaces the habit:

> **Every change to a running server's configuration is a commit, an image rebuild, and a roll.** No exceptions for "just a tiny fix." No exceptions for "I will commit it after."

This rule is the *rebuild-vs-patch decision rule*, and it has exactly one branch:

- If the change is **temporary** (a debugging tool you need for the next five minutes, a `tcpdump`, a `strace`), you may SSH in and run it. You may *not* save anything to disk that persists past the next reboot. Anything you install with `apt install` is permitted only on the understanding that the next boot of that instance will not have it. The standard discipline is: install in `/tmp/`, run, leave.
- If the change is **permanent** (a config file edit, a package install, a service restart that should survive reboots), it is a **rebuild**. Commit the change to the config repo. Trigger a Packer build. Roll the fleet.

There is no third branch. The temptation is to add one: "if it is a real emergency at 3 AM, I am allowed to SSH in and fix it." The temptation is wrong, and the post-mortem after the next incident will explain why: the fix you made at 3 AM is not in the config repo; the next person to boot a new instance from the image is going to step on the same bug; you have *added* a snowflake to the fleet without fixing the root cause. The emergency fix is to **roll back** to the last known-good image (a 90-second operation) — not to mutate the broken server. Mutation is what got you here.

The corollary is that your build pipeline must be fast enough that "rebuild" is not the expensive option. If a Packer build takes 90 minutes, engineers will SSH in to "save time." If it takes 6 minutes, they will not. Section 11 of this lecture is the build pipeline; treat its 6-minute target as a hard constraint, not an aspirational number.

---

## 5. What Packer is, and what it is not

Packer is HashiCorp's image-baking tool. It produces machine images for many targets — AWS AMIs, GCP images, Azure managed disks, DigitalOcean snapshots, QEMU images, VirtualBox VMs, Docker images, OCI artifacts — from a single HCL configuration. The model is:

1. **Source.** Declare what kind of image you want (a DigitalOcean snapshot in `nyc3` based on `ubuntu-24-04-x64`).
2. **Build.** Spin up a transient instance from the *base* image (the Ubuntu official image), run provisioners against it (shell scripts, file uploads, Ansible plays), and snapshot the result.
3. **Artifact.** The snapshot ID. Packer prints it; your CI captures it; Terraform consumes it.

Packer is not a configuration management tool. It does not run continuously, it does not reconcile, it does not have a state file (in the Terraform sense). Each `packer build` invocation is a one-shot: it produces an image, then it exits. The image is the artifact; the build droplet is destroyed at the end of every build. You can think of Packer as a function: it takes a `*.pkr.hcl` configuration and returns a snapshot ID, deterministically (modulo timestamps and the base image's drift).

Packer is also not a replacement for `terraform apply`. The split:

- **Packer** answers *what is in the image*.
- **Terraform** answers *how many instances of the image are running, where, and how they are connected*.

A complete workflow is: Packer builds the image → Terraform consumes the snapshot ID via a `data "digitalocean_image"` block → Terraform brings up droplets from the image → some kind of controller (Argo, Flux, or the small reconciler in the mini-project) tells Terraform *which* image to consume on each reconciliation.

---

## 6. The Packer HCL file shape

A Packer configuration is one or more `*.pkr.hcl` files in a directory. The same file-merging rule as Terraform applies (every `.pkr.hcl` in the directory is concatenated at parse time). The five top-level blocks you will write regularly:

| Block | What it declares |
|-------|------------------|
| `packer` | Required Packer version, required plugins |
| `source` | The cloud / format and the base image to start from |
| `variable` | An input parameter |
| `local` | A computed value |
| `build` | Which sources to use and which provisioners to run |

There are more in the schema (`data`, `hcp_packer_iteration`, `post-processor` at the top level) but the five above cover 99% of real builds. The HCL syntax is the same dialect Terraform uses; if you can read a `.tf` file, you can read a `.pkr.hcl` file. The one syntactic difference: provisioners live *inside* a `build` block, not at the top level.

---

## 7. The `packer` block

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

Same shape as Terraform's `terraform` block. The `required_version` constrains the Packer CLI; the `required_plugins` block constrains the per-cloud plugins. The plugin source is a GitHub path, not a HashiCorp registry namespace — historical quirk; do not let it confuse you. `packer init` reads this block and downloads the plugins into `~/.packer.d/plugins/`.

You always set both fields. The `~> 1.5` constraint means "1.5.x through 1.999.999 but not 2.0.0." Same semantics as Terraform.

---

## 8. The `source` block

```hcl
source "digitalocean" "ubuntu" {
  api_token     = var.do_token
  image         = "ubuntu-24-04-x64"
  region        = var.region
  size          = "s-1vcpu-1gb"
  ssh_username  = "root"
  snapshot_name = "c15-w06-app-{{timestamp}}"

  snapshot_regions = [var.region]
}
```

A `source` block declares one cloud target. The two labels (`"digitalocean"` and `"ubuntu"`) are positional: the first is the *builder type* (matches a plugin); the second is the *local name* you reference from `build` blocks. The fields inside the block are the builder's arguments — these vary by builder. For DigitalOcean: an API token, the base image slug, the region, the size of the build droplet, the SSH username (always `root` for DO Ubuntu images), and a snapshot name.

> **Why the `{{timestamp}}` template?** Snapshots must have unique names within an account. The `{{timestamp}}` template (a Packer-native expression, not HCL) expands to a Unix epoch second at build time, so two builds in the same minute do not collide. The newer HCL form is `formatdate("YYYYMMDD-hhmmss", timestamp())` inside a `locals` block, which is the better shape for new code:

```hcl
locals {
  snapshot_suffix = formatdate("YYYYMMDD-hhmmss", timestamp())
}

source "digitalocean" "ubuntu" {
  # ...
  snapshot_name = "c15-w06-app-${local.snapshot_suffix}"
}
```

The `snapshot_regions` field controls where the snapshot is *available*; the `region` field controls where the build droplet runs. They are usually the same. You set `snapshot_regions` to a list if you want the same image promoted to multiple regions in a single build.

---

## 9. The `build` block

```hcl
build {
  name = "c15-w06-app"

  sources = ["source.digitalocean.ubuntu"]

  provisioner "shell" {
    inline = [
      "cloud-init status --wait",
      "apt-get update -y",
      "apt-get install -y docker.io",
      "systemctl enable docker",
    ]
  }

  provisioner "file" {
    source      = "${path.root}/files/app.service"
    destination = "/etc/systemd/system/app.service"
  }

  provisioner "shell" {
    inline = [
      "docker pull ${var.image_ref}",
      "systemctl daemon-reload",
      "systemctl enable app.service",
    ]
  }
}
```

A `build` block ties one or more sources to a sequence of provisioners. The `sources` argument is a list of fully qualified source references (`source.<type>.<name>`). The provisioners run *in order*, on the build droplet that the source created, before the snapshot is taken.

The two provisioners you use this week:

- **`shell`** — runs commands inside the build droplet over SSH. Use `inline` for short command lists; use `script` for a path to a `.sh` file when the command list grows past five lines.
- **`file`** — uploads a local file or directory to the build droplet. Use it to drop in systemd unit files, configuration files, or scripts that the next `shell` provisioner will execute.

> **The `cloud-init status --wait` line.** DigitalOcean's official Ubuntu images run cloud-init at first boot to configure SSH keys and basic networking. If you run `apt-get install` before cloud-init finishes, you can hit a lock on `/var/lib/dpkg/`. The `cloud-init status --wait` blocks until cloud-init is done. Always put it first. The five minutes you save by *not* having a build fail every other run is worth the three seconds the wait costs.

The provisioners you do *not* use this week, but should know exist:

- **`ansible`** — runs an Ansible playbook against the build droplet. The right choice if you already have Ansible expertise on the team.
- **`puppet-masterless` / `chef-solo`** — equivalents for Puppet and Chef shops. Most new builds in 2026 are shell-or-Ansible; Puppet and Chef are legacy.
- **`breakpoint`** — pauses the build until you press a key. Useful for debugging: insert a `breakpoint` provisioner, `packer build -on-error=ask`, then SSH into the still-running build droplet and inspect.

---

## 10. The `variable` block and the `do_token` shape

```hcl
variable "do_token" {
  type        = string
  sensitive   = true
  description = "DigitalOcean API token with read/write scope"
}

variable "region" {
  type    = string
  default = "nyc3"
}

variable "image_ref" {
  type        = string
  description = "OCI image reference to pre-pull (e.g. ghcr.io/you/repo:tag)"
}
```

Same shape as Terraform variables. The `sensitive = true` flag tells Packer to redact the value in logs. Packer does not have a `.pkrvars.hcl` *file* convention as well-defined as Terraform's `.tfvars`, but it accepts `-var-file=foo.pkrvars.hcl` on the CLI, and most teams keep a `production.pkrvars.hcl` (gitignored) and a `dev.pkrvars.hcl` (committed, no secrets).

The token can also come from the environment variable `PKR_VAR_do_token`. This is the right shape for CI; never the right shape for the API token of your personal account (use a credentials file or your shell's keychain integration).

---

## 11. The `packer init / fmt / validate / build` discipline

The four-command discipline that turns "I ran packer" into "I shipped an image":

```bash
packer init .
packer fmt -recursive .
packer validate .
packer build -var-file=dev.pkrvars.hcl .
```

The same shape as Terraform's four commands, with the same intent:

- **`packer init`** downloads the plugins declared in `required_plugins`. Run once after every plugin version bump and on every fresh checkout. Cached in `~/.packer.d/plugins/`.
- **`packer fmt -recursive`** formats every `*.pkr.hcl` file under the current directory to the canonical 2-space-indent style. Run it on every save. The `-check` flag (no rewrite, exit non-zero on diff) is what CI runs.
- **`packer validate`** parses and type-checks the configuration. Fast, no API calls, no build droplet created. The right thing to run as the first step of CI.
- **`packer build`** creates the build droplet, runs the provisioners, snapshots, and destroys the build droplet. The only command that produces an artifact and the only one that costs cloud-money.

> **Status panel — Packer build cycle**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  PACKER BUILD — c15-w06-app                         │
> │                                                     │
> │  Phase                  Duration   Status           │
> │  ─────────────────────  ─────────  ────────────     │
> │  init (plugin pull)     8 s        ok               │
> │  validate               1 s        ok               │
> │  source droplet boot    42 s       ok               │
> │  cloud-init wait        15 s       ok               │
> │  apt-get install docker 28 s       ok               │
> │  docker pull image      54 s       ok               │
> │  snapshot create        2 m 12 s   ok               │
> │  build droplet destroy  6 s        ok               │
> │  ─────────────────────  ─────────  ────────────     │
> │  Total                  4 m 46 s   ok               │
> │                                                     │
> │  Artifact: snap-7f2c1a9b  (4.1 GB, in nyc3)         │
> └─────────────────────────────────────────────────────┘
> ```

Target total: **under 6 minutes** for a build at this scope. If your build takes more than 8 minutes, look at the snapshot create step first — that is usually the longest, and reducing the size of the build droplet's disk is the only meaningful lever.

---

## 12. Reading the artifact back into Terraform

The snapshot ID is what Terraform consumes. The two patterns:

### Pattern A — `data "digitalocean_image"` by name

```hcl
data "digitalocean_image" "app" {
  name = "c15-w06-app-20260513-140230"
}

resource "digitalocean_droplet" "app" {
  image  = data.digitalocean_image.app.id
  # ...
}
```

The data source looks up a snapshot by its exact name. The downside is that you must know the exact name (timestamp-suffixed names make this hard); the upside is that you pin to one specific image. This is the right shape when the snapshot name comes from a config-repo commit, not from a `{{timestamp}}`.

### Pattern B — pass the snapshot ID through a variable

```hcl
variable "app_image_id" {
  type        = string
  description = "DO snapshot ID baked by Packer; bumped via the config repo"
}

resource "digitalocean_droplet" "app" {
  image = var.app_image_id
  # ...
}
```

The variable is set by the controller (Argo / Flux / your reconciler). The config repo holds the current `app_image_id`. A commit that bumps this value is what triggers a re-roll. This is the shape the mini-project uses.

Pattern B is the GitOps-friendly one because the change is *visible in git*: the diff on a deploy is one line, the value of `app_image_id`. Pattern A pushes the change to the snapshot name itself, which is less reviewable.

---

## 13. The build-promote-roll pipeline

The CI shape you wire up in Exercise 1:

1. **A push to `main` of the application repo** triggers the Week 4 image build. The image is pushed to GHCR with a tag (commit SHA).
2. **A push to `main` of the application repo also** triggers a Packer build that pre-pulls the new image into a new snapshot. The Packer build runs in GitHub Actions; it has a DigitalOcean API token from `secrets.DO_TOKEN` and outputs the snapshot ID.
3. **A bot opens a PR against the config repo** that bumps the `app_image_id` variable to the new snapshot ID. (In the mini-project this is a manual step; in Exercise 1 it is just the snapshot ID printed at the end of the build.)
4. **A human reviews the PR and merges.** The merge is what triggers the reconciliation in the cluster / controller.
5. **The controller reconciles**: the new image ID is in the config; the current droplet is on the old image ID; Terraform plans a replace; the controller applies; the new droplet boots from the new snapshot; the old droplet is destroyed.

The whole pipeline takes about 8 minutes end to end (4 min Packer + 1 min PR ceremony + 3 min reconcile). The human-review step is the only one not automated, by design: it is the audit checkpoint.

---

## 14. Three Packer anti-patterns

You will see these in the wild. Avoid each.

**Anti-pattern 1 — secrets in the image.** Never bake an API token, a database password, or a TLS private key into the image. Anything baked is on every snapshot; snapshots can leak; the blast radius of a leaked snapshot is unbounded. Pass secrets at boot via cloud-init `user_data`, or read them from a secrets manager. The right test: if your snapshot were uploaded to a public bucket tomorrow, what would leak? Anything but Linux and Docker, you are doing it wrong.

**Anti-pattern 2 — `apt-get install -y` without `cloud-init status --wait`.** Half your builds will fail with `Could not get lock /var/lib/dpkg/lock-frontend`. The root cause is cloud-init running at the same time as your provisioner. The fix is one line. We covered this in Section 9; we mention it again because every team you join will have someone who did not read Section 9.

**Anti-pattern 3 — building from an unpinned base image.** `image = "ubuntu-24-04-x64"` is fine for a lab. For production, you want to pin to a specific minor version (`ubuntu-24-04-x64` is a slug; the underlying image rolls forward on every patch release). The `digitalocean_image` data source can be used in Packer to pin via the image ID, not the slug, but it requires running Terraform first — which is a chicken-and-egg situation many teams resolve by snapshotting the official image once at the start of each year and using that snapshot as the base. The general rule: every input to a reproducible build must itself be pinned.

---

## 15. Closing — the bridge to Lecture 2

You now have, in principle, a way to bake an immutable image and a way (Terraform from Week 5) to deploy instances of that image. What you do not have yet is a *controller* that does the deployment for you when the configuration changes. Lecture 2 is that controller: Argo CD and Flux, the two reference implementations of the GitOps pattern. We will see why "the controller pulls from a git repo on a clock" is a stronger property than "CI pushes on every merge," and we will see the standard config-repo layout that both Argo and Flux assume.

The Packer artifact we produced this lecture (a snapshot ID) is exactly the kind of input a GitOps controller wants: an immutable, content-addressable reference that lives in a commit in a config repo. The next lecture wires the two halves together.

---

*If you find errors in this material, please open an issue or send a PR.*
