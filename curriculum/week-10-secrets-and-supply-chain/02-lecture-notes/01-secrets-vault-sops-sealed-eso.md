# Lecture 1 — Secrets Management: Vault, SOPS, Sealed Secrets, External Secrets

> *A secret in source control is not encrypted by the act of being committed; it is published.*

Last week we made the cluster legible — every request a span, every error a label, every latency histogram a panel. This week the question is no longer "what is the cluster doing" but "do I trust the cluster, and does the cluster trust what it runs". The first half of the answer, today, is about secrets. The second half — Tuesday and Wednesday — is about supply chain.

A **secret**, in operations terms, is a value whose disclosure changes the system's behavior. A Postgres password. An AWS access key. A TLS private key. An OAuth client secret. A JWT signing key. An API token for a paid third-party service. The category is not defined by the type — it is defined by what happens if it leaks. A 32-byte random string written to a YAML file in a Git repo is, if its value matters, a public document the moment that repo is cloned.

The naive instinct is to fix this with `kubectl create secret`. That instinct is wrong, and it is wrong in a specific, instructive way. A Kubernetes `Secret` object is **base64-encoded**, not encrypted. Base64 is a transport encoding; it makes binary data safe to put in JSON. It is not a cipher. Anyone with `get secrets` RBAC on the namespace — which by default includes every cluster admin and, in many installations, every developer — sees the plaintext after one `base64 -d`. Worse, etcd, the backing store, holds the secret on disk, in plaintext, unless the cluster operator has separately enabled etcd encryption-at-rest ([kubernetes.io/docs/tasks/administer-cluster/encrypt-data](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/)). On a typical small `kind` cluster, encryption-at-rest is not enabled. The secret is on disk in plaintext. The secret is in the API server's memory in plaintext. The secret is in `kubectl get secret -o yaml | base64 -d` reach.

This is not a flaw; it is a layering. The Kubernetes `Secret` is a container type, a way for the API server to deliver bytes to a pod and to know those bytes are "the sensitive ones" rather than the public-config bytes. The actual security layer — encryption, access control, rotation, audit — is layered on top. That layering is the subject of this lecture.

The four problems we are solving are not one problem with four names. They are four problems:

1. **At-rest encryption** — the bytes on a disk somewhere should be ciphertext, not plaintext.
2. **Access control** — only some identities should be allowed to decrypt.
3. **Rotation** — the secret should change on a schedule, ideally without redeploying every consumer.
4. **Audit** — every read of the secret should be recorded.

A single Kubernetes `Secret` solves none of the four by itself. Etcd encryption-at-rest solves (1). RBAC solves (2) at the cluster boundary but not below it. Nothing in vanilla Kubernetes solves (3) or (4). That is why we install something else. The "something else" comes in four major flavors — Vault, SOPS, Sealed Secrets, External Secrets Operator — and a serious team usually uses two or three of them at once. This lecture is about which one solves which problem and where the seams meet.

---

## 1. HashiCorp Vault — the canonical secrets store

Vault, in its open-source form, is what most teams reach for when they need all four properties at once. It is a daemon that runs on a host or in a cluster, stores secrets in a backend (file, integrated raft, or Consul), encrypts them with a master key that is itself sealed until an operator (or an auto-unseal mechanism) presents the unseal shares, and serves an HTTP API on port 8200 for clients to read and write under access policies.

Architecturally, Vault has three layers and one ceremony you must understand on Day 1.

**The storage backend** is where the encrypted blobs live. The default in dev mode is in-memory — every restart loses everything. The production backends are the **integrated raft** backend (Vault stores its own state replicated across Vault server nodes) or **Consul** (Vault stores in a separate Consul cluster). Raft is simpler and is what HashiCorp has recommended since Vault 1.4; Consul was the historical default.

**The seal** is what protects the master encryption key when Vault is at rest. On startup, Vault is **sealed** — it has the encrypted master key on disk but does not have the unseal key in memory. It cannot read its own data. To **unseal**, you present some number of **unseal key shares** — by default, three of five shares generated at initialization. This is Shamir's Secret Sharing: the operator splits the master key across five trusted parties, any three of whom can together reconstruct the key. The point is that no single person holds the cluster's full secret material. In production, the Shamir flow is usually replaced by **auto-unseal** against a cloud KMS (AWS KMS, GCP KMS, Azure Key Vault) — Vault encrypts its master key under the cloud KMS, the KMS lets only the Vault host read the encrypted key, and unseal becomes automatic on restart. For our purposes this week, dev mode unseals automatically; HA mode uses Shamir for the exercise and we type the three shares by hand.

**The auth methods** are how clients prove who they are. The token-based default — every client carries a `VAULT_TOKEN` — is the lowest-friction but the worst-hygiene option, because tokens are long-lived bearer credentials. The auth methods we care about this week are:

- **Kubernetes auth.** A pod presents its service-account JWT to Vault. Vault verifies the JWT against the cluster's API server (using a dedicated `vault` service account with `tokenreviews.authentication.k8s.io` rights). On success Vault issues the pod a short-lived Vault token bound to a Vault role. The pod uses that token to read its secrets and never sees a long-lived credential. Documented at <https://developer.hashicorp.com/vault/docs/auth/kubernetes>.
- **AppRole.** For machines outside Kubernetes. Two values: a public `role_id` (in config) and a private `secret_id` (delivered out of band, often a one-shot). The pair becomes a Vault token. Used by CI/CD runners that are not inside the cluster.
- **JWT / OIDC.** For GitHub Actions, GitLab CI, GCP service accounts, anywhere there is an OIDC provider. The runner presents its OIDC token; Vault verifies the issuer's JWKS; Vault issues a Vault token. Used by the keyless-CI pattern we will return to on Tuesday.

**The secret engines** are how secrets are stored and rendered to the client. The simplest is **K/V version 2** (`kv/`), which is a versioned key-value store: `vault kv put secret/myapp/db password=hunter2`, then `vault kv get -field=password secret/myapp/db`. Beyond K/V, the engines that matter are:

- **Database** — Vault issues short-lived database credentials. `vault read database/creds/myapp-readonly` returns a fresh Postgres username/password, valid for an hour, dropped automatically when it expires. This is the rotation story: nobody has a long-lived database password because there is no such thing.
- **PKI** — Vault is a certificate authority. Issue short-lived TLS certs from the CA, on demand. Used by service-mesh control planes (covered Week 11).
- **Transit** — encryption-as-a-service. The application sends plaintext to Vault and gets ciphertext back; Vault holds the key and the application never does. Useful when you want application-level encryption without giving the application the key.
- **AWS / GCP / Azure** — Vault issues short-lived cloud-provider credentials. The same pattern as Database but for IAM.

**Policies** are HCL documents that map a path to a capability set. The standard reference:

```hcl
path "secret/data/myapp/*" {
  capabilities = ["read", "list"]
}

path "secret/data/myapp/private/*" {
  capabilities = ["deny"]
}
```

The Vault role binds a Kubernetes service account, a policy, and a max TTL together:

```bash
vault write auth/kubernetes/role/myapp \
  bound_service_account_names=myapp \
  bound_service_account_namespaces=default \
  policies=myapp \
  ttl=1h
```

Now the pod whose service account is `default/myapp` can authenticate to Vault, get a 1-hour token, and read everything under `secret/data/myapp/`. Lose the token, get a new one in five seconds.

**The Vault Agent and the Vault Agent Injector** are the operational layer on top of all of this. The Agent is a sidecar that runs inside the pod, authenticates to Vault, renders secrets into a tmpfs volume (`/vault/secrets/`), and renews tokens on schedule. The Injector is a Kubernetes mutating-webhook controller that inserts the Agent sidecar automatically when a pod is annotated with `vault.hashicorp.com/agent-inject: "true"`. The end result: a developer adds three annotations to their Deployment, and their `Secret` becomes a file on disk that the application reads. The application code is unchanged. The Vault token is never visible. Rotation happens behind the scenes.

This is the model. Everything else in the secrets-management space is either (a) a different storage layer doing the same conceptual job (cloud KMS, Conjur, Doppler) or (b) a different delivery layer making the same store reach the application differently.

There is a license note worth raising before we move on. HashiCorp moved Vault from the Mozilla Public License 2.0 to the **Business Source License 1.1** in August 2023. The BSL is *source-available* but not OSI-certified open-source: competitors of HashiCorp/IBM cannot offer a managed Vault product, and the source converts to MPL 2.0 only after four years per release. For student / non-competitive use it remains free in the way that matters, and the binary is downloadable from <https://releases.hashicorp.com/vault/>. The fully-OSI-licensed fork is **OpenBao** at <https://openbao.org/>, governed by the Linux Foundation, with the same API surface. If you ever need a strict-open-source Vault, OpenBao is the answer. For this week, the open-source Vault binary is what every tutorial and Helm chart targets, and the rest of the lecture refers to it as "Vault" throughout.

---

## 2. Mozilla SOPS — encrypt-and-commit

Vault is the right tool when secrets *live somewhere*. SOPS is the right tool when secrets *live in Git*.

The use case: your team has a Helm values file with a Postgres password in it. You want to check that values file in. You do not want anyone with read access to the repo to learn the password. The Git-native solution is **Secrets OPerationS**, a Mozilla tool originally written to manage the credentials Firefox Sync needed to deploy.

The SOPS innovation, and the reason it became the default for GitOps-shaped teams, is **per-value encryption**. A `secrets.yaml` like this:

```yaml
db:
  host: postgres.default.svc.cluster.local
  port: 5432
  user: webapp
  password: hunter2-actual-real-secret
api:
  stripe_key: sk_live_aaaaaaaaaaaaaa
  webhook_secret: whsec_bbbbbbbb
```

becomes, after `sops -e -i secrets.yaml`:

```yaml
db:
    host: postgres.default.svc.cluster.local
    port: 5432
    user: webapp
    password: ENC[AES256_GCM,data:dGVzdA==,iv:dGVzdA==,tag:dGVzdA==,type:str]
api:
    stripe_key: ENC[AES256_GCM,data:eGVzdA==,iv:eGVzdA==,tag:eGVzdA==,type:str]
    webhook_secret: ENC[AES256_GCM,data:fGVzdA==,iv:fGVzdA==,tag:fGVzdA==,type:str]
sops:
    age:
        - recipient: age1qx... (your age public key)
          enc: -----BEGIN AGE ENCRYPTED FILE----- ...
    lastmodified: "2026-05-14T09:12:31Z"
    mac: ENC[AES256_GCM,data:...]
    version: 3.9.4
```

Two properties of this file matter. First, the *structure* is preserved: `db.host` is still readable, `db.password` is opaque. Code review still works; a reviewer can verify the values file's *shape* (correct keys, correct host, correct port) without learning the password. Second, the *metadata* — the `sops:` footer — names the keys that can decrypt this file. Anyone whose age private key is one of the recipients can run `sops -d secrets.yaml` and get the original back. Nobody else can.

The cipher used inside is AES-256-GCM with a per-file data key. That data key is then encrypted to each recipient. Recipients are one of: an **age** keypair (the modern default; we use it this week), a **PGP** keypair (the historical default; cumbersome), an AWS KMS key, a GCP KMS key, an Azure Key Vault key, or a Vault Transit key. You can have multiple recipients — say, "every developer's age key plus the CI runner's KMS key plus the operations team's PGP key" — and any one of them can decrypt independently. Adding a new recipient is `sops -r -i --add-age age1... secrets.yaml`; removing is `--rm-age`.

The **age** ([github.com/FiloSottile/age](https://github.com/FiloSottile/age)) toolchain is the third leg of this stool. age is "PGP minus everything nobody needed". Two key types: X25519 keypairs and SSH-key recipients (Ed25519 or RSA SSH keys can decrypt without a separate age key). The file format is short and specified at <https://github.com/C2SP/C2SP/blob/main/age.md>. Generate a keypair: `age-keygen -o key.txt`. The file contains the private key (line: `AGE-SECRET-KEY-1...`) and the public key as a comment. Share the public key (`age1...`); guard the private key.

The .sops.yaml file (note the leading dot, in the repo root) sets **creation rules** so `sops -e file.yaml` knows which recipients to use:

```yaml
creation_rules:
  - path_regex: secrets/dev/.*\.yaml$
    age: age1devkey...
  - path_regex: secrets/prod/.*\.yaml$
    age: age1prodkey...
```

Now `sops -e -i secrets/prod/db.yaml` automatically encrypts to the production age recipient; `sops -e -i secrets/dev/db.yaml` to the dev recipient. The repo holds both encrypted and the right humans hold the right keys.

The integration with Kubernetes is where SOPS becomes load-bearing for GitOps. Two patterns:

- **helm-secrets** (<https://github.com/jkroepke/helm-secrets>). A Helm plugin that wraps `helm install/template` and decrypts SOPS-encrypted values files at install time. The values file in Git is encrypted; the decrypted version exists in memory for the duration of `helm template` only.
- **kustomize + KSOPS** (<https://github.com/viaduct-ai/kustomize-sops>). A kustomize generator that reads SOPS-encrypted resources and produces decrypted manifests at build time. Works with Flux and Argo CD; the CD agent has the decryption key.

The trade-off vs. Vault is sharp. With SOPS, the secret travels with the manifest, is encrypted in transit and at rest in Git, and is decrypted at deploy time. There is no separate live store to query. The cost: rotation requires a Git commit. Audit is via Git log, not a live audit trail. Read access cannot be revoked retroactively — anyone who ever cloned the repo and held a recipient key has the historical secrets forever. (You can re-encrypt and rotate, but the old commits are still readable to old keyholders.) These properties are fine for static configuration. They are not fine for short-lived database credentials.

---

## 3. Bitnami Sealed Secrets — encrypted-in-Git for Kubernetes Secrets

Sealed Secrets is, in spirit, "SOPS but Kubernetes-native". Same goal: an encrypted blob safe to commit to Git. Different mechanism: the encryption is asymmetric to a key held inside the cluster, and the decryption is performed by a controller running inside the cluster at the moment the `SealedSecret` CRD is applied.

The architecture has two pieces:

1. **The Sealed Secrets controller.** A Deployment running in `kube-system` (by default). On startup, it generates an RSA-4096 keypair (or loads an existing one from a `Secret` in its own namespace). The public key is exposed; the private key never leaves the cluster. The controller watches for `SealedSecret` CRDs and produces a corresponding `Secret` CRD by decrypting with its private key.
2. **The `kubeseal` CLI.** A client-side binary. It fetches the controller's public key (via `kubeseal --fetch-cert`) and uses it to encrypt a plaintext `Secret` into a `SealedSecret`. The encrypted blob is what you commit.

The workflow:

```bash
# Make a plaintext Secret (never commit this file)
kubectl create secret generic mydb \
  --from-literal=password=hunter2 \
  --dry-run=client -o yaml > mydb-plain.yaml

# Seal it
kubeseal --format yaml < mydb-plain.yaml > mydb-sealed.yaml

# Commit mydb-sealed.yaml; delete mydb-plain.yaml
git add mydb-sealed.yaml
git commit -m "Add sealed db credential"

# Apply
kubectl apply -f mydb-sealed.yaml
```

The applied object is a `SealedSecret`, which the controller reconciles into a `Secret` named `mydb` in the same namespace. The application reads the `Secret` normally. The `Secret` is never committed; the `SealedSecret` is.

Two properties of Sealed Secrets matter and bear emphasizing:

**The encryption is scoped to a specific (namespace, name) pair by default.** A `SealedSecret` encrypted to namespace `default` with name `mydb` cannot be decrypted into any other namespace. This prevents a SealedSecret intended for `staging/api-key` from being applied into `prod/api-key` by a curious or malicious user — the controller will refuse. You can relax the scope (`--scope namespace-wide` or `--scope cluster-wide`) but the default is strict-binding, which is the right default.

**The private key never leaves the cluster — and that is both the strength and the burden.** Strength: there is no key file on a developer's laptop to lose. Burden: if the controller's Secret holding the private key is lost (e.g., you destroy the cluster), every SealedSecret ever encrypted for that cluster becomes unreadable. **Back up the controller's key.** The standard backup is:

```bash
kubectl get secret -n kube-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key \
  -o yaml > sealed-secrets-key-backup.yaml
```

Store that backup somewhere offline (or in another cluster's Vault). On a fresh cluster, re-apply the backup before installing the controller, and the controller picks up the existing keypair. The Bitnami README has the full procedure under "Bring your own certificates".

The comparison to SOPS is worth pausing on. Both encrypt-and-commit. Both produce a Git-safe blob. The differences:

- SOPS encrypts at the *field* level inside a structured file; SealedSecrets encrypts the whole Secret as one blob. A SealedSecret's keys and structure are opaque on disk; a SOPS file's structure is legible.
- SOPS supports many KMS providers; SealedSecrets is RSA + an in-cluster controller, full stop.
- SOPS works for any file; SealedSecrets works only for Kubernetes `Secret`-shaped data.
- SOPS decryption requires the decryptor to hold the key (often distributed to many developers and CI runners); SealedSecrets decryption is centralized to one controller (the developer holds only the public key).

The right pick is workflow-dependent. Teams that want one tool for many file types (Helm values, env files, scripts) tend toward SOPS. Teams that want strict centralization of the decryption key and a Kubernetes-native CRD tend toward SealedSecrets. Both are free, both are open source, both are widely deployed in production.

---

## 4. External Secrets Operator — pull from an external store

The fourth pattern says: the secret should *not* live in Git, encrypted or otherwise. It should live in a real external secrets store (Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, Bitwarden, 1Password, Doppler, GitLab CI variables, Akeyless, Conjur, ~25 others). Kubernetes is told *where to find it* and *how to authenticate*. A controller in the cluster pulls the secret on a schedule and projects it into a native `Secret` object.

This is the **External Secrets Operator** (ESO). It became the de-facto cloud-native pattern between 2021 and 2024; the project is now a CNCF Sandbox/Incubation candidate and is the answer most platform teams give when asked "how should our apps get their secrets".

The architecture, again, has two CRDs and one controller.

**The `ClusterSecretStore`** is the connection to the external store. One per store, per cluster:

```yaml
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: "http://vault.vault.svc.cluster.local:8200"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "external-secrets"
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets
```

This says: there is a Vault at this address. Authenticate to it using the Kubernetes auth method, presenting our service-account JWT, requesting the role `external-secrets`. The `external-secrets` SA exists in the `external-secrets` namespace; the Vault side has been pre-configured with a corresponding role bound to that SA.

**The `ExternalSecret`** is the request for a specific secret:

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: app-db-credentials
  namespace: default
spec:
  refreshInterval: "1h"
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: app-db
    creationPolicy: Owner
  data:
    - secretKey: password
      remoteRef:
        key: secret/data/myapp/db
        property: password
    - secretKey: username
      remoteRef:
        key: secret/data/myapp/db
        property: username
```

This says: every hour, read `secret/data/myapp/db` from the Vault store, pull the `password` and `username` fields, and write them into a Kubernetes Secret named `app-db` in `default`. The pod mounts `app-db` like any other Secret.

The properties this gives you, which SOPS and SealedSecrets do not:

- **Live rotation.** Operations rotates the secret in Vault. Within `refreshInterval` (default 1h, configurable down to seconds), the in-cluster Secret picks up the new value. The pod can be configured (via Reloader, Stakater's controller, or a similar) to restart on Secret change.
- **Single source of truth.** The secret lives in one place. Multiple environments (clusters, namespaces) read from that one place. No drift.
- **Audit at the store.** Every read is logged at the Vault audit endpoint. You see the SA, the time, the path, the resulting token.
- **Revocation.** Delete the Vault role; pods immediately lose access; the cluster's Secret becomes stale and the next refresh fails loudly.

The properties it does *not* give you, which SOPS and SealedSecrets do:

- **Offline auditability of Git.** With ESO, the secret is not in Git. The Git repo lists *where* the secret is read from; it does not encode the secret itself. Recovery from "I deleted my cluster, what was running on it" is harder.
- **Independence from the store.** ESO requires the external store to be reachable. If Vault is down, the cluster cannot refresh secrets (existing Secrets keep working until they expire).
- **One-tool simplicity.** ESO is *another* control plane to operate. The total dependency surface — ESO + Vault + (ESO's Vault role config) + (cluster's network path to Vault) — is larger than just "kubeseal + SealedSecrets".

In practice, a serious team uses **both** ESO and Sealed Secrets (or SOPS). ESO handles the secrets that should live outside Git: database passwords (rotated every 90 days), API keys for third-party services (rotated when the third party requires), TLS certs (issued from PKI and rotated daily). SealedSecrets handles the secrets that *should* live in Git: the initial bootstrap credential, the deploy-time configuration that is sensitive but does not rotate, the OAuth client secret for an integration that does not exist outside this app. The choice per-secret is "does it need to live and rotate on its own, or does it travel with the manifest". Both answers are common in the same repo.

---

## 5. The which-when matrix

Here is the cheat sheet:

| Need                                                       | Vault | SOPS | SealedSecrets | ESO  |
|------------------------------------------------------------|:-----:|:----:|:-------------:|:----:|
| Encrypt secret at rest                                     |   X   |  X   |       X       |   X  |
| Commit to Git safely                                       |       |  X   |       X       |      |
| Rotate without redeploy                                    |   X   |      |               |   X  |
| Issue short-lived dynamic credentials (DB, cloud)          |   X   |      |               |   X* |
| One source of truth across clusters                        |   X   |      |               |   X  |
| Works for non-Kubernetes consumers                         |   X   |  X   |               |   X  |
| Per-value encryption inside a structured file              |       |  X   |               |      |
| Decryption key never leaves the cluster                    |       |      |       X       |      |
| Works without any external network call                    |       |  X   |       X       |      |
| Has an audit log of every read                             |   X   |      |               |   X* |

(\* via the underlying store, not ESO itself.)

The pattern that emerges:

- **Static, low-rotation, deploy-time secrets** → SealedSecrets or SOPS. Both encrypt-in-Git. SOPS for things that are not Kubernetes Secrets (Helm values, env files); SealedSecrets for things that are.
- **Dynamic, rotating, runtime secrets** → Vault (with Agent injection or ESO).
- **Multi-cluster, single-source-of-truth secrets** → Vault + ESO.
- **Just need it to work on day one and not commit a password** → SealedSecrets. It is the lowest-friction.

A pragmatic small team that is just starting often goes: install SealedSecrets on Monday, ship for three months, and add Vault + ESO when the first secret needs to rotate. There is no rule that says you have to choose one upfront. The four tools coexist on the same cluster; we will install three of them this week.

---

## 6. The boundary cases

A few patterns that show up in real systems and that the four tools above do not directly address:

**Secrets in CI/CD.** Your build pipeline needs an API token to publish a package, a registry credential to push an image, an SSH key to push a tag. These secrets live in GitHub Secrets, GitLab CI variables, Jenkins credentials, etc. The modern best practice is **keyless CI via OIDC** — the CI runner presents an OIDC token to a service (Vault with JWT auth, AWS IAM with `sts:AssumeRoleWithWebIdentity`, GCP Workload Identity Federation), and the service issues a short-lived credential. No long-lived token is stored. We will see this again on Tuesday with cosign's keyless signing.

**Secrets in development.** Developers need to run the app on their laptops. They need *some* version of the secrets. The cheap-and-wrong answer is to send the production secrets over Slack. The right answer is a separate set of dev secrets in Vault (or a separate `.sops.yaml` recipient set), bound to dev service accounts. The cheaper-and-still-right answer is **direnv + a shared `.envrc` decrypted via SOPS**: every dev has the recipient age key, `direnv allow` decrypts on cd, the variables enter the shell, the app reads them.

**Encryption in transit.** Secrets in motion between Vault and the cluster (and between External Secrets and Vault) must be over TLS. Both `vault` and `external-secrets-operator` support TLS to the backend; the dev-mode shortcuts we use this week skip it. In production, never skip it.

**Root key management.** Every system above eventually has a root key that, if lost, is unrecoverable. For Vault: the unseal shares or the cloud KMS unseal key. For SOPS+age: the age private key(s). For SealedSecrets: the controller's RSA key. For ESO: the backend's authentication credential. **Each of these must be backed up.** The standard pattern is a printed paper copy stored in a safe (yes, paper) plus an offline-only digital copy on an air-gapped drive. This sounds paranoid; it is what every regulated industry actually does because the alternative is "your cluster is unrecoverable".

---

## 7. Looking ahead

Today we built the secrets layer. Tomorrow we turn to the *artifact* layer: we will sign container images with cosign, watch the signature record itself in rekor, and read the SLSA spec end to end. The throughline between today and tomorrow is *identity-based trust*: the Vault role binds an identity to a permission; the cosign signature binds an identity to an artifact. The vocabulary is shared. By Wednesday we will tie the artifact layer back to today by writing an admission policy: "do not deploy an image without a valid cosign signature, and do not run a pod without an ExternalSecret-projected database credential".

The questions to leave today's lecture holding:

1. For one app on your laptop, which of the four tools above would you use, and why?
2. What is your team's current root-key story for whichever store holds your prod secrets? Where is the backup?
3. Does any of your current production code do `os.environ["DB_PASSWORD"]` where the value came from a hand-edited `.env` file? What is the migration path?

Bring answers to Thursday's exercise debrief.

---

## References cited

- HashiCorp Vault — <https://developer.hashicorp.com/vault/docs>
- Vault Kubernetes auth — <https://developer.hashicorp.com/vault/docs/auth/kubernetes>
- Vault Agent Injector — <https://developer.hashicorp.com/vault/docs/platform/k8s/injector>
- OpenBao (Vault open-source fork) — <https://openbao.org/>
- Mozilla SOPS — <https://github.com/getsops/sops>
- age — <https://age-encryption.org/v1/>
- age spec — <https://github.com/C2SP/C2SP/blob/main/age.md>
- helm-secrets — <https://github.com/jkroepke/helm-secrets>
- KSOPS — <https://github.com/viaduct-ai/kustomize-sops>
- Bitnami Sealed Secrets — <https://github.com/bitnami-labs/sealed-secrets>
- External Secrets Operator — <https://external-secrets.io/>
- Kubernetes Secret docs — <https://kubernetes.io/docs/concepts/configuration/secret/>
- Kubernetes encryption-at-rest — <https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/>
