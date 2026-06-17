# Lecture 3 — SBOMs, Vulnerability Scanning, and Two Famous Attacks

> *An SBOM is the ingredient label on the side of the box. It does not, by itself, make the food safe. It makes the food legible — and legibility is the prerequisite to every safety check that follows.*

Monday we covered secrets. Tuesday we covered signatures and the SLSA framework. Today closes the supply-chain story with two more things every production cluster needs: a **software bill of materials** for every image it runs, and a **vulnerability scan** against that bill of materials. We will then walk through two famous attacks — event-stream in 2018 and ua-parser-js in 2021 — and ask, for each, which of this week's tools would have caught them.

The argument structure of today's lecture is: **SBOM → vulnerability scan → attestation → policy → case studies → forward**. Each step builds on the previous one. By the end you will know how syft generates an SBOM, how grype turns that SBOM into a list of CVEs, how cosign attaches that list as a signed attestation, and how a Kyverno policy can refuse to deploy an image whose attestation is missing or whose scan exceeds a threshold.

---

## 1. SBOM — what it is and what it is not

A **Software Bill of Materials** is a machine-readable list of every component in a software artifact. For a container image, that means every binary, every library, every interpreted-language package, every system file with a known provenance. For a static binary, it means every linked library and every transitively-included dependency. The point is *legibility*: given an SBOM, a downstream consumer can answer "is library X version Y inside this artifact" without unpacking, reverse-engineering, or running the artifact.

The legal-procurement-floor for SBOMs is the **CISA Minimum Elements for an SBOM** ([cisa.gov/sbom](https://www.cisa.gov/sbom)), derived from the U.S. NTIA report of July 2021. The seven mandatory fields:

1. **Supplier name.** Who built and distributed the component (the package maintainer, the vendor, the project).
2. **Component name.** The canonical name of the component as used by its supplier.
3. **Version.** The supplier's version identifier (semver, date-stamped, build-numbered — whatever the supplier uses).
4. **Unique identifier.** A globally-unique ID for the component. The two common forms are **PURL** (Package URL, [github.com/package-url/purl-spec](https://github.com/package-url/purl-spec)) — e.g., `pkg:pypi/requests@2.31.0` — and **CPE** (Common Platform Enumeration, the NVD's older standard) — e.g., `cpe:2.3:a:python:requests:2.31.0:*:*:*:*:*:*:*`.
5. **Dependency relationship.** How this component relates to others ("included by", "depends on").
6. **Author of the SBOM data.** Who generated the SBOM (different from the supplier of any one component).
7. **Timestamp.** When the SBOM was generated.

Beyond the seven minimum fields, the CISA document also mandates:

- **Automation support.** The SBOM must be machine-readable in a standard format. Currently three are accepted: **SPDX** (the Linux Foundation standard, ISO/IEC 5962:2021), **CycloneDX** (the OWASP standard), and **SWID** (the ISO/IEC 19770-2 software-identification tag standard). In practice, SPDX and CycloneDX dominate; SWID is mostly used in enterprise-software-asset-management contexts.
- **Practices and processes.** The SBOM should be generated *for every release*, at the *full depth* of the dependency graph, and distributed alongside the artifact.

What an SBOM is *not*:

- It is **not** a safety claim. An SBOM that says "this image contains OpenSSL 3.0.10" does not mean OpenSSL is patched, does not mean OpenSSL is configured securely, does not mean the application uses it safely. It just means it is in there.
- It is **not** a vulnerability list. The SBOM and the vulnerability scan are separate artifacts. The SBOM names components; the scan correlates components against a vulnerability database (NVD, OSV, GHSA) and emits findings.
- It is **not** a license-compliance check. Some SBOM formats (SPDX especially) carry license metadata, but a license-clearance audit is a separate process that consumes SBOMs.
- It is **not** a signature. An SBOM is just data. It becomes trustworthy when it is signed (typically as a cosign attestation, as we saw Tuesday).

The right frame: the SBOM is the *substrate* for everything else. Without an SBOM you cannot answer "do any of my images contain the new Log4j CVE that was disclosed this morning". With an SBOM you can grep across every image's SBOM in the registry and have an answer in seconds.

---

## 2. SPDX vs CycloneDX — the two formats

Most SBOM tools (including syft) emit *both* on demand. You will encounter both in real environments. Knowing which is which matters more for parsing than for choice.

**SPDX** (Software Package Data Exchange) is the Linux Foundation's standard, originating in license-compliance work (the "SPDX license list" at <https://spdx.org/licenses/> is the canonical reference for short-form license identifiers — `MIT`, `Apache-2.0`, `GPL-3.0-or-later`, etc.). SPDX became ISO/IEC 5962:2021 — the only ISO-standardized SBOM format. Used heavily in U.S. federal procurement and in regulated industries that need an ISO citation. The current version is SPDX 2.3 (with SPDX 3.0 in draft).

A trimmed SPDX-JSON example:

```json
{
  "spdxVersion": "SPDX-2.3",
  "dataLicense": "CC0-1.0",
  "SPDXID": "SPDXRef-DOCUMENT",
  "name": "myapp-image",
  "documentNamespace": "https://example.com/myapp-image-2026-05-14",
  "creationInfo": {
    "created": "2026-05-14T09:00:00Z",
    "creators": ["Tool: syft-1.18.0"]
  },
  "packages": [
    {
      "SPDXID": "SPDXRef-Package-requests",
      "name": "requests",
      "versionInfo": "2.31.0",
      "supplier": "Person: Kenneth Reitz",
      "downloadLocation": "https://pypi.org/project/requests/2.31.0/",
      "filesAnalyzed": false,
      "licenseDeclared": "Apache-2.0",
      "externalRefs": [
        {
          "referenceCategory": "PACKAGE-MANAGER",
          "referenceType": "purl",
          "referenceLocator": "pkg:pypi/requests@2.31.0"
        }
      ]
    }
  ],
  "relationships": [
    {
      "spdxElementId": "SPDXRef-DOCUMENT",
      "relatedSpdxElement": "SPDXRef-Package-requests",
      "relationshipType": "DESCRIBES"
    }
  ]
}
```

The SPDX vocabulary is **packages**, **files**, **relationships**, **license expressions**. The "DESCRIBES" relationship in the example says the document describes this package; "DEPENDS_ON" relationships connect packages to their dependencies.

**CycloneDX** is the OWASP standard, originating in security-tooling work. CycloneDX was designed from the start with vulnerability correlation in mind; the schema includes first-class support for **vulnerabilities** (CVE references), **services** (the network endpoints a component exposes), and **compositions** (statements about the completeness of the SBOM). Used heavily in security-tooling pipelines. The current version is CycloneDX 1.6.

A trimmed CycloneDX-JSON example:

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.6",
  "serialNumber": "urn:uuid:3e671687-395b-41f5-a30f-a58921a69b79",
  "version": 1,
  "metadata": {
    "timestamp": "2026-05-14T09:00:00Z",
    "tools": [{"name": "syft", "version": "1.18.0"}],
    "component": {
      "type": "container",
      "name": "myapp-image",
      "version": "v1.0.0"
    }
  },
  "components": [
    {
      "type": "library",
      "name": "requests",
      "version": "2.31.0",
      "purl": "pkg:pypi/requests@2.31.0",
      "licenses": [{"license": {"id": "Apache-2.0"}}],
      "bom-ref": "pkg:pypi/requests@2.31.0"
    }
  ],
  "dependencies": [
    {
      "ref": "pkg:pypi/requests@2.31.0",
      "dependsOn": ["pkg:pypi/charset-normalizer@3.3.2", "pkg:pypi/idna@3.6"]
    }
  ]
}
```

The CycloneDX vocabulary is **components**, **services**, **dependencies**, **vulnerabilities**, **compositions**. The JSON is slightly flatter and easier to parse than SPDX's. The PURL field is first-class.

**Which to use:** if your downstream consumers are U.S. federal procurement officers, SPDX (because of ISO 5962). If they are application-security teams using DefectDojo, OWASP Dependency-Track, or a CycloneDX-native vulnerability platform, CycloneDX. If you do not know, emit both — syft makes it free.

---

## 3. syft — generating SBOMs

**syft** is Anchore's open-source SBOM generator. It is at <https://github.com/anchore/syft>. License Apache 2.0. Distributed as a single Go binary.

Install:

```bash
brew install syft           # macOS
# or:
curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh \
  | sh -s -- -b /usr/local/bin
```

syft scans a target — a container image (by reference or local), a directory, a tar archive, a Singularity image, a few others — and emits an SBOM in one of many formats.

Typical commands:

```bash
# Scan a pulled image, emit syft-native JSON
syft myapp:v1.0 -o syft-json > sbom.syft.json

# Scan, emit SPDX-JSON
syft myapp:v1.0 -o spdx-json > sbom.spdx.json

# Scan, emit CycloneDX-JSON
syft myapp:v1.0 -o cyclonedx-json > sbom.cdx.json

# Scan a directory
syft ./my-project -o spdx-json > sbom.spdx.json

# Scan a container without pulling (registry credentials assumed)
syft registry:ghcr.io/myorg/myapp:v1.0 -o spdx-json
```

Behind the scenes, syft walks the target and runs **catalogers** — small modules that know how to recognize one type of artifact:

- The **alpm** cataloger reads `/var/lib/pacman/local/` for Arch packages.
- The **apk** cataloger reads `/lib/apk/db/installed` for Alpine packages.
- The **deb** cataloger reads `/var/lib/dpkg/status` for Debian/Ubuntu packages.
- The **rpm** cataloger reads the RPM database for Red Hat / Fedora / SUSE packages.
- The **python** cataloger reads `*.dist-info` directories and `*.egg-info` for Python packages.
- The **javascript** cataloger reads `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml` for Node packages.
- The **go-mod** cataloger reads Go binary metadata (Go embeds module info into the binary at build time) and `go.mod` files in source.
- The **java-archive** cataloger reads `META-INF/MANIFEST.MF` and `pom.properties` inside `.jar`, `.war`, `.ear` files.
- Plus catalogers for Rust (`Cargo.toml`), Ruby (`Gemfile.lock`), .NET (`*.deps.json`), Swift (`Package.resolved`), Elixir (`mix.lock`), Erlang (`rebar.lock`), PHP (`composer.lock`), Dart (`pubspec.lock`), Cocoapods (`Podfile.lock`), and a handful of others.

The cataloger list is at <https://github.com/anchore/syft/tree/main/syft/pkg/cataloger>. New language ecosystems are added on a regular cadence; if you have an exotic one, check the list before assuming syft cannot handle it.

The output for a real container — say, the official `nginx:1.27-alpine` image — is typically 300-500 packages. Most of them are Alpine `apk` packages from `apk add` lines in the Dockerfile; the rest are language packages from the application layer. The SBOM is several hundred kilobytes of JSON. Compressed, ~20-40 KB. This is the right ballpark to expect.

---

## 4. grype — scanning the SBOM

**grype** is Anchore's open-source vulnerability scanner. It is at <https://github.com/anchore/grype>. License Apache 2.0. Same distribution model as syft.

Install:

```bash
brew install grype
# or:
curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh \
  | sh -s -- -b /usr/local/bin
```

grype can scan an image *directly* (running syft internally and then matching) or it can scan an *existing SBOM* you generated earlier. The two-step flow — `syft` once, `grype` against the SBOM — is the canonical pipeline pattern because the SBOM becomes the persistent record and the scan can be re-run against new vulnerability data without re-scanning the image.

Commands:

```bash
# Scan an image directly
grype myapp:v1.0

# Scan an SBOM
grype sbom:./sbom.spdx.json

# Fail the build if any high-or-critical findings exist
grype myapp:v1.0 --fail-on high

# Output JSON for downstream tooling
grype myapp:v1.0 -o json > scan.json

# Output the OWASP DefectDojo-ingest format
grype myapp:v1.0 -o cyclonedx-json > scan.cdx.json
```

grype's vulnerability data sources are:

- **NVD** — the National Vulnerability Database from NIST. The historical primary source.
- **OSV** — the Open Source Vulnerabilities database from Google ([osv.dev](https://osv.dev/)). Curated, language-aware, often more accurate than NVD for application packages.
- **GHSA** — the GitHub Security Advisory database ([github.com/advisories](https://github.com/advisories)). Curated by GitHub's security team; the source of CVE identifiers for many open-source projects.
- **Per-distro feeds** — Alpine, Debian, Ubuntu, Red Hat, SUSE, Amazon Linux all publish their own vulnerability data (the upstream CVE plus the distribution's patch status). grype consumes each distro's feed.
- **Anchore Vulnerability Match Manifest** — Anchore's enriched matching data, free under Apache 2.0.

The output is a list of findings, one per (package, vulnerability) pair:

```
NAME       INSTALLED  FIXED-IN     TYPE  VULNERABILITY     SEVERITY
openssl    3.0.10-r3  3.0.13-r0    apk   CVE-2023-5363     High
zlib       1.2.13-r0  (none)       apk   CVE-2023-45853    Critical
requests   2.28.0     2.31.0       python CVE-2023-32681   Medium
```

Each finding has: the affected package (name, version), the version it is fixed in (or `(none)` if no fix is yet known), the package type (`apk`, `deb`, `python`, `go`, etc.), the CVE identifier, and the severity (`Negligible`, `Low`, `Medium`, `High`, `Critical`, `Unknown`).

Interpreting the output is its own discipline. A high finding in a library your application does not actually call is *not the same* as a high finding in a library that handles user input on the request path. grype cannot know which is which; the security team and the developers, reading the findings together, can. The serious teams maintain a **vulnerability exception list** — `.grype.yaml` — that suppresses specific CVE/package pairs with a written justification:

```yaml
ignore:
  - vulnerability: CVE-2023-1234
    package:
      name: example-lib
      version: 1.0.0
    fix-state: not-fixed
    # We do not use the affected codepath; tracked in JIRA-456
```

The exception list is itself reviewed at a regular cadence. CVEs that *should* be fixed eventually have their exceptions removed. The discipline scales because the exception count, ideally, declines over time as fixes ship.

---

## 5. Attaching SBOMs and scan results as attestations

The cosign attestation flow from Tuesday composes directly with syft and grype:

```bash
# Generate SBOM
syft ghcr.io/alice/myapp:v1.0 -o spdx-json > sbom.spdx.json

# Sign it as an attestation attached to the image
cosign attest --predicate sbom.spdx.json \
  --type spdxjson \
  ghcr.io/alice/myapp@sha256:abc123...

# Scan the SBOM
grype sbom:./sbom.spdx.json -o cyclonedx-json > scan.cdx.json

# Attach the scan result too
cosign attest --predicate scan.cdx.json \
  --type vuln \
  ghcr.io/alice/myapp@sha256:abc123...
```

Now the image has three things attached: a cosign signature, an SBOM attestation (SPDX type), and a vulnerability-scan attestation (vuln type). A consumer's policy can demand all three:

```bash
cosign verify ghcr.io/alice/myapp@sha256:abc123... \
  --certificate-identity-regexp '^https://github\.com/alice/myapp/.+' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com'

cosign verify-attestation ghcr.io/alice/myapp@sha256:abc123... \
  --type spdxjson \
  --certificate-identity-regexp '^https://github\.com/alice/myapp/.+' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com'

cosign verify-attestation ghcr.io/alice/myapp@sha256:abc123... \
  --type vuln \
  --certificate-identity-regexp '^https://github\.com/alice/myapp/.+' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com'
```

The verifier can then *parse the attestation payload* and run a downstream policy: "the vuln attestation must have zero High-or-Critical findings", "the SBOM must contain a record for `requests >= 2.31.0`", etc. Kyverno can do this in-cluster at admission time; we will write that policy in Challenge 1.

The architectural property: **the image, the SBOM, the scan, and the signatures all live together in the registry, all bound to the same image digest, all independently verifiable**. The registry becomes the source of truth. The cluster fetches the image and its attached metadata in one transaction.

---

## 6. Case study 1 — event-stream, November 2018

event-stream was a popular npm package, ~2 million weekly downloads, providing utility functions for working with Node.js streams. It was maintained for years by Dominic Tarr, an open-source author who wrote many small useful libraries. By 2018, Dominic had moved on to other projects and was no longer actively maintaining the package — but it was widely depended-on and the issue tracker continued to receive reports.

In September 2018, a stranger ("right9ctrl") opened a GitHub issue asking to take over maintenance. Dominic agreed and transferred publish rights. Three months later, in November 2018, right9ctrl published `event-stream@3.3.6` — a minor version bump that, alongside legitimate changes, added a dependency on a new package called `flatmap-stream`. `flatmap-stream@0.1.1` was clean. `flatmap-stream@0.1.2`, published the same day, contained malicious code.

The malicious payload was clever in two ways. First, it was **encrypted with a key derived from a specific downstream package's name** (`copay`, a popular Bitcoin wallet). If the malicious code ran in a process whose `package.json` named `copay`, it decrypted and executed; otherwise it was silent. This kept the package undetected on millions of unrelated installs. Second, the payload itself was **bitcoin-wallet-exfiltration code** that captured private keys from running copay instances and uploaded them to an attacker-controlled server.

The attack was discovered ten weeks after publication, in late November 2018, by a developer who noticed a suspicious dependency tree. The issue at <https://github.com/dominictarr/event-stream/issues/116> documents the discovery and the maintainer's reflection. Estimated value stolen: hard to pin down; estimates range from "tens of thousands" to "low millions" of USD.

**What would have caught this?**

- **Pinning by hash, not version range.** If `copay`'s consumers had pinned `event-stream` to a specific *content hash* (npm shrinkwrap, lockfile-with-integrity, or now `package-lock.json`'s `integrity` field), the new version would not have been auto-installed during a `npm install` run.
- **SBOM diffing.** If `copay` had generated an SBOM on every build and compared it to the previous build's SBOM, the new `flatmap-stream` dependency would have appeared and prompted review.
- **Maintainer-handoff red flags.** A formal policy of "if a maintainer changes, re-audit the package before bumping". This is more cultural than technical, but the supply-chain-security tooling can surface the signal — e.g., npm's `npm audit signatures` will warn when a package's publisher key changes.
- **Signed publishes.** If npm had required all publishes to be signed by a long-lived publisher identity (and consumers had verified that signature), the new maintainer would have appeared as a different signer and triggered review. npm now supports this via sigstore-keyless publishing ([docs.npmjs.com/generating-provenance-statements](https://docs.npmjs.com/generating-provenance-statements)); it was not available in 2018.

The lesson the industry took: **dependency review must be an ongoing process, not a one-time act**. The dependency you trusted six months ago is not the dependency you have today.

---

## 7. Case study 2 — ua-parser-js, October 2021

ua-parser-js was another popular npm package, ~6 million weekly downloads, providing user-agent-string parsing. Maintained for years by Faisal Salman.

On October 22, 2021, three new versions were published over a four-hour window: 0.7.29, 0.8.0, and 1.0.0. All three contained a postinstall script that:

1. Detected the host OS (Windows, macOS, Linux).
2. Downloaded an OS-appropriate binary from an attacker-controlled domain.
3. Executed the binary, which installed:
   - A cryptominer (Monero, via `xmrig`).
   - A credential stealer (targeting Chrome saved passwords, file-system tokens, the host's environment variables).

The packages were live on npm for ~4 hours before Faisal noticed (he received an unfamiliar password-reset email from npm) and immediately revoked. The disclosure issue at <https://github.com/faisalman/ua-parser-js/issues/536> documents the timeline. CISA's advisory at <https://www.cisa.gov/news-events/alerts/2021/10/22/malware-discovered-popular-npm-package-ua-parser-js> followed within a day.

The attack vector was **maintainer account compromise**, not a maintainer handoff. Faisal's npm account credentials were apparently stolen via phishing or credential reuse; the attacker logged in as the maintainer and published. The downstream blast radius — every project that ran `npm install` during the four-hour window — was significant; CISA's advisory listed several U.S. critical-infrastructure organizations as affected.

**What would have caught this?**

- **MFA on package-publishing accounts.** npm now mandates 2FA on high-impact packages ([docs.npmjs.com/configuring-two-factor-authentication](https://docs.npmjs.com/configuring-two-factor-authentication)); in 2021, 2FA was optional. This is the single biggest defensive control.
- **Pinning + integrity checks**, same as event-stream.
- **Provenance signatures.** If the package were published with a sigstore-keyless provenance attestation tied to the maintainer's GitHub Actions workflow, an attacker who stole the npm credential alone would not have been able to forge the provenance — they would also need to compromise the GitHub workflow.
- **Behavioral monitoring at install time.** A postinstall script that downloads and executes a binary is *itself* an anti-pattern. Tools like `socket.dev` and `snyk.io` flag this behavior in real time. A hardened CI policy might refuse to run install scripts at all (`npm install --ignore-scripts`).
- **SBOM diffing**, again. The new versions of ua-parser-js had a different SBOM (the postinstall artifact added files); a build that compared SBOM diffs across version bumps would have surfaced the change.

The lesson the industry took: **publish-time identity must be strong**. MFA, hardware tokens, OIDC-bound CI publishing. The legacy model of "username and password to publish" is a credential type that does not survive modern attack costs.

---

## 8. The defensive stack — putting it together

If you wired together every tool from this week into a single pipeline, here is the shape:

```
   Developer commits to Git
            |
            v
   GitHub Actions / GitLab CI (hosted, isolated, SLSA L2+)
            |
            +---> Build image
            +---> Run syft to generate SBOM
            +---> Run grype against SBOM, fail-on-high
            +---> Push image to registry
            +---> cosign sign --keyless (Fulcio + Rekor)
            +---> cosign attest --type spdxjson sbom.json
            +---> cosign attest --type vuln scan.json
            +---> cosign attest --type slsaprovenance provenance.json
            |
            v
   Registry (image + signature + 3 attestations)
            |
            v
   Kubernetes cluster admission webhook (Kyverno)
            |
            +---> Verify cosign signature (must be from prod-workflow OIDC)
            +---> Verify SBOM attestation present
            +---> Verify vuln attestation has zero High-Critical
            +---> Verify slsaprovenance attestation matches expected builder
            |
            +---> If any check fails -> reject pod creation
            |
            v
   Pod runs
            |
            +---> Reads secrets from Vault via External Secrets
            +---> Vault auth via Kubernetes service-account JWT
            +---> Secrets rotated by Vault, ESO picks up changes
            |
            v
   Service observable (Week 9 stack)
   Service authenticated (Week 11 mesh)
   Service production-ready (Week 12 checklist)
```

This is roughly the architecture that the U.S. federal procurement floor (EO 14028 + NIST SSDF) describes. It is roughly the architecture that the CNCF best-practices documents at <https://github.com/cncf/tag-security> describe. It is, in 2026, the table-stakes posture for production Kubernetes.

The good news: every component above is open source and free. The bad news: there is no shortcut to standing it up; the discipline is in the integration. This week's exercises and mini-project are the integration.

---

## 9. Forward — what Week 11 builds on this

Next week we turn to the network: service mesh, mTLS, network policies, the "zero-trust" pattern that says no pod implicitly trusts any other pod. The throughline is the same identity-based-trust framing we have been developing all week. The mesh's certificate authority is itself a secrets-management system; the mesh's mTLS is an artifact-level analogue of cosign's signature — "I, the issuer of this cert, vouch that this pod's identity is `frontend.shop.svc.cluster.local`".

You will use Week 10's tooling in Week 11 indirectly: the mesh's root CA can live in Vault; the mesh's identity tokens can be SLSA-style attestations bound to image provenance. The two weeks compose into the production-trust story.

The questions to leave today's lecture holding:

1. For one image you ship today, run `syft` on it. How many packages does it find? Are you surprised?
2. Run `grype` against the SBOM. How many findings? How many would you actually act on?
3. Pick one of the two case studies and write down, in one paragraph, the policy change that would have caught it. What would the policy cost in developer friction?

Bring answers to Thursday.

---

## References cited

- CISA Minimum Elements for an SBOM — <https://www.cisa.gov/sbom>
- NTIA Minimum Elements report (PDF) — linked from CISA above
- SPDX specification — <https://spdx.dev/specifications/>
- SPDX license list — <https://spdx.org/licenses/>
- CycloneDX specification — <https://cyclonedx.org/specification/overview/>
- PURL spec — <https://github.com/package-url/purl-spec>
- syft — <https://github.com/anchore/syft>
- grype — <https://github.com/anchore/grype>
- OSV database — <https://osv.dev/>
- GitHub Security Advisories — <https://github.com/advisories>
- NVD — <https://nvd.nist.gov/>
- event-stream disclosure — <https://github.com/dominictarr/event-stream/issues/116>
- Snyk event-stream post-mortem — <https://snyk.io/blog/a-post-mortem-of-the-malicious-event-stream-backdoor/>
- ua-parser-js disclosure — <https://github.com/faisalman/ua-parser-js/issues/536>
- ua-parser-js CISA advisory — <https://www.cisa.gov/news-events/alerts/2021/10/22/malware-discovered-popular-npm-package-ua-parser-js>
- npm provenance — <https://docs.npmjs.com/generating-provenance-statements>
- npm 2FA — <https://docs.npmjs.com/configuring-two-factor-authentication>
- socket.dev — <https://socket.dev/>
- snyk.io — <https://snyk.io/>
- CNCF TAG Security — <https://github.com/cncf/tag-security>
- Executive Order 14028 — <https://www.whitehouse.gov/briefing-room/presidential-actions/2021/05/12/executive-order-on-improving-the-nations-cybersecurity/>
- NIST SP 800-218 SSDF — <https://csrc.nist.gov/publications/detail/sp/800-218/final>
