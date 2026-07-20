# Week 2 — Resources

Every resource on this page is **free** and **publicly accessible**. No paywalled books. If a link 404s, please open an issue.

## Required reading (work it into your week)

- **Dockerfile reference** — the canonical specification. Read sections `FROM`, `RUN`, `COPY`, `CMD`, `ENTRYPOINT`, `ARG`, `ENV`, `USER`, `HEALTHCHECK`, `.dockerignore` before Tuesday: <https://docs.docker.com/reference/dockerfile/>
- **BuildKit overview** — what the modern Docker build engine actually does: <https://docs.docker.com/build/buildkit/>
- **`RUN --mount=type=cache`** — the single most under-used feature in Docker, with examples: <https://docs.docker.com/build/cache/optimize/#use-cache-mounts>
- **Best practices for writing Dockerfiles** — Docker's own list. About 70% useful, 20% out of date, 10% wrong. Read it critically: <https://docs.docker.com/build/building/best-practices/>
- **Distroless project README** — Google's image family, what is in each base, and the maintenance policy: <https://github.com/GoogleContainerTools/distroless>
- **Trivy quickstart** — the scanner we use this week: <https://trivy.dev/latest/getting-started/>

## The specs (skim, don't memorize)

- **OCI Image Specification** — what you are building, format-wise. You met this in Week 1: <https://github.com/opencontainers/image-spec>
- **Dockerfile frontend syntax versions** — the `# syntax=docker/dockerfile:1.7` directive: <https://docs.docker.com/build/buildkit/dockerfile-frontend/>
- **BuildKit LLB** — the intermediate representation BuildKit compiles your Dockerfile to. Useful when a cache miss makes no sense: <https://github.com/moby/buildkit/blob/master/docs/dev/solver.md>

## Official tool docs

- **Docker `build` command**: <https://docs.docker.com/reference/cli/docker/buildx/build/>
- **Docker `buildx`** — the multi-builder, multi-platform CLI: <https://docs.docker.com/build/buildx/>
- **Docker scout** — Docker's own scanner; bundled in Docker Desktop: <https://docs.docker.com/scout/>
- **Trivy** — image, filesystem, repo, SBOM, IaC scanner. Apache-2.0: <https://github.com/aquasecurity/trivy>
- **Grype** — Anchore's scanner, often used together with `syft` for SBOMs. Apache-2.0: <https://github.com/anchore/grype>
- **Syft** — SBOM generator that pairs with Grype. Apache-2.0: <https://github.com/anchore/syft>
- **Dive** — interactive layer inspector. MIT: <https://github.com/wagoodman/dive>
- **Hadolint** — Dockerfile linter. GPL-3.0: <https://github.com/hadolint/hadolint>
- **Buildah** — daemonless image builder, OCI-native. Apache-2.0: <https://buildah.io/>
- **Kaniko** — builds images inside Kubernetes without a privileged daemon. Apache-2.0: <https://github.com/GoogleContainerTools/kaniko>

## Base-image references

- **`python` official image** — every variant, every tag, the Dockerfiles that build them: <https://hub.docker.com/_/python>
- **Debian `slim`** — what is and is not included in `*-slim` tags: <https://hub.docker.com/_/debian>
- **Alpine Linux** — the base, and the `musl` libc caveat: <https://hub.docker.com/_/alpine>
- **Distroless image catalog** — `static`, `base`, `cc`, `python3`, `nodejs`, `java`, debug variants: <https://github.com/GoogleContainerTools/distroless#what-images-are-available>
- **Wolfi** — a glibc, distroless-style image base from Chainguard, with daily CVE updates: <https://github.com/wolfi-dev/os>
- **Chainguard Images** — hardened, minimal images with public-good free tier: <https://images.chainguard.dev/>

## Free books and write-ups

- **"Docker Best Practices for Python Developers"** by Michael Herman — the single best free Python-Dockerfile write-up on the internet: <https://testdriven.io/blog/docker-best-practices/>
- **"How I made my Python Docker image 9x smaller"** — Itamar Turner-Trauring, opinionated and practical: <https://pythonspeed.com/articles/smaller-python-docker-images/>
- **Itamar Turner-Trauring's full container series** — read all of them, they are short: <https://pythonspeed.com/docker/>
- **"Multi-stage builds, explained slowly"** — Julia Evans zine excerpt: <https://wizardzines.com/comics/docker-multi-stage/>
- **"The 100% correct Dockerfile for Python web apps"** — opinionated, defensible: <https://sourcery.ai/blog/python-docker/>
- **Snyk's "10 Docker image security best practices"** — vendor content, but technically solid: <https://snyk.io/blog/10-docker-image-security-best-practices/>
- **"BuildKit in depth"** — Tonis Tiigi (one of the BuildKit maintainers): <https://medium.com/@tonistiigi/build-secrets-and-ssh-forwarding-in-docker-18-09-ae8161d066>

## Talks and videos (free, no signup)

- **"Distroless: minimal container images" — Matthew Moore, KubeCon** (~30 min). The talk that introduced distroless to the wider community: <https://www.youtube.com/results?search_query=distroless+matthew+moore>
- **"Tips and tricks of the Docker captains" — Bret Fisher, DockerCon** (~45 min). The single best collection of practical Dockerfile patterns: <https://www.youtube.com/results?search_query=bret+fisher+docker+tips>
- **"BuildKit: the modern Docker build engine" — Tonis Tiigi, DockerCon** (~40 min): <https://www.youtube.com/results?search_query=tonis+tiigi+buildkit>
- **"Container image scanning explained" — Liz Rice, Aqua Security** (~25 min). The mental model behind every scanner: <https://www.youtube.com/results?search_query=liz+rice+image+scanning>

## Open-source projects to read this week

You can learn more from one hour reading other people's Dockerfiles than from three hours of tutorials. Pick one and just read it:

- **`python` official Dockerfile** — `python:3.12-slim`'s source: <https://github.com/docker-library/python>
- **`postgres` official Dockerfile** — a stateful service done right: <https://github.com/docker-library/postgres>
- **`prometheus` Dockerfile** — multi-stage Go build, scratch final image: <https://github.com/prometheus/prometheus/blob/main/Dockerfile>
- **`grafana` Dockerfile** — Go + Node frontend + Alpine final stage: <https://github.com/grafana/grafana/blob/main/Dockerfile>
- **`distroless` itself** — `bazel`-built, instructive even if you do not use Bazel: <https://github.com/GoogleContainerTools/distroless>

## Tools you'll install this week

| Tool | Install | Purpose |
|------|---------|---------|
| `docker` | <https://docs.docker.com/engine/install/> | Build, run, push images |
| `docker buildx` | bundled in Docker 24+ | Multi-platform, BuildKit features |
| `dive` | `brew install dive` / [release page](https://github.com/wagoodman/dive/releases) | Inspect image layers interactively |
| `trivy` | `brew install trivy` / [install docs](https://trivy.dev/latest/getting-started/installation/) | CVE scanning |
| `grype` | `brew install grype` / `curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh \| sh -s -- -b /usr/local/bin` | Second-opinion CVE scanning |
| `syft` | `brew install syft` / similar curl-pipe-sh installer | SBOM generation |
| `hadolint` | `brew install hadolint` / [release page](https://github.com/hadolint/hadolint/releases) | Dockerfile linter |

## Glossary cheat sheet

Keep this open in a tab.

| Term | Plain English |
|------|---------------|
| **Build context** | The directory you pass to `docker build` — everything in it (minus `.dockerignore` exclusions) is sent to the daemon. |
| **Layer** | A filesystem diff produced by a `RUN`, `COPY`, or `ADD` instruction. Cached by content hash. |
| **Cache key** | The hash BuildKit computes for an instruction; if the key matches a prior build, the layer is reused. |
| **Multi-stage build** | A `Dockerfile` with more than one `FROM`; the final stage `COPY --from=` artifacts from earlier stages. |
| **Stage** | One `FROM` block. Named with `AS <name>`; targetable with `docker build --target <name>`. |
| **Distroless** | A base image with no shell, no package manager, only what the application binary needs. |
| **SBOM** | Software Bill of Materials — a machine-readable list of every component in an image. |
| **CVE** | Common Vulnerabilities and Exposures — a public ID for a known security issue. |
| **Digest** | A SHA-256 hash of an image's manifest; immutable. |
| **Tag** | A human-readable, mutable label. `latest` is a tag. |
| **`.dockerignore`** | A file that excludes paths from the build context. Like `.gitignore`, for `docker build`. |

---

*If a link 404s, please [open an issue](https://github.com/CODE-CRUNCH-CLUB) so we can replace it.*
