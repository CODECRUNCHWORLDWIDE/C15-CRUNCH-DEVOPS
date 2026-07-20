# Week 2 — Dockerfiles That Don't Suck

> *A `Dockerfile` is a build script that is going to be read more often than it is run. Write it for the reader.*

Welcome to Week 2 of **C15 · Crunch DevOps**. Week 1 taught you what a container *is*. Week 2 teaches you how to *build one well* — small, fast, reproducible, and defensible in a code review. By Sunday you will have built the same Flask app three different ways (naive single-stage, multi-stage virtualenv, distroless), measured each on size, build-time, and CVE count, and you will have an opinion about which one belongs in production.

We focus this week on the **`Dockerfile` itself**: the eleven instructions you will use 95% of the time, the two you should not (`ADD`, the long-form `MAINTAINER`), and the one nearly everybody forgets (`HEALTHCHECK`). Then we move to the three force-multipliers that turn a 1 GB image into a 40 MB image: **layer caching**, **multi-stage builds**, and **distroless base images**. Finally we add image scanning (`trivy`, `grype`) so you stop shipping CVEs you did not know about.

Last week's image-shrinking challenge was a warm-up. This week it becomes muscle memory.

---

## Learning objectives

By the end of this week, you will be able to:

- **Read** any production `Dockerfile` and explain, line by line, *why* each instruction is where it is — and what would break if it moved.
- **Write** a multi-stage `Dockerfile` for a Python web service that lands **under 100 MB**, runs as a non-root user, pins its base image by digest, and reuses its dependency layer on rebuild.
- **Distinguish** the runtime semantics of `CMD` vs `ENTRYPOINT`, the build-time semantics of `ARG` vs `ENV`, and the security semantics of `ADD` vs `COPY` — without looking them up.
- **Explain** BuildKit's layer-caching model: when a layer is reused, when it is invalidated, and how to order instructions so the cache works *for* you, not against you.
- **Use** `RUN --mount=type=cache` to keep package caches (`pip`, `apt`, `npm`) out of the final image without losing rebuild speed.
- **Choose** between `python:3.12-slim`, `python:3.12-alpine`, and `gcr.io/distroless/python3-debian12` for a given workload, and defend the choice with a tradeoff matrix.
- **Scan** an image with `trivy` and `grype`, read the report, distinguish a real CVE from a false-positive-shaped one, and decide which findings block the build.
- **Write** a `.dockerignore` that prevents secrets, build artifacts, and `.git/` from leaking into the build context.

---

## Prerequisites

This week assumes you have completed **Week 1 of C15** and pushed your mini-project. Specifically:

- You have Docker (or Podman) installed and have built at least one image.
- You can read the output of `docker images`, `docker history`, and `docker inspect`.
- You have run the image-shrinking challenge from Week 1 and have an instinct for what a 1 GB image costs.
- You have a Linux host or a working Docker Desktop. macOS and Windows are fine this week — there is no `unshare` in the lecture material.

If Docker is not installed, follow the official guide: <https://docs.docker.com/engine/install/>. Confirm with `docker version` and `docker buildx version`. We assume **Docker 24+** (BuildKit on by default) throughout. If you are on Docker 20.x, set `DOCKER_BUILDKIT=1` in your shell and read the migration note in `resources.md`.

---

## Topics covered

- The `Dockerfile` instruction set, in order of how often you will write each: `FROM`, `WORKDIR`, `COPY`, `RUN`, `ENV`, `ARG`, `EXPOSE`, `USER`, `HEALTHCHECK`, `ENTRYPOINT`, `CMD`. Plus the one you should almost never write: `ADD`.
- `CMD` vs `ENTRYPOINT`: the four combinations and what each one *actually* runs.
- `ENV` vs `ARG`: build-time vs runtime, and the security trap of `ARG` for secrets.
- `USER`: why running as `root` inside the container is a vulnerability one CVE away from a breakout, and the `useradd` recipe that fixes it.
- `EXPOSE` as documentation: what it does *not* do (it does not publish ports).
- `HEALTHCHECK`: the instruction every team forgets and every orchestrator wants.
- `.dockerignore`: keeping `.git/`, `.env`, `__pycache__/`, and `node_modules/` out of your build context.
- **Layer caching**: how BuildKit decides "this hasn't changed," the cache key, and the COPY-deps-first / COPY-source-second ordering rule.
- **BuildKit cache mounts**: `RUN --mount=type=cache,target=...` for `pip`, `apt`, `npm`, `cargo` caches.
- **Multi-stage builds**: build in one image, run in another. The virtualenv pattern. Named stages and `--target`.
- **Distroless images**: Google's `gcr.io/distroless/*`, what they give up (shell, package manager, `ls`), what they gain (no CVEs from packages you do not run).
- **Alpine vs Debian-slim vs distroless**: a tradeoff matrix you can defend.
- **Image scanning**: `trivy`, `grype`, and `snyk` — what each finds, what each misses, and how to wire one into CI.
- **Reproducibility**: pinning the base image by digest, pinning Python deps in a lockfile, and the `SOURCE_DATE_EPOCH` trick for deterministic timestamps.

---

## Weekly schedule

The schedule below adds up to approximately **36 hours**. Some sections click in 20 minutes; others need 3 hours. The total is what matters, not the daily split.

| Day       | Focus                                            | Lectures | Exercises | Challenges | Quiz/Read | Homework | Mini-Project | Self-Study | Daily Total |
|-----------|--------------------------------------------------|---------:|----------:|-----------:|----------:|---------:|-------------:|-----------:|------------:|
| Monday    | Anatomy of a Dockerfile (Lecture 1)              |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Tuesday   | Caching, multistage, distroless (Lecture 2)      |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Wednesday | Cache mounts + BuildKit (Exercise 2)             |    1h    |    2h     |     1h     |    0.5h   |   1h     |     1h       |    0.5h    |     7h      |
| Thursday  | Image scanning with trivy (Exercise 3)           |    1h    |    1h     |     1h     |    0.5h   |   1h     |     2h       |    0.5h    |     7h      |
| Friday    | Mini-project — containerize three ways           |    0h    |    0h     |     1h     |    0.5h   |   1h     |     3h       |    0.5h    |     6h      |
| Saturday  | Challenge — shrink to < 50 MB / project wrap     |    0h    |    0h     |     1h     |    0h     |   1h     |     1h       |    0h      |     3h      |
| Sunday    | Quiz, write the README                           |    0h    |    0h     |     0h     |    0.5h   |   0h     |     0h       |    0h      |     0.5h    |
| **Total** |                                                  | **6h**   | **7h**    | **4h**     | **3h**    | **6h**   | **7h**       | **2.5h**   | **35.5h**   |

---

## How to navigate this week

| File | What's inside |
|------|---------------|
| [README.md](./README.md) | This overview (you are here) |
| [resources.md](./resources.md) | Curated readings: official docs, distroless references, scanner docs |
| [lecture-notes/01-the-anatomy-of-a-dockerfile.md](./lecture-notes/01-the-anatomy-of-a-dockerfile.md) | Every instruction, in the order you use it |
| [lecture-notes/02-layer-caching-multistage-distroless.md](./lecture-notes/02-layer-caching-multistage-distroless.md) | Caching, multi-stage builds, distroless, scanning |
| [exercises/README.md](./exercises/README.md) | Index of hands-on drills |
| [exercises/exercise-01-three-builds-three-images.md](./exercises/exercise-01-three-builds-three-images.md) | Naive vs multi-stage vs distroless, measured |
| [exercises/exercise-02-cache-mounts.md](./exercises/exercise-02-cache-mounts.md) | BuildKit `--mount=type=cache` for pip and apt |
| [exercises/exercise-03-scan-with-trivy.md](./exercises/exercise-03-scan-with-trivy.md) | Image scanning end-to-end with `trivy` |
| [challenges/README.md](./challenges/README.md) | Index of weekly challenges |
| [challenges/challenge-01-shrink-to-under-50mb.md](./challenges/challenge-01-shrink-to-under-50mb.md) | A harder version of the Week-1 shrink, with new constraints |
| [quiz.md](./quiz.md) | 10 multiple-choice questions |
| [homework.md](./homework.md) | Six practice problems |
| [mini-project/README.md](./mini-project/README.md) | Containerize one real Python app three ways; compare on size, build time, security |

---

## Stretch goals

If you finish early and want to push further:

- Read the [BuildKit LLB documentation](https://github.com/moby/buildkit) end-to-end and run one of the example frontends. BuildKit is a graph compiler, not a script runner; once you see the graph, every weird cache miss starts to make sense.
- Build the same image with `buildah` (no daemon) and `kaniko` (no privileged build) and compare the cache behavior. Both matter when you cannot run Docker-in-Docker in CI.
- Inspect the layers of a distroless image with `dive`. Count how many of the layers are from `cacert.pem`, `tzdata`, and the Python interpreter itself.
- Generate an SBOM for your image with `syft` (`syft <image> -o spdx-json`). We use SBOMs in Week 11; getting one this week is free practice.
- Sign one of your built images with `cosign` against a keyless OIDC identity. Verify the signature. This is Week 11 material, but the tools are mature enough to play with now.

---

## Up next

Continue to [Week 3 — `docker compose` and the 12-Factor App](../week-03/) once you have pushed your Week 2 mini-project to GitHub. Week 3 is where one container becomes a *system* of containers — and where most of the confusion about Docker networking gets resolved.

---

*If you find errors in this material, please open an issue or send a PR. Future learners will thank you.*
