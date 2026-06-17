# Week 5 — Quiz

Ten questions. Lectures closed. Aim for 9/10.

---

**Q1.** A `terraform` block contains `required_version = ">= 1.9.0, < 2.0.0"`. A teammate runs `terraform 1.8.5` against the module. What happens?

- A) Terraform 1.8.5 silently warns and runs anyway.
- B) Terraform 1.8.5 refuses to plan and exits with a version-mismatch error.
- C) Terraform 1.8.5 plans successfully but refuses to apply.
- D) The `required_version` constraint is advisory; nothing happens.

---

**Q2.** Which of the following describes the **state file** in one sentence?

- A) A JSON document that records, for every resource Terraform manages, its address, the cloud's identifier for it, and a snapshot of every attribute the provider returned the last time Terraform read or wrote it.
- B) A YAML document that records the configuration the user wrote.
- C) A binary file produced by `terraform init` containing the provider plugins.
- D) A SQL database that stores resource histories.

---

**Q3.** A module is being refactored from a flat root layout (`resource "digitalocean_droplet" "web"`) into a child module (`module.web.digitalocean_droplet.this`). Without any special blocks, what does `terraform plan` show?

- A) "No changes." Terraform infers the move automatically.
- B) "Plan: 0 to add, 1 to change, 0 to destroy."
- C) "Plan: 1 to add, 0 to change, 1 to destroy." Terraform sees the old address gone from configuration and the new address absent from state.
- D) An error: "address mismatch."

---

**Q4.** Which Terraform 1.1+ block tells the planner that a resource has been renamed without destroying and recreating it?

- A) `import`
- B) `moved`
- C) `removed`
- D) `rename`

---

**Q5.** A `variable` block declares `type = string` and no `default`. The caller does not pass a value. What happens at plan time?

- A) Terraform uses the empty string `""` as the value.
- B) Terraform uses `null` as the value.
- C) Terraform prompts interactively for the value (unless `-input=false`, in which case it errors).
- D) Terraform skips any resource that references the variable.

---

**Q6.** Which of the following is the **correct** shape for a module's `outputs.tf` when the output carries a database connection string?

- A) `output "db_url" { value = "..." }`
- B) `output "db_url" { value = "..." sensitive = true }`
- C) `output "db_url" { value = "..." encrypted = true }`
- D) Outputs cannot carry sensitive values; use a `local` instead.

---

**Q7.** Which is the **correct** reason to use `for_each` instead of `count` for a list of three workers in three different regions?

- A) `count` is deprecated as of Terraform 1.9.
- B) `for_each` runs three times faster than `count` at plan time.
- C) `for_each` tracks each instance by a stable key; removing the middle worker destroys only that worker. `count` would re-index the remaining two, causing them to be destroyed and recreated.
- D) `for_each` lets you use the `each.value` expression, which `count` does not support.

---

**Q8.** Which is the **correct** order of operations for the two-phase bootstrap pattern?

- A) Create the backend bucket with a remote backend, then create the rest of the infrastructure with a local backend.
- B) Create the backend bucket with a local backend (a separate `bootstrap/` directory with `terraform apply`), then create the rest of the infrastructure in a different directory that uses the now-existing bucket as a remote backend.
- C) Create everything in one configuration with one `terraform apply`; the backend bootstraps itself.
- D) Use the cloud's web console to create the bucket manually, then declare a backend block referencing it.

---

**Q9.** A `provider` block has no aliased variant, and a `resource` block does not declare `provider = ...`. The module's `required_providers` declares two providers (e.g. `aws` and `digitalocean`). Where does the resource get its provider from?

- A) The first `provider` block in the file, alphabetically.
- B) The provider whose source matches the resource's type prefix (`aws_*` resources use the `aws` provider; `digitalocean_*` use the `digitalocean` provider).
- C) The provider declared in `required_providers` first in source order.
- D) An error; you must always declare `provider = ...` on every resource when multiple providers are present.

---

**Q10.** A teammate runs `terraform apply` while you are running `terraform apply` against the same remote state. With state locking enabled (e.g., `use_lockfile = true` on the S3 backend), what happens to the teammate's apply?

- A) Both applies run in parallel; the last write wins.
- B) The teammate's apply silently waits for the lock to release, then continues.
- C) The teammate's apply fails fast with a lock-info error that includes the holder of the lock and a timestamp.
- D) The teammate's apply overrides the lock and proceeds.

---

## Answers

1. **B.** `required_version` is enforced. Terraform 1.8 refuses to plan against a module that requires 1.9+.
2. **A.** The state file is a JSON snapshot of every resource Terraform manages, including their cloud-side IDs and every attribute the provider returned. Treat it as a secret because it can contain secrets.
3. **C.** Without a `moved` block, Terraform sees `digitalocean_droplet.web` in state but not in configuration (so: destroy), and sees `module.web.digitalocean_droplet.this` in configuration but not in state (so: create). The `moved` block tells the planner this is a rename, not a destroy-then-create.
4. **B.** The `moved` block (Terraform 1.1+) is the declarative replacement for `terraform state mv`.
5. **C.** Without a default, the variable is required. Terraform prompts interactively unless `-input=false` is passed, in which case it errors. CI passes `-input=false` and relies on `TF_VAR_*` env vars or `-var-file=`.
6. **B.** Sensitive outputs are marked `sensitive = true`. Terraform then redacts the value in plan/apply output (but it is still in state, encrypted at rest in your remote backend).
7. **C.** `for_each` tracks identity by key; removing one entry affects only that one instance. `count` tracks by index; removing an entry re-indexes everyone after it, causing unnecessary destroys.
8. **B.** Two phases, two directories. The bootstrap creates the backend bucket (with a local state on disk). The real working directory then uses the bucket as its remote backend.
9. **B.** Terraform infers the provider from the resource type's prefix. The local name of the provider in `required_providers` (`aws`, `digitalocean`) is what the prefix maps to. You only need `provider = ...` to disambiguate when there are multiple aliases of the same provider.
10. **C.** State locking is mandatory mutual exclusion. The second apply fails fast with a clear lock-info error (holder, time, operation). This is correct behavior; the alternative (silent waiting, or worse, parallel writes) would corrupt state.

---

*If you missed more than two, re-read the relevant lecture section before moving on. The state-file and module-refactoring questions especially are foundational to everything in Weeks 6-12.*
