# Lecture 3 — The Add-On Stack: Ingress, Certs, DNS, ArgoCD

> *A fresh cluster, managed or self-managed, can run pods and route to them by ClusterIP. It cannot terminate TLS, register DNS, route external traffic by hostname, or reconcile manifests from Git. Those four jobs are the add-on stack — and every production Kubernetes cluster you will ever touch has them installed.*

You created a cluster. The control plane is healthy. `kubectl get nodes` returns nodes. You can apply a Deployment and a Service and see pods come up. None of this is useful to your users yet, because:

- They cannot reach your pods. The `ClusterIP` Service is internal-only.
- If they could reach them, they would do it over HTTP, not HTTPS. There is no certificate.
- They would have to know your pods' IPs, not a hostname. There is no DNS.
- Every deploy is a `kubectl apply` you remember to do. There is no GitOps.

This lecture is about the four open-source add-ons that solve those four problems, the order to install them, and why we pick the open-source version of each over the cloud-provider's bundled equivalent. By Wednesday afternoon you will have installed each of these on a `kind` cluster (Exercises 1 through 3); by Sunday you will have used all of them in the mini-project. The add-on stack is small, opinionated, portable, and free.

---

## 1. The four problems

Before we name the four tools, let us be specific about what each one solves.

### Problem 1 — External traffic by hostname (Ingress)

A `Service` of type `ClusterIP` is internal to the cluster. A `Service` of type `LoadBalancer` asks the cloud to provision an external IP, which works on GKE / EKS / AKS / DOKS but not on `kind` (without MetalLB) and gives you one IP per Service, which gets expensive fast.

What you actually want is: one IP for the cluster (provisioned once, $0.025/hour on GCP, similar on AWS and Azure), and *that* IP routes by *Host header* and *path* to the right Service inside the cluster. So `https://app.example.com/` goes to the web Service, `https://api.example.com/` goes to the API Service, and a single external load balancer fronts both.

That is what an **Ingress controller** does. The `Ingress` resource is the desired routing; the Ingress controller is the data-plane pod that reads `Ingress` resources and configures itself accordingly. NGINX Ingress Controller is one such pod; the GKE Gateway controller is another; the AWS Load Balancer Controller is another. They speak the same API.

### Problem 2 — TLS certificates without keys you manage by hand (cert-manager)

You have an Ingress. You want users to reach it over HTTPS, not HTTP. So you need a TLS certificate. The certificate must:

- Be issued by a Certificate Authority your users' browsers trust.
- Be installed in the right Secret in the right namespace.
- Be renewed automatically before it expires.
- Be revoked and reissued if the key leaks.

The wrong answer is: you go to Let's Encrypt by hand, you put the result in a Secret, you set a calendar reminder to renew in 80 days. The right answer is: a controller in the cluster watches a `Certificate` resource you write, asks Let's Encrypt (or your internal CA) for the certificate, stores the result in a Secret, watches the expiration, renews before expiry. That controller is **cert-manager**.

### Problem 3 — DNS records that follow your cluster (external-dns)

You have an Ingress and a TLS certificate. Your Ingress controller has an external IP (or a cloud-provider-assigned hostname). You need DNS records to point your application's hostnames at that IP.

You could do this by hand in your DNS provider's console. The wrong answer. The right answer is: a controller in the cluster watches `Ingress` and `Service` resources, reads the hostname annotations, and writes the appropriate `A` / `CNAME` records to your DNS provider (Cloudflare, Route 53, Google Cloud DNS). That controller is **external-dns**.

This add-on is the only one of the four that requires you to own a domain. On `kind` (no public DNS), you can skip it and use `/etc/hosts` or the cluster's internal DNS. The mini-project this week works without external-dns; we cover it in homework.

### Problem 4 — Deployments reconciled from Git (ArgoCD)

You have an Ingress, a certificate, DNS. To deploy your application, you run `kubectl apply -f` on a YAML file. The YAML file lives somewhere — your laptop, a CI pipeline, a Slack message. There is no audit trail. There is no rollback story. Two engineers running `kubectl apply` at the same time can race.

The right answer is: the cluster reconciles itself toward a Git repo. Every change goes through Git (pull request, review, merge). A controller in the cluster watches the repo and applies whatever is there. That controller is **ArgoCD** (or Flux; both are correct).

ArgoCD is what you used in Week 6 as a black box. This week we use it deliberately, on the cluster you opened up in Week 7, deploying to the cluster you stood up this week. The full GitOps loop, end to end.

---

## 2. NGINX Ingress Controller — install, configure, use

NGINX Ingress Controller is the open-source ingress controller maintained by the Kubernetes project itself (`kubernetes/ingress-nginx`). It is the most-installed ingress controller in the ecosystem; it is what `kind`'s ingress recipe installs; it is what 80% of production clusters reach for. It runs as a Deployment (or a DaemonSet, your pick) of NGINX pods that watch `Ingress` resources and reload their NGINX config accordingly.

### 2.1 Why open-source NGINX over the GKE Gateway / AWS LB Controller

The cloud-provider-bundled ingresses are excellent at what they do. GKE's bundled Gateway controller provisions Google Cloud Load Balancers and integrates with Google IAM, Cloud Armor, and Cloud CDN. The AWS Load Balancer Controller does the equivalent with ALBs. The Azure Application Gateway Ingress Controller does it with App Gateway.

We pick NGINX anyway, for three reasons:

1. **Portability.** NGINX Ingress runs on every Kubernetes cluster — managed, self-managed, kind, bare metal. Your manifests do not need to change when you move clusters.
2. **Cost predictability.** A single external IP for the cluster vs. a Google Cloud LB per Ingress (or an ALB per Ingress on AWS). On a cluster with 10 Ingresses, the cost difference is real.
3. **Feature breadth.** NGINX Ingress has every routing feature you will ever need plus most you will not. The cloud-bundled controllers are more limited.

The argument against NGINX is: you are now operating an NGINX deployment. The reply is: cert-manager renews the certificates, the Ingress controller maintainers handle the NGINX updates, the operational tax is small. The argument that ALB / GCLB are "more managed" is true in a narrow sense; NGINX Ingress on a managed cluster is, in practice, also managed (you `helm upgrade` it twice a year).

### 2.2 Install with Helm

```bash
# Add the chart repo and update
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update

# Install in a dedicated namespace
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=LoadBalancer
```

On GKE / EKS / AKS, `--set controller.service.type=LoadBalancer` causes the cloud to provision an external IP. On `kind`, this would not work; the kind recipe instead sets `--set controller.hostPort.enabled=true` and uses `extraPortMappings` to forward ports 80/443 from the host to the kind node (Exercise 1 walks through this).

### 2.3 The Ingress resource

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  namespace: app
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-staging
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - app.example.com
      secretName: app-tls
  rules:
    - host: app.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: app
                port:
                  number: 80
```

Field-by-field:

- `apiVersion: networking.k8s.io/v1` — stable since Kubernetes 1.19. There is no longer a `networking.k8s.io/v1beta1`; do not use it.
- `ingressClassName: nginx` — pick the NGINX Ingress controller specifically. A cluster may have several Ingress controllers (e.g., NGINX for the public path and Contour for an internal path); the class name disambiguates.
- `cert-manager.io/cluster-issuer: letsencrypt-staging` — the annotation cert-manager watches. When this Ingress is created, cert-manager auto-creates a `Certificate` resource, asks the named `ClusterIssuer` for a certificate, and stores the result in the Secret named `app-tls`. The Ingress then uses that Secret for TLS.
- `tls.hosts` and `tls.secretName` — the certificate covers these hosts, and the Secret named here will hold the certificate.
- `rules.host` and `rules.http.paths` — the routing. Host header `app.example.com` plus path prefix `/` routes to Service `app` in namespace `app` on port 80.

This same YAML works on `kind`, on GKE, on EKS, on AKS, on bare metal with MetalLB. Portability is concrete.

### 2.4 The Gateway API alternative (sidebar)

The Kubernetes project's strategic replacement for Ingress is the Gateway API. It went GA (`v1`) in Kubernetes 1.29 (late 2023). It separates the concerns of "the cluster has a gateway" (the `Gateway` resource, owned by the platform team) from "this app routes through it" (the `HTTPRoute` resource, owned by the application team).

The equivalent of the Ingress above, in Gateway:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: app-gateway
  namespace: gateway-system
spec:
  gatewayClassName: nginx
  listeners:
    - name: https
      protocol: HTTPS
      port: 443
      tls:
        mode: Terminate
        certificateRefs:
          - name: app-tls
      allowedRoutes:
        namespaces:
          from: All
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: app-route
  namespace: app
spec:
  parentRefs:
    - name: app-gateway
      namespace: gateway-system
  hostnames:
    - app.example.com
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: app
          port: 80
```

The Gateway model is cleaner — multi-team, multi-route, multi-listener — and the long-term direction of the project. We use Ingress this week for two reasons: (a) Ingress is what cert-manager and external-dns most cleanly integrate with as of May 2026; (b) NGINX Ingress's adoption is still ~5x Gateway's. Expect to encounter both; expect Gateway to grow.

---

## 3. cert-manager — install, ClusterIssuer, Certificate

cert-manager is the Kubernetes-native certificate operator. It is a Jetstack project, donated to CNCF, now graduated. It runs as a small Deployment that watches `Certificate`, `Issuer`, `ClusterIssuer`, and `CertificateRequest` resources, and it talks to Certificate Authorities (Let's Encrypt over ACME, internal CAs, Vault, AWS PCA, Google CAS) to issue certificates.

### 3.1 Install

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.15.0 \
  --set installCRDs=true
```

`--set installCRDs=true` installs the CRDs (`Certificate`, `Issuer`, etc.) at the same time as the Helm release. The alternative — installing the CRDs separately — is the "Helm upgrade safety" pattern recommended by the cert-manager team for some workflows; for a new install, the combined path is simplest.

### 3.2 The Let's Encrypt ClusterIssuer

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
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ops@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-account
    solvers:
      - http01:
          ingress:
            ingressClassName: nginx
```

Two ClusterIssuers, one pointed at Let's Encrypt staging (lower rate limits, certificates not browser-trusted — fine for testing) and one pointed at production (rate-limited per domain, certificates browser-trusted). The standard practice is: test with staging until the issuance is reliable, then switch the annotation on the Ingress to `letsencrypt-prod`.

The `http01` solver works by: when cert-manager wants a certificate for `app.example.com`, Let's Encrypt asks it to prove ownership by serving a specific token at `http://app.example.com/.well-known/acme-challenge/<token>`. cert-manager temporarily injects an Ingress rule that routes that path to a small solver pod, Let's Encrypt fetches the token, cert-manager removes the rule, the certificate is issued. End-to-end: about 30 seconds.

There is also `dns01` for cases where HTTP is not reachable (private clusters, wildcard certs). It requires the DNS provider to be one cert-manager has a plugin for (Cloudflare, Route 53, Cloud DNS) and the cert-manager pod to have credentials for that provider.

### 3.3 The self-signed ClusterIssuer (for kind)

On `kind`, Let's Encrypt cannot reach you (your cluster is behind your laptop's NAT). The right answer is a self-signed ClusterIssuer:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned
spec:
  selfSigned: {}
```

Certificates issued by this issuer are not trusted by browsers, but they are valid certificates for `kubectl`, for `curl --insecure`, and for everything the mini-project does. Exercise 2 walks through the kind path.

### 3.4 The Certificate resource (when not using the Ingress annotation)

The Ingress annotation `cert-manager.io/cluster-issuer: <name>` auto-creates a Certificate. When you want explicit control — different lifetime, different DNS names, different secret name — write the Certificate directly:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: app-cert
  namespace: app
spec:
  secretName: app-tls
  issuerRef:
    kind: ClusterIssuer
    name: letsencrypt-prod
  commonName: app.example.com
  dnsNames:
    - app.example.com
    - www.app.example.com
  duration: 2160h    # 90 days
  renewBefore: 360h  # renew 15 days before expiry
```

`duration` defaults to 90 days (the Let's Encrypt default); `renewBefore` defaults to one-third of the duration. Both are tunable.

---

## 4. external-dns — install, annotations, the binding

external-dns is the Kubernetes-SIG project that syncs Kubernetes hostnames to your DNS provider. Without it, you write Ingress with `host: app.example.com` and you also go to your DNS provider and manually create an `A` record pointing `app.example.com` at your Ingress's external IP. With external-dns, the second step is automatic.

### 4.1 Install (Cloudflare example)

```bash
helm repo add external-dns https://kubernetes-sigs.github.io/external-dns
helm repo update

helm install external-dns external-dns/external-dns \
  --namespace external-dns \
  --create-namespace \
  --set provider=cloudflare \
  --set cloudflare.apiToken=$CLOUDFLARE_API_TOKEN \
  --set domainFilters[0]=example.com \
  --set policy=sync \
  --set sources[0]=ingress \
  --set sources[1]=service \
  --set txtOwnerId=my-cluster
```

Flags worth noting:

- `provider=cloudflare` — which DNS provider's API to use. external-dns supports about 40 providers (AWS Route 53, Google Cloud DNS, Cloudflare, DigitalOcean, etc.). The full list is at <https://github.com/kubernetes-sigs/external-dns#status-of-providers>.
- `cloudflare.apiToken` — a Cloudflare API token with `Zone.DNS:Edit` permission on `example.com`. The recommended pattern in production is to provide this via a Kubernetes Secret rather than as a Helm value.
- `domainFilters` — which DNS zones external-dns is allowed to manage. Without this, external-dns will try to manage records for any hostname it sees on any Ingress.
- `policy=sync` — full sync (create, update, delete). The other options are `upsert-only` (no deletes; safer for shared zones) and `create-only` (no updates either).
- `sources=ingress,service` — which Kubernetes resources to watch. We watch both, so a `Service` of type `LoadBalancer` with a hostname annotation also gets DNS records.
- `txtOwnerId` — an identifier external-dns writes into a TXT record next to every A record it manages. Lets you tell "this record was made by *this* external-dns instance" — important if you have multiple clusters managing the same zone.

### 4.2 The annotation that drives it

On an Ingress:

```yaml
metadata:
  annotations:
    external-dns.alpha.kubernetes.io/hostname: app.example.com
```

Or on a `Service` of type `LoadBalancer`:

```yaml
metadata:
  annotations:
    external-dns.alpha.kubernetes.io/hostname: api.example.com
```

When external-dns sees one of these, it creates the corresponding A record pointing at the resource's external IP (or external hostname, for AWS NLB / ALB which emit a CNAME-able name).

### 4.3 The kind-equivalent path

`kind` has no public DNS and no external IP. external-dns has nothing to do. The mini-project this week does not depend on external-dns; the hostname `app.localhost` resolves to `127.0.0.1` on most operating systems, which is exactly where the kind cluster's port-mapped Ingress lives.

In homework, you can experiment with running external-dns against a Cloudflare zone you own. Free tier on Cloudflare; about $0 if you already own the domain. We do not require it.

---

## 5. metrics-server — small, essential, often forgotten

metrics-server is the cluster-wide CPU and memory metrics aggregator. It is *not* Prometheus; it is a smaller, simpler service that provides the `metrics.k8s.io` API. It is the dependency for:

- `kubectl top nodes`
- `kubectl top pods`
- The Horizontal Pod Autoscaler (HPA) using CPU or memory metrics

GKE and AKS have it installed by default. EKS does not (you install it). `kind` does not.

### 5.1 Install

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

On `kind` and on clusters where the kubelet's serving certs are self-signed, you need one extra flag on the metrics-server Deployment: `--kubelet-insecure-tls`. Exercise 2 covers this; the canonical components.yaml does not include the flag.

After install, `kubectl top nodes` works within about 30 seconds. The HPA can use CPU/memory metrics.

---

## 6. ArgoCD — install, login, the Application

ArgoCD is the CNCF-graduated GitOps controller. You wrote about it in Week 6 from the outside; this week you install it on your own cluster (or kind), point it at a Git repo, and watch it reconcile.

### 6.1 Install

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

This is the "install via the project's static manifests" path. A Helm chart equivalent exists (`argo/argo-cd`) and is preferred for production because it supports values-file customization; for a first install, the static manifest is simplest.

ArgoCD installs a half-dozen Deployments (server, repo-server, application-controller, dex, redis, notifications-controller, applicationset-controller). They take about 2 minutes to all become Ready.

### 6.2 First login

The admin password is auto-generated on first start and stored in a Secret:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
```

Port-forward the UI:

```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443
```

Open `https://localhost:8080`, log in as `admin` with the password above. The first thing you do is change the password (`argocd account update-password`) or, better, delete the admin account entirely and configure SSO. For a learning cluster, keep the admin account and just change the password.

### 6.3 The Application resource

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: hello-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/my-org/my-app-manifests.git
    targetRevision: main
    path: manifests/hello
  destination:
    server: https://kubernetes.default.svc
    namespace: hello
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

Field-by-field:

- `source.repoURL` — the Git repo ArgoCD watches.
- `source.targetRevision` — which branch / tag / commit SHA to sync. `main` is common; pinning to a specific SHA is more deterministic.
- `source.path` — the subdirectory in the repo where the manifests live.
- `destination.server` — which cluster. `https://kubernetes.default.svc` is the in-cluster API server (this cluster).
- `destination.namespace` — which namespace to sync into.
- `syncPolicy.automated.prune: true` — if a manifest is deleted from Git, ArgoCD deletes the resource from the cluster. Without `prune`, ArgoCD only creates and updates; deletes are manual.
- `syncPolicy.automated.selfHeal: true` — if someone `kubectl edit`s a resource ArgoCD owns, ArgoCD reverts it on the next sync. The strict GitOps posture.
- `syncOptions: CreateNamespace=true` — if the destination namespace does not exist, create it.

This is the resource you write most often when using ArgoCD. The whole pattern in seven sentences:

1. You commit YAML to Git.
2. ArgoCD's application-controller has a watch on Git (every 3 minutes by default, or on webhook).
3. It detects a difference between Git and the cluster.
4. It applies the difference to the cluster (`kubectl apply`-equivalent, via the Kubernetes API).
5. The cluster's controllers do their normal reconciliation.
6. ArgoCD's UI shows the application as `Synced` and `Healthy`.
7. If something drifts (someone edits a resource by hand), `selfHeal` reverts it; if a resource is deleted from Git, `prune` removes it from the cluster.

### 6.4 Sync waves

ArgoCD lets you order resources via the `argocd.argoproj.io/sync-wave: "N"` annotation. Resources with lower N apply first. Useful when one resource needs another to exist first — for instance, a CRD must exist before a Custom Resource of that kind can be applied.

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-1"   # apply early
```

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "1"    # apply later
```

The mini-project this week uses sync waves to ensure cert-manager's CRDs land before the `Certificate` resource that depends on them.

### 6.5 ArgoCD vs Flux (the choice you do not have to make once)

Both are CNCF-graduated GitOps controllers. Both watch Git and reconcile clusters. They differ in shape:

| | ArgoCD | Flux |
|---|---|---|
| UI | Full-featured web UI | None (CLI / dashboards by third parties) |
| App definition | `Application` CRD | `Kustomization` + `GitRepository` + `HelmRelease` CRDs |
| Multi-cluster | Single ArgoCD manages many clusters | One Flux per cluster |
| Helm support | Yes, with limitations | Native, deeper |
| Sync UX | Click-to-sync in UI; auto-sync | Auto-sync by design; no manual click |

Both are correct. Teams pick ArgoCD for the UI and the single-pane-of-glass view across clusters; teams pick Flux for the cleaner CLI-only posture and the Helm-native model. For this week we use ArgoCD because Week 6 already touched it; the patterns translate to Flux in an afternoon.

---

## 7. The order to install them

This is operationally important.

1. **NGINX Ingress first.** No external traffic flows without it. On kind, this is the cluster-bootstrap step (Exercise 1).
2. **cert-manager second.** Once Ingress is up, you can issue HTTP-01 certs. Without Ingress, the HTTP-01 solver cannot work.
3. **metrics-server somewhere along the way.** Not in the dependency chain, but you want it before the HPA exercises in Week 9.
4. **external-dns when you have a domain.** Skip on kind.
5. **ArgoCD last** — once you have a working cluster, install ArgoCD and point it at a Git repo. From then on, *everything else* goes through Git.

The mini-project this week installs items 1, 2, 3, and 5. external-dns is a homework problem.

---

## 8. The portability claim, verified

The whole point of the open-source-first add-on stack is portability. Here is the verification table — what changes when you move the mini-project's manifests from `kind` to GKE Autopilot to EKS to AKS:

| Resource | kind | GKE Autopilot | EKS | AKS |
|---|---|---|---|---|
| `Deployment` | unchanged | unchanged | unchanged | unchanged |
| `Service` (type `ClusterIP`) | unchanged | unchanged | unchanged | unchanged |
| `Ingress` (NGINX) | unchanged | unchanged | unchanged | unchanged |
| `Certificate` (cert-manager) | unchanged | unchanged | unchanged | unchanged |
| `ClusterIssuer` (self-signed) | use this | use Let's Encrypt | use Let's Encrypt | use Let's Encrypt |
| `ClusterIssuer` (Let's Encrypt) | does not work (NAT) | works | works | works |
| `Service` of NGINX Ingress | `hostPort` | `LoadBalancer` | `LoadBalancer` | `LoadBalancer` |
| `StorageClass` (for PVCs) | `standard` | `standard-rwo` (GCE PD) | `gp3` (EBS) | `managed-csi` (Azure Disk) |
| ServiceAccount IAM | none | Workload Identity | IRSA | AAD Workload Identity |
| ArgoCD `Application` | unchanged | unchanged | unchanged | unchanged |

Of the eleven rows, eight are identical across all four clusters. Three differ: the Ingress controller's Service type (`hostPort` on kind, `LoadBalancer` on cloud), the ClusterIssuer (self-signed on kind, Let's Encrypt on cloud), and the StorageClass name (the only place you have to redeclare per cluster). The pod-to-cloud IAM binding is fundamentally provider-specific but the *shape* (a KSA annotation pointing to a provider identity) is the same.

This is what "portable open-source add-on stack" delivers. Three lines of cluster-specific config, eight lines of completely portable workload spec. The same Git repo can drive both your kind cluster and your Autopilot cluster — which is what the stretch goal at the end of the README hints at.

---

## 9. What we do not install this week

The cluster-add-on ecosystem is much bigger than four tools. We install the four most-important; we will install more in later weeks. For reference, here is the canonical "what you eventually install" list:

- **Prometheus + Grafana + Alertmanager** — observability. Week 12.
- **OpenTelemetry Collector** — traces and metrics export. Week 12.
- **Loki** (or equivalent) — log aggregation. Week 12.
- **Falco** — runtime security monitoring. Week 11.
- **OPA Gatekeeper** or **Kyverno** — policy enforcement. Week 11.
- **Velero** — cluster backup. Week 13.
- **Sealed Secrets** (or **External Secrets Operator**) — secrets management for GitOps. Week 13.
- **Karpenter** (EKS) / **GKE Node Auto-Provisioning** — smarter node autoscalers. Mentioned, not installed.

The four this week — Ingress, certs, DNS, GitOps — are the four every cluster needs from day one. The others come as the cluster matures.

---

## 10. The mental model you should leave with

Three things from this lecture:

1. **The add-on stack is a finite list of well-known tools.** NGINX Ingress, cert-manager, external-dns, metrics-server, ArgoCD. Every production Kubernetes cluster has 4 of these 5 (external-dns is optional if your DNS lives elsewhere). Install them once, understand them once, and they work the same on every cluster.
2. **Open-source first.** Each of the four has a cloud-bundled alternative. The open-source path keeps your manifests portable and your dependency on the cloud provider small. The exceptions are deliberate (the cloud's managed DNS, the cloud's managed database, the cloud's certificate-of-record for compliance), not accidental.
3. **The kind cluster is a viable stand-in for everything we have discussed.** You can install Ingress, certs (self-signed), and ArgoCD on a kind cluster on your laptop and complete the entire mini-project for $0. The cloud-side material is for understanding; the practice runs locally. The portability claim is verified by the mini-project, not asserted in a slide deck.

The exercises this week walk through each install step by step. The mini-project assembles all four into a working end-to-end deploy. By Sunday you will have a small app deployed via ArgoCD, behind an NGINX Ingress, with a cert-manager-issued certificate, on a kind cluster, with the same manifests that would run on GKE Autopilot.

---

*Previous: [Lecture 2 — GKE Autopilot, Node Pools, and Workload Identity](./02-gke-autopilot-node-pools-and-workload-identity.md).*
