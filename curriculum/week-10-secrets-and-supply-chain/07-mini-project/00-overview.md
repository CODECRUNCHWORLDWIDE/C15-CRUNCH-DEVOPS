# Week 10 Mini-Project — A Signed, SBOM'd, Secret-Aware Service

**Time:** ~7 hours (~6h building, ~1h write-up).
**Cost:** $0.00 (kind path).
**Prerequisites:** All four exercises and both challenges complete. The `w10` kind cluster is running with Vault, ESO, Sealed Secrets, and Kyverno installed.

---

## What you are building

A FastAPI service — call it `vaultedapi` — whose entire lifecycle from build through deploy enforces this week's discipline:

1. **Built in CI** with a GitHub Actions workflow (or simulated locally if you do not want to push to GitHub). The build emits a SLSA-style provenance attestation.
2. **Signed at build time** with cosign keyless, attaching the signature to the image as an OCI artifact and recording in Rekor.
3. **SBOM and vuln-scan attestations** attached to the image alongside the signature.
4. **Secrets at runtime** come from Vault via the External Secrets Operator. The application reads a JWT signing key, a Postgres password, and a third-party API token from `/etc/secrets`. None of those values exists in the repo.
5. **Bootstrap-time secrets** that *do* live in the repo (the namespace setup, a feature-flag JSON) are encrypted as Sealed Secrets.
6. **Admission-gated** by Kyverno: a Pod cannot enter the `vaultedapi` namespace unless its image carries a valid cosign signature whose identity matches the production CI workflow.
7. **Observable** by the Week 9 stack (optional but recommended): Prometheus scrapes `/metrics`, OpenTelemetry traces are shipped, logs go to Loki.

The whole thing — application code, Dockerfile, build workflow, Sealed Secrets, ExternalSecret manifests, Kyverno policies, runbooks — lives in a Git repo. ArgoCD (or `kubectl apply`) applies it.

---

## The application

The `vaultedapi` service:

- `GET /api/health` — returns `{"status":"ok"}`. Used by readiness probes.
- `GET /api/echo?name=<name>` — returns `{"greeting": "Hello, <name>", "signed_by_jwt": "<short-lived-jwt>"}`. The JWT is signed with a key read from `/etc/secrets/jwt-key` at boot. To demonstrate ExternalSecret rotation, the key can be rotated and the next request returns a JWT signed by the new key.
- `GET /api/db-status` — opens a connection to `postgres.default.svc.cluster.local` using credentials from `/etc/secrets/db-password` and `/etc/secrets/db-username`. Returns `{"connected": true, "version": "..."}` on success. (Use any small Postgres in-cluster; the official `postgres:16-alpine` Helm chart works.)
- `GET /version` — returns the build metadata baked in at build time (git SHA, git ref, build timestamp, version tag).
- `GET /metrics` — Prometheus exposition (optional).
- `GET /docs` — FastAPI's bundled OpenAPI UI.

---

## Architecture

```
                    Browser / curl
                          |
                          | HTTPS
                          v
                +-----------------------+
                |   kind cluster, w10   |
                |                       |
                |  Kyverno admission:   |
                |   * verify cosign sig |
                |   * verify SPDX attn  |
                |   * fail if missing   |
                |                       |
                |  +-----------------+  |     +-----------------+
                |  | vaultedapi pod  |  |     |   Vault         |
                |  |                 |  |     |   (dev mode)    |
                |  |  reads:         |  +<----+ ESO refreshes   |
                |  |   /etc/secrets/ |  |     |  secrets every  |
                |  |     db-password |  |     |  30s            |
                |  |     db-username |  |     +-----------------+
                |  |     jwt-key     |  |
                |  |     api-token   |  |     +-----------------+
                |  +-----------------+  |     | SealedSecrets   |
                |                       +<----+  controller     |
                |  Bootstrap (sealed):  |     |  unseals at     |
                |   * feature-flags JSON|     |  apply-time     |
                |                       |     +-----------------+
                +-----------------------+
                          ^
                          |
                          | watches main branch
                          |
                +-----------------------+
                |  Git repo:            |
                |  github.com/YOU/      |
                |    c15-w10-vaultedapi |
                |                       |
                |  manifests/           |
                |    + Sealed Secrets   |
                |    + ESO config       |
                |    + Kyverno policies |
                |    + Deployment       |
                |                       |
                |  app/                  |
                |    + vaultedapi.py    |
                |    + Dockerfile       |
                |    + requirements.txt |
                |                       |
                |  .github/workflows/   |
                |    release.yaml       |
                |    (builds, signs,    |
                |     SBOMs, attests)   |
                +-----------------------+
```

---

## Required deliverables

A Git repo containing:

```
c15-week10-mini-project/
+-- README.md                            - your project description
+-- app/
|   +-- Dockerfile
|   +-- requirements.txt
|   +-- vaultedapi.py                    - the FastAPI service
+-- manifests/                           - what kubectl/ArgoCD applies
|   +-- 00-namespace.yaml                - vaultedapi namespace
|   +-- 10-sealed-feature-flags.yaml     - bootstrap SealedSecret
|   +-- 20-clustersecretstore.yaml       - ESO ClusterSecretStore to Vault
|   +-- 30-externalsecret.yaml           - ESO ExternalSecret projecting Vault secrets
|   +-- 40-deployment.yaml               - vaultedapi Deployment + Service
|   +-- 50-kyverno-cosign-policy.yaml    - Kyverno ClusterPolicy requiring sig
+-- vault-setup/                         - imperative setup, not GitOps
|   +-- README.md                        - vault auth/role/policy commands
|   +-- vault-policy.hcl                 - the Vault policy as code
+-- ci/                                   - optional, if you wire up GitHub Actions
|   +-- release.yaml                     - build, push, sign, attest
+-- runbooks/                            - markdown for each scenario
|   +-- rotate-jwt-key.md
|   +-- rotate-db-password.md
|   +-- emergency-key-recovery.md
+-- screenshots/                         - your evidence
|   +-- cosign-verify.png
|   +-- rekor-entry.png
|   +-- externalsecret-reconciled.png
|   +-- kyverno-block-unsigned.png
|   +-- jwt-rotation-demo.png
+-- LICENSE                              - MIT or Apache-2.0 your choice
+-- .gitignore                           - excludes plaintext secrets, age key
+-- .sops.yaml                           - if you use SOPS for any extras
```

---

## Phased build

### Phase 1 — Application and Dockerfile (1 hour)

Write `vaultedapi.py` based on `signed_app.py` from Exercise 3 but extended:

- Reads `/etc/secrets/jwt-key` at boot. Re-reads on each `/api/echo` request to support rotation.
- Reads `/etc/secrets/db-password`, `/etc/secrets/db-username`, and uses them to open a Postgres connection in `/api/db-status`.
- Reads `/etc/secrets/api-token` and includes a redacted version in `/version`.
- Type hints on every function. `python3 -m py_compile vaultedapi.py` clean.

Write the Dockerfile. Include the env vars for build metadata. Build locally:

```bash
docker build -t vaultedapi:dev .
```

### Phase 2 — Vault setup (45 min)

Document in `vault-setup/README.md` the imperative commands to:

1. Enable the K/V v2 engine.
2. Write the four secrets (`jwt-key`, `db-username`, `db-password`, `api-token`) to `secret/vaultedapi/*`.
3. Write a Vault policy granting read access only to those paths.
4. Configure the Kubernetes auth method (reuse Exercise 2's config).
5. Create a Vault role `vaultedapi` bound to the `vaultedapi/vaultedapi` service account.

The policy file `vault-setup/vault-policy.hcl` should be the canonical HCL.

### Phase 3 — Manifests (1.5 hours)

Write each numbered manifest. Key points:

- `00-namespace.yaml` creates the namespace with the label that Kyverno's selector matches.
- `10-sealed-feature-flags.yaml` contains a SealedSecret with at least one bootstrap value (a `feature-flags.json` blob). Generate via `kubeseal` from a plaintext that you do not commit.
- `20-clustersecretstore.yaml` points ESO at Vault using the Kubernetes auth method.
- `30-externalsecret.yaml` projects all four Vault secrets into a Secret named `vaultedapi-runtime`.
- `40-deployment.yaml` mounts `vaultedapi-runtime` at `/etc/secrets`, references your signed image by digest, sets resource requests/limits, configures readiness/liveness probes against `/api/health`.
- `50-kyverno-cosign-policy.yaml` requires every Pod in the `vaultedapi` namespace to carry a cosign signature from your CI workflow's OIDC identity. Set `validationFailureAction: Enforce` and `failurePolicy: Fail`.

### Phase 4 — Sign and attest (45 min)

Build the image. Push to your registry. Sign with cosign. Generate the SBOM. Attest. The workflow:

```bash
docker build -t $IMAGE .
docker push $IMAGE
DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' $IMAGE | cut -d@ -f2)
export IMAGE_BY_DIGEST=$(echo $IMAGE | cut -d: -f1)@$DIGEST

cosign sign $IMAGE_BY_DIGEST

syft $IMAGE_BY_DIGEST -o spdx-json > sbom.spdx.json
grype sbom:./sbom.spdx.json -o json > scan.json

cosign attest --predicate sbom.spdx.json --type spdxjson $IMAGE_BY_DIGEST
cosign attest --predicate scan.json --type vuln $IMAGE_BY_DIGEST
```

Update `40-deployment.yaml` to use `$IMAGE_BY_DIGEST` (the digest-pinned reference, not the tag).

### Phase 5 — Apply and verify (1 hour)

```bash
kubectl apply -f manifests/

kubectl -n vaultedapi rollout status deploy/vaultedapi --timeout=180s

kubectl -n vaultedapi get pods,svc,externalsecret,sealedsecret
```

Verify:

- The Pod is running.
- Kyverno admitted it (check `kubectl get events -n vaultedapi`).
- ExternalSecret status is `Ready`.
- Secret `vaultedapi-runtime` exists with the four keys.
- `curl http://localhost:8080/api/health` returns `{"status":"ok"}`.
- `curl http://localhost:8080/api/echo?name=test` returns a JWT.
- `curl http://localhost:8080/version` shows the build metadata.

### Phase 6 — Demonstrate enforcement (30 min)

Try to deploy a Pod with an unsigned image in the namespace; capture the rejection.

```bash
kubectl run unsigned-attempt --image=nginx:1.27-alpine -n vaultedapi
# Expect: admission webhook denied the request.
```

Try to deploy a Pod with an image signed by a *different* OIDC identity; capture the rejection. (You can simulate this by signing a separate image with a key-based cosign signature; Kyverno will reject because the keyless-identity policy is not satisfied.)

### Phase 7 — Demonstrate rotation (30 min)

Rotate the JWT key in Vault:

```bash
vault kv put secret/vaultedapi/jwt-key value=NEW-JWT-KEY-ROTATED
```

Wait the ESO refresh interval. Hit `/api/echo` again. The JWT it returns should be signed by the new key. Capture the demonstration (the old JWT vs the new JWT, both decoded with `jwt-cli` or jwt.io).

### Phase 8 — Write the runbooks (45 min)

For each of:

- `rotate-jwt-key.md` — how an operator rotates the JWT key safely (Vault put, ESO refresh, application warm-up window).
- `rotate-db-password.md` — same for the DB password (Vault put, ESO refresh, application reconnect; with a note that some DB drivers cache connections — pair with Reloader).
- `emergency-key-recovery.md` — what to do if the Sealed Secrets controller's key is lost (restore from the backup; if no backup, every SealedSecret in the repo must be re-sealed against a new key).

Each runbook is ~half a page. Step-by-step. Tested by you on the cluster.

### Phase 9 — Wrap and submit (15 min)

Write the top-level `README.md` describing what you built, what worked, what was hard. Include screenshots in `screenshots/`.

---

## Grading rubric

| Component | Points |
|-----------|-------:|
| Application code (vaultedapi.py reads from /etc/secrets correctly; type hints; compiles clean) | 10 |
| Dockerfile (multi-stage if you like, builds with `--no-cache`, no secrets baked in) | 5 |
| Vault setup documented and runnable from `vault-setup/README.md` | 10 |
| SealedSecret manifest applied and reconciled | 5 |
| ExternalSecret manifest applied; secrets visible in pod | 10 |
| Image signed via cosign with an OIDC identity policy | 10 |
| SBOM attestation attached and verifiable | 5 |
| Vuln-scan attestation attached and verifiable | 5 |
| Kyverno policy applied; unsigned-image rejection demonstrated | 10 |
| Rotation demonstrated (JWT key rotates; new key effective within 60s) | 10 |
| Runbooks present and accurate | 10 |
| Screenshots documenting the working state | 5 |
| README explains what was built and what was hard | 5 |
| **Total** | **100** |

100: outstanding.
85+: pass.
70-84: pass with minor revisions.
<70: redo and resubmit.

---

## Stretch goals

- Wire up the **GitHub Actions release workflow** to do everything Phase 4 does automatically on every push to `main`. Use the GHA OIDC token as the cosign-keyless identity. The workflow file should be < 100 lines.
- Add the **Week 9 observability stack** alongside; the vaultedapi service emits `/metrics` and Prometheus scrapes it. Show one dashboard panel showing request rate + secret-refresh-success rate.
- Add a **second cosign signer**: require two distinct signers for production images. Update the Kyverno policy to demand `count: 2` in the attestor block.
- **Verify the SBOM attestation in-cluster** with a Kyverno policy that not only requires the attestation but parses it and rejects deployments whose SBOM contains a forbidden package (e.g., `log4j-core@<2.17`). Kyverno's policy language supports this; the syntax is at <https://kyverno.io/docs/writing-policies/verify-images/sigstore/#in-toto-attestations>.

---

## Cost summary

```
+-----------------------------------------------------+
|  COST PANEL - Week 10 mini-project                  |
|                                                     |
|  kind cluster (local)                    $0.00      |
|  Vault dev container                     $0.00      |
|  Sealed Secrets controller               $0.00      |
|  External Secrets Operator               $0.00      |
|  Kyverno admission controller            $0.00      |
|  cosign keyless (Fulcio + Rekor)         $0.00      |
|  syft + grype                            $0.00      |
|  GHCR or local registry                  $0.00      |
|  GitHub Actions (free tier, public repo) $0.00      |
|                                                     |
|  Required total                          $0.00      |
+-----------------------------------------------------+
```

---

## Tear-down

When you finish, tear down the cluster:

```bash
kind delete cluster --name w10
docker rm -f kind-registry      # if you ran the local registry
```

The signed images remain in your registry; the cosign signatures and Rekor entries persist (Rekor is append-only — your signatures are part of the public log forever).

The age key, the Sealed Secrets controller backup, and your `vault-setup/README.md` should be filed somewhere durable; you will need them again in Week 11 when we extend the trust model into the service mesh.
