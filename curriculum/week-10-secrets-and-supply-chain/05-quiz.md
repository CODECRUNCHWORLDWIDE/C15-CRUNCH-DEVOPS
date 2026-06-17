# Quiz — Week 10

Twelve multiple-choice questions. Answer all twelve; one paragraph of reasoning each. The answer key is at the bottom. Do not peek.

---

### Q1. A Kubernetes `Secret` object is:

a) Encrypted at rest in etcd by default.
b) Base64-encoded, which is a transport encoding, not encryption.
c) Stored as a signed-only blob, with cosign verification on read.
d) Hidden from any user without the `cluster-admin` role.

---

### Q2. The Vault Kubernetes auth method works by:

a) Embedding a long-lived Vault token in a Kubernetes Secret.
b) Validating the pod's service-account JWT against the cluster API via TokenReview.
c) Issuing a TLS client cert to each pod from Vault's PKI engine.
d) Querying the Kubernetes audit log for recent pod-create events.

---

### Q3. SOPS encrypts:

a) An entire file as one blob, breaking the file's original structure.
b) Each value in a structured file individually, preserving the structure for code review.
c) Only the keys, leaving the values in plaintext.
d) Filenames and contents using PGP only.

---

### Q4. The Sealed Secrets controller's private key:

a) Lives on every developer's laptop.
b) Is uploaded to the GitHub repo so reviewers can verify SealedSecrets.
c) Is held inside the cluster, in a Secret in `kube-system`, and never leaves.
d) Is generated fresh on every controller restart, invalidating older SealedSecrets.

---

### Q5. The External Secrets Operator's role is to:

a) Encrypt local Kubernetes Secrets and commit them to Git.
b) Pull secrets from an external store on a schedule and project them into Kubernetes Secrets.
c) Replace the kubelet's secret-mounting behavior.
d) Sign images with cosign at admission time.

---

### Q6. SLSA Build Level 2 requires:

a) Reproducible bit-identical builds.
b) Two-party review of every source change.
c) A hosted build platform that signs the provenance.
d) An air-gapped build environment.

---

### Q7. Cosign keyless signing depends on:

a) A long-lived signing key held in a hardware token.
b) An OIDC token, an ephemeral cert from Fulcio, and a Rekor transparency-log entry.
c) A pre-shared symmetric key between signer and verifier.
d) The signer's SSH key, registered with the registry.

---

### Q8. The Rekor transparency log:

a) Is a private database operated by each cosign user.
b) Is a public, append-only log of every signature issued via sigstore.
c) Stores the artifact bytes themselves, not just signatures.
d) Is opt-in; signatures default to off-log.

---

### Q9. The CISA Minimum Elements for an SBOM include:

a) Supplier, component name, version, unique identifier, dependency, author, timestamp.
b) Only the package name and version.
c) The full source code of every dependency.
d) Vulnerability scan results.

---

### Q10. The difference between SPDX and CycloneDX is:

a) SPDX is closed-source; CycloneDX is open.
b) SPDX is the Linux Foundation / ISO standard; CycloneDX is OWASP and was designed with vulnerability correlation in mind.
c) SPDX is for binaries; CycloneDX is for source code.
d) SPDX is JSON-only; CycloneDX is XML-only.

---

### Q11. In the event-stream (2018) attack, the primary defensive control that would have caught the malicious dependency was:

a) Running an antivirus on the build server.
b) Pinning dependencies by content hash plus SBOM diffing across builds.
c) Using a CDN with DDoS protection.
d) Disabling JavaScript in the browser.

---

### Q12. A Kyverno `ClusterPolicy` of type `verifyImages` with `failurePolicy: Fail` will:

a) Reject Pod creation if the admission webhook is unreachable.
b) Allow Pod creation regardless of the webhook's state.
c) Only apply to Deployments, not Pods.
d) Only verify in the `default` namespace.

---

## Answer key

1. **b)** Base64 is transport encoding, not encryption. Etcd encryption-at-rest is a separate, opt-in feature. Kubernetes Secrets are *containers* for sensitive bytes; the encryption layer is layered on top.

2. **b)** The pod presents its SA JWT; Vault calls the cluster's TokenReview API via the `system:auth-delegator` ClusterRoleBinding; on success Vault issues a short-lived Vault token bound to the configured role.

3. **b)** Per-value encryption preserves the file's structure. The values are opaque; the keys, the shape, and the file's existence are not. This is why SOPS-encrypted files can be code-reviewed.

4. **c)** The controller generates the keypair on first start and stores it in `kube-system` as a Secret. The CLI (`kubeseal`) fetches only the public key. Backing up the controller's Secret is the operator's responsibility.

5. **b)** ESO is a controller that runs in the cluster, holds credentials to one or more external stores, and projects external secrets into native Kubernetes Secrets on a configurable refresh interval. The pod sees a normal Secret.

6. **c)** L2 requires a hosted platform that signs the provenance. L4 (in v0.1) was reproducibility; v1.0 removed L4 and consolidated the framework. A developer's laptop cannot reach L2 because there is no hosted-platform signing key.

7. **b)** OIDC token → Fulcio short-lived cert → cosign signs with the ephemeral key → Rekor records the event. The "keyless" property is that no long-lived signing key exists; the cert expires in ~10 minutes.

8. **b)** Rekor is public, append-only, and Merkle-tree-backed. It is the architectural analogue of Certificate Transparency. Anyone can search it.

9. **a)** The seven minimum elements from the NTIA report adopted by CISA. Vulnerability scan results are *separate* artifacts, not part of the SBOM minimum.

10. **b)** SPDX is the ISO standard (ISO/IEC 5962:2021) maintained by the Linux Foundation; CycloneDX is the OWASP standard designed with security tooling in mind. Both are JSON-and-XML; both are open; both are widely supported.

11. **b)** Content-hash pinning would have prevented the auto-install of the new version; SBOM diffing across builds would have surfaced the new `flatmap-stream` dependency for review. Together they would have caught it.

12. **a)** `failurePolicy: Fail` means "if the webhook is unreachable, default to rejecting the request". This is the strict choice; `failurePolicy: Ignore` is the permissive one that allows admission if the webhook is down. For high-stakes policies you want Fail; the trade-off is that webhook outages block all Pod creation.

---

## Scoring

12/12 — you have internalized the week. Move to the mini-project with confidence.
9-11/12 — solid; re-read the lecture for the misses.
6-8/12 — you skipped a lecture; go back.
<6/12 — re-read all three lectures before the mini-project.
