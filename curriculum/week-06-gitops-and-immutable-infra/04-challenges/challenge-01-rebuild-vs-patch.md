# Challenge 01 — A Rebuild-vs-Patch Runbook for Four Real Incident Shapes

**Goal.** Write a one-page runbook that an on-call engineer can follow at 3 AM to decide whether to **rebuild** (Packer + Terraform reconciliation, ~8 min) or **patch in place** (SSH + edit, ~2 min) when a production incident demands a change to a running server. The runbook covers four incident shapes; the decision-rule must survive all four. Include a worked example for each shape against your Exercise 1 snapshot and the Week 5 droplet.

**Estimated time.** 2-3 hours.

**Cost.** $0.00 (no new cloud resources; the Week 5 droplet and Exercise 1 snapshot already exist).

---

## Why we are doing this

Lecture 1 stated the rebuild-vs-patch rule in Section 4: every permanent change is a rebuild; only temporary changes are patches. The rule is short; the practice is not. The four incident shapes below each push on a different part of the rule, and the team that has not thought about them in advance will compromise on the rule under pressure. The whole point of having a runbook is that the runbook is the thing under pressure, not the engineer.

---

## What you will produce

A single file `runbook.md` in `~/c15/week-06/challenge-01/`, with the structure below. Push it to a GitHub repo. The file is the deliverable; the four "worked example" sections are where the work happens.

```markdown
# Rebuild vs Patch — Runbook

## Decision rule (one-paragraph statement)

(write your version of Lecture 1 Section 4's rule, refined by what you learned this week)

## The four incident shapes

### Shape 1 — security CVE in `openssl`
(impact, urgency, decision, steps)

### Shape 2 — runaway log writer filling the disk
(impact, urgency, decision, steps)

### Shape 3 — a configuration value is wrong and the app cannot start
(impact, urgency, decision, steps)

### Shape 4 — a transient debugging session
(impact, urgency, decision, steps)

## Worked examples (with terminal output)

(reproduce each shape on the Week 5 droplet or a kind cluster, capture the keystrokes,
include redacted output)

## The "I am tempted to break the rule" section

(name three temptations and write the rebuttal for each)
```

---

## The four shapes, in detail

### Shape 1 — security CVE in `openssl`

The scenario: a CVE drops with a CVSS 9.8 score against `libssl`. The Ubuntu security team has a patched package available in the `security` apt repository. Your fleet is running an `openssl` version below the fix.

The temptation: SSH into each droplet, run `apt-get update && apt-get install -y openssl`, restart the affected services. Fix in 2 minutes per host.

The decision under the rule: **rebuild**. This is a permanent configuration change (the package version on disk). Patching one droplet does not patch the *image*, so the next droplet booted from the image (auto-scale event, instance replacement after a hardware failure, your own rollback) will boot with the *unpatched* `openssl`. The fix that lives on disk-but-not-in-the-image is a snowflake.

The steps the runbook should specify:

1. Trigger a Packer build with the latest `apt-get update` cached in the image.
2. Promote the new snapshot ID to the config repo.
3. Roll the fleet.
4. Verify the new `openssl` version on every running instance.

Worked example: re-run your Exercise 1 Packer build, capture the new snapshot ID, replace the Week 5 droplet via `terraform apply` with the new image ID. Time the whole loop. Compare against the "8 min total" target from Lecture 1.

### Shape 2 — runaway log writer filling the disk

The scenario: the app is writing logs to `/var/log/myapp.log` and the file has reached 90% of the disk. Logs are not being rotated. The droplet is alerting on disk pressure; eventually it will become unresponsive.

The temptation: SSH in, `truncate -s 0 /var/log/myapp.log`, deploy a logrotate config.

The decision under the rule: **both**. The immediate fix is patch-in-place (truncate the file — disk pressure relieved in 5 seconds). The durable fix is rebuild (logrotate config baked into the image). The runbook should say: *truncate to relieve pressure, then immediately open a PR against the config repo adding the logrotate config, then trigger the rebuild and roll*.

The lesson: emergency-mitigation and root-cause-fix are different steps. The rule does not forbid temporary patches; it requires that every patch is followed by a rebuild that makes the patch permanent. The patch buys you minutes; the rebuild buys you forever.

Worked example: on the Week 5 droplet, simulate the disk pressure (`fallocate -l 5G /tmp/fill`); SSH in, truncate; commit the logrotate config; rebuild; roll; verify.

### Shape 3 — a configuration value is wrong and the app cannot start

The scenario: the new image you just rolled has `DATABASE_URL` pointing at the wrong Postgres host. The app crashes on boot. The fleet is degraded.

The temptation: SSH in, edit `/etc/c15/app.env`, `systemctl restart app.service`. Fix in 90 seconds.

The decision under the rule: **roll back, not patch**. The right immediate response is to roll back to the previous snapshot (which had the previous config). The cluster is back in 90 seconds; same recovery time as the patch. Then fix the config in the repo, rebuild, roll forward.

Why not patch: because the broken config is *in the image*. If you patch one droplet and the controller decides to scale out (auto-heal, replacement), the new droplet boots from the same broken image. You will whack-a-mole the same fix repeatedly. The rollback gets you to the previously-known-good state with no whack-a-mole. The patch-in-place is *more work*, not less.

A wrinkle: the configuration in this exercise is *not* baked into the image (it is in cloud-init `user_data`, by design). For *this* shape, the right fix is to edit the cloud-init data in the config repo and re-`terraform apply`. The rebuild-or-patch decision becomes "edit and reconcile, never SSH." The same principle, slightly different mechanic.

Worked example: deliberately push a broken `DATABASE_URL` value via the config repo. Watch the app crash. Roll back the commit. Watch the cluster recover.

### Shape 4 — a transient debugging session

The scenario: a customer report comes in about a slow endpoint. You want to `strace` the app process to see what syscall is blocking.

The temptation: well, this is actually fine.

The decision under the rule: **patch is fine**. This is the case Lecture 1 explicitly carves out: temporary debugging tools, installed under `/tmp/`, that do not persist past the next reboot. SSH in. Install `strace`. Run it. Capture the output. Log out. The next boot of this instance will not have `strace`; the next reconciliation will not detect any drift. No follow-up rebuild needed.

The wrinkle: how do you keep yourself honest? The discipline is *do not save anything to disk that survives a reboot*. The test is: if this instance reboots in the next 60 seconds, does anything I did survive? If the answer is "the `strace` binary in `/usr/bin/`," you broke the rule. If the answer is "nothing," you stayed honest.

Worked example: SSH into the Week 5 droplet, install a debugging tool to `/tmp/`, use it, log out. Reboot the droplet via `doctl compute droplet-action reboot`. SSH back in; confirm the tool is gone.

---

## The "I am tempted to break the rule" section

The runbook should name at least three temptations explicitly. Examples:

- **"The build is broken, I have to ship a fix tonight."** Rebuttal: the broken build is a separate incident from the production fix. Fix the build first (it might be a 10-minute fix); rebuild; ship. If the build is broken in a way you cannot fix in 30 minutes, that itself is a paging event for the platform team, not a reason to bypass the build.
- **"It is just one line, the rebuild is more risk than the patch."** Rebuttal: every rebuild changes exactly the lines you commit. The risk surface of the rebuild is the diff in git. The risk surface of the patch is the rest of the disk, plus your finger-memory at 3 AM. The patch is *more* risk, not less.
- **"The customer is waiting; I do not have time for the build."** Rebuttal: the build is 6 minutes; the rollback is 90 seconds. Roll back, fix the build at leisure, roll forward when the build is green. The customer is "waiting 90 seconds" not "waiting 6 minutes." The framing was wrong.

---

## Acceptance criteria

- [ ] `runbook.md` exists in your challenge directory with all five sections (decision rule, four shapes, worked examples, temptations).
- [ ] Each of the four worked examples includes terminal output (redacted) demonstrating you actually ran the steps against a real droplet or `kind` cluster.
- [ ] The decision-rule statement at the top is in your own words, not a paste of Lecture 1.
- [ ] The "temptations" section names at least three temptations with rebuttals.
- [ ] The runbook is one page or less when printed (target: 600-800 words plus the worked examples).
- [ ] Pushed to a public GitHub repo; the URL is in your week's `notes/README.md`.

---

## Stretch goals

- Add a fifth shape: a kernel CVE. Kernel patches require a reboot of the running instance, not just a service restart. Decide whether the runbook's rule still works. (It does: rebuild → roll, where "roll" includes the new instance booting on the patched kernel.)
- Add a sixth shape: a database schema change. The droplet's image cannot help here (the DB is managed); the change is purely an application-level migration. Decide which part of the runbook applies. (None of it: this is the "out of scope of GitOps" case from Lecture 2 Section 4.)
- Convert the runbook into a slide deck for a 10-minute team presentation. The deck should be readable without the runbook open beside it; the runbook should be readable without the deck.

---

*If you find errors in this material, please open an issue or send a PR.*
