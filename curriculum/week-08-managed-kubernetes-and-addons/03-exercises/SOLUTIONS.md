# Exercises — Solutions and Expected Output

Worked solutions for all four exercises. Read this only after attempting the exercise yourself; the value is in struggling with the diagnostic questions and getting unstuck, not in copying.

---

## Exercise 1 — Stand Up kind with NGINX Ingress

### Step 1 expected output

The exact version strings vary; what matters is that each command runs:

```
$ kind version
kind v0.24.0 go1.22.4 darwin/arm64

$ kubectl version --client
Client Version: v1.31.0
Kustomize Version: v5.4.2

$ helm version --short
v3.14.4+gabcde

$ docker info | head -1
Client: Docker Engine - Community
```

### Step 3 expected output

`kind create cluster` output ends with:

```
Creating cluster "w08" ...
 ✓ Ensuring node image (kindest/node:v1.31.0) 🖼
 ✓ Preparing nodes 📦
 ✓ Writing configuration 📜
 ✓ Starting control-plane 🕹️
 ✓ Installing CNI 🔌
 ✓ Installing StorageClass 💾
Set kubectl context to "kind-w08"
```

(Emojis above are from kind's CLI output and are not part of our voice.)

`kubectl get nodes`:

```
NAME                STATUS   ROLES           AGE   VERSION
w08-control-plane   Ready    control-plane   45s   v1.31.0
```

### Step 4 expected output

After `helm install`:

```
NAME: ingress-nginx
LAST DEPLOYED: ...
NAMESPACE: ingress-nginx
STATUS: deployed
```

After `kubectl rollout status`:

```
daemon set "ingress-nginx-controller" successfully rolled out
```

`kubectl -n ingress-nginx get pods`:

```
NAME                            READY   STATUS    RESTARTS   AGE
ingress-nginx-controller-abcd1  1/1     Running   0          45s
```

### Step 5 expected output

`curl -v http://localhost/`:

```
*   Trying 127.0.0.1:80...
* Connected to localhost (127.0.0.1) port 80
> GET / HTTP/1.1
> Host: localhost
> ...
< HTTP/1.1 404 Not Found
< Server: nginx
< ...
```

The `404` is the right answer. It proves NGINX received the request and could not match it to any Ingress rule.

### Step 7 expected output

`curl -v http://app.localhost/`:

```
> GET / HTTP/1.1
> Host: app.localhost
> ...
< HTTP/1.1 200 OK
< Server: nginx
< Content-Type: text/html
< ...
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
...
```

### Diagnostic questions

- **Q: Why does the NGINX pod need `hostNetwork: true`?** Because we want NGINX to bind to the kind node's port 80 and 443, which means it has to be in the host network namespace of the *node*. In kind, the "node" is itself a Docker container, so the "host network of the node" is the network namespace of the kind container, which is what the `extraPortMappings` forwards from your laptop.
- **Q: Why DaemonSet and not Deployment?** With `hostNetwork: true`, only one pod per node can bind to port 80. A DaemonSet (one pod per node) makes that constraint explicit and predictable. A Deployment with `replicas: 1` would work for a single-node cluster but breaks the moment you scale to multi-node.
- **Q: What changes for a multi-node kind cluster?** Each node needs the `ingress-ready=true` label and the `extraPortMappings`, but only one node should map ports 80/443 to the *host* (because the host has only one port 80). In practice, multi-node kind for ingress is rare; we keep it single-node.

---

## Exercise 2 — Install cert-manager and Issue a Certificate

### Step 1 expected output

After all three rollouts succeed:

```
deployment "cert-manager" successfully rolled out
deployment "cert-manager-webhook" successfully rolled out
deployment "cert-manager-cainjector" successfully rolled out
```

`kubectl get crds | grep cert-manager`:

```
certificaterequests.cert-manager.io        ...
certificates.cert-manager.io               ...
challenges.acme.cert-manager.io            ...
clusterissuers.cert-manager.io             ...
issuers.cert-manager.io                    ...
orders.acme.cert-manager.io                ...
```

### Step 2 expected output

```
$ kubectl get clusterissuer selfsigned -o jsonpath='{.status.conditions[0].type}={.status.conditions[0].status}{"\n"}'
Ready=True
```

### Step 3 expected output

`kubectl -n ex01 get certificate app-tls`:

```
NAME      READY   SECRET    AGE
app-tls   True    app-tls   15s
```

`openssl x509 -text -noout` of the decoded cert:

```
Certificate:
    Data:
        Version: 3 (0x2)
        Serial Number:
            ...
        Signature Algorithm: sha256WithRSAEncryption
        Issuer: O = cert-manager, CN = ...
        Validity
            Not Before: May 14 ...
            Not After:  Aug 12 ...
        Subject: CN = app.localhost
        ...
        X509v3 extensions:
            X509v3 Subject Alternative Name:
                DNS:app.localhost
```

### Step 5 expected output

`curl -v --insecure https://app.localhost/`:

```
* Server certificate:
*  subject: CN=app.localhost
*  start date: ...
*  expire date: ... (90 days later)
*  issuer: O=cert-manager; CN=...
*  SSL certificate verify result: self signed certificate (18), continuing anyway.
> GET / HTTP/2
< HTTP/2 200
```

### Step 7 expected output

`kubectl -n ex01 describe certificaterequest <name>` shows:

```
Status:
  Conditions:
    Type:   Ready
    Status: True
    Reason: Issued
  ...
Events:
  Reason   ... Message
  IssuancePending  ... Waiting for issuer to sign the request
  CertificateIssued ... Certificate issued
```

### Diagnostic questions

- **Q: Why does cert-manager need a webhook?** The webhook is the admission controller that validates cert-manager resources before the API server accepts them. If you submit a malformed Certificate (e.g., referring to a non-existent Issuer), the webhook returns a 4xx before the resource is stored, and you get a clear error message instead of an opaque controller-loop failure later.
- **Q: Why is the renewal demo done by deleting the Secret?** cert-manager renews when (a) the Certificate's `renewBefore` window opens, or (b) the Secret is missing or corrupt. Deleting the Secret simulates the second case and is the fast path for testing the loop without waiting weeks.
- **Q: What is the difference between a self-signed cert and a Let's Encrypt staging cert?** Both are real X.509 certificates. The self-signed cert is signed by a CA cert-manager generated; that CA exists nowhere else, so no browser trusts it. The Let's Encrypt staging cert is signed by Let's Encrypt's staging CA, which is also not in browser trust stores (deliberately, so staging certs cannot be misused). Both fail browser validation; the staging cert at least exercises the same code path the production cert uses.

---

## Exercise 3 — Bootstrap ArgoCD and Sync an App

### Step 1 expected output

After all three rollouts succeed:

```
statefulset rolling update complete N pods at revision ...
deployment "argocd-server" successfully rolled out
deployment "argocd-repo-server" successfully rolled out
```

`kubectl -n argocd get pods`:

```
NAME                                                READY   STATUS    AGE
argocd-application-controller-0                     1/1     Running   90s
argocd-applicationset-controller-...                1/1     Running   90s
argocd-dex-server-...                               1/1     Running   90s
argocd-notifications-controller-...                 1/1     Running   90s
argocd-redis-...                                    1/1     Running   90s
argocd-repo-server-...                              1/1     Running   90s
argocd-server-...                                   1/1     Running   90s
```

### Step 2 expected output

```
$ INITIAL_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret \
    -o jsonpath="{.data.password}" | base64 -d)
$ echo "$INITIAL_PASSWORD"
abCdEf12345...
```

(The password is a random 16+ character string.)

### Step 4 expected output

`kubectl get application hello-argo -n argocd -o jsonpath='{.status.sync.status}{"  "}{.status.health.status}{"\n"}'`:

```
# Initially:
OutOfSync  Missing

# After ~10 seconds:
Synced  Progressing

# After ~30 seconds:
Synced  Healthy
```

`kubectl -n hello-argo get all`:

```
NAME                                READY   STATUS    AGE
pod/guestbook-ui-...                1/1     Running   30s

NAME                  TYPE        CLUSTER-IP    PORT(S)   AGE
service/guestbook-ui  ClusterIP   10.96.x.x     80/TCP    30s

NAME                            READY   UP-TO-DATE   AVAILABLE
deployment.apps/guestbook-ui    1/1     1            1

NAME                                       DESIRED   CURRENT   READY
replicaset.apps/guestbook-ui-...           1         1         1
```

### Step 5 expected output

Before the scale:

```
$ kubectl -n hello-argo get deployment guestbook-ui
NAME           READY   UP-TO-DATE   AVAILABLE   AGE
guestbook-ui   1/1     1            1           2m
```

After `kubectl scale --replicas=5`:

```
$ kubectl -n hello-argo get deployment guestbook-ui
NAME           READY   UP-TO-DATE   AVAILABLE   AGE
guestbook-ui   5/5     5            5           2m
```

After waiting ~30 seconds for ArgoCD's selfHeal sweep:

```
$ kubectl -n hello-argo get deployment guestbook-ui
NAME           READY   UP-TO-DATE   AVAILABLE   AGE
guestbook-ui   1/1     1            1           3m
```

The replica count is back at 1. In the ArgoCD UI, the Application history shows two recent sync events: one for the initial deploy, one for the selfHeal.

### Step 7 expected output (selected commands)

```
$ argocd app list
NAME        CLUSTER                         NAMESPACE     PROJECT  STATUS  HEALTH   SYNCPOLICY
hello-argo  https://kubernetes.default.svc  hello-argo    default  Synced  Healthy  Auto-Prune
```

### Diagnostic questions

- **Q: Why is the Application namespaced to `argocd` but its workload is in `hello-argo`?** The `Application` resource itself lives wherever ArgoCD is configured to watch (the `argocd` namespace by default; `applicationsets` and multi-namespace setups change this). The `destination.namespace` field is where the workload goes. Two different namespaces, two different concerns: the ArgoCD-control-plane namespace and the workload namespace.
- **Q: What would happen if you deleted the `Application` resource?** ArgoCD would stop reconciling. The workload resources (Deployment, Service) would remain. To clean up the workload as well, you would delete the Application with the `cascade=true` finalizer behavior, which ArgoCD handles via the `resources-finalizer.argocd.argoproj.io` finalizer on the Application. The safer pattern is to remove the Application's manifests from Git and let ArgoCD prune.
- **Q: Why does `selfHeal` not always revert immediately?** ArgoCD polls Git on a schedule (default 3 minutes) and reconciles. The selfHeal sweep runs on the same loop. If you want faster reverts, decrease the polling interval (`timeout.reconciliation` in the ArgoCD ConfigMap) or trigger a manual sync via webhook from Git.

---

## Exercise 4 — GKE Autopilot Dry-Run

There is no "expected output" for Exercise 4 because it is a dry-run; the artifact is your write-up.

### The reflection in Section 7 — what we are looking for

For prompt 1 (three differences):

1. The cluster creation command: `gcloud container clusters create-auto` vs `kind create cluster --config ...`. Autopilot is a managed cluster; kind is a local Docker-in-Docker cluster.
2. The NGINX Ingress Service type: `LoadBalancer` (Autopilot provisions a Google Cloud Load Balancer with an external IP) vs `hostPort` (kind binds to the kind container's network namespace, which is then forwarded to your laptop).
3. The cert-manager ClusterIssuer: Let's Encrypt staging/production (Autopilot is reachable from the public Internet, so HTTP-01 works) vs self-signed (kind is behind your laptop's NAT, so HTTP-01 cannot work).

For prompt 2 (cost):

- Autopilot control plane: $0/hour (free tier covers one zonal cluster).
- 2 replicas of `nginx-unprivileged` at the Autopilot minimum (250m CPU, 512Mi memory): roughly 0.5 vCPU and 1 GiB memory, billed at ~$0.045/vCPU-hour and ~$0.005/GiB-hour as of May 2026. So roughly $0.030/hour for the application pods.
- Google Cloud Load Balancer (provisioned by the LoadBalancer Service): $0.025/hour plus per-GB egress (negligible for an hour of testing).
- Total: roughly $0.05-$0.10 for an hour of testing. Tear down before you forget and it stays bounded.

For prompt 3 (Workload Identity binding):

- The principal `serviceAccount:PROJECT.svc.id.goog[ex04/app-sa]` precisely identifies *one* KSA in *one* namespace. Granting `[*/app-sa]` would let any namespace's `app-sa` KSA impersonate the GSA, which would mean any user with permission to create a KSA named `app-sa` in any namespace (a much broader set of users) could call Google APIs as the GSA. This is a privilege-escalation vector.
- The fix is what cert-manager and ArgoCD also do: scope by namespace explicitly. Names are cheap; trust boundaries are not.

For prompt 4 (open question): we expect a substantive question — about the Autopilot scheduler, about Compute Classes, about the Workload Identity metadata server, about the cost model. Reflective engagement is the goal.

---

## Common debugging patterns across all four exercises

Three diagnostic commands you will reach for repeatedly:

1. **`kubectl describe <kind> <name>`** — for any resource that is not in the state you expect. The "Events" section at the bottom is where the cluster tells you what is wrong. Read top to bottom; the most recent events are at the bottom.
2. **`kubectl logs <pod> [--previous]`** — for any pod that is CrashLoopBackOff or whose containers are misbehaving. `--previous` shows the *last* container's logs, which is critical when the current container is restarting too fast to read live.
3. **`kubectl get events --sort-by='.lastTimestamp'`** — cluster-wide event log. Useful when you do not know which resource is the problem and just want a chronological list of "what has the cluster been doing."

These are the three commands you will use 80% of the time as a Kubernetes operator. Internalize them this week; you will use them every week for the rest of this course.
