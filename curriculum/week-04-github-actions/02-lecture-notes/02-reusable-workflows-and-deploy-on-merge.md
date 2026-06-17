# Lecture 2 — Reusable Workflows, OIDC, and Deploy on Merge

> **Outcome:** You can factor a 200-line workflow into a reusable `workflow_call` workflow and a composite action, consume both from a thin caller workflow, push a multi-arch image to GHCR on merge to `main` with no long-lived registry credentials, and cut a tagged release with a single `git tag v1.2.3 && git push --tags`. You can wire OIDC from a workflow to AWS (or Azure, or GCP) and delete every `AWS_ACCESS_KEY_ID` from your repo secrets in the same PR.

Lecture 1 gave you the file shape — one workflow, one set of jobs, one matrix, one cache. Lecture 2 covers the **delivery** half of CI/CD: how that file becomes a pipeline that **ships** something, on every merge, with no human at the console. Two things change from Lecture 1: (a) we factor for reuse, because a real team has more than one service and you do not write the same `lint + test + build` block twice; (b) we wire the workflow into a registry and a cloud, with the modern auth shape — OIDC federation — that has replaced long-lived secrets across the industry.

We continue with **GitHub-hosted Ubuntu 24.04 runners** and the **Actions schema as of 2026**. We assume your repo has a working Lecture-1-style `ci.yml`. By the end of this lecture you will have, on top of that, a `release.yml` and a `deploy.yml`, both calling into one or two reusable workflows, all green, with `permissions:` scoped correctly.

---

## 1. Why factor for reuse at all

If your org has one service, one workflow per concern (`ci.yml`, `release.yml`, `deploy.yml`) is fine. The moment you have three services that share 80% of the build+test logic, the choice is between:

1. **Copy-paste.** Three near-identical `ci.yml`s. The first time you fix a bug in one, you forget to fix it in the others, and the second-oldest copy quietly diverges. This is the most common shape in real repos and it is the wrong one.
2. **A reusable workflow** in a separate `.yml` invoked from three thin caller workflows. One source of truth, three call sites.
3. **A composite action** wrapping the shared steps. Smaller surface, useful inside one workflow that has the same setup repeated across jobs.

Pick (2) when the unit of reuse is **a whole pipeline** (lint + test + build). Pick (3) when the unit is **a handful of steps** (setup-python + pip-install + ruff). Both are first-class primitives. Both are underused.

> **Status panel — the choice, in one line**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  Whole pipeline shared?     → reusable workflow     │
> │  A few steps shared?        → composite action      │
> │  Used once in one repo?     → keep it inline        │
> │  Used across many repos?    → publish as Marketplace│
> └─────────────────────────────────────────────────────┘
> ```

---

## 2. Composite actions — the smaller primitive

A composite action lives at `.github/actions/<name>/action.yml`. The whole shape:

```yaml
# .github/actions/setup-python-app/action.yml
name: "Setup Python App"
description: "Set up Python with pip cache and install requirements."
inputs:
  python-version:
    description: "Python version to install"
    required: false
    default: "3.13"
  requirements:
    description: "Requirements files to install"
    required: false
    default: "requirements.txt requirements-dev.txt"

runs:
  using: "composite"
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ inputs.python-version }}
        cache: pip

    - name: Install
      shell: bash
      run: |
        pip install --upgrade pip
        for f in ${{ inputs.requirements }}; do
          if [ -f "$f" ]; then pip install -r "$f"; fi
        done
```

Use it from any workflow in the same repo:

```yaml
- uses: actions/checkout@v4
- uses: ./.github/actions/setup-python-app
  with:
    python-version: "3.13"
```

Three things to know:

1. **Steps in a composite must declare `shell:`.** Unlike a normal workflow, the composite action has no default shell.
2. **Inputs are strings.** A `default: true` value is the *string* `"true"`. Compare with `== 'true'`, not `== true`.
3. **The composite action runs in the *caller's* working directory** with the *caller's* `GITHUB_TOKEN`. It is not isolated. If you wrote `rm -rf .` in a composite action, it would erase the caller's checkout. Treat it as inline code, not a sandbox.

To publish a composite action as a Marketplace action, push the `action.yml` to the *root* of a separate repo (not `.github/actions/…`), tag a release, and others can `uses: yourorg/yourrepo@v1`.

---

## 3. Reusable workflows — the bigger primitive

A reusable workflow lives at `.github/workflows/<name>.yml` like any other workflow, but declares `on: workflow_call:` instead of (or alongside) `on: push:`. Full shape:

```yaml
# .github/workflows/build-and-test.yml
name: build-and-test

on:
  workflow_call:
    inputs:
      python-version:
        description: "Python version to test"
        required: false
        type: string
        default: "3.13"
      run-coverage:
        required: false
        type: boolean
        default: false
    outputs:
      image-digest:
        description: "Digest of the built image (when push: true)"
        value: ${{ jobs.build.outputs.digest }}
    secrets:
      # Pass-through; declared so the caller knows what we need
      codecov-token:
        required: false

permissions:
  contents: read

jobs:
  lint:
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-python-app
        with:
          python-version: ${{ inputs.python-version }}
      - run: ruff check .

  test:
    runs-on: ubuntu-24.04
    needs: [lint]
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/setup-python-app
        with:
          python-version: ${{ inputs.python-version }}
      - run: pytest -q --cov=app

      - if: inputs.run-coverage
        uses: codecov/codecov-action@v4
        with:
          token: ${{ secrets.codecov-token }}

  build:
    runs-on: ubuntu-24.04
    needs: [test]
    timeout-minutes: 10
    outputs:
      digest: ${{ steps.build.outputs.digest }}
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - id: build
        uses: docker/build-push-action@v6
        with:
          context: .
          push: false
          tags: app:ci-${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

Call it from a thin caller workflow:

```yaml
# .github/workflows/ci.yml
name: ci

on:
  pull_request: { branches: [main] }
  push:         { branches: [main] }

permissions:
  contents: read

jobs:
  pipeline:
    uses: ./.github/workflows/build-and-test.yml
    with:
      python-version: "3.13"
      run-coverage: ${{ github.event_name == 'pull_request' }}
    secrets:
      codecov-token: ${{ secrets.CODECOV_TOKEN }}
```

Notes:

- The caller's `uses:` points at the reusable workflow file. `./.github/workflows/x.yml` works for same-repo; `owner/repo/.github/workflows/x.yml@v1` works for cross-repo.
- Inputs are typed (`string`, `number`, `boolean`). Booleans are real booleans, unlike composite-action inputs.
- Secrets must be passed explicitly with `secrets:` (or `secrets: inherit` to forward all of the caller's). The default is *no* secrets — a reusable workflow you `uses:` from elsewhere has none of your secrets unless you pass them.
- The reusable workflow can declare `outputs:` that map to a downstream job's outputs. The caller reads them as `${{ needs.<jobid>.outputs.<key> }}` on the calling job.

The **single most important property** of a reusable workflow: it pins the *workflow*, not just an action. When you upgrade `actions/checkout` in the reusable workflow, every caller picks it up on the next run. That is a feature (one upgrade, many consumers) and a danger (one bug, many breakages). Pin reusable workflows by tag when used cross-repo, exactly like Marketplace actions.

---

## 4. Reusable workflow vs composite action — the decision table

| Property | Composite action | Reusable workflow |
|----------|------------------|-------------------|
| File path | `.github/actions/<n>/action.yml` | `.github/workflows/<n>.yml` |
| Unit of reuse | A few steps | Whole jobs (one or many) |
| Caller scope | Steps inside one job | Jobs at workflow level |
| Inherits `GITHUB_TOKEN`? | Yes (caller's) | No — call site must pass `secrets:` |
| Can run multiple jobs? | No — composite is one step group | Yes — `jobs:` with `needs:` DAGs |
| Triggers itself? | No | Yes (it is a workflow; you can give it `on: push` and `on: workflow_call`) |
| Pins to which level? | The action ref | The workflow ref |
| Marketplace-publishable? | Yes (own repo) | No — workflows can be cross-repo but not Marketplace |

Rule of thumb: **a composite action is a function; a reusable workflow is a service.** If the shared code is "do these five steps with these parameters," it is a function. If it is "run a whole CI pipeline with these inputs," it is a service.

---

## 5. The `GITHUB_TOKEN`, in depth

The runner mints a `GITHUB_TOKEN` on every run. It is a GitHub App installation token scoped to the workflow run. Its capabilities are controlled by:

1. **Repo settings** — the org or repo admin sets the *default* permissions baseline. After 2023 the default is `read`; legacy repos may still be `write`.
2. **Workflow-level `permissions:`** — narrows or expands within the repo default.
3. **Job-level `permissions:`** — narrows or expands within the workflow level.

The token expires at the end of the run. There is no way to extend it. There is no way to read its value safely — it is exposed as `${{ secrets.GITHUB_TOKEN }}` and `${{ github.token }}`, both treated as secrets and redacted from logs.

What the `GITHUB_TOKEN` can do, depending on scope:

| Scope | Cap | Example use |
|-------|-----|-------------|
| `contents: read` | Read repo files via the API | Clone via `actions/checkout` |
| `contents: write` | Push commits, tags, releases | Create a release |
| `pull-requests: write` | Comment on, close, merge PRs | The auto-comment bot |
| `issues: write` | Open / close issues | A flaky-test reporter |
| `packages: write` | Push to GHCR | The deploy-on-merge job |
| `id-token: write` | Mint an OIDC JWT for cloud federation | The OIDC step |
| `attestations: write` | Sign and publish artifact attestations | The supply-chain step |
| `pages: write` | Deploy GitHub Pages | The docs-site job |

The right default at workflow level is `contents: read`. Scope up at job level. Never `permissions: write-all`.

---

## 6. Secrets and variables — repo, environment, organization

GitHub Actions has three storage tiers for secrets and non-secret variables:

| Tier | Where | When to use |
|------|-------|-------------|
| **Repo** | Repo settings → Secrets and variables → Actions | Repo-only credentials (e.g., the codecov token) |
| **Environment** | Settings → Environments → `<env>` → Secrets | Per-environment credentials, gated by an approval rule |
| **Organization** | Org settings → Secrets | Shared across all repos in the org (e.g., an NPM publish token) |

Use **environments** for any secret that gates a deploy. A GitHub Actions Environment is more than a folder of secrets; it can require:

- Approval from one or more named reviewers.
- A wait timer (e.g., 30 minutes between staging and prod).
- A branch restriction (e.g., only `main` can deploy to prod).

The shape on the job:

```yaml
jobs:
  deploy-prod:
    runs-on: ubuntu-24.04
    environment:
      name: production
      url: https://app.example.com
    steps:
      - uses: actions/checkout@v4
      - name: Deploy
        run: ./scripts/deploy.sh
        env:
          API_TOKEN: ${{ secrets.PROD_API_TOKEN }}
```

When this job starts, the Actions UI shows a "Waiting for approval" banner if the environment has reviewers configured. A named reviewer clicks **Approve and deploy**, and only then does the job pick up the environment's secrets and run. This is the GitHub-native primitive for **deployment gates**; it replaces the bespoke "Slack-approve-via-button" workflows you may have seen in 2021.

`vars` is the non-secret sibling of `secrets`. Use it for URLs, region names, log levels — anything you want to set per-environment but is not a credential. The expression is `${{ vars.STAGING_URL }}`.

---

## 7. The `GITHUB_TOKEN` lets you push to GHCR

GitHub Container Registry is at `ghcr.io/<owner>/<image>`. To push from a workflow, you need:

```yaml
permissions:
  contents: read
  packages: write

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
        type=ref,event=pr
        type=semver,pattern={{version}}
        type=sha,format=short

  - uses: docker/build-push-action@v6
    with:
      context: .
      push: true
      tags: ${{ steps.meta.outputs.tags }}
      labels: ${{ steps.meta.outputs.labels }}
      cache-from: type=gha
      cache-to: type=gha,mode=max
```

That is the entire deploy-on-merge surface for GHCR. Six steps. No registry credentials in repo secrets. The `GITHUB_TOKEN` with `packages: write` is exactly enough to push to the repo owner's GHCR namespace, and only there.

The `docker/metadata-action` is doing real work. It reads the Git ref and generates the OCI tag set. On a push to `main`, the tags will include `ghcr.io/<owner>/<repo>:main` and `ghcr.io/<owner>/<repo>:sha-a7c3f1d`. On a `v1.2.3` tag, they will include `:1.2.3`, `:1.2`, `:1`, and `:latest`. On a PR, they will include `:pr-12`. You almost never want to hand-roll this list; let the action do it.

> **Status panel — push result**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  PUSH — ghcr.io/codecrunch/crunchwriter             │
> │                                                     │
> │  Tags:    main, sha-a7c3f1d                         │
> │  Digest:  sha256:9b2d8a7c...                        │
> │  Bytes:   148 MB pushed in 14 s                     │
> │  Cache:   84% layers reused from previous build     │
> └─────────────────────────────────────────────────────┘
> ```

---

## 8. Multi-arch builds — `linux/amd64,linux/arm64`

A modern image should be multi-arch. Apple Silicon laptops, ARM cloud instances, and ARM cheaper-runner pools all consume `linux/arm64`; everything else consumes `linux/amd64`. The right shape:

```yaml
- uses: docker/setup-qemu-action@v3
- uses: docker/setup-buildx-action@v3

- uses: docker/build-push-action@v6
  with:
    context: .
    push: true
    platforms: linux/amd64,linux/arm64
    tags: ${{ steps.meta.outputs.tags }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

Two costs to be aware of:

1. **QEMU emulation is slow.** Building `linux/arm64` on an `amd64` runner via QEMU is roughly 4–6x slower than native. For a Python image with no compile step this is acceptable. For anything that compiles native code, switch to a `ubuntu-24.04-arm` runner for that platform via a matrix.
2. **Multi-arch push is a manifest list.** The pushed reference is a single tag (`ghcr.io/owner/repo:1.2.3`) that points to a manifest list, which points to one manifest per platform. `docker pull ghcr.io/owner/repo:1.2.3` on an Apple Silicon laptop pulls the `arm64` variant transparently. You see one tag; the registry stores two.

---

## 9. Releasing on a version tag

The classic release shape: a PR merges to `main`, you (or release-please) cut a `v1.2.3` tag, and a `release.yml` workflow fires. The workflow:

```yaml
# .github/workflows/release.yml
name: release

on:
  push:
    tags: ["v*"]

permissions:
  contents: write       # to create the GitHub Release
  packages: write       # to push to GHCR
  id-token: write       # for image attestation
  attestations: write   # for image attestation

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

      - name: Attest image
        uses: actions/attest-build-provenance@v2
        with:
          subject-name: ghcr.io/${{ github.repository }}
          subject-digest: ${{ steps.build.outputs.digest }}
          push-to-registry: true

      - uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
          body: |
            Image: `ghcr.io/${{ github.repository }}:${{ github.ref_name }}`
            Digest: `${{ steps.build.outputs.digest }}`
```

Walk-through:

- **Trigger:** `push: tags: ["v*"]`. Releases are tag-driven.
- **`fetch-depth: 0`:** the release-notes generator needs the full Git history.
- **`concurrency: cancel-in-progress: false`:** if two tags are pushed within seconds, do not cancel the first release — finish it, then run the second.
- **Permissions:** four scopes, every one justified.
- **Build → attest → release:** the image is built and pushed; an attestation is recorded with the build provenance (who built it, on which workflow, from which commit); the GitHub Release is created with auto-generated notes.

Cutting a release is now: `git tag v1.2.3 && git push --tags`. The next time anyone runs `docker pull ghcr.io/<owner>/<repo>:1.2.3`, they pull a multi-arch image with verifiable provenance, signed by GitHub's OIDC issuer. That is "supply-chain hygiene" — not because you read about it on a blog, but because the same five-step recipe gives you a signed artifact and a release note in one shot.

---

## 10. OIDC into a cloud — the trust chain

The 2026 default for "CI deploys to AWS / Azure / GCP" is OIDC federation, not long-lived secrets. The trust chain:

1. **Your workflow** declares `permissions: id-token: write` and runs `aws-actions/configure-aws-credentials@v4` (or the Azure / GCP equivalent).
2. **The runner** asks the GitHub Actions token issuer for a short-lived OIDC JWT. The JWT's `sub` claim is something like `repo:codecrunch/crunchwriter:ref:refs/heads/main` — uniquely identifying *this workflow on this branch in this repo*.
3. **The action** sends the JWT to the cloud's STS / federation endpoint.
4. **The cloud** validates the JWT against the GitHub issuer, looks up an IAM role whose trust policy matches the JWT's `sub`, and returns short-lived cloud credentials (typically 1 hour).
5. **The workflow** uses those credentials for the rest of the job. They expire when the job ends.

What is *not* in the picture:

- No `AWS_ACCESS_KEY_ID` in repo secrets.
- No long-lived password rotation.
- No "the intern with prod access left, who has the AWS key now."

Setup (AWS, one-time, in your AWS account):

```bash
# 1. Register GitHub as an OIDC identity provider
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# 2. Create an IAM role with a trust policy keyed on your repo
cat > trust.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:codecrunch/crunchwriter:ref:refs/heads/main"
      }
    }
  }]
}
EOF

aws iam create-role \
  --role-name gh-deploy-crunchwriter-prod \
  --assume-role-policy-document file://trust.json

# Attach the permissions the role actually needs (S3, ECR, etc.)
aws iam attach-role-policy \
  --role-name gh-deploy-crunchwriter-prod \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
```

Use it from the workflow:

```yaml
permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-24.04
    environment: production
    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/gh-deploy-crunchwriter-prod
          role-session-name: gh-${{ github.run_id }}
          aws-region: us-east-1

      - run: aws sts get-caller-identity
      - run: aws s3 ls s3://my-bucket/
```

Three rules:

1. **The trust policy's `sub` claim is your access control.** `repo:codecrunch/crunchwriter:ref:refs/heads/main` only lets `main`-branch workflows assume the role. `repo:codecrunch/crunchwriter:environment:production` only lets workflows targeting the `production` environment assume it. Pick the most specific claim that does the job.
2. **`id-token: write` is the magic permission.** Without it, the runner cannot mint the OIDC JWT, and the `configure-aws-credentials` step will fail with a 401 from STS. Add it at job level, not workflow level — only the job that needs cloud access should be able to mint the token.
3. **Use environments for prod.** Combine OIDC with a GitHub Actions Environment that requires a named-reviewer approval. That way a compromised PR cannot pivot to prod even if it tricks `main` into running malicious code.

Azure and GCP have the same shape with different config files; the four-line workflow snippet is essentially identical, just `azure/login@v2` or `google-github-actions/auth@v2` instead of `aws-actions/configure-aws-credentials@v4`.

---

## 11. Image attestation — the 2024+ baseline

`actions/attest-build-provenance@v2` was generally available in 2024 and is the new "ship a signed artifact" baseline. It produces a [SLSA Provenance v1.0](https://slsa.dev/spec/v1.0/provenance) attestation: a signed JSON document that records *which workflow, on which runner, from which commit, with which inputs* produced this image digest.

Adding it to the release workflow is six lines (Section 9 above includes them). Verifying it from a consumer side:

```bash
gh attestation verify \
  --owner codecrunch \
  oci://ghcr.io/codecrunch/crunchwriter@sha256:9b2d8a7c...
```

The verifier checks (a) the attestation's signature against GitHub's OIDC issuer, (b) the `sub` claim matches the expected workflow on the expected repo, and (c) the subject digest matches the image you are about to deploy. The chain is end-to-end: source → workflow → image → consumer, with a signature at every hop.

We are not asking you to verify attestations in production this week. We are asking you to **produce** them, so that the option exists for whoever consumes your images later.

---

## 12. The deploy-on-merge pattern, fully shaped

Here is the canonical merge-to-`main` workflow that you will run in Exercise 3:

```yaml
# .github/workflows/deploy.yml
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
    with: { python-version: "3.13" }

  build-and-push:
    needs: [ci]
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

Walk-through:

- **`ci` job** calls the reusable workflow from Section 3. That gives you lint + matrix test for free, with no duplication.
- **`build-and-push`** runs only after `ci` succeeds (`needs: [ci]`).
- **Permissions are job-scoped.** `contents: read` at workflow level, then `packages: write`, `id-token: write`, `attestations: write` scoped up only on the push job.
- **Concurrency is `cancel-in-progress: false`.** A deploy in flight is not cancelled by the next merge; the next merge queues until the deploy completes.
- **`workflow_dispatch:`** gives you a Run-workflow button to re-deploy on demand, useful when you need to bake a fresh image without a commit.

The Lecture 1 `ci.yml` + this `deploy.yml` + Section 9's `release.yml` is a complete pipeline: every PR is tested; every merge produces a tagged, signed image in GHCR; every `v*` tag cuts a release with multi-arch artifacts and provenance. Three files, one reusable workflow, one composite action, ~250 total YAML lines. That is what a competent 2026 pipeline looks like.

---

## 13. The `pull_request_target` footgun

`pull_request` and `pull_request_target` differ in one critical respect: **whose context the workflow runs in**.

- `pull_request` runs in the **base** repo's context with the `GITHUB_TOKEN` scoped to **read-only** on the head ref. The PR's code is *checked out* in the workflow, but the workflow itself is the **base** repo's workflow file (the one on `main` or whichever branch the PR targets). Secrets are *not* exposed by default to PRs from forks.
- `pull_request_target` also runs in the **base** repo's context, but the `GITHUB_TOKEN` has the **base repo's** permissions and **secrets are exposed**. The workflow file is again the base repo's.

The footgun: `pull_request_target` + a step like `uses: actions/checkout@v4 with: ref: ${{ github.event.pull_request.head.sha }}` checks out the PR's code (controlled by the attacker on a fork) and then runs `npm install` or `pip install` in the workflow that has *the base repo's secrets*. The PR can ship a `postinstall` script in its `package.json` and exfiltrate every secret in the repo. This is the recipe for the supply-chain incidents you have read about.

The rules:

1. **Default to `pull_request`.** It is safe for untrusted code because secrets are not exposed.
2. **Only use `pull_request_target` when you genuinely need write access on the PR thread** — auto-labeler, auto-commenter, dependency-update bot.
3. **If you must use `pull_request_target`, never check out the PR's code in the same workflow.** If you absolutely must, scope `permissions:` down to the minimum and treat the PR as actively hostile.

> **Status panel — pull_request flavor matrix**
> ```
> ┌─────────────────────────────────────────────────────────────┐
> │  Event                  Workflow source   Secrets   Safe?   │
> │  pull_request           base repo         no        yes     │
> │  pull_request_target    base repo         yes       NO      │
> │  push (fork via PR)     (does not trigger)                  │
> └─────────────────────────────────────────────────────────────┘
> ```

If you remember nothing else from this lecture, remember the cell in row 2 column 4.

---

## 14. Pinning by digest, in practice

Lecture 1 covered pinning conceptually. In practice, the workflow looks like this:

```yaml
- uses: actions/checkout@v4   # before
```

After running `ratchet pin .github/workflows/ci.yml`:

```yaml
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.2.2
```

The action ref is now a 40-char Git SHA, with a comment recording the human-readable tag. Dependabot can still upgrade it (it updates the SHA and the comment together). A malicious push to the `v4` tag in `actions/checkout` cannot affect your workflow until you accept a PR.

Add to `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "weekly" }
    groups:
      actions:
        patterns: ["*"]
```

Now every Sunday morning you get one PR with the week's action updates. Reading it takes 60 seconds. Merging it takes one click. Skipping it for three weeks is how you end up exposed.

---

## 15. Anti-patterns to refuse on sight (Lecture 2 edition)

- **`pull_request_target` checking out the PR ref** — Section 13. Never.
- **`AWS_ACCESS_KEY_ID` in repo secrets** — replace with OIDC (Section 10).
- **A long-lived `GHCR_TOKEN` PAT in repo secrets** — use `GITHUB_TOKEN` with `packages: write`.
- **`uses: actions/checkout@main`** — `@main` is a moving target on someone else's repo. Major tag or digest.
- **`secrets: inherit` to a third-party reusable workflow** — that hands every secret you have to the workflow author. Use explicit `secrets:` mapping.
- **`environment: production` on a job with no reviewers configured** — the environment exists but provides no gate. Configure the reviewer rule.
- **A 30-line `run: |` block of bash in a workflow** — extract to `./scripts/deploy.sh` and version-control the script; `run:` only invokes it.
- **One workflow file with 14 jobs** — split. The Actions UI is row-per-workflow.

---

## 16. What you should have, by the end of this lecture

By the end of Lecture 2's exercises and the mini-project, your Week 3 mini-project repo should have:

- **`.github/workflows/ci.yml`** — Lecture 1's pipeline, calling a reusable workflow.
- **`.github/workflows/build-and-test.yml`** — the reusable workflow (`on: workflow_call`).
- **`.github/workflows/deploy.yml`** — push-to-`main` builds and pushes a multi-arch image to GHCR with attestation.
- **`.github/workflows/release.yml`** — tag-to-`v*` cuts a GitHub Release with multi-arch image and provenance.
- **`.github/actions/setup-python-app/action.yml`** — the composite action for the shared setup.
- **`.github/dependabot.yml`** — weekly updates for GitHub Actions and pip.
- An image at `ghcr.io/<you>/<repo>:latest` that you can `docker pull` from anywhere.
- An image at `ghcr.io/<you>/<repo>:1.0.0` with a build-provenance attestation.

That is six files in `.github/`, 300–350 YAML lines total, and one tagged release. From now on, every merge to `main` produces a deployable image; every `v*` tag produces a release. You no longer need your laptop to ship.

The pipeline you built this week is not the most sophisticated one you will write. It is the **simplest one that does its job**, and that simplicity is the point. The next nine weeks will add observability, Kubernetes, secrets management, and an on-call runbook on top — but the bones are right today.

What changes in Week 5 is not the pipeline; it is the **target**. Week 5 takes the image that this pipeline now pushes to GHCR on every merge, and runs it on a real Kubernetes cluster. The GHCR tag in your `release.yml` becomes the input to a Kubernetes Deployment manifest. The merge-to-`main` event becomes a deploy event. The story remains the same; the surface widens.
