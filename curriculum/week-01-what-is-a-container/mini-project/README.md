# Mini-Project — Containerize an Existing App

> Take an existing Python web service — your C16 `crunchwriter`, or a small Flask/FastAPI app of your own, or the reference app provided below — and produce a production-grade containerization. Two artifacts: a hand-built container (`unshare` + tarball) and a real Docker image. Both must run the same app. Both must be defensible in a code review.

This is the synthesis project for Week 1. By doing it you will touch every concept from both lectures: namespaces, cgroups, capabilities, the OCI image format, multi-stage builds, base-image selection, digest pinning, and a `.dockerignore`. By the end you will have a repo you can show in an interview.

**Estimated time:** 7 hours, spread across Thursday–Saturday.

---

## What you will build

A public GitHub repo `c15-week-01-container-<yourhandle>` containing:

1. **`app/`** — a small Python web service (Flask or FastAPI, your choice). One health endpoint, one demo endpoint, structured JSON output.
2. **`Dockerfile`** — a multi-stage `Dockerfile` for the app. Image size **under 100 MB**. Non-root user. Pinned base image (preferably by digest).
3. **`by-hand/`** — scripts and notes for building and running the same app inside a hand-built container using `unshare`, `chroot`, and a Debian rootfs tarball. **No Docker** in this directory.
4. **`compare.md`** — a side-by-side comparison of the two containerizations: size, startup time, namespaces used, security posture, what each delivers that the other does not.
5. **`README.md`** — explains the project, the layout, and how to run both flavors. Aimed at a reader who has not taken C15.
6. **`Makefile`** (or `justfile`) with at least these targets:
   - `make build`         — builds the Docker image.
   - `make run`           — runs the container, prints the URL.
   - `make smoke`         — `curl`s the endpoints, expects 200s.
   - `make by-hand`       — runs the hand-built container.
   - `make clean`         — removes the rootfs, image, and stopped containers.

---

## Acceptance criteria

- [ ] A public GitHub repo at the URL above.
- [ ] `make build && make run && make smoke` works on a fresh clone with only Docker installed.
- [ ] `make by-hand` works on a Linux host with `debootstrap` installed (skipping on macOS is acceptable; document it).
- [ ] `docker images <yourimage>` reports a size **under 100 MB**. Under 50 MB earns an "exceeded expectations" note.
- [ ] The Dockerfile is multi-stage with at least two `FROM` lines.
- [ ] The container runs as a non-root user (verify with `docker exec <id> id` showing `uid != 0`).
- [ ] `app/` is meaningfully more than a hello-world: at least two endpoints, structured logs, a configurable port via env var.
- [ ] `compare.md` includes at least: image size, startup time (measured), namespaces, capabilities dropped, and one sentence each on what is gained or lost.
- [ ] A pinned base image: either `FROM python:3.12-slim@sha256:...` or a clearly-documented decision not to pin (with reasoning).
- [ ] No emoji in any file. No marketing language. The README reads like documentation, not a sales pitch.

---

## The reference app (optional)

If you do not have your own app to containerize, use this one. Save under `app/main.py`:

```python
import os
import logging
import platform
import sys
from flask import Flask, jsonify, request

# Structured-ish logging. Week 10 goes deeper.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("c15-week01")

app = Flask(__name__)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/info")
def info():
    log.info("info requested by %s", request.remote_addr)
    return jsonify({
        "service": os.environ.get("SERVICE_NAME", "c15-week01"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "uid": os.getuid(),
        "pid": os.getpid(),
        "env_count": len(os.environ),
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
```

And `app/requirements.txt`:

```text
flask==3.0.3
gunicorn==22.0.0
```

---

## Suggested layout

```
c15-week-01-container-<handle>/
├── README.md
├── Makefile
├── compare.md
├── .dockerignore
├── Dockerfile
├── app/
│   ├── main.py
│   └── requirements.txt
├── by-hand/
│   ├── 01-build-rootfs.sh    ← runs debootstrap, copies the app in
│   ├── 02-run.sh             ← the unshare + chroot invocation
│   └── README.md
└── notes/
    ├── decisions.md          ← what choices you made and why
    └── journal.md            ← what you tried and what failed
```

---

## Suggested order of operations

### Phase 1 — Bring the app up locally (30 min)

1. Create the repo. Init git.
2. Drop in `app/main.py` and `app/requirements.txt`.
3. Run it directly: `cd app && python -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python main.py`. Hit `localhost:8000/info`.
4. Commit. Tag this commit so you have a baseline.

### Phase 2 — The Dockerfile (90 min)

Iterate from a naïve single-stage to a tight multi-stage.

**v1: single stage, big base.**

```dockerfile
FROM python:3.12
WORKDIR /app
COPY app/ /app/
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
```

Build, measure. Likely > 1 GB. Note the size in `notes/journal.md`.

**v2: slim, single stage.**

Switch the base. Note the new size.

**v3: multi-stage, virtualenv pattern.**

The version from Lecture 2. Should land under 200 MB.

**v4: non-root user + `.dockerignore` + `--no-cache-dir`.**

Should land under 150 MB.

**v5 (optional): alpine or distroless.**

Under 80 MB. Watch for `musl` issues on Alpine; distroless will not let you `exec sh` for debug.

Stop when you are under 100 MB and the smoke test passes. Commit the final `Dockerfile`.

### Phase 3 — The Makefile (30 min)

A real `Makefile`. Targets:

```make
.PHONY: build run stop smoke by-hand clean

IMAGE := c15-week01:dev
NAME  := c15-week01

build:
	docker build -t $(IMAGE) .

run:
	docker run -d --rm -p 8000:8000 --name $(NAME) $(IMAGE)
	@echo "running on http://localhost:8000"

stop:
	-docker stop $(NAME)

smoke:
	curl -sf localhost:8000/healthz
	curl -sf localhost:8000/info | jq

by-hand:
	bash by-hand/01-build-rootfs.sh
	bash by-hand/02-run.sh

clean: stop
	-docker rmi $(IMAGE)
	-sudo rm -rf /var/lib/c15/week01-rootfs
```

### Phase 4 — The by-hand directory (90 min)

Adapt Exercise 1 to actually serve the app:

**`by-hand/01-build-rootfs.sh`** — `debootstrap` a fresh rootfs, then `chroot` into it and `pip install` the app's requirements into a system Python, then `cp` the `app/` directory in.

**`by-hand/02-run.sh`** — `unshare` with the same flags as Exercise 1, plus `--net` if you can wire up a veth pair, and run `python /app/main.py` as the container's entrypoint. Bonus points for putting it in a cgroup with `memory.max=200M`.

Document any limitations (e.g., "we are sharing the host's network namespace because configuring veth across distros is a Week 3 problem") in `by-hand/README.md`.

### Phase 5 — `compare.md` (60 min)

The real deliverable. Open a Markdown file and fill in:

```markdown
# Two ways to ship the same app

## Image size

| Variant | Size on disk | Layers | Build time |
|---------|------------:|-------:|----------:|
| By hand (rootfs tarball) | 110 MB | 1 (it is a tarball) | 2 min (debootstrap) |
| Docker (multi-stage) |  85 MB | 5 | 18 s (cached) |

## Startup time

| Variant | Cold start | Warm start |
|---------|----------:|-----------:|
| By hand | ~60 ms | ~60 ms |
| Docker | ~250 ms | ~150 ms |

## Namespaces used

[fill in table from `/proc/$pid/ns/`]

## Capabilities dropped

[fill in `capsh --print` output]

## What Docker gives you that by-hand does not

- Image layering / overlayfs (the rootfs in by-hand is one tarball).
- Registry push/pull.
- Network namespace + bridge + iptables wired up automatically.
- Restart policy.
- `docker inspect`, structured metadata.

## What by-hand teaches you that Docker hides

- The kernel is doing the work.
- The rootfs is just a directory.
- Networking is veth pairs + routes + NAT.
- Limits are file writes under /sys/fs/cgroup.
```

### Phase 6 — README polish (30 min)

Treat the README as the only thing a stranger will read. Include:

- One-paragraph description of what the project is and what it demonstrates.
- A "Quick start" with the three commands that work on a fresh clone.
- A diagram (ASCII is fine) showing the relationship between `app/`, `Dockerfile`, and `by-hand/`.
- A "Why this exists" section. One paragraph.
- A "Known limitations" section. Two or three bullets.
- A "License" line. GPL-3.0, to match C15.

### Phase 7 — Tag and push (15 min)

```bash
git tag -a v1.0 -m "Week 1 mini-project complete"
git push --tags
```

Open a PR against your own `main` if you want code-review practice; otherwise just push.

---

## Stretch goals

- Push the image to GHCR with a digest, then in the README reference it by digest, not by tag.
- Add a `make scan` target that runs `trivy image` and writes a SARIF report into `notes/`.
- Build the image for both `amd64` and `arm64` using `docker buildx`. Push a multi-arch manifest.
- Wire the `by-hand` script up with `pivot_root` instead of `chroot`, and document the difference in `by-hand/README.md`.
- Add a tiny GitHub Actions workflow that builds the image on push and runs the smoke test in CI.

---

## Rubric

| Criterion | Weight | "Great" looks like |
|-----------|------:|--------------------|
| It runs end-to-end on a fresh clone | 25% | `make build && make smoke` works for someone who has only just cloned the repo |
| Dockerfile quality | 20% | Multi-stage, non-root, < 100 MB, pinned base, readable |
| By-hand build works | 15% | `make by-hand` reliably starts a container without Docker |
| `compare.md` quality | 20% | Numbers are real measurements, not made up; conclusions are defensible |
| README | 10% | A stranger can use it without asking you a question |
| Stretch | 10% | At least one stretch goal delivered |

---

## Why this matters

Containers are the substrate for the next eleven weeks. Kubernetes, CI/CD, observability, secrets — all of them assume you have an image, you can run it, you can reason about what is inside it. If Week 1 lands, the rest of C15 is teaching you how to operate clusters of these things. If Week 1 does not land, every subsequent week will feel like cargo-culting commands.

The "two ways to ship the same app" framing is not academic. The next time you sit in a code review and someone asks "do we really need Docker for this?" you will be the person in the room who actually knows the answer — and the alternatives.

---

## Submission

Push to GitHub. Open an issue in the C15 cohort tracker (or, if studying solo, in your own repo) with the URL. Tag the commit `v1.0`. Move on to Week 2.
