# Lecture 2 — SLSA, Sigstore, and Keyless Signing

> *To verify an artifact is to ask three questions: what is it, where did it come from, and who vouches for it. Until 2021 we did not have a public answer to any of them.*

Yesterday we made the cluster's *runtime* secrets honest — Vault, SOPS, Sealed Secrets, External Secrets. Today we turn to the cluster's *build-time* trust. The question is no longer "is the password safe" but "is the container image the one I think it is".

The story this lecture tells unfolds in three threads. The first is **why** — the supply-chain attacks of the early 2020s that made the industry care. The second is **the framework** — SLSA, the Supply-chain Levels for Software Artifacts spec from <https://slsa.dev/>, which defines what "the build pipeline is trustworthy" actually means. The third is **the tooling** — sigstore, the OpenSSF project that gave the industry a free, keyless, transparency-logged way to sign and verify artifacts. By the end you will have read the SLSA spec end-to-end (or know where to find it), understood what cosign actually does when you type `cosign sign`, and be ready to write the first signed-image flow in Exercise 3.

---

## 1. Why supply chain became the story

The pre-2020 mental model of "is this software safe" was, roughly: trust your dependencies because the maintainers are trustworthy, scan your sources with SAST tools, run your binaries through an antivirus. This model was not wrong so much as it was incomplete. It had one assumption — *the build pipeline that turned source into binary was trustworthy* — that, from 2020 onward, repeatedly turned out to be the weakest link.

The case studies are short and worth knowing by name.

**SolarWinds Orion, December 2020.** Attackers compromised SolarWinds' *build server* (Microsoft TeamCity, the on-prem one). They inserted a malicious payload — SUNBURST — into the build output of the legitimate Orion product. The source code was clean. The build artifact was malicious. Eighteen thousand customers received the poisoned update, including most of the U.S. federal cabinet. Documented in depth in [Mandiant's analysis](https://www.mandiant.com/resources/blog/sunburst-additional-technical-details). The lesson: source-level review is insufficient; the *build* itself must be attestable.

**Codecov bash uploader, April 2021.** Attackers stole Codecov's Bash uploader script — the script that millions of CI pipelines `curl | bash`'d on every build. They modified it to exfiltrate environment variables (which, for many builds, contained CI secrets). Affected: ~29,000 customers. Documented in [Codecov's incident report](https://about.codecov.io/security-update/). The lesson: the supply chain includes the tools you fetch *during* the build, not just the dependencies you declare.

**Kaseya VSA, July 2021.** Attackers exploited a zero-day in Kaseya VSA (an RMM tool for managed-service providers) and pushed ransomware *through the MSPs* to their downstream customers. Roughly 1,500 small businesses encrypted. Documented in [CISA's advisory](https://www.cisa.gov/news-events/cybersecurity-advisories/aa21-209a). The lesson: the supply chain is multi-hop; "trust" needs to compose across vendor boundaries.

**MOVEit, May 2023.** Attackers exploited a SQL injection in Progress Software's MOVEit Transfer product, used by thousands of organizations to move files between counterparties. Affected: ~2,700 organizations including the U.S. Department of Energy. Documented at [progress.com/security-bulletins](https://www.progress.com/security/moveit-transfer-and-moveit-cloud-vulnerability). The lesson: managed-software vendors are themselves single points of failure for their customers' supply chains.

**xz-utils, March 2024.** The most recent and arguably most concerning. A patient attacker spent two years building maintainer-level trust on `xz-utils`, a ubiquitous compression library used in the dependency graph of nearly every Linux distribution and many container base images. The backdoor was inserted into build *scripts* — the `m4` autotools macros that produced the build artifact — rather than into the publicly-readable C source. Documented in [Andres Freund's initial disclosure](https://www.openwall.com/lists/oss-security/2024/03/29/4) and [Russ Cox's build-script forensics](https://research.swtch.com/xz-script). Caught by accident before it shipped to stable distributions. The lesson: trust in a single maintainer is itself a supply-chain risk.

The throughline across these incidents: **the source was, in most cases, fine**. The compromise was at the build step, the dependency step, or the distribution step. The defensive posture that emerged — codified in the U.S. **Executive Order 14028 on Improving the Nation's Cybersecurity** (May 2021) and the resulting **NIST SP 800-218 SSDF** — is: every artifact must be accompanied by a *provenance attestation* that says, verifiably, what it is and how it was built. The framework that gives this its operational shape is SLSA.

---

## 2. SLSA — Supply-chain Levels for Software Artifacts

SLSA (pronounced "salsa") is a framework, not a tool. It defines four levels of supply-chain integrity, each level a strict superset of the previous. The current version is v1.0, finalized in April 2023 and stable since; the spec lives at <https://slsa.dev/spec/v1.0/>.

SLSA v1.0 reorganized the levels around the *build track* — the part of the supply chain from source to binary — and acknowledged that other tracks (source, dependencies, distribution) would be added later. As of May 2026, the build track is the only formally-defined track, and it has three levels: L1, L2, L3. (The original SLSA v0.1 had a fourth level, "two-party review and reproducibility", which v1.0 marked as aspirational and removed from the formal grading. v1.0 is what every tool targets today.)

The levels:

**Build L1 — *the build is scripted and produces provenance*.** The minimum bar. To qualify: the build runs from a recorded script (a Dockerfile, a Makefile, a CI workflow file), and the build emits a provenance document that names the source repo, the source commit, the builder, and the resulting artifact. The provenance does not have to be signed. The build does not have to be isolated. A developer running `docker build` on their laptop, followed by writing down "I built `myapp:v1.0` from `git@github.com:me/myapp:abc123` at 09:31 UTC", technically satisfies L1. The point of L1 is the discipline of *writing the provenance down* rather than the integrity of the writing.

**Build L2 — *hosted build platform, signed provenance*.** The build runs on a hosted platform (GitHub Actions, GitLab CI, Cloud Build, Jenkins) that the consumer trusts. The platform signs the provenance with its own key, so the consumer can verify the provenance came from the named builder. The build inputs (source repo, source commit, dependencies) are recorded. **A developer's laptop can never reach L2** — a laptop is not a hosted platform with a trusted signing key.

**Build L3 — *hardened build platform, isolated builds*.** Beyond L2: the build platform is *hardened* — separate workers for separate builds (no cross-build contamination), the build process cannot exfiltrate the signing key, the provenance cannot be forged by the build itself. The classic threat L3 defends against is "malicious build can modify the provenance to claim to be a different build". To reach L3, the platform must be architected so that the provenance is generated by a layer the build cannot reach. Few platforms qualify out of the box; GitHub Actions reaches L3 only when used with the [SLSA GitHub Generator](https://github.com/slsa-framework/slsa-github-generator) which adds the necessary isolation.

The original L4 in v0.1 (since removed in v1.0) required *two-party review of every source change* and *reproducibility* — bit-identical rebuilds from the same source. This was acknowledged as the right aspiration but too prescriptive for a framework that wanted broad adoption. The reproducible-builds discipline continues at <https://reproducible-builds.org/> and is still the right north star.

**What a SLSA provenance document looks like.** The schema is at <https://slsa.dev/spec/v1.0/provenance>. An example (abbreviated):

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [{
    "name": "ghcr.io/myorg/myapp",
    "digest": {"sha256": "abc123..."}
  }],
  "predicateType": "https://slsa.dev/provenance/v1",
  "predicate": {
    "buildDefinition": {
      "buildType": "https://actions.github.io/buildtypes/workflow/v1",
      "externalParameters": {
        "workflow": {
          "ref": "refs/heads/main",
          "repository": "https://github.com/myorg/myapp",
          "path": ".github/workflows/release.yaml"
        }
      },
      "internalParameters": {
        "github": {
          "event_name": "push",
          "repository_id": "123456",
          "repository_owner_id": "789012"
        }
      },
      "resolvedDependencies": [
        {
          "uri": "git+https://github.com/myorg/myapp@refs/heads/main",
          "digest": {"gitCommit": "abc123..."}
        }
      ]
    },
    "runDetails": {
      "builder": {
        "id": "https://github.com/actions/runner/github-hosted"
      },
      "metadata": {
        "invocationId": "https://github.com/myorg/myapp/actions/runs/...",
        "startedOn": "2026-05-14T09:00:00Z",
        "finishedOn": "2026-05-14T09:03:21Z"
      }
    }
  }
}
```

Three pieces matter. The **subject** is the artifact this provenance describes — named by its content digest, not its tag. The **buildDefinition** describes *what* was built, including the source repo, the source commit, and the workflow file path. The **runDetails** describe *who* and *when* — the builder identity and the timestamps. The whole document is wrapped in an **in-toto Statement** ([in-toto.io](https://in-toto.io/)), which is the cross-vendor schema for "signed claim about an artifact". The Statement is then itself signed (by cosign, by slsa-github-generator, by Tekton Chains, by any compatible signer) and attached to the artifact in the registry.

The key conceptual move: **the provenance is itself an artifact, signed and verifiable, distinct from the artifact it describes**. A consumer can fetch the artifact, fetch the provenance, verify the provenance's signature, and then check that the provenance's claims match the artifact's identity (digest match, source repo match, builder match). This is the audit trail. Every regulated industry's procurement standard from 2023 onward demands it.

---

## 3. Sigstore — the project, the architecture

If SLSA is the framework, **sigstore** ([sigstore.dev](https://sigstore.dev/)) is the canonical free open-source implementation of the signing and verification primitives the framework needs. Sigstore is an OpenSSF project, started in 2021 by engineers from Google, Red Hat, and Chainguard. Its design goal was: make code signing free, free of the long-lived-key management problem, and verifiable by third parties.

Sigstore has three components, and the design choices in each are worth understanding before we touch the CLI.

**Cosign** is the client. The CLI a developer or CI pipeline uses to sign and verify artifacts (container images, blobs, attestations). Cosign is what `cosign sign` and `cosign verify` invoke. It is at <https://github.com/sigstore/cosign>.

**Fulcio** is a free **certificate authority** for code-signing identities. The novelty: instead of issuing long-lived signing certificates that the developer must guard for years, Fulcio issues **short-lived certificates (10 minutes)** based on an **OIDC identity** the developer proves at the moment of signing. The developer authenticates with Google, GitHub, Microsoft, or another OIDC provider; Fulcio receives the OIDC token, verifies it against the provider's JWKS, and issues a cert that binds the developer's OIDC identity (e.g., `alice@example.com` from Google's IDP) to a freshly-generated keypair. The cert lasts 10 minutes; the keypair is discarded immediately after signing. Fulcio is at <https://github.com/sigstore/fulcio>; the public-good instance runs at <https://fulcio.sigstore.dev/>.

**Rekor** is a free **transparency log** of every signature. Every time Fulcio issues a cert and cosign uses it to sign something, the signature event is recorded in Rekor — a Merkle-tree-backed append-only log that anyone can read. Rekor's API at <https://rekor.sigstore.dev/api/v1/log/entries> lets a verifier prove that a specific signature was issued at a specific time. Rekor is at <https://github.com/sigstore/rekor>; the public-good instance at <https://rekor.sigstore.dev/>.

The three together compose into a workflow nobody had before 2021:

1. Alice runs `cosign sign ghcr.io/alice/myapp:v1.0` from her laptop.
2. Cosign opens a browser to her OIDC provider (Google, GitHub, etc.).
3. Alice authenticates; the browser receives an OIDC token; cosign captures it.
4. Cosign generates an ephemeral keypair (in memory, will be discarded).
5. Cosign sends the OIDC token + a CSR (Certificate Signing Request) for the ephemeral public key to Fulcio.
6. Fulcio verifies the OIDC token, issues a 10-minute certificate binding Alice's identity to the ephemeral public key.
7. Cosign uses the ephemeral private key to sign the image's digest. The signature is a tiny blob.
8. Cosign uploads the signature, the certificate, and a Rekor entry pointing at both to the registry, as an OCI artifact stored next to the image (using OCI 1.1 referrers or the legacy `:sha256-abc123.sig` tag convention).
9. Cosign uploads the same data to Rekor for transparency.
10. The ephemeral private key is discarded.

The result: there is now a signature in the registry, a public record in Rekor, and Alice has no long-lived signing key to lose, leak, or rotate. A verifier later:

1. Fetches `ghcr.io/alice/myapp:v1.0`.
2. Asks the registry for the attached signature.
3. Fetches the Fulcio certificate that signed it.
4. Verifies the certificate chain back to Fulcio's well-known root.
5. Verifies the Rekor inclusion proof — the signature was recorded in Rekor at a specific time.
6. Verifies the certificate's OIDC identity matches a policy ("must be from `*@alice-example.com`" or "must be from GitHub Actions in `github.com/alice/myapp`").
7. Verifies the signature itself against the image's digest.

All seven steps run from the verifier's CLI in a single `cosign verify` command. There is no signing-key trust to extend; the trust is in Fulcio's CA (whose root is published) and Rekor's append-only log (whose root is published).

The critique you should hold: **this depends on the public sigstore infrastructure remaining trustworthy and online**. Fulcio is operated by the OpenSSF on best-effort terms; Rekor likewise. Sigstore has, in 2026, an excellent uptime record and a transparent governance model, but it is not a paid SLA. For high-stakes deployments, **organizations can run their own private Fulcio + Rekor** (cosign supports `--fulcio-url` and `--rekor-url` flags). The public-good instance is fine for the vast majority of cases; this lecture and the exercises use it.

The second critique: **keyless signing binds the signature to an OIDC identity that exists today, not to a long-lived corporate identity that persists across personnel changes**. If Alice signs an image with her Google account and leaves the company, the cert still verifies (it was valid at sign-time, and Rekor preserves it), but operationally the policy should probably say "signed by a corporate identity, not a personal one". This is why production setups usually use the GitHub Actions OIDC token of the *repository* (not the developer), or a corporate Google Workspace identity, rather than personal accounts.

---

## 4. The cosign CLI in practice

The command surface you need for this week is small.

**Install:**

```bash
brew install cosign            # macOS
# or:
go install github.com/sigstore/cosign/v2/cmd/cosign@latest
# or download the binary release from https://github.com/sigstore/cosign/releases
```

**Sign an image (keyless, public sigstore):**

```bash
cosign sign ghcr.io/alice/myapp@sha256:abc123...
```

Note the use of the **digest**, not the tag. Cosign refuses to sign by tag because tags are mutable — signing `:v1.0` today does not bind the signature to whatever `:v1.0` happens to point at tomorrow. Pinning to the digest is the only correct flow. (Cosign has a `cosign sign ghcr.io/alice/myapp:v1.0` form that resolves the tag at sign-time; it warns you about the resolution.)

**Sign an image (key-based, when keyless is not available):**

```bash
cosign generate-key-pair        # creates cosign.key (private) + cosign.pub (public)
cosign sign --key cosign.key ghcr.io/alice/myapp@sha256:abc123...
```

Key-based is the fallback when there is no OIDC provider available (air-gapped CI, classified environments). The private key is now your concern to protect, rotate, and back up; you have lost the "keyless" property in exchange for offline signing.

**Verify (keyless):**

```bash
cosign verify ghcr.io/alice/myapp@sha256:abc123... \
  --certificate-identity-regexp '^alice@example\.com$' \
  --certificate-oidc-issuer 'https://accounts.google.com'
```

The `--certificate-identity-regexp` is the policy: the cert must have been issued to this OIDC identity. The `--certificate-oidc-issuer` is the policy: that identity must have come from this issuer. Without both, you would accept a signature from anyone Fulcio has ever issued a cert to — too permissive. Cosign refuses to verify without an identity policy starting in v2.0.

**Verify (key-based):**

```bash
cosign verify --key cosign.pub ghcr.io/alice/myapp@sha256:abc123...
```

The public key replaces the identity policy. Same idea: this signature must verify against this specific key.

**Attach an attestation (e.g., SLSA provenance):**

```bash
cosign attest --predicate provenance.json \
  --type slsaprovenance \
  ghcr.io/alice/myapp@sha256:abc123...
```

The predicate is the provenance JSON. The type names the predicate schema (`slsaprovenance`, `spdxjson`, `cyclonedx`, `vuln`, custom URIs). Cosign wraps the predicate in an in-toto Statement, signs it the same way as a regular cosign signature (keyless or key-based), and attaches it to the image as an OCI artifact.

**Verify an attestation:**

```bash
cosign verify-attestation ghcr.io/alice/myapp@sha256:abc123... \
  --type slsaprovenance \
  --certificate-identity-regexp '^alice@example\.com$' \
  --certificate-oidc-issuer 'https://accounts.google.com'
```

This returns the verified attestation payload (the provenance JSON) which the verifier can then check against policy.

The mental model: **signatures attest *that* an artifact was endorsed by an identity; attestations attest *what* the identity is claiming**. A signature is "I, Alice, vouch for this artifact". An attestation is "I, the GitHub Actions builder, claim this artifact was built from this source at this commit by this workflow". The two compose: a signed attestation is "I, the builder, claim this provenance, and I am vouched for by Fulcio's CA". This is the SLSA L2 minimum, achievable with stock GitHub Actions and a one-line cosign step.

---

## 5. Rekor — what it actually is and why

The transparency log is the part of sigstore that surprises people the most. The intuition "the signature is in a log somewhere" is correct as far as it goes; the *why* is worth unpacking.

The threat model rekor defends against: **a future revelation that a cert was issued under suspicious circumstances**. Suppose, hypothetically, that an attacker compromises Fulcio for a fifteen-minute window and persuades it to issue a cert for `bob@example.com` that Bob did not authorize. The attacker uses that cert to sign a malicious image. Bob has no way to know. Six months later, the attack is discovered by other means.

Without a transparency log, the only audit trail is Fulcio's internal logs — which the attacker, having compromised Fulcio, can edit. With a transparency log, every cert issuance and every signature is recorded in an append-only Merkle-tree-backed log that *every* sigstore client checks. The compromise is detectable because the log entries exist and Bob's monitoring tools can detect "a cert was issued for bob@example.com that I did not authorize". Bob can then investigate, revoke trust in the affected window, and notify downstream consumers.

This is the same architectural pattern as **Certificate Transparency** for the public Web PKI ([certificate.transparency.dev](https://certificate.transparency.dev/)) — the system that, since 2013, has required every public CA to log every cert issuance to a public log monitored by browsers and CAs. CT caught DigiNotar's compromise and several smaller incidents that internal-audit alone would have missed. Rekor is the sigstore-shaped equivalent.

Practically, Rekor exposes a public API that any client can query. To check whether a signature exists for a given artifact:

```bash
rekor-cli search --sha sha256:abc123...
```

To fetch an entry by UUID:

```bash
rekor-cli get --uuid 24296fb24b8ad77a...
```

Cosign queries rekor automatically on verify. The `--insecure-ignore-tlog` flag exists to disable this check; it is a footgun and should only be used for air-gapped environments where rekor is unreachable.

---

## 6. The OIDC identity policy in production

A subtlety worth addressing: when you write the `--certificate-identity-regexp` for `cosign verify`, what should it be in practice?

For a personal project, signing with your own OIDC identity:

```
--certificate-identity-regexp '^alice@example\.com$'
--certificate-oidc-issuer 'https://accounts.google.com'
```

For a team project signing from GitHub Actions, the OIDC identity is the *workflow path*, not a user. The certificate's identity field looks like:

```
https://github.com/myorg/myapp/.github/workflows/release.yaml@refs/heads/main
```

So the policy is:

```
--certificate-identity-regexp '^https://github\.com/myorg/myapp/\.github/workflows/release\.yaml@refs/heads/main$'
--certificate-oidc-issuer 'https://token.actions.githubusercontent.com'
```

This policy says: "the signature must have been produced by *this specific workflow in this specific repo on this specific branch*". A malicious developer who learns the cosign command but cannot push to `main` of the production repo cannot produce a signature that satisfies this policy. This is the real-world deployment.

For multi-repo organizations, regexes typically widen one dimension at a time:

```
--certificate-identity-regexp '^https://github\.com/myorg/.+/\.github/workflows/release\.yaml@refs/heads/main$'
```

— "any repo in myorg, but only the `release.yaml` workflow, only on `main`".

The discipline: write the most-specific regex that admits your real production paths and excludes everything else. Audit it whenever the workflow paths change.

---

## 7. Tying back to today and Monday

Today's lecture and Monday's lecture share an underlying claim: **trust should be expressed as policy over identity, not as possession of a key**. Vault binds a Kubernetes service-account identity to a permission to read a secret; cosign binds an OIDC identity to a permission to vouch for an artifact. Both replace the "whoever holds this string can do this thing" model with "whoever can prove this identity at this moment can do this thing". The strings — Vault tokens, cosign signatures — exist; they are short-lived and bound to specific actions. There is no master credential.

This identity-first framing is the operational shift of the 2020s. The cluster of tools that implements it — OIDC + cosign + rekor + Vault + OPA / Kyverno — composes into what we now call **zero-trust supply chain**. We will see the cluster-side enforcement on Thursday when we write a Kyverno policy that demands cosign signatures on every production image. The whole picture comes together in the mini-project.

The questions to leave today's lecture holding:

1. For an image your team ships, what is the OIDC identity policy you would write?
2. If you were a regulator and could mandate one of SLSA L1 / L2 / L3 across a procurement program, which would you pick and why? What would the operational cost be?
3. What is in your build pipeline today that the SUNBURST attack would have exploited? What is one change you could make this week that would prevent it?

Bring answers to Thursday.

---

## References cited

- SLSA spec — <https://slsa.dev/spec/v1.0/>
- SLSA provenance schema — <https://slsa.dev/spec/v1.0/provenance>
- SLSA GitHub Generator — <https://github.com/slsa-framework/slsa-github-generator>
- in-toto Attestation Framework — <https://in-toto.io/> and <https://github.com/in-toto/attestation>
- sigstore project — <https://sigstore.dev/>
- cosign — <https://github.com/sigstore/cosign>
- Fulcio — <https://github.com/sigstore/fulcio>
- Rekor — <https://github.com/sigstore/rekor>
- Certificate Transparency — <https://certificate.transparency.dev/>
- NIST SSDF SP 800-218 — <https://csrc.nist.gov/publications/detail/sp/800-218/final>
- Executive Order 14028 — <https://www.whitehouse.gov/briefing-room/presidential-actions/2021/05/12/executive-order-on-improving-the-nations-cybersecurity/>
- SolarWinds Mandiant report — <https://www.mandiant.com/resources/blog/sunburst-additional-technical-details>
- Codecov incident — <https://about.codecov.io/security-update/>
- Kaseya CISA advisory — <https://www.cisa.gov/news-events/cybersecurity-advisories/aa21-209a>
- MOVEit Progress bulletin — <https://www.progress.com/security/moveit-transfer-and-moveit-cloud-vulnerability>
- xz-utils disclosure — <https://www.openwall.com/lists/oss-security/2024/03/29/4>
- Russ Cox xz-script forensics — <https://research.swtch.com/xz-script>
- Reproducible Builds — <https://reproducible-builds.org/>
