# Challenge 1 — Shrink the Image

**Time estimate:** ~3 hours.
**Required:** Docker installed; basic Python familiarity.
**Reward:** The single most useful skill of Week 1. Smaller images mean faster CI, cheaper egress, smaller attack surface, fewer CVEs in your inbox.

---

## Problem statement

You are given a deliberately bloated `Dockerfile` for a tiny Flask app. Its built image is over 1 GB. Your task: reduce it to **under 50 MB** without changing the application's behavior. The smaller it gets, the better.

You may change every line of the `Dockerfile`. You may not change `app.py` or `requirements.txt`.

---

## Starter files

Create the following files in a new directory, exactly as shown.

**`app.py`**:

```python
from flask import Flask, jsonify
import platform, sys

app = Flask(__name__)

@app.get("/")
def root():
    return jsonify({
        "message": "hello from C15 Week 1",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

**`requirements.txt`**:

```text
flask==3.0.3
gunicorn==22.0.0
```

**`Dockerfile.naive`** (the starter, deliberately terrible):

```dockerfile
FROM python:3.12

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y \
    curl wget git vim build-essential \
    libpq-dev libssl-dev libffi-dev \
 && pip install --upgrade pip \
 && pip install -r requirements.txt

EXPOSE 8000
CMD ["python", "app.py"]
```

Build and measure:

```bash
docker build -f Dockerfile.naive -t c15-naive .
docker images c15-naive --format '{{.Repository}}:{{.Tag}} {{.Size}}'
# Expect something like: c15-naive:latest   1.07GB
```

Run and smoke-test:

```bash
docker run -d --rm -p 8000:8000 --name c15-naive c15-naive
curl -s localhost:8000 | jq
docker stop c15-naive
```

Save that JSON output. Every shrunk image must produce the same shape of response (the `python` and `platform` strings will differ — that is fine).

---

## Acceptance criteria

You can mark this challenge done when:

- [ ] A new file `Dockerfile.small` exists alongside `Dockerfile.naive`.
- [ ] `docker build -f Dockerfile.small -t c15-small .` succeeds.
- [ ] `docker images c15-small` reports a size **under 50 MB**.
- [ ] `docker run -d --rm -p 8000:8000 --name c15-small c15-small` followed by `curl -s localhost:8000` returns valid JSON with `message`, `python`, and `platform` fields.
- [ ] You commit a `notes/shrinking-journal.md` that lists, in order, each variant you tried and the resulting size. Five rows minimum. The journal is more valuable than the final number.
- [ ] (Optional but recommended.) A scan with `trivy image c15-small` reports fewer critical and high CVEs than `trivy image c15-naive`.

---

## Tactics, ranked roughly by payoff

You will need a combination of these. None alone gets you under 50 MB.

### 1. Switch base image (~700 MB saved)

`python:3.12` is the heavy variant; it includes the full Debian build toolchain. Three lighter options:

| Base | Size | Cost to you |
|------|-----:|-------------|
| `python:3.12-slim` | ~120 MB | Same Debian, no build tools. You may need `apt-get install -y build-essential` *only inside a build stage*. |
| `python:3.12-alpine` | ~50 MB | `musl` libc; some PyPI wheels are unavailable and must compile from source. Flask and gunicorn work fine. |
| `gcr.io/distroless/python3-debian12` | ~50 MB | No shell, no `pip`, no `apt`. You install Python deps elsewhere and `COPY` them in. |

Try `python:3.12-slim` first to get a baseline. Then try `alpine`.

### 2. Multi-stage build (~30–50 MB saved)

Even with `slim`, you have `pip`'s cache, `__pycache__`, build artifacts. Move package installation into a builder stage:

```dockerfile
FROM python:3.12-slim AS builder
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY app.py .
EXPOSE 8000
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]
```

The runtime stage starts from a fresh `python:3.12-slim` and copies in only the virtualenv. None of the build cache survives.

### 3. `--no-cache-dir` on every `pip install` (~20 MB)

By default `pip` caches downloaded wheels in `~/.cache/pip`. That goes into the layer. `pip install --no-cache-dir ...` skips it.

### 4. Clean apt caches in the *same* `RUN` (~30 MB)

`apt-get install` leaves `/var/lib/apt/lists/*` populated. Removed in a separate `RUN` later, it still lives in the earlier layer. Chain everything in one `RUN`:

```dockerfile
RUN apt-get update \
 && apt-get install -y --no-install-recommends some-pkg \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
```

### 5. Drop everything you do not need

The naïve Dockerfile pulls `curl wget git vim build-essential libpq-dev libssl-dev libffi-dev`. None of that is needed at runtime for a Flask app that does not talk to Postgres. Audit ruthlessly.

### 6. Run as a non-root user, with a non-shell login

```dockerfile
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER app
```

This does not shrink the image. It does eliminate `bash` history files and reduce the attack surface. Good hygiene, free of charge.

### 7. Use a `.dockerignore` file

Sounds trivial; matters a lot. Without `.dockerignore`, `COPY . .` copies your `.git/`, `node_modules/`, `__pycache__/`, `.venv/`, your `.env`, your `Dockerfile.naive` itself, *and the build context goes over the wire* to Docker daemon. Create:

**`.dockerignore`**:

```text
.git
.venv
__pycache__
*.pyc
.env
Dockerfile*
notes
README.md
```

This shaves real megabytes off the build context and prevents you from accidentally leaking your `.env`.

### 8. Use BuildKit

BuildKit is the default builder in Docker 23+; make sure it is on:

```bash
export DOCKER_BUILDKIT=1
```

BuildKit caches build steps more aggressively, parallelizes stages, and supports `--mount=type=cache` for keeping `pip` cache *outside* the layer:

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt
```

### 9. (Hard mode) Distroless

`gcr.io/distroless/python3-debian12` has no shell, no package manager, no `find`, no `bash`. Your `Dockerfile` ends like:

```dockerfile
FROM gcr.io/distroless/python3-debian12
COPY --from=builder /opt/venv /opt/venv
COPY app.py /app/app.py
ENV PYTHONPATH=/opt/venv/lib/python3.12/site-packages
ENTRYPOINT ["/usr/bin/python3", "-m", "gunicorn", "-b", "0.0.0.0:8000", "--chdir", "/app", "app:app"]
```

You cannot `docker exec ... bash` into a distroless container — there is no bash. You debug with a sidecar or by rebuilding with a debug base.

---

## Common pitfalls

- **Image looks small in `docker history` but `docker images` says 1 GB.** You are still pulling a heavy base. `docker history` shows *delta sizes*; `docker images` shows the total. Switch the base.
- **`pip install` re-runs on every build.** You `COPY . .` before `COPY requirements.txt`. Invert the order: `COPY requirements.txt` first, `pip install`, *then* `COPY app.py`.
- **Multi-stage with `--from=builder` does not actually shrink.** You forgot to switch the final `FROM` to `python:3.12-slim` and are still building on top of the heavy base.
- **App fails to start under non-root user.** It is trying to write to `/app` or bind a port < 1024. Move state to `/tmp`; expose 8000 not 80.
- **Alpine breaks with `ImportError: ... missing libssl.so.1.1`.** `musl` ≠ glibc. Some wheels do not exist for `musllinux`. Add `apk add --no-cache libffi openssl` in a builder stage, or stick with `-slim`.

---

## Rubric

| Criterion | Weight | "Great" looks like |
|-----------|------:|--------------------|
| Final size | 40% | < 50 MB |
| App still works | 20% | `curl` returns valid JSON with all three fields |
| Journal completeness | 20% | At least 5 distinct attempts logged with sizes |
| Security posture | 10% | Non-root user; `trivy` shows fewer high/critical CVEs |
| Code clarity | 10% | `Dockerfile.small` is readable; multi-stage labels are sensible |

---

## Submission

Push to your `c15-week-01-shrink` repo or a directory of your week-01 portfolio:

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

---

## Why this matters

The first three years of your DevOps career, "small image" wins are continuous. Build time, push time, pull time, cold-start time, registry storage, egress bills, supply-chain audit results — all of them respond linearly to image size. The engineer who can take a 1 GB image to 50 MB without breaking it is permanently more useful than the one who cannot.

You will not stop optimizing images. You will get faster at it. This challenge is the first rep.
