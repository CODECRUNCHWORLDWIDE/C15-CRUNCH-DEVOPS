# Exercise 3 — Write Your First Dockerfile

**Goal:** Author a small but correct multi-stage `Dockerfile` for a Python web service, build it, run it, and then read the result back with `docker history` to prove that every `FROM`, `COPY`, and `RUN` line you wrote landed where you expected. In Exercise 1 you built a rootfs by hand; in Exercise 2 you pulled and inspected someone else's image. Now you write the recipe that produces your own.

**Estimated time:** 90 minutes.

---

## Why we are doing this

Up to now you have consumed images — `debootstrap` built one for you, Docker Hub shipped you `debian:bookworm` and `python:3.12-slim`. A `Dockerfile` is the build recipe that turns a base image plus your code into a new image. It is the single most-edited file in a DevOps engineer's week, and the difference between a Dockerfile written carefully and one copied off Stack Overflow is the difference between a 60 MB image that builds in 4 seconds on a cache hit and a 1.2 GB image that rebuilds from scratch on every commit.

The two ideas you are drilling here are **build stages** and **layer caching**. A multi-stage build uses one stage to compile or install and a second, slimmer stage to run — so the build tools never ship to production. Layer caching means Docker reuses any layer whose inputs have not changed; ordering your instructions so the slow, rarely-changing steps come first is the whole game. Get the ordering wrong and every one-character code change triggers a full dependency reinstall.

By the end of this exercise the multi-stage Python Dockerfile stops being something you paste and starts being something you can write from a blank file and defend line by line — which is exactly what this week's learning objectives ask of you.

---

## Setup

You need Docker installed and working from Exercise 2. Verify:

```bash
docker version          # client and server both print
docker run --rm hello-world
```

Make a working directory for a tiny Python web service:

```bash
mkdir -p ~/c15/week01/dockerfile-drill
cd ~/c15/week01/dockerfile-drill
```

---

## Step 1 — Write the app (10 min)

We need something to containerize. A single-file Flask service is enough — the point is the Dockerfile, not the app.

Create `app.py`:

```python
from flask import Flask

app = Flask(__name__)


@app.get("/")
def index() -> str:
    return "C15 container is up.\n"


@app.get("/healthz")
def healthz() -> tuple[str, int]:
    return "ok\n", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

Pin your dependencies in `requirements.txt`:

```text
flask==3.0.3
gunicorn==22.0.0
```

We pin exact versions on purpose. `flask` without a version is a `latest`-by-another-name footgun: the image you build today and the image your colleague builds next month would differ silently. Pinning is the same discipline as the digest-pinning you did in Exercise 2, one layer up the stack.

---

## Step 2 — Write the naive single-stage Dockerfile (10 min)

Start with the version most people write first. Create `Dockerfile.naive`:

```dockerfile
FROM python:3.12

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
```

Build it and note the size:

```bash
docker build -f Dockerfile.naive -t c15-web:naive .
docker images c15-web:naive
```

Then watch the cache misbehave. Change one byte of `app.py` (add a comment), rebuild, and watch:

```bash
echo "# touch" >> app.py
docker build -f Dockerfile.naive -t c15-web:naive .
```

The `pip install` step **reran**, even though your dependencies did not change. That is the cost of `COPY . .` before `RUN pip install`: any change to any file busts the cache for every layer below it, including the slow dependency install. The image is also large — `python:3.12` carries a full build toolchain (~1 GB) you do not need at runtime.

Note both numbers (size, and whether `pip install` reran) in your notes file. They are the "before" you will improve.

---

## Step 3 — Write the multi-stage Dockerfile (25 min)

Now write the version you would actually ship. Create `Dockerfile`:

```dockerfile
# ---- Stage 1: build ----
# Install dependencies into a virtualenv using the full image (has build tools).
FROM python:3.12-slim AS build

WORKDIR /app

# Copy ONLY the dependency manifest first, so this layer caches
# independently of your application code.
COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: runtime ----
# Start from a fresh slim base. Copy ONLY the venv and the app — no pip cache,
# no build tools, no apt lists.
FROM python:3.12-slim AS runtime

# Run as a non-root user. Container root is host root by default (you proved
# this in Exercise 2); dropping to an unprivileged user is the cheap mitigation.
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app

COPY --from=build /opt/venv /opt/venv
COPY app.py .

ENV PATH="/opt/venv/bin:$PATH"
USER appuser

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
```

Read each decision out loud — this is the part the README's learning objective grades:

- **Two `FROM`s** — `AS build` then `AS runtime`. The build stage has whatever it needs to install; the runtime stage is a clean slim base. Only the runtime stage ships.
- **`COPY requirements.txt .` before `COPY app.py .`** — dependencies change rarely, code changes constantly. Put the rarely-changing input first so the expensive `pip install` layer survives a code edit.
- **`pip install --no-cache-dir`** — pip's download cache is dead weight inside an image; we never `pip install` again at runtime.
- **`COPY --from=build /opt/venv /opt/venv`** — this is the multi-stage payoff. We lift the installed virtualenv out of the build stage and leave the build stage's toolchain behind.
- **`USER appuser`** — the process runs unprivileged. If the app is compromised, the attacker lands as `appuser`, not root.
- **`CMD` as a JSON array** — exec form, not shell form. The process becomes PID 1 directly (no `/bin/sh -c` wrapper), so signals like `SIGTERM` from `docker stop` reach `gunicorn` cleanly.

Build it:

```bash
docker build -t c15-web:multi .
docker images c15-web:multi
```

Compare its size to `c15-web:naive`. It should be a few hundred MB smaller — the slim base plus dropping the build toolchain does most of the work.

---

## Step 4 — Run it and hit it (10 min)

```bash
docker run --rm -d -p 8000:8000 --name c15-web c15-web:multi

curl http://localhost:8000/
# Expect: C15 container is up.

curl -i http://localhost:8000/healthz
# Expect: HTTP/1.1 200 OK ... ok
```

Confirm it is running as a non-root user, not host root:

```bash
docker exec c15-web whoami
# Expect: appuser
docker exec c15-web id -u
# Expect: 10001
```

Clean up:

```bash
docker stop c15-web
```

---

## Step 5 — Prove the cache works (15 min)

This is the step that makes the layer-ordering lesson concrete.

First, edit `app.py` (change the index string), then rebuild and time it:

```bash
sed -i 's/container is up/container is still up/' app.py
time docker build -t c15-web:multi .
```

Watch the build output. The `pip install` layer should print `CACHED` — it did **not** rerun, because `requirements.txt` did not change and you copied it on its own line before the code. Only the `COPY app.py .` layer and everything below it rebuilt. That is the payoff of Step 3's ordering.

Now change a dependency and rebuild:

```bash
# bump gunicorn (or just re-pin the same version to force the edit)
sed -i 's/gunicorn==22.0.0/gunicorn==23.0.0/' requirements.txt
time docker build -t c15-web:multi .
```

This time `pip install` **reran** — correctly, because its input changed. Record both build times in your notes. The gap between "code change" and "dependency change" rebuild time is the entire reason layer ordering matters.

Read the layers back the way you did in Exercise 2:

```bash
docker history c15-web:multi
```

Map each row to a line in your `Dockerfile`. You wrote the recipe; now you can read it back in the image. That round-trip — author the instruction, see the layer — is the skill.

---

## Step 6 — Tear down

```bash
docker image rm c15-web:naive c15-web:multi 2>/dev/null || true
docker image prune -f
```

Leave the `dockerfile-drill/` directory in place — the Week 1 challenge ("shrink the image") starts from a Dockerfile like this one.

---

## Acceptance criteria

You can mark this exercise done when:

- [ ] You wrote `app.py` and a version-pinned `requirements.txt`.
- [ ] You built `Dockerfile.naive`, edited one byte of `app.py`, and watched `pip install` rerun.
- [ ] You wrote a two-stage `Dockerfile` (`build` → `runtime`) from a blank file and it builds.
- [ ] The multi-stage image is meaningfully smaller than the naive image, and you recorded both sizes.
- [ ] `curl http://localhost:8000/` and `/healthz` both respond; `docker exec ... whoami` returns `appuser`, not `root`.
- [ ] You edited `app.py`, rebuilt, and confirmed the `pip install` layer printed `CACHED`; then edited `requirements.txt` and confirmed it reran.
- [ ] You can explain — in writing, in a `notes/first-dockerfile.md` in your week-01 repo — why `COPY requirements.txt` comes before `COPY app.py`, and what the `COPY --from=build` line buys you.

---

## Stretch

- Swap the runtime base from `python:3.12-slim` to a [distroless](https://github.com/GoogleContainerTools/distroless) image (`gcr.io/distroless/python3-debian12`). It has no shell, so `docker exec ... bash` will fail — that is the security trade-off. Note what breaks and what shrinks.
- Add a `.dockerignore` that excludes `.git`, `__pycache__`, and your notes. Rebuild and confirm the build context shrank (watch the `transferring context` line at the top of the build).
- Add a `HEALTHCHECK` instruction that curls `/healthz`, then run with `docker run` and watch `docker ps` flip the container's status to `healthy`.
- Re-pin both lines of `requirements.txt` to digests-of-wheels via `pip-compile --generate-hashes` (from `pip-tools`) and add `--require-hashes` to the install. Now your dependency install is supply-chain auditable — the pinning-strategy learning objective, made real.

---

## Hints

<details>
<summary>If <code>docker build</code> errors with <code>failed to compute cache key: ... requirements.txt not found</code></summary>

You are running `docker build` from the wrong directory, or your build context (`.`) does not contain `requirements.txt`. The path in a `COPY` is relative to the build context, not to where the `Dockerfile` lives. `cd` into `dockerfile-drill/` and build with the trailing `.`.

</details>

<details>
<summary>If <code>curl http://localhost:8000/</code> hangs or refuses the connection</summary>

Check the published port mapping with `docker ps` — the line should show `0.0.0.0:8000->8000/tcp`. If it is missing, you forgot `-p 8000:8000`. If gunicorn is bound to `127.0.0.1` instead of `0.0.0.0`, it is unreachable from outside the container — confirm the `--bind 0.0.0.0:8000` in the `CMD`.

</details>

<details>
<summary>If the <code>pip install</code> layer reruns even when only <code>app.py</code> changed</summary>

You copied the code before the dependency manifest. Make sure `COPY requirements.txt .` and its `pip install` come *before* `COPY app.py .`. If both are in a single `COPY . .`, split them — that is the whole lesson of Step 3.

</details>

<details>
<summary>If the runtime stage cannot find <code>gunicorn</code> (<code>exec: "gunicorn": not found</code>)</summary>

The runtime stage starts fresh — it does not inherit the build stage's `ENV` or installed packages automatically. Confirm you have both `COPY --from=build /opt/venv /opt/venv` and the `ENV PATH="/opt/venv/bin:$PATH"` line in the runtime stage.

</details>

---

## What just happened

You wrote the file that, more than any other, defines your day-to-day as a DevOps engineer. You saw why the naive single-stage Dockerfile is large (it ships the build toolchain) and slow to iterate (it busts the dependency cache on every code change), and you fixed both with two ideas: a second stage that leaves the build tools behind, and an instruction order that puts slow, stable inputs above fast, churning ones.

Everything from here builds on this. Week 2 is an entire week of Dockerfile craft. The mini-project asks you to containerize a real existing app. The image-shrinking challenge takes a Dockerfile like the one you just wrote and pushes it under 50 MB. But the load-bearing skill — author a `FROM`/`COPY`/`RUN` recipe and predict exactly what image it produces — is the one you just built.

---

When this exercise feels comfortable, move on to the [Week 1 challenge](../challenges/challenge-01-shrink-the-image.md).
