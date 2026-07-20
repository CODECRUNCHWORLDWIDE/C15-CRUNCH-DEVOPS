# Exercise 3 — Deploy on Merge

**Goal.** Wire a workflow that builds a Docker image and pushes it to GitHub Container Registry on every merge to `main`. Wire a second workflow that cuts a release on a `v*` tag. Confirm both work end to end: `docker pull ghcr.io/<you>/<repo>:latest` returns the image, and a `git tag v0.1.0` produces a GitHub Release plus a versioned image.

**Estimated time.** 120 minutes (60 min building, 30 min experimenting and reading logs, 30 min writing up).

---

## Why we are doing this

Exercises 1 and 2 produced **artifacts inside the runner** — test output, coverage reports, a built image that never left the VM. None of that is a delivery. Exercise 3 is the first time your CI ships something a third party can consume — an image in a public registry, addressable by tag, pulled by `docker pull`. This is the line between "we have CI" and "we have a delivery pipeline."

We use the `GITHUB_TOKEN` (not a personal access token, not a long-lived secret) to authenticate to GHCR. We use `docker/metadata-action` to generate the OCI tag set. We use `docker/build-push-action` with `cache-from=gha,cache-to=gha,mode=max` to keep build times reasonable. And we use `actions/attest-build-provenance` to ship a signed provenance attestation alongside the image — the 2024+ baseline for any image you expect to deploy.

---

## Setup

Continue from Exercise 2, or start fresh:

```bash
mkdir -p ~/c15/week-04/ex-03-deploy
cd ~/c15/week-04/ex-03-deploy
git init -b main
gh repo create c15-week-04-ex03-$USER --public --source=. --remote=origin
```

Copy your Exercise 2 source files. You need one more file: a Dockerfile.

`Dockerfile` (multi-stage, slim, non-root, pinned):

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.13.0-slim-bookworm AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.13.0-slim-bookworm AS runtime

RUN useradd --create-home --shell /bin/bash app
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/ ./app/
USER app
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=2)"

CMD ["python", "-m", "flask", "--app", "app.main", "run", "--host=0.0.0.0", "--port=8000"]
```

`.dockerignore`:

```text
.git
.github
.venv
__pycache__
*.pyc
.pytest_cache
.ruff_cache
notes
```

Verify locally:

```bash
docker build -t ex03:local .
docker run --rm -d -p 8000:8000 --name ex03 ex03:local
sleep 3
curl -fsS http://localhost:8000/healthz
docker stop ex03
```

Should return `{"ok": true}`.

---

## Step 1 — The `deploy.yml` workflow (15 min)

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
  build-and-push:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
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

Commit and push:

```bash
git add .
git commit -m "exercise 03 — deploy on merge"
git push -u origin main
```

Watch the run:

```bash
gh run watch
```

Expect a green run in ~90 seconds (cold cache). Verify the image landed:

```bash
docker pull ghcr.io/$(gh repo view --json nameWithOwner -q .nameWithOwner):latest
docker run --rm -d -p 8001:8000 --name pulled ghcr.io/$(gh repo view --json nameWithOwner -q .nameWithOwner):latest
sleep 3
curl -fsS http://localhost:8001/healthz
docker stop pulled
```

You just pulled and ran an image that *you did not build on this machine*. That image was built on a GitHub-hosted runner, signed by GitHub's OIDC issuer, pushed to a public registry, and addressable by tag from anywhere in the world.

---

## Step 2 — Inspect the metadata and the attestation (10 min)

Look at the tags `metadata-action` generated. In the run UI, open the `meta` step's output. You should see something like:

```text
ghcr.io/<you>/<repo>:main
ghcr.io/<you>/<repo>:sha-a7c3f1d
ghcr.io/<you>/<repo>:latest
```

Three tags, one image. The `:main` is "head of the default branch." The `:sha-a7c3f1d` is the immutable per-commit tag. The `:latest` is the alias `metadata-action` adds because of `type=raw,value=latest,enable={{is_default_branch}}`.

List the images in the registry:

```bash
gh api -X GET /users/$USER/packages/container/$(gh repo view --json name -q .name)/versions \
  | jq '.[] | {tags: .metadata.container.tags, digest: .name}'
```

Note the three tags all point to one digest. That is the contract: identical content, multiple names.

Verify the build-provenance attestation:

```bash
gh attestation verify \
  --owner $USER \
  oci://ghcr.io/$(gh repo view --json nameWithOwner -q .nameWithOwner):latest
```

Expect a "Verification succeeded!" line. The verifier checked:

- The attestation is signed by GitHub's OIDC issuer.
- The `sub` claim ties the attestation to *this* workflow on *this* repo on *the default branch*.
- The image digest in the attestation matches the digest you are about to deploy.

If any link in that chain were broken, the verifier would refuse. That is the supply-chain story end to end.

---

## Step 3 — Multi-arch (15 min)

The image is currently `linux/amd64` only. Make it multi-arch.

Edit the workflow. Add the QEMU setup step before Buildx:

```yaml
      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3
```

Add `platforms:` to the `build-push-action` step:

```yaml
      - id: build
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          platforms: linux/amd64,linux/arm64
          # ... rest as before
```

Push. The build now takes longer (the `arm64` build under QEMU emulation is 4–5x slower than native). For our Flask image, expect ~3–4 minutes cold cache, ~30 seconds warm.

After it lands, verify the manifest list:

```bash
docker buildx imagetools inspect ghcr.io/$(gh repo view --json nameWithOwner -q .nameWithOwner):latest
```

Expect output like:

```text
Name:      ghcr.io/.../ex03:latest
MediaType: application/vnd.oci.image.index.v1+json
Digest:    sha256:abc...

Manifests:
  Name:      ghcr.io/.../ex03:latest@sha256:def...
  MediaType: application/vnd.oci.image.manifest.v1+json
  Platform:  linux/amd64

  Name:      ghcr.io/.../ex03:latest@sha256:ghi...
  MediaType: application/vnd.oci.image.manifest.v1+json
  Platform:  linux/arm64
```

One tag, two platforms. Pull from an Apple Silicon laptop: you get the arm64 variant transparently.

---

## Step 4 — The `release.yml` workflow (15 min)

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
  release:
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

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

            **Pull:**
            ```
            docker pull ghcr.io/${{ github.repository }}:${{ github.ref_name }}
            ```

            **Verify provenance:**
            ```
            gh attestation verify --owner ${{ github.repository_owner }} \
              oci://ghcr.io/${{ github.repository }}:${{ github.ref_name }}
            ```
```

Commit and push:

```bash
git add .github/workflows/release.yml
git commit -m "add release workflow"
git push
```

Then cut a release:

```bash
git tag v0.1.0
git push --tags
```

The `release` workflow fires. Watch it:

```bash
gh run watch
```

Expect ~3–4 minutes. When it finishes, check:

1. The image:
   ```bash
   docker pull ghcr.io/$(gh repo view --json nameWithOwner -q .nameWithOwner):0.1.0
   ```
2. The release:
   ```bash
   gh release view v0.1.0
   ```
3. The attestation:
   ```bash
   gh attestation verify --owner $USER \
     oci://ghcr.io/$(gh repo view --json nameWithOwner -q .nameWithOwner):0.1.0
   ```

You should see three semver tags pushed (`0.1.0`, `0.1`, `0`), a GitHub Release with auto-generated notes, and a verified attestation.

---

## Step 5 — Watch a real "merge to main" cycle (15 min)

Treat the next change like a real PR:

```bash
git checkout -b feature/banner
# Edit app/main.py to add a banner endpoint
```

`app/main.py`:

```python
@app.get("/banner")
def banner() -> dict:
    return {"banner": "C15 W04 EX03 — deploy on merge demo"}
```

Add a test:

```python
def test_banner():
    client = app.test_client()
    resp = client.get("/banner")
    assert resp.status_code == 200
    assert "banner" in resp.json
```

```bash
git commit -am "add /banner endpoint"
git push -u origin feature/banner
gh pr create --fill
```

The PR's CI runs (from Exercise 1's `ci.yml`, if you ported it here; otherwise just the `deploy.yml`'s `paths-ignore:` filter will skip non-essential changes). Once green, merge:

```bash
gh pr merge --merge --delete-branch
```

The `deploy.yml`'s `push: branches: [main]` trigger fires. The image gets a new `sha-XXX` tag and the `:latest` tag is reassigned to the new digest.

Verify:

```bash
docker pull ghcr.io/$(gh repo view --json nameWithOwner -q .nameWithOwner):latest
docker run --rm -d -p 8002:8000 --name banner-check ghcr.io/$(gh repo view --json nameWithOwner -q .nameWithOwner):latest
sleep 3
curl -fsS http://localhost:8002/banner
docker stop banner-check
```

The `/banner` endpoint should respond. You did not type `docker build` or `docker push` once during that cycle. The pipeline did it.

---

## Step 6 — Cut a second release (10 min)

```bash
git tag v0.2.0
git push --tags
```

Wait for the workflow. Verify:

```bash
gh release list --limit 5
docker pull ghcr.io/$(gh repo view --json nameWithOwner -q .nameWithOwner):0.2.0
```

Note that the `:latest` tag from the `deploy.yml` and the `:0.2.0` tag from the `release.yml` may point to **different digests** if the release was cut from a commit before the most recent `main` push. That is correct behavior: `:latest` follows `main`, `:0.2.0` follows the tag.

In `notes/two-pipelines.md`, write 3–4 sentences explaining the relationship between `:latest`, `:main`, `:sha-XXX`, and `:0.2.0`. Which one would you use in a `Dockerfile FROM` line? Which in a Kubernetes manifest? Which in a `docker-compose.yml`? Why?

---

## Step 7 — Pin and Dependabot (10 min)

```bash
ratchet pin .github/workflows/deploy.yml .github/workflows/release.yml
```

Ensure `.github/dependabot.yml` covers `github-actions`. Push.

---

## Acceptance checklist

- [ ] `deploy.yml` runs on `push: branches: [main]` and pushes a multi-arch image to GHCR.
- [ ] `release.yml` runs on `push: tags: ["v*"]` and creates a GitHub Release.
- [ ] Top-level `permissions: contents: read`; job-level scopes-up as needed.
- [ ] `concurrency: cancel-in-progress: false` on both deploy and release.
- [ ] `docker/metadata-action` generates branch, sha, semver, and `latest` tags appropriately.
- [ ] `actions/attest-build-provenance@v2` ships an attestation with every build.
- [ ] `gh attestation verify` succeeds on at least one image.
- [ ] At least two releases (`v0.1.0` and `v0.2.0`) exist with auto-generated notes.
- [ ] `:latest` is reassigned on every push to `main`; `:0.2.0` is immutable.
- [ ] `notes/two-pipelines.md` answers the tag-usage question.
- [ ] Every `uses:` is SHA-pinned.

---

## Reflection questions

1. The `GITHUB_TOKEN` was sufficient to push to GHCR; no PAT was created. What would change if you wanted to push to **Docker Hub** instead? Two sentences.
2. `concurrency: cancel-in-progress: false` on the release workflow is the opposite of Exercise 1's CI default. Defend the choice in one paragraph.
3. The `metadata-action` step generates four tag types from one Git ref. Predict the tags for a push to a branch called `feature/oidc`. Predict the tags for a push of tag `v2.3.1-rc.1`. (Hint: the `{{version}}` template includes prerelease suffixes; `{{major}}.{{minor}}` does not.)
4. The build-provenance attestation includes the workflow's `sub` claim. What protections does this provide against a malicious actor who steals a developer's GitHub credentials and tries to push a backdoored image to your registry? What does it *not* protect against? (Two sentences each.)

Write the answers in `notes/reflection.md`.

---

## What this exercise reps

Exercise 1 wrote a workflow. Exercise 2 fanned it out. Exercise 3 made it produce a delivery. That third move — from "the build succeeded on the runner" to "an artifact exists in a public registry, addressable by tag, signed for provenance, and reproducible from this exact Git commit" — is the move that turns a CI tutorial into an operating pipeline. Every workflow you write in the rest of the course will start from the shape you have in this exercise.

When done, push the repo and continue to the [Saturday challenge](../challenges/challenge-01-build-and-push-to-ghcr.md) and the [mini-project](../mini-project/README.md).
