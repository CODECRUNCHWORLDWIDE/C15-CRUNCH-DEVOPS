# Solutions — Week 10 Exercises

Worked answers, expected outputs, and the diagnostic questions to ask if you are stuck. Read the exercise's own write-up first; this file is the debrief, not the walkthrough.

---

## Exercise 1 — Vault and SOPS

**Q: `vault status` reports `Cannot connect to Vault`.**
Either Vault is not running or the port-forward is not active. Run `kubectl get pods -n vault` — the `vault-0` pod should be `Running` with `1/1` ready. If yes, check `kubectl get svc -n vault` and confirm the NodePort is 30200. The kind config in `kind-w10.yaml` forwards host 8200 to node 30200; if you did not start the cluster with that config, the port-forward is missing and you must explicitly run `kubectl port-forward -n vault svc/vault 8200:8200`.

**Q: `vault kv put` returns `error reading secret: permission denied`.**
The `VAULT_TOKEN` is not set or is wrong. Dev mode hard-codes the root token to `root`; if you wrote a different value to `VAULT_DEV_ROOT_TOKEN_ID` in the StatefulSet, use that. Confirm with `vault token lookup`.

**Q: The Python client reports `vault authentication failed for token-auth`.**
Same root cause. `python3 vault_demo.py` reads `VAULT_TOKEN` from the environment; if you set it in a different shell, export it again in this one.

**Q: SOPS encryption fails with `no age recipients found`.**
The `.sops.yaml` creation rules did not match the file path you tried to encrypt, or the file is not named according to the regex. Edit `.sops.yaml` to broaden the regex or rename the file.

**Q: SOPS decryption fails with `no identity matched any of the X recipients`.**
The `SOPS_AGE_KEY_FILE` is pointing at a key that is not one of the encryption recipients. Re-export the env var with the correct path and try again. If the original key is genuinely lost and there is no recovery recipient on the file, the file is unrecoverable — this is the failure mode SOPS is designed to give you.

**Reflection answers (sample):**

1. *Which tool would you use?* For a Postgres password that rotates monthly and is read by a service inside the cluster, I would use Vault + ExternalSecrets — the rotation story works, the secret never enters Git, and ESO handles the projection into a pod-readable Secret. For a third-party API key that is set once at sign-up and never rotated (e.g., a marketing-platform token), I would use SOPS + age + a `.sops.yaml` checked into the deploy repo. The trade-off: Vault gives me live rotation and audit at the cost of one more control plane; SOPS gives me Git-native review at the cost of "rotation requires a PR".

2. *Loss of the age key vs the Vault root.* Age key loss: the encrypted files are unrecoverable. Recovery is "re-encrypt every file with a new key from a second recipient who still has theirs", which requires the second recipient to have been configured up-front. Vault root-key loss: in dev mode, the root token resets on every restart (it is hard-coded), so there is nothing to lose; in HA mode, the master key is sealed under Shamir shares or auto-unseal. Lose enough shares and the cluster is unrecoverable; the discipline is "back up the shares to multiple offline locations and rotate them on a calendar".

---

## Exercise 2 — Sealed Secrets and External Secrets

**Q: `kubeseal --fetch-cert` returns an error or empty output.**
The controller is not yet running, or it has not generated its keypair. Check `kubectl get pods -n kube-system -l name=sealed-secrets-controller`. The first start-up takes ~10 seconds to generate the RSA keypair; subsequent restarts reuse the existing key from the in-cluster Secret.

**Q: The SealedSecret applies but no Secret is created.**
Three common causes. First, the `SealedSecret` is in a namespace different from what `kubeseal` expected — by default a sealed secret is bound to a (namespace, name) pair. Recreate with the correct namespace. Second, the controller's logs show a decryption error — the SealedSecret was encrypted against a *different* controller's public cert. Re-fetch the cert and re-seal. Third, the SealedSecret is bound to a name that already exists as an unmanaged Secret — delete the existing Secret first, or set `creationPolicy` appropriately on the SealedSecret template.

**Q: `vault write auth/kubernetes/config` fails with `token_reviewer_jwt` errors.**
The vault SA does not have the `system:auth-delegator` ClusterRoleBinding. `manifests-vault-dev.yaml` creates it; verify with `kubectl get clusterrolebinding vault-token-review -o yaml`. If missing, re-apply.

**Q: The `myapp-db` Secret is not appearing.**
Three checks. First, `kubectl describe externalsecret myapp-db -n default` — the status conditions tell you which step failed: secret-store connection, secret read, or secret projection. Second, `kubectl logs -n external-secrets deploy/external-secrets` for the operator's errors. Third, `vault read auth/kubernetes/role/eso-myapp` confirms the role exists with the expected bound SA.

**Q: `/verify` always reports `rotated: false` after a Vault write.**
The ESO `refreshInterval` defaults to 30 seconds in `manifests-external-secrets.yaml`. If you wait less than that, the Kubernetes Secret has not been refreshed yet. If you wait more and the Secret *has* been refreshed (`kubectl get secret myapp-db -o yaml`), but the pod still sees the old value, the issue is the pod's mount cache — Kubernetes refreshes Secret mounts on a 60-90 second cadence depending on kubelet config. Restart the pod (`kubectl rollout restart deploy/secret-consumer`) and the new value lands instantly.

**Reflection answers (sample):**

1. *SealedSecrets vs ExternalSecrets in the same repo.* SealedSecret for the OAuth client_secret of an integration that does not exist anywhere else — the secret travels with the manifest and is committed encrypted; the controller decrypts on apply; no external dependency. ExternalSecret for the production Postgres password — the secret lives in Vault, rotates on a 30-day cadence via Vault's database engine, and is projected into the cluster fresh on every refresh.

2. *Vault down failure mode.* ESO's refresh fails; the existing Kubernetes Secret keeps its last-known value; the pod's mount keeps the same value (Kubernetes does not delete a Secret because its source is unavailable). The application keeps running until either (a) Vault comes back and refresh succeeds, or (b) the pod restarts (and the Secret mount stays the same), or (c) someone deletes the ExternalSecret (which deletes the Secret with `creationPolicy: Owner`). The Vault token issued via Kubernetes auth has TTL 1h; if the token has expired during the outage and Vault comes back, ESO will re-auth and resume.

---

## Exercise 3 — cosign Sign and Verify

**Q: `cosign sign` opens the browser but the page reports "Invalid OIDC token".**
The Fulcio public-good instance has occasional outages; check <https://status.sigstore.dev/>. If sigstore is up, the issue is your OIDC provider — log in to Google/GitHub manually and confirm. If you are signing from a corporate environment with SSO + conditional access, the OIDC redirect can fail; try a different OIDC provider via `cosign sign --identity-token` with a manually-obtained token.

**Q: `cosign verify` returns `Error: no matching signatures`.**
Either no signature exists for the digest, or the identity policy does not match. Run `cosign tree $IMAGE_BY_DIGEST` first to confirm a signature is attached. Then run `cosign verify` with `--certificate-identity-regexp '.*' --certificate-oidc-issuer-regexp '.*'` to accept any signer; if that works, your identity regex is wrong. If the open regex also fails, the signature is not associated with this digest.

**Q: `docker push` to GHCR fails with `denied: permission_denied`.**
Your PAT is missing the `write:packages` scope, or you logged in as a different user than the image namespace. `docker logout ghcr.io` then re-login.

**Q: The Rekor entry shows my email address.**
Yes. Keyless signing publishes the OIDC identity to a public transparency log. This is the architectural feature: anyone can verify *who* signed a given artifact. If this is a privacy concern, use key-based signing instead (`cosign sign --key`) or use a corporate OIDC identity (a service account, not your personal email).

**Reflection answers (sample):**

1. *Signature vs Rekor entry.* The signature contains: the digest of the artifact, the signature bytes, the Fulcio cert. The Rekor entry adds: the integrated timestamp (proof the signature existed at this time), the inclusion proof (a Merkle path showing the entry is in the log), the log's signed root at integration time. Rekor is what makes the signature non-repudiable — even if the signer deletes the signature from the registry, Rekor still has a record.

2. *OIDC identity policy.* For a CI pipeline pushing to GHCR, I would write `^https://github\.com/myorg/myapp/\.github/workflows/release\.yaml@refs/heads/main$` with issuer `https://token.actions.githubusercontent.com`. Strict: one workflow file, one repo, one branch. The trade-off: any change to the workflow path (rename, move, branch) breaks signing until the policy is updated. This is the right trade-off for a small repo; for an org-wide policy across 50 repos, I would widen to `^https://github\.com/myorg/.+/\.github/workflows/release\.yaml@refs/heads/main$` — same workflow filename, any repo in the org.

---

## Exercise 4 — SBOM and grype

**Q: `syft` takes a long time on the first scan.**
syft does no caching by default; the first scan pulls the image layers if not already local and runs every cataloger. ~30-60 seconds for a small image is normal. To speed it up: `syft registry:$IMAGE` reads from the registry's manifest API without pulling.

**Q: `grype` reports "no vulnerability database found".**
The first grype run downloads the vulnerability database (~200 MB) from <https://anchore.com/oss/grype/>. If the download fails, `grype db update` retries. On a corporate network behind a proxy, set `HTTPS_PROXY` and try again.

**Q: `sbom_check.py` reports many components missing `supplier`.**
This is the most common shortfall. syft fills in `supplier` best-effort: for Python packages it uses the PyPI maintainer; for apk/deb packages it uses the package's `Maintainer` field. For some niche packages, no supplier is recorded upstream. Three options: (1) accept the gap, document it, and produce the SBOM anyway; (2) post-process the SBOM with a supplier-enrichment step (Anchore's enterprise tooling does this); (3) reject the SBOM and require the developer to investigate. Real teams pick (1) and accept partial-CISA-compliance, because the alternative is build-blocking on metadata that does not actually affect security.

**Q: `cosign attest` succeeds but `cosign verify-attestation` returns no payload.**
You are using the wrong `--type`. The type string in `--type` must match what you used in `--type` at attest time. The list of standardized types is at <https://github.com/in-toto/attestation/tree/main/spec/predicates>. For SPDX, use `spdxjson`; for CycloneDX, use `cyclonedx`; for vuln-scan, use `vuln`.

**Reflection answers (sample):**

1. *Highest-severity finding.* In a current `python:3.12-slim` image, the typical finding is a Medium-severity CVE in a stdlib component (e.g., a recent CVE in `zlib` or `expat`) that is fixed in a newer Debian point release. The application does not call zlib directly; FastAPI and Uvicorn use it through Python's stdlib for compression. Fix path: rebuild the image with a newer base (`python:3.12.5-slim` instead of `python:3.12.0-slim`). If no fix is available yet, document in `.grype.yaml` with a JIRA reference and re-check monthly.

2. *What the SBOM does not protect against.* The SBOM correctly names every dependency at build time. It does NOT protect against: (a) a build system compromise that adds a malicious component *and* updates the SBOM to hide it (the SBOM is data, not behavior); (b) a maintainer-credential theft where the same maintainer signs the malicious version (the signature still verifies because the identity is the same); (c) a future build that intentionally adds a malicious component (the SBOM and grype will record it but not flag it as "malicious" — only known CVEs are flagged). The SBOM is necessary but not sufficient. Combine with SLSA L2+ provenance (binds the build to a specific isolated builder), multi-party review (catches the "same maintainer signs malicious version" case), and runtime detection (Falco, Tetragon — catches behavior the SBOM cannot predict).

---

## Common cross-exercise pitfalls

A few problems that bite across multiple exercises and that are easier to diagnose with the right mental model:

**The kind cluster's `extraPortMappings` are sticky.** If you destroy and recreate the cluster, you must reapply the `kind-w10.yaml` config; otherwise the NodePort forwards for 8200 and 8080 are gone and `curl http://127.0.0.1:8200` will fail with `Connection refused`. This is not a Vault problem; it is a kind problem. Verify with `docker ps --filter "name=w10-" --format '{{.Names}}\t{{.Ports}}'`.

**Time skew breaks OIDC.** If your laptop's clock is more than 60 seconds off real time, Fulcio rejects the OIDC token as "not yet valid" or "expired". This happens most often on machines that have hibernated for a long time. `sudo sntp -sS time.apple.com` (macOS) or `sudo chronyc makestep` (Linux) and retry.

**`docker push` to GHCR fails with `unauthorized` after `docker login` succeeded.** GHCR uses the *image namespace* as the authorization scope. If you logged in as `alice` but try to push `ghcr.io/bob/myimage`, the push fails. Either log in as `bob` (if you own that namespace) or change the image path.

**Helm chart versions drift.** This week's manifests target specific Helm chart versions (Vault chart 0.29+, ESO 0.10+, Sealed Secrets 0.27+, Kyverno 3.3+). If you `helm repo update` after a long break, the chart's defaults may shift and the manifests may need a touch-up. Always pass `--version X.Y.Z` to pin.

**`cosign verify-attestation --type spdxjson` returns the wrong attestation.** If you have attached multiple attestations of different types, the `--type` filter selects one. If you have attached two SPDX attestations (e.g., one for the application layer and one for the full container), both are returned. Use `--predicate-type` (cosign 2.4+) to disambiguate by the in-toto predicate URI.

**ExternalSecrets in `v1` vs `v1beta1`.** ESO 0.10.x promoted the API to `v1`. Older tutorials and Helm charts may still install only the `v1beta1` CRDs. If `kubectl apply -f manifests-external-secrets.yaml` reports "no matches for kind \"ClusterSecretStore\" in version \"external-secrets.io/v1\"", upgrade the Helm chart: `helm upgrade external-secrets external-secrets/external-secrets -n external-secrets --version 0.10.6`.

**Sealed Secrets controller key not yet generated.** On the first install, the controller takes ~10 seconds after pod-ready to finish generating its RSA keypair and become ready to sign. If `kubeseal --fetch-cert` returns empty, wait 10 seconds and retry.

---

## Diagnostic command cheat sheet

When something is wrong and you do not know which layer:

```bash
# Vault layer
kubectl -n vault get pods,svc
kubectl -n vault logs deploy/vault | tail -50
curl -s http://127.0.0.1:8200/v1/sys/health | jq .

# Sealed Secrets layer
kubectl -n kube-system logs deploy/sealed-secrets-controller | tail -50
kubectl get sealedsecret -A

# ESO layer
kubectl -n external-secrets get pods
kubectl -n external-secrets logs deploy/external-secrets | tail -50
kubectl get clustersecretstore,externalsecret -A
kubectl describe externalsecret <name> -n <ns>

# Kyverno layer
kubectl -n kyverno get pods
kubectl -n kyverno logs deploy/kyverno-admission-controller | tail -100
kubectl get clusterpolicy
kubectl get events -A --sort-by='.lastTimestamp' | tail -20

# Cosign layer
cosign tree $IMAGE_BY_DIGEST
cosign verify $IMAGE_BY_DIGEST --certificate-identity-regexp '.*' --certificate-oidc-issuer-regexp '.*' 2>&1 | head -20
rekor-cli search --sha $DIGEST

# Image layer
docker inspect $IMAGE | jq '.[0].RepoDigests, .[0].Config.Env'
crane manifest $IMAGE_BY_DIGEST | jq .

# SBOM layer
jq '.packages | length' sbom.spdx.json
jq '.components | length' sbom.cdx.json
python3 sbom_check.py sbom.spdx.json
```

Run these in order from the layer closest to the symptom outward.
