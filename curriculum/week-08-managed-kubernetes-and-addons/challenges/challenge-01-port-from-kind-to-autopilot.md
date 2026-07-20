# Challenge 1 — Port from kind to GKE Autopilot

**Time:** 90 minutes.
**Cost:** $0.00 (this is a paper exercise; no cluster required).

---

## The setup

You have a Git repo with the working manifests from Exercises 1, 2, and 3 — they deploy to a kind cluster correctly. Your team has decided to move to GKE Autopilot. Your task: port the manifests so they apply cleanly to an Autopilot cluster and produce the same application behavior (an HTTPS endpoint at a public hostname, with a valid cert, deployed via ArgoCD).

You do *not* need to actually provision the Autopilot cluster. The deliverable is the modified manifests plus a written explanation.

---

## The starting manifests (from Exercises 1-3)

Assume the following manifests are in your repo:

### `manifests/ingress-nginx-values.yaml`

```yaml
# Values passed to `helm install ingress-nginx ingress-nginx/ingress-nginx -f this-file`
controller:
  hostPort:
    enabled: true
  hostNetwork: true
  kind: DaemonSet
  nodeSelector:
    ingress-ready: "true"
  tolerations:
    - key: node-role.kubernetes.io/control-plane
      operator: Equal
      effect: NoSchedule
  publishService:
    enabled: false
  service:
    type: ClusterIP
```

### `manifests/cluster-issuer.yaml`

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned
spec:
  selfSigned: {}
```

### `manifests/app.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: app
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello
  namespace: app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: hello
  template:
    metadata:
      labels:
        app: hello
    spec:
      containers:
        - name: hello
          image: nginxinc/nginx-unprivileged:1.27-alpine
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: "50m"
              memory: "64Mi"
            limits:
              memory: "128Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: hello
  namespace: app
spec:
  selector:
    app: hello
  ports:
    - port: 80
      targetPort: 8080
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: app-tls
  namespace: app
spec:
  secretName: app-tls
  issuerRef:
    kind: ClusterIssuer
    name: selfsigned
  commonName: app.localhost
  dnsNames:
    - app.localhost
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hello
  namespace: app
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

---

## Your task

Produce the Autopilot-equivalent of each file, in a separate directory (`manifests-autopilot/`), and write a `PORT-NOTES.md` explaining every change.

The constraints:

1. The application's hostname must change from `app.localhost` to `app.YOUR_DOMAIN.com` (use a placeholder).
2. The certificate must come from Let's Encrypt staging (Autopilot is reachable from the public Internet; HTTP-01 will work).
3. The Ingress controller's Service must be type `LoadBalancer` (Autopilot will provision a Google Cloud LB).
4. The Deployment's resource requests should be set to values that match the Autopilot minimum (250m CPU, 512Mi memory) so you are billed for what you request, not for the minimum-bumping behavior.
5. Add a `PodDisruptionBudget` for the Deployment (Autopilot rotates nodes; without a PDB you can briefly have zero replicas).
6. Add a `livenessProbe` to the Deployment (the kind manifest had only a readinessProbe).
7. Do NOT add any GCP-specific annotations (e.g., `cloud.google.com/...`). The manifests must remain portable to EKS and AKS with at most a `StorageClass` rename and an Ingress-controller-Service-type tweak.

---

## What to write up

Create `challenges/notes-c01.md` with the following structure:

### Section 1 — The diff summary table

A table with columns: `File | Change | Reason`. One row per change, no more than 10 rows total. Concise.

### Section 2 — The new manifests

Either inline the new manifest YAML in your write-up, or point to `manifests-autopilot/` if you have a repo.

### Section 3 — The reasoning for the more interesting changes

In one paragraph each:

1. Why did you change the ingress-nginx-values.yaml from `hostPort` to `service.type=LoadBalancer`? What does each provide on the respective cluster type?
2. Why did you change the ClusterIssuer from `selfsigned` to Let's Encrypt? What would happen if you left it as self-signed on Autopilot?
3. Why did you bump the resource requests? What is the Autopilot-specific bin-packing rule that makes "request what you need" the right default?
4. Why did you add a PodDisruptionBudget? What specific Autopilot behavior makes a PDB more important on Autopilot than on kind?

### Section 4 — The portability checklist

A list of 5-8 statements about the new manifests that confirm they remain portable. For example: "The Deployment manifest has no GCP-specific annotations." "The Ingress class is `nginx`, which works on any cluster that has the NGINX Ingress controller installed." Each statement is a property of the manifest that holds across all four target clusters (kind, GKE Autopilot, EKS, AKS).

### Section 5 — One open question

A specific question you have about how this would behave on Autopilot in practice that the dry-run does not answer.

---

## Acceptance criteria

The challenge is complete when:

- `manifests-autopilot/` contains the ported version of every file in the starting set.
- `python3 -c "import yaml,sys; list(yaml.safe_load_all(open('<each-file>')))"` passes on each new YAML file.
- Your `notes-c01.md` answers all four questions in Section 3 in your own words.
- Your portability checklist contains at least 5 distinct statements, each of which would be straightforwardly verifiable by reading the manifest.

---

## Hints (use only after attempting on your own)

- The Helm values file changes most. Strip the `hostPort`, `hostNetwork`, `kind`, `nodeSelector`, and `tolerations`. Set `controller.service.type: LoadBalancer`. The rest is default.
- The ClusterIssuer file becomes two ClusterIssuers (staging and production), and the Ingress annotation changes to `cert-manager.io/cluster-issuer: letsencrypt-staging` to drive certificate creation. The explicit `Certificate` resource becomes unnecessary because the annotation auto-creates it.
- The Deployment's resource block becomes `requests.cpu: 250m, requests.memory: 512Mi`, with `limits.memory: 512Mi` (set memory limit equal to request to avoid OOM surprises). CPU limit is typically not set on Autopilot.
- The PodDisruptionBudget is 4 lines plus the selector. `minAvailable: 1` is the most common pattern for a 2-replica Deployment.

The challenge is solvable in 90 minutes with the lecture notes open. If you find yourself reaching for Google for more than a minute on any single change, re-read Lecture 2 Sections 3 and 5.
