# Exercise 2 — Cache Mounts

**Goal.** Take the multi-stage Dockerfile from Exercise 1 and add BuildKit cache mounts for `pip` and `apt`. Measure the rebuild speedup when dependencies change. Confirm the cache directories are not in the final image.

**Estimated time.** 90 minutes.

---

## Why we are doing this

Layer caching is great when nothing changes. But every time you add a dependency to `requirements.txt`, the `pip install` cache key is busted and the whole install re-runs. On a real app with 30+ Python packages that takes 60–90 seconds. Multiply by 20 dep-bumps a week, multiply by 10 engineers, and you are looking at *several engineer-days* of pip-install wait time per month, per team.

`RUN --mount=type=cache` solves this. The cache directory is persistent across builds but never lands in the image. Adding one package re-installs just that package; the rest are pulled from the cache.

By the end of this exercise you will have measured the speedup yourself, on your machine, and you will have the muscle memory to add the lines to every future Dockerfile.

---

## Setup

Continue from Exercise 1's directory:

```bash
cd ~/c15/week-02/ex-01-three-builds
ls
# Expect: app/  Dockerfile.v1  Dockerfile.v2  Dockerfile.v3  requirements.txt  .dockerignore
```

Confirm BuildKit is in use:

```bash
docker buildx version
# Expect: github.com/docker/buildx v0.12.x or newer
```

---

## Step 1 — Baseline: how slow is a cold cache? (~15 min)

Start by measuring how long a cold pip install takes. Reset BuildKit's cache:

```bash
docker builder prune -af
```

Build v2 (multi-stage, slim) and time the pip step specifically:

```bash
time docker build -f Dockerfile.v2 -t c15-ex02:baseline .
```

Capture the total time. Then add a new dependency to `requirements.txt` to simulate a dep bump:

```text
# requirements.txt
flask==3.0.3
gunicorn==22.0.0
requests==2.32.3
```

Rebuild and time again:

```bash
time docker build -f Dockerfile.v2 -t c15-ex02:baseline .
```

The pip step re-ran from scratch. Even though `flask` and `gunicorn` were unchanged, BuildKit had no way to know — it just sees that `requirements.txt`'s digest changed, busts the `RUN pip install` layer, and starts over. The pip cache lived inside the layer; when the layer goes, the cache goes with it.

Record both times in `notes/cache-mounts.md`:

```markdown
| Build | requirements.txt | Time (no cache mount) |
|-------|------------------|---------------------:|
| 1 (cold)        | flask, gunicorn | 45 s |
| 2 (add requests) | flask, gunicorn, requests | 47 s |
```

---

## Step 2 — Add a pip cache mount (~25 min)

Create `Dockerfile.v2-cached`:

```dockerfile
# syntax=docker/dockerfile:1.7

# --- Build stage ---
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# apt cache mount (covered in Step 3; left in for completeness)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .

# THE NEW LINE: pip cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# --- Runtime stage (unchanged from v2) ---
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

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

Note two things about the pip line:

1. `--mount=type=cache,target=/root/.cache/pip` — tells BuildKit to mount a persistent cache directory at `/root/.cache/pip` for the duration of this `RUN`.
2. `pip install --no-cache-dir` — yes, both. The mount is *external* cache; `--no-cache-dir` tells pip not to *also* keep a cache inside the image. Belt and braces.

> **Why `--no-cache-dir` *and* `--mount=type=cache`?** The mount persists across builds (good). It does not, however, prevent pip from caching wheels into the layer if your pip config is unusual. Setting `--no-cache-dir` ensures the layer is clean even when the mount is. The two flags do different things.

Reset and rebuild:

```bash
docker builder prune -af
time docker build -f Dockerfile.v2-cached -t c15-ex02:cached .
```

The first build downloads everything and populates the cache. Now simulate the dep bump again — revert `requirements.txt` to two packages, rebuild:

```text
flask==3.0.3
gunicorn==22.0.0
```

```bash
time docker build -f Dockerfile.v2-cached -t c15-ex02:cached .
```

Then re-add the dep and rebuild:

```text
flask==3.0.3
gunicorn==22.0.0
requests==2.32.3
```

```bash
time docker build -f Dockerfile.v2-cached -t c15-ex02:cached .
```

The expected pattern: the first build is the slow baseline. Removing `requests` re-runs `pip install` but pulls cached wheels for `flask` and `gunicorn`. Re-adding `requests` re-runs `pip install` but `requests` is *also* in the cache from the first build. Both rebuilds should be substantially faster than the equivalent in Step 1.

Record:

```markdown
| Build | requirements.txt | Time (with cache mount) |
|-------|------------------|------------------------:|
| 1 (cold)         | flask, gunicorn, requests | 47 s |
| 2 (remove requests) | flask, gunicorn | 9 s |
| 3 (re-add requests) | flask, gunicorn, requests | 11 s |
```

Your absolute numbers will vary. The shape — slow first build, 3–5× faster subsequent rebuilds with dep changes — should hold.

---

## Step 3 — Add an apt cache mount (~15 min)

The apt cache mount is more finicky than pip's because Debian's default behavior is to *delete* its caches on every install. The cache mount works around this; here is the recipe (already included in `Dockerfile.v2-cached`'s builder stage):

```dockerfile
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev
```

Three lines worth understanding:

1. `--mount=type=cache,target=/var/cache/apt,sharing=locked` — keeps downloaded `.deb` files between builds.
2. `--mount=type=cache,target=/var/lib/apt/lists,sharing=locked` — keeps the apt package index between builds.
3. `rm -f /etc/apt/apt.conf.d/docker-clean` — the official `python:3.12-slim` image ships with a `docker-clean` apt config that *deletes* the cache. We have to remove that file before the cache mount can do its job.
4. `sharing=locked` — apt uses lock files; concurrent builds with `sharing=shared` (the default) corrupt them. `locked` serializes apt operations across concurrent builds.

You normally do not need to add many `apt-get install` steps in a Python Dockerfile, so the apt cache win is smaller than pip's. The first build downloads `gcc` and `libc6-dev` (about 50 MB); subsequent builds where you add or remove an apt package reuse that cache.

To test: add `git` to your apt install line, rebuild, and observe:

```dockerfile
apt-get install -y --no-install-recommends gcc libc6-dev git
```

The build re-runs the apt step (cache key changed) but pulls `gcc` and `libc6-dev` from the cache mount — only `git` (and its deps) is freshly downloaded.

---

## Step 4 — Confirm the cache is NOT in the image (~10 min)

The whole point of `--mount=type=cache` is that the cache directory is mounted *during* the `RUN` and unmounted *after*. The cache contents should not appear in any layer.

Verify with `dive` (if installed) or with `docker history`:

```bash
docker history c15-ex02:cached --no-trunc --format '{{.Size}}  {{.CreatedBy}}' | head -20
```

Look for the `pip install` layer. The layer size should be small (just the bytes Pip wrote into `/opt/venv` plus its metadata — typically 30–40 MB for a flask+gunicorn install), not the multi-hundred-MB size you would expect if the pip cache (downloaded wheels + per-package metadata) were committed.

You can also exec into the image and look:

```bash
docker run --rm -it --entrypoint /bin/sh c15-ex02:cached -c 'ls /root/.cache 2>&1 || echo "no cache dir"'
# Expect: "no cache dir" or an empty directory
```

If `/root/.cache/pip` does not exist or is empty, the mount worked correctly.

---

## Step 5 — Bonus: a `npm` cache mount (~10 min, optional)

If your team uses Node.js, the same pattern applies. Drop this into `notes/cache-mounts.md` as a reference snippet, even if you do not have a Node project to test on:

```dockerfile
# syntax=docker/dockerfile:1.7
FROM node:20-slim AS builder

WORKDIR /build
COPY package.json package-lock.json ./

RUN --mount=type=cache,target=/root/.npm \
    npm ci --omit=dev

# ... rest of build
```

`npm ci` is the production-correct invocation (faster than `npm install`, fails on lockfile drift). The cache mount keeps `npm`'s wheel-equivalent (`~/.npm/_cacache`) around between builds.

For comparison with pip's pattern, write down in your notes:

| Manager | Mount path                  | Strict-install command |
|---------|-----------------------------|------------------------|
| pip     | `/root/.cache/pip`          | `pip install --no-cache-dir -r requirements.txt` |
| apt     | `/var/cache/apt` + `/var/lib/apt/lists` | `apt-get install -y --no-install-recommends ...` |
| npm     | `/root/.npm`                | `npm ci --omit=dev` |
| cargo   | `/usr/local/cargo/registry` + `/app/target` | `cargo build --release` |
| go      | `/root/.cache/go-build` + `/go/pkg/mod` | `go build` |

---

## Acceptance criteria

You can mark this exercise done when:

- [ ] `Dockerfile.v2-cached` exists with both pip and apt cache mounts.
- [ ] You have a `notes/cache-mounts.md` with two filled-in tables: one for the no-mount baseline (Step 1) and one for the with-mount runs (Step 2).
- [ ] The with-mount rebuild times for adding/removing a single dep are clearly faster than the without-mount equivalents.
- [ ] `docker history` shows the `pip install` layer is small (no wheel cache committed).
- [ ] You have a snippet for at least one non-Python ecosystem (`npm`, `cargo`, or `go`) in your notes.

---

## Common pitfalls

- **No measurable speedup.** Either (a) BuildKit is not active (run `docker buildx version` to confirm) or (b) you forgot the `# syntax=docker/dockerfile:1.7` line and BuildKit is parsing your file with an older frontend that ignores `--mount`.
- **apt cache mount silently does nothing.** You did not remove `/etc/apt/apt.conf.d/docker-clean`. The official slim images explicitly delete apt cache after install; you have to disable that.
- **`pip install` still slow on every build.** Your `COPY` order is wrong — `COPY app/` is before `COPY requirements.txt`, so any source change busts the cache before pip even runs. Re-read Lecture 2 Section 3.
- **"Cache mount" appears in the layer.** Use `dive` to inspect; the cache mount's target directory should not appear under `/`. If it does, you are looking at the wrong directory (the mount is `/root/.cache/pip`, not `/var/cache/pip`).

---

## What good looks like

A done version of this exercise has:

- Two Dockerfiles: `Dockerfile.v2` (no cache mounts, kept as the baseline) and `Dockerfile.v2-cached` (cache mounts added).
- A `notes/cache-mounts.md` with measured timings showing the speedup.
- A reference table of cache-mount paths for at least three package managers.

A bonus version has a `Dockerfile.v3-cached` — the distroless variant — with cache mounts in its builder stage. The runtime stage is unchanged (distroless does not run any cache-able commands).

---

## Why this matters

Cache mounts are the *single highest-impact, lowest-effort optimization* you will encounter this week. Four lines of Dockerfile, 3–5× faster rebuilds during dependency changes, no impact on final image size. The engineer who knows the recipe is permanently more useful than the one who does not.

You will use this pattern on every Dockerfile you write for the next decade. Today is the day it becomes muscle memory.
