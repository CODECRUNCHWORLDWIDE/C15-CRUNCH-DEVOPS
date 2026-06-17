# Mini-Project — Convert the Week 5 Terraform Setup to GitOps

> Take the Week 5 droplet + managed Postgres + DNS infrastructure, the Packer-baked snapshot from Exercise 1, the config repo from Exercise 2/3, and wire them into a GitOps loop. A commit to the config repo bumps the `app_image_id` variable. A reconciler running on a schedule pulls the new value, runs `terraform plan`, applies if there is a diff, and updates DNS. You stop running `terraform apply` by hand; `git push` is the only deploy keystroke.

This is the synthesis project for Week 6. By doing it, you will touch every concept from both lectures: immutable infrastructure (Packer artifact), the pull model (a reconciler that polls the config repo), continuous reconciliation (the reconciler runs on a clock forever), and the discipline of `terraform plan -out=plan.tfplan` then `terraform apply plan.tfplan`. The reconciler in this project is **not** Argo CD or Flux — those manage Kubernetes resources, and the Week 5 droplet is not Kubernetes. Instead you write a small reconciler (about 80 lines of Python) that does the same loop against your Spaces-backed Terraform state. The point is that GitOps is a *pattern*, and the pattern works wherever you can write a controller.

**Estimated time.** 7 hours, spread across Thursday-Saturday.

**Cost.** ~$1 incremental this week, on top of the ~$6 you are already paying for the Week 5 infrastructure that this project consumes.

---

## What you will build

The work happens in two new GitHub repositories plus changes to your existing Week 5 repo:

1. **`c15-week-06-config-<you>`** — the config repo (already created in Exercise 2; we extend it).
2. **`c15-week-06-reconciler-<you>`** — a small Python program that runs as a systemd service on the Week 5 droplet (or anywhere you can run a Python script on a schedule). It pulls the config repo, computes the desired Packer snapshot ID, runs `terraform plan`, and applies if there is a diff. The reconciler is ~80 lines plus a Dockerfile and a systemd unit.
3. **`c15-week-05-miniproject-<you>` (modified)** — the Week 5 Terraform repo, with two changes: (a) the droplet's `image` argument now reads from a `var.app_image_id` variable; (b) the variable is loaded from a `.auto.tfvars.json` file that the reconciler writes from the config repo.

Plus:

4. **A GitHub Actions workflow on the config repo** — runs `terraform fmt -check`, `terraform validate`, and a `terraform plan` dry-run on every PR, so a broken commit is caught before it reaches the reconciler.

---

## Acceptance criteria

- [ ] The config repo has an `infra/c15-w06-prod/app_image_id.auto.tfvars.json` file containing the current Packer snapshot ID.
- [ ] The Week 5 Terraform repo's `web-droplet` module reads `app_image_id` from a variable, not a hardcoded value.
- [ ] The reconciler runs on a schedule (every 5 minutes) and:
  - Pulls the latest `main` from the config repo.
  - Copies `app_image_id.auto.tfvars.json` into the Terraform working directory.
  - Runs `terraform plan -out=plan.tfplan` against the Spaces-backed state.
  - Inspects the plan: if there are no changes, exits 0; if there are changes, runs `terraform apply plan.tfplan`.
  - Logs every action to `journalctl` with a structured format.
  - Posts a status check back to the config repo's commit (via the GitHub API) on each cycle.
- [ ] A commit to the config repo bumping `app_image_id` triggers (within 5 minutes) a `terraform apply` that replaces the droplet with one booted from the new snapshot. The replace uses `create_before_destroy = true`, so there is no downtime (or very short downtime).
- [ ] DNS is updated automatically as part of the apply (the new droplet's IP is registered).
- [ ] The reconciler is itself version-controlled, has a CI pipeline that builds it into an OCI image and pushes to GHCR, and is **also** deployed via the GitOps loop (the snapshot baked in Packer pre-pulls the reconciler image; the reconciler restarts itself on the droplet when its own image changes).
- [ ] A `runbook.md` in the reconciler repo describes: how to see what the reconciler did last (`journalctl -u reconciler.service`), how to pause it (`systemctl stop reconciler.timer`), how to roll back (revert the config repo commit and wait), and how to disaster-recover from scratch (rebuild reconciler, replay config repo from `main`).
- [ ] `terraform fmt -check`, `terraform validate`, `tflint` all return 0 on the Week 5 repo.
- [ ] `terraform destroy` brings the bill back to zero at the end of the week.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│   ENGINEER                                                             │
│     │                                                                  │
│     │  git push (bump app_image_id.auto.tfvars.json)                   │
│     ▼                                                                  │
│   ┌─────────────────────────────────────────────────────────┐          │
│   │  CONFIG REPO  (github.com/<you>/c15-week-06-config-<you>)│         │
│   │  infra/c15-w06-prod/app_image_id.auto.tfvars.json         │        │
│   │  Branch protection: 1 review required on main             │        │
│   └─────┬─────────────────────────────────────────────────────┘        │
│         │                                                              │
│         │  poll every 5 min (git fetch)                                │
│         ▼                                                              │
│   ┌─────────────────────────────────────────────────────────┐          │
│   │  RECONCILER  (systemd timer on the Week 5 droplet)      │          │
│   │   1. git fetch + diff                                   │          │
│   │   2. copy *.auto.tfvars.json into working dir           │          │
│   │   3. terraform plan -out=plan.tfplan                    │          │
│   │   4. if changes: terraform apply plan.tfplan            │          │
│   │   5. post commit status to GitHub                       │          │
│   └─────┬─────────────────────────────────────────────────────┘        │
│         │  terraform apply (state in Spaces from W5 Ex 3)              │
│         ▼                                                              │
│   ┌─────────────────────────────────────────────────────────┐          │
│   │  DIGITALOCEAN                                           │          │
│   │   - droplet  (image = packer snapshot ID from config)   │          │
│   │     create_before_destroy = true                        │          │
│   │   - managed Postgres  (unchanged from W5)               │          │
│   │   - DNS A record  (points at new droplet IP)            │          │
│   └─────────────────────────────────────────────────────────┘          │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

> **Status panel — target steady state**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  GITOPS STATUS — c15-w06-mini-project               │
> │                                                     │
> │  Reconciler:    healthy        last cycle: 2 m ago  │
> │  Cycle outcome: no changes                          │
> │  Config repo:   main @ 4c2f1ab                      │
> │  Current image: snap-7f2c1a9b                       │
> │  Desired image: snap-7f2c1a9b   (match)             │
> │  Droplet:       1 / 1 running   uptime: 4 h 17 m    │
> │  Postgres:      online          connections: 1      │
> │  DNS:           resolving       TTL: 300 s          │
> │  Last apply:    yesterday 14:02 UTC                 │
> └─────────────────────────────────────────────────────┘
> ```

---

## Step-by-step build

### Step 1 — Modify the Week 5 Terraform to read `app_image_id` from a variable

In your `c15-week-05-miniproject-<you>` repo, open `infra/variables.tf` and add:

```hcl
variable "app_image_id" {
  type        = number
  description = "DigitalOcean snapshot ID (a number; doctl shows them as integers) baked by Packer; controlled by the config repo"
}
```

In `infra/modules/web-droplet/main.tf`, replace `image = "ubuntu-24-04-x64"` with `image = var.app_image_id` (and add the matching `variable "app_image_id"` in the module's `variables.tf`).

Pass the value through the root module's call:

```hcl
module "web_droplet" {
  source = "./modules/web-droplet"

  # ... existing fields ...
  app_image_id = var.app_image_id
}
```

Add a `lifecycle` block on the droplet to keep replaces graceful:

```hcl
resource "digitalocean_droplet" "this" {
  # ... existing fields ...
  image = var.app_image_id

  lifecycle {
    create_before_destroy = true
  }
}
```

Confirm `terraform fmt -recursive`, `terraform validate`, `tflint --recursive` all pass. Commit:

```bash
git add infra/
git commit -m "feat: app_image_id is now an input variable (GitOps prep)"
git push
```

### Step 2 — Bootstrap the config repo's per-environment directory

Re-use the config repo from Exercise 2. Add a new top-level directory:

```bash
cd ~/c15/week-06/config-repo
mkdir -p infra/c15-w06-prod
```

Create `infra/c15-w06-prod/app_image_id.auto.tfvars.json`:

```json
{
  "app_image_id": 156782341
}
```

(Use the snapshot ID from your Exercise 1 build.)

Create `infra/c15-w06-prod/README.md` documenting the file's purpose: "this file is read by the reconciler running on the production droplet; bumping the value triggers a re-roll."

Commit:

```bash
git add infra/
git commit -m "feat: prod env initial image pin"
git push
```

### Step 3 — Write the reconciler

In a new repo (`c15-week-06-reconciler-<you>`), create `reconciler.py`:

```python
#!/usr/bin/env python3
"""C15 Week 6 GitOps reconciler.

Polls the config repo, syncs *.auto.tfvars.json into the Terraform
working directory, plans, applies if non-empty, posts commit status.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib import request

CONFIG_REPO     = os.environ["CONFIG_REPO"]          # e.g. https://github.com/me/cfg
CONFIG_BRANCH   = os.environ.get("CONFIG_BRANCH", "main")
CONFIG_PATH     = os.environ["CONFIG_PATH"]          # e.g. infra/c15-w06-prod
WORKING_DIR     = Path(os.environ["TF_WORKING_DIR"]) # e.g. /var/lib/reconciler/infra
LOCAL_CLONE     = Path(os.environ["CONFIG_CLONE"])   # e.g. /var/lib/reconciler/config-repo
GITHUB_TOKEN    = os.environ["GITHUB_TOKEN"]

def log(level, msg, **kv):
    """Structured log line; JetBrains Mono-friendly."""
    line = {"ts": time.time(), "level": level, "msg": msg, **kv}
    sys.stdout.write(json.dumps(line) + "\n")
    sys.stdout.flush()

def run(cmd, cwd=None, check=True):
    log("info", "exec", cmd=cmd, cwd=str(cwd) if cwd else None)
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)

def git_fetch():
    if not LOCAL_CLONE.exists():
        run(["git", "clone", "--branch", CONFIG_BRANCH, CONFIG_REPO, str(LOCAL_CLONE)])
    else:
        run(["git", "fetch", "origin", CONFIG_BRANCH], cwd=LOCAL_CLONE)
        run(["git", "reset", "--hard", f"origin/{CONFIG_BRANCH}"], cwd=LOCAL_CLONE)
    sha = run(["git", "rev-parse", "HEAD"], cwd=LOCAL_CLONE).stdout.strip()
    return sha

def sync_tfvars():
    src = LOCAL_CLONE / CONFIG_PATH
    for f in src.glob("*.auto.tfvars*"):
        dst = WORKING_DIR / f.name
        shutil.copy2(f, dst)
        log("info", "copied", src=str(f), dst=str(dst))

def tf_plan_apply():
    run(["terraform", "init", "-input=false", "-lockfile=readonly"], cwd=WORKING_DIR)
    plan = run(["terraform", "plan", "-input=false", "-detailed-exitcode",
                "-out=plan.tfplan"], cwd=WORKING_DIR, check=False)
    # detailed-exitcode: 0 = no diff; 2 = diff; 1 = error
    if plan.returncode == 0:
        return "no-changes"
    if plan.returncode == 2:
        run(["terraform", "apply", "-input=false", "plan.tfplan"], cwd=WORKING_DIR)
        return "applied"
    log("error", "plan failed", stderr=plan.stderr)
    raise SystemExit(1)

def post_status(sha, state, description):
    repo = CONFIG_REPO.removeprefix("https://github.com/").removesuffix(".git")
    url = f"https://api.github.com/repos/{repo}/statuses/{sha}"
    body = json.dumps({"state": state, "context": "c15-w06/reconciler",
                       "description": description}).encode()
    req = request.Request(url, data=body, method="POST",
                          headers={"Authorization": f"token {GITHUB_TOKEN}",
                                   "Accept": "application/vnd.github+json"})
    with request.urlopen(req) as resp:
        log("info", "status posted", sha=sha, state=state, code=resp.status)

def main():
    sha = git_fetch()
    sync_tfvars()
    try:
        outcome = tf_plan_apply()
        post_status(sha, "success", f"reconciled: {outcome}")
        log("info", "cycle complete", sha=sha, outcome=outcome)
    except SystemExit as e:
        post_status(sha, "failure", f"reconcile failed (exit {e.code})")
        raise

if __name__ == "__main__":
    main()
```

About 70 lines. Add a small `Dockerfile`:

```dockerfile
FROM hashicorp/terraform:1.13 AS terraform
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY --from=terraform /bin/terraform /usr/local/bin/terraform

WORKDIR /app
COPY reconciler.py /app/

ENTRYPOINT ["python3", "/app/reconciler.py"]
```

And a CI workflow (`.github/workflows/build.yml`) that builds and pushes the image to GHCR on every merge to `main`. (Same shape as Week 4.)

### Step 4 — Bake the reconciler into the Packer image

Update `files/app.service.tftpl` in your Exercise 1 Packer directory: add a second systemd unit for the reconciler, and a systemd timer that runs it every 5 minutes.

`files/reconciler.service`:

```ini
[Unit]
Description=c15-w06 GitOps reconciler
After=docker.service

[Service]
Type=oneshot
EnvironmentFile=/etc/c15/reconciler.env
ExecStart=/usr/bin/docker run --rm \
  --env-file=/etc/c15/reconciler.env \
  -v /var/lib/reconciler:/var/lib/reconciler \
  ghcr.io/<you>/c15-week-06-reconciler:latest
```

`files/reconciler.timer`:

```ini
[Unit]
Description=Run the reconciler every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Unit=reconciler.service

[Install]
WantedBy=timers.target
```

Update `build.pkr.hcl` to upload both files and pre-pull the reconciler image. Re-run `packer build`. Capture the new snapshot ID (call it `snap-X`).

Update the config repo:

```bash
cd ~/c15/week-06/config-repo
# edit infra/c15-w06-prod/app_image_id.auto.tfvars.json to point at snap-X
git add infra/
git commit -m "feat: bump to image with reconciler pre-baked"
git push
```

### Step 5 — Bootstrap once, then never again

This is the one-time bootstrap. After this step, you do not run `terraform apply` by hand again — the reconciler does it.

```bash
cd ~/c15/week-05-miniproject-<you>/infra

# Pull the latest tfvars from the config repo manually for the first apply
curl -L https://raw.githubusercontent.com/<you>/c15-week-06-config-<you>/main/infra/c15-w06-prod/app_image_id.auto.tfvars.json \
  > app_image_id.auto.tfvars.json

terraform init -backend-config=backend.hcl
terraform plan -out=plan.tfplan
terraform apply plan.tfplan
```

The apply boots a new droplet from `snap-X` (the Packer image with the reconciler pre-baked). On first boot, cloud-init writes `/etc/c15/reconciler.env` (with `CONFIG_REPO`, `CONFIG_PATH`, `GITHUB_TOKEN`, `TF_WORKING_DIR`, `CONFIG_CLONE`). Within 2 minutes (the `OnBootSec` on the timer), the reconciler runs its first cycle. From this point forward, the only deploy keystroke is `git push` to the config repo.

### Step 6 — Roll forward with a config commit

Bake a new Packer snapshot (say `snap-Y`). Update the config repo:

```bash
cd ~/c15/week-06/config-repo
# Edit infra/c15-w06-prod/app_image_id.auto.tfvars.json to snap-Y
git add infra/
git commit -m "deploy: roll to snap-Y (commit a91d34b in app repo)"
git push
```

Wait up to 5 minutes. Watch `journalctl -u reconciler.service -f` on the droplet. You should see:

```
{"ts": 1715608520.4, "level": "info", "msg": "exec", "cmd": ["git", "fetch", ...], ...}
{"ts": 1715608521.1, "level": "info", "msg": "copied", "src": ".../app_image_id.auto.tfvars.json", ...}
{"ts": 1715608522.8, "level": "info", "msg": "exec", "cmd": ["terraform", "init", ...], ...}
{"ts": 1715608533.2, "level": "info", "msg": "exec", "cmd": ["terraform", "plan", ...], ...}
{"ts": 1715608540.6, "level": "info", "msg": "exec", "cmd": ["terraform", "apply", "plan.tfplan"], ...}
{"ts": 1715608605.9, "level": "info", "msg": "status posted", "sha": "a91d34b...", "state": "success", "code": 201}
{"ts": 1715608605.9, "level": "info", "msg": "cycle complete", "sha": "a91d34b...", "outcome": "applied"}
```

The droplet is now booted from `snap-Y`. The old droplet was destroyed automatically (because of `create_before_destroy = true`). The new droplet picked up the same cloud-init data (including the `reconciler.env`), is running its own reconciler, and will keep doing so on a clock.

### Step 7 — Roll back with a `git revert`

A bad commit, a wrong image, an outage:

```bash
cd ~/c15/week-06/config-repo
git log --oneline | head -3
# a91d34b deploy: roll to snap-Y
# 4c2f1ab deploy: roll to snap-X
# ...

git revert HEAD --no-edit
git push
# Within 5 minutes, the reconciler rolls the droplet back to snap-X.
```

The audit trail in `git log` of the config repo is a complete deployment history. The audit trail in `journalctl -u reconciler.service` on the droplet is the exact sequence of actions Terraform took to enact each commit.

---

## Step 8 — Disaster recovery test (optional but recommended)

The point of GitOps is that the config repo is the source of truth. Test it:

```bash
# 1. Destroy the production droplet (intentionally, to simulate a hardware failure)
doctl compute droplet delete <name> --force

# 2. Don't touch the config repo.

# 3. Run terraform apply manually to bring up a fresh droplet from the same snapshot
cd ~/c15/week-05-miniproject-<you>/infra
terraform apply -auto-approve
```

The new droplet boots from the same snapshot, picks up the same cloud-init data (because cloud-init is rendered from the same config repo), runs the same reconciler, and within 5 minutes is in steady state. The disaster-recovery time is dominated by `terraform apply` (90 seconds) and droplet boot (90 seconds): under 5 minutes from "production droplet is gone" to "production is back."

Compare this to a mutable-server world: you would have to remember every `apt install`, every config edit, every cron job ever added by hand. Hours, sometimes days.

---

## Cleanup

At the end of the week, if you are not continuing into Week 7:

```bash
cd ~/c15/week-05-miniproject-<you>/infra
terraform destroy -auto-approve
# Destroy complete! Resources: N destroyed.

doctl compute droplet list      # empty
doctl databases list            # empty
doctl compute domain records list <yourdomain.com>  # empty (or just the NS records)

# Snapshots cost $0.05/GB/mo; clean up if you don't need them
doctl compute snapshot list | grep c15-w06 | awk '{print $1}' | xargs -n1 doctl compute snapshot delete --force
```

Confirm the bill is $0 going forward (DigitalOcean's billing page is the authoritative source).

---

## What you should be able to articulate after this project

1. **Why** the reconciler is "GitOps" even though there is no Argo CD or Flux involved. (Answer: the four OpenGitOps principles hold. The config is declarative — JSON tfvars. It is versioned and immutable — git. It is pulled automatically — the systemd timer. It is continuously reconciled — every 5 minutes forever.)
2. **What** the trust boundary looks like. (Answer: the reconciler is *inside* the production droplet; it has the credentials. The CI pipeline only ever does git-push to the config repo; it has no production credentials. The blast radius of compromised CI is one git repo, gated by branch protection.)
3. **How** to recover the cluster from the config repo alone. (Answer: provision a new droplet from the snapshot pinned in the config repo's tfvars file, with cloud-init pointing at the same config repo. The new droplet self-reconciles within 5 minutes. No state is lost because state is in Spaces, not on the droplet.)
4. **When** this pattern is the wrong choice. (Answer: when the change cadence is sub-minute — every-commit-deploys-immediately rather than every-five-minute polling — you want webhooks instead of polling. When the cluster has many apps with different cadences, you want Argo or Flux's per-app reconciliation interval rather than a global timer. When you do not have a config repo separate from the app repo, the discipline does not hold.)

---

## Stretch goals

- Replace the 5-minute polling with a webhook: GitHub's `push` event triggers a `systemd-run` that fires the reconciler immediately. Polling becomes the fallback.
- Add a `terraform plan -refresh-only` step before the `plan` to detect *drift caused outside the reconciler* (someone manually edited the droplet via the DO dashboard). On detected drift, page rather than silently correct.
- Add a `lock` step to the reconciler: write a flag file to Spaces before the apply, refuse to start a new cycle if the flag is present. Catches the race condition where the timer fires while a previous cycle is still running.
- Replace the reconciler with `Atlantis` (a real, production-grade Terraform GitOps tool). Compare 80 lines of Python with the install of a real tool. Decide which you would maintain.
- Add Argo CD on the side: run a `kind` cluster on the droplet (or anywhere), point Argo at the same config repo, and have it manage a small Kubernetes-side concern (e.g., an `external-dns` record). Argo and the Python reconciler together manage the full stack — Argo for the Kubernetes parts, the reconciler for the IaC parts.

---

*If you find errors in this material, please open an issue or send a PR.*
