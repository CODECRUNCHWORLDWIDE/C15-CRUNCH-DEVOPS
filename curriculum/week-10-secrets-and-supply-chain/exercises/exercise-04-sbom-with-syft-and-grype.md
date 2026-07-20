# Exercise 4 — SBOM Generation with syft, Vulnerability Scan with grype, Attestation with cosign

**Time:** 75 minutes (20 min reading, 40 min hands-on, 15 min write-up).
**Cost:** $0.00.
**Cluster:** Host-only; uses the image from Exercise 3.

---

## Goal

Generate an SBOM for the `w10-signed-app` image in both SPDX-JSON and CycloneDX-JSON formats. Verify the SBOM satisfies the CISA Minimum Elements using the `sbom_check.py` script. Scan the SBOM for known vulnerabilities with grype. Attach the SBOM and the scan results to the image as signed cosign attestations.

After this exercise you should have:

- `sbom.spdx.json` and `sbom.cdx.json` files on disk.
- `sbom_check.py` reporting `ok: true` for each (or a list of any missing fields).
- `scan.json` containing grype's findings against the SBOM.
- Two cosign attestations attached to the image, one for the SBOM and one for the vulnerability scan.
- A `cosign verify-attestation` run that succeeds and prints the SBOM payload.

---

## Step 1 — Install syft and grype

```bash
brew install syft grype                           # macOS
# or:
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin
curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin

syft version
grype version
```

`syft --help` and `grype --help` both have short, well-organized output. Skim them.

---

## Step 2 — Generate the SBOM (both formats)

Reuse the `$IMAGE_BY_DIGEST` from Exercise 3 (or rebuild and re-pin if you destroyed your shell):

```bash
# If you need to restate the image-by-digest:
DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' $IMAGE | cut -d@ -f2)
export IMAGE_BY_DIGEST=$(echo $IMAGE | cut -d: -f1)@$DIGEST
echo "image: $IMAGE_BY_DIGEST"
```

Generate the SBOMs:

```bash
syft $IMAGE_BY_DIGEST -o spdx-json > sbom.spdx.json
syft $IMAGE_BY_DIGEST -o cyclonedx-json > sbom.cdx.json
syft $IMAGE_BY_DIGEST -o syft-json > sbom.syft.json
```

Look at the sizes:

```bash
ls -lh sbom.*.json
```

You should see ~50-200 KB each, depending on the base image. The slim Python 3.12 base has ~80-100 packages; with the FastAPI dependencies, ~120-150.

Browse one of them:

```bash
jq '.packages[0:3]' sbom.spdx.json
jq '.components[0:3]' sbom.cdx.json
```

The SPDX shape names "packages"; the CycloneDX shape names "components". Both contain the PURL identifier, the version, the license (when known), and the supplier (when known).

---

## Step 3 — Verify the SBOMs satisfy CISA Minimum Elements

The `sbom_check.py` script in this folder checks each SBOM for the seven required fields per component.

```bash
python3 sbom_check.py sbom.spdx.json
python3 sbom_check.py sbom.cdx.json
```

Expected output (abbreviated):

```
---
file: sbom.spdx.json
  format: spdx
  timestamp_present: True
  author_present: True
  component_count: 142
  components_with_missing_fields: 0
  ok: True
```

If `ok: True` for both, your SBOMs meet the CISA floor. If not, the report lists which fields are missing on which components. The common shortfall is the **supplier name** for distro packages; syft fills this in best-effort, but some apk packages lack a recorded supplier. The right fix in a real pipeline is to enrich the SBOM with a follow-up pass (e.g., using Anchore's enterprise SBOM enrichment), or to flag the unsourced packages as "unknown supplier" and accept the gap with a documented exception.

---

## Step 4 — Scan the SBOM with grype

The first run downloads the vulnerability database (~200 MB) from <https://anchore.com/oss/grype/>. Subsequent runs use the cache.

```bash
grype sbom:./sbom.spdx.json
grype sbom:./sbom.cdx.json
```

Expected output:

```
NAME       INSTALLED  FIXED-IN  TYPE      VULNERABILITY    SEVERITY
openssl    3.0.10-r3  3.0.13-r0  apk      CVE-2023-5363    High
zlib       1.2.13-r0  (none)     apk      CVE-2023-45853   Critical
...
```

The exact findings depend on the base image's age and the date you run this. Recent `python:3.12-slim` images have a handful of Medium and Low findings and (typically) zero High or Critical.

Export the scan results as JSON for downstream use:

```bash
grype sbom:./sbom.spdx.json -o json > scan.json
jq '. | {summary: .descriptor, count: (.matches | length)}' scan.json
```

The `scan.json` file is what we attach to the image as an attestation.

To enforce a policy in a CI pipeline:

```bash
grype sbom:./sbom.spdx.json --fail-on high
# Exit code is 0 if no High-or-Critical findings; non-zero otherwise.
```

In a CI workflow, this is the gate: a build that brings in a High-severity CVE in a dependency cannot promote past this step without an explicit exception.

---

## Step 5 — Manage exceptions

Create `.grype.yaml` in the project root to suppress findings you have triaged as not-exploitable-in-context:

```bash
cat > .grype.yaml <<'EOF'
ignore:
  - vulnerability: CVE-2023-XXXXX
    package:
      name: example-package
      version: 1.0.0
    fix-state: not-fixed
    # We do not call this codepath; tracked in JIRA-12345.
EOF
```

Re-run grype with the config:

```bash
grype --config .grype.yaml sbom:./sbom.spdx.json
```

The suppressed finding disappears from the table. In a real pipeline, the `.grype.yaml` is committed to Git, reviewed at PRs, and the exceptions audited quarterly.

---

## Step 6 — Attach the SBOM as a cosign attestation

Sign the SBOM as an attestation attached to the image:

```bash
cosign attest --predicate sbom.spdx.json \
  --type spdxjson \
  $IMAGE_BY_DIGEST
```

Cosign will:

1. Wrap the SBOM in an in-toto Statement (`predicateType: https://spdx.dev/Document`).
2. Open the browser for OIDC authentication (or reuse a cached cert if you signed recently).
3. Get a Fulcio cert for your identity.
4. Sign the Statement.
5. Push the attestation to the registry alongside the image.
6. Record the attestation in Rekor.

Attach the vulnerability-scan attestation:

```bash
cosign attest --predicate scan.json \
  --type vuln \
  $IMAGE_BY_DIGEST
```

The vuln type is one of the predicate types defined in <https://github.com/in-toto/attestation/tree/main/spec/predicates>.

---

## Step 7 — Verify both attestations

```bash
cosign verify-attestation $IMAGE_BY_DIGEST \
  --type spdxjson \
  --certificate-identity-regexp '<your-oidc-email-regex>' \
  --certificate-oidc-issuer-regexp '.*' \
  | jq -r '.payload' | base64 -d | jq .

cosign verify-attestation $IMAGE_BY_DIGEST \
  --type vuln \
  --certificate-identity-regexp '<your-oidc-email-regex>' \
  --certificate-oidc-issuer-regexp '.*' \
  | jq -r '.payload' | base64 -d | jq '.predicate.matches[0:3]'
```

The first command should print the full SPDX SBOM, recovered from the attestation. The second should print the first three vulnerability matches.

A downstream consumer (a cluster's admission webhook, a developer running `cosign verify-attestation` from the command line) can now:

1. Confirm the image was signed by a known identity.
2. Confirm an SBOM exists and was signed by the same identity.
3. Confirm a vulnerability scan exists and was signed by the same identity.
4. Read the scan payload and run policy: "no High-or-Critical findings without exception".

This is the SLSA L2 + SBOM + vuln-scan posture. Every component is open source. Every artifact is signed and verifiable.

---

## Step 8 — Inspect the image's attached artifacts

The registry now holds the image plus three OCI artifacts: a signature, an SPDX attestation, and a vuln attestation. Browse them:

```bash
cosign tree $IMAGE_BY_DIGEST
```

Expected output:

```
ghcr.io/alice/w10-signed-app@sha256:abc123...
├── 🍒 Attestations for an image tag: sha256-abc123....att
│   └── 🍒 sha256:def456...
└── 🔐 Signatures for an image tag: sha256-abc123....sig
    └── 🔐 sha256:ghi789...
```

This is the OCI 1.1 "referrers" view — the registry's index of what is attached to which digest. Tools like `crane` and `oras` expose the same view.

---

## Step 9 — Reflection

Write two paragraphs in your notes:

1. **For the image you just scanned, what was the highest-severity finding?** Was it in a library the application actually calls? If yes, what is the fix path? If no, would you ignore it in `.grype.yaml`? Why or why not.

2. **What does the SBOM attestation *not* protect against?** Trace through: an attacker who has compromised the build system, an attacker who has stolen the maintainer's GitHub credentials, a malicious dependency added in a future build. Which of the three would the SBOM detect?

---

## Cleanup

Nothing to clean up unless you want to. The SBOM files, the scan.json, and the attestations are all small and harmless to keep.

If you want to free the disk space the grype database takes:

```bash
grype db delete
```

---

## Cost summary

```
+-------------------------------------+
|  syft + grype binaries      $0.00   |
|  cosign attestation         $0.00   |
|  Fulcio (public OpenSSF)    $0.00   |
|  Rekor (public OpenSSF)     $0.00   |
|  Vulnerability DB           $0.00   |
|                                     |
|  Total                      $0.00   |
+-------------------------------------+
```
