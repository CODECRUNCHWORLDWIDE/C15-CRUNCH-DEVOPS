# Exercise 3 — Sign and Verify a Container Image with cosign

**Time:** 75 minutes (20 min reading, 40 min hands-on, 15 min write-up).
**Cost:** $0.00 (uses the public sigstore infrastructure at fulcio.sigstore.dev and rekor.sigstore.dev).
**Cluster:** Host-only; no Kubernetes cluster needed for this exercise.

---

## Goal

Build a container image of the `signed_app.py` FastAPI service, push it to a registry, sign it keylessly with cosign (using your GitHub or Google identity), verify the signature from a fresh shell, and inspect the corresponding Rekor transparency-log entry.

After this exercise you should have:

- A built container image, `ghcr.io/<your-handle>/w10-signed-app:v1.0` (or `localhost:5001/...` if you used the local kind registry).
- A cosign signature attached to that image, recorded in Rekor.
- A successful `cosign verify` run with an OIDC identity policy.
- The URL of the Rekor entry for your signature.
- Notes on what changes when you sign the *digest* versus the *tag*.

---

## Step 1 — Install cosign

```bash
brew install cosign                            # macOS
# or:
go install github.com/sigstore/cosign/v2/cmd/cosign@latest
# or download from https://github.com/sigstore/cosign/releases
cosign version
```

You should see `2.4.x` or newer. Cosign 1.x is end-of-life as of 2024.

---

## Step 2 — Build the container image

Create a minimal Dockerfile in the same folder as `signed_app.py`:

```bash
cat > Dockerfile <<'EOF'
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.115.2 uvicorn==0.32.0
COPY signed_app.py .
ENV PORT=8080 \
    BUILD_VERSION=v1.0.0 \
    BUILD_GIT_SHA=manual \
    BUILD_GIT_REF=refs/heads/main \
    BUILD_TIMESTAMP=2026-05-14T09:00:00Z
EXPOSE 8080
CMD ["python3", "signed_app.py"]
EOF

# Pick ONE of the registry paths below.

# Option A: GitHub Container Registry (preferred for the keyless flow).
export REGISTRY=ghcr.io
export OWNER=<your-github-handle>   # lower case, no spaces
export IMAGE=$REGISTRY/$OWNER/w10-signed-app:v1.0

# Option B: a local kind-hosted registry (no auth, no external network).
# Spin one up:
#   docker run -d --restart=always -p 5001:5000 --name kind-registry registry:2
# Then:
#   export IMAGE=localhost:5001/w10-signed-app:v1.0

docker build -t $IMAGE .
```

---

## Step 3 — Push the image

For GHCR, log in first:

```bash
# Personal access token with `write:packages` scope, from
# https://github.com/settings/tokens
echo $GHCR_PAT | docker login ghcr.io -u $OWNER --password-stdin

docker push $IMAGE
```

For the local registry, no auth is needed:

```bash
docker push $IMAGE
```

Capture the digest. **This is the load-bearing identifier from here on.**

```bash
DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' $IMAGE | cut -d@ -f2)
echo "digest: $DIGEST"
export IMAGE_BY_DIGEST=$(echo $IMAGE | cut -d: -f1)@$DIGEST
echo "image-by-digest: $IMAGE_BY_DIGEST"
```

The output should look like `sha256:abc123...`. Cosign signs the digest, not the tag. The tag is a *pointer* that can move; the digest is *immutable*.

---

## Step 4 — Sign the image (keyless)

The keyless flow opens a browser to your OIDC provider for authentication. Cosign caches the OIDC token for the duration of the signing call only.

```bash
cosign sign $IMAGE_BY_DIGEST
```

Cosign will:

1. Generate an ephemeral keypair in memory.
2. Open <https://oauth2.sigstore.dev/auth> in your browser.
3. Ask you to sign in with your provider (Google, GitHub, Microsoft, etc.).
4. Exchange the OIDC token for a 10-minute Fulcio cert bound to your identity.
5. Sign the image's digest with the ephemeral key.
6. Upload the signature, the Fulcio cert, and a Rekor entry to <https://rekor.sigstore.dev>.
7. Push the signature as an OCI artifact to the registry, alongside the image.
8. Discard the ephemeral private key.

Expected output:

```
Generating ephemeral keys...
Retrieving signed certificate...

Note that there may be personally identifiable information associated with this signed artifact.
This may include the email address associated with the account with which you authenticate.
This information will be used for signing this artifact and will be stored in public transparency logs (...).
By typing 'y', you attest that you grant (or have permission to grant) and agree to have this information stored permanently in transparency logs.
Are you sure you would like to continue? [y/N] y

Your browser will now be opened to:
https://oauth2.sigstore.dev/auth/auth?...

Successfully verified SCT...
tlog entry created with index: 123456789
Pushing signature to: ghcr.io/<your-handle>/w10-signed-app
```

Note the `tlog entry created with index` line — that index is your Rekor entry. Save it.

---

## Step 5 — Verify the signature

In a fresh shell (or with new env vars to simulate one), verify:

```bash
cosign verify $IMAGE_BY_DIGEST \
  --certificate-identity-regexp '<your-oidc-email-regex>' \
  --certificate-oidc-issuer-regexp '.*' \
  | jq .
```

Replace `<your-oidc-email-regex>` with a regex matching your OIDC identity. For example:

- Google: `^alice@example\.com$`
- GitHub personal: `^alice@users.noreply.github.com$`
- GitHub Actions: `^https://github\.com/alice/myrepo/.+`

Expected output (abbreviated):

```json
[
  {
    "critical": {
      "identity": {
        "docker-reference": "ghcr.io/alice/w10-signed-app"
      },
      "image": {
        "docker-manifest-digest": "sha256:abc123..."
      },
      "type": "cosign container image signature"
    },
    "optional": {
      "Bundle": {...},
      "Issuer": "https://accounts.google.com",
      "Subject": "alice@example.com"
    }
  }
]
```

The Issuer and Subject fields name your OIDC identity. The Bundle field is the cosign-bundle structure that combines signature + cert + Rekor inclusion proof.

---

## Step 6 — Inspect the Rekor entry

Install `rekor-cli`:

```bash
brew install rekor-cli                         # macOS
# or:
go install github.com/sigstore/rekor/cmd/rekor-cli@latest
```

Look up the entry by image digest:

```bash
rekor-cli search --sha $DIGEST
```

You should see one or more UUIDs. Fetch the first:

```bash
ENTRY_UUID=$(rekor-cli search --sha $DIGEST --format=json | jq -r '.UUIDs[0]')
rekor-cli get --uuid $ENTRY_UUID
```

The output names:

- The signer's OIDC identity (your email or GitHub identity).
- The Fulcio CA chain.
- The signature itself.
- The Rekor inclusion proof (a Merkle-tree path back to the log root).
- The integrated timestamp.

The Rekor entry is a *public record*. Anyone who knows the image digest can look it up and see who signed it and when. This is the transparency property — you have not introduced a private side channel.

You can also browse Rekor in the web UI: <https://search.sigstore.dev/?logIndex=$TLOG_INDEX>. Replace `$TLOG_INDEX` with the number from Step 4's output.

---

## Step 7 — Try a verify with the wrong policy

To experience the failure mode, run a verify with a deliberately wrong identity regex:

```bash
cosign verify $IMAGE_BY_DIGEST \
  --certificate-identity-regexp '^impostor@example\.com$' \
  --certificate-oidc-issuer-regexp '.*'
```

Expected output:

```
Error: no matching signatures: ...does not match required identity regex...
```

Cosign refuses. This is the policy enforcement: a signature exists, the signature is valid, but the *identity* does not match what you required. Try again with the right regex; verify succeeds.

---

## Step 8 — Sign by tag and observe the warning

To see why cosign prefers digests, try signing by tag:

```bash
cosign sign $IMAGE
```

Cosign will:

1. Resolve the tag to a digest *right now*.
2. Sign the digest.
3. Warn you that you should have used the digest in the first place.

Mutate the tag (push a new build):

```bash
docker build -t $IMAGE .
docker push $IMAGE
```

Now `$IMAGE` (by tag) points at a *different* digest. The old signature is still valid for the *old* digest. A user who pulls `$IMAGE` and verifies will see "no signature found for current digest". This is by design: tags are mutable, digests are not, signatures bind to digests.

---

## Step 9 — Reflection

Write two paragraphs in your notes:

1. **What is in the Rekor entry that is NOT in the signature?** Inspect both and write down the difference.

2. **For a CI pipeline that pushes images to GHCR, what is the OIDC identity policy you would write?** Be specific about the workflow path and the branch. Defend the trade-off between strict (one workflow on one branch) and permissive (any workflow in the org).

---

## Cleanup

Keep the image in your registry; we use it again in Exercise 4 for SBOM generation. The local kind-registry (if you used Option B) can run indefinitely.

```bash
# To stop the local registry:
# docker rm -f kind-registry
```

---

## Cost summary

```
+-------------------------------------+
|  cosign binary              $0.00   |
|  Fulcio (public OpenSSF)    $0.00   |
|  Rekor (public OpenSSF)     $0.00   |
|  GHCR (free tier)           $0.00   |
|  Local kind registry        $0.00   |
|                                     |
|  Total                      $0.00   |
+-------------------------------------+
```
