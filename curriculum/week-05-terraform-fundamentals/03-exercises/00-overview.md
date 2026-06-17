# Week 5 — Exercises

Three hands-on drills, escalating in scope. Each builds on the previous; do them in order. By the end of Exercise 3, your laptop will hold no state for any of them — everything in a DigitalOcean Spaces bucket, encrypted, locked, reproducible.

| Exercise | Title | Time | Cost |
|----------|-------|------|------|
| [01](./exercise-01-first-resource.md) | Your first real resource on DigitalOcean | 90 min | ~$0.05 (destroyed at end) |
| [02](./exercise-02-modules-and-vars.md) | Modules, variables, and outputs | 90 min | ~$0.05 (destroyed at end) |
| [03](./exercise-03-remote-state.md) | Remote state on Spaces with the two-phase bootstrap | 90 min | ~$1.00 (Spaces stays for the week) |

---

## Before you start

Have these ready:

- A DigitalOcean account with a payment method on file.
- A DigitalOcean **personal access token** with both **read** and **write** scopes. Mint it at <https://cloud.digitalocean.com/account/api/tokens>. Export it as `TF_VAR_do_token` in every shell you use this week.
- `terraform` installed (`terraform -version` reports 1.9.0 or later).
- `doctl` installed and authenticated (`doctl auth init` once, with the token you just minted).
- `tflint` installed.
- An SSH key in `~/.ssh/id_ed25519` (or wherever you keep your keys). The exercises read the public key from disk.
- `gh` installed and authenticated. Every exercise lives in its own GitHub repo, which we will push to.

```bash
export TF_VAR_do_token=dop_v1_........................................
terraform -version
# Terraform v1.13.x  on darwin_arm64  (or your platform)

doctl account get
# email: jeanstephane@aloyd.com
# status: active

tflint -v
# TFLint version 0.55.x
```

If any of those commands fails, fix it before running an exercise. Terraform errors that come from a missing credential look like provider errors, and you will burn an hour chasing the wrong thing.

---

## Cleanup discipline

Every exercise ends with `terraform destroy`. **Do not skip it.** A droplet you forgot about for three days is $0.60. A managed database you forgot about for three days is $1.50. A Spaces bucket you forgot about for three days is $0.06 — but the state file inside it is the problem if you push secrets and forget.

Add this to the bottom of every exercise's run log:

```bash
terraform destroy -auto-approve
# Destroy complete! Resources: N destroyed.

doctl compute droplet list
# (empty — confirm)

doctl databases list
# (empty — confirm)
```

The `doctl ... list` calls are belt-and-suspenders. If `terraform destroy` succeeded and `doctl` returns a non-empty list, something is wrong: either a resource is unmanaged (created outside Terraform), or destroy did not actually run. Investigate before moving on.

---

*If you find errors in this material, please open an issue or send a PR.*
