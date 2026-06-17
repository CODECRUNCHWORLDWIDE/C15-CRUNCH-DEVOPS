# Exercise 2 — Install cert-manager and Issue a Certificate

**Time:** 75 minutes (15 min reading, 45 min hands-on, 15 min write-up).
**Cost:** $0.00.
**Prerequisite:** Exercise 1 complete; the `w08` kind cluster is running with NGINX Ingress.

---

## Goal

Install cert-manager on the `w08` kind cluster. Create a self-signed `ClusterIssuer`. Issue a `Certificate` resource for `app.localhost`. Update the Exercise 1 Ingress to use TLS. Verify the certificate.

After this exercise you should have:

- The `cert-manager` Helm chart installed in the `cert-manager` namespace with all CRDs.
- A `ClusterIssuer` named `selfsigned` that issues self-signed certificates.
- A `Certificate` resource named `app-tls` in namespace `ex01`, with status `Ready: True`.
- The Exercise 1 Ingress updated to terminate TLS using `app-tls`.
- A `curl https://app.localhost/` that returns 200 (with `--insecure` because the cert is self-signed).

---

## Step 1 — Install cert-manager

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.15.0 \
  --set installCRDs=true
```

Notes:

- We pin to `v1.15.0`. As of May 2026, the latest cert-manager is in the `v1.16` series; `v1.15` is the previous stable line. Pinning the version means everyone in the class lands on the same software; in production you would probably track the latest minor.
- `installCRDs=true` puts the CRDs (`Certificate`, `Issuer`, `ClusterIssuer`, `CertificateRequest`, `Order`, `Challenge`) in the same Helm release as the controller. The alternative — installing CRDs separately — is the operationally safer pattern for `helm upgrade` (CRDs are not deleted by `helm uninstall`), but for a fresh install the combined path is simplest.

Wait for the rollout:

```bash
kubectl -n cert-manager rollout status deployment/cert-manager --timeout=120s
kubectl -n cert-manager rollout status deployment/cert-manager-webhook --timeout=120s
kubectl -n cert-manager rollout status deployment/cert-manager-cainjector --timeout=120s
```

Three deployments should each report `successfully rolled out`. cert-manager has three components and you should know what they are:

- `cert-manager` — the main controller. Watches `Certificate`, `Issuer`, `ClusterIssuer`. The brains.
- `cert-manager-webhook` — the admission webhook. Validates cert-manager resources before they are stored in etcd.
- `cert-manager-cainjector` — injects CA bundles into other resources (CRDs, ValidatingWebhookConfigurations) that need to trust cert-manager-issued certs. The detail you do not usually think about.

Verify the CRDs exist:

```bash
kubectl get crds | grep cert-manager
```

You should see at least: `certificaterequests.cert-manager.io`, `certificates.cert-manager.io`, `challenges.acme.cert-manager.io`, `clusterissuers.cert-manager.io`, `issuers.cert-manager.io`, `orders.acme.cert-manager.io`.

---

## Step 2 — Create a self-signed ClusterIssuer

Save as `cluster-issuer.yaml`:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned
spec:
  selfSigned: {}
```

Why self-signed on kind: Let's Encrypt cannot reach a kind cluster (your cluster is behind your laptop's NAT). The HTTP-01 challenge requires Let's Encrypt to fetch a token from a public URL pointing at your cluster; on kind, that URL is unreachable. Self-signed sidesteps the problem entirely: cert-manager generates the CA, signs the cert, and the cert is valid as a TLS cert (browsers and `curl` will warn that it is self-signed, but it works).

Apply:

```bash
kubectl apply -f cluster-issuer.yaml
kubectl get clusterissuer selfsigned -o jsonpath='{.status.conditions[0].type}={.status.conditions[0].status}{"\n"}'
```

Expected output: `Ready=True`.

If it is `False`, run `kubectl describe clusterissuer selfsigned` and read the `Conditions` section.

---

## Step 3 — Issue a Certificate explicitly

Save as `app-cert.yaml`:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: app-tls
  namespace: ex01
spec:
  secretName: app-tls
  issuerRef:
    kind: ClusterIssuer
    name: selfsigned
  commonName: app.localhost
  dnsNames:
    - app.localhost
  duration: 2160h     # 90 days
  renewBefore: 360h   # 15 days
```

Apply:

```bash
kubectl apply -f app-cert.yaml
```

Wait and verify:

```bash
kubectl -n ex01 wait certificate/app-tls --for=condition=Ready --timeout=60s
kubectl -n ex01 get certificate app-tls
kubectl -n ex01 get secret app-tls
```

You should see a `Secret` named `app-tls` of type `kubernetes.io/tls` with two keys (`tls.crt` and `tls.key`). The certificate is in `tls.crt`; the key is in `tls.key`. Both base64-encoded.

Inspect the actual certificate:

```bash
kubectl -n ex01 get secret app-tls -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -text -noout | head -20
```

You should see:

- `Issuer: O = cert-manager, CN = ...` — issued by cert-manager's auto-generated self-signed CA.
- `Subject: CN = app.localhost` — the common name we requested.
- `X509v3 Subject Alternative Name: DNS:app.localhost` — the DNS names we requested.
- `Not Before: ...` and `Not After: ...` — about 90 days apart.

That is a valid certificate. It is not trusted by your browser (because the CA is not in your trust store), but it is a real X.509 certificate.

---

## Step 4 — Update the Exercise 1 Ingress to use TLS

Save as `test-app-tls.yaml` (this replaces the Ingress from Exercise 1):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hello
  namespace: ex01
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - app.localhost
      secretName: app-tls
  rules:
    - host: app.localhost
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: hello
                port:
                  number: 80
```

The only change from Exercise 1 is the `tls:` block. Apply:

```bash
kubectl apply -f test-app-tls.yaml
```

NGINX Ingress watches this resource; within ~5 seconds it reloads its config to terminate TLS using `app-tls` Secret. Verify:

```bash
kubectl -n ex01 get ingress hello -o jsonpath='{.spec.tls}{"\n"}'
```

You should see your TLS block.

---

## Step 5 — Curl over HTTPS

```bash
# Without --insecure: certificate is self-signed; curl will warn and fail
curl https://app.localhost/

# With --insecure: trust the self-signed cert for the test
curl -v --insecure https://app.localhost/
```

Expected: `200 OK`, the same `nginxinc/nginx-unprivileged` welcome page.

In the verbose output you should see:

```
* Server certificate:
*  subject: CN=app.localhost
*  issuer: O=cert-manager; CN=...
```

That confirms TLS is being terminated by NGINX using the cert-manager-issued certificate.

---

## Step 6 — Trigger an automatic renewal (optional, ~10 minutes)

cert-manager renews automatically when the certificate is within `renewBefore` of expiry. You can force a renewal by deleting the Secret; cert-manager re-issues:

```bash
kubectl -n ex01 delete secret app-tls
kubectl -n ex01 wait certificate/app-tls --for=condition=Ready --timeout=60s
kubectl -n ex01 get secret app-tls
```

The Secret is back, with a fresh certificate. The reconciliation loop in action.

---

## Step 7 — Inspect the CertificateRequest

When cert-manager issues a certificate, it creates an intermediate `CertificateRequest` resource. List them:

```bash
kubectl -n ex01 get certificaterequest
```

There should be at least one (or two, if you did Step 6). Describe one:

```bash
kubectl -n ex01 describe certificaterequest <name>
```

The "Events" section tells the story of the issuance: request submitted → signed by issuer → certificate persisted to Secret. This is the level at which you diagnose cert-manager problems when they occur.

---

## Step 8 — Now switch to a Let's Encrypt staging ClusterIssuer (read-only)

For exposure to the Let's Encrypt path, write (do not apply) `letsencrypt-staging.yaml`:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: ops@example.com
    privateKeySecretRef:
      name: letsencrypt-staging-account
    solvers:
      - http01:
          ingress:
            ingressClassName: nginx
```

What would change on a real cluster with a real domain:

- The email is yours.
- The Ingress would have annotation `cert-manager.io/cluster-issuer: letsencrypt-staging` (not a separate Certificate resource).
- cert-manager would auto-create the Certificate, run the HTTP-01 challenge, and Let's Encrypt would issue a real (staging-untrusted, but real) cert.
- After the staging cert works end-to-end, you switch to `letsencrypt-prod` (same shape, different ACME server URL).

We do not apply this on kind because the HTTP-01 challenge cannot complete. You will use this shape on the GKE Autopilot dry-run in Exercise 4 and in homework if you provision a real cluster.

---

## Step 9 — What to write up

Create `exercises/notes-ex02.md` with:

- A one-paragraph summary: what you installed and what state the cluster is in.
- The output of `kubectl get clusterissuer` and `kubectl -n ex01 get certificate,certificaterequest,secret`.
- The first 10 lines of the decoded certificate (`openssl x509 -text -noout`).
- A reflection: what is the difference between a self-signed cert from cert-manager and a Let's Encrypt cert, from the perspective of a browser, and from the perspective of NGINX?
- One question you still have about cert-manager. (You do not need to answer it.)

---

## Troubleshooting

1. **`Error: rendered manifests contain a resource that already exists`** — leftover from a previous install. `helm uninstall cert-manager -n cert-manager; kubectl delete ns cert-manager; kubectl get crds | grep cert-manager.io | awk '{print $1}' | xargs kubectl delete crd`. Then retry.
2. **Certificate stuck `Ready: False`** — `kubectl describe certificate` and read the events. For self-signed, the most common cause is the ClusterIssuer's `Ready` condition is `False`; check that first.
3. **Secret not appearing** — cert-manager generates the Secret only after the certificate is issued. If the Certificate is `Ready: False`, the Secret will not appear. Wait or diagnose.
4. **NGINX not picking up the TLS Secret** — `kubectl -n ingress-nginx logs <pod>` to see if NGINX detected the Ingress change. The default reload interval is sub-second; if NGINX has not reloaded in 10 seconds, something is wrong.
5. **Browser does not trust the self-signed cert** — expected. Self-signed certificates are not in any trust store. `--insecure` on `curl` or "Accept Risk" in the browser is the right workaround for this exercise.

---

## What you should leave with

You have now seen the cert-manager mental model in practice: a `Certificate` resource is your *desire*; a `Secret` of type `kubernetes.io/tls` is the *state*; the `ClusterIssuer` is the *backend* that issues. cert-manager's controller is the reconciliation loop that gets from desire to state. The same shape applies whether the issuer is self-signed (this exercise), Let's Encrypt (the next exercise on a real cluster), HashiCorp Vault, AWS Private CA, or your internal corporate CA. The mechanism generalizes.

Exercise 3 installs ArgoCD on the same cluster and points it at a Git repo. After that, the mini-project assembles the full stack.
