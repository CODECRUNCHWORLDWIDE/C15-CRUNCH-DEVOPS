# Exercise 2 — The Application and Its CI Pipeline

**Estimated time:** 120 minutes.
**Prerequisite reading:** Lecture 1; W2 Dockerfile review.
**Files used:** the application source under `mini-project/capstone/app/`.

The goal of this exercise is to build the application image, push it to the local registry from Exercise 1, sign it with cosign, generate an SBOM, and run a Trivy scan. The same pipeline runs in GitHub Actions on every push to `main`; for the exercise you run the steps locally to confirm each one works.

The application is intentionally small. The work this week is not in the application code; it is in the pipeline that ships the application.

---

## Part A — The application source

Create the application source tree under `mini-project/capstone/app/`. The structure:

```
mini-project/capstone/app/
├── Dockerfile
├── compose.yaml
├── pyproject.toml
├── src/
│   └── crunch_quotes/
│       ├── __init__.py
│       ├── main.py
│       └── db.py
├── tests/
│   └── test_main.py
└── frontend/
    └── index.html
```

The full source is in `mini-project/capstone/app/`. Read each file before continuing; do not paste-and-run blindly. The source totals approximately 200 lines of Python plus 30 lines of HTML.

The application has three endpoints:

- `GET /health` — returns 200 OK with a small JSON body indicating the database connection works. Used by the readiness/liveness probes.
- `GET /quote` — selects a random row from the `quotes` table in Postgres and returns it as JSON.
- `GET /metrics` — Prometheus exposition format. Exposes `http_requests_total`, `http_request_duration_seconds`, and the standard process metrics.

---

## Part B — Build the image

From `mini-project/capstone/app/`:

```bash
# Build the image and tag it with both the registry path and a
# semantic version. The build is multi-stage; the final image is
# distroless-based (~80 MB) and runs as a non-root user.
IMAGE="localhost:5001/crunch-quotes"
TAG="0.1.0"

docker build -t "$IMAGE:$TAG" -t "$IMAGE:latest" .

# Push to the local registry.
docker push "$IMAGE:$TAG"
docker push "$IMAGE:latest"

# Verify the image is present.
curl -sf "http://localhost:5001/v2/crunch-quotes/tags/list" | python3 -m json.tool
```

Expected: the registry catalog shows both `0.1.0` and `latest`.

---

## Part C — Scan with Trivy

```bash
trivy image --severity HIGH,CRITICAL --exit-code 1 "$IMAGE:$TAG"
```

If Trivy reports HIGH or CRITICAL CVEs, the exit code is 1. For a fresh distroless-Python build there should be none; if there are, update the base image (the Dockerfile's `FROM gcr.io/distroless/python3-debian12:nonroot` pulls the current digest at build time).

For an offline-friendly mode (no `--exit-code`):

```bash
trivy image --format table "$IMAGE:$TAG"
```

---

## Part D — Generate the SBOM

Two formats; either is acceptable. We use CycloneDX in the capstone.

```bash
# CycloneDX
trivy image --format cyclonedx --output sbom-cyclonedx.json "$IMAGE:$TAG"

# Or SPDX
trivy image --format spdx-json --output sbom-spdx.json "$IMAGE:$TAG"
```

Inspect the SBOM:

```bash
python3 -c "
import json
data = json.load(open('sbom-cyclonedx.json'))
components = data.get('components', [])
print(f'Components: {len(components)}')
for c in components[:5]:
    print(f'  - {c.get(\"name\")} {c.get(\"version\")}')
"
```

The SBOM lists every package the image contains. For a distroless-Python image, expect ~30 to 50 components — the Python stdlib plus FastAPI plus its transitive dependencies.

---

## Part E — Sign with cosign

We use cosign's *keyless* mode where possible. Keyless mode obtains a short-lived signing certificate from Sigstore's Fulcio CA, tied to your OIDC identity (GitHub Actions OIDC in CI; an interactive browser flow locally). The signature is stored in the registry alongside the image and the proof of identity is logged to Rekor's public transparency log.

```bash
# Interactive (opens a browser):
cosign sign "$IMAGE:$TAG"
```

For the local kind registry (which does not support OCI-1.1 signatures the way ghcr.io does), use cosign's key-based mode:

```bash
# Generate a key pair if you do not have one.
cosign generate-key-pair
# Sign:
cosign sign --key cosign.key "$IMAGE:$TAG"
# Verify:
cosign verify --key cosign.pub "$IMAGE:$TAG"
```

The `cosign.pub` public key is what the Kyverno `verifyImages` policy in Exercise 4 will check signatures against. Keep `cosign.key` out of Git (the `.gitignore` already excludes it).

---

## Part F — The GitHub Actions workflow

The capstone repository contains `.github/workflows/release.yaml`. The workflow's stages:

1. **Checkout** the source.
2. **Set up Buildx** for multi-architecture builds.
3. **Log in** to the registry (ghcr.io via the workflow's auto-provided GITHUB_TOKEN).
4. **Build and push** the image.
5. **Scan** the image with Trivy; fail the workflow on HIGH or CRITICAL.
6. **Generate** the SBOM and attach it to the image (cosign attest).
7. **Sign** the image with keyless cosign (OIDC identity = the workflow's GitHub-Actions identity).
8. **Update** the Kustomize overlay's image tag and open a PR (or commit directly to `main` if the team's policy allows).

The full workflow is in `mini-project/capstone/.github/workflows/release.yaml`. Read the file before continuing.

For local testing without GitHub Actions, the make target `make ci-local` runs the equivalent of stages 4 through 7 against your local registry. The signing step uses the local key pair from Part E rather than the OIDC-keyless path.

---

## Part G — Compose for local dev

The `compose.yaml` runs the same image against a local Postgres in Docker Compose. This is the W3 12-factor flow — the application reads its configuration from environment variables, the same configuration the cluster supplies via ConfigMap and Vault Agent.

```bash
docker compose up -d
sleep 10
curl -sf http://localhost:8000/health
curl -sf http://localhost:8000/quote
docker compose down
```

This loop is what a developer iterates with locally — no kind cluster needed.

---

## Part H — Checkpoint

Capture the following and paste into `SOLUTIONS.md`:

1. The output of `docker images localhost:5001/crunch-quotes`.
2. The first 20 lines of `trivy image localhost:5001/crunch-quotes:0.1.0`.
3. The output of `cosign verify --key cosign.pub localhost:5001/crunch-quotes:0.1.0`.
4. The number of components reported in the SBOM.
5. A one-paragraph reflection: what changed in this image, between the W1-W2 Dockerfile lectures and now, that makes it a *production* image rather than a *demo* image?

The fifth item is the integration of W1-W2 and W10. Expected mentions: multi-stage build, distroless base, non-root user, HEALTHCHECK, signature, SBOM, scan in CI. Bonus credit for naming the pieces the Dockerfile *cannot* fix (the host's container runtime, the orchestrator's image-pull policy, the registry's TLS) — those are the layers below the artifact.

---

## Troubleshooting

**`docker push` fails with "http: server gave HTTP response to HTTPS client".** The local registry serves HTTP, not HTTPS. Docker requires you to register the registry as "insecure" in the daemon configuration:

```bash
# macOS / Docker Desktop: open Settings -> Docker Engine and add:
{
  "insecure-registries": ["localhost:5001"]
}
# Restart the daemon.
```

**`cosign sign` fails with "no token to use".** Keyless mode requires an OIDC identity. For interactive use, cosign opens a browser; if you are SSH'd into a remote machine, fall back to key-based signing as in Part E.

**Trivy reports CVEs in the distroless base.** The base image is rotated frequently; pull the current digest with `docker pull gcr.io/distroless/python3-debian12:nonroot` and rebuild. If the CVE persists, check the Google Container Tools issue tracker.

**The application's `/quote` endpoint returns 500.** The database is not seeded. Run `docker compose exec postgres psql -U quotes_app -d quotes -f /docker-entrypoint-initdb.d/seed.sql` (the compose setup includes the seed file; on the kind cluster, the StatefulSet's init container does the seeding).

---

## Reading

- Multi-stage builds: <https://docs.docker.com/build/building/multi-stage/>
- Distroless images: <https://github.com/GoogleContainerTools/distroless>
- Trivy image scanning: <https://trivy.dev/latest/docs/target/container_image/>
- Cosign keyless signing: <https://docs.sigstore.dev/cosign/signing/overview/>
- CycloneDX specification: <https://cyclonedx.org/specification/overview/>
- GitHub Actions OIDC: <https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect>

Continue to Exercise 3.
