# Exercise 3 — Scan with Trivy

**Goal.** Install `trivy`, scan all three images from Exercise 1, read the reports, decide which findings block a deploy, write a `.trivyignore` policy with documented exceptions, and wire `trivy` into a smoke-test script that fails on `HIGH` or `CRITICAL` CVEs.

**Estimated time.** 90 minutes.

---

## Why we are doing this

Every image you ship has some inherited vulnerability count. You did not put the CVEs there — they came in with your base image's packages — but you are the one shipping them. The first responsibility of running production containers is *knowing what is in the image*. The second is *deciding which findings block a release*.

`trivy` answers the first question. A `.trivyignore` policy answers the second. By the end of this exercise you will be able to scan an image in CI, fail the build on real findings, document the unfixable ones, and produce a SARIF report that your security team can consume.

---

## Setup

### Install `trivy`

Pick your platform:

```bash
# macOS (Homebrew)
brew install trivy

# Linux (apt / Debian-based)
sudo apt install -y wget gnupg lsb-release
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo gpg --dearmor -o /usr/share/keyrings/trivy.gpg
echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
sudo apt update && sudo apt install -y trivy

# Direct download (anywhere)
# See https://trivy.dev/latest/getting-started/installation/
```

Verify:

```bash
trivy --version
# Expect: Version: 0.55.0 or newer
```

### Prerequisites from earlier exercises

You should have three images in your local Docker daemon from Exercise 1:

```bash
docker images | grep c15-ex01
# c15-ex01    v1    ...   1.07GB
# c15-ex01    v2    ...   135MB
# c15-ex01    v3    ...   62MB
```

If you do not, go back and complete Exercise 1.

---

## Step 1 — First scan: v1 (the naive image) (~15 min)

```bash
trivy image c15-ex01:v1
```

`trivy` will download its vulnerability database on the first run (about 100 MB; cached afterward), then scan. Expect output that ends in something like:

```
Total: 187 (UNKNOWN: 0, LOW: 102, MEDIUM: 53, HIGH: 28, CRITICAL: 4)
```

The exact numbers vary day to day as new CVEs are published. The shape is consistent: **`python:3.12` ships with hundreds of known vulnerabilities** because it includes the entire Debian build toolchain, every package of which has its own CVE history.

Read the report. Three things to notice:

1. Most are `LOW` and `MEDIUM`. Almost all of those are "in theory, this package has a vulnerability; in practice, the vulnerable code path is in a CLI tool you never invoke from your app."
2. The `HIGH` and `CRITICAL` findings are usually in libraries that are linked into a lot of things: `libssl`, `glibc`, `zlib`. These are real and worth tracking.
3. The "Fixed Version" column matters more than the CVE ID. If "Fixed Version" is populated, rebuilding on a fresh base image closes it. If it is empty, no patch exists yet.

Save the full output:

```bash
trivy image c15-ex01:v1 > notes/scan-v1.txt 2>&1
```

---

## Step 2 — Scan v2 (multi-stage slim) (~5 min)

```bash
trivy image c15-ex01:v2 > notes/scan-v2.txt 2>&1
trivy image c15-ex01:v2 --severity HIGH,CRITICAL
```

Expect roughly half the total of v1's, because the apt build tools were dropped in the multi-stage transition. The remaining findings are from `python:3.12-slim`'s base packages: `libssl`, `libc`, `python3.12` itself.

---

## Step 3 — Scan v3 (distroless) (~5 min)

```bash
trivy image c15-ex01:v3 > notes/scan-v3.txt 2>&1
trivy image c15-ex01:v3 --severity HIGH,CRITICAL
```

Expect the count to drop to 0–5. Distroless ships only the minimum: libc, the CA cert bundle, the Python interpreter, and tzdata. There is simply not much *in* the image to be vulnerable.

This is the moment "distroless reduces attack surface" stops being a vendor talking point and becomes a number on your screen.

---

## Step 4 — The comparison table (~10 min)

Fill in `notes/scan-comparison.md`:

```markdown
# CVE comparison across three Dockerfile variants

| Variant | Base                                     | Total | LOW | MEDIUM | HIGH | CRITICAL |
|---------|------------------------------------------|------:|----:|-------:|-----:|---------:|
| v1      | `python:3.12`                            | 187   | 102 | 53     | 28   | 4        |
| v2      | `python:3.12-slim`                       | 73    | 38  | 24     | 9    | 2        |
| v3      | `gcr.io/distroless/python3-debian12`     | 3     | 1   | 1      | 1    | 0        |

## Findings worth tracking (HIGH+CRITICAL only)

### v3 (distroless)

- CVE-2024-XXXXX — libssl3 — Fixed in 3.0.X. **Action:** wait for next distroless base rebuild.

[... fill in your actual findings here ...]

## Conclusion

Distroless reduces total CVE surface by approximately 60x compared to the naive build.
The remaining findings in v3 are inherited from the small set of libraries distroless does
ship — almost all of them are tracked upstream and close within days of disclosure.
```

Your numbers will differ from this example. Capture the real ones.

---

## Step 5 — The CI-style invocation (~15 min)

In CI you do not want `trivy` to print a 200-line table. You want a pass/fail signal and a machine-readable artifact.

The CI-style invocation:

```bash
trivy image \
  --severity HIGH,CRITICAL \
  --exit-code 1 \
  --format sarif \
  --output trivy-report.sarif \
  c15-ex01:v2
```

The flags:

- `--severity HIGH,CRITICAL` — only fail on serious findings; do not block on `LOW`/`MEDIUM`.
- `--exit-code 1` — exit non-zero (so CI fails) when matching findings exist.
- `--format sarif` — Static Analysis Results Interchange Format. GitHub Security tab consumes this directly; Jenkins, GitLab, etc. all support it.
- `--output trivy-report.sarif` — write the report to a file as well as exiting non-zero.

Try it on each image:

```bash
trivy image --severity HIGH,CRITICAL --exit-code 1 c15-ex01:v1; echo "exit=$?"
trivy image --severity HIGH,CRITICAL --exit-code 1 c15-ex01:v2; echo "exit=$?"
trivy image --severity HIGH,CRITICAL --exit-code 1 c15-ex01:v3; echo "exit=$?"
```

Capture the three exit codes in your notes. v1 and v2 typically fail (exit 1); v3 typically passes (exit 0).

### The "first CI step" pattern

Write a `scan.sh` script that you would run as a CI job:

```bash
#!/usr/bin/env bash
# scan.sh — scan an image and fail the build on HIGH/CRITICAL findings
set -euo pipefail

IMAGE="${1:-c15-ex01:v3}"
REPORT="${2:-trivy-report.sarif}"

echo "[$(date -u +%FT%TZ)] scanning $IMAGE"

trivy image \
  --severity HIGH,CRITICAL \
  --exit-code 1 \
  --format sarif \
  --output "$REPORT" \
  --ignore-unfixed \
  "$IMAGE"

echo "[$(date -u +%FT%TZ)] scan complete: $IMAGE clean of HIGH/CRITICAL findings with fixes available"
```

Two notes on the script:

1. `--ignore-unfixed` skips CVEs that have no upstream patch. Operationally, you cannot fix a CVE that has no fix; carrying it in your CI signal is noise.
2. The script writes a SARIF report regardless of pass/fail. Even when the build passes, you want the artifact in case audit wants it.

Run it:

```bash
chmod +x scan.sh
./scan.sh c15-ex01:v3 v3-scan.sarif
```

Commit the script.

---

## Step 6 — Write a `.trivyignore` (~15 min)

Some CVEs you can prove are unreachable. Some have an upstream fix but it would require a major-version bump that breaks your app. These need *documented exceptions*, not silent suppression.

Create `.trivyignore` at the repo root:

```text
# .trivyignore
# Format: one CVE ID per line. Lines beginning with # are comments.
# EVERY ENTRY MUST HAVE: rationale, owner, expiry. No exceptions.

# ---------------------------------------------------------------
# CVE-2024-XXXXX  libssl3 timing side-channel
#   Rationale: not reachable in our threat model — we do not handle
#              attacker-controlled crypto on shared CPUs.
#   Owner: jeanstephane@aloyd.com
#   Expiry: 2026-08-01 (revisit at the next quarterly audit)
# ---------------------------------------------------------------
CVE-2024-XXXXX

# ---------------------------------------------------------------
# CVE-2024-YYYYY  python pickle deserialization
#   Rationale: we never pickle user input. Confirmed by grep of
#              the codebase 2026-05-12.
#   Owner: jeanstephane@aloyd.com
#   Expiry: 2026-11-12
# ---------------------------------------------------------------
CVE-2024-YYYYY
```

Pick one or two real CVE IDs from your earlier scan output. Add them with rationale-owner-expiry blocks like above. **Do not suppress a CVE you have not investigated.** Suppression is a load-bearing security decision; treat it like one.

Rescan with the ignorefile:

```bash
trivy image --severity HIGH,CRITICAL --exit-code 1 c15-ex01:v2
```

`trivy` looks for `.trivyignore` in the current directory automatically. The suppressed CVEs no longer appear; the rest still do.

---

## Step 7 — Bonus: generate an SBOM with `syft` (~15 min, optional)

A Software Bill of Materials is a machine-readable list of *everything* in your image. Week 11 covers supply-chain security in depth; today is a free preview.

Install `syft`:

```bash
brew install syft   # or curl the install script from https://github.com/anchore/syft
```

Generate SBOMs in SPDX format for each image:

```bash
syft c15-ex01:v1 -o spdx-json > notes/sbom-v1.spdx.json
syft c15-ex01:v2 -o spdx-json > notes/sbom-v2.spdx.json
syft c15-ex01:v3 -o spdx-json > notes/sbom-v3.spdx.json
```

Count the components:

```bash
jq '.packages | length' notes/sbom-v1.spdx.json
jq '.packages | length' notes/sbom-v2.spdx.json
jq '.packages | length' notes/sbom-v3.spdx.json
```

Expect v1 to have several hundred entries, v2 to have ~100, v3 to have under 30. Every entry is a thing that can have a CVE in the future. **Fewer things in the image, fewer future CVEs.**

---

## Acceptance criteria

You can mark this exercise done when:

- [ ] `trivy --version` returns 0.55.0 or newer.
- [ ] `notes/scan-v1.txt`, `notes/scan-v2.txt`, `notes/scan-v3.txt` exist with the raw scan output for each image.
- [ ] `notes/scan-comparison.md` exists with a comparison table populated with **your** measured numbers and at least one finding written up by hand.
- [ ] `scan.sh` exists, is executable, and runs `trivy` with `--severity HIGH,CRITICAL --exit-code 1`.
- [ ] `.trivyignore` exists with at least one suppression and proper rationale/owner/expiry annotations.
- [ ] You can articulate, in one sentence, the difference between `--ignore-unfixed` and `.trivyignore`.

---

## Common pitfalls

- **`trivy` takes forever the first time.** It downloads its vuln DB. Subsequent runs are fast.
- **`trivy` shows zero CVEs on everything.** Your vuln DB failed to download (firewall? offline?). Force a refresh: `trivy image --download-db-only`.
- **Different scan results on different days.** Expected. Upstream publishes new CVEs daily; `trivy`'s database refreshes every 6 hours by default. Pin your CI's `trivy` version and update the pin deliberately.
- **`scan.sh` exits 0 on a known-bad image.** You forgot `--exit-code 1`. By default `trivy` always exits 0 and just prints findings.
- **A scanned image has more CVEs than `docker history` would suggest.** `trivy` is finding language-package CVEs (the `flask`, `gunicorn`, `requests` in your `requirements.txt`) as well as OS-package CVEs. Both matter.

---

## What good looks like

A done version has:

- A reproducible scan against all three images with the numbers captured.
- A real, defensible policy file (`.trivyignore`) that someone could code-review.
- A `scan.sh` script that would slot into a CI pipeline tomorrow.
- One paragraph in `notes/scan-comparison.md` explaining what you would tell a colleague who asked "what's the actual security benefit of distroless?" — backed by the numbers you measured today.

---

## Why this matters

In Week 4 we wire CI/CD. The scan step you wrote today is the scan step your `build-and-push.yml` will use to gate every merge to `main`. In Week 11 we cover SBOM signing, attestation, and image signing with `cosign`. All of that builds on the scanner output you generated today.

More importantly, knowing what is in your image is the difference between "operating containers" and "running containers and hoping." After this exercise, you are operating.
