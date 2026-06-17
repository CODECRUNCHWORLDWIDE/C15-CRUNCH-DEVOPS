# Exercise 2 — Sealed Secrets and the External Secrets Operator

**Time:** 90 minutes (20 min reading, 55 min hands-on, 15 min write-up).
**Cost:** $0.00.
**Cluster:** The `w10` kind cluster from Exercise 1 with Vault dev still running.

---

## Goal

Install Bitnami Sealed Secrets and convert a plaintext `Secret` into a `SealedSecret` you could safely commit to Git. Then install the External Secrets Operator, configure it to read from the Vault dev instance from Exercise 1, and project a Vault secret into a Kubernetes `Secret` mounted into a consumer pod. Watch the consumer pod see the secret on boot; rotate the Vault secret; watch the consumer's `/verify` endpoint report the rotation.

After this exercise you should have:

- The Sealed Secrets controller running in `kube-system`.
- A `SealedSecret` in `default` named `api-token`, created by `kubeseal` from a plaintext `Secret`, and the corresponding `Secret` reconciled by the controller.
- The External Secrets Operator running in `external-secrets`.
- A Vault auth role `eso-myapp` bound to the `default/secret-consumer` service account.
- A `ClusterSecretStore` pointing at Vault.
- An `ExternalSecret` projecting `secret/myapp/db` into a Kubernetes `Secret` named `myapp-db`.
- A `secret-consumer` Deployment that mounts `myapp-db` and exposes `/`, `/health`, and `/verify`.
- A demonstrated rotation: change the Vault secret, wait for ESO's refreshInterval (30s), and watch `/verify` report `rotated: true`.

---

## Step 1 — Install Sealed Secrets

The simplest install path is the controller's published manifest from the GitHub releases page:

```bash
SS_VERSION=v0.27.2

kubectl apply -f \
  https://github.com/bitnami-labs/sealed-secrets/releases/download/${SS_VERSION}/controller.yaml

kubectl -n kube-system rollout status deploy/sealed-secrets-controller --timeout=120s
```

Install the `kubeseal` CLI:

```bash
brew install kubeseal                               # macOS
# or download from https://github.com/bitnami-labs/sealed-secrets/releases
kubeseal --version
```

Fetch the controller's public certificate so kubeseal can encrypt without contacting the controller every time:

```bash
kubeseal --fetch-cert > pub-cert.pem
ls -l pub-cert.pem
```

---

## Step 2 — Convert a plaintext Secret into a SealedSecret

Generate a plaintext Secret manifest (do NOT apply this; we are using it as input to `kubeseal`):

```bash
kubectl create secret generic api-token \
  --from-literal=token=actual-real-token-value-do-not-commit \
  --dry-run=client -o yaml > api-token-plain.yaml

cat api-token-plain.yaml
```

Encrypt it:

```bash
kubeseal --format yaml --cert pub-cert.pem \
  < api-token-plain.yaml \
  > api-token-sealed.yaml

cat api-token-sealed.yaml
```

Note: the `data` field is replaced by `encryptedData`, an opaque blob. The structure is otherwise normal Kubernetes YAML, safe to commit. **Delete the plaintext file**:

```bash
rm api-token-plain.yaml
```

Apply the SealedSecret:

```bash
kubectl apply -f api-token-sealed.yaml
```

Watch the controller reconcile it into a Secret:

```bash
kubectl get sealedsecret api-token
kubectl get secret api-token
kubectl get secret api-token -o jsonpath='{.data.token}' | base64 -d
echo
```

The decoded token should match the value you typed in Step 2. The controller did the decryption in-cluster; the SealedSecret on disk is opaque to anyone who does not have the controller's private key.

---

## Step 3 — Back up the Sealed Secrets controller's private key

This is the critical-and-easy-to-skip step. If the controller's private key is lost, every SealedSecret in the cluster is unreadable. Back it up:

```bash
kubectl get secret -n kube-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key \
  -o yaml > sealed-secrets-key-backup.yaml

ls -l sealed-secrets-key-backup.yaml
```

In a real cluster you would store this offline (encrypted external drive, secure password manager, printed paper copy). For this exercise, on-disk is enough. **Add the filename to `.gitignore` immediately.**

---

## Step 4 — Configure Vault's Kubernetes auth method

Vault needs to be told it can trust the cluster's API server to identify pods. The dev mode skips the TLS bits.

```bash
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'

vault auth enable kubernetes

# Get the cluster's API server address and the token-review CA.
KUBE_HOST=$(kubectl config view --raw --minify --flatten \
  -o jsonpath='{.clusters[].cluster.server}')
echo "kube host: $KUBE_HOST"

# Get the SA token Vault will use to call TokenReview.
# (The vault SA + cluster-role-binding to system:auth-delegator was created
#  by manifests-vault-dev.yaml.)
VAULT_SA_NAME=vault
VAULT_SA_NAMESPACE=vault

# Create a token for the SA (k8s 1.24+ no longer auto-creates token secrets).
TOKEN_REVIEW_JWT=$(kubectl create token $VAULT_SA_NAME \
  -n $VAULT_SA_NAMESPACE --duration=8760h)

# Get the cluster's CA cert.
KUBE_CA_CERT=$(kubectl config view --raw --minify --flatten \
  -o jsonpath='{.clusters[].cluster.certificate-authority-data}' | base64 -d)

vault write auth/kubernetes/config \
  token_reviewer_jwt="$TOKEN_REVIEW_JWT" \
  kubernetes_host="$KUBE_HOST" \
  kubernetes_ca_cert="$KUBE_CA_CERT"
```

Create a Vault policy and bind it to a role:

```bash
vault policy write myapp - <<'EOF'
path "secret/data/myapp/*" {
  capabilities = ["read"]
}
EOF

vault write auth/kubernetes/role/eso-myapp \
  bound_service_account_names=secret-consumer \
  bound_service_account_namespaces=default \
  policies=myapp \
  ttl=1h
```

The role is `eso-myapp`. It accepts the `default/secret-consumer` service-account JWT, attaches the `myapp` policy, and issues a 1-hour Vault token.

---

## Step 5 — Install the External Secrets Operator

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

helm install external-secrets external-secrets/external-secrets \
  --namespace external-secrets \
  --create-namespace \
  --version 0.10.6 \
  --set installCRDs=true

kubectl -n external-secrets rollout status deploy/external-secrets --timeout=180s
```

---

## Step 6 — Apply the ClusterSecretStore + ExternalSecret + consumer pod

Make the consumer code available as a ConfigMap (so the pod can mount it):

```bash
kubectl create configmap secret-consumer-code \
  -n default \
  --from-file=secret_consumer.py=secret_consumer.py
```

Apply the manifests:

```bash
kubectl apply -f manifests-external-secrets.yaml

kubectl -n default rollout status deploy/secret-consumer --timeout=120s
```

Verify ESO is reading from Vault:

```bash
kubectl get externalsecret myapp-db -n default
kubectl get clustersecretstore vault-backend

kubectl describe externalsecret myapp-db -n default | head -40

# The Kubernetes Secret should now exist, populated by ESO.
kubectl get secret myapp-db -n default
kubectl get secret myapp-db -n default -o jsonpath='{.data.db-password}' | base64 -d
echo
```

The decoded password should match what you wrote to Vault in Exercise 1.

---

## Step 7 — Verify the consumer pod sees the secret

Hit the consumer's `/` endpoint:

```bash
curl -s http://127.0.0.1:8080/ | jq .
```

Expected output (abbreviated):

```json
{
  "secrets_dir": "/etc/secrets",
  "boot_keys": ["db-host", "db-password", "db-username"],
  "redacted_values": {
    "db-host": "po***(40 chars)",
    "db-password": "hu***(28 chars)",
    "db-username": "we***(6 chars)"
  }
}
```

The pod saw the three keys on boot; the redaction utility prints the first 2 chars and the length without leaking the full secret.

---

## Step 8 — Rotate the Vault secret and watch ESO refresh

In one terminal, hit `/verify` repeatedly:

```bash
watch -n 5 'curl -s http://127.0.0.1:8080/verify | jq .rotated_keys'
```

In another terminal, write a new value to Vault:

```bash
vault kv put secret/myapp/db \
  username=webapp \
  password=hunter2-ROTATED-VERSION-2 \
  host=postgres.default.svc.cluster.local
```

Within ~30 seconds (the `refreshInterval` on the ExternalSecret), ESO refreshes the Kubernetes Secret. The pod's secret mount is updated atomically via a symlink swap; the next read sees the new value. The watch loop should print `["db-password"]` once the rotation lands.

**Why does the pod see the rotation without restarting?** Kubernetes mounts Secrets via projected volumes that are updated by the kubelet. The pod's filesystem snapshot is refreshed; the secret_consumer.py re-reads the file in `/verify` and sees the new value. This is the live-rotation property that distinguishes ESO from SealedSecrets.

To make a *running* application reload (e.g., to pick up a new connection string), you typically pair ESO with [Stakater Reloader](https://github.com/stakater/Reloader), which restarts pods on Secret change. Out of scope for this exercise; worth knowing about.

---

## Step 9 — Reflection

Write two paragraphs in your notes:

1. **When would you use SealedSecrets versus ExternalSecrets, in the same repo?** Pick two real secret types your team handles and assign each to one of the two tools. Defend.

2. **What is the failure mode if Vault is down?** Trace through: ESO's refresh fails; the Kubernetes Secret keeps its last-known value; the pod's mount keeps its last-known value; the application keeps running. How long can this go on? What changes when the existing Vault token expires?

---

## Cleanup

We keep the `w10` cluster running for the rest of the week. To pause and resume later:

```bash
# To stop the cluster (preserves state):
docker stop $(docker ps -q --filter "name=w10-")

# To resume:
docker start $(docker ps -aq --filter "name=w10-")

# To destroy:
# kind delete cluster --name w10
```

---

## Cost summary

```
+-------------------------------------+
|  Sealed Secrets controller  $0.00   |
|  ESO Helm chart             $0.00   |
|  Vault (from Exercise 1)    $0.00   |
|  kind cluster               $0.00   |
|                                     |
|  Total                      $0.00   |
+-------------------------------------+
```
