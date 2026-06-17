# Resources — Week 10

A curated list. All resources are free except where noted. Read at least one item from each of the four sections below before Friday.

---

## 1. The canonical specifications and reference docs

These are the primary sources. When two blog posts disagree, these are the tiebreakers.

- **HashiCorp Vault documentation** — <https://developer.hashicorp.com/vault/docs>. The *Concepts* section ([developer.hashicorp.com/vault/docs/concepts](https://developer.hashicorp.com/vault/docs/concepts)) is the right starting place: seal/unseal, tokens, policies, secret engines, auth methods. The *Kubernetes auth* page at <https://developer.hashicorp.com/vault/docs/auth/kubernetes> is what we use in Exercise 1. The *Agent Injector* tutorial at <https://developer.hashicorp.com/vault/tutorials/kubernetes/kubernetes-sidecar> is the practical end-to-end. License note: Vault has been under the Business Source License (BSL 1.1) since August 2023; for student and non-competitive use it remains free, and the BSL terms convert each release to MPL 2.0 after four years. The OpenBao fork ([openbao.org](https://openbao.org/)) is the LF-stewarded open-source continuation if you want a fully-OSI-licensed alternative — same API.
- **Mozilla SOPS** — <https://github.com/getsops/sops>. The README is the manual. The encrypt/decrypt flow is documented at the top; the KMS provider list (AWS KMS, GCP KMS, Azure Key Vault, Vault, age, PGP) is on the second page. The `.sops.yaml` creation-rules section is where most production setups live; read it before you commit your first encrypted file.
- **age — modern file encryption** — <https://age-encryption.org/v1/> and the GitHub repo <https://github.com/FiloSottile/age>. age is "PGP minus the parts nobody used". Two key types: X25519 keypairs and SSH-key recipients. Used by SOPS, by `helm-secrets`, by `chezmoi`, by `restic`. The format spec is at <https://github.com/C2SP/C2SP/blob/main/age.md> — short and worth a read.
- **Bitnami Sealed Secrets** — <https://github.com/bitnami-labs/sealed-secrets>. The README covers the controller install (Helm or raw manifests), the `kubeseal` CLI, and the rotation story. The "How does this work?" section is short and answers most of the architecture questions.
- **External Secrets Operator** — <https://external-secrets.io/>. The *Getting Started* page is the right starting place. The *Provider* list at <https://external-secrets.io/latest/provider/> shows the integrations: Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, GitLab, Bitwarden, Doppler, 1Password, and ~25 others. The `v1` API reference is at <https://external-secrets.io/latest/api/spec/>.
- **sigstore project** — <https://sigstore.dev/>. The *How it Works* page is the right starting place. Components: **cosign** at <https://github.com/sigstore/cosign>, **fulcio** at <https://github.com/sigstore/fulcio>, **rekor** at <https://github.com/sigstore/rekor>. The public-good instances live at <https://fulcio.sigstore.dev/> (issuance) and <https://rekor.sigstore.dev/> (transparency log).
- **SLSA — Supply-chain Levels for Software Artifacts** — <https://slsa.dev/>. The v1.0 specification is at <https://slsa.dev/spec/v1.0/>. The *Levels* page ([slsa.dev/spec/v1.0/levels](https://slsa.dev/spec/v1.0/levels)) is the one-page reference. The *Provenance* schema at <https://slsa.dev/spec/v1.0/provenance> is what tools like cosign attach.
- **syft + grype** — <https://github.com/anchore/syft> and <https://github.com/anchore/grype>. Two CLIs from Anchore. syft generates SBOMs (SPDX, CycloneDX, syft-native). grype consumes SBOMs (or scans directly) and emits vulnerability findings. The docs are short; the README plus `--help` is enough.
- **CISA SBOM minimum elements** — <https://www.cisa.gov/sbom>. The U.S. CISA page is the canonical reference for the *minimum* fields a federal-procurement-eligible SBOM must contain. The original NTIA document — *The Minimum Elements For a Software Bill of Materials (SBOM)* — is linked from there as a PDF; ~30 pages, the relevant sections are 2 (Data Fields) and 3 (Automation Support).
- **SPDX specification** — <https://spdx.dev/specifications/>. The Linux Foundation's SBOM standard. ISO/IEC 5962:2021. We use the SPDX-JSON format in Exercise 4.
- **CycloneDX specification** — <https://cyclonedx.org/specification/overview/>. OWASP's SBOM standard. We use the CycloneDX-JSON format in Exercise 4.
- **in-toto attestation framework** — <https://in-toto.io/> and the spec at <https://github.com/in-toto/attestation>. The schema cosign uses for attaching attestations to images. Read the *Statement* schema before you write your first attestation.
- **Kyverno documentation** — <https://kyverno.io/docs/>. The *Image Verification* policy type at <https://kyverno.io/docs/writing-policies/verify-images/sigstore/> is the cosign-enforcement reference. Used in Challenge 1.

---

## 2. The two famous supply-chain attacks — primary sources

We will reference both in Lecture 3 and Challenge 2. Read at least one in full.

- **event-stream (November 2018).** The original disclosure is GitHub issue [dominictarr/event-stream#116](https://github.com/dominictarr/event-stream/issues/116) — short, calm, and worth reading for the maintainer's prose. Follow-up writeups: the post-incident [npm blog post](https://blog.npmjs.org/post/180565383195/details-about-the-event-stream-incident.html) (archived) and Snyk's analysis at <https://snyk.io/blog/a-post-mortem-of-the-malicious-event-stream-backdoor/>. The poisoned dependency was `flatmap-stream`, which targeted only one downstream package: `copay`, a bitcoin wallet — a deliberately narrow blast radius that delayed detection.
- **ua-parser-js (October 2021).** The disclosure thread on GitHub is [faisalman/ua-parser-js#536](https://github.com/faisalman/ua-parser-js/issues/536). The CISA advisory is at <https://www.cisa.gov/news-events/alerts/2021/10/22/malware-discovered-popular-npm-package-ua-parser-js>. Three poisoned versions (0.7.29, 0.8.0, 1.0.0) over a four-hour window installed a cryptominer plus a credential stealer; the package had ~6 million weekly downloads. The maintainer regained the account same-day.
- **SolarWinds Orion (December 2020).** The advanced precedent. Mandiant's writeup at <https://www.mandiant.com/resources/blog/sunburst-additional-technical-details> is the technical reference; the *Highly Evasive Attacker Leverages SolarWinds Supply Chain to Compromise Multiple Global Victims With SUNBURST Backdoor* paper is the canonical incident report. The attack injected malicious code into SolarWinds' *build pipeline*, not the source — which is why SLSA emphasizes hardened, isolated build platforms.
- **xz-utils backdoor (March 2024).** The most recent and arguably most concerning. The disclosure thread: <https://www.openwall.com/lists/oss-security/2024/03/29/4>. The attacker spent two years building maintainer trust on a small but ubiquitous compression library; the backdoor was in the build scripts, not the obvious source files. Read [Andres Freund's writeup](https://research.swtch.com/xz-script) for the build-script forensics. The relevant lesson: trust in a single maintainer is a supply-chain risk; multi-maintainer review and reproducible builds are not optional at the lowest levels of the stack.

---

## 3. Talks, papers, and long-form articles

These complement the docs. Pick at least two.

- **Aqua Security — *Supply Chain Security Best Practices*** — <https://blog.aquasec.com/software-supply-chain-security>. A pragmatic survey of the threat model and the controls. Free; ~30 pages of content across the linked posts.
- **Google — *Securing the Software Supply Chain*** — <https://services.google.com/fh/files/misc/securing_the_supply_chain.pdf>. Google's framing, borrowed from their internal SLSA-equivalent. The whitepaper is the source of the SLSA framework's design.
- **OpenSSF — *Concise Guide for Developing More Secure Software*** — <https://openssf.org/oss-security-guide/>. The OpenSSF (Open Source Security Foundation) is the cross-vendor body behind sigstore and the SLSA spec. The guide is short and ranks the practices by impact.
- **Dan Lorenc — *Why Sigstore*** — the original announcement at <https://blog.sigstore.dev/why-sigstore-and-how-do-i-use-it-b6f395f1bbd0>. Dan Lorenc was one of the sigstore founders; the post is the clearest single explanation of the keyless-signing design.
- **Bob Callaway — *Rekor's Public Good Mission*** — a Sigstore community talk archived at <https://www.youtube.com/c/Sigstore-AContainerSigningSolution>. The argument for a public transparency log and how it differs from a private signing service.
- **NTIA — *The Minimum Elements For a Software Bill of Materials (SBOM)*** — the original federal document, linked from <https://www.cisa.gov/sbom>. The 30-page PDF that defined the U.S. federal floor. Read sections 2 and 3 at minimum.
- **CNCF — *The State of Cloud Native Security 2024*** — <https://www.cncf.io/reports/the-state-of-cloud-native-security/>. The annual survey from the Cloud Native Computing Foundation. Useful for "what fraction of teams are actually doing this".
- **HashiCorp — *Zero Trust Security with HashiCorp Vault*** — <https://www.hashicorp.com/resources/zero-trust-security-with-hashicorp-vault>. A vendor whitepaper but a clear architectural treatment. The "identity-based access" model is what we configure in Exercise 1.

---

## 4. Hands-on guides and Helm-chart docs

For when you are stuck in the middle of an exercise.

- **`vault` Helm chart** — <https://github.com/hashicorp/vault-helm>. The values file is long; the relevant sections for this week are `server.dev`, `server.ha`, and `injector`. The README walks through dev-mode install.
- **`sealed-secrets` Helm chart** — <https://github.com/bitnami-labs/sealed-secrets/tree/main/helm/sealed-secrets>. The minimal install is `helm install sealed-secrets sealed-secrets/sealed-secrets -n kube-system`. The README covers key rotation.
- **`external-secrets` Helm chart** — <https://github.com/external-secrets/external-secrets/tree/main/deploy/charts/external-secrets>. Install once, then write `ClusterSecretStore` and `ExternalSecret` CRDs.
- **`kyverno` Helm chart** — <https://github.com/kyverno/kyverno/tree/main/charts/kyverno>. The Kyverno admission controller. We use it for image-signature verification in Challenge 1.
- **`cosign` install** — <https://docs.sigstore.dev/cosign/installation/>. Binary releases or `go install`. macOS: `brew install cosign`.
- **`syft` install** — <https://github.com/anchore/syft#installation>. macOS: `brew install syft`. Linux: the install script at <https://raw.githubusercontent.com/anchore/syft/main/install.sh>.
- **`grype` install** — <https://github.com/anchore/grype#installation>. macOS: `brew install grype`. Linux: the install script at <https://raw.githubusercontent.com/anchore/grype/main/install.sh>.
- **`age` install** — <https://github.com/FiloSottile/age#installation>. macOS: `brew install age`. Linux: most distros package it directly.
- **`sops` install** — <https://github.com/getsops/sops/releases>. Binary releases. macOS: `brew install sops`.

For instrumenting Python with these tools (Exercise 4 and the mini-project):

- **`hvac` — the official Python Vault client** — <https://hvac.readthedocs.io/>. Used in the optional Python Vault example in Exercise 1.
- **`cyclonedx-bom` — Python SBOM emitter** — <https://github.com/CycloneDX/cyclonedx-python>. Useful when you want the SBOM in build-time Python code rather than at container scan time.

---

## 5. Books (optional, not required)

- **Bridget Kromhout, Stephen Chin, Melissa McKay, Ixchel Ruiz — *DevSecOps: A Leader's Guide to Producing Secure Software Without Compromising Flow, Feedback and Continuous Improvement*** (Tag1 Press, 2023). The current best survey from the practitioner side. Out of scope for a one-week module but worth bookmarking.
- **Glenn ten Cate, Riccardo ten Cate — *Secure by Design*** (Manning, 2019). Older but durable. The "design out the secret" arguments — favor short-lived credentials over rotated long-lived ones, favor capability tokens over passwords — are still the right framing.
- **Aaron Parecki — *OAuth 2.0 Simplified*** (free at <https://www.oauth.com/>). Tangentially relevant: keyless cosign uses OIDC, which is OAuth 2.0 plus identity claims. If you have never read the OAuth spec end-to-end, this is the gentlest introduction.

---

## 6. Tools that show up in this week's exercises

Each of these is referenced from at least one exercise or the mini-project.

- **`kubectl`** — the Kubernetes CLI. <https://kubernetes.io/docs/reference/kubectl/>.
- **`helm`** — the package manager. <https://helm.sh/docs/>.
- **`kind`** — Kubernetes in Docker. <https://kind.sigs.k8s.io/>.
- **`vault`** — Vault CLI. <https://developer.hashicorp.com/vault/docs/commands>.
- **`sops`** — Mozilla SOPS CLI. <https://github.com/getsops/sops>.
- **`age`** + **`age-keygen`** — age encryption CLI. <https://age-encryption.org/v1/>.
- **`kubeseal`** — Bitnami Sealed Secrets CLI. <https://github.com/bitnami-labs/sealed-secrets#installation>.
- **`cosign`** — sigstore signing CLI. <https://docs.sigstore.dev/cosign/>.
- **`rekor-cli`** — Rekor transparency-log CLI. <https://docs.sigstore.dev/rekor/cli/>.
- **`syft`** — Anchore SBOM generator. <https://github.com/anchore/syft>.
- **`grype`** — Anchore vulnerability scanner. <https://github.com/anchore/grype>.
- **`crane`** — go-containerregistry CLI for poking at images. <https://github.com/google/go-containerregistry/tree/main/cmd/crane>. Optional but useful.

---

## 7. The list of things deliberately not covered this week

Worth flagging so you know where to look later:

- **Vault Enterprise features** — namespaces, performance replication, DR replication, the HSM seal, Sentinel policies. Not free. The open-source binary covers everything we need for this week.
- **Runtime detection (Falco, Tetragon, Tracee)** — eBPF-based runtime security. The "alert me when a pod exec's `/bin/sh`" tooling. Covered briefly in Week 12 and at <https://falco.org/>, <https://tetragon.io/>, <https://github.com/aquasecurity/tracee>.
- **Policy engines** — we cover Kyverno for image verification. **OPA Gatekeeper** ([open-policy-agent.github.io/gatekeeper](https://open-policy-agent.github.io/gatekeeper/)) is the alternative, written in Rego. Both are first-class; pick the one whose policy language you prefer.
- **Software composition analysis (SCA) at the language level** — `pip-audit`, `npm audit`, `cargo audit`, `bundler-audit`. Pre-build vulnerability scanning. Useful in CI; covered in Week 6's CI lecture. We focus on container-image scanning this week.
- **Reproducible builds** — <https://reproducible-builds.org/>. The discipline of bit-identical rebuilds from the same source. The path to SLSA L4. Out of scope for one week but worth knowing about.
- **Image-distribution attacks (typosquatting, dependency confusion in registries)** — covered briefly in Lecture 3's case studies. The full taxonomy is at <https://github.com/CICDSEC/awesome-cicd-attacks>.
- **Hardware-rooted attestation (TPM-based, Intel TDX, AMD SEV-SNP)** — the lowest layer of the supply chain. Used by confidential-computing platforms. Out of scope for an intro week.
- **Secret scanning in Git history** — `gitleaks`, `trufflehog`, GitHub's built-in secret scanning. Detects committed secrets *after the fact*. We focus on preventing the commit (SOPS, Sealed Secrets) rather than detecting after.

If a topic is on this list and you need it for your project, follow the link; it will lead you to a primary source.
