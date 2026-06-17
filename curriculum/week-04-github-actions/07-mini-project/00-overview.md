# Mini-Project — A Real CI/CD Pipeline for a Real Repo

> Build a complete CI/CD pipeline for your Week 3 mini-project: lint on every PR, matrix test on every PR, build a multi-arch Docker image on every merge to `main`, push it to GHCR with build-provenance, and cut a tagged release on every `v*` tag. Three workflows, one reusable workflow, one composite action, every action SHA-pinned, every permission scoped to the smallest job that needs it.

This is the synthesis project for Week 4. By doing it, you will touch every concept from both lectures: workflows, jobs, matrices, caching, reusable workflows, composite actions, `GITHUB_TOKEN` permissions, GHCR pushes, multi-arch builds, semver tagging, and build-provenance attestation.

**Estimated time.** 7 hours, spread across Thursday–Saturday.

---

## What you will build

The work happens **in your Week 3 mini-project repo** (`c15-week-03-localdev-<yourhandle>`). You will add a `.github/` directory containing:

1. **`.github/workflows/ci.yml`** — runs on every `pull_request` and `push: main`. Calls the reusable build-and-test workflow.
2. **`.github/workflows/build-and-test.yml`** — the reusable workflow. `on: workflow_call:`. Does lint, matrix test, and a no-push image build. Outputs the image digest.
3. **`.github/workflows/deploy.yml`** — runs on `push: main`. Calls `build-and-test`, then pushes the resulting multi-arch image to GHCR with a build-provenance attestation.
4. **`.github/workflows/release.yml`** — runs on `push: tags: ["v*"]`. Pushes semver-tagged images, cuts a GitHub Release with notes that include the digest and pull command.
5. **`.github/actions/setup-python-app/action.yml`** — composite action used by `build-and-test.yml`. Sets up Python, restores the pip cache, installs requirements.
6. **`.github/dependabot.yml`** — weekly updates for `github-actions` and `pip`.
7. **`.github/CODEOWNERS`** — your own GitHub handle as the default owner.

Plus, in the existing repo:

8. **An `actionlint.yml` config** (optional) and a passing `actionlint` run.
9. **Your existing `Dockerfile`** — must remain green; no changes required this week.
10. **`README.md` updates** — a "CI/CD" section at the top with three badges (CI status, latest release version, image pull command).

---

## Acceptance criteria

- [ ] All four workflows present in `.github/workflows/`.
- [ ] The composite action present in `.github/actions/setup-python-app/`.
- [ ] `actionlint` runs clean on every workflow file (`actionlint .github/workflows/*.yml` returns 0).
- [ ] Every `uses:` line is pinned by SHA (run `ratchet check` to verify).
- [ ] Top-level `permissions: contents: read` on every workflow.
- [ ] Job-level `permissions:` scoped up only where needed (`packages: write` on deploy/release; `id-token: write` on attest; `contents: write` on release).
- [ ] `concurrency:` block on every workflow with the appropriate `cancel-in-progress:` policy (`true` for `ci.yml`, `false` for `deploy.yml` and `release.yml`).
- [ ] The matrix in `build-and-test.yml` runs over **three Python versions** with `fail-fast: false`.
- [ ] At least three green runs in the Actions tab on `main`.
- [ ] At least one tagged release exists (`v0.1.0` minimum). The release page shows the auto-generated notes and a digest.
- [ ] `docker pull ghcr.io/<you>/<repo>:latest` and `docker pull ghcr.io/<you>/<repo>:0.1.0` both succeed from a clean machine.
- [ ] `docker buildx imagetools inspect ghcr.io/<you>/<repo>:latest` shows both `linux/amd64` and `linux/arm64`.
- [ ] `gh attestation verify --owner <you> oci://ghcr.io/<you>/<repo>:0.1.0` succeeds.
- [ ] `gh secret list` shows **zero** registry / cloud credentials. `GITHUB_TOKEN` is the only auth.
- [ ] `.github/dependabot.yml` covers `github-actions` and `pip` with weekly schedule.
- [ ] The README has three working badges and a one-paragraph CI/CD section.

---

## Sketch of the pipeline

### `ci.yml` — the thin caller

```yaml
name: ci

on:
  pull_request: { branches: [main] }
  push:         { branches: [main], paths-ignore: ["docs/**", "**/*.md"] }

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  pipeline:
    uses: ./.github/workflows/build-and-test.yml
    with:
      run-coverage: ${{ github.event_name == 'pull_request' }}
```

### `build-and-test.yml` — the reusable engine

```yaml
name: build-and-test

on:
  workflow_call:
    inputs:
      run-coverage:
        required: false
        type: boolean
        default: false
    outputs:
      image-tag:
        value: ${{ jobs.build.outputs.tag }}

permissions:
  contents: read

jobs:
  lint:
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-python-app
        with: { python-version: "3.13" }
      - run: ruff check .
      - run: ruff format --check .

  test:
    runs-on: ubuntu-24.04
    needs: [lint]
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        python: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-python-app
        with: { python-version: "${{ matrix.python }}" }
      - if: inputs.run-coverage && matrix.python == '3.13'
        run: pytest -q --cov=app --cov-report=xml --cov-fail-under=70
      - if: '!(inputs.run-coverage && matrix.python == ''3.13'')'
        run: pytest -q

  build:
    runs-on: ubuntu-24.04
    needs: [test]
    timeout-minutes: 10
    outputs:
      tag: ${{ steps.meta.outputs.version }}
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=sha,format=short
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: false
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### `deploy.yml` — push to GHCR on merge

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
  ci:
    uses: ./.github/workflows/build-and-test.yml

  push:
    needs: [ci]
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    permissions:
      contents: read
      packages: write
      id-token: write
      attestations: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=ref,event=branch
            type=sha,format=short
            type=raw,value=latest,enable={{is_default_branch}}
      - id: build
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          platforms: linux/amd64,linux/arm64
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - uses: actions/attest-build-provenance@v2
        with:
          subject-name: ghcr.io/${{ github.repository }}
          subject-digest: ${{ steps.build.outputs.digest }}
          push-to-registry: true
```

### `release.yml` — cut a release on a `v*` tag

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
  release:
    runs-on: ubuntu-24.04
    timeout-minutes: 25
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3
      - id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
      - id: build
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          platforms: linux/amd64,linux/arm64
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - uses: actions/attest-build-provenance@v2
        with:
          subject-name: ghcr.io/${{ github.repository }}
          subject-digest: ${{ steps.build.outputs.digest }}
          push-to-registry: true
      - uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
          body: |
            **Image:** `ghcr.io/${{ github.repository }}:${{ github.ref_name }}`
            **Digest:** `${{ steps.build.outputs.digest }}`

            ```
            docker pull ghcr.io/${{ github.repository }}:${{ github.ref_name }}
            ```
```

### `setup-python-app/action.yml` — the composite

```yaml
name: "Setup Python App"
description: "Checkout-aware Python setup with cache and dev requirements install."
inputs:
  python-version:
    required: false
    default: "3.13"
runs:
  using: "composite"
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ inputs.python-version }}
        cache: pip
        cache-dependency-path: |
          requirements.txt
          requirements-dev.txt
    - shell: bash
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt -r requirements-dev.txt
```

### `dependabot.yml`

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "weekly", day: "sunday" }
    groups:
      actions:
        patterns: ["*"]
  - package-ecosystem: "pip"
    directory: "/"
    schedule: { interval: "weekly", day: "sunday" }
    open-pull-requests-limit: 5
```

---

## The README updates

Replace (or add at the top of) `README.md` with:

```markdown
# c15-week-03-localdev-<yourhandle>

[![ci](https://github.com/<you>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<you>/<repo>/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/<you>/<repo>?label=release)](https://github.com/<you>/<repo>/releases)
[![image](https://img.shields.io/badge/image-ghcr.io%2F<you>%2F<repo>-blue?logo=docker)](https://github.com/<you>/<repo>/pkgs/container/<repo>)

## CI/CD

Every PR runs lint and a 3-Python matrix test. Every merge to `main` builds a multi-arch image and pushes it to `ghcr.io/<you>/<repo>:latest` with a SLSA build-provenance attestation. Every `v*` tag cuts a release with semver-tagged images. Pull:

    docker pull ghcr.io/<you>/<repo>:latest

Verify provenance:

    gh attestation verify --owner <you> oci://ghcr.io/<you>/<repo>:latest

(Rest of the existing README.)
```

---

## Grading rubric

- **30% — All workflows green on the first push.** The pipeline must work without "re-run failed jobs." A re-run after a manual fix is fine; a re-run-until-green pattern is not.
- **25% — Reuse is correctly factored.** `ci.yml` and `deploy.yml` both consume `build-and-test.yml`. The composite action is consumed from `build-and-test.yml`. No copy-pasted blocks.
- **20% — Security hygiene.** Every `uses:` SHA-pinned. Workflow-level `permissions: contents: read`. Job-level escalations justified. No registry tokens in repo secrets.
- **15% — Multi-arch image and verifiable attestation.** `imagetools inspect` shows both platforms; `gh attestation verify` succeeds.
- **10% — README and badges.** A teammate visiting the repo sees the CI status, the latest release version, and the pull command without scrolling.

---

## Common pitfalls

- **`workflow_call` workflow inherits no secrets.** If the reusable workflow needs `secrets.CODECOV_TOKEN`, the caller must pass it explicitly with `secrets: { codecov-token: ${{ secrets.CODECOV_TOKEN }} }` (or `secrets: inherit` to forward all). Forgetting this is the most common reusable-workflow bug.
- **`permissions:` at workflow level overrides per-job permissions.** If you set `permissions: contents: read` at workflow level and then `permissions: packages: write` at job level, you get **only** `packages: write` on that job — `contents` is *removed*. The fix is to set both: `permissions: { contents: read, packages: write }`.
- **Composite action steps need `shell:`.** A composite-action step without `shell:` is a parser error. Always include `shell: bash`.
- **`docker/metadata-action` does not push tags; it computes them.** If you forget to feed `steps.meta.outputs.tags` into `docker/build-push-action`'s `tags:` input, no tags get pushed and you get only the digest.
- **`actions/attest-build-provenance` needs `id-token: write` and `attestations: write`.** Both. Missing either fails with a confusing 403 from the Sigstore TUF mirror.
- **The first `release.yml` run is slow.** QEMU emulation for `arm64` adds 2–3 minutes the first time, before any cache. Do not time it on the first run.
- **`paths-ignore:` does not stop a workflow that was already triggered.** If you push a commit that touches `docs/**` and the workflow has `paths-ignore: ["docs/**"]`, it does not run — but a *required* check still shows as "Expected" on the PR. Use `paths-ignore:` for cost savings, not for required-check semantics.

---

## Submission

Push the repo, then open an issue with three things:

1. The repo URL.
2. The URL of one green CI run, one green deploy run, and one green release run.
3. The output of `docker buildx imagetools inspect ghcr.io/<you>/<repo>:0.1.0`.

We grade by `git clone`-ing on a clean machine, running `gh attestation verify`, and pulling the image. If those three succeed, you have shipped Week 4.

Continue to **Week 5 — Kubernetes Without the Helm Chart Yet** once the project is submitted. Week 5 takes the image your CI pipeline now pushes to GHCR every merge and runs it on a real cluster — and the merge-to-`main` event you wired this week becomes the input to a deploy event on a cluster.
