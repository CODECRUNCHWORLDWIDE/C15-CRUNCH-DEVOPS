# Challenge 1 — Shrink to Under 50 MB

**Time estimate.** ~3 hours.
**Required.** Docker 24+, BuildKit on, `trivy` installed.
**Reward.** Real proof that you can take a non-trivial Python service to a distroless-class image without breaking it. Week 1's challenge was the warm-up; this is the rep.

---

## Problem statement

You are given a Flask service with a handful of **real** runtime dependencies (a database driver, a JSON validator, a structured logger, and a couple of standard libraries). Its naive `Dockerfile` produces an image of roughly 1.2 GB. Your task: reduce it to **under 50 MB** while keeping every endpoint working and every dependency importable.

You may rewrite the `Dockerfile` from scratch. You may use multi-stage builds, distroless, cache mounts, BuildKit secrets, or anything else from this week. You may **not** change `app.py`, `requirements.txt`, or the expected JSON response shape.

The difference between Week 1's shrink challenge and this one: Week 1's app had two pure-Python deps with no C extensions. This week's app has `pydantic` (C-compiled), `psycopg[binary]` (Postgres driver with bundled libpq), and `structlog`. None of those have a "just use Alpine" easy answer.

---

## Starter files

Create these in a new directory exactly as shown.

### `app.py`

```python
import os
import sys
import platform
import logging
import structlog
from flask import Flask, jsonify, request
from pydantic import BaseModel, Field, ValidationError

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(message)s")
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)
log = structlog.get_logger("c15-week02-shrink")

app = Flask(__name__)


class EchoIn(BaseModel):
    message: str = Field(min_length=1, max_length=200)
    repeat: int = Field(ge=1, le=10, default=1)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/info")
def info():
    log.info("info_requested", remote=request.remote_addr)
    return jsonify({
        "service": os.environ.get("SERVICE_NAME", "c15-week02-shrink"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "uid": os.getuid(),
        "pid": os.getpid(),
    })


@app.post("/echo")
def echo():
    try:
        payload = EchoIn.model_validate(request.get_json(force=True))
    except ValidationError as e:
        return jsonify({"error": "validation", "details": e.errors()}), 400
    return jsonify({
        "echoed": [payload.message] * payload.repeat,
        "count":  payload.repeat,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
```

### `requirements.txt`

```text
flask==3.0.3
gunicorn==22.0.0
pydantic==2.8.2
structlog==24.2.0
psycopg[binary]==3.2.1
```

### `Dockerfile.naive` (the bloated starting point)

```dockerfile
FROM python:3.12

WORKDIR /app
COPY . .

RUN apt-get update && apt-get install -y \
    curl wget git vim build-essential \
    libpq-dev libssl-dev libffi-dev postgresql-client \
 && pip install --upgrade pip \
 && pip install -r requirements.txt

EXPOSE 8000
CMD ["python", "app.py"]
```

### `.dockerignore`

Start it empty. You will write the real one.

---

## Step 0 — Baseline measurement

```bash
docker build -f Dockerfile.naive -t shrink:naive .
docker images shrink:naive --format '{{.Size}}'
# Expect ~1.2 GB
```

Smoke-test:

```bash
docker run -d --rm -p 8000:8000 --name shrink-naive shrink:naive
sleep 2

curl -s localhost:8000/healthz | jq                  # {"ok": true}
curl -s localhost:8000/info | jq                     # service / python / platform / uid=0 / pid

curl -s -X POST localhost:8000/echo \
  -H 'content-type: application/json' \
  -d '{"message": "hi", "repeat": 3}' | jq           # {"echoed": ["hi","hi","hi"], "count": 3}

curl -s -X POST localhost:8000/echo \
  -H 'content-type: application/json' \
  -d '{"message": "", "repeat": 1}' | jq             # 400 with validation error

docker stop shrink-naive
```

Save those three response shapes as the **golden truth**. Every smaller image must produce identical responses (the `python`/`platform` strings will differ; everything else must match).

---

## Acceptance criteria

You are done when:

- [ ] A `Dockerfile.small` exists alongside `Dockerfile.naive`.
- [ ] `docker build -f Dockerfile.small -t shrink:small .` succeeds.
- [ ] `docker images shrink:small` reports a size **under 50 MB**.
- [ ] All four smoke-test calls (`/healthz`, `/info`, `/echo` happy path, `/echo` validation error) return the expected response shapes.
- [ ] The container runs as non-root (verify via `/info`'s `uid` field — must be non-zero).
- [ ] `trivy image --severity HIGH,CRITICAL shrink:small` reports strictly fewer findings than the same scan against `shrink:naive`.
- [ ] A `notes/shrinking-journal.md` exists with **at least 6 rows** documenting your iterations: variant name, base image, key change, resulting size.
- [ ] A `.dockerignore` exists with at least 8 entries.

---

## What the journal looks like

```markdown
| # | Variant | Base | Key change | Size | Smoke |
|--:|---------|------|------------|-----:|:-----:|
| 0 | naive | `python:3.12` | starter | 1.21 GB | pass |
| 1 | slim | `python:3.12-slim` | drop dev tools | 270 MB | pass |
| 2 | slim+multistage | `python:3.12-slim` | venv copied | 195 MB | pass |
| 3 | slim+mount | `python:3.12-slim` | pip cache mount | 195 MB (same), build 18 s | pass |
| 4 | distroless | `gcr.io/distroless/python3-debian12:nonroot` | builder → distroless | 78 MB | **fail** (psycopg missing libpq) |
| 5 | distroless+libpq | same | `COPY` libpq from slim builder | 63 MB | pass |
| 6 | distroless+strip | same | `pip install --no-compile`, prune `*.pyc` | 48 MB | pass |
```

This is the journal you would actually keep. Eight entries beats six.

---

## Tactics, ranked by payoff

You will need a stack of these. None alone gets you under 50 MB on this app.

### 1. Multi-stage with distroless final (~80–90% of the win)

The pattern from Lecture 2. Build in `python:3.12-slim` with `gcc` and `libpq-dev`; copy the venv into `gcr.io/distroless/python3-debian12:nonroot`.

The trap: `psycopg[binary]` ships its own libpq inside the wheel. *Usually* that means distroless works without copying libpq. But some platforms (older arm64) fall back to the system libpq. Verify in your container:

```bash
docker run --rm -it --entrypoint /opt/venv/bin/python shrink:small \
  -c "import psycopg; print(psycopg.__version__); psycopg.Connection.connect"
```

If it imports cleanly but errors only on a real DB call (we are not connecting to a real DB in this challenge, so a clean import is sufficient), you are fine.

### 2. Strip Python bytecode and metadata (~5–10 MB)

After installing into the venv, the build stage can prune:

```dockerfile
RUN find /opt/venv -name '__pycache__' -type d -exec rm -rf {} + ; \
    find /opt/venv -name '*.dist-info' -type d -exec sh -c 'rm -rf "$1"/RECORD "$1"/INSTALLER "$1"/WHEEL "$1"/REQUESTED' _ {} \; ; \
    find /opt/venv -name 'tests' -type d -exec rm -rf {} + ; \
    find /opt/venv -name '*.pyc' -delete
```

Be cautious: removing `*.dist-info` directories entirely can break `pkg_resources`. Remove only the metadata files you do not need at runtime.

### 3. Use `pip install --no-compile` (~2–5 MB)

`--no-compile` skips writing `.pyc` files at install time. Combined with `PYTHONDONTWRITEBYTECODE=1` at runtime, no bytecode ever lands in the image.

### 4. The right `.dockerignore` (varies; can be ~50+ MB if you have a big repo)

```text
.git
.gitignore
.venv
__pycache__
*.pyc
.env
.env.*
.DS_Store
Dockerfile*
README.md
notes/
tests/
.pytest_cache
.mypy_cache
.ruff_cache
.coverage
htmlcov/
docs/
```

### 5. Pin base image by digest

Does not shrink the image — but reproducibility is part of "image quality." Required in production by Week 4.

### 6. Cache mounts for fast iteration

Does not shrink the image either. But you are going to iterate a *lot* on this challenge; cache mounts make every wrong turn cheap to back out of.

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --no-compile -r requirements.txt
```

### 7. (Hard mode) `python:3.12-alpine` with musl wheels

Pydantic v2 ships musl wheels. `psycopg[binary]` ships musl wheels starting from 3.1.x. Flask, gunicorn, structlog are pure-Python. So Alpine is *potentially* viable here — but it is a fight. Distroless is the cleaner answer.

### 8. (Hard mode) `wolfi-base` or Chainguard's `python`

If you have a Chainguard account (free for community use), `cgr.dev/chainguard/python:latest` is glibc, distroless-style, daily-patched. Typically lands in the 35–45 MB range with a venv copy. Worth a side experiment.

---

## Common pitfalls (specific to this app)

- **`psycopg` import fails on distroless** with `ImportError: libpq.so.5`. Two fixes: (a) use `psycopg[binary]` which bundles libpq (most cases work); (b) `COPY --from=builder /usr/lib/x86_64-linux-gnu/libpq.so.5 /usr/lib/x86_64-linux-gnu/` into the final stage.
- **`pydantic` import fails on distroless** with a `_pydantic_core` symbol error. This is a stale wheel; rebuild the builder stage and confirm `pip` is picking the right wheel for the platform.
- **`structlog` imports but logging blows up at runtime.** `structlog` 24.x needs `python>=3.8` — fine. Most likely cause is a missing `iso` timestamp formatter; in 24.2 it is built-in, no extra deps.
- **Image is exactly 51 MB and you cannot get the last megabyte.** Try `pip install --no-cache-dir --no-compile` and the bytecode strip. Often gets you 2–4 MB.

---

## Rubric

| Criterion | Weight | "Great" looks like |
|-----------|------:|--------------------|
| Final size | 35% | Under 50 MB. Bonus under 45. |
| App correctness | 20% | All four smoke calls match the golden output |
| Journal completeness | 20% | 6+ iterations logged with sizes and notes |
| Security posture | 10% | Non-root, fewer `trivy` HIGH/CRITICAL than baseline |
| Dockerfile readability | 10% | Multi-stage with named stages; comments where non-obvious |
| Reproducibility | 5% | Base image digest-pinned; deps version-pinned |

---

## Submission

Push to `c15-week-02-shrink-<yourhandle>` or a `challenge-01-shrink/` subdirectory of your week-02 portfolio. Required layout:

```
shrink/
├── app.py
├── requirements.txt
├── Dockerfile.naive
├── Dockerfile.small
├── .dockerignore
└── notes/
    └── shrinking-journal.md
```

Tag the final commit `week-02-challenge-01-done`.

---

## Why this matters

Week 1's shrink was a hello-world version of the same skill. This week's app has C extensions, a database driver, and dependencies that *some* size-reduction tactics break. The 50 MB target is achievable but not trivial; the path requires *combinations* of tactics, not a single trick.

When you ship real software, your apps will look like this one — not like the Week 1 hello-world. The engineer who can take a real app to a tight image is the one whose CI runs in 30 seconds instead of 4 minutes, whose images pull in 1 second instead of 30, and whose security audits come back clean. That engineer is operationally more valuable than the one who only knows the easy cases.

Today is one more rep toward being that engineer.
