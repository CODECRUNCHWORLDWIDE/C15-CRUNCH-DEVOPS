# Exercise 1 — Cluster Bootstrap: kind + Terraform + ArgoCD

**Estimated time:** 90 minutes.
**Prerequisite reading:** Lecture 1.
**Files used:** `kind-w12.yaml`, `manifests-app-of-apps.yaml`.

The goal of this exercise is to stand up the empty cluster the capstone will run in. By the end you will have a kind cluster with ArgoCD installed and an `app-of-apps` Application reconciling. Subsequent exercises add the platform components and the application.

We use only free, open-source components. Terraform is used to make the bootstrap reproducible; the alternative (a shell script) is shorter but harder to operate.

---

## Part A — Verify prerequisites

From a fresh terminal:

```bash
docker --version              # 24.x or later
kind --version                # 0.24 or later
kubectl version --client      # 1.31 or compatible
helm version --short          # 3.14 or later
terraform version             # 1.9 or later
argocd version --client       # 2.12 or later
```

If any are missing, install before continuing. Install paths:

- Docker Desktop: <https://docs.docker.com/desktop/>
- kind: <https://kind.sigs.k8s.io/docs/user/quick-start/#installation>
- kubectl: <https://kubernetes.io/docs/tasks/tools/>
- Helm: <https://helm.sh/docs/intro/install/>
- Terraform: <https://developer.hashicorp.com/terraform/install>
- ArgoCD CLI: <https://argo-cd.readthedocs.io/en/stable/cli_installation/>

---

## Part B — Create the kind cluster

The `kind-w12.yaml` configuration creates a 3-node cluster (1 control-plane + 2 workers) with host ports 80 and 443 mapped through the control-plane node so that ingress-nginx (installed in Exercise 3) can serve external traffic.

```bash
kind create cluster --name capstone --config kind-w12.yaml
kubectl cluster-info --context kind-capstone
kubectl get nodes
```

Expected: three nodes Ready. The control-plane node has the label `ingress-ready=true` (verify with `kubectl get nodes --show-labels | grep ingress-ready`).

The first `kind create cluster` after a `kind delete cluster` sometimes leaves a stale Docker network. If you see "network in use", run:

```bash
docker network prune -f
kind create cluster --name capstone --config kind-w12.yaml
```

---

## Part C — Set up the local container registry

The capstone builds and pushes its application image to a local registry running on the same Docker network as the kind cluster. This is the standard kind + local-registry recipe from <https://kind.sigs.k8s.io/docs/user/local-registry/>.

```bash
# Create the registry container if not already running.
if [ "$(docker inspect -f '{{.State.Running}}' kind-registry 2>/dev/null || true)" != "true" ]; then
  docker run -d --restart=always \
    -p 127.0.0.1:5001:5000 \
    --network bridge \
    --name kind-registry \
    registry:2
fi

# Connect the registry to the kind network.
if [ "$(docker inspect -f '{{json .NetworkSettings.Networks.kind}}' kind-registry)" = 'null' ]; then
  docker network connect kind kind-registry
fi

# Document the registry in the cluster.
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:5001"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF
```

Verify:

```bash
curl -sf http://localhost:5001/v2/_catalog
# expected output: {"repositories":[]}
```

---

## Part D — Install ArgoCD via Helm

This is the only Helm install you run by hand. Every subsequent install comes through ArgoCD.

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update

helm install argocd argo/argo-cd \
  --namespace argocd \
  --create-namespace \
  --version 7.6.0 \
  --set server.service.type=ClusterIP \
  --set configs.params."server\.insecure"=true \
  --wait \
  --timeout 5m
```

Notes on the flags:

- `server.service.type=ClusterIP`: we will `port-forward` for the UI; no NodePort.
- `configs.params.server.insecure=true`: ArgoCD serves the UI on HTTP behind the in-cluster network. ingress-nginx (Exercise 3) will terminate TLS on the public edge. For an exposed ArgoCD UI in production, this flag must be false.

Verify:

```bash
kubectl get pods -n argocd
kubectl wait --for=condition=available --timeout=5m \
  deployment/argocd-server -n argocd
```

Retrieve the initial admin password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d ; echo
```

Save the password somewhere safe; we will replace the secret with a managed credential in production.

Port-forward and log in:

```bash
kubectl port-forward -n argocd svc/argocd-server 8080:443 &
ARGOCD_PF_PID=$!
sleep 3

argocd login localhost:8080 --insecure --username admin --password "<PASTE>"
argocd app list
```

The `argocd app list` should return an empty list. We have no Applications yet.

---

## Part E — Apply the App-of-Apps

The `manifests-app-of-apps.yaml` is the root Application. Edit the `repoURL` field to point at your fork of the capstone repository, then:

```bash
kubectl apply -f manifests-app-of-apps.yaml
```

For now the App-of-Apps will reference an empty `gitops/apps/` directory (or your fork's directory if you have one ready). It is fine for the root Application to be Healthy with zero child Applications.

Verify:

```bash
argocd app list
# expected: one Application named app-of-apps
argocd app get app-of-apps
# expected: Sync Status = Synced, Health Status = Healthy
```

If the App-of-Apps reports `OutOfSync` because the `gitops/apps/` directory does not yet exist in your fork, that is expected — the next exercises populate it.

---

## Part F — Checkpoint

Capture the following and paste into `SOLUTIONS.md`:

1. The output of `kubectl get nodes -o wide`.
2. The output of `kubectl get pods -A | head -30`.
3. The output of `argocd app list`.
4. A one-paragraph reflection: the bootstrap had three steps that could not be automated through GitOps — what were they, and why is each one a chicken-and-egg problem?

The third item is the qualitative part. Take the answer seriously; you will refer back to it when you write the runbook on Saturday.

The expected answers to question 4: (a) `kind create cluster` because there is no Kubernetes API to talk to before the cluster exists; (b) the ArgoCD install because there is no ArgoCD to reconcile the ArgoCD install; (c) the App-of-Apps apply because the ArgoCD Application CRD does not exist until ArgoCD is installed.

---

## Troubleshooting

**`kind create cluster` hangs at "Ensuring node image".** First-time runs pull the node image (~700 MB) from Docker Hub. The pull can take 5 to 10 minutes; the apparent hang is normal. Subsequent runs are sub-minute.

**ArgoCD pods stuck in `Pending`.** Check `kubectl describe pod -n argocd <pod>` for the scheduler's reason. Most likely: not enough memory. Increase Docker Desktop's memory allocation to 8 GB.

**`argocd login` times out.** The port-forward dropped. Re-run `kubectl port-forward -n argocd svc/argocd-server 8080:443 &` and retry.

**The App-of-Apps says `Unknown` status.** ArgoCD is fetching the Git repository for the first time; wait 30 seconds and retry. If it stays Unknown for more than 2 minutes, check `argocd app get app-of-apps` for the underlying error — usually a typo in the `repoURL`.

---

## Tear-down

The cluster persists across exercises. Tear down only on Sunday after the mini-project:

```bash
kubectl delete -f manifests-app-of-apps.yaml --ignore-not-found
helm uninstall argocd -n argocd
kind delete cluster --name capstone
docker stop kind-registry && docker rm kind-registry
```

---

## Reading

- kind: <https://kind.sigs.k8s.io/docs/user/quick-start/>
- kind local registry: <https://kind.sigs.k8s.io/docs/user/local-registry/>
- ArgoCD getting started: <https://argo-cd.readthedocs.io/en/stable/getting_started/>
- ArgoCD declarative setup: <https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/>
- App-of-Apps pattern: <https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/>

Continue to Exercise 2.
