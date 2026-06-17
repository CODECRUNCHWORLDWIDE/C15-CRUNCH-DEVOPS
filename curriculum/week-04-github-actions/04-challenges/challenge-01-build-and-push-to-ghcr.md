# Challenge 1 — Build and Push to GHCR with Provenance

**Outcome.** A public GHCR image at `ghcr.io/<you>/c15-w04-chal01:1.0.0`, built multi-arch (`linux/amd64` + `linux/arm64`), tagged with the `latest`, `main`, `sha-XXXXXXX`, and three semver flavours, attested with build-provenance, and verifiable from any machine with `gh` installed.

**Estimated time.** 90 minutes.

---

## The acceptance test

A grader (you, on a clean machine, with only `docker` and `gh` installed) runs:

```bash
# 1. Pull
docker pull ghcr.io/<you>/c15-w04-chal01:1.0.0

# 2. Confirm multi-arch
docker buildx imagetools inspect ghcr.io/<you>/c15-w04-chal01:1.0.0 \
  | grep -E "linux/amd64|linux/arm64"
# Expect both lines present.

# 3. Run
docker run --rm -d -p 9000:8000 --name chal01 ghcr.io/<you>/c15-w04-chal01:1.0.0
sleep 3
curl -fsS http://localhost:9000/healthz
# Expect: {"ok": true}
docker stop chal01

# 4. Verify provenance
gh attestation verify --owner <you> \
  oci://ghcr.io/<you>/c15-w04-chal01:1.0.0
# Expect: "Verification succeeded!"

# 5. Confirm reproducibility
gh release view v1.0.0
# Expect: a release exists, notes include the digest, image link is correct.
```

All five steps must succeed without intervention. If any step fails, the challenge is not complete.

---

## Constraints

You may use the work from Exercise 3 as a starting point. The differences:

1. **The Dockerfile must build a non-trivial application.** Not the `app/main.py` from the exercise — copy your **Week 3 mini-project** code (or a public Flask / FastAPI app of comparable size). The point is to feel the cache savings on a real image, not a 30-byte echo server.
2. **The repo must use a reusable workflow.** Define the build-and-push logic in `.github/workflows/build-image.yml` with `on: workflow_call:` and call it from `deploy.yml` and `release.yml`. Both callers must be under 30 lines.
3. **Every `uses:` must be SHA-pinned.** Run `ratchet pin` before pushing. The grader will reject any major-tag pin.
4. **The workflow file must not contain a long-lived registry token.** No `GHCR_PAT` in repo secrets. The `GITHUB_TOKEN` with `packages: write` is the only auth.
5. **The release workflow must produce three semver tags, the `latest` alias, and a build-provenance attestation.**

---

## The reusable workflow

Create `.github/workflows/build-image.yml`:

```yaml
name: build-image

on:
  workflow_call:
    inputs:
      tags:
        description: "Newline-separated list of OCI tags to push"
        required: true
        type: string
      platforms:
        description: "Comma-separated list of platforms"
        required: false
        type: string
        default: "linux/amd64,linux/arm64"
    outputs:
      digest:
        description: "Pushed image digest"
        value: ${{ jobs.build.outputs.digest }}

permissions:
  contents: read
  packages: write
  id-token: write
  attestations: write

jobs:
  build:
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    outputs:
      digest: ${{ steps.build.outputs.digest }}
    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3

      - id: build
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          platforms: ${{ inputs.platforms }}
          tags: ${{ inputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - uses: actions/attest-build-provenance@v2
        with:
          subject-name: ghcr.io/${{ github.repository }}
          subject-digest: ${{ steps.build.outputs.digest }}
          push-to-registry: true
```

---

## The deploy caller

Create `.github/workflows/deploy.yml`:

```yaml
name: deploy

on:
  push:
    branches: [main]
    paths-ignore: ["docs/**", "**/*.md"]
  workflow_dispatch: {}

permissions:
  contents: read

concurrency:
  group: deploy-main
  cancel-in-progress: false

jobs:
  tags:
    runs-on: ubuntu-24.04
    outputs:
      tags: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=ref,event=branch
            type=sha,format=short
            type=raw,value=latest,enable={{is_default_branch}}

  build:
    needs: [tags]
    uses: ./.github/workflows/build-image.yml
    with:
      tags: ${{ needs.tags.outputs.tags }}
```

---

## The release caller

Create `.github/workflows/release.yml`:

```yaml
name: release

on:
  push:
    tags: ["v*"]

permissions:
  contents: write
  packages: write
  id-token: write
  attestations: write

concurrency:
  group: release-${{ github.ref }}
  cancel-in-progress: false

jobs:
  tags:
    runs-on: ubuntu-24.04
    outputs:
      tags: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}

  build:
    needs: [tags]
    uses: ./.github/workflows/build-image.yml
    with:
      tags: ${{ needs.tags.outputs.tags }}

  github-release:
    needs: [build]
    runs-on: ubuntu-24.04
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
          body: |
            **Image:** `ghcr.io/${{ github.repository }}:${{ github.ref_name }}`

            **Digest:** `${{ needs.build.outputs.digest }}`

            **Pull:** `docker pull ghcr.io/${{ github.repository }}:${{ github.ref_name }}`
```

---

## Run it

```bash
# Pin
ratchet pin .github/workflows/*.yml

# Initial deploy on main
git add .
git commit -m "challenge 01 — reusable workflow for build and push"
git push -u origin main
gh run watch

# First release
git tag v1.0.0
git push --tags
gh run watch

# Verify
gh attestation verify --owner $USER \
  oci://ghcr.io/$(gh repo view --json nameWithOwner -q .nameWithOwner):1.0.0
```

All commands should succeed. The Actions UI should show four runs (one CI, one deploy on main, one release, one re-deploy if you re-pushed after pinning).

---

## Grading rubric

- **30%** — All five acceptance-test steps pass on a clean machine.
- **20%** — `build-image.yml` is reused by both `deploy.yml` and `release.yml`; each caller is under 30 lines.
- **20%** — Every `uses:` is SHA-pinned with a human-readable comment.
- **15%** — `permissions:` are scoped at job level, not blanket-`write-all`.
- **10%** — The image is multi-arch and the manifest list shows both platforms.
- **5%** — The release notes include the image digest and pull command.

---

## Stretch goal

After the basic challenge passes, add **image signing with cosign**. The minimal addition:

```yaml
      - uses: sigstore/cosign-installer@v3
      - run: |
          cosign sign --yes \
            ghcr.io/${{ github.repository }}@${{ steps.build.outputs.digest }}
        env:
          COSIGN_EXPERIMENTAL: "1"
```

Cosign uses the same OIDC-keyless flow as `attest-build-provenance`. After it runs, your image has both a SLSA provenance attestation and a cosign signature, verifiable with `cosign verify`.

This is the 2026 shape of "I trust this image" in cloud-native systems.

---

## Common failures

- **`denied: permission_denied: write_package`** — your job is missing `permissions: packages: write`. Add it at job level.
- **`failed to verify: cannot find a matching attestation`** — the image you pulled is not the image you attested. Most likely you pushed twice and the second push overwrote the tag but not the attestation. Re-run the workflow.
- **`buildx failed to solve: arm64 step exited with 132`** — QEMU emulation tripped on a CPU feature. Either drop arm64 or pin the base image to a tag known to emulate cleanly.
- **`gh attestation verify` says "Sigstore TUF mirror unreachable"** — transient. Retry. If it persists for more than 10 minutes, file a `gh` bug.

---

When this challenge is green, you have built the artifact the rest of the course will deploy.
