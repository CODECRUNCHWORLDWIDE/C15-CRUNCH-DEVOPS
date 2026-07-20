# Exercise 1 — Vault in Dev Mode + SOPS with age

**Time:** 75 minutes (15 min reading, 45 min hands-on, 15 min write-up).
**Cost:** $0.00.
**Cluster:** A fresh `w10` kind cluster, created in Step 1 below.

---

## Goal

Stand up HashiCorp Vault in dev mode on a `kind` cluster, write a secret to it from the command line, read it back from a Python client (`vault_demo.py`), and separately encrypt a YAML file with Mozilla SOPS using an age keypair.

After this exercise you should have:

- A `w10` kind cluster running with the manifests from `kind-w10.yaml`.
- Vault in dev mode in the `vault` namespace, reachable on `http://127.0.0.1:8200` via the NodePort forwarded by kind.
- A Vault K/V v2 entry at `secret/myapp/db` containing username, password, and host.
- The same data successfully read back by `python3 vault_demo.py`.
- An age keypair (`age-key.txt`) and a SOPS-encrypted file (`secrets.enc.yaml`) on your laptop.
- A short journal note answering the two questions at the end.

---

## Step 1 — Create the kind cluster

```bash
kind create cluster --config kind-w10.yaml
kubectl cluster-info --context kind-w10
kubectl get nodes
```

Expected: three nodes, one control-plane, two workers, all `Ready` within ~60 seconds. The cluster forwards container port 30200 to host port 8200 — that is the path we will use to reach Vault from the host.

---

## Step 2 — Deploy Vault in dev mode

```bash
kubectl apply -f manifests-vault-dev.yaml
kubectl wait --for=condition=Ready pod -l app=vault -n vault --timeout=120s
```

Verify Vault is reachable:

```bash
curl -s http://127.0.0.1:8200/v1/sys/health | jq .
```

Expected output (abbreviated):

```json
{
  "initialized": true,
  "sealed": false,
  "standby": false,
  "version": "1.18.1"
}
```

`sealed: false` is the dev-mode property; production Vault starts sealed and requires unseal shares. The dev-mode root token is hardcoded to `root` (set by `VAULT_DEV_ROOT_TOKEN_ID` in the StatefulSet manifest). **Never use this configuration outside of an exercise.**

---

## Step 3 — Write and read a secret with the Vault CLI

If you do not have the `vault` CLI installed:

```bash
brew install vault         # macOS
# or download from https://releases.hashicorp.com/vault/
```

Configure the environment and write a secret:

```bash
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'

vault status

vault kv put secret/myapp/db \
  username=webapp \
  password=hunter2-not-a-real-password \
  host=postgres.default.svc.cluster.local

vault kv get secret/myapp/db
```

Expected: the `kv put` returns a creation timestamp; the `kv get` prints all three fields.

---

## Step 4 — Read the secret from Python

The `vault_demo.py` file in this folder is the Python client. It supports both token-auth (used here) and Kubernetes auth (used in Exercise 2).

Install the client library and run the demo:

```bash
pip install hvac==2.3.0
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'
export VAULT_AUTH_MODE=token

python3 vault_demo.py
```

Expected log output:

```
INFO vault token-auth ok: addr=http://127.0.0.1:8200
INFO vault kv write ok: path=myapp/db keys=['username', 'password', 'host']
INFO vault kv read ok: path=myapp/db keys=['username', 'password', 'host']
INFO read-back: {'username': 'webapp', 'password': 'hunter2-not-a-real-password', 'host': 'postgres.default.svc.cluster.local'}
```

If you see `vault authentication failed`, your `VAULT_TOKEN` is wrong or the dev pod has not finished starting; re-check Step 2.

---

## Step 5 — Install age and create a keypair

age is the modern encryption tool we will use as SOPS's KMS. Install:

```bash
brew install age                              # macOS
# or:
go install filippo.io/age/cmd/...@latest      # any platform with Go
```

Verify and generate a keypair:

```bash
age-keygen --version

age-keygen -o age-key.txt
chmod 600 age-key.txt
cat age-key.txt
```

The file contains both the private key (the `AGE-SECRET-KEY-1...` line) and the public key (commented `# public key: age1...`). **Guard the private key.** In a real workflow this file lives in a password manager or in a dedicated key store; for this exercise, on-disk is fine.

Export the public key for convenience:

```bash
export AGE_PUBLIC_KEY=$(grep '# public key:' age-key.txt | awk '{print $4}')
echo "public: $AGE_PUBLIC_KEY"
```

---

## Step 6 — Install SOPS and encrypt a file

Install:

```bash
brew install sops                             # macOS
# or download from https://github.com/getsops/sops/releases
```

Create a plaintext secrets file:

```bash
cat > secrets.yaml <<'EOF'
db:
  host: postgres.default.svc.cluster.local
  port: 5432
  user: webapp
  password: hunter2-actual-real-secret
api:
  stripe_key: sk_live_aaaaaaaaaaaaaa
  webhook_secret: whsec_bbbbbbbb
EOF
```

Set up the .sops.yaml so SOPS knows which age recipient to use:

```bash
cat > .sops.yaml <<EOF
creation_rules:
  - path_regex: secrets.*\.ya?ml$
    age: $AGE_PUBLIC_KEY
EOF
```

Encrypt the file in place:

```bash
export SOPS_AGE_KEY_FILE=$(pwd)/age-key.txt
sops -e secrets.yaml > secrets.enc.yaml
```

Inspect the encrypted file. The values are opaque; the structure is legible:

```bash
cat secrets.enc.yaml
```

You should see:

```yaml
db:
    host: postgres.default.svc.cluster.local
    port: 5432
    user: webapp
    password: ENC[AES256_GCM,data:...,iv:...,tag:...,type:str]
api:
    stripe_key: ENC[AES256_GCM,data:...,iv:...,tag:...,type:str]
    webhook_secret: ENC[AES256_GCM,data:...,iv:...,tag:...,type:str]
sops:
    age:
        - recipient: age1...
          enc: |
            -----BEGIN AGE ENCRYPTED FILE-----
            ...
            -----END AGE ENCRYPTED FILE-----
    lastmodified: "..."
    mac: ENC[AES256_GCM,data:...]
    version: 3.9.4
```

Decrypt and verify:

```bash
sops -d secrets.enc.yaml
```

You should see the original plaintext. Now **delete the plaintext file** (you would never commit it in a real workflow):

```bash
rm secrets.yaml
```

Commit `secrets.enc.yaml` and `.sops.yaml` to a Git repo if you want — both are safe to push. **Never commit `age-key.txt`.** Add it to `.gitignore`.

---

## Step 7 — Try the "wrong key" failure mode

To experience the access-control side of SOPS, generate a *second* age key and try to decrypt with it:

```bash
age-keygen -o age-key-2.txt

export SOPS_AGE_KEY_FILE=$(pwd)/age-key-2.txt
sops -d secrets.enc.yaml
```

Expected output:

```
Failed to get the data key required to decrypt the SOPS file.

Group 0: FAILED
  age1...: FAILED
    - | no identity matched any of the 1 recipients
```

This is what an unauthorized reader sees. The file's structure is on disk; its values are unreachable without a recipient key. Switch the env var back to the original key file and the decrypt works.

---

## Step 8 — Reflection

Write two paragraphs in your notes:

1. **Which tool would you use, and why?** You now have two ways to keep a Postgres password out of source control: write it to Vault and read it at runtime (Exercise 1), or encrypt it with SOPS and commit the ciphertext (Exercise 6 of this exercise's SOPS work). For an app you ship today, pick one. Defend the choice in three sentences.

2. **What happens if the age key is lost?** Sketch the recovery procedure. Compare it to the Vault root-key-loss procedure. Which is recoverable and which is not? Why?

---

## Cleanup

We keep the `w10` cluster running for Exercise 2. The Vault dev instance and the age files stay where they are.

```bash
# Do NOT delete the cluster yet.
# When you finish Exercise 2, run:
#   kind delete cluster --name w10
```

---

## Cost summary

```
+-------------------------------------+
|  Vault container image      $0.00   |
|  kind cluster (in Docker)   $0.00   |
|  age + SOPS binaries        $0.00   |
|                                     |
|  Total                      $0.00   |
+-------------------------------------+
```
