# Lecture 1 — The Anatomy of a Dockerfile

> **Outcome:** You can read any production `Dockerfile`, name every instruction, explain what each one does at build time vs runtime, and identify the three or four things that are wrong with it. You can write a small but correct `Dockerfile` for a Python web service that runs as a non-root user, declares a health check, and does not leak the build context.

A `Dockerfile` is a build script. It is also a contract. It says: *given this base image and this build context, produce an OCI image whose config blob says X, whose layers contain Y, and whose entrypoint runs Z.* The instructions are not magic — every one of them maps to a deterministic mutation of either the in-progress image's layers, or its config blob, or both. This lecture walks through every instruction you will write in the next 12 weeks, in roughly the order you will write them in a real `Dockerfile`.

We use **Docker 24+** with BuildKit on by default (it has been the default since Docker 23.0, January 2023). Anything BuildKit-specific is marked. The Dockerfile frontend syntax we use throughout is `# syntax=docker/dockerfile:1.7`, which is the recommended modern frontend as of 2026.

---

## 1. The shortest correct `Dockerfile`

Before any of the instructions, here is the smallest `Dockerfile` that actually does something useful:

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim
WORKDIR /app
COPY app.py .
CMD ["python", "app.py"]
```

Four lines. It will build. It will run. It is also wrong in about six different ways, every one of which we will fix over the next 400 lines. But it is the right starting point: every instruction you add from here is an *explicit choice* to make the image smaller, more reproducible, more secure, or more readable.

The opening `# syntax=` directive is not a comment Docker ignores. It tells BuildKit which Dockerfile-frontend version to pull and use. Pin it. Without the pin you get whatever the daemon's built-in frontend is, which may be older than the features you use.

---

## 2. `FROM` — the base image

```dockerfile
FROM python:3.12-slim
```

Every `Dockerfile` starts with `FROM`. (Almost. A `Dockerfile` may start with `ARG` to parameterize the `FROM` line, and `# syntax=` is technically before everything. But `FROM` is the first *real* instruction.) `FROM` declares the base image — the starting layer set on top of which your image will be built.

### Tags vs digests

Three ways to refer to a base image, in increasing order of reproducibility:

```dockerfile
FROM python                                     # No tag → defaults to "latest". Avoid.
FROM python:3.12-slim                           # Tag. Stable enough for development.
FROM python:3.12-slim@sha256:9b2d8a7c...        # Digest. The only fully reproducible form.
```

`python:3.12-slim` is a **tag**. Tags are mutable: the image the Python maintainers point `3.12-slim` at today will be different from the one they point it at next month (they rebuild for security patches). For a development image, that mutability is helpful — you get patched glibc for free. For a production deployment manifest, that mutability is a **supply-chain bug waiting to happen**. Pin by digest:

```bash
docker pull python:3.12-slim
docker inspect python:3.12-slim --format '{{index .RepoDigests 0}}'
# python@sha256:9b2d8a7c...
```

Copy that digest into your `Dockerfile`. Re-do this dance once a month and you have a reproducible, auditable base.

> **Status check — base image pinning**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  BASE IMAGE PIN STATUS — crunchwriter-api           │
> │                                                     │
> │  Pin form:  digest        Drift since pin: 28 days  │
> │  Last bump: 2026-04-15    Bumped by:       renovate │
> │  CVE delta: -3 critical   CI:               passing │
> └─────────────────────────────────────────────────────┘
> ```

### Choosing a base

We will cover this exhaustively in Lecture 2's Alpine-vs-slim-vs-distroless section. For now, the one rule: **start with `python:3.12-slim`** unless you have a measured reason to do otherwise.

### `FROM scratch`

`FROM scratch` means "start with no layers." This is what you build a statically linked Go binary on top of. The resulting image is just your binary plus its CA certs. A typical Go-on-scratch image is 5–15 MB. Python on `scratch` is not practical because Python wants a libc, a filesystem, and an interpreter; you can do it, but you will reinvent the standard image plumbing badly.

### Multi-platform `FROM`

```dockerfile
FROM --platform=$BUILDPLATFORM python:3.12-slim AS builder
```

The `--platform=` flag is for cross-compilation: build *on* `amd64`, produce an image that runs *on* `arm64`. We touch this in Week 4 when we wire up CI; this week, leave it off.

---

## 3. `WORKDIR` — the directory every following instruction runs in

```dockerfile
WORKDIR /app
```

`WORKDIR` sets the working directory for every subsequent `RUN`, `COPY`, `ADD`, `ENTRYPOINT`, and `CMD`. If the directory does not exist, it is created. Use it instead of `RUN mkdir /app && cd /app`, which does not actually do what it looks like (each `RUN` is a fresh shell; the `cd` is forgotten in the next instruction).

Two non-obvious points:

1. **Use absolute paths.** `WORKDIR app` works the first time but compounds across multiple `WORKDIR` calls (`WORKDIR /a` then `WORKDIR b` lands you in `/a/b`). Always anchor with a leading `/`.
2. **Conventional `WORKDIR` is `/app`.** Not `/srv`, not `/usr/src/app`, not `/home/whatever`. The community standard for application code in a container is `/app`. It is just a convention, but conventions in operations have value.

---

## 4. `COPY` — bring files in from the build context

```dockerfile
COPY requirements.txt .
COPY app/ ./app/
```

`COPY <src> <dst>` copies files from the **build context** (the directory you passed to `docker build`) into the image. Two source-path rules:

- Relative paths are resolved against the build context root.
- The trailing `/` on the destination matters: `COPY foo bar` copies `foo` to a file named `bar`; `COPY foo bar/` copies `foo` *into* the `bar/` directory.

`COPY` is the simplest instruction in the file and the one most often used wrong. The dominant mistake:

```dockerfile
# WRONG: invalidates the dep-install cache on every source change
COPY . .
RUN pip install -r requirements.txt
```

Versus:

```dockerfile
# RIGHT: deps cached separately from source
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ ./app/
```

We will hammer this in Lecture 2 under "layer caching." For now, internalize: **anything that changes rarely goes earlier; anything that changes often goes later.**

### `COPY --chown` and `COPY --chmod`

```dockerfile
COPY --chown=appuser:appuser --chmod=755 entrypoint.sh /usr/local/bin/
```

Avoid the `RUN chown -R ...` antipattern. Every `RUN chown` on a copied tree creates a *second* layer with the same files with different ownership, which doubles the image size for that path. `COPY --chown` and `--chmod` do it in the layer that already exists.

### `COPY --from=<stage>` and `COPY --from=<image>`

```dockerfile
COPY --from=builder /opt/venv /opt/venv          # From an earlier stage
COPY --from=alpine:3.20 /etc/ssl/certs /etc/ssl/ # From any image
```

This is the foundation of multi-stage builds (Lecture 2). For now, just know that `COPY` can pull from *any* image, not only the current build.

---

## 5. `ADD` — almost always the wrong answer

```dockerfile
ADD https://example.com/big.tar.gz /app/         # Don't.
ADD source.tar.gz /app/                          # Don't.
ADD source.zip /app/                             # Doesn't even auto-extract zips. Don't.
```

`ADD` does what `COPY` does, plus two "convenience" features:

1. **It can fetch URLs.** This means your image build now depends on a remote server being up, on the file's checksum being whatever the server returned at the moment of build, and on you remembering to check the checksum. None of that is reproducible.
2. **It auto-extracts local tarballs.** `ADD source.tar.gz /app/` will untar `source.tar.gz` *if* it is a recognized format (gzip, bzip2, xz, lzma — but **not** zip), into `/app/`. This is a footgun: change the source from `.tar.gz` to `.zip` and the same instruction silently does a literal copy instead of an extract.

The rule is simple, and every style guide agrees:

> **Use `COPY` for local files. Use `RUN curl + verify checksum + tar` for remote files. Do not use `ADD` at all unless you are intentionally trying to use one of its two magic behaviors and have a comment saying so.**

The Hadolint linter (DL3020) flags `ADD` by default. Leave that lint on.

The one defensible exception: pulling a remote artifact with `ADD <url>` *if* you immediately verify its checksum in a `RUN` step. Even then, BuildKit's `ADD --checksum=sha256:...` (added 2023) is the safer form:

```dockerfile
ADD --checksum=sha256:abc123... https://example.com/file.tar.gz /tmp/
```

That fails the build if the checksum changes. Better. Still rare.

---

## 6. `RUN` — execute a command at build time

```dockerfile
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
```

`RUN` runs a command and commits the resulting filesystem state as a new layer. Two execution forms:

```dockerfile
RUN apt-get install -y curl       # Shell form: runs via /bin/sh -c "..."
RUN ["apt-get", "install", "-y", "curl"]  # Exec form: argv, no shell
```

Exec form is required if the base image has no shell (distroless). For ordinary `RUN`s in a Debian-based image, shell form is more readable and supports `&&`, `||`, `\`, redirection — the things you want from a shell.

### The "one RUN, one logical step" rule

```dockerfile
# WRONG: three layers, two of which still contain garbage
RUN apt-get update
RUN apt-get install -y curl
RUN rm -rf /var/lib/apt/lists/*

# RIGHT: one layer; garbage is never in any layer that ships
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*
```

Each `RUN` produces a layer. A separate `rm` in a later `RUN` cannot remove files from an *earlier* layer — those files are still in the image, just hidden by overlay-mount semantics. The fix is to do everything in one `RUN` so the "garbage" never makes it into a layer at all.

Trade-off: a giant single-`RUN` chain is harder to read and harder to debug (one of the commands failed; which one?). Break by *logical* steps, not by *individual* commands:

```dockerfile
# Apt-installed system packages: one RUN
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Python deps: another RUN
RUN pip install --no-cache-dir -r requirements.txt

# Build the asset bundle: a third
RUN npm run build
```

Three layers, each one logically coherent.

### `RUN --mount` (BuildKit)

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt
```

`--mount=type=cache` keeps the cache directory *out* of the final image but persists it across builds. We cover this in depth in Lecture 2.

---

## 7. `ENV` and `ARG` — variables

The two variable-setting instructions are constantly confused. Get the distinction right once and you will never confuse them again.

| Instruction | When set | Where visible | In final image? |
|-------------|----------|---------------|-----------------|
| `ARG`       | Build time only | Only in the `Dockerfile` itself (and on the `docker build --build-arg` flag) | **No** — not recorded in the image config |
| `ENV`       | Build time and forward | In the `Dockerfile`, every subsequent `RUN`, and in the *running container* | **Yes** — written into the image config blob |

```dockerfile
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on
```

### `ARG` and the secrets trap

A common, **wrong** pattern:

```dockerfile
ARG GITHUB_TOKEN
RUN git clone https://${GITHUB_TOKEN}@github.com/me/private.git
```

You pass `--build-arg GITHUB_TOKEN=...` to `docker build`. The build succeeds. You ship the image. Six months later someone runs `docker history --no-trunc <image>` and reads your token from the build history.

`ARG` is **not a secret-passing mechanism**. The value lands in `docker history`. Use BuildKit's `--secret` flag instead:

```dockerfile
RUN --mount=type=secret,id=github_token \
    git clone https://$(cat /run/secrets/github_token)@github.com/me/private.git
```

Build with:

```bash
docker build --secret id=github_token,src=$HOME/.gh-token .
```

The secret is mounted to a tmpfs during that one `RUN` and never appears in any layer or in the history. We cover this fully in Week 11 (Security); for this week, the rule is **never put a secret in `ARG`**.

### `ENV` and the runtime contract

```dockerfile
ENV PORT=8000
ENV LOG_LEVEL=info
```

`ENV` writes into the image config and becomes the default environment in the running container. The application reads `os.environ["PORT"]`, the operator overrides it with `docker run -e PORT=9000`, and the contract is explicit. Twelve-factor apps (Week 3) live and die by this.

The four `ENV` lines almost every Python image should have:

```dockerfile
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on
```

- `PYTHONDONTWRITEBYTECODE=1` stops Python from writing `.pyc` files into your image.
- `PYTHONUNBUFFERED=1` flushes stdout/stderr line by line, so `docker logs` shows them in real time.
- `PIP_NO_CACHE_DIR=on` keeps `pip`'s cache out of the layer.
- `PIP_DISABLE_PIP_VERSION_CHECK=on` saves a network call on every `pip` invocation.

---

## 8. `USER` — run as non-root, always

```dockerfile
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER app
```

Containers run as `root` by default. Inside the container, that "root" is constrained by capabilities and namespaces — but it is still root, and a single kernel CVE turns "root inside a container" into "root on the host." The defense is to not be root in the first place.

The official `python:3.12-slim` image runs as root. So does `node`, `nginx` (debatable — the master is root, the workers are not), `redis`, `postgres`, and most other officials. **You are expected to add a `USER` line.** It is not done for you.

### The `useradd` recipe

```dockerfile
RUN useradd --system \
            --uid 10001 \
            --no-create-home \
            --shell /usr/sbin/nologin \
            app
USER app
```

- `--system` makes a system user (UID < 1000 on Debian by default; we override with `--uid` to pin it).
- `--uid 10001` pins the UID. Pinning matters because Kubernetes' `runAsUser` and OpenShift's SCC checks reference the UID, not the name.
- `--no-create-home` skips `/home/app`. Your application has `WORKDIR /app`; it does not need a home.
- `--shell /usr/sbin/nologin` denies interactive shell. If an attacker manages to drop you to this user, they cannot `bash`.

Once you set `USER app`, every subsequent `RUN`, `CMD`, and `ENTRYPOINT` runs as `app`. If you need to install something as root *after* the `USER` line, use `USER root` to switch back. Most well-organized `Dockerfile`s have a single `USER app` line near the bottom, after all installation is done.

### Filesystem ownership

A common mistake:

```dockerfile
COPY app/ /app/
USER app
CMD ["python", "/app/main.py"]    # Fails: /app/ owned by root, app cannot import
```

Fix with `--chown` on the `COPY`:

```dockerfile
COPY --chown=app:app app/ /app/
USER app
CMD ["python", "/app/main.py"]
```

Or, if `app` has UID `10001`:

```dockerfile
COPY --chown=10001:10001 app/ /app/
```

The UID form is more portable — it works even on bases that do not have the `app` user pre-created.

### Privileged ports

Ports below 1024 require `CAP_NET_BIND_SERVICE`. By default a non-root container does not have it (it has the kernel-level capability dropped). Two fixes:

1. **Don't bind low ports.** Bind to 8000, 8080, 3000 — whatever your app likes. The orchestrator (Compose, K8s) maps host port 80 → container 8000.
2. **Grant `cap_net_bind_service` on the binary**, if you really must bind 80:

   ```dockerfile
   RUN setcap 'cap_net_bind_service=+ep' /usr/local/bin/python3.12
   ```

(1) is the standard approach. (2) is for the rare cases where you cannot indirect through a load balancer.

---

## 9. `EXPOSE` — documentation, not configuration

```dockerfile
EXPOSE 8000
```

`EXPOSE` is the most misunderstood instruction in the spec. **It does not publish a port.** It does not open a firewall. It does not make a port reachable from the host. All it does is:

1. Write the port number into the image's config blob, where `docker inspect` and `docker port` will show it.
2. Make `docker run -P` (capital P) map all `EXPOSE`d ports to random host ports.

To actually publish a port at runtime you write `docker run -p 8000:8000`, regardless of whether `EXPOSE 8000` is in the `Dockerfile`. So why use it at all? **Documentation.** When a colleague does `docker inspect`, they see at a glance what ports the application expects to bind. Convention over command-line spelunking.

One line, one port, near the bottom of the file. Use it.

---

## 10. `HEALTHCHECK` — the instruction every team forgets

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1
```

`HEALTHCHECK` declares a command Docker (or your orchestrator) runs periodically to determine whether the container is *actually* healthy, not just *running*. Without a `HEALTHCHECK`, Docker only knows whether the PID-1 process is alive — which says nothing about whether the application is responding to requests.

### The four flags you will use

- `--interval=30s` — how often to run the check. Default 30 s. For a fast-start service, 5–10 s is reasonable; for a slow Java service, 60 s.
- `--timeout=3s` — how long a single check is allowed to take. If your health endpoint can take 3 s under load, you have a different problem.
- `--start-period=10s` — grace period at startup during which failures do not count against the container's "unhealthy" status. Default 0. Always set it.
- `--retries=3` — how many consecutive failures before the container is marked unhealthy. Default 3.

### The check command

```dockerfile
HEALTHCHECK CMD curl -fsS http://localhost:8000/healthz || exit 1
```

- `-f` (`--fail`) makes `curl` exit non-zero on HTTP 4xx/5xx (without it, `curl` exits 0 on any response).
- `-sS` is "silent except errors."
- `|| exit 1` is belt-and-braces — `curl -f` already exits non-zero, but explicit is fine.

Distroless images do not have `curl`. The alternative is a tiny Go binary, a Python one-liner, or a status check baked into the application itself. We solve this for distroless in Lecture 2.

### Orchestrator interaction

- **Docker / Compose** honor `HEALTHCHECK` and gate `depends_on: condition: service_healthy` (Week 3) on it.
- **Kubernetes** does **not** read `HEALTHCHECK`. K8s uses its own `livenessProbe`, `readinessProbe`, and `startupProbe`. Setting `HEALTHCHECK` in the `Dockerfile` does no harm in K8s but does no good either. The recommended pattern: define a `/healthz` endpoint in the app; reference it from `HEALTHCHECK` for local Compose, and from `readinessProbe` for K8s. Same endpoint, two consumers.

---

## 11. `CMD` vs `ENTRYPOINT` — the four combinations

The single most-confused topic in Docker. The two instructions interact, and the interaction defines what your container actually runs.

Three forms each, two instructions, two execution modes. Here is the truth table you should memorize:

| `ENTRYPOINT` | `CMD` | What runs |
|--------------|-------|-----------|
| not set | `CMD ["python", "app.py"]` | `python app.py` |
| `ENTRYPOINT ["python"]` | not set | `python` (no args) |
| `ENTRYPOINT ["python"]` | `CMD ["app.py"]` | `python app.py` (CMD becomes args) |
| `ENTRYPOINT ["python", "app.py"]` | `CMD ["--debug"]` | `python app.py --debug` |
| `ENTRYPOINT python` (shell form) | (anything) | `/bin/sh -c "python"` — CMD ignored |

### The two forms

```dockerfile
CMD ["python", "app.py"]      # Exec form (preferred): JSON array, no shell
CMD python app.py             # Shell form: runs via /bin/sh -c "python app.py"
```

**Always use exec form** unless you specifically need shell substitution. Shell form wraps your command in `sh -c`, which means:

1. Your application is PID 2, not PID 1. The shell is PID 1.
2. Signals (`SIGTERM` from `docker stop`) go to the shell, not to your app. The shell does not forward them. Your app gets `SIGKILL`ed after a 10-second grace period instead of cleanly shutting down.

That second point is the source of approximately half of "my container takes 10 seconds to stop" tickets.

### When to use each

- **`CMD` only.** Most applications. `docker run myimage` invokes your default command. `docker run myimage some-other-cmd` overrides it. Simple. Use this 80% of the time.
- **`ENTRYPOINT` only.** When the image is fundamentally a wrapper around one binary, and arguments come from the run command. The `python` official image does this:
  ```dockerfile
  ENTRYPOINT ["python3"]
  ```
  Then `docker run python:3.12 -c 'print(2+2)'` runs `python3 -c 'print(2+2)'`.
- **`ENTRYPOINT` + `CMD`.** When you want a default command-line that the caller can override the *arguments* to but not the binary. Common pattern for CLI tools:
  ```dockerfile
  ENTRYPOINT ["/usr/local/bin/myapp"]
  CMD ["--help"]
  ```
  Then `docker run myimage` shows help; `docker run myimage serve --port 8080` runs `myapp serve --port 8080`.

### The "exec dumb-init" pattern

If you have a shell script as your entrypoint and that script needs to forward signals properly:

```dockerfile
ENTRYPOINT ["dumb-init", "--"]
CMD ["python", "app.py"]
```

`dumb-init` (or `tini`) is a tiny PID-1 init that forwards signals and reaps zombies. We will not need this until Week 3 when long-running multi-process containers come up; for now, `CMD ["python", ...]` is fine.

---

## 12. `.dockerignore` — the often-forgotten essential

`.dockerignore` is not an instruction in the `Dockerfile`. It is a separate file, in the build-context root, that lists paths to exclude before the build context is sent to the Docker daemon.

```text
# .dockerignore
.git
.gitignore
.venv
__pycache__
*.pyc
*.pyo
.env
.env.*
node_modules
dist
build
.idea
.vscode
.DS_Store
Dockerfile*
.dockerignore
README.md
docs/
tests/
.pytest_cache
.mypy_cache
.ruff_cache
.coverage
htmlcov/
```

Three reasons it matters:

1. **Speed.** Without `.dockerignore`, every `docker build` sends the *entire* directory tree to the daemon over a Unix socket. With a 500 MB `node_modules/` or a 2 GB `.git/`, that is seconds you wait on every build.
2. **Cache invalidation.** Any `COPY . .` invalidates the cache when *any* file in the context changes. Without `.dockerignore`, editing your `README.md` busts your `pip install` cache. With `.dockerignore`, `README.md` is excluded; the cache holds.
3. **Secret leakage.** This is the big one. The classic incident:
   ```
   $ docker build -t myapp .
   $ docker run myapp cat /app/.env
   POSTGRES_PASSWORD=hunter2
   AWS_ACCESS_KEY_ID=AKIA...
   ```
   You have a `.env` file in your repo (you should not, but everyone has done it). You wrote `COPY . .` in your `Dockerfile`. You just shipped the credentials. `.dockerignore` is the line of defense.

### Glob syntax

`.dockerignore` uses Go's `filepath.Match` syntax (Docker's spec, not the same as `.gitignore`'s):

- `*.pyc` — match any `.pyc` in the build-context root.
- `**/*.pyc` — match any `.pyc` recursively.
- `!important.pyc` — re-include `important.pyc` even if `*.pyc` excluded it.
- `secrets/` — exclude the entire `secrets/` directory.

Always include at least: `.git`, `.env`, `.env.*`, `__pycache__`, `node_modules`, `*.pyc`, `.venv`, `.DS_Store`, `Dockerfile*`, and your IDE config dirs.

> **Status check — build context hygiene**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  BUILD CONTEXT — pre-commit verification            │
> │                                                     │
> │  Context size: 4.2 MB     .dockerignore: present    │
> │  .env files:   0 leaked   .git/:        excluded    │
> │  node_modules: excluded   build cache:  cold        │
> └─────────────────────────────────────────────────────┘
> ```

---

## 13. A complete, defensible `Dockerfile`

Putting it together. This is the `Dockerfile` for a tiny Flask service — single-stage, but every instruction is deliberate.

```dockerfile
# syntax=docker/dockerfile:1.7

# --- Base ---
FROM python:3.12-slim@sha256:9b2d8a7c1f3e4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b

# --- Environment ---
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PORT=8000

# --- System packages: install ca-certs only, clean up in the same RUN ---
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# --- Application user: non-root, no shell, pinned UID ---
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

# --- Application deps: cached separately from source ---
WORKDIR /app
COPY --chown=app:app requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Application source: copied last so it does not bust the deps layer ---
COPY --chown=app:app app/ ./app/

# --- Runtime configuration ---
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:${PORT}/healthz || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app.main:app"]
```

Let us walk through the choices line by line, because this is what a code review looks like:

| Line | Why it is where it is |
|------|----------------------|
| `# syntax=docker/dockerfile:1.7` | Pin BuildKit frontend. Get the modern features (`--mount=type=cache`, `--mount=type=secret`, `COPY --chmod`). |
| `FROM python:3.12-slim@sha256:...` | Pin by digest. Tag is a hint; digest is the contract. |
| `ENV` block | Four Python env vars that every Python image should set. Combined into one `ENV` so it is one layer. |
| `RUN apt-get ... rm -rf /var/lib/apt/lists/*` | One `RUN`, install + cleanup, so the apt cache never makes it into a layer. |
| `RUN useradd ...` | Non-root user, pinned UID. Before installing deps so the user exists for the `--chown` flags later. |
| `WORKDIR /app` | Conventional. Absolute path. |
| `COPY requirements.txt .` *then* `RUN pip install` *then* `COPY app/ ./app/` | The cache rule. Changes to `app/` source code do not invalidate the dep-install layer. |
| `USER app` | Switch to non-root after all root-required installation is done. |
| `EXPOSE 8000` | Documentation. The orchestrator publishes; this just tells the reader what to publish. |
| `HEALTHCHECK` | Compose can gate `depends_on` on it. K8s ignores it but the app has a `/healthz` endpoint anyway. |
| `CMD ["gunicorn", ...]` | Exec form (not shell). Gunicorn is PID 1 and receives `SIGTERM` directly. |

This is still a single-stage build. In Lecture 2 we will convert it to multi-stage, drop another 30 MB, and harden it against the build-tools-in-runtime problem.

---

## 14. The instructions we did not cover

For completeness, four more `Dockerfile` instructions exist but are rare in modern usage:

- **`LABEL`** — write metadata key/value pairs into the image config. Used for OCI annotations (`org.opencontainers.image.source=...`). Good practice; we will add labels in Week 4's CI pipeline so each image knows the commit SHA it came from.
- **`VOLUME`** — declare a path as a volume. Mostly useful for stateful services (database directories) where you want to prevent accidental layer-baking of mutable data. Rare for stateless web apps.
- **`STOPSIGNAL`** — override the signal sent on `docker stop` (default `SIGTERM`). Set if your app prefers `SIGINT` or `SIGQUIT`. Almost never needed.
- **`SHELL`** — change the shell used by shell-form `RUN`. Useful when building on Windows containers (PowerShell). Almost never useful on Linux.

The deprecated ones we do *not* cover:

- **`MAINTAINER`** — replaced by `LABEL maintainer=...` in 2017. Hadolint flags it (DL4000).
- **`ONBUILD`** — a trigger that fires on a downstream build. Mostly a footgun; not seen in modern `Dockerfile`s.

---

## 15. What you should be able to do now

You have read this lecture if you can, without looking back:

- List the instructions in the order they typically appear in a `Dockerfile`.
- State the difference between `CMD` and `ENTRYPOINT` in one sentence each.
- State why `ADD` is dangerous and what to use instead.
- Name three things `EXPOSE` does *not* do.
- Write the four-flag `HEALTHCHECK` line from memory.
- Write the `useradd` line for a non-root system user with a pinned UID.
- Explain why `COPY requirements.txt . && RUN pip install` *before* `COPY . .` is the standard ordering.
- Write a `.dockerignore` that excludes `.git`, `.env`, `node_modules`, and Python caches.

If any of those feel shaky, re-read the relevant section before Lecture 2. Lecture 2 builds on every one of them.

---

## 16. One last thing — read other people's `Dockerfile`s

The fastest way to internalize this material is to read production `Dockerfile`s and ask "why is this here?" Three good ones to start with, all linked in `resources.md`:

- **`python:3.12-slim`** — the Dockerfile that builds the base image you use every day. About 30 lines. Read it; it is plain Bash, plain `apt-get`.
- **`prometheus`** — Go service, multi-stage with `scratch` final image. Read for the "I shipped a 50 MB image of a real production service" pattern.
- **`grafana`** — Go + Node + Alpine. Read for "what does a real multi-language multi-stage build look like?"

You will see every instruction in this lecture used in context, plus a few oddities (`STOPSIGNAL SIGUSR1`, `VOLUME ["/var/lib/grafana"]`) that are now no longer mysterious.

Tuesday's lecture: how Docker decides "this hasn't changed," how multi-stage actually works under the hood, how to live without a shell (distroless), and how to scan what you ship.
