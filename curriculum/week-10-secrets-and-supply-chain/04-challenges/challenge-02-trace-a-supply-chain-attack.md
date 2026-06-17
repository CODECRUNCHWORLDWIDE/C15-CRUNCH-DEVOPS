# Challenge 2 — Trace a Supply-Chain Attack Back Through Provenance

**Time:** 60 minutes.
**Cost:** $0.00.
**Cluster:** Host-only; no Kubernetes needed.
**Prerequisites:** Familiarity with the case studies from Lecture 3 (event-stream, ua-parser-js). syft, grype, and cosign on your laptop.

---

## The brief

You are the on-call engineer for a small startup. At 09:14 UTC on a Tuesday, Grafana alerts that the `pricing-api` service's CPU is at 100% across all three replicas. SSH'ing to a host (you still have hosts in 2026; the startup has not finished its kind→GKE migration) shows a process named `xmrig` consuming the CPU. Someone has put a cryptominer on your production fleet.

You have three artifacts:

1. The current image's digest: `ghcr.io/yourstartup/pricing-api@sha256:bad999...`
2. The previous-known-good image's digest: `ghcr.io/yourstartup/pricing-api@sha256:abc123...`
3. The build pipeline's GitHub Actions workflow at `.github/workflows/release.yaml`.

Your job is to:

1. Generate an SBOM for both images.
2. Diff the SBOMs to identify what changed.
3. Identify the malicious component.
4. Check the cosign signatures and attestations on both images.
5. Determine whether the attack was: (a) a malicious dependency added in a recent commit, (b) a compromise of the build pipeline that did not change the source, or (c) a stolen cosign credential used to sign a malicious image outside of CI.
6. Write a one-paragraph incident summary in the format the SRE rotation expects (see Week 12 for the full template; for now: what happened, when, blast radius, root cause, fix).

This challenge does not require you to actually rebuild a malicious image. It asks you to reason about the data flow and document the diagnostic you would run.

---

## Step 1 — Set the scene with concrete commands

For this challenge, simulate the two images locally. Build `signed_app.py` twice with different dependencies:

```bash
# Build A: the known-good image with normal dependencies
cat > Dockerfile.good <<'EOF'
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.2 uvicorn==0.32.0
COPY signed_app.py .
ENV BUILD_VERSION=v1.0.0
CMD ["python3", "signed_app.py"]
EOF

docker build -f Dockerfile.good -t good-pricing-api:v1.0 .

# Build B: the "bad" image with an extra dependency that simulates the malicious addition
cat > Dockerfile.bad <<'EOF'
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.2 uvicorn==0.32.0 pyminer==0.0.1
COPY signed_app.py .
ENV BUILD_VERSION=v1.0.1
CMD ["python3", "signed_app.py"]
EOF

# Note: pyminer is a placeholder name; the build will fail if you try this
# literally. The point is to simulate a difference in the SBOM. To make the
# build succeed for the exercise, replace pyminer==0.0.1 with a real but
# unexpected package, e.g., flask-mongoengine==1.0.0 — something the original
# service does not need.
docker build -f Dockerfile.bad -t bad-pricing-api:v1.0.1 .
```

---

## Step 2 — Generate SBOMs for both

```bash
syft good-pricing-api:v1.0 -o spdx-json > sbom-good.spdx.json
syft bad-pricing-api:v1.0.1 -o spdx-json > sbom-bad.spdx.json

ls -lh sbom-*.json
```

---

## Step 3 — Diff the SBOMs

There is no built-in syft diff. The Anchore project has `sbom-diff` as a side experiment, but a `jq` one-liner is sufficient for this exercise.

Extract the (name, version) tuples from each:

```bash
jq -r '.packages[] | "\(.name)==\(.versionInfo)"' sbom-good.spdx.json \
  | sort > pkgs-good.txt

jq -r '.packages[] | "\(.name)==\(.versionInfo)"' sbom-bad.spdx.json \
  | sort > pkgs-bad.txt

diff pkgs-good.txt pkgs-bad.txt
```

Expected output: lines beginning with `>` for packages that exist in the bad image but not the good. Identify the suspicious additions. These are your candidates for "the malicious component".

---

## Step 4 — Scan both SBOMs

```bash
grype sbom:./sbom-good.spdx.json -o table > scan-good.txt
grype sbom:./sbom-bad.spdx.json -o table > scan-bad.txt

diff scan-good.txt scan-bad.txt
```

In a real attack, the cryptominer is typically not a known CVE — it is a *legitimate package* installed for a malicious purpose. grype will not flag it. The SBOM diff catches it because the package was not there yesterday.

This is the lesson worth internalizing: **vulnerability scanning catches known-bad. SBOM diffing catches not-where-it-was-supposed-to-be**. Both are necessary; neither is sufficient alone.

---

## Step 5 — Inspect the signatures

For the real version of this challenge, your good and bad images would each have cosign attestations. Run:

```bash
cosign verify ghcr.io/yourstartup/pricing-api@sha256:abc123... \
  --certificate-identity-regexp '^https://github\.com/yourstartup/pricing-api/.+' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com'

cosign verify ghcr.io/yourstartup/pricing-api@sha256:bad999... \
  --certificate-identity-regexp '^https://github\.com/yourstartup/pricing-api/.+' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com'
```

Three possible outcomes:

- **The bad image has no signature.** It was pushed by an attacker who bypassed CI entirely. Root cause: registry write credentials leaked, OR the admission policy was not enforced.
- **The bad image has a signature, but from a different identity.** The attacker has a valid cosign credential but it is not your CI workflow's. Root cause: a developer signed manually using their personal OIDC, OR a workflow in a different repo signed using the same registry path.
- **The bad image has a signature from the expected CI identity.** The attacker compromised your CI. Root cause: stolen GitHub Actions OIDC token (rare but possible), OR malicious commit merged to main that the CI signed correctly. Check the provenance attestation.

Fetch and inspect the provenance:

```bash
cosign verify-attestation ghcr.io/yourstartup/pricing-api@sha256:bad999... \
  --type slsaprovenance \
  --certificate-identity-regexp '^https://github\.com/yourstartup/pricing-api/.+' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
  | jq -r '.payload' | base64 -d | jq '.predicate.buildDefinition.externalParameters'
```

The provenance names the source commit. Run `git log --oneline <commit>` on that commit to see what changed. If the commit is innocuous, the attack happened in the build script, not the source — check the `.github/workflows/release.yaml` history.

---

## Step 6 — Write the incident summary

In ~150 words, write the incident summary as if posting to your team:

> **Incident: pricing-api cryptominer (2026-05-14 09:14 UTC)**
>
> *What:* The `pricing-api` Deployment ran an unsanctioned `xmrig` process across all three replicas, consuming 100% CPU. Detected by Grafana CPU alert.
>
> *Blast radius:* All `pricing-api` pods on the cluster. Estimated 23 minutes of unsanctioned compute (deployed 08:51 UTC, detected and stopped 09:14 UTC). No customer data exfiltrated.
>
> *Root cause:* The image `pricing-api@sha256:bad999...` was deployed after a CI build from commit abc123. The commit added `pyminer` (or your real example) to `requirements.txt`, justified as "needed for analytics". SBOM diff against the prior build showed the new dependency. The dependency is the malicious component.
>
> *Containment:* Rolled back to `pricing-api@sha256:abc123...`. Reverted the commit. Notified security.
>
> *Follow-up:* SBOM-diff gate added to PR check. Reviewer cannot merge a PR that adds dependencies without explicit acknowledgment.

---

## Step 7 — Reflection

Write a short note answering:

1. **Which controls from Week 10 would have caught this?** Be specific about which tool (SBOM diff, vulnerability scan, signature verification, provenance verification, cosign identity policy) and what it would have detected.

2. **Which Week 10 control would NOT have caught this, even if applied perfectly?** Explain why.

3. **Which of the two famous case studies — event-stream or ua-parser-js — is this scenario most analogous to?** Defend the comparison in two sentences.

---

## Grading rubric

- SBOM diff produced with clear identification of the changed package: **5 points**.
- grype run that contextualizes whether the change has a known CVE: **5 points**.
- Cosign verification chain reasoning is correct: **5 points**.
- Incident summary follows the what/when/blast/cause/fix pattern: **5 points**.
- Reflection answers the three questions: **5 points**.

25/25: pass.

---

## Hints

If you are stuck:

- The `jq` filter to get unique additions in the bad SBOM:
  `jq -r '.packages[] | .name' sbom-bad.spdx.json | sort -u > bad-names.txt; jq -r '.packages[] | .name' sbom-good.spdx.json | sort -u > good-names.txt; comm -23 bad-names.txt good-names.txt`
- For the "no signature" failure mode, recall Exercise 3 — `cosign tree` shows what is attached. If the bad image was pushed directly via `docker push`, no signature exists.
- For the "signature from wrong identity" failure mode, the cosign verify output explicitly says "does not match required identity regex". This is the diagnostic you would see.
