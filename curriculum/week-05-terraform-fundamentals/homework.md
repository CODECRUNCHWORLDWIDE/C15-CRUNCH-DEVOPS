# Week 5 Homework

Six problems, ~6 hours total. Commit each in your week-05 repo.

---

## Problem 1 — Annotate a real module (45 min)

Pick a real `main.tf` (and its `variables.tf`, `outputs.tf`) from one of these published modules on the Terraform Registry or on GitHub:

- **`terraform-aws-modules/terraform-aws-vpc`** — the most-downloaded module in the registry. Read its top-level `main.tf`: <https://github.com/terraform-aws-modules/terraform-aws-vpc>.
- **`cloudposse/terraform-null-label`** — a single-purpose module worth reading for the discipline: <https://github.com/cloudposse/terraform-null-label>.
- **`digitalocean/terraform-provider-digitalocean/examples/kubernetes`** — the provider's own example module: <https://github.com/digitalocean/terraform-provider-digitalocean/tree/main/examples>.
- **`gruntwork-io/terraform-aws-eks`** — a large, opinionated module wrapping a complex resource: <https://github.com/gruntwork-io/terraform-aws-eks>.

Copy the relevant `.tf` files into `notes/annotated-module/`. For **every `resource`**, **every `data`** block, **every non-trivial `variable`**, and the `terraform` block, add an HCL comment that explains:

1. *What* this block does in one phrase.
2. *Why* it is structured this way (validation choice, `for_each` vs `count`, lifecycle hooks).
3. *What would break* if you removed it or changed it.

**Acceptance.** `notes/annotated-module/` contains the files with at least 30 comment lines distributed across the blocks, plus a `README.md` naming the source and the commit SHA you read.

---

## Problem 2 — State audit on Exercise 3's bucket (45 min)

Pick your Spaces bucket from Exercise 3. Run, in order:

```bash
doctl spaces object list <bucket>
doctl spaces object download <bucket> ex-03/terraform.tfstate /tmp/state.json
cat /tmp/state.json | jq '.serial, .lineage, .version, .terraform_version'
cat /tmp/state.json | jq '.resources[] | {type, name, instance_count: (.instances | length)}'
cat /tmp/state.json | jq '[.resources[].instances[].attributes | keys] | flatten | unique'
rm /tmp/state.json
```

Then read each output and answer:

1. What is the `lineage` UUID for? When does it change?
2. What is `serial`? What was it on your second `apply`? Your fifth?
3. What `terraform_version` wrote this state? What would happen if you tried to read it with Terraform 1.7?
4. List three attributes the state file contains that you would consider sensitive. Are any of them marked `sensitive` in the state's metadata?

**Acceptance.** `notes/state-audit.md` contains the answers, the redacted `jq` output, and a one-paragraph reflection on what this audit changes about how you treat state files going forward.

---

## Problem 3 — Build the slow plan, then the fast one (90 min)

Take your Exercise 2 repo. Write a second configuration `notes/slow.tf` that deliberately does **everything wrong** from a Terraform-taste perspective:

- A flat root module with ten copy-pasted `digitalocean_droplet` blocks (one per region).
- No `variable` blocks; every value is hardcoded.
- No `lifecycle` hooks anywhere.
- No `for_each`; ten literal `digitalocean_droplet.web_us`, `web_eu`, `web_ap`, etc.
- A hardcoded `provider` token (commented out — do not actually commit a real token, even by accident).
- Pinned to `version = "2.40.0"` exactly (no `~>` constraint).

You do not need to `apply` this; `terraform plan` is enough to feel the file's weight.

Then write `notes/fast.tf` that is the optimal version:

- One `web-droplet` module call with `for_each` over a `var.regions` list.
- A `variable "regions" { type = set(string) }` with a validation that each region is a valid DO slug.
- `lifecycle { create_before_destroy = true }` on the droplet.
- `version = "~> 2.40"` on the provider.

Run `terraform plan` on both. Count the lines of HCL.

**Acceptance.** `notes/before-after.md` contains:

- The two configurations.
- A table: `metric | slow | fast | improvement`. Lines of HCL, plan output line count, time-to-understand (your subjective estimate in minutes).
- A one-paragraph reflection on which optimization moved the needle most.

Target improvement: at least **3x** reduction in HCL line count.

---

## Problem 4 — Drift detection (45 min)

Take your Exercise 1 configuration. Re-apply it (one droplet). Then **modify the droplet from the DigitalOcean dashboard**: add a new tag manually (e.g., `manual-drift`).

Run `terraform plan -refresh-only`. Read the output. Then run `terraform plan`. Read that output too.

Answer:

1. What did `plan -refresh-only` print? Did it report a change?
2. What did `plan` (without `-refresh-only`) print? Was the manual change reflected in the diff?
3. What would have happened on a `terraform apply`? Would the tag have been removed?
4. How would you have used `lifecycle { ignore_changes = [tags] }` to prevent Terraform from fighting an external system over tags?

Apply `terraform destroy` at the end.

**Acceptance.** `notes/drift.md` contains the answers and the two plan outputs (redacted of any sensitive values).

---

## Problem 5 — The `import` block in practice (60 min)

The `import` block (Terraform 1.5+) is the declarative way to adopt an existing resource. Practice it.

1. Use `doctl` to create a Spaces bucket **outside Terraform**:

```bash
doctl spaces create c15-w05-hw-import-$USER --region nyc3 --acl private
```

2. In a fresh directory (`~/c15/week-05/hw-import`), write a configuration that uses an `import` block to adopt this bucket into state:

```hcl
import {
  to = digitalocean_spaces_bucket.imported
  id = "nyc3,c15-w05-hw-import-<yourhandle>"
}

resource "digitalocean_spaces_bucket" "imported" {
  name   = "c15-w05-hw-import-<yourhandle>"
  region = "nyc3"
  acl    = "private"
}
```

3. Run `terraform init` (with the same `s3` backend pointed at your Exercise 3 bucket, different `key`). Then `terraform plan -out=plan.tfplan`. Read the plan: it should report the import and zero other changes.

4. Apply. Confirm the bucket is now in state: `terraform state list`.

5. Destroy the imported bucket via Terraform.

**Acceptance.** `notes/import.md` contains the configuration, the plan output (showing the import), and the `terraform state list` output (showing the bucket is managed).

---

## Problem 6 — Choose your remote-state poison (60 min)

You have used DigitalOcean Spaces for remote state this week. The same `s3` backend works against AWS S3, MinIO, Cloudflare R2, and several others. Pick **one** alternative and configure it.

The four contenders, in difficulty order:

- **AWS S3** (easiest if you have an AWS account). Native locking via the same `use_lockfile = true` flag in Terraform 1.10+, or via a DynamoDB table in older versions.
- **Cloudflare R2** (cheap, zero egress). Same `skip_*` flags as Spaces; endpoint is `https://<account-id>.r2.cloudflarestorage.com`.
- **MinIO** (run it yourself in a container; works for local labs). Endpoint is `http://localhost:9000`.
- **Terraform Cloud / HCP Terraform** (no `s3` backend; uses the `cloud` block). Free tier is 500 resources.

Bootstrap a small bucket / project / namespace on your choice. Write a minimal Terraform configuration (one resource of your choosing) that stores state there. Run `terraform plan` and `terraform apply`. Confirm state is in the remote.

**Acceptance.** `notes/alt-backend.md` contains:

- Which backend you chose and why.
- The `versions.tf` and `backend.hcl` (or `cloud` block) snippets, with credentials redacted.
- A one-paragraph comparison of the alternative against Spaces (cost, locking, UX, regional availability).

---

## How to submit

Each problem produces a folder or a file in `notes/`. Commit them as you go:

```bash
git add notes/
git commit -m "homework: problem N — <title>"
```

End-of-week, push everything to `origin/main`. Add a `notes/README.md` that links to each problem's folder.

```bash
git push -u origin main
```

The homework is not graded the way exercises are graded; it is the seed of a portfolio. Future-you reading these notes in 2027 will be glad you wrote them down.
