# Exercise 1 — Three Builds, Three Images

**Goal.** Build the same Flask application three different ways — naive single-stage, multi-stage with `python:3.12-slim`, and multi-stage with `gcr.io/distroless/python3-debian12`. Measure each on image size, build time (cold and warm), CVE count, and runtime smoke test. Produce a side-by-side comparison table you would defend in a code review.

**Estimated time.** 120 minutes (90 minutes of building + 30 minutes of writing up the comparison).

---

## Why we are doing this

Reading about a 1 GB image is one thing. Watching one *that you built yourself* drop to 60 MB after two specific changes is another. By the end of this exercise you will have the numbers in muscle memory: "a `python:3.12` naive build is around 1 GB; `python:3.12-slim` single-stage is around 150 MB; distroless multi-stage is around 60 MB; the build-time delta between cold and warm cache is roughly 20× on a real pip install."

This is also the warm-up for the mini-project. The mini-project asks you to do the same thing on a *real* app. Today you do it on a starter app where the numbers are predictable.

---

## Setup

### Working directory

```bash
mkdir -p ~/c15/week-02/ex-01-three-builds
cd ~/c15/week-02/ex-01-three-builds
```

### Verify Docker version and BuildKit

```bash
docker version | grep -E 'Version|Engine'
docker buildx version
```

Expect Docker 24+ and a `buildx` version. If BuildKit is somehow not active:

```bash
export DOCKER_BUILDKIT=1
```

### Starter files

Create `app/main.py`:

```python
import os
import platform
import sys
from flask import Flask, jsonify

app = Flask(__name__)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/info")
def info():
    return jsonify({
        "service": os.environ.get("SERVICE_NAME", "c15-ex01"),
        "python":   sys.version.split()[0],
        "platform": platform.platform(),
        "uid":      os.getuid(),
        "pid":      os.getpid(),
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
```

Create `app/__init__.py` (empty file).

Create `requirements.txt`:

```text
flask==3.0.3
gunicorn==22.0.0
```

Create `.dockerignore`:

```text
.git
.venv
__pycache__
*.pyc
*.pyo
.env
.env.*
.DS_Store
Dockerfile*
README.md
notes/
```

---

## Step 1 — Build v1: naive single-stage (~15 min)

Create `Dockerfile.v1`:

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ ./app/

EXPOSE 8000
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:8000", "app.main:app"]
```

Build and time it:

```bash
time docker build -f Dockerfile.v1 -t c15-ex01:v1 .
```

Capture two numbers in your notebook:

```bash
docker images c15-ex01:v1 --format '{{.Size}}'
```

Expect around **1.0–1.1 GB**.

Smoke-test:

```bash
docker run -d --rm -p 8001:8000 --name c15-v1 c15-ex01:v1
sleep 2
curl -s localhost:8001/info | jq
curl -s localhost:8001/healthz | jq
docker stop c15-v1
```

The `info` endpoint should report your container's UID (`0`, i.e. root — that is the bug this week's lectures fixed).

Rebuild with no changes to measure warm-cache time:

```bash
time docker build -f Dockerfile.v1 -t c15-ex01:v1 .
```

Expect well under 1 second. All steps `CACHED`.

---

## Step 2 — Build v2: multi-stage with `python:3.12-slim` (~25 min)

Create `Dockerfile.v2`:

```dockerfile
# syntax=docker/dockerfile:1.7

# --- Build stage ---
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on \
    PIP_DISABLE_PIP_VERSION_CHECK=on

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libc6-dev \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Runtime stage ---
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

Build and measure:

```bash
time docker build -f Dockerfile.v2 -t c15-ex01:v2 .
docker images c15-ex01:v2 --format '{{.Size}}'
```

Expect around **120–150 MB**. Roughly 7× smaller than v1.

Smoke-test:

```bash
docker run -d --rm -p 8002:8000 --name c15-v2 c15-ex01:v2
sleep 2
curl -s localhost:8002/info | jq
docker stop c15-v2
```

Confirm `info`'s `uid` field is now `10001`, not `0`. Non-root achieved.

---

## Step 3 — Build v3: multi-stage with distroless (~25 min)

Create `Dockerfile.v3`:

```dockerfile
# syntax=docker/dockerfile:1.7

# --- Build stage ---
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libc6-dev \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Runtime stage: distroless, no shell, no apt ---
FROM gcr.io/distroless/python3-debian12:nonroot

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/opt/venv/lib/python3.12/site-packages"

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY app/ ./app/

# distroless ships a 'nonroot' user (UID 65532). Use it.
USER nonroot

EXPOSE 8000

# distroless has no shell. Health command must be exec-form Python.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["/opt/venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz').read()"]

ENTRYPOINT ["/opt/venv/bin/gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app.main:app"]
```

Build and measure:

```bash
time docker build -f Dockerfile.v3 -t c15-ex01:v3 .
docker images c15-ex01:v3 --format '{{.Size}}'
```

Expect around **55–70 MB**. Roughly 18× smaller than v1.

Smoke-test:

```bash
docker run -d --rm -p 8003:8000 --name c15-v3 c15-ex01:v3
sleep 2
curl -s localhost:8003/info | jq
docker stop c15-v3
```

Confirm `info`'s `uid` is `65532` — distroless's pre-baked `nonroot` user.

### What happens if you `docker exec` into distroless?

Try it:

```bash
docker run -d --rm -p 8003:8000 --name c15-v3 c15-ex01:v3
docker exec -it c15-v3 sh
# Expect: OCI runtime exec failed: exec failed: unable to start container process:
#         exec: "sh": executable file not found in $PATH: unknown
docker stop c15-v3
```

There is no shell. That is not a bug — that is the entire point. Write down in your notes the moment you understood that "no shell in production" is a *feature*.

---

## Step 4 — The measurements table (~30 min)

Run this measurement script and save the output:

```bash
echo "=== c15-ex01 measurements ==="
for tag in v1 v2 v3; do
  echo "--- c15-ex01:$tag ---"
  docker images c15-ex01:$tag --format 'size: {{.Size}}'
  docker history --no-trunc --format 'layers: {{.Size}}' c15-ex01:$tag | wc -l | xargs -I {} echo "layers: {}"
done
```

Then build each image **cold** (after `docker builder prune -af`) and time it:

```bash
docker builder prune -af
time docker build -f Dockerfile.v1 -t c15-ex01:v1 .   # cold
time docker build -f Dockerfile.v1 -t c15-ex01:v1 .   # warm

docker builder prune -af
time docker build -f Dockerfile.v2 -t c15-ex01:v2 .
time docker build -f Dockerfile.v2 -t c15-ex01:v2 .

docker builder prune -af
time docker build -f Dockerfile.v3 -t c15-ex01:v3 .
time docker build -f Dockerfile.v3 -t c15-ex01:v3 .
```

Fill in this table in `notes/comparison.md`:

```markdown
| Variant | Base image                                    | Final size | Layers | Cold build | Warm build | Runtime UID | Has shell? |
|---------|-----------------------------------------------|-----------:|-------:|-----------:|-----------:|------------:|:-----------|
| v1      | `python:3.12`                                 | 1.07 GB    | 8      | 78 s       | 0.3 s      | 0           | yes        |
| v2      | `python:3.12-slim` (multi-stage)              | 135 MB     | 12     | 48 s       | 0.4 s      | 10001       | yes        |
| v3      | `gcr.io/distroless/python3-debian12:nonroot`  | 62 MB      | 11     | 51 s       | 0.4 s      | 65532       | **no**     |
```

Your absolute numbers will differ. The ratios should not.

---

## Step 5 — Inspect with `dive` (optional, ~15 min)

`dive` is an interactive layer inspector. If you have it installed (`brew install dive` or download from the releases page):

```bash
dive c15-ex01:v1
```

Navigate with `tab` to switch panes. Look at the `pip` install layer — you can see `__pycache__` directories, the entire pip cache, every package's `.dist-info`. Most of that is dead weight.

Now:

```bash
dive c15-ex01:v3
```

The distroless image has *almost nothing* in it. A `/usr` with libc and Python. A `/etc/passwd` with `nonroot`. CA certs. Your `/opt/venv` and `/app`. That is the whole image.

---

## Acceptance criteria

You can mark this exercise done when:

- [ ] Three files exist: `Dockerfile.v1`, `Dockerfile.v2`, `Dockerfile.v3`.
- [ ] All three images build cleanly: `docker build -f Dockerfile.vX -t c15-ex01:vX .` succeeds for X in {1,2,3}.
- [ ] All three pass the same smoke test: `curl localhost:800X/healthz` returns `{"ok": true}` and `curl localhost:800X/info` returns valid JSON.
- [ ] `c15-ex01:v3` reports `uid: 65532` from its `/info` endpoint.
- [ ] `docker exec -it c15-v3 sh` fails with "executable file not found."
- [ ] `notes/comparison.md` contains a filled-in version of the table above with **your** measured numbers.
- [ ] `notes/comparison.md` contains a one-paragraph answer to: "If you had to ship one of these to production tomorrow, which one and why?"

---

## Common pitfalls

- **`time docker build` shows 0.0 s.** You built once already and BuildKit cached everything. Run `docker builder prune -af` to force a cold build, then measure.
- **`docker run` on v3 fails with "exec format error" or "no such file."** Your `ENTRYPOINT` references `/opt/venv/bin/gunicorn` but the venv copy did not work. Check `docker run --rm c15-ex01:v3 --help` (the `--help` becomes args to gunicorn).
- **Multi-stage build is bigger than single-stage.** You forgot to switch the final `FROM` to `slim`. Check that your second `FROM` is `python:3.12-slim`, not `python:3.12`.
- **`HEALTHCHECK` fails on v3.** distroless's `python` interpreter is at `/opt/venv/bin/python` (because we are using the venv copy). The exec-form `HEALTHCHECK` must reference that exact path.
- **`useradd: command not found` in v3.** distroless has no `useradd`. That is why we use distroless's *pre-baked* `nonroot` user — no `RUN useradd` needed.

---

## What good looks like

A done version of this exercise has:

- All three Dockerfiles committed.
- A `notes/comparison.md` with real measured numbers, not made-up ones.
- A `notes/reflection.md` (one paragraph) on which one you would ship and why. There is a defensible argument for `v2` (debuggable in production), and a defensible one for `v3` (smaller, fewer CVEs). Pick one. Defend it.

The point of having an opinion is so that Lecture 2's "production-grade Dockerfile" example stops being abstract. By the end of this exercise you should know whether you are a "distroless or nothing" engineer or a "slim is fine, I want to be able to exec a shell at 3 AM" engineer. Both are valid; you will be on a team of one or the other.

---

## Why this matters

Every interview for a DevOps or Platform role in 2026 has some version of: "Walk me through your Dockerfile for a Python service." The answer that gets the offer is not the one with the most tricks; it is the one that has *measured* the tradeoffs and can defend the choice. After this exercise, you can.
