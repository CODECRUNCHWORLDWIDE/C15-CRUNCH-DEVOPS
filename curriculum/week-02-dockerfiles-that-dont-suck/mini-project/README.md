# Mini-Project — Containerize a Real Python App Three Ways

> Take one real Python web service — your C16 `crunchwriter`, or any non-trivial Flask/FastAPI app of your own, or the reference app provided below — and produce **three** containerized variants: naive single-stage, multi-stage with `python:3.12-slim`, and multi-stage with distroless. Measure each on image size, build time (cold and warm), CVE count, and runtime characteristics. Write a comparison document that you would publish on your team's wiki.

This is the synthesis project for Week 2. By doing it you will touch every concept from both lectures: every Dockerfile instruction worth using, layer caching, cache mounts, multi-stage builds, distroless base images, image scanning, and the discipline of measuring before you ship.

**Estimated time.** 7 hours, spread across Thursday–Saturday.

---

## What you will build

A public GitHub repo `c15-week-02-three-ways-<yourhandle>` containing:

1. **`app/`** — a real Python web service with at least three endpoints, real third-party deps including at least one C-extension package, structured logging, and a configurable port via env var.
2. **Three `Dockerfile` variants:**
   - `Dockerfile.naive` — single-stage, `python:3.12`, no `.dockerignore`, no `USER` — the *bad* example, kept for comparison.
   - `Dockerfile.slim` — multi-stage with `python:3.12-slim` runtime, non-root user, `HEALTHCHECK`, `.dockerignore`, cache mounts.
   - `Dockerfile.distroless` — multi-stage with `gcr.io/distroless/python3-debian12:nonroot` runtime.
3. **`compare.md`** — the deliverable. A 600–800 word write-up with measured tables and a defended recommendation.
4. **`scan.sh`** — a shell script that scans all three images with `trivy` and writes per-image SARIF reports.
5. **`Makefile`** with at least: `build-all`, `smoke-all`, `scan-all`, `compare`, `clean`.
6. **`README.md`** — explains the project for someone who has not taken C15.

---

## Acceptance criteria

- [ ] Public GitHub repo at the URL above.
- [ ] `make build-all` produces three images: `<repo>:naive`, `<repo>:slim`, `<repo>:distroless`.
- [ ] `make smoke-all` passes against all three: every endpoint returns the same JSON shape (the runtime variant string is allowed to differ).
- [ ] `make scan-all` runs `trivy` against all three and writes SARIF reports under `reports/`.
- [ ] `compare.md` contains real measured numbers for image size, layer count, cold-build time, warm-build time, HIGH+CRITICAL CVE count, and runtime UID.
- [ ] The `slim` and `distroless` variants run as non-root (uid != 0). Verified by an endpoint that returns `os.getuid()`.
- [ ] The `slim` variant lands under **150 MB**. The `distroless` variant lands under **80 MB**.
- [ ] The `slim` and `distroless` Dockerfiles pin their bases by `@sha256:` digest.
- [ ] No emoji in any file. No marketing language. The README reads like documentation, not a sales pitch.

---

## The reference app (if you do not have your own)

Save under `app/main.py`:

```python
import os
import sys
import platform
import logging
import structlog
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from pydantic import BaseModel, Field, ValidationError

# --- Structured logging ---
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(message)s")
structlog.configure(processors=[
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.JSONRenderer(),
])
log = structlog.get_logger("c15-week02-mp")

app = Flask(__name__)

# --- Models ---
class GreetIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    formal: bool = False

# --- Endpoints ---
@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/info")
def info():
    log.info("info_requested", remote=request.remote_addr)
    return jsonify({
        "service":  os.environ.get("SERVICE_NAME", "c15-week02-mp"),
        "version":  os.environ.get("APP_VERSION", "0.0.0"),
        "python":   sys.version.split()[0],
        "platform": platform.platform(),
        "uid":      os.getuid(),
        "pid":      os.getpid(),
        "time_utc": datetime.now(timezone.utc).isoformat(),
    })

@app.post("/greet")
def greet():
    try:
        data = GreetIn.model_validate(request.get_json(force=True))
    except ValidationError as e:
        return jsonify({"error": "validation", "details": e.errors()}), 400
    if data.formal:
        message = f"Good day, {data.name}."
    else:
        message = f"Hi {data.name}!"
    return jsonify({"message": message, "formal": data.formal})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
```

And `app/requirements.txt`:

```text
flask==3.0.3
gunicorn==22.0.0
pydantic==2.8.2
structlog==24.2.0
```

`app/__init__.py` (empty).

---

## Suggested layout

```
c15-week-02-three-ways-<handle>/
├── README.md
├── Makefile
├── compare.md
├── scan.sh
├── .dockerignore
├── Dockerfile.naive
├── Dockerfile.slim
├── Dockerfile.distroless
├── app/
│   ├── __init__.py
│   ├── main.py
│   └── requirements.txt
├── reports/                       # produced by scan.sh
│   ├── trivy-naive.sarif
│   ├── trivy-slim.sarif
│   └── trivy-distroless.sarif
└── notes/
    ├── journal.md                 # what you tried and what failed
    └── decisions.md               # the choices you made, in writing
```

---

## Suggested order of operations

### Phase 1 — Bring the app up locally (30 min)

1. Create the repo. Init git.
2. Drop in `app/main.py` and `app/requirements.txt`.
3. Run it directly: `python -m venv .venv && .venv/bin/pip install -r app/requirements.txt && PORT=8000 .venv/bin/python -m app.main`.
4. Hit `localhost:8000/info` and `localhost:8000/healthz`. Test `/greet` with both happy path and validation error.
5. Commit. Tag this commit so you have a baseline.

### Phase 2 — Write `Dockerfile.naive` (15 min)

Start with the deliberately-bad starter. This is your "before":

```dockerfile
FROM python:3.12

WORKDIR /app
COPY . .
RUN pip install -r app/requirements.txt
EXPOSE 8000
CMD ["python", "-m", "app.main"]
```

Build and measure. Smoke-test. Note the size and the `/info` UID (it will be 0).

### Phase 3 — Write `Dockerfile.slim` (60 min)

This is the production-grade Lecture-2 pattern. The full version:

```dockerfile
# syntax=docker/dockerfile:1.7

# --- Build stage ---
FROM python:3.12-slim@sha256:<your-digest-here> AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY app/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --no-compile -r requirements.txt

# --- Runtime stage ---
FROM python:3.12-slim@sha256:<your-digest-here>

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

Get the digest with:

```bash
docker pull python:3.12-slim
docker inspect python:3.12-slim --format '{{index .RepoDigests 0}}'
```

Build and measure. Target under 150 MB.

### Phase 4 — Write `Dockerfile.distroless` (60 min)

```dockerfile
# syntax=docker/dockerfile:1.7

# --- Build stage: same as Dockerfile.slim ---
FROM python:3.12-slim@sha256:<your-digest> AS builder
# ... (identical to Dockerfile.slim's builder stage)

# --- Runtime stage: distroless ---
FROM gcr.io/distroless/python3-debian12:nonroot@sha256:<your-distroless-digest>

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/opt/venv/lib/python3.12/site-packages"

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY app/ ./app/

USER nonroot

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["/opt/venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz').read()"]

ENTRYPOINT ["/opt/venv/bin/gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app.main:app"]
```

Pull and inspect the distroless image once to get its digest. Build, measure, smoke-test. Confirm `/info` reports `uid: 65532` and that `docker exec -it <id> sh` fails.

Target under 80 MB.

### Phase 5 — Write the `Makefile` (30 min)

```make
.PHONY: build-all build-naive build-slim build-distroless \
        smoke-all smoke-naive smoke-slim smoke-distroless \
        scan-all compare clean

REPO  := c15-week02-mp
NAIVE := $(REPO):naive
SLIM  := $(REPO):slim
DIST  := $(REPO):distroless

# ---- build ----
build-all: build-naive build-slim build-distroless

build-naive:
	docker build -f Dockerfile.naive -t $(NAIVE) .

build-slim:
	docker build -f Dockerfile.slim -t $(SLIM) .

build-distroless:
	docker build -f Dockerfile.distroless -t $(DIST) .

# ---- smoke ----
smoke-all: smoke-naive smoke-slim smoke-distroless

smoke-naive:
	./smoke.sh $(NAIVE) 8001

smoke-slim:
	./smoke.sh $(SLIM) 8002

smoke-distroless:
	./smoke.sh $(DIST) 8003

# ---- scan ----
scan-all:
	mkdir -p reports
	./scan.sh $(NAIVE)        reports/trivy-naive.sarif
	./scan.sh $(SLIM)         reports/trivy-slim.sarif
	./scan.sh $(DIST)         reports/trivy-distroless.sarif

# ---- compare ----
compare:
	@echo "=== sizes ==="
	@docker images $(NAIVE) --format '{{.Tag}}: {{.Size}}'
	@docker images $(SLIM)  --format '{{.Tag}}: {{.Size}}'
	@docker images $(DIST)  --format '{{.Tag}}: {{.Size}}'

clean:
	-docker rmi $(NAIVE) $(SLIM) $(DIST)
	rm -rf reports
```

Write `smoke.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
IMAGE="$1"
PORT="$2"
NAME="smoke-$(echo $IMAGE | tr ':/' '--')"

docker run -d --rm -p $PORT:8000 --name $NAME $IMAGE
trap "docker stop $NAME >/dev/null 2>&1 || true" EXIT
sleep 2

curl -sf http://localhost:$PORT/healthz | jq
curl -sf http://localhost:$PORT/info | jq
curl -sf -X POST http://localhost:$PORT/greet \
  -H 'content-type: application/json' \
  -d '{"name": "test", "formal": true}' | jq

echo "PASS: $IMAGE"
```

Write `scan.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
IMAGE="$1"
REPORT="$2"

trivy image \
  --severity HIGH,CRITICAL \
  --format sarif \
  --output "$REPORT" \
  --ignore-unfixed \
  "$IMAGE" || true  # do not fail the build here; we report

echo "scan complete: $REPORT"
trivy image --severity HIGH,CRITICAL --ignore-unfixed "$IMAGE" | tail -20
```

`chmod +x smoke.sh scan.sh`.

### Phase 6 — Write `compare.md` (60 min)

The real deliverable. Open a Markdown file and fill in **measured** values for everything below — your numbers, not the example numbers.

````markdown
# Containerizing one Python app three ways

This repo contains three Dockerfile variants for the same Python service:

- `Dockerfile.naive`     — the "default" pattern many tutorials show. Single-stage. Heavy base.
- `Dockerfile.slim`      — production-grade pattern from C15 Week 2.
- `Dockerfile.distroless` — same builder, hardened distroless runtime.

## Measurements

| Variant       | Size   | Layers | Cold build | Warm build | UID  | Has shell |
|---------------|-------:|-------:|-----------:|-----------:|-----:|:---------:|
| naive         | 1.18 GB | 8      | 73 s       | 0.3 s      | 0    | yes       |
| slim          | 138 MB  | 13     | 48 s       | 0.5 s      | 10001 | yes      |
| distroless    | 64 MB   | 12     | 52 s       | 0.4 s      | 65532 | no       |

## CVE scan (HIGH + CRITICAL, fixed-version available only)

| Variant       | HIGH | CRITICAL |
|---------------|-----:|---------:|
| naive         | 28   | 4        |
| slim          | 9    | 2        |
| distroless    | 0    | 0        |

## Tradeoffs

### naive

**Use when:** never. This variant exists only for comparison.

**What it costs:** registry storage, network egress, build time on CI, scan
findings count, pull time on a fresh node.

### slim

**Use when:** the team is mid-incident and wants to `docker exec sh` into a
running container to grep a log. The slim variant is debuggable.

**What it gives up:** roughly 60 MB and a handful of HIGH/CRITICAL CVEs that
distroless avoids.

### distroless

**Use when:** the team has settled on its dependency set, the application has
been running for a while, and the operational priority is "minimum CVE
surface."

**What it gives up:** interactive debugging. To get a shell on a misbehaving
container, you switch to the `:debug` tag temporarily or run a sidecar.

## Recommendation

For this app today: **distroless**. The application has stabilized; we have
not needed to `exec sh` into it in the last 30 days; the security delta
matters.

When we would switch back to slim: if we start needing interactive debugging
more than once a week, or if we add a dep that pulls in a system library we
cannot easily copy into distroless.

## How to reproduce

```bash
make build-all
make smoke-all
make scan-all
make compare
```

## Limitations

- The naive build is not actually scanned for "all" CVEs — we ran `trivy`
  with `--ignore-unfixed`, which is operationally correct but undercounts the
  total surface.
- HEALTHCHECK on distroless uses Python `urllib`. A pure HTTP probe via the
  orchestrator (Compose, K8s) is the recommended pattern in production.
- We did not multi-arch this image. That is a Week 4 concern.
````

### Phase 7 — README polish (30 min)

The README is the only thing a stranger reads. Include:

- One-paragraph description of what the project is and what it demonstrates.
- A "Quick start" with the three commands that work on a fresh clone.
- A pointer to `compare.md` as the real deliverable.
- A "Why this exists" section. One paragraph.
- A "License" line. GPL-3.0, to match C15.

### Phase 8 — Tag and push (15 min)

```bash
git tag -a v1.0 -m "Week 2 mini-project complete"
git push --tags
```

---

## Stretch goals

- Push all three images to GHCR (`ghcr.io/<you>/c15-week02-mp:<variant>`). Reference them by digest in `compare.md`.
- Add a `make sbom-all` target that runs `syft` against each image and writes SPDX-JSON SBOMs under `reports/`.
- Add a GitHub Actions workflow that builds and scans all three images on every push and uploads the SARIF reports to the repo's Security tab.
- Build the slim and distroless variants for both `linux/amd64` and `linux/arm64` using `docker buildx`. Push a multi-arch manifest.
- Add a fourth variant: `Dockerfile.wolfi` using `cgr.dev/chainguard/python:latest` as the runtime. Compare it against distroless in `compare.md`.

---

## Rubric

| Criterion | Weight | "Great" looks like |
|-----------|------:|--------------------|
| It runs end-to-end on a fresh clone | 20% | `make build-all && make smoke-all` works for someone who just cloned the repo |
| Three working variants | 20% | All three build, smoke, and report the right UIDs |
| Multi-stage Dockerfile quality | 15% | `slim` and `distroless` are multi-stage, pinned, non-root, cache-mounted, healthchecked |
| `compare.md` quality | 20% | Measurements are real; recommendation is defended; tradeoffs are honest |
| `scan.sh` + reports | 10% | `make scan-all` produces three SARIFs; the contents are non-empty |
| README | 10% | A stranger can use it without asking you a question |
| Stretch | 5% | At least one stretch goal delivered |

---

## Why this matters

You have just lived the path every team takes when "we have a containerized app" stops being good enough and "we have a containerized app we can defend in a security review" becomes the bar. The naive→slim transition is the cheap one; almost every team gets there. The slim→distroless transition is the one most teams *do not* take, because it requires giving up `docker exec sh` and most engineers value that interactive debugging more than they value the CVE reduction.

There is no universally right answer. The right answer depends on the team, the application, the threat model, and the on-call rotation's comfort with not-having-a-shell. **Your job after this week is to be the engineer who has measured both options and can make the call.**

The next time someone in a code review says "we should switch to distroless," you will not be the person nodding along; you will be the person who pulls up `compare.md` and walks the team through the actual tradeoffs. That is the level Week 2 graduates from C15 are expected to operate at.

---

## Submission

Push to GitHub. Tag the commit `v1.0`. Open an issue in the C15 cohort tracker (or your own repo) with the URL.

Move on to [Week 3 — `docker compose` and the 12-Factor App](../../week-03/).
