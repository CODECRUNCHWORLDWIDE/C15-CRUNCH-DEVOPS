# Week 6 — Exercises

Three hands-on drills, escalating in scope. Each builds on the previous; do them in order. By the end of Exercise 3, you will have a Packer-baked DigitalOcean snapshot in your account, an Argo CD install on a local `kind` cluster reconciling against a config repo, and a Flux install on a parallel `kind` cluster doing the same thing with different shape.

| Exercise | Title | Time | Cost |
|----------|-------|------|------|
| [01](./exercise-01-packer-image.md) | Bake a DigitalOcean droplet image with Packer | 90 min | ~$0.20 (build droplet + snapshot storage for the week) |
| [02](./exercise-02-argocd-setup.md) | Install Argo CD on a `kind` cluster and reconcile a small app | 90 min | $0.00 (entirely local) |
| [03](./exercise-03-flux-vs-argo.md) | Install Flux on a parallel `kind` cluster; reconcile the same app; write the comparison | 90 min | $0.00 (entirely local) |

---

## Before you start

Have these ready:

- A DigitalOcean account with a payment method on file (carried over from Week 5).
- A DigitalOcean **personal access token** with both **read** and **write** scopes. Export it as `TF_VAR_do_token` and `PKR_VAR_do_token` in every shell you use this week.
- `terraform` installed (1.9+), `packer` installed (1.11+), `kind` installed (0.24+), `kubectl` installed, `argocd` CLI installed, `flux` CLI installed.
- `doctl` authenticated against the same DigitalOcean account.
- An SSH key in `~/.ssh/id_ed25519` (the same one Week 5 registered with DigitalOcean).
- `gh` authenticated. Every exercise lives in its own GitHub repo or uses the config repo we create in Exercise 2.
- Docker Desktop (or Colima, or Podman with Docker compatibility) running. `kind` needs a container runtime.

```bash
export TF_VAR_do_token=dop_v1_........................................
export PKR_VAR_do_token=$TF_VAR_do_token
packer -version            # 1.11+
kind version               # 0.24+
kubectl version --client   # 1.30+ (server version is whatever kind installs)
argocd version --client    # 2.13+
flux --version             # 2.4+
docker info                # must succeed
```

If any command fails, fix it before running an exercise. The most common failure mode in this week's exercises is *Docker is not running* — `kind` will print a misleading error that looks like a Kubernetes problem.

---

## Cleanup discipline

Two cleanup loops this week:

- **DigitalOcean** — Packer build droplets are destroyed automatically at the end of each build. Snapshots are kept (we use them in the mini-project). At the end of the week, run `doctl compute snapshot list` and delete any that are not needed; each one is $0.05 / GB / month.
- **Local `kind` clusters** — Run `kind delete cluster --name <name>` at the end of Exercise 2 and Exercise 3. The clusters are free but they consume RAM and disk. Two `kind` clusters together is about 3 GB of RAM.

```bash
doctl compute snapshot list
# (review; remove anything you don't need)

doctl compute snapshot delete <snapshot-id>

kind get clusters
# argocd-lab
# flux-lab

kind delete cluster --name argocd-lab
kind delete cluster --name flux-lab
```

The Spaces bucket from Week 5 Exercise 3 stays in place. The mini-project uses it.

---

*If you find errors in this material, please open an issue or send a PR.*
