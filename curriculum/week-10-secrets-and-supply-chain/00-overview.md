# Week 10 — Secrets Management and Supply-Chain Security

> *A secret is a value whose disclosure changes the system's behavior. A supply chain is every artifact, every dependency, every machine, and every human that touches a build between the developer's keyboard and the production runtime. The job, in 2026, is to keep the first secret and to make the second auditable.*

Welcome to Week 10 of **C15 · Crunch DevOps**. Last week you instrumented a service end-to-end — metrics, logs, traces, dashboards, alerts, an SLO with a burn-rate alert pair. You can see the application. You can answer questions you did not think to ask in advance. The cluster is observable; the operator is informed.

This week the question changes. It is no longer "is the service healthy" but "do I trust what is running on it". A container image arrived in your registry an hour ago. Where did it come from. Who built it. What is in it. Was it tampered with on the way. The Postgres password sitting in a YAML file in a Git repo — is that a real secret or a placeholder. The Apache Log4j library buried six dependencies deep inside the service — was it patched after CVE-2021-44228, and how would you know without grepping through every image. These are supply-chain questions. They are the questions that, between 2018 and 2024, became the central security questions in every regulated industry.

We will cover two halves of one story. **The first half is secrets management** — the discipline of keeping passwords, API keys, certificates, and other high-value strings out of source control and out of human hands. We will install **HashiCorp Vault** in open-source mode and bring it up against a `kind` cluster. We will encrypt files with **Mozilla SOPS** using **age** keys and check the encrypted files into Git the way you would check in any other file. We will install **Bitnami Sealed Secrets** so that a Kubernetes `Secret` can live in Git as an encrypted CRD and the cluster decrypts it at apply time. We will install the **External Secrets Operator** and configure it to read from Vault and project secrets into the cluster as native `Secret` objects. Four different tools that solve four overlapping problems; we will be explicit about which problem each one solves and why a real team often uses more than one.

**The second half is supply-chain security** — the discipline of signing, attesting, and verifying every artifact that reaches production. We will read the **SLSA** specification ([slsa.dev](https://slsa.dev/)) — the framework for grading supply-chain integrity — and understand what each of the four levels demands. We will sign a container image with **cosign** ([sigstore.dev](https://sigstore.dev/)), watch the signature record itself in the **rekor** transparency log, and verify the signature from a fresh client. We will generate a **Software Bill of Materials (SBOM)** with **syft** in SPDX and CycloneDX formats, scan it for known vulnerabilities with **grype**, and write an admission policy that refuses to deploy an image whose SBOM is missing or whose vulnerability scan exceeds a threshold. We will read the **CISA Minimum Elements for an SBOM** ([cisa.gov](https://www.cisa.gov/sbom)) so we know which fields the U.S. federal procurement floor requires. We will study two famous supply-chain attacks — **event-stream** in November 2018 and **ua-parser-js** in October 2021 — and reason about which of this week's tools would have caught each one.

By Sunday you will have signed an image, generated an SBOM, scanned it, deployed a service whose secrets live in Vault, and refused (in a Kyverno policy) to deploy an image without a valid cosign signature. The cluster from Week 9 grows another layer: it now knows where its software came from and what is inside the YAML it applies.

---

## Learning objectives

By the end of this week, you will be able to:

- **Distinguish** the four problems that the words "secrets management" cover in practice: (1) storing the secret somewhere encrypted at rest, (2) controlling who can read it, (3) rotating it without redeploying every consumer, (4) auditing every read. Explain why a `kubectl create secret` alone solves only (1).
- **Install** HashiCorp Vault in open-source dev mode and in HA mode on `kind`. Initialize the cluster, unseal it (or use auto-unseal where available), and write a secret to the K/V engine. Configure a **policy** that grants a service account read access to one path and only one path.
- **Configure** Vault's **Kubernetes auth method** so a pod's service-account JWT becomes a Vault token. Reason about why this is preferable to embedding a long-lived Vault token in a `Secret`. Cite the docs at <https://developer.hashicorp.com/vault/docs/auth/kubernetes>.
- **Encrypt** a file with **SOPS** ([github.com/getsops/sops](https://github.com/getsops/sops)) using an **age** keypair ([github.com/FiloSottile/age](https://github.com/FiloSottile/age)). Commit the encrypted file to Git; recover the plaintext by running `sops -d`. Understand SOPS's per-value (not per-file) encryption and why that matters for code review.
- **Install** Bitnami **Sealed Secrets** ([github.com/bitnami-labs/sealed-secrets](https://github.com/bitnami-labs/sealed-secrets)). Convert a `Secret` to a `SealedSecret` using `kubeseal`; commit the SealedSecret to Git; watch the controller decrypt it in-cluster on apply. Reason about why the SealedSecrets controller's private key never leaves the cluster.
- **Install** the **External Secrets Operator** ([external-secrets.io](https://external-secrets.io/)). Configure a `ClusterSecretStore` that points at Vault. Define an `ExternalSecret` that projects a Vault path into a Kubernetes `Secret`. Reason about the difference between External Secrets (pull from external store) and Sealed Secrets (encrypted-in-Git).
- **Articulate** the SLSA framework. Name each of the four levels (Build L1 through L4) and the verification properties each one guarantees. Cite [slsa.dev/spec](https://slsa.dev/spec/v1.0/). Explain why a build run on a developer's laptop is, in SLSA terms, never above L1.
- **Sign** a container image with **cosign** ([github.com/sigstore/cosign](https://github.com/sigstore/cosign)). Use keyless signing (OIDC against Fulcio + Rekor transparency log) and key-based signing. Verify a signed image from a fresh shell.
- **Generate** a Software Bill of Materials with **syft** ([github.com/anchore/syft](https://github.com/anchore/syft)) in SPDX-JSON and CycloneDX formats. Scan the SBOM with **grype** ([github.com/anchore/grype](https://github.com/anchore/grype)). Read the output; distinguish a high-severity finding that is actually exploitable from one that is in a library you never call.
- **Recite** the CISA Minimum Elements for an SBOM ([cisa.gov/sbom](https://www.cisa.gov/sbom)): supplier name, component name, version, unique identifier (PURL or CPE), dependency relationship, author, timestamp. Verify a syft-generated SBOM contains all seven.
- **Write** a Kyverno (or OPA Gatekeeper) admission policy that requires every image in production namespaces to carry a verifiable cosign signature. Reason about the failure modes (controller down, registry slow, network partition) and how policy authors handle them.
- **Tell** the event-stream (2018) story and the ua-parser-js (2021) story. Identify, for each, the failure mode (npm package takeover, NPM account compromise, dependency-confusion), the blast radius, and which of this week's tools — pin-by-digest, SBOM diffing, cosign-verified provenance — would have helped.
- **Defend** the choice of an in-toto / SLSA provenance attestation as the audit trail of choice, over a vendor's proprietary build-history blob. Cite [in-toto.io](https://in-toto.io/) and the SLSA provenance schema.

---

## Prerequisites

This week assumes you have completed **Weeks 1-9 of C15**. Specifically:

- You finished Week 9's mini-project — a FastAPI service with full observability on a `kind` cluster. We will not reuse that cluster directly; we will spin up `w10` fresh. The discipline you learned — apply manifests, watch reconcile, read events — is what we use this week.
- You have `kind` (0.24+), `kubectl` (1.31+), `helm` (3.14+), `docker` running, `python3` (3.11+), and a fresh terminal where you can install half a dozen new CLIs. Verify:

```bash
kind version
kubectl version --client
helm version --short
docker info | head -1
python3 --version
```

- You have ~6 GB of free RAM. The Week 10 footprint is lighter than Week 9's — no Prometheus retention, no Grafana — but Vault in HA mode wants ~500 MB and the various operators each add 100-200 MB. Plus 2-3 GB for the kind cluster itself.
- You have **Docker Hub** or **GitHub Container Registry** credentials. We will push a signed image. If you do not have a registry, we will use `kind`'s built-in local registry; the cosign flow works identically.
- You understand the difference between a Kubernetes `Secret` (base64 — not encryption) and an encrypted-at-rest backing store (etcd encryption, an external KMS, Sealed Secrets, SOPS). Week 7 covered the first; this week covers the second.

We use **Kubernetes 1.31+**, **Vault 1.18+**, **SOPS 3.9+**, **age 1.2+**, **Sealed Secrets 0.27+**, **External Secrets 0.10+**, **cosign 2.4+**, **syft 1.18+**, **grype 0.85+**, and **Kyverno 1.13+**. All current; no deprecated APIs in this week's material. API versions used: `apps/v1` (Deployment), `v1` (Secret, ServiceAccount, ConfigMap), `bitnami.com/v1alpha1` (SealedSecret), `external-secrets.io/v1` (ExternalSecret, ClusterSecretStore — note: `v1` is the GA version as of External Secrets 0.10, replacing the older `v1beta1`), `kyverno.io/v1` (ClusterPolicy).

If you are coming back to this material after a break, the relevant 2025-2026 changes are: (a) **External Secrets Operator promoted its API to `v1`** in 2024, so `v1beta1` examples on the web are still functionally correct but on the deprecation path; (b) **cosign 2.0 removed the legacy KMS provider URIs** in favor of the unified `--key` syntax — old `awskms://` URIs still work but the docs now show the cleaner form; (c) **Sigstore's Fulcio now issues short-lived certificates (10 minutes)** for keyless signing, with the signature event itself recorded in Rekor — the practical workflow is unchanged but the cert lifetime is shorter than it was in 2022.

---

## Topics covered

- **Why `kubectl create secret` is not enough.** Kubernetes `Secret` objects are stored in etcd as base64 — not encryption. Anyone with `get secrets` RBAC sees the plaintext. The fix is one or more of: etcd encryption-at-rest (cluster operator concern), External Secrets backed by a vault, or Sealed Secrets / SOPS for Git-checked-in encryption. We cover all three.
- **HashiCorp Vault, open-source path.** Architecture: storage backend (file, integrated raft, Consul) plus seal/unseal mechanism plus auth methods plus secret engines. Initialize, unseal, write to the K/V v2 engine. The PKI engine (issue short-lived certs). The Transit engine (encryption-as-a-service). Auth methods: AppRole (for machines outside K8s), Kubernetes auth (for pods inside K8s), JWT/OIDC (for CI/CD pipelines). Policies as HCL: `path "secret/data/myapp/*" { capabilities = ["read"] }`.
- **Vault Agent and the sidecar pattern.** A pod runs Vault Agent as a sidecar; the agent authenticates to Vault using the pod's service-account JWT, fetches secrets, renders them into a tmpfs volume, and renews them on a schedule. The application reads from a file. The application never sees a Vault token. The Vault Agent Injector ([developer.hashicorp.com/vault/docs/platform/k8s/injector](https://developer.hashicorp.com/vault/docs/platform/k8s/injector)) automates injection via pod annotations.
- **Why Vault, vs cloud KMS, vs External Secrets pointing at a cloud KMS.** Vault is the open-source pick that runs anywhere. Cloud KMS (AWS KMS, GCP KMS, Azure Key Vault) is the cloud-native pick that is cheaper and easier if you are already in one cloud. External Secrets Operator is the abstraction layer that lets the application not care which one you picked. We use Vault this week because it is free and self-contained; the External Secrets pattern transfers.
- **Mozilla SOPS + age.** SOPS encrypts files in place — YAML, JSON, ENV, INI, binary — per-value rather than per-file. The encrypted file is human-readable in structure, so code review still works. age ([age-encryption.org/v1](https://age-encryption.org/v1/)) is the lightweight modern alternative to PGP for SOPS keys. SOPS supports KMS providers (AWS KMS, GCP KMS, Azure Key Vault, Vault, age, PGP) — we use age because it is local and free. The workflow: `sops -e -i secrets.yaml`, commit, on the consumer `sops -d secrets.yaml`.
- **Bitnami Sealed Secrets.** A controller that runs in the cluster, holds a private key, and reconciles `SealedSecret` CRDs into native `Secret` objects. The `kubeseal` CLI encrypts a `Secret` against the controller's public key. The encrypted blob is safe to commit. The private key never leaves the cluster (back it up; if it is lost, all SealedSecrets are unreadable). One-cluster scope unless you copy keys.
- **External Secrets Operator (ESO).** The other end of the spectrum: the secret lives in a real external store (Vault, AWS Secrets Manager, GCP Secret Manager, etc.) and ESO is the controller that projects the external secret into a Kubernetes Secret on a schedule. Cluster operators reconfigure the store without touching application manifests. Two CRDs: `ClusterSecretStore` (the connection to the store) and `ExternalSecret` (the request for a specific secret).
- **Which-when matrix.** SOPS: for static config encrypted in Git, decrypted at apply time by the CD tool. Sealed Secrets: for the same use case but where the CD tool does the decrypting via the in-cluster controller. ESO: when the secret lives outside Git and changes outside Git. Vault: when you need rotation, audit, short-lived tokens, dynamic credentials. Real teams combine SOPS for boot-time config + ESO + Vault for runtime credentials.
- **The supply-chain threat model.** From SolarWinds (2020) onward, the assumption that "my dependencies are safe" failed catastrophically. The supply chain attacks of 2020-2024 — SolarWinds, Codecov, Kaseya, 3CX, MOVEit, the 2024 xz-utils backdoor — were not bugs; they were intentional injections by attackers who had compromised the *build pipeline*, not the source. The defensive shift: do not just verify the source, verify the build.
- **SLSA — Supply-chain Levels for Software Artifacts.** The framework from <https://slsa.dev/>. Build L1: build is scripted and produces provenance. L2: hosted build platform that signs the provenance. L3: build platform is hardened, builds are isolated, the provenance is non-falsifiable. L4 (now folded into L3 in v1.0): two-party review and reproducibility. We will reach L2 in this week's exercises and discuss what L3 would require.
- **sigstore — the keyless signing project.** Three components: **cosign** (the signing CLI), **fulcio** (a free CA that issues 10-minute identity certs based on OIDC tokens — your Google / GitHub / Microsoft login), **rekor** (an immutable transparency log of every signature ever issued by Fulcio). Keyless signing means: the signer authenticates to an OIDC provider, Fulcio issues a short-lived cert tied to that identity, cosign signs with the cert and uploads a signature record to rekor. Verifiers check rekor and Fulcio. No long-lived key to lose. Free public infrastructure at <https://sigstore.dev/>.
- **SBOM — Software Bill of Materials.** A machine-readable list of every component in a binary. Two standards: **SPDX** ([spdx.dev](https://spdx.dev/)) — Linux Foundation, used in regulated industries, ISO/IEC 5962:2021; **CycloneDX** ([cyclonedx.org](https://cyclonedx.org/)) — OWASP, more security-oriented, easier JSON shape. Most tools emit both. **syft** generates SBOMs by scanning containers, directories, or archives. **grype** consumes an SBOM (or scans directly) and emits vulnerability findings, matching against the NVD CVE database and Anchore's enriched DB.
- **CISA Minimum Elements for an SBOM.** The U.S. federal procurement floor, defined by CISA at <https://www.cisa.gov/sbom>: data fields (supplier, component name, version, unique identifier, dependency, author, timestamp), automation support (machine-readable, SPDX or CycloneDX), practices and processes (frequency, depth, distribution). Any tool we use this week must generate output that satisfies these.
- **Provenance attestations.** A signed statement of *how* an artifact was built — the source repo, the commit SHA, the builder, the inputs, the steps. Distinct from the signature, which only proves *that* the artifact was signed. The SLSA Provenance schema ([slsa.dev/spec/v1.0/provenance](https://slsa.dev/spec/v1.0/provenance)) is the canonical shape. **in-toto** ([in-toto.io](https://in-toto.io/)) is the underlying attestation framework. cosign attaches an attestation to an image just like it attaches a signature.
- **Two attack case studies.** **event-stream (2018):** a popular npm package, ~2 million downloads/week. The maintainer handed it off to a stranger who, three months later, pushed a minor-version bump injecting a bitcoin-wallet exfiltration payload targeted at a specific downstream package. Disclosed via [a GitHub issue](https://github.com/dominictarr/event-stream/issues/116). **ua-parser-js (2021):** a popular npm package, ~6 million downloads/week. The maintainer's NPM account was compromised; the attacker published three poisoned versions over a four-hour window that ran a cryptominer + credential stealer. Disclosed by [the maintainer's tweet](https://github.com/faisalman/ua-parser-js/issues/536) and later [a CISA advisory](https://www.cisa.gov/news-events/alerts/2021/10/22/malware-discovered-popular-npm-package-ua-parser-js). For each, we map the defensive controls.

---

## Weekly schedule

The schedule below adds up to approximately **35 hours**. Total is what matters; reshuffle within the week as your life demands.

| Day       | Focus                                                       | Lectures | Exercises | Challenges | Quiz/Read | Homework | Mini-Project | Self-Study | Daily Total |
|-----------|-------------------------------------------------------------|---------:|----------:|-----------:|----------:|---------:|-------------:|-----------:|------------:|
| Monday    | Vault, SOPS, Sealed Secrets, ESO (Lecture 1)                |    2h    |    1.5h   |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     5.5h    |
| Tuesday   | SLSA, sigstore (cosign, rekor, fulcio) (Lecture 2)          |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Wednesday | SBOM with syft, scan with grype, attestations (Lecture 3)   |    2h    |    2h     |     1h     |    0.5h   |   1h     |     0h       |    0.5h    |     7h      |
| Thursday  | Hands-on: sign + SBOM + admission policy end-to-end         |    0h    |    2h     |     1h     |    0.5h   |   1h     |     1h       |    0.5h    |     6h      |
| Friday    | Mini-project — secret-aware, signature-gated service        |    0h    |    0h     |     0h     |    0.5h   |   1h     |     3h       |    0.5h    |     5h      |
| Saturday  | Mini-project finish; read the SLSA spec end to end          |    0h    |    0h     |     0h     |    1h     |   0h     |     2h       |    0h      |     3h      |
| Sunday    | Quiz, recap, tear down clusters                             |    0h    |    0h     |     0h     |    0.5h   |   0h     |     1h       |    0h      |     1.5h    |
| **Total** |                                                             | **6h**   | **7.5h**  | **2h**     | **4h**    | **5h**   | **7h**       | **2.5h**   | **34h**     |

---

## How to navigate this week

| File | What is inside |
|------|----------------|
| [README.md](./00-overview.md) | This overview (you are here) |
| [resources.md](./01-resources.md) | Curated readings: Vault docs, SOPS GitHub, Sealed Secrets, sigstore.dev, slsa.dev, CISA SBOM |
| [lecture-notes/01-secrets-vault-sops-sealed-eso.md](./02-lecture-notes/01-secrets-vault-sops-sealed-eso.md) | The four secrets tools, the which-when matrix, the Vault auth flow |
| [lecture-notes/02-slsa-sigstore-cosign-rekor-fulcio.md](./02-lecture-notes/02-slsa-sigstore-cosign-rekor-fulcio.md) | SLSA levels, sigstore architecture, keyless signing, transparency logs |
| [lecture-notes/03-sbom-syft-grype-attestations-attacks.md](./02-lecture-notes/03-sbom-syft-grype-attestations-attacks.md) | SBOMs, SPDX vs CycloneDX, vulnerability scanning, two case studies |
| [exercises/exercise-01-vault-and-sops.md](./03-exercises/exercise-01-vault-and-sops.md) | Install Vault in dev mode; encrypt a file with SOPS + age |
| [exercises/exercise-02-sealed-secrets-and-eso.md](./03-exercises/exercise-02-sealed-secrets-and-eso.md) | Install Sealed Secrets and External Secrets; project a Vault secret into a pod |
| [exercises/exercise-03-cosign-sign-and-verify.md](./03-exercises/exercise-03-cosign-sign-and-verify.md) | Build, sign, push, and verify a container image; look at rekor |
| [exercises/exercise-04-sbom-with-syft-and-grype.md](./03-exercises/exercise-04-sbom-with-syft-and-grype.md) | Generate SBOM, scan for CVEs, attach the attestation |
| [exercises/SOLUTIONS.md](./03-exercises/SOLUTIONS.md) | Worked solutions, expected output, the diagnostic questions to ask |
| [challenges/challenge-01-block-unsigned-images-with-kyverno.md](./04-challenges/challenge-01-block-unsigned-images-with-kyverno.md) | A Kyverno policy that requires cosign signatures on production images |
| [challenges/challenge-02-trace-a-supply-chain-attack.md](./04-challenges/challenge-02-trace-a-supply-chain-attack.md) | A whodunnit: trace a poisoned image back through the build provenance |
| [quiz.md](./05-quiz.md) | 12 multiple-choice questions |
| [homework.md](./06-homework.md) | Six practice problems |
| [mini-project/README.md](./07-mini-project/00-overview.md) | A signed, SBOM'd, secret-aware service on kind with Kyverno enforcement |

---

## A note on cost

Week 10 is structured so that **no student needs a credit card to complete it**. Every tool in this week — Vault open-source, SOPS, age, Sealed Secrets, External Secrets Operator, cosign, rekor, fulcio (the public-good instance at <https://rekor.sigstore.dev/>), syft, grype, Kyverno — is open-source and free. The Fulcio CA and Rekor transparency log are operated as a public good by the OpenSSF; you sign in with your Google or GitHub account and pay nothing.

```
+-----------------------------------------------------+
|  COST PANEL - Week 10 incremental spend             |
|                                                     |
|  kind cluster (local, in Docker)         $0.00      |
|  HashiCorp Vault (open-source)           $0.00      |
|  Mozilla SOPS + age                      $0.00      |
|  Bitnami Sealed Secrets                  $0.00      |
|  External Secrets Operator               $0.00      |
|  cosign (sigstore client)                $0.00      |
|  Fulcio (public OpenSSF instance)        $0.00      |
|  Rekor (public OpenSSF instance)         $0.00      |
|  syft + grype (Anchore, Apache 2.0)      $0.00      |
|  Kyverno (Nirmata, Apache 2.0)           $0.00      |
|                                                     |
|  Optional reading                                   |
|    Google "Securing the Software Supply Chain"      |
|      whitepaper (free)                   $0.00      |
|    Aqua "Supply Chain Security Best                 |
|      Practices" (free)                   $0.00      |
|                                                     |
|  Required subtotal (kind path):          $0.00      |
+-----------------------------------------------------+
```

If you push the same flow to a real cloud — sign images pushed to GHCR or DockerHub, run Vault on a real cluster — the public sigstore infrastructure is still free and the only cost is the cloud compute, the same $0.10-$0.50/hour as last week. Vault Enterprise (with namespaces, performance replication, the HSM seal) is *not free* and is *not used in this week's material*; we use the open-source Vault binary throughout. The license is BSL 1.1 since IBM's 2024 acquisition of HashiCorp, which is source-available but not OSI open source; for student / non-competitive use it remains free.

---

## Stretch goals

If you finish early and want to push further:

- Replace SOPS+age with **SOPS+Vault**. Configure SOPS to use Vault's Transit secret engine as the KMS provider. The encrypted file in Git references a Vault transit key; only operators with Vault credentials can decrypt. Useful when the team already runs Vault and does not want to manage age keys.
- Add a second cosign signature to your image, signed by a **second identity** (a different OIDC account or a different key). Write a Kyverno policy that requires *at least two distinct signers*. This is the manual analogue to the SLSA L4 "two-party review" property.
- Generate an SBOM not just for the container image but for **the running cluster** using **`trivy k8s`** or **`kubescape`**. Compare the surface area: what is in the image vs what is on the host vs what is in cluster components.
- Read the **NIST SP 800-218 Secure Software Development Framework (SSDF)** at <https://csrc.nist.gov/Projects/ssdf>. The U.S. federal procurement framework that mandates SBOM, attestation, and provenance. Identify the practices that this week's tooling addresses and the ones it does not.
- Write a **GitHub Actions** workflow that signs an image with cosign's **keyless OIDC** flow — using GitHub's OIDC token as the Fulcio identity. The "no-key" deployment story: no long-lived secrets in any CI/CD environment. Documented at <https://docs.sigstore.dev/cosign/signing/overview/>.
- Read the **Google "Securing the Software Supply Chain" whitepaper** at <https://services.google.com/fh/files/misc/securing_the_supply_chain.pdf>. Google's framing — borrowing from their internal SLSA-equivalent for Borg builds. Useful prior art.

---

## Up next

Continue to **Week 11 — Service Mesh and Zero-Trust Networking** once you have shipped your Week 10 mini-project. Week 11 takes the security posture into the network layer: mTLS between every pod (Istio or Linkerd), the question of "service mesh or plain Kubernetes networking", network policies (Calico, Cilium), and the zero-trust pattern that says no pod trusts any other pod by default. Week 12 closes the curriculum with production-readiness: capacity planning, on-call rotations, incident review, the operational hygiene of a service that has graduated from "we wrote it" to "we run it".

A note on the order: we did secrets and supply chain (Week 10) before service mesh (Week 11) deliberately. The argument is that the mesh's value proposition — mTLS, identity-based authorization, per-pod certificates — depends on a working key-issuance story. The mesh's CA *is* a secret-management system, and it inherits all of Week 10's concerns about how the root key is stored and rotated. By learning Vault, cosign, and the provenance vocabulary first, the mesh chapter reads as "another consumer of the secrets and signatures discipline you already built" rather than as a new system invented from nothing.

---

*If you find errors in this material, please open an issue or send a PR. Future learners will thank you.*
