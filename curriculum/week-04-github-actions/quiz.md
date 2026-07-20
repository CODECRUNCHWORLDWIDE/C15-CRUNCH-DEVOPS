# Week 4 — Quiz

Ten questions. Lectures closed. Aim for 9/10.

---

**Q1.** What is the default value of `permissions:` for a `GITHUB_TOKEN` in a repository created **after** early 2023?

- A) `write-all`
- B) `read-all`
- C) `contents: read` (and nothing else)
- D) Whatever the workflow file's `permissions:` block says; there is no default.

---

**Q2.** A workflow has `on: pull_request:` and runs on a PR opened **from a fork**. Which of the following is true about the `GITHUB_TOKEN` and repository secrets in that run?

- A) The token has write access and all secrets are exposed; the PR can push to `main`.
- B) The token is read-only on the head ref and secrets are **not** exposed by default.
- C) The token has the same permissions as on `main`, but secrets require explicit `secrets:` mapping.
- D) The workflow does not run on fork PRs at all.

---

**Q3.** Which of the following `concurrency:` configurations is the correct shape for a **deploy-to-prod** workflow that you do not want cancelled mid-flight when another merge to `main` lands?

- A) `concurrency: { group: deploy-prod, cancel-in-progress: true }`
- B) `concurrency: { group: deploy-prod, cancel-in-progress: false }`
- C) Omit `concurrency:` entirely.
- D) `concurrency: { group: ${{ github.run_id }}, cancel-in-progress: true }`

---

**Q4.** A workflow has `runs-on: ubuntu-latest`. Why is this considered a smell in 2026?

- A) `ubuntu-latest` is deprecated and will be removed in 2027.
- B) The label silently changes when GitHub rolls the underlying OS version, which can introduce unexpected behavior changes on existing pipelines.
- C) GitHub charges more for the `latest` label than for pinned versions.
- D) `ubuntu-latest` does not support Docker; you have to use `ubuntu-24.04` to get Docker.

---

**Q5.** A workflow file contains this step:

```yaml
- uses: actions/checkout@main
```

What is the supply-chain risk?

- A) `@main` is a moving target on the action's repository; a malicious commit pushed to `actions/checkout`'s `main` branch would run on your next push without any change in your repo.
- B) There is no risk; `actions/checkout` is a GitHub-maintained action.
- C) The risk is purely performance; `@main` is slower to resolve than a tag.
- D) `@main` is not a valid action reference and the workflow will fail to parse.

---

**Q6.** A workflow defines a matrix:

```yaml
strategy:
  matrix:
    python: ["3.11", "3.12", "3.13"]
    os: [ubuntu-24.04, macos-14]
    include:
      - python: "3.13"
        os: ubuntu-24.04
        coverage: true
    exclude:
      - python: "3.11"
        os: macos-14
```

How many jobs run?

- A) 6
- B) 5
- C) 7
- D) 4

---

**Q7.** Which is the **correct** way to authenticate from a GitHub Actions workflow to AWS for a production deploy, as recommended in 2026?

- A) Store an `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in repo secrets and use `aws-actions/configure-aws-credentials@v4` with those secrets.
- B) Use a personal access token from the AWS CLI committed to a file in the repo.
- C) Use OIDC federation: the workflow declares `permissions: id-token: write`, calls `aws-actions/configure-aws-credentials@v4` with a `role-to-assume`, and AWS validates the OIDC JWT against an IAM role's trust policy. No long-lived AWS credentials in repo secrets.
- D) Use a self-hosted runner inside the AWS VPC; the runner's EC2 instance profile is sufficient.

---

**Q8.** A workflow has `permissions: id-token: write` at the **workflow** level. What is the more secure variant?

- A) Move `id-token: write` to the job level on only the job that needs it.
- B) Remove `id-token: write` entirely; OIDC tokens are minted automatically.
- C) Change it to `id-token: read`.
- D) Move it to step level.

---

**Q9.** A repository has a workflow that uses `docker/metadata-action@v5` to generate tags. On a push to the default branch with commit SHA `a7c3f1d...`, which set of tags will it generate, given:

```yaml
with:
  images: ghcr.io/codecrunch/app
  tags: |
    type=ref,event=branch
    type=sha,format=short
    type=raw,value=latest,enable={{is_default_branch}}
```

- A) Only `ghcr.io/codecrunch/app:main`
- B) `ghcr.io/codecrunch/app:main`, `ghcr.io/codecrunch/app:sha-a7c3f1d`, `ghcr.io/codecrunch/app:latest`
- C) Only `ghcr.io/codecrunch/app:latest`
- D) `ghcr.io/codecrunch/app:main`, `ghcr.io/codecrunch/app:a7c3f1d` (no `sha-` prefix), `ghcr.io/codecrunch/app:latest`

---

**Q10.** Which of the following is the **single most dangerous anti-pattern** covered in Lecture 2?

- A) Using `actions/checkout@v4` instead of pinning by SHA.
- B) Using `pull_request_target` and checking out the PR's head ref in the same workflow.
- C) Setting `concurrency: cancel-in-progress: true` on a release workflow.
- D) Forgetting to add `timeout-minutes:` to a job.

---

## Answer key

<details>
<summary>Click to reveal</summary>

1. **C** — The 2023 change made `contents: read` the default; nothing else is granted. (B) was the previous default; (A) was the original default and is the legacy footgun in old repos. (D) is false — defaults exist.

2. **B** — `pull_request` from a fork is the safe variant. The token is read-only on the head ref; secrets are not exposed. (A) describes `pull_request_target`'s footgun, not `pull_request`. (C) is wrong about secrets. (D) is wrong — the workflow runs, it is just sandboxed.

3. **B** — Deploys should not be cancelled mid-flight; cancelling can leave production half-deployed. Set `cancel-in-progress: false` and let the second deploy queue. (A) is the right shape for CI, not deploys. (C) means concurrent deploys could run simultaneously and step on each other. (D) ungroups every run, defeating the point.

4. **B** — The floating label re-maps every six months. Your workflow that worked yesterday on `ubuntu-22.04`-flavored runners can silently behave differently tomorrow on `ubuntu-24.04`. Pin explicitly. (A) is fabricated; (C) is fabricated; (D) is false.

5. **A** — A `@<branch>` reference is a moving target. The action's maintainer (or anyone who compromises them) can push a malicious commit and you would consume it on your next run. The mitigation is to pin by SHA or by major tag plus Dependabot. (B) is wrong; trusted-by-default is a cultural failure of the 2019–2022 era. (C) is wrong. (D) is wrong — `@<branch>` is valid syntax.

6. **B** — 5 jobs. The 3×2 product is 6 cells; `exclude:` removes one (`3.11/macos-14`), giving 5. The `include:` extends an *existing* cell (3.13/ubuntu) with `coverage: true`; it does **not** add a new cell.

7. **C** — OIDC federation is the 2026 default. (A) was the 2019–2022 norm and is now considered a security liability — long-lived AWS keys in repo secrets are the source of most CI-origin cloud breaches. (B) is absurd. (D) works for some shapes but only if you actually use a self-hosted runner inside the VPC, which has its own footguns.

8. **A** — Least privilege says move sensitive permissions to the **smallest scope** that needs them. If only the deploy job needs OIDC, only the deploy job should have `id-token: write`. (B) is wrong — `id-token: write` is required for OIDC; without it the token cannot be minted. (C) is fabricated — there is no `id-token: read`. (D) is wrong — `permissions:` is workflow or job level, not step level.

9. **B** — On a push to the default branch (`main`): `type=ref,event=branch` produces `:main`; `type=sha,format=short` produces `:sha-a7c3f1d` (the `sha-` prefix is the default for `format=short`); `type=raw,value=latest,enable={{is_default_branch}}` produces `:latest` because the conditional matches. (A) misses two tags. (C) misses two tags. (D) has the wrong prefix on the SHA tag.

10. **B** — `pull_request_target` + checkout of the PR ref is the recipe for the most common Actions RCE. The PR is attacker-controlled; the workflow has the base repo's secrets; a malicious `postinstall` script can exfiltrate every secret. (A) is a smell but not the most dangerous; (C) is wrong-shape but not catastrophic; (D) wastes runner-minutes but does not breach anything.

</details>

If under 7, re-read the lectures you missed. If 9+, you are ready for the [homework](./homework.md).
