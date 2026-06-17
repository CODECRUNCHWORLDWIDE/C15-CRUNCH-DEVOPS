# Homework — Week 10

Six practice problems. Do at least four. Write each answer in your notes file with the YAML / shell / reasoning you used and a one-paragraph explanation of why.

---

## Problem 1 — Audit a real codebase for committed secrets

Pick a real project — your own, an open-source one you know, or a public Git repo from GitHub. Run `gitleaks` (free, <https://github.com/gitleaks/gitleaks>) against its history:

```bash
brew install gitleaks
gitleaks detect --source <repo-path> --verbose
```

Report:

- Number of findings.
- The top three by severity (or all of them, if fewer than three).
- For each, whether it is a true positive (a real leaked secret) or a false positive (e.g., a test fixture, an `EXAMPLE_KEY_XXX`).
- For each true positive, the remediation: rotate the credential, rewrite Git history (`git filter-repo`), or accept the leak and replace.

This exercise tells you something true about how your team treats secrets. Most repos have at least one finding. Document.

---

## Problem 2 — Set up SOPS for your own dotfiles

You have at least one config file with a secret in it — `~/.aws/credentials`, `~/.kube/config`, a `.env` for a side project, a `.netrc`, a GitHub token in `.gitconfig`. Pick one. Encrypt it with SOPS + age:

1. Generate an age keypair, store it in `~/.config/age/key.txt`.
2. Set up a `.sops.yaml` in the repo (or directory) that holds the file.
3. Encrypt the file in place: `sops -e -i secrets.yaml`.
4. Commit the encrypted version. Add `key.txt` to `.gitignore`.
5. Write a brief wrapper that decrypts the file to a temporary location on use and deletes it after.

Submit: the `.sops.yaml`, the encrypted file (sanitized — change the values to fake ones), and the wrapper script.

---

## Problem 3 — Sign one of your existing public images

If you have ever pushed a container image to a public registry — Docker Hub, GHCR, Quay — go sign it. If you have never pushed one, build a trivial image from a Dockerfile of your choice and push it now.

1. `docker pull` it to get the digest.
2. `cosign sign` it (keyless, your OIDC of choice).
3. `cosign verify` it with an identity policy that names *you* specifically.
4. Inspect the Rekor entry at <https://search.sigstore.dev>.
5. Generate an SBOM with syft, attach it as an attestation.

Submit: the image reference, the cosign verify output, and the Rekor entry URL.

---

## Problem 4 — Write a Kyverno policy you would actually deploy

Pick one of the three:

- **No `latest` tags allowed.** A Kyverno policy that rejects any Pod whose image reference ends in `:latest` or has no tag. Tag-discipline is its own kind of supply-chain hygiene.
- **Required labels on Production Pods.** Every Pod in namespaces with the label `tier=production` must carry labels `app`, `version`, `owner`, and `git-sha`. Reject otherwise.
- **No privileged containers.** Reject any Pod that requests `privileged: true` or `allowPrivilegeEscalation: true` in any container.

Write the ClusterPolicy YAML. Test it on the `w10` kind cluster by applying a violating Pod and capturing the rejection message. Submit the YAML and the test output.

---

## Problem 5 — Diff two real SBOMs

Pick two versions of the same public image (different tags of the same upstream project). For example: `nginx:1.26-alpine` and `nginx:1.27-alpine`. Or `python:3.11-slim` and `python:3.12-slim`.

1. syft both.
2. Diff the (name, version) pairs.
3. Report: how many packages were added? Removed? Version-bumped?
4. For each added package, do a quick judgment: legitimate (e.g., a new transitive dependency from a feature add) or suspicious (you cannot explain why it was added)?
5. Run grype on both. Did the version bump fix any CVEs? Introduce any?

Submit the diff and your analysis.

---

## Problem 6 — Map a hypothetical attack to the Week 10 stack

Pick one of the four 2020-2024 supply-chain attacks discussed in Lecture 3 (SolarWinds, Codecov, MOVEit, xz-utils). Read the primary source. Then map: for each step of the attack, which Week 10 tool would have helped, and *how* (which specific check, which specific config). Be concrete:

- Which signature would have failed to verify, against which identity policy?
- Which SBOM diff would have surfaced what?
- Which Vault audit log entry would have shown the suspicious read?

A good answer is a table: attack step on the left, defensive control on the right, expected diagnostic in the middle.

---

## Stretch

- **Try OpenBao instead of Vault.** Install OpenBao (the LF-stewarded open-source Vault fork) and run through Exercise 1 on it instead. Note any API differences. Submit a comparison.
- **Sign an attestation in GitHub Actions.** Write a GitHub Actions workflow that signs an image and attaches an SBOM attestation, using the GHA OIDC token via cosign's keyless flow. Document the workflow YAML.
- **Read the SLSA v1.0 spec end-to-end** at <https://slsa.dev/spec/v1.0/>. The full spec is ~25 pages. Write a one-paragraph summary of each major section.

---

## Grading rubric

Each problem is worth ~15 points. Total: 90 (with 10 points reserved for the quality of explanation across all problems).

- Correct YAML / shell / cosign output that runs successfully: 5 points.
- Sensible defense of choices in a paragraph: 5 points.
- Concrete evidence of execution (screenshot of admission rejection / cosign verify / Rekor URL / SBOM diff): 5 points.

90+: pass.
75-89: pass with minor revisions.
<75: redo and resubmit.
