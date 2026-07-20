# Week 7 — Exercises

Three hands-on drills, escalating in scope. Each builds on the previous; do them in order. By the end of Exercise 3, you will have a `kind` cluster running on your laptop, fluent `kubectl` reflexes, and a working Deployment + Service + ConfigMap manifest you can copy into the mini-project.

| Exercise | Title | Time | Cost |
|----------|-------|------|------|
| [01](./exercise-01-bootstrap-a-cluster.md) | Bring up a `kind` cluster and inspect every component | 60 min | $0.00 (local) |
| [02](./exercise-02-kubectl-the-cluster.md) | `kubectl get`, `describe`, `explain`, jsonpath, the four flavours of access | 90 min | $0.00 (local) |
| [03](./exercise-03-deploy-a-stateless-app.yaml) | A complete Deployment + Service + ConfigMap manifest with a walkthrough | 60 min | $0.00 (local) |

Solutions are in [SOLUTIONS.md](./SOLUTIONS.md). Try each exercise yourself first; check the solution only when you are stuck for more than 10 minutes.

---

## Before you start

Have these ready:

- A laptop with **Docker Desktop** (or **Colima**, or **Podman with Docker compatibility**) running. `kind` brings up Kubernetes inside Docker; without a container runtime, none of this works.
- **`kind`** (0.24+), **`kubectl`** (1.31+), and **`docker`** installed.
- About **6 GB of free RAM**. A single-node `kind` cluster is 2-3 GB at idle; the mini-project pushes it to 4-5 GB.
- The GitHub Container Registry image you built and pushed in **Week 4 Exercise 3** (a small Python or Node Hello-World API). If you no longer have it, any public image will do; the docs default to `ghcr.io/nginxinc/nginx-unprivileged:latest`.
- A terminal you trust. We will run a lot of `kubectl` in this week; the prompt should be one you can read fast.

```bash
kind version              # 0.24+
kubectl version --client  # 1.31+
docker info | head -1     # must succeed; if not, start Docker Desktop
```

If any command fails, fix it before running an exercise. The most common failure mode in this week's exercises is **Docker is not running** — `kind` will print a misleading error that looks like a Kubernetes problem.

---

## Cleanup discipline

Two cleanup loops this week:

- **Local `kind` clusters** — Run `kind delete cluster --name <name>` between exercises if you do not need the previous one. Each cluster is 2-3 GB of RAM; running three at once will swamp a 16 GB laptop.
- **Docker images** — `kind load docker-image` copies images into the cluster's node. These accumulate on disk; `docker system prune` reclaims them at the end of the week.

```bash
kind get clusters
# ex01-cluster
# ex02-cluster
# ex03-cluster

kind delete cluster --name ex01-cluster
kind delete cluster --name ex02-cluster
kind delete cluster --name ex03-cluster
```

The exercises share a single cluster (`c15-w07-lab`) unless noted; you do not need three. The example above is to show what cleanup looks like if you have ended up with three.

---

*If you find errors in this material, please open an issue or send a PR.*
