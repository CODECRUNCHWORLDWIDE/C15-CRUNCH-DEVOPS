# Week 1 — Resources

Every resource on this page is **free** and **publicly accessible**. No paywalled books, no proprietary PDFs. If a link breaks, please open an issue.

## Required reading (work it into your week)

- **Linux `namespaces(7)` man page** — the kernel-side reference. Read it before Tuesday:
  <https://man7.org/linux/man-pages/man7/namespaces.7.html>
- **Linux `cgroups(7)` man page** — same author (Michael Kerrisk), same quality:
  <https://man7.org/linux/man-pages/man7/cgroups.7.html>
- **Linux `capabilities(7)` man page** — the third leg of the stool:
  <https://man7.org/linux/man-pages/man7/capabilities.7.html>
- **OCI Image Specification** — what is in an image, in 50 readable pages:
  <https://github.com/opencontainers/image-spec>
- **OCI Runtime Specification** — what a runtime consumes:
  <https://github.com/opencontainers/runtime-spec>
- **Docker official docs — "What is a container?"** — the vendor framing, useful to know:
  <https://docs.docker.com/get-started/docker-overview/>

## The specs (skim, don't memorize)

You will rarely read these end-to-end. But the first time a code review cites "per the OCI image spec, the manifest media type is `application/vnd.oci.image.manifest.v1+json`," you should know what file that comes from.

- **OCI Image Layout**: <https://github.com/opencontainers/image-spec/blob/main/image-layout.md>
- **OCI Manifest**: <https://github.com/opencontainers/image-spec/blob/main/manifest.md>
- **OCI Image Config**: <https://github.com/opencontainers/image-spec/blob/main/config.md>
- **OCI Distribution Spec (registry API)**: <https://github.com/opencontainers/distribution-spec>
- **The Linux Programming Interface — kernel-facing book by Kerrisk** (chapters on namespaces are free samples from the publisher): <https://man7.org/tlpi/>

## Official tool docs

- **Docker Engine**: <https://docs.docker.com/engine/>
- **Dockerfile reference**: <https://docs.docker.com/reference/dockerfile/>
- **BuildKit** (the modern Docker build backend): <https://docs.docker.com/build/buildkit/>
- **Podman**: <https://docs.podman.io/>
- **containerd**: <https://containerd.io/docs/>
- **`runc`**: <https://github.com/opencontainers/runc>
- **`crun`** (faster, written in C): <https://github.com/containers/crun>
- **nerdctl** (Docker-compatible CLI for containerd): <https://github.com/containerd/nerdctl>
- **Buildah** (image building without a daemon): <https://buildah.io/>
- **`skopeo`** (inspect, copy, sign images without pulling them): <https://github.com/containers/skopeo>

## Free books and write-ups

- **"Container Internals" by Liz Rice (KubeCon keynote series — free on YouTube)** — search YouTube for "Liz Rice container from scratch." Her *Container Security* book is paid, but the conference talks cover most of it for free.
- **Julia Evans — "What is a container?" zine excerpt**: <https://wizardzines.com/comics/what-is-a-container/>
- **Julia Evans — "Linux containers in 500 lines of code"**: <https://blog.lizrice.com/post/2018-10-09-tracee/> (Liz Rice's article; Julia has companion zines)
- **"Operating Systems: Three Easy Pieces" (free PDF), chapters on virtualization**:
  <https://pages.cs.wisc.edu/~remzi/OSTEP/>
- **Jess Frazelle — "Setting the record straight: containers vs. zones vs. jails vs. VMs"**:
  <https://blog.jessfraz.com/post/containers-zones-jails-vms/>
- **Ivan Velichko — "Learning containers from the bottom up"**:
  <https://iximiuz.com/en/posts/container-learning-path/>
- **Red Hat — "A Practical Introduction to Container Terminology"**:
  <https://developers.redhat.com/blog/2018/02/22/container-terminology-practical-introduction>

## Videos (free, no signup)

- **"Containers From Scratch" — Liz Rice, GOTO Conference** (40 min). The canonical "containers are just Linux" talk:
  <https://www.youtube.com/watch?v=8fi7uSYlOdc>
- **"What Have Namespaces Done for You Lately?" — Liz Rice, LinuxCon**:
  <https://www.youtube.com/results?search_query=liz+rice+namespaces>
- **"cgroup v2 in production" — Chris Down (Meta)** — for when v1 vs v2 starts mattering:
  <https://www.youtube.com/results?search_query=chris+down+cgroup+v2>

## Open-source projects to read this week

You can learn more from one hour reading other people's code than from three hours of tutorials. Pick one and just scroll through the README and the entry-point file:

- **`runc`** — the reference OCI runtime, ~10k lines of Go: <https://github.com/opencontainers/runc>
- **`crun`** — same job in C, leaner: <https://github.com/containers/crun>
- **`containerd`** — the high-level engine Docker uses under the hood: <https://github.com/containerd/containerd>
- **`bocker`** — Docker in ~100 lines of bash (educational, no longer maintained, still the clearest read): <https://github.com/p8952/bocker>

## Tools you'll use this week

- **`unshare`** (from `util-linux`) — pre-installed on every Linux. `man unshare`.
- **`chroot`** — same.
- **`debootstrap`** — builds a minimal Debian rootfs from upstream: `sudo apt install debootstrap`.
- **`docker`** — install per <https://docs.docker.com/engine/install/>. Or Docker Desktop for macOS / Windows.
- **`skopeo`** — `sudo apt install skopeo` (Ubuntu 22.04+) or `brew install skopeo`.
- **`dive`** — interactive image-layer inspector, MIT-licensed: <https://github.com/wagoodman/dive>
- **`trivy`** — image vulnerability scanner, Apache-2.0: <https://github.com/aquasecurity/trivy>

## Glossary cheat sheet

Keep this open in a tab.

| Term | Plain English |
|------|---------------|
| **namespace** | A kernel feature that gives a process its own view of one kind of system resource (PIDs, mounts, network, etc.). |
| **cgroup** | A kernel feature that *limits* and *accounts for* resource use (CPU, memory, IO) per process group. |
| **capability** | A finer-grained piece of `root` power, e.g. `CAP_NET_BIND_SERVICE`. Containers drop most by default. |
| **chroot** | Change a process's notion of the filesystem root. Older, weaker than namespaces. |
| **OCI** | Open Container Initiative — the body that standardizes the image format and runtime interface. |
| **runtime** | The low-level program that actually `clone()`s the process and applies namespaces. `runc`, `crun`, `youki`. |
| **engine** | The higher-level daemon/CLI that pulls images, talks to a runtime, exposes a user interface. Docker, Podman, containerd. |
| **image** | A read-only filesystem template plus metadata, addressable by content hash. |
| **layer** | A tarball of filesystem changes; images are stacks of layers. |
| **manifest** | The JSON file listing an image's layers and config blob, by digest. |
| **registry** | An HTTP server that stores and serves images per the OCI distribution spec. |
| **digest** | A SHA-256 content hash, e.g. `sha256:9b…`; immutable. |
| **tag** | A human-readable pointer to a digest, e.g. `python:3.12-slim`; mutable. |

---

*If a link 404s, please [open an issue](https://github.com/CODE-CRUNCH-CLUB) so we can replace it.*
