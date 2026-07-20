# Week 4 — Resources

Every resource on this page is **free** and **publicly accessible**. No paywalled books. If a link 404s, please open an issue.

## Required reading (work it into your week)

- **GitHub Actions — Quickstart and "Understanding workflows"** — the two pages that finally make the execution model click. Read both before Monday's lecture: <https://docs.github.com/en/actions/get-started/quickstart> and <https://docs.github.com/en/actions/concepts/workflows-and-actions>.
- **Workflow syntax for GitHub Actions** — the canonical reference. You will return to this page weekly for the rest of your career. Read sections "name," "on," "jobs," "permissions," and "concurrency" before Tuesday: <https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions>.
- **Security hardening for GitHub Actions** — the page nobody assigns and everybody should. Read end to end before Wednesday: <https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions>.
- **About security hardening with OpenID Connect** — the trust chain that replaces long-lived cloud credentials. Read before Thursday: <https://docs.github.com/en/actions/security-for-github-actions/security-guides/about-security-hardening-with-openid-connect>.

## The specs (skim, don't memorize)

- **GitHub Actions metadata syntax (action.yml)** — what an action file actually contains: <https://docs.github.com/en/actions/reference/metadata-syntax-for-github-actions>.
- **Contexts reference** — `github`, `env`, `vars`, `secrets`, `inputs`, `needs`, `steps`, `job`, `runner` — every variable you can interpolate, indexed: <https://docs.github.com/en/actions/reference/context-and-expression-syntax-for-github-actions>.
- **Events that trigger workflows** — every event, with its payload schema and the rules that apply (forks, default branches, drafts): <https://docs.github.com/en/actions/reference/events-that-trigger-workflows>.
- **GHCR (GitHub Container Registry) docs** — push/pull semantics, visibility, retention: <https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry>.

## Official tool docs

- **`actions/checkout`** — every input, what `fetch-depth: 0` costs, the `persist-credentials` footgun on `pull_request_target`: <https://github.com/actions/checkout>.
- **`actions/setup-python`** — Python install with cache for `pip`/`pipenv`/`poetry`: <https://github.com/actions/setup-python>.
- **`actions/cache`** — keying strategies, the `restore-keys:` fallback chain, the 10 GB-per-repo eviction policy: <https://github.com/actions/cache>.
- **`docker/setup-buildx-action`** — Buildx in CI, why you need it, what `driver: docker-container` buys you: <https://github.com/docker/setup-buildx-action>.
- **`docker/build-push-action`** — multi-arch, multi-tag, registry cache, attestation: <https://github.com/docker/build-push-action>.
- **`docker/login-action`** — the four-line GHCR login that uses the auto-provisioned `GITHUB_TOKEN`: <https://github.com/docker/login-action>.
- **`docker/metadata-action`** — the action that mints OCI tags from `git` refs (`v1.2.3`, `pr-12`, `sha-a7c3f1d`, `latest`): <https://github.com/docker/metadata-action>.
- **`aws-actions/configure-aws-credentials`** — the canonical OIDC consumer for AWS: <https://github.com/aws-actions/configure-aws-credentials>.

## Free books, write-ups, and reference repos

- **"GitHub Actions in Action" — sample chapters** — Manning ships the first three chapters free; the workflow-syntax chapter alone is worth the click: <https://www.manning.com/books/github-actions-in-action>.
- **`actions/starter-workflows`** — GitHub's own catalog of starter templates, organized by language and stack. Read three; copy from none: <https://github.com/actions/starter-workflows>.
- **`sethvargo/ratchet`** — a CLI to pin every `uses:` line in your workflows to a Git SHA, with automatic comment annotation. Read the README and run it on a workflow you wrote: <https://github.com/sethvargo/ratchet>.
- **`step-security/secure-repo`** — a free auditor that scans your workflows for unpinned actions, dangerous `pull_request_target` patterns, and missing `permissions:` blocks: <https://github.com/step-security/secure-repo>.
- **"Pinning GitHub Actions by SHA" — GitHub Security Lab** — the post that crystallized the digest-pinning convention: <https://securitylab.github.com/research/github-actions-untrusted-input/>.
- **`nektos/act`** — run GitHub Actions workflows locally in Docker. The single most useful debug tool when a workflow only fails in CI: <https://github.com/nektos/act>.

## Talks and videos (free, no signup)

- **"GitHub Actions: 5 patterns I wish I had known earlier" — Brian Douglas** (~25 min). The composite-action vs reusable-workflow distinction explained the way it should have been in the docs: <https://www.youtube.com/results?search_query=brian+douglas+github+actions+patterns>.
- **"OIDC: GitHub Actions to AWS without long-lived credentials" — Aidan Steele** (~30 min). The talk that taught the industry to delete `AWS_ACCESS_KEY_ID` from repo secrets: <https://www.youtube.com/results?search_query=aidan+steele+oidc+github+actions+aws>.
- **"Supply chain attacks on CI" — Adam Baldwin** (~40 min). Why you pin actions by digest, told as four real incidents: <https://www.youtube.com/results?search_query=adam+baldwin+supply+chain+ci>.

## Open-source workflows worth reading

You will learn more from one hour reading other people's workflows than from three hours of tutorials. Pick one and just read it:

- **`kubernetes/kubernetes` `.github/workflows/`** — the largest open-source repo's CI matrix; pay attention to the `concurrency:` and `permissions:` patterns: <https://github.com/kubernetes/kubernetes/tree/master/.github/workflows>.
- **`vercel/next.js` `.github/workflows/`** — a frontend repo with a long matrix, heavy caching, and reusable workflows for the deploy preview: <https://github.com/vercel/next.js/tree/canary/.github/workflows>.
- **`hashicorp/terraform` `.github/workflows/`** — the digest-pinning discipline is exemplary: <https://github.com/hashicorp/terraform/tree/main/.github/workflows>.
- **`docker/build-push-action` `.github/workflows/`** — the action that builds and pushes other people's images; their own CI is the textbook example of "use your own tools": <https://github.com/docker/build-push-action/tree/master/.github/workflows>.
- **`actions/cache` `.github/workflows/`** — the action that caches other people's CI; their own caching is enlightening: <https://github.com/actions/cache/tree/main/.github/workflows>.

## OIDC into the three clouds

If you do not have a sandbox cloud account, the AWS Free Tier and Google Cloud's $300 / 90-day trial both work for this week's exercises.

- **AWS** — IAM OIDC identity provider for `token.actions.githubusercontent.com`, then an IAM role with a trust policy keyed on the workflow's `sub` claim: <https://docs.github.com/en/actions/security-for-github-actions/security-guides/configuring-openid-connect-in-amazon-web-services>.
- **Azure** — federated credentials on an App Registration, no client secret: <https://docs.github.com/en/actions/security-for-github-actions/security-guides/configuring-openid-connect-in-azure>.
- **GCP** — Workload Identity Federation with a service account: <https://docs.github.com/en/actions/security-for-github-actions/security-guides/configuring-openid-connect-in-google-cloud-platform>.

The three docs are 80% identical. Read whichever cloud you have a free-tier account in. If none, AWS — its IAM trust-policy syntax is the one you will see on the most other teams.

## Tools you'll install this week

| Tool | Install | Purpose |
|------|---------|---------|
| `gh` | `brew install gh` / `apt install gh` | The GitHub CLI; used to view runs, re-run, view logs, mint workflow dispatches |
| `act` | `brew install act` | Run GitHub Actions workflows locally in Docker |
| `ratchet` | `brew install ratchet` | Pin `uses:` lines to a Git SHA across a whole workflow |
| `actionlint` | `brew install actionlint` | Static lint for `.github/workflows/*.yml` — type-checks expressions, catches typos |
| `cosign` | `brew install cosign` | Sign and verify OCI images; we use it for image attestation in the challenge |

## Glossary cheat sheet

Keep this open in a tab.

| Term | Plain English |
|------|---------------|
| **Workflow** | One `.yml` file in `.github/workflows/`. Top-level config + a set of jobs. |
| **Job** | A unit that runs on one runner. Jobs run in parallel unless `needs:` orders them. |
| **Step** | One sequential instruction inside a job. Either `uses:` (call an action) or `run:` (a shell command). |
| **Action** | A reusable unit. JavaScript (`actions/checkout`), Docker (`docker/build-push-action`), or composite (a bundle of steps in `action.yml`). |
| **Runner** | The VM (or container) that executes a job. GitHub-hosted or self-hosted. |
| **Marketplace** | The public catalog of actions at `github.com/marketplace?type=actions`. |
| **Matrix** | A way to fan out one job over multiple input combinations (Python versions, OS, region). |
| **Reusable workflow** | A workflow you `uses:` from another workflow with `workflow_call`. The DRY primitive for whole pipelines. |
| **Composite action** | An action whose `runs.using: "composite"` lets you bundle steps. The DRY primitive for a few steps. |
| **`GITHUB_TOKEN`** | The auto-provisioned token Actions creates per run. Scoped by `permissions:`. Expires when the run ends. |
| **`permissions:`** | Per-workflow or per-job declaration of what the `GITHUB_TOKEN` can do. Default since 2023: `contents: read`. |
| **OIDC token** | A short-lived JWT GitHub mints on demand, exchanged at a cloud IdP for cloud credentials. The reason you can delete `AWS_ACCESS_KEY_ID` from secrets. |
| **`concurrency:`** | The two-line idiom that cancels in-flight runs of the same group when a new one arrives. Prevents queue pile-ups. |
| **`needs:`** | Job-level dependency. `job-b: needs: [job-a]` means job-b waits for job-a's success. |
| **`if:`** | Job- or step-level guard. Takes a GitHub Actions expression. The most common shape is `if: github.ref == 'refs/heads/main'`. |
| **GHCR** | GitHub Container Registry — OCI registry at `ghcr.io/<owner>/<image>`. Pushes use `GITHUB_TOKEN` with `packages: write`. |
| **Attestation** | A signed, machine-readable claim about an artifact (provenance, SBOM, signature). The 2024+ supply-chain norm. |

---

*If a link 404s, please [open an issue](https://github.com/CODE-CRUNCH-CLUB) so we can replace it.*
