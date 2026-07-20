# Challenge 1 — Block Unsigned Images with a Kyverno Admission Policy

**Time:** 60 minutes.
**Cost:** $0.00.
**Cluster:** The `w10` kind cluster from Exercises 1 and 2.
**Prerequisites:** A signed image from Exercise 3. The Kyverno admission controller installed in the cluster.

---

## The brief

A platform team has set the rule: **every Pod in the `signed-only` namespace must carry an image whose cosign signature was issued from this team's GitHub Actions release workflow**. Pods that try to use an unsigned image — or an image signed by anyone else — are rejected at admission time.

Your job is to write the Kyverno `ClusterPolicy` that enforces this rule, install it, and verify it works in both directions: a Pod with a properly-signed image is admitted, and a Pod with an unsigned image is rejected with a clear error message.

This is the cluster-side enforcement layer that ties the signing discipline from Exercise 3 to runtime trust. Without admission enforcement, the signatures are decorative.

---

## Step 1 — Install Kyverno

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update

helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace \
  --version 3.3.x

kubectl -n kyverno rollout status deploy/kyverno-admission-controller --timeout=300s
```

Kyverno installs five Deployments: admission controller, background controller, cleanup controller, reports controller, and the policy webhook. All must reach Ready before policies can be applied.

---

## Step 2 — Apply the starter policy

The file `manifests-kyverno-cosign.yaml` in the `exercises/` folder contains the starting policy. Open it and **edit the `subject` URL** in the `attestors` block to match your real OIDC identity. The starter says:

```yaml
- keyless:
    subject: "https://github.com/EXAMPLE-OWNER/EXAMPLE-REPO/.github/workflows/release.yaml@refs/heads/main"
    issuer: "https://token.actions.githubusercontent.com"
```

If you signed from your laptop with a personal Google identity, change the subject and issuer:

```yaml
- keyless:
    subject: "alice@example.com"
    issuer: "https://accounts.google.com"
```

Apply:

```bash
kubectl apply -f ../exercises/manifests-kyverno-cosign.yaml
```

Verify the policy is loaded:

```bash
kubectl get clusterpolicy
kubectl describe clusterpolicy require-cosign-signature
```

The status should show "Ready: true".

---

## Step 3 — Test: try to deploy an UNSIGNED image (must fail)

Pick a public image that has no cosign signature attached. The official `nginx:1.27-alpine` from Docker Hub is unsigned:

```bash
kubectl run unsigned-test \
  --image=nginx:1.27-alpine \
  --restart=Never \
  -n signed-only
```

Expected output:

```
Error from server: admission webhook "mutate.kyverno.svc" denied the request:
resource Pod/signed-only/unsigned-test was blocked due to the following policies

require-cosign-signature:
  verify-images-in-signed-only-namespace: ...
    no matching signatures: image is unsigned
```

Kyverno's webhook intercepted the create call, ran cosign verification, found no signature, and rejected. The Pod was never created. Confirm:

```bash
kubectl get pod -n signed-only
# No resources found in signed-only namespace.
```

---

## Step 4 — Test: deploy your SIGNED image (must succeed)

Use the image you signed in Exercise 3. Create a Pod manifest:

```bash
cat > signed-test-pod.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: signed-test
  namespace: signed-only
spec:
  containers:
    - name: app
      image: $IMAGE_BY_DIGEST
      ports:
        - containerPort: 8080
EOF

kubectl apply -f signed-test-pod.yaml
```

Expected: the Pod is admitted. Kyverno verified the signature against the configured identity and let the request through.

```bash
kubectl get pod signed-test -n signed-only
kubectl logs signed-test -n signed-only
```

If you get an error like `no matching signatures: ...does not match required identity`, your policy's `subject` field does not match the OIDC identity that actually signed the image. Re-edit the policy and re-apply.

---

## Step 5 — Inspect the admission event

Kyverno records every admission decision as a Kubernetes Event. List them:

```bash
kubectl get events -n signed-only --sort-by='.lastTimestamp' | tail -10
```

You should see two events: one `PolicyViolation` for the rejected unsigned-nginx attempt and one `PolicyApplied` for the accepted signed-app.

For longer-term observability, Kyverno also publishes Prometheus metrics — `kyverno_admission_review_total`, `kyverno_admission_review_blocked_total`, etc. — at the kyverno-admission-controller Service. Wire these into the Week 9 Prometheus stack if you want a dashboard.

---

## Step 6 — The harder variant: require SBOM and signature

The starter policy file also includes `require-sbom-attestation`, set to `validationFailureAction: Audit` (warns but does not block). Switch it to `Enforce` and verify that Pods using an image *without* an SPDX attestation are rejected:

```bash
kubectl patch clusterpolicy require-sbom-attestation \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/validationFailureAction","value":"Enforce"}]'
```

Now an image that was signed but has no SBOM attestation will be rejected. Test by attaching an SBOM to one image but not another and running the same Pod creation.

---

## Step 7 — Reflection

Write a short note answering:

1. **What is the failure mode if the Kyverno controller is down?** Pod creation in `signed-only` blocks (because `failurePolicy: Fail` in the policy). Is this the right choice? When would you set `failurePolicy: Ignore` instead?

2. **What is the failure mode if the public sigstore infrastructure is unreachable?** Cosign verification depends on reaching Rekor; can the policy still verify? See the `--insecure-ignore-tlog` flag in cosign and Kyverno's `useCache` option. Is there an architecture you would prefer for high-stakes deployments?

3. **How would you allowlist a vendor image (e.g., a Helm chart from a third party) that is not signed by your team?** Write the addition to the ClusterPolicy that exempts a specific image namespace.

---

## Grading rubric

- An unsigned image is reliably rejected: **5 points**.
- The signed image is reliably accepted: **5 points**.
- The reflection note answers the three questions: **5 points each (15 total)**.

25/25: pass.

---

## Hints

If you are stuck:

- `kubectl logs -n kyverno deploy/kyverno-admission-controller` shows what cosign saw at verify time.
- Run the same `cosign verify` command from your laptop with the same identity policy — if it fails from your laptop, it will fail from Kyverno too. Debug at the cosign layer first.
- The starter policy uses `imageReferences` glob patterns. If your image's registry path does not match any of `ghcr.io/*/*`, `docker.io/*/*`, or `localhost:5001/*`, add yours to the list.
