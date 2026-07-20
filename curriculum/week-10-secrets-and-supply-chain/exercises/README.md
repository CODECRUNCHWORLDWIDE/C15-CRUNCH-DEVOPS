# Exercises — Week 10

Four hands-on exercises. Each is self-contained but they share the `w10` kind cluster. Do them in order on Monday, Tuesday, and Wednesday; revisit on Thursday during the integration window.

| Exercise | Topic | Time | Cluster state required |
|---------:|-------|------|-----------------------|
| 01 | Install Vault in dev mode; encrypt a file with SOPS + age | ~75 min | fresh `w10` kind cluster |
| 02 | Install Sealed Secrets and External Secrets; project Vault into a pod | ~90 min | Vault running from 01 |
| 03 | Build, sign, and verify a container image with cosign | ~75 min | host-only; no cluster needed |
| 04 | Generate an SBOM with syft; scan with grype; attach the attestation | ~75 min | host-only; signed image from 03 |

Solutions, expected output, and the diagnostic questions to ask if you are stuck are in [SOLUTIONS.md](./SOLUTIONS.md).

Files in this folder:

- `kind-w10.yaml` — kind cluster config
- `manifests-vault-dev.yaml` — Vault dev-mode StatefulSet + Service
- `manifests-external-secrets.yaml` — ESO ClusterSecretStore + ExternalSecret + consumer Deployment
- `manifests-sealed-secret-example.yaml` — sample SealedSecret shape
- `manifests-kyverno-cosign.yaml` — Kyverno ClusterPolicy for cosign verification
- `vault_demo.py` — Vault client used in Exercise 1
- `secret_consumer.py` — secret-consuming pod used in Exercise 2
- `signed_app.py` — FastAPI service used as the cosign target in Exercises 3 and 4
- `sbom_check.py` — CISA-minimum-elements checker used in Exercise 4
