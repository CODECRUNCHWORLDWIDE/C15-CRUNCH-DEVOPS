# Lecture 2 — From Tarball to Image: The OCI Stack

> **Outcome:** You can describe, with precision, what is inside an OCI image; which program does what when you type `docker run`; why Docker, Podman, containerd, runc, and nerdctl exist as separate tools; and why production images should be pinned by digest, not by tag.

Yesterday we learned that a container is a process with namespaces, cgroups, capabilities, and a swapped root. None of that says anything about *images*, *registries*, or *Docker*. Today we add those layers, and we learn the small but important vocabulary that lets you read a `Dockerfile`, a manifest, and a registry URL without guessing.

---

## 1. The road to here, in five hops

A potted history. None of these dates is on the quiz, but you should be able to put them in the right order.

| Year | What appeared | Why it mattered |
|------|---------------|-----------------|
| **1979** | `chroot` in Unix V7 | First "filesystem root, but not really" mechanism. Built-in to every Unix since. |
| **2000** | FreeBSD jails | Beyond `chroot`: separate `hostname`, `IP`, processes. Closer in spirit to a modern container. |
| **2002** | Linux mount namespaces (`CLONE_NEWNS`) | The first Linux namespace. Per-process mount tables. |
| **2008** | LXC (Linux Containers) | First user-friendly wrapper. "Containers" become a common word in Linux circles. |
| **2013** | Docker 0.1 | LXC + tooling + the image format + the registry. The package that won the market. |
| **2015** | Open Container Initiative (OCI) | Vendor-neutral specs for the image and the runtime. Docker, CoreOS, Red Hat, Google sign on. |
| **2017** | `containerd` and `runc` split out of Docker | The engine and the runtime become separable, replaceable components. |
| **2019** | Kubernetes deprecates `dockershim` | Kubernetes talks to `containerd` directly. Docker becomes one option among several. |

The takeaway: there is a *standard* (OCI) that defines what an image is and what a runtime must do, and there are *multiple implementations* of that standard. The whole point of "OCI-compliant" is that you can swap `runc` for `crun`, or `docker` for `podman`, and your images keep working.

---

## 2. What is in an image

An **OCI image** is three things on disk:

1. **One or more layer blobs**, each of which is a `tar` (or `tar.gz`) archive of filesystem changes.
2. **A config blob**, a JSON document describing the default command, environment variables, working directory, exposed ports, labels, and so on.
3. **A manifest**, a JSON document that lists the layers and the config, *by SHA-256 digest*.

That is it. An image is content-addressable: every blob is named by its SHA-256 hash, and the manifest pins those hashes. If you change a single byte in a layer, the layer's digest changes, the manifest pointing at it changes, and the image's digest changes. You cannot mutate an image in place. You can only build a new one.

### The directory layout

If you pull an image and store it on disk in the `oci-layout` format, the directory looks like this:

```
my-image/
├── oci-layout                ← {"imageLayoutVersion": "1.0.0"}
├── index.json                ← entrypoint; points at the manifest(s)
└── blobs/
    └── sha256/
        ├── 4f1a3c...         ← layer 1 (a tarball of files)
        ├── 9e02bb...         ← layer 2
        └── 7d2f8c...         ← config JSON
```

You can produce this layout from any registry image with `skopeo`:

```bash
skopeo copy docker://docker.io/library/alpine:3.20 oci:./alpine-image:latest
```

Then `cat alpine-image/index.json` and follow the digest chain by hand. This is the single best way to demystify the format. Exercise 2 has you do it.

### The manifest

A minimal OCI manifest looks like:

```json
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.oci.image.manifest.v1+json",
  "config": {
    "mediaType": "application/vnd.oci.image.config.v1+json",
    "digest": "sha256:7d2f8c...",
    "size": 1472
  },
  "layers": [
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:4f1a3c...",
      "size": 3221225
    },
    {
      "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
      "digest": "sha256:9e02bb...",
      "size": 712419
    }
  ]
}
```

The whole spec is at <https://github.com/opencontainers/image-spec/blob/main/manifest.md>. Read it once.

### The config blob

The config describes how to *use* the image. A trimmed example:

```json
{
  "architecture": "amd64",
  "os": "linux",
  "config": {
    "Env": ["PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"],
    "Entrypoint": ["/usr/local/bin/python"],
    "Cmd": ["-m", "myapp"],
    "WorkingDir": "/app",
    "ExposedPorts": {"8000/tcp": {}},
    "User": "10001"
  },
  "rootfs": {
    "type": "layers",
    "diff_ids": [
      "sha256:e2eb...", "sha256:b3a1..."
    ]
  },
  "history": [...]
}
```

Every `Dockerfile` instruction except `RUN`, `COPY`, and `ADD` writes into this config. `ENV`, `ENTRYPOINT`, `CMD`, `EXPOSE`, `WORKDIR`, `USER`, `LABEL` — these all set fields here. They do not produce a new layer; they produce a new config (which is itself a new blob with a new digest, hence a new manifest, hence a new image).

### Layers and overlay filesystems

When the runtime starts a container from an image, it does not unpack the layers into one folder. It stacks them with an **overlay filesystem** (`overlayfs` is the default on Linux). Reads come from the top-most layer that has the file; writes go to a new writable top layer that is discarded when the container exits — unless you give it a volume.

That stacking is why Docker is fast. Pulling an image you have already pulled before is mostly a no-op: the layers are content-addressable, the digests are the same, the existing blobs are reused. *Only the layers that changed* travel over the network.

A consequence with operational bite: if your build adds and then removes a 500 MB file in two separate `RUN` lines, the 500 MB still lives in the first layer. The second layer just records the deletion. The image is still 500 MB bigger than it needs to be. We will fix this with multi-stage builds in §6.

---

## 3. Engines vs runtimes

This is the single most common point of confusion in container interviews. Pay attention.

A **runtime** is a low-level program that knows how to take an `oci-layout` filesystem and a `config.json` and turn them into a running process. It calls `clone()` with the right namespace flags, applies cgroup limits, drops capabilities, `pivot_root`s into the rootfs, and `exec`s the entrypoint. That is its entire job.

An **engine** is a higher-level program that knows how to: pull images from a registry, store layers on disk, manage networks and volumes, expose an HTTP or gRPC API, accept user commands like "run this image with these ports forwarded," and delegate the *actual process creation* to a runtime.

A 2026 picture of the major implementations:

```
   You type:  docker run nginx
        │
        ▼
    +-----------+                 +----------+              +-------+
    | docker    | -- gRPC over -> | containerd | -- exec -> | runc  | ── clone(), namespaces, cgroups ── nginx
    | (CLI/API) |   unix socket   | (engine)   |            | (runtime)
    +-----------+                 +----------+              +-------+

   Podman:  podman run nginx
        │
        ▼
    +-----------+              +-------+
    | podman    | -- exec  --> | crun  | ── nginx
    | (CLI)     |              | or runc|
    +-----------+              +-------+
```

Differences worth knowing:

- **Docker** is an engine (a long-running daemon, `dockerd`) plus a CLI (`docker`). Under the hood, since 2017, the daemon delegates the *actual container start* to **containerd** (an engine) which delegates to **runc** (a runtime). This split makes the components separately reusable.
- **Podman** is a daemonless engine. There is no `podmand`; each `podman run` forks a `conmon` plus a runtime (`crun` by default, `runc` optional). Containers survive without a parent daemon. Rootless mode is the default. Output of `podman run` is compatible with Docker, by design.
- **containerd** is what Kubernetes (kubelet) talks to on most clusters since the `dockershim` deprecation. You rarely interact with `containerd` directly — its CLI (`ctr`) is for low-level use. **nerdctl** is the user-friendly `docker`-compatible CLI for containerd.
- **runc** is the OCI reference runtime, written in Go, maintained by the Linux Foundation. **crun** is a faster, smaller C reimplementation. **youki** is a Rust reimplementation. All three accept the same `config.json`.
- **CRI-O** is a Kubernetes-specific container engine designed only to satisfy the Kubernetes CRI (Container Runtime Interface). It is what Red Hat OpenShift ships. Equivalent in role to containerd.

What does this mean for you? In normal life, you use `docker` and never think about the layers underneath. The first time you debug a Kubernetes node that has `containerd` but no `docker`, you will need to know to reach for `crictl` or `nerdctl` instead. The first time you read a security advisory that says "affects `runc` < 1.1.12," you will know to check whether your engine bundles it.

---

## 4. Registries and the distribution spec

An **image registry** is an HTTP server that stores and serves OCI image blobs and manifests, conforming to the [OCI Distribution Specification](https://github.com/opencontainers/distribution-spec). Examples:

| Registry | URL pattern | Notes |
|----------|-------------|-------|
| **Docker Hub** | `docker.io/library/nginx:1.25` | The default if you omit the host. Free tier rate-limits anonymous pulls (100/6h). |
| **GitHub Container Registry (GHCR)** | `ghcr.io/your-org/your-image:tag` | Free for public images. Authenticated via PAT or GitHub Actions. |
| **Amazon ECR** | `<account>.dkr.ecr.<region>.amazonaws.com/repo:tag` | Pay-per-GB. Authenticated via IAM. |
| **Google Artifact Registry** | `<region>-docker.pkg.dev/<project>/<repo>/image:tag` | Pay-per-GB. Authenticated via GCP IAM. |
| **Quay.io** | `quay.io/coreos/etcd:v3.5` | Red Hat's. Strong on signing. |
| **Self-hosted `registry:2`** | `your-host:5000/image:tag` | The reference open-source registry, runnable in one container. |

All of them speak the same protocol. `docker pull` (or `skopeo`, or `podman`, or `crane`) does roughly:

```
GET /v2/                                       → 200, server says "I'm a v2 registry"
GET /v2/library/nginx/manifests/1.25            → JSON manifest, with layer digests
GET /v2/library/nginx/blobs/sha256:<layer-1>    → bytes of the layer
GET /v2/library/nginx/blobs/sha256:<layer-2>    → bytes of the layer
...
```

Authentication is bolted on with `Bearer` tokens. Pushing is the same in reverse: `PUT` the blobs, then `PUT` the manifest.

You can run a registry yourself in one line:

```bash
docker run -d -p 5000:5000 --name registry registry:2
```

Then `docker push localhost:5000/whatever:dev` works. There is no magic in "the cloud" version of this.

---

## 5. Tags lie. Digests do not.

A **tag** is a human-readable, *mutable* pointer to an image digest. `python:3.12-slim` today points to one digest; tomorrow, after the Python maintainers rebuild it, it points to a different digest. The tag does not change. The contents do.

A **digest** is the content-addressable SHA-256 of the manifest. Example:

```text
python@sha256:9c2ad9c0d3b8b9c1c3e8a4f8b7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8
```

That digest, by definition, refers to one and only one set of bytes — forever. Two engineers pulling that digest get bit-identical layers.

The operational rule is simple:

- **In a `Dockerfile` for development**, `FROM python:3.12-slim` is fine. You want to pick up base-image security updates.
- **In production deployment manifests**, pin by digest:
  ```yaml
  image: python@sha256:9c2ad9c0d3b8b9c1c3e8a4f8b7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8
  ```
  Promotions from staging to prod should be by digest, not by tag, so that "what we tested" and "what we deployed" are the exact same bytes.
- **In a CI pipeline**, capture the digest of every built image and emit it as a pipeline output. GitHub Actions has [`docker/build-push-action`](https://github.com/docker/build-push-action) which writes the digest to `${{ steps.build.outputs.digest }}`. Use it.

The Supply Chain Levels for Software Artifacts ([SLSA](https://slsa.dev/)) framework — which we will revisit in Week 11 — assumes digest pinning end-to-end. Everything else is theatre.

---

## 6. Multi-stage Dockerfiles, in one page

A naïve `Dockerfile` for a Python web app:

```dockerfile
FROM python:3.12
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "-m", "myapp"]
```

Three problems:

1. **Image size.** `python:3.12` is ~1 GB because it includes the entire Debian build toolchain (so users can `pip install` packages with C extensions). You ship that to production. You should not.
2. **Cache invalidation.** `COPY . .` happens before `pip install`, so editing any `.py` file invalidates the layer cache and re-runs `pip install`. Builds are slow.
3. **Security surface.** Compilers, `apt`, `sudo`, and a shell history are all in the production image. A vulnerability in `gcc` is now your problem.

A **multi-stage** `Dockerfile` solves all three. There are two `FROM` lines; the final image only carries artifacts from the last stage.

```dockerfile
# ---- Stage 1: builder ----
FROM python:3.12-slim AS builder

# Install build deps in a virtualenv so we can copy it to the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the dependency manifest first — this layer is cached
# until requirements.txt itself changes.
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the source code. Changes here do NOT invalidate the
# pip install layer above.
COPY src/ ./src/

# ---- Stage 2: runtime ----
FROM python:3.12-slim AS runtime

# Run as a non-root user. UID 10001 is a convention; pick whatever, just not 0.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

# Copy the venv and source from the builder stage. Nothing else from
# the builder makes it to the runtime image.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/src /app/src

ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app
USER app
EXPOSE 8000

ENTRYPOINT ["python", "-m", "src.myapp"]
```

Wins:

- The final image is `python:3.12-slim` plus a virtualenv plus your source. About 150 MB instead of 1 GB. Sometimes 50 MB on Alpine.
- Editing `src/main.py` invalidates only the last two layers. `pip install` does not re-run.
- No build toolchain in the runtime image. No `apt` history. Tighter attack surface.
- Runs as a non-root user. `CAP_*` reduced by default. One fewer escalation vector.

We will spend most of Week 2 on `Dockerfile`s. This is just to anchor the shape.

### Base image choices

| Base | Typical size | Good for | Caveats |
|------|-------------:|----------|---------|
| `debian:bookworm-slim` | ~80 MB | Default. `apt` available. Largest userland coverage. | Slightly larger; standard glibc. |
| `python:3.12-slim` | ~120 MB | Python apps. | Same Debian base + Python. |
| `alpine:3.20` | ~7 MB | Smallest practical Linux. | `musl` libc breaks some Python wheels; `apk add` instead of `apt`. |
| `gcr.io/distroless/python3-debian12` | ~50 MB | Production Python with no shell. | No `bash`, no `apt`, no debugging tools in the image. |
| `scratch` | 0 bytes | Statically linked binaries (Go, Rust, some C). | Nothing inside. Not even libc. Your binary is on its own. |

Pick the smallest base that does not break your runtime. `distroless` is the right answer for production *if* you have a separate debug image. Otherwise `slim` is the pragmatic default.

---

## 7. Reproducibility vs determinism

A `docker build` is **not** deterministic by default. Two builds of the same `Dockerfile` from the same source can produce different image digests because:

- `RUN apt-get install -y curl` resolves to a *currently latest* version of `curl`. Tomorrow that version is different.
- `RUN pip install -r requirements.txt` resolves against PyPI today; tomorrow a transitive dep gets a patch release.
- Timestamps on files end up in layer tarballs. Touch the source, get a new tar, get a new digest.

Making builds **reproducible** is a separate engineering effort. The toolbox:

| Tool | What it pins |
|------|--------------|
| `pip install -r requirements.lock` (from `pip-compile`) | Exact Python dep tree, transitive. |
| `uv lock` | Same idea, faster, single-file. |
| `apt-get install -y curl=7.88.1-10` | A specific Debian package version. |
| `FROM python@sha256:…` | The exact base-image bytes. |
| `--build-arg SOURCE_DATE_EPOCH=…` | Tells BuildKit to zero out file mtimes. |
| `buildx --provenance --sbom` | Emits SLSA provenance and a software bill of materials. |
| `cosign sign <digest>` | Cryptographic signature on the image. |

You do not need all of these in Week 1. You do need to know they exist. Pick the minimum that matches your risk tolerance: pin the base by digest, lockfile your deps, and you have ruled out 90% of "it works on my machine."

---

## 8. The Podman / Buildah / nerdctl landscape

Docker is the household name. It is not the only option, and in some shops it is no longer the default. Five reasons you might use something else:

1. **Daemonlessness.** Podman runs without a long-lived daemon. No root daemon to attack. Pods (sets of containers sharing namespaces) are a first-class concept. Drop-in replacement: `alias docker=podman` works for most workflows.
2. **Rootlessness.** Podman runs rootless by default. Rootless Docker exists but is opt-in and adds setup. For shared developer machines and CI runners, rootless is the safer default.
3. **Daemonless image building.** `buildah` builds OCI images without a Docker daemon, scriptable from shell. It is what Podman shells out to when you `podman build`.
4. **Kubernetes alignment.** `nerdctl` talks to `containerd` directly. If your production stack is `kubelet -> containerd`, using `nerdctl` locally narrows the dev/prod gap.
5. **Licensing.** Docker Desktop has a paid license for organizations over 250 employees / $10M revenue. Podman Desktop, Rancher Desktop, and OrbStack are free alternatives.

None of these reasons obsoletes Docker. Docker remains the most polished, best-documented option, and "I know Docker" is still the answer interviewers expect. Know it, and know that there are alternatives, and know *why* you might switch.

---

## 9. Self-check

Without re-reading:

1. What three components make up an OCI image on disk?
2. A `Dockerfile` says `ENV FOO=bar`. Does that produce a new layer? Why or why not?
3. Name the engine that Kubernetes (`kubelet`) talks to on most clusters since the deprecation of `dockershim`.
4. What is the relationship between `runc` and `crun`?
5. Why should production deployments pin images by digest, not by tag?
6. Your `python:3.12` image is 1 GB. Name two concrete changes to bring it under 200 MB without losing functionality.

---

## Further reading

- **OCI Image Specification (the manifest doc specifically)**:
  <https://github.com/opencontainers/image-spec/blob/main/manifest.md>
- **OCI Runtime Specification**:
  <https://github.com/opencontainers/runtime-spec/blob/main/spec.md>
- **Docker's own "Dockerfile best practices"** — still the right starting point:
  <https://docs.docker.com/build/building/best-practices/>
- **Adrian Mouat — "Five things you need to know about Buildah"**:
  <https://www.redhat.com/sysadmin/buildah-features>
- **Reproducible Builds project — Docker section**:
  <https://reproducible-builds.org/docs/>

Next: roll up your sleeves with [Exercise 1 — Build a Container by Hand](../03-exercises/exercise-01-build-a-container-by-hand.md).
