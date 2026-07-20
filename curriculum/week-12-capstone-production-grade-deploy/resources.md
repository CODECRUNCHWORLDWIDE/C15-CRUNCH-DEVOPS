# Week 12 — Resources

All resources here are free at the time of writing (May 2026). Where a paid product or commercial cloud service is referenced, it is identified as such and a free equivalent is named. The order is curated, not alphabetical; read top to bottom for a coherent path through the material.

This week's resource list is longer than the others by design — the capstone integrates every previous week, and the resources below are organized in roughly the same order. Treat the list as a reference rather than a reading list; you will dip into it during the build, not read it cover to cover.

---

## The capstone reference architecture — primary sources

- **Kubernetes — concepts.** <https://kubernetes.io/docs/concepts/>. The top-level concept index. By Week 12 you should know this site cold; the link is here for completeness.
- **Kubernetes — the documentation home.** <https://kubernetes.io/docs/>. Always the canonical reference for any API object, controller, or upstream feature gate. The capstone uses only stable APIs; the *Concepts* and *Tasks* sections cover all of them.
- **Cloud Native Computing Foundation — the landscape.** <https://landscape.cncf.io/>. Every component the capstone uses is on the landscape. Browse it once; the spatial layout of "which projects are in which category" is one of the more useful mental maps the discipline has produced.
- **The Twelve-Factor App.** <https://12factor.net/>. The reference for the application's configuration model (env-var driven, stateless, port-bound). Still the cleanest 4,000-word case for the discipline.

---

## ArgoCD and GitOps

- **ArgoCD — documentation home.** <https://argo-cd.readthedocs.io/en/stable/>. The canonical docs. Read the *Getting Started* and the *Operator Manual / Architectural Overview* first.
- **ArgoCD — App-of-Apps pattern.** <https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/>. The pattern used in the capstone. The "cluster bootstrapping" page documents it.
- **ArgoCD — declarative setup.** <https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/>. The reference for how to define `Application` CRDs in Git rather than in `argocd app create` invocations. The capstone uses declarative throughout.
- **ArgoCD — sync waves and hooks.** <https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/>. Critical for the bootstrap-order problem the lecture covers. Sync waves are how you tell ArgoCD to apply CRDs before the resources that depend on them.
- **ArgoCD — image updater.** <https://argocd-image-updater.readthedocs.io/en/stable/>. The optional sidecar component that watches the image registry and writes new tags into the Git repo automatically. Useful but optional; the capstone wires it as a stretch goal.
- **GitOps principles — OpenGitOps.** <https://opengitops.dev/>. The principles document — declarative, versioned, pulled, continuously reconciled. The reference for the discipline rather than for any one tool.
- **Flux — the alternative.** <https://fluxcd.io/>. The other CNCF GitOps controller. The capstone uses ArgoCD; Flux is functionally equivalent and the lessons port. Worth knowing exists.

---

## CI/CD — GitHub Actions

- **GitHub Actions — documentation home.** <https://docs.github.com/en/actions>. The canonical reference. Read the *Workflow syntax* and *Reusable workflows* pages.
- **GitHub Actions — `docker/build-push-action`.** <https://github.com/docker/build-push-action>. The standard build-and-push composite action. Supports cache from registry and SBOM attestation.
- **GitHub Actions — `docker/setup-buildx-action`.** <https://github.com/docker/setup-buildx-action>. Sets up Buildx for multi-platform builds. The capstone builds single-platform `linux/amd64` to keep CI fast.
- **GitHub Actions — `sigstore/cosign-installer`.** <https://github.com/sigstore/cosign-installer>. Installs cosign in the workflow runner. Combined with OIDC, lets the workflow sign without a stored private key.
- **GitHub Actions — `aquasecurity/trivy-action`.** <https://github.com/aquasecurity/trivy-action>. Runs Trivy in CI. Configurable to fail on critical-severity CVEs.
- **GitHub Actions — `anchore/sbom-action`.** <https://github.com/anchore/sbom-action>. Generates SBOMs via Syft. Attaches the SBOM as a release artifact.
- **GitHub OIDC for cloud providers.** <https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect>. The reference for keyless authentication from CI to AWS, GCP, Azure, and Sigstore.

---

## Cosign, Sigstore, and supply-chain controls

- **Sigstore — documentation home.** <https://docs.sigstore.dev/>. The umbrella project for cosign, fulcio (CA), and rekor (transparency log).
- **Cosign — sign and verify.** <https://docs.sigstore.dev/cosign/signing/signing_with_blobs/>. The reference for cosign's sign and verify operations. Read the *Keyless signing* page for OIDC-based signing.
- **Cosign in Kyverno — `verifyImages` rule.** <https://kyverno.io/docs/writing-policies/verify-images/sigstore/>. The reference for using Kyverno to verify signatures at admission. The capstone's admission policy is templated on this page.
- **SLSA — the framework.** <https://slsa.dev/>. Supply-chain Levels for Software Artifacts. The framework the capstone's supply-chain controls map onto. Read the *Levels* page.
- **The in-toto attestation framework.** <https://in-toto.io/>. The standard for attaching attestations to artifacts. Cosign produces in-toto attestations under the hood.

---

## Trivy, scanning, and SBOMs

- **Trivy — documentation home.** <https://trivy.dev/>. The scanner used in the capstone. Read the *Image* and *Filesystem* scanning pages and the *Configuration* page.
- **Aqua Security — Trivy GitHub repository.** <https://github.com/aquasecurity/trivy>. The source.
- **Syft — SBOM generator.** <https://github.com/anchore/syft>. The companion to Grype; produces SBOMs in SPDX and CycloneDX format. Trivy also generates SBOMs; either is acceptable.
- **CycloneDX — SBOM specification.** <https://cyclonedx.org/>. One of the two industry-standard SBOM formats. The capstone uses CycloneDX in CI.
- **SPDX — SBOM specification.** <https://spdx.dev/>. The other industry-standard SBOM format. Linux Foundation project.

---

## Vault, SOPS, and secrets

- **HashiCorp Vault — documentation home.** <https://developer.hashicorp.com/vault/docs>. The reference for the open-source product the capstone uses. The `helm/vault-helm` chart is the install path.
- **Vault — Kubernetes auth method.** <https://developer.hashicorp.com/vault/docs/auth/kubernetes>. The reference for how the application's ServiceAccount becomes a Vault identity.
- **Vault Agent injector.** <https://developer.hashicorp.com/vault/docs/platform/k8s/injector>. The sidecar pattern the capstone uses to inject secrets into the application pod.
- **External Secrets Operator.** <https://external-secrets.io/>. The alternative to the Vault Agent injector — reads from any secret store, writes to native Kubernetes Secrets. Useful when the secret store is AWS Secrets Manager or GCP Secret Manager.
- **Mozilla SOPS.** <https://github.com/getsops/sops>. The Git-side secrets tool. Encrypts named keys in YAML/JSON files using KMS, GPG, or age. The capstone uses age keys for portability.
- **age — file encryption.** <https://github.com/FiloSottile/age>. The encryption primitive SOPS uses in the capstone. Simple, modern, file-based.
- **SealedSecrets — the alternative.** <https://github.com/bitnami-labs/sealed-secrets>. The Bitnami project for Git-side secret encryption with a Kubernetes-controller decryption path. SOPS and SealedSecrets are interchangeable for the capstone's use case.

---

## Cert-manager and ingress

- **Cert-manager — documentation home.** <https://cert-manager.io/docs/>. The reference. Read the *Concepts*, the *Installation* on Helm, and the *Configuration / ACME* page.
- **Cert-manager — ACME (Let's Encrypt).** <https://cert-manager.io/docs/configuration/acme/>. The reference for the cloud path. The kind path uses a self-signed `ClusterIssuer` covered on the *Selfsigned* configuration page.
- **Let's Encrypt — documentation.** <https://letsencrypt.org/docs/>. The free ACME-protocol CA. Used by cert-manager in the cloud path.
- **ingress-nginx — documentation home.** <https://kubernetes.github.io/ingress-nginx/>. The reference. Read the *Deployment* and *User Guide / TLS* pages.
- **External-DNS.** <https://github.com/kubernetes-sigs/external-dns>. The controller that creates DNS records for Ingress objects. Optional on the capstone's local path; used on the cloud path.

---

## Observability — Prometheus, Grafana, Loki, OpenTelemetry

- **Prometheus — documentation home.** <https://prometheus.io/docs/>. The reference.
- **kube-prometheus-stack chart.** <https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack>. The Helm chart the capstone uses. The values file is the largest single configuration surface in the platform layer.
- **Grafana — documentation home.** <https://grafana.com/docs/grafana/latest/>. The reference. Read *Dashboards*, *Data sources*, and *Alerts*.
- **Grafana — provisioning.** <https://grafana.com/docs/grafana/latest/administration/provisioning/>. The reference for committing dashboards as JSON into the repo. The capstone provisions its dashboards from Git.
- **Loki — documentation home.** <https://grafana.com/docs/loki/latest/>. The reference. Read *Get started* and *LogQL*.
- **Promtail.** <https://grafana.com/docs/loki/latest/send-data/promtail/>. The log-shipper DaemonSet.
- **OpenTelemetry — documentation home.** <https://opentelemetry.io/docs/>. The reference. The capstone uses the OTel SDK for Python and the OTel Collector for export.
- **OpenTelemetry Collector — configuration.** <https://opentelemetry.io/docs/collector/configuration/>. The reference for the collector's `receivers/processors/exporters` pipeline.
- **OpenTelemetry — Kubernetes Operator.** <https://github.com/open-telemetry/opentelemetry-operator>. Optional. Manages OTel Collector lifecycle via CRDs.
- **Tempo — distributed tracing backend.** <https://grafana.com/docs/tempo/latest/>. The Grafana-Labs tracing backend. Used in the capstone as the trace store.
- **Jaeger — the alternative.** <https://www.jaegertracing.io/>. The other major open-source tracing backend. Functionally interchangeable for the capstone.

---

## OpenCost and FinOps

- **OpenCost — project home.** <https://www.opencost.io/>. The reference for the cost-engineering project from Week 11.
- **OpenCost Helm chart.** <https://github.com/opencost/opencost-helm-chart>. The chart the capstone installs.
- **FinOps Foundation — framework.** <https://www.finops.org/framework/>. The reference for the cost-discipline framework.
- **Kyverno — `verifyImages` and label policies.** <https://kyverno.io/docs/writing-policies/>. The reference for the two Kyverno policies the capstone uses — image verification and label enforcement.

---

## Terraform and infrastructure-as-code

- **Terraform — documentation home.** <https://developer.hashicorp.com/terraform/docs>. The reference.
- **OpenTofu — the open-source fork.** <https://opentofu.org/>. The IBM-supported fork after HashiCorp's BSL relicense. The capstone's Terraform is OpenTofu-compatible.
- **`tehcyx/kind` Terraform provider.** <https://registry.terraform.io/providers/tehcyx/kind/latest>. The community provider used to provision the kind cluster from Terraform. Useful for the bootstrap to be a single `terraform apply`.
- **`hashicorp/helm` Terraform provider.** <https://registry.terraform.io/providers/hashicorp/helm/latest>. The provider used to install ArgoCD as the first workload. After that ArgoCD installs everything else.
- **`hashicorp/kubernetes` Terraform provider.** <https://registry.terraform.io/providers/hashicorp/kubernetes/latest>. The provider for applying the App-of-Apps `Application` CRD directly.

---

## Docker and container internals

- **Docker — Dockerfile reference.** <https://docs.docker.com/engine/reference/builder/>. The reference. The capstone Dockerfile uses every major directive.
- **Distroless images.** <https://github.com/GoogleContainerTools/distroless>. The reference for the runtime base image. The capstone uses `gcr.io/distroless/python3-debian12:nonroot`.
- **Docker — Compose reference.** <https://docs.docker.com/compose/compose-file/>. The reference for the `compose.yaml` used in local dev.
- **OCI Image Specification.** <https://github.com/opencontainers/image-spec>. The standard the image format complies with. Worth reading once.

---

## FastAPI and the application

- **FastAPI — documentation home.** <https://fastapi.tiangolo.com/>. The reference for the application framework.
- **FastAPI — `/metrics` with Prometheus.** <https://github.com/trallnag/prometheus-fastapi-instrumentator>. The community library the capstone uses to expose metrics. Alternative: `starlette-prometheus`.
- **OpenTelemetry — instrumentation for FastAPI.** <https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html>. The auto-instrumentation library for FastAPI. Adds spans for every request handler with three lines of code.
- **PostgreSQL — documentation home.** <https://www.postgresql.org/docs/>. The reference for the database.
- **Bitnami PostgreSQL chart.** <https://github.com/bitnami/charts/tree/main/bitnami/postgresql>. The Helm chart the capstone uses for Postgres. Single-replica, PVC-backed; sufficient for the capstone.

---

## Books and long-form reading

- **Kubernetes Up & Running (O'Reilly, 3rd ed.).** Burns, Beda, Hightower, Villalba. Still the cleanest introduction; the 3rd edition (2022) covers everything through 1.24 and most of what shifted since.
- **Production Kubernetes (O'Reilly).** Vargo, Suomi, Schillinger, Belamaric, et al. Operations-focused. Read the *Stateful workloads* and *Networking* chapters if you have time.
- **The Phoenix Project.** Kim, Behr, Spafford. The novelization of DevOps. Reads in 4 to 6 hours; the cultural arguments are the same arguments that justify the capstone existing.
- **Site Reliability Engineering (Google).** <https://sre.google/sre-book/table-of-contents/>. Free, the entire book. Read the *Service Level Objectives* and *Practical Alerting from Time-Series Data* chapters before designing the capstone's SLO.
- **The DevOps Handbook (2nd ed.).** Kim, Humble, Debois, Willis. The companion to *The Phoenix Project*. The CALMS framework (Culture, Automation, Lean, Measurement, Sharing) is here.
- **Accelerate.** Forsgren, Humble, Kim. The metrics-of-elite-performance study. Cited in every executive pitch for the discipline. Worth reading once; the data is from 2014-2017 and the conclusions still hold.

---

## Talks and videos — free

- **KubeCon — the playlist.** <https://www.youtube.com/@cncf>. Every KubeCon talk is on the CNCF YouTube channel for free. Filter by year; the 2024 and 2025 talks are most relevant.
- **GitOpsCon — the playlist.** Hosted by CNCF. Find via the CNCF YouTube channel and the OpenGitOps site.
- **HashiCorp Vault — the official tutorials.** <https://developer.hashicorp.com/vault/tutorials>. Free, hands-on, video-and-text. The *Kubernetes* track covers the capstone's auth method.
- **ArgoCon.** <https://events.linuxfoundation.org/argocon-na/>. The Argo project's conference. Videos are on the CNCF channel after each event.

---

## Reference projects — read the source

- **kubernetes/example-go.** <https://github.com/kelseyhightower/kubernetes-the-hard-way>. Kelsey Hightower's "Kubernetes the Hard Way". A line-by-line bootstrap of a Kubernetes cluster from primitives. The capstone is the *easy* way; this is the hard way, and reading it is the fastest way to understand why the easy way works.
- **argoproj/argocd-example-apps.** <https://github.com/argoproj/argocd-example-apps>. The reference repository for App-of-Apps. The capstone's `gitops/` directory is patterned on this.
- **bitnami/charts.** <https://github.com/bitnami/charts>. The Bitnami catalog. The reference for Postgres, Vault, Redis, and many others. Charts are open-source and free.
- **prometheus-community/helm-charts.** <https://github.com/prometheus-community/helm-charts>. The reference for kube-prometheus-stack and the standalone Prometheus, Alertmanager, and node-exporter charts.

---

## The two questions every resource list should answer

1. **What do I read first?** Read the README of this week (you are here), then *The Twelve-Factor App* (4,000 words), then the ArgoCD *Getting Started* page (~3,000 words), then this week's three lecture notes. That is the path; allocate one evening.

2. **What do I read when I am stuck?** The Kubernetes documentation home, the documentation for the specific component that is failing, and the GitHub issues tracker for that component. The discipline of "read the docs, then read the issues, then ask a person" is the discipline of operating Kubernetes. Build the habit this week; carry it for the career.
