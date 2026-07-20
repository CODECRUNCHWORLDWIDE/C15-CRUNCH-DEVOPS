# Week 1 — What is a Container, Really?

> *Before you `docker run`, you should be able to build a container with the tools that come on a stock Linux box. Otherwise Docker is a magic word and the moment something breaks you have nowhere to stand.*

Welcome to **C15 · Crunch DevOps**. Week 1 is deliberately unusual: we do not start by installing Docker. We start by building a container by hand — `unshare`, `chroot`, a tarball, a few cgroup writes — so that when Docker shows up on Wednesday, it is not a tool you have to trust; it is a tool you can read.

Most DevOps courses begin with `docker run hello-world` and walk away three months later with engineers who can write a `Dockerfile` but cannot tell you which kernel feature makes process isolation actually work. We are not doing that. By Friday of Week 1 you will be able to explain — to a colleague, to an interviewer, to yourself at 3 AM during an incident — what a container *is*, why it is not a VM, and which Linux primitives the entire container ecosystem rests on.

The second half of the week is a tour of the **OCI image stack**: image format, registry protocol, runtimes (`runc`, `crun`), engines (Docker, Podman, containerd, nerdctl). You will leave Week 1 with a working mental model of the layers between your Dockerfile and a running process, and a defensible answer to "why is Docker the default and what is replacing it?"

---

## Learning objectives

By the end of this week, you will be able to:

- **Explain** what a Linux container is in terms of namespaces, cgroups, and capabilities — without using the word "Docker."
- **Build** a working container by hand using only `unshare`, `chroot`, a base-image tarball, and a few `cgroup` writes. No Docker, no Podman.
- **Distinguish** a container from a virtual machine on at least four axes: kernel sharing, boot time, density, security model.
- **Read** an OCI image: list its layers, inspect its manifest, locate its config blob, and explain what each one does.
- **Distinguish** the container engine (Docker, Podman, nerdctl) from the container runtime (`runc`, `crun`, `youki`) — and explain why decoupling them was the whole point of the OCI.
- **Write** a small but correct multi-stage `Dockerfile` for a Python web service and explain why each `RUN`, `COPY`, and `FROM` instruction is where it is.
- **Defend** a pinning strategy for base images that survives a supply-chain audit: digests over tags, lockfiles over `latest`.

---

## Prerequisites

This week assumes you have completed **C1 weeks 1–11** *and* **C14 · Crunch Linux**, or have equivalent comfort. Specifically:

- You can move around a shell: `cd`, `ls`, `find`, `grep`, `sudo`, file permissions.
- You have run a Linux box before — bare metal, VM, WSL2, or a cloud instance. You know what an init system is in name.
- You can read a `man` page and a `--help`.
- You have written a small Python or Flask app at some point. We use one as our containerization target.

If any of those are shaky, **stop** and review the relevant C1 or C14 week before continuing. Week 1 of C15 moves fast.

You also need access to a **Linux** machine (kernel 5.x or newer) where you can run privileged commands. macOS and Windows do not have Linux namespaces; the unhand-built container exercise requires Linux. Options, in order of preference:

1. A small cloud VM ($5 / month tier on DigitalOcean, Hetzner, or Linode).
2. A local Linux VM via `multipass`, `colima`, or VirtualBox.
3. WSL2 with Ubuntu 22.04 or newer.
4. A bare-metal Linux box.

Docker Desktop runs a Linux VM under the hood. That's fine for Wednesday onward, but not for the hand-built container exercise — you need real `unshare` access.

---

## Topics covered

- The four kernel features that make containers possible: **namespaces**, **cgroups**, **capabilities**, **chroot** (with **pivot_root**).
- Each namespace in detail: `pid`, `mount`, `net`, `user`, `uts`, `ipc`, `cgroup`, `time`.
- Why a container is **not** a VM: shared kernel, no hypervisor, no virtual hardware. Implications for cost, density, startup time, and the security model.
- The historical road to here: chroot (1979), FreeBSD jails (2000), LXC (2008), Docker (2013), OCI (2015), containerd / runc (2017).
- Building a container *without* Docker: `unshare`, `chroot`, a Debian rootfs tarball, a cgroup directory.
- The **OCI Image Specification**: layers, manifest, config, content-addressable storage.
- The **OCI Runtime Specification** and the `config.json` a runtime consumes.
- Container engines vs runtimes: Docker (engine) → containerd (engine) → runc (runtime). Podman vs Docker. nerdctl vs `docker`.
- Image registries: Docker Hub, GHCR, ECR, GAR — and the v2 registry HTTP API.
- Tag mutability vs digest immutability. Why production should pin by digest.
- Multi-stage `Dockerfile`s, base-image choices (Debian, Alpine, distroless, scratch), and lockfile discipline.
- A first real `Dockerfile` for a Python app — written carefully, line by line.

---

## Weekly schedule

The schedule below adds up to approximately **36 hours**. Treat it as a target. Some sections will click in 20 minutes, others will need 3 hours. That's fine.

| Day       | Focus                                              | Lectures | Exercises | Challenges | Quiz/Read | Homework | Mini-Project | Self-Study | Daily Total |
|-----------|----------------------------------------------------|---------:|----------:|-----------:|----------:|---------:|-------------:|-----------:|------------:|
| Monday    | Namespaces, cgroups, the mental model              |    2h    |    1h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     5h      |
| Tuesday   | Hand-built container with `unshare` + `chroot`     |    1h    |    2h     |     1h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Wednesday | OCI image stack, runtimes vs engines               |    2h    |    1h     |     1h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Thursday  | First real Dockerfile, layer caching               |    1h    |    2h     |     1h     |    0.5h   |   1h     |     2h       |    0.5h    |     8h      |
| Friday    | Registries, pinning, image-shrinking challenge     |    0h    |    1h     |     1h     |    0.5h   |   1h     |     2h       |    0.5h    |     6h      |
| Saturday  | Mini-project deep work                             |    0h    |    0h     |     0h     |    0h     |   1h     |     3h       |    0h      |     4h      |
| Sunday    | Quiz, review, write the README                     |    0h    |    0h     |     0h     |    0.5h   |   0h     |     0h       |    0h      |     0.5h    |
| **Total** |                                                    | **6h**   | **7h**    | **4h**     | **3h**    | **6h**   | **7h**       | **2.5h**   | **35.5h**   |

---

## How to navigate this week

| File | What's inside |
|------|---------------|
| [README.md](./README.md) | This overview (you are here) |
| [resources.md](./resources.md) | Curated readings: kernel docs, OCI specs, free books |
| [lecture-notes/01-namespaces-cgroups-and-the-container-mental-model.md](./lecture-notes/01-namespaces-cgroups-and-the-container-mental-model.md) | The kernel features that make containers possible |
| [lecture-notes/02-from-tarball-to-image-the-oci-stack.md](./lecture-notes/02-from-tarball-to-image-the-oci-stack.md) | OCI image format, runtimes, engines, registries |
| [exercises/README.md](./exercises/README.md) | Index of short hands-on drills |
| [exercises/exercise-01-build-a-container-by-hand.md](./exercises/exercise-01-build-a-container-by-hand.md) | Build a container with `unshare` + `chroot` + a tarball |
| [exercises/exercise-02-first-real-docker.md](./exercises/exercise-02-first-real-docker.md) | Build the same container with Docker; compare |
| [challenges/README.md](./challenges/README.md) | Index of weekly challenges |
| [challenges/challenge-01-shrink-the-image.md](./challenges/challenge-01-shrink-the-image.md) | Take a 1GB image to under 50MB without breaking it |
| [quiz.md](./quiz.md) | 10 multiple-choice questions |
| [homework.md](./homework.md) | Six practice problems |
| [mini-project/README.md](./mini-project/README.md) | Full spec for the "Containerize an Existing App" project |

---

## Stretch goals

If you finish early and want to push further:

- Read the [OCI Image Specification](https://github.com/opencontainers/image-spec) end-to-end. It is short and unusually well-written for a spec.
- Pick one of `runc`, `crun`, or `youki` and skim its `README` and `main.go` / `main.rs`. You do not need to understand it all — just see that "the runtime" is a small program.
- Browse [`namespaces(7)`](https://man7.org/linux/man-pages/man7/namespaces.7.html) and [`cgroups(7)`](https://man7.org/linux/man-pages/man7/cgroups.7.html) on `man7.org`. These two man pages are the single best free reference on the kernel side of containers.
- Run `docker run --rm -it alpine sh`, then in another terminal run `ps -ef | grep sh` on the *host*. Find your container's `sh` process in the host's process tree. That is the namespace boundary made tangible.

---

## Up next

Continue to [Week 2 — Dockerfiles That Don't Suck](../week-02-dockerfiles-that-dont-suck/) once you have pushed your Week 1 mini-project to GitHub.

---

*If you find errors in this material, please open an issue or send a PR. Future learners will thank you.*
