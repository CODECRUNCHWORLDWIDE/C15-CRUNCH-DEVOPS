# Lecture 2 — Layer Caching, Multi-stage Builds, Distroless, and Scanning

> **Outcome:** You can describe BuildKit's cache model precisely enough to predict whether a given Dockerfile change will trigger a rebuild. You can write a multi-stage Dockerfile that produces an under-50 MB image of a Python web service. You can choose between Alpine, Debian-slim, and distroless for a given workload and defend the choice. You can scan an image with `trivy`, read the report, and decide which findings block a deploy.

Lecture 1 was the instruction reference. Lecture 2 is the multipliers — the three patterns that take a 1 GB naive image down to 40 MB, plus the scanning step that prevents you from shipping CVEs into production.

We continue to assume **Docker 24+** with **BuildKit** on by default, and a Dockerfile frontend pinned to `# syntax=docker/dockerfile:1.7`.

---

## 1. The mental model: a Dockerfile is a build graph, not a script

The single biggest shift between "Dockerfiles I wrote my first month" and "Dockerfiles I would code-review" is realizing that BuildKit does *not* execute your Dockerfile top to bottom like a Bash script. It compiles your Dockerfile to a **Low-Level Build (LLB) graph**, then executes the graph — caching, parallelizing, and short-circuiting wherever it can.

In LLB:

- Each instruction is a node.
- Each node has a **cache key** computed from its inputs.
- Two builds with identical inputs produce identical cache keys; the second build reuses the prior node's output.

This is why "did I change the order of these two lines" can either be invisible (no observed effect) or cataclysmic (cache invalidated, ten minutes of rebuild). Once you see your Dockerfile as a graph, every caching surprise has a deterministic explanation.

---

## 2. How BuildKit computes a cache key

For each instruction, BuildKit hashes:

| Instruction | What contributes to the cache key |
|-------------|-----------------------------------|
| `FROM <image>` | The digest of the base image (resolved from tag at build time) |
| `RUN <command>` | The exact command string + the cache keys of all preceding instructions |
| `COPY <src> <dst>` | The digests of every file in `<src>` + path + `<dst>` + flags (`--chown`, `--chmod`) |
| `ENV`, `WORKDIR`, `USER`, `ARG`, `EXPOSE`, `CMD`, `ENTRYPOINT`, `LABEL` | The exact value, plus the cache keys of preceding instructions |

Three corollaries that drive almost every caching rule:

1. **Order matters absolutely.** If instruction *N* changes its key, instructions *N+1, N+2, …* all bust their cache, regardless of whether *they* changed. The dependency is positional.
2. **`RUN` keys do not look inside the command.** BuildKit hashes the literal `RUN apt-get update && apt-get install -y curl`. It does not know that `apt-get update` fetches different package lists today than yesterday. If you want to force-refresh, you have to bust the key yourself (`docker build --no-cache`, or change the command).
3. **`COPY` keys hash file *contents*, not timestamps.** Touching a file's mtime without changing its contents does not bust the cache. (This is BuildKit; the legacy builder hashed mtimes too, which is why upgrading to BuildKit made many people's caches "suddenly start working.")

### Watching the cache work

Run a build twice, with no change in between:

```bash
$ docker build -t demo .
[+] Building 12.4s (10/10) FINISHED
 => [1/6] FROM docker.io/library/python:3.12-slim          2.1s
 => [2/6] WORKDIR /app                                     0.1s
 => [3/6] COPY requirements.txt .                          0.0s
 => [4/6] RUN pip install -r requirements.txt              9.8s
 => [5/6] COPY app/ ./app/                                 0.1s
 => [6/6] CMD ["python", "app/main.py"]                    0.0s

$ docker build -t demo .
[+] Building 0.4s (10/10) FINISHED
 => CACHED [1/6] FROM docker.io/library/python:3.12-slim   0.0s
 => CACHED [2/6] WORKDIR /app                              0.0s
 => CACHED [3/6] COPY requirements.txt .                   0.0s
 => CACHED [4/6] RUN pip install -r requirements.txt       0.0s
 => CACHED [5/6] COPY app/ ./app/                          0.0s
 => CACHED [6/6] CMD ["python", "app/main.py"]             0.0s
```

Every step is `CACHED`. Now change `app/main.py` (touch a print statement) and rebuild:

```bash
$ docker build -t demo .
 => CACHED [1/6] FROM docker.io/library/python:3.12-slim   0.0s
 => CACHED [2/6] WORKDIR /app                              0.0s
 => CACHED [3/6] COPY requirements.txt .                   0.0s
 => CACHED [4/6] RUN pip install -r requirements.txt       0.0s
 => [5/6] COPY app/ ./app/                                 0.1s
 => [6/6] CMD ["python", "app/main.py"]                    0.0s
```

Step 5 re-ran. Steps 4 and earlier were reused. **Step 4 — the slow one — is cached.** That is the whole point of the COPY-deps-first ordering.

---

## 3. The COPY-deps-first / COPY-source-second ordering rule

The single most useful Dockerfile pattern in the world:

```dockerfile
# Change rarely
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Change often
COPY app/ ./app/
```

The dep-install layer's cache key depends on `requirements.txt` and on every preceding instruction. As long as none of those change, the slow `pip install` is `CACHED` even when you change your application code on every commit.

Invert the order:

```dockerfile
# WRONG: deps re-install on every source change
COPY . .
RUN pip install -r requirements.txt
```

Now the `COPY . .` key depends on every file in the build context. Edit one line of Python; key changes; `RUN pip install` re-runs from scratch. You just turned a 0.4-second build into a 60-second build.

The same pattern applies to every language:

| Language | "Deps file" you `COPY` first | "Source" you `COPY` later |
|----------|------------------------------|---------------------------|
| Python   | `requirements.txt` / `pyproject.toml` + `poetry.lock` | `app/`, `src/` |
| Node.js  | `package.json` + `package-lock.json` | `src/` |
| Go       | `go.mod` + `go.sum` | `cmd/`, `internal/` |
| Rust     | `Cargo.toml` + `Cargo.lock` | `src/` |
| Java     | `pom.xml` / `build.gradle` | `src/main/` |

Memorize the pattern: deps first, then build (cached); source last, then run (not cached, but cheap).

---

## 4. BuildKit cache mounts

BuildKit added a feature in 2019 that makes the "deps cache" pattern even better: `RUN --mount=type=cache`. The cache mount keeps a directory *persistent across builds* but **outside** the final image.

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
CMD ["python", "app/main.py"]
```

What happens here:

1. **First build.** `pip` downloads wheels into `/root/.cache/pip`. The cache mount is BuildKit-managed storage, *not* a layer. After the `RUN`, the cache mount is unmounted; nothing about `/root/.cache/pip` is committed to the image.
2. **Second build, even with a changed `requirements.txt`.** The `RUN` instruction's cache key changed (because the file changed), so `pip install` re-runs. But `pip` finds its wheels still in `/root/.cache/pip` from the previous build — most of the network fetch is skipped.

The double win: **smaller image** (no pip cache in any layer) *and* **faster rebuilds** when deps change.

### The four cache-mount patterns

For Python, apt, npm, and Cargo:

```dockerfile
# Python: pip
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Debian/Ubuntu: apt
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl

# Node.js: npm
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Rust: Cargo
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/app/target \
    cargo build --release
```

The `sharing=locked` on the apt mounts prevents concurrent builds from corrupting the apt lock files. Default is `shared`, which is fine for `pip` and `npm` but breaks `apt`.

### When NOT to use cache mounts

Cache mounts are local to the builder. They do not survive between machines or between CI workers, unless you configure a remote cache (a separate topic, covered in Week 4 with the CI/CD pipeline). If you are building on ephemeral CI runners *without* a remote cache, cache mounts buy you nothing.

For CI, configure BuildKit's GHA or registry-backed cache:

```bash
docker buildx build \
  --cache-from type=gha \
  --cache-to type=gha,mode=max \
  -t myapp .
```

We will set that up in Week 4. For local development, plain `--mount=type=cache` is the default win.

---

## 5. Multi-stage builds

A multi-stage build is a Dockerfile with more than one `FROM`. The non-final stages build artifacts; the final stage `COPY --from=` those artifacts and discards the rest. The build dependencies, compilers, source code, and intermediate files **never reach the final image**.

The pattern, in the abstract:

```dockerfile
# Stage 1: build
FROM python:3.12 AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Stage 2: runtime
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY app/ ./app/
CMD ["python", "app/main.py"]
```

Two `FROM` lines. The first is heavy (`python:3.12` includes build-essential, git, the entire compiler toolchain) — fine, because it does not ship. The second is `python:3.12-slim` — what actually ships. The `COPY --from=builder` line is the bridge: the installed Python packages cross from builder to runtime, and nothing else does.

### The virtualenv variant (recommended)

A cleaner pattern that avoids relying on `/root/.local`:

```dockerfile
# syntax=docker/dockerfile:1.7

# --- Build stage ---
FROM python:3.12-slim AS builder

# Build tools that we do NOT want in the runtime image
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libc6-dev \
 && rm -rf /var/lib/apt/lists/*

# Build into a virtualenv that we will copy whole
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# --- Runtime stage ---
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Copy ONLY the virtualenv from the builder
COPY --from=builder /opt/venv /opt/venv

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app
COPY --chown=app:app app/ ./app/

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz').read()" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app.main:app"]
```

This Dockerfile typically lands at ~120 MB. The single-stage version from Lecture 1 lands at ~150 MB. Where did the 30 MB go? `gcc`, `libc6-dev`, and the apt cache — all needed at build time, none needed at runtime. The builder stage held them; the runtime stage never saw them.

> **Status check — multi-stage build outcome**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  BUILD COMPARISON — same app, two Dockerfiles        │
> │                                                     │
> │  Single-stage (slim):  155 MB    build:  47 s        │
> │  Multi-stage  (slim):  118 MB    build:  52 s        │
> │  Multi-stage (distroless):  62 MB  build:  54 s      │
> │                                                     │
> │  CVE count (trivy, HIGH+CRITICAL):                  │
> │    Single-stage:        12        Multi:    8        │
> │    Distroless:           0                          │
> └─────────────────────────────────────────────────────┘
> ```

### Named stages and `--target`

```dockerfile
FROM python:3.12-slim AS builder
# ...

FROM python:3.12-slim AS runtime
# ...

FROM python:3.12 AS debug
COPY --from=runtime / /
# Debug shell baked in for local poking
```

Three named stages. `docker build --target builder .` builds only up through `builder` and stops — useful when you want to inspect intermediate artifacts. `docker build --target runtime .` is the default-style build. `docker build --target debug .` produces an image with everything `runtime` has *plus* the debug tools.

The pattern of having a `runtime` stage and a `debug` stage that builds *on top of* `runtime` is the standard answer to "we want a small production image but we also want to be able to `bash` into one when something is on fire."

### Cross-stage `COPY --from=` rules

```dockerfile
COPY --from=builder /opt/venv /opt/venv      # By stage name
COPY --from=0 /opt/venv /opt/venv            # By stage index (0-based, fragile)
COPY --from=alpine:3.20 /etc/ssl/certs /etc/ssl/  # From any image
```

Always use **named** references (`--from=builder`), never indices. Indices break the moment you reorder stages.

The "from any image" form is what makes statically-linked `FROM scratch` builds practical:

```dockerfile
FROM golang:1.22 AS builder
WORKDIR /src
COPY . .
RUN CGO_ENABLED=0 go build -o /out/server ./cmd/server

FROM scratch
COPY --from=builder /out/server /server
COPY --from=alpine:3.20 /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
ENTRYPOINT ["/server"]
```

A Go binary on `scratch` with CA certs pulled from `alpine`. The final image is ~10 MB.

---

## 6. Distroless images

"Distroless" is Google's name for a base-image family that contains **only your application's language runtime and its direct dependencies** — and nothing else. No shell. No package manager. No `ls`, no `find`, no `cat`. The image's entire surface area is "the binary, the libc, the CA certs."

```dockerfile
FROM python:3.12-slim AS builder
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM gcr.io/distroless/python3-debian12
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/opt/venv/lib/python3.12/site-packages"
COPY app/ /app/
WORKDIR /app
USER nonroot
EXPOSE 8000
ENTRYPOINT ["/opt/venv/bin/gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app.main:app"]
```

Notes on the distroless variant:

- `gcr.io/distroless/python3-debian12` ships Python 3.12 on a Debian 12 userspace, ~50 MB total.
- It has a `nonroot` user pre-defined (UID 65532). You do not need `useradd`.
- It has **no shell**. `docker exec -it <id> bash` fails. So does `sh`. To debug, see "debugging distroless" below.
- `HEALTHCHECK` based on `curl` will not work because there is no `curl`. Use a Python one-liner, or rely on the orchestrator's probes (Kubernetes, Compose) which run *outside* the container.

### The distroless image catalog

| Image | Contents | Typical size |
|-------|----------|-------------:|
| `gcr.io/distroless/static-debian12` | CA certs, tzdata, `/etc/passwd` with `nonroot` user. Nothing else. | ~2 MB |
| `gcr.io/distroless/base-debian12` | `static` + glibc + libssl + libcrypto. | ~20 MB |
| `gcr.io/distroless/cc-debian12` | `base` + libgcc + libstdc++. For C/C++ apps. | ~25 MB |
| `gcr.io/distroless/python3-debian12` | `base` + CPython 3.11/3.12. | ~50 MB |
| `gcr.io/distroless/nodejs20-debian12` | `base` + Node.js 20. | ~75 MB |
| `gcr.io/distroless/java21-debian12` | `base` + OpenJDK 21 JRE. | ~200 MB |
| Each, with `:debug` tag | The above + BusyBox shell. For development only. | +5 MB |

The `:debug` tags are how you debug distroless: build the same Dockerfile twice, once with `gcr.io/distroless/python3-debian12` for production, once with `gcr.io/distroless/python3-debian12:debug` for the rare interactive session.

### What distroless gives you

1. **CVE surface area near zero.** A typical `python:3.12-slim` ships with 30–100 known CVEs across its installed Debian packages (most low-severity, but they show up in every scan). Distroless typically scans clean.
2. **Fewer "did this just run" mysteries.** No shell means no `sh -c '...'` wrapping your entrypoint, no signal-forwarding bugs, no shell injection in your `RUN` commands at runtime.
3. **Smaller images.** Around 50 MB for Python vs 120 MB for `slim`.

### What distroless takes away

1. **No `docker exec ... sh` for debugging.** You debug by ephemeral container, by sidecar, or by switching to the `:debug` tag temporarily.
2. **Some libraries need things distroless does not ship.** Anything that shells out (`subprocess.run(["bash", "-c", ...])`) will fail. Anything that needs `git`, `ssh`, `curl` at runtime fails.
3. **You cannot `apt-get install` at runtime.** This is a *feature*, not a bug — but it does mean you have to plan installation entirely in the builder stage.

---

## 7. The Alpine vs Debian-slim vs distroless tradeoff matrix

| Axis                          | `python:3.12` | `python:3.12-slim` | `python:3.12-alpine` | `gcr.io/distroless/python3-debian12` | `python:3.12-slim` + `FROM scratch` (Go-style) |
|-------------------------------|--------------:|-------------------:|---------------------:|-------------------------------------:|------------------------------------------------:|
| Typical final image size      | ~1 GB         | ~120 MB            | ~50 MB               | ~50 MB                               | N/A (not practical for Python)                  |
| libc                          | glibc         | glibc              | musl                 | glibc                                | —                                               |
| Has a shell                   | bash, sh      | bash, sh           | ash                  | **no**                               | —                                               |
| Has a package manager         | apt           | apt                | apk                  | **no**                               | —                                               |
| All PyPI wheels available     | yes           | yes                | **partial** (musl)   | yes                                  | —                                               |
| `pip install <C-extension>` works without a compiler | yes | no — needs build tools in a builder stage | partial | no, must build in builder | — |
| Typical CVE count at scan     | 200+          | 50–80              | 5–10                 | **0–2**                              | —                                               |
| Easy to debug interactively   | yes           | yes                | yes                  | **no** (use `:debug` tag)            | no                                              |
| Best for                      | dev / one-off | most apps          | tiny apps; CPU-bound | hardened production                  | Go binaries only                                |

The rules of thumb that fall out of the matrix:

- **Use `python:3.12-slim`** for the runtime stage of most workloads. The dev experience is unchanged, the size is fine, the CVE count is acceptable, and every PyPI wheel works.
- **Use `python:3.12-alpine`** only when (a) image size really matters (edge deployment, expensive registry egress), and (b) you have verified that every wheel you depend on has a `musllinux` build. Pandas, NumPy, Pillow, and the like *do* have musl wheels now, but verify.
- **Use `gcr.io/distroless/python3-debian12`** for production workloads that have settled and where you want minimum CVE surface. You give up interactive debugging in exchange.
- **Use `FROM scratch`** only for statically-linked binaries (Go, Rust with `musl` target). Not for Python.

### The Alpine musl trap

A common, painful first encounter with Alpine:

```dockerfile
FROM python:3.12-alpine
COPY requirements.txt .
RUN pip install -r requirements.txt
```

If `requirements.txt` lists `psycopg2` or `cryptography` or any package whose maintainer ships *only* glibc wheels, `pip install` will try to *build from source*. Alpine does not have `gcc`. You see:

```
error: command 'gcc' failed: No such file or directory
ERROR: Failed building wheel for psycopg2
```

Fix: install build tools in an Alpine builder stage:

```dockerfile
FROM python:3.12-alpine AS builder
RUN apk add --no-cache build-base postgresql-dev libffi-dev openssl-dev
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.12-alpine
COPY --from=builder /root/.local /root/.local
ENV PATH="/root/.local/bin:$PATH"
```

If the build *still* fails, the wheel is fundamentally musl-incompatible and you should switch to `slim`. Some Python packages, especially older ones bundling C++ extensions, never got musl support.

---

## 8. Image scanning — what is in your image you did not put there

Every image you build sits on a base of hundreds of files from upstream packages. Some of those files have CVEs. Some of those CVEs are reachable in your app. **Scanners tell you which CVEs exist; you decide which ones matter.**

Three scanners worth knowing, all free and open-source:

| Tool | Vendor | Strength | Weakness |
|------|--------|----------|----------|
| **`trivy`** | Aqua Security | Broad coverage (OS packages + language deps + IaC + secrets); fast; the de facto default | Occasionally noisy on patched-but-not-yet-tagged CVEs |
| **`grype`** | Anchore | Often catches Python/Node deps `trivy` misses; pairs with `syft` for SBOMs | Slower, larger DB |
| **Docker Scout** | Docker Inc | Bundled in Docker Desktop; nice UI in Hub | Subscription required for full features |

For this week, install `trivy`. Optionally also install `grype` so you can sanity-check `trivy`'s findings.

### Running `trivy` against an image

```bash
$ trivy image c15-week02:latest
2026-05-13T14:02:01.234Z  INFO  Vulnerability scanning is enabled
2026-05-13T14:02:01.234Z  INFO  Secret scanning is enabled

c15-week02:latest (debian 12.5)
================================
Total: 12 (HIGH: 8, CRITICAL: 4)

┌─────────────────┬────────────────┬──────────┬──────────────────┬──────────────────┬───────────────────────────────┐
│     Library     │ Vulnerability  │ Severity │ Installed Version │ Fixed Version   │             Title             │
├─────────────────┼────────────────┼──────────┼──────────────────┼──────────────────┼───────────────────────────────┤
│ libssl3         │ CVE-2024-12345 │ CRITICAL │ 3.0.11-1~deb12u1 │ 3.0.11-1~deb12u3 │ openssl: timing side-channel  │
│ ...             │                │          │                  │                  │                               │
└─────────────────┴────────────────┴──────────┴──────────────────┴──────────────────┴───────────────────────────────┘
```

### Reading the report

Three columns matter:

- **Severity.** `CRITICAL` and `HIGH` block production; `MEDIUM` is a backlog item; `LOW` is noise.
- **Installed version** vs **fixed version.** If "fixed version" is empty, no patch exists upstream — you cannot fix it by rebuilding. If "fixed version" is populated, rebuilding with a current base usually closes it.
- **Library.** Was the vulnerable library something *you* put in the image, or was it from the base? A vulnerable `libssl3` from `python:3.12-slim` is a base-image problem; a vulnerable `flask==2.0.0` from your `requirements.txt` is your problem.

The single most effective response to a scan is: **rebuild on a fresh base image**. The Python and Debian maintainers patch most CVEs within days; pulling a fresh `python:3.12-slim` and rebuilding closes the majority of findings without code changes. This is why digest pinning + a monthly renovate bot is the operationally correct pattern: you get the *security* of pinning plus the *patches* of a regular bump.

### Filtering by severity

In CI you do not want to fail on `MEDIUM` and `LOW`. The flag:

```bash
trivy image --severity HIGH,CRITICAL --exit-code 1 c15-week02:latest
```

`--exit-code 1` makes `trivy` fail the build if any matching CVE is found.

### Suppression files

Some CVEs are unfixable, irrelevant, or accepted risks. Suppress them with `.trivyignore`:

```text
# .trivyignore
# CVE-2024-12345 — libssl timing side-channel; not reachable in our threat model.
# Owner: telsamair, expires 2026-08-01
CVE-2024-12345

# CVE-2024-23456 — only triggered by --debug flag we never set in prod.
CVE-2024-23456
```

Treat `.trivyignore` like a code change: comment every entry, name an owner, set an expiry. A suppression with no expiry is technical debt; a suppression with a 90-day expiry is risk-managed.

### `grype` as a second opinion

```bash
$ syft c15-week02:latest -o spdx-json > c15-week02.spdx.json
$ grype sbom:./c15-week02.spdx.json
```

Generate an SBOM with `syft`, then scan the SBOM with `grype`. The same image scanned by both tools usually shows a 70–90% overlap; the disagreements are interesting and worth reading. The standard practice: pick one scanner for your CI gate, run the other monthly as a sanity check.

---

## 9. Reproducibility: pinning, lockfiles, and `SOURCE_DATE_EPOCH`

A reproducible image is one where building the same Dockerfile in the same context produces *byte-identical* output. Three knobs to turn.

### Pin the base image by digest

```dockerfile
FROM python:3.12-slim@sha256:9b2d8a7c1f3e4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b
```

Without this, `python:3.12-slim` resolves to "whatever the Python maintainers pushed most recently to that tag." Two builds a week apart can produce different bases.

### Pin your application's dependencies

For Python:

```bash
pip-compile requirements.in > requirements.txt
# or
pip freeze > requirements.txt
```

`requirements.txt` should list every transitive dependency with an exact version. Better: use `uv pip compile` or `poetry export` to also pin *hashes* (`flask==3.0.3 --hash=sha256:...`). Hash-pinned deps fail the build if the upstream package was tampered with.

For Node: `package-lock.json` does this automatically (`npm ci` over `npm install`).

For Go: `go.sum` does this automatically; `go build` enforces it.

### Pin build-time timestamps with `SOURCE_DATE_EPOCH`

Even with everything else pinned, some build outputs carry timestamps. The `SOURCE_DATE_EPOCH` environment variable, honored by most build tools (and by BuildKit's `--build-arg SOURCE_DATE_EPOCH`), pins those timestamps:

```bash
docker build --build-arg SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) -t myimage .
```

This is the difference between "two byte-identical images" and "two images that differ only in `created_at` timestamps." For most teams, the latter is good enough; for software-supply-chain audits and `cosign`-signed reproducible builds (Week 11), the former matters.

---

## 10. Putting it all together: the production-grade Dockerfile

The Dockerfile we will use as the gold standard for the rest of C15:

```dockerfile
# syntax=docker/dockerfile:1.7

# ============================================================
# Build stage: heavy, throwaway, never ships
# ============================================================
FROM python:3.12-slim@sha256:9b2d8a7c1f3e4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# Build-time tools. Cached separately; never reach the final image.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev

# Build into a self-contained virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# ============================================================
# Runtime stage: tiny, hardened, what actually ships
# ============================================================
FROM gcr.io/distroless/python3-debian12:nonroot@sha256:abc123...

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/opt/venv/lib/python3.12/site-packages"

# Bring across just the virtualenv
COPY --from=builder /opt/venv /opt/venv

# Application code
WORKDIR /app
COPY app/ ./app/

# Distroless ships a `nonroot` user (UID 65532). Use it.
USER nonroot

EXPOSE 8000

# Distroless has no curl; rely on K8s/Compose probes hitting /healthz externally.
# HEALTHCHECK still useful for Compose: use a Python one-liner.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["/opt/venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz').read()"]

ENTRYPOINT ["/opt/venv/bin/gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app.main:app"]
```

This is the Dockerfile your mini-project should converge toward. Roughly 60 MB final image, 0–2 CVEs at scan, no shell to exploit, non-root, every layer ordered for cache friendliness, every external dependency pinned by digest.

---

## 11. The image-quality checklist

A working list you can paste into a PR template:

```markdown
## Dockerfile review checklist

- [ ] `# syntax=docker/dockerfile:1.7` (or later) on line 1
- [ ] Base image pinned by `@sha256:` digest
- [ ] Multi-stage; build tools never reach runtime
- [ ] `COPY requirements.txt` before `COPY app/`
- [ ] `RUN --mount=type=cache` on pip/apt/npm where applicable
- [ ] No `ADD` (except `ADD --checksum=` for verified remote files)
- [ ] No secrets in `ARG`
- [ ] Non-root `USER` set
- [ ] Pinned UID (or distroless `nonroot`)
- [ ] `HEALTHCHECK` present (or documented why omitted, e.g. distroless + K8s probes)
- [ ] `EXPOSE` documents application port
- [ ] `CMD` / `ENTRYPOINT` in exec form (JSON array)
- [ ] `.dockerignore` excludes `.git`, `.env`, `__pycache__`, `node_modules`
- [ ] `trivy image --severity HIGH,CRITICAL` passes (or every finding documented in `.trivyignore`)
- [ ] Image size under team threshold (typically < 200 MB for Python services)
```

Print this. Tape it to your monitor. Use it on every Dockerfile PR you review for the next year. After that you will have internalized it.

---

## 12. What you should be able to do now

You have read this lecture if you can, without looking back:

- Describe in two sentences how BuildKit computes a cache key.
- State the COPY-deps-first ordering rule and explain *why* it works.
- Write the `RUN --mount=type=cache,target=...` line for pip from memory.
- Write a two-stage Dockerfile that builds in `python:3.12-slim` and runs in `gcr.io/distroless/python3-debian12`.
- Explain the Alpine musl trap and how to work around it.
- Name three things distroless takes away and three things it gives.
- Write the `trivy image --severity HIGH,CRITICAL --exit-code 1` invocation for CI.
- Explain the three pinning levels (base image digest, dep lockfile, SOURCE_DATE_EPOCH) and when each matters.

If any of those feel shaky, re-read the relevant section before starting the exercises. The exercises are where this stops being abstract.

---

## 13. Up next

The exercises this week walk you through the multi-stage / cache-mount / scan triad on a real app. The mini-project takes one Python web service and builds it three different ways — naive, multi-stage, distroless — and asks you to compare on size, build time, and security. The challenge raises the bar: take a real image to under 50 MB with all of this week's tools at your disposal.

After Week 2, you will never write a single-stage Dockerfile again unless you mean to.
