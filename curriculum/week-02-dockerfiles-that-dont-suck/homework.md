# Week 2 Homework

Six problems, ~6 hours total. Commit each in your week-02 repo.

---

## Problem 1 — Annotate a production Dockerfile (45 min)

Pick a real `Dockerfile` from one of these open-source projects:

- **Prometheus** — <https://github.com/prometheus/prometheus/blob/main/Dockerfile>
- **Grafana** — <https://github.com/grafana/grafana/blob/main/Dockerfile>
- **Caddy** — <https://github.com/caddyserver/caddy-docker/blob/master/2.8/alpine/Dockerfile>
- **PostgreSQL official** — <https://github.com/docker-library/postgres/tree/master>

Copy the `Dockerfile` into `notes/annotated.Dockerfile`. For **every instruction**, add a comment that explains:

1. *What* this instruction does in one phrase.
2. *Why* it is at this position (cache friendliness, security, etc.).
3. *What would break* if you moved or removed it.

**Acceptance.** `notes/annotated.Dockerfile` contains the file, with one or more comment lines per instruction, totaling at least 30 comment lines.

---

## Problem 2 — `CMD` vs `ENTRYPOINT` truth table (45 min)

Build four images, named `hw2-a`, `hw2-b`, `hw2-c`, `hw2-d`, each with a `Dockerfile` containing only:

- `hw2-a`: `FROM alpine` + `CMD ["echo", "hello", "from", "cmd"]`
- `hw2-b`: `FROM alpine` + `ENTRYPOINT ["echo", "hello", "from", "entrypoint"]`
- `hw2-c`: `FROM alpine` + `ENTRYPOINT ["echo"]` + `CMD ["default-arg"]`
- `hw2-d`: `FROM alpine` + `ENTRYPOINT echo hello` (shell form) + `CMD ["wont-be-used"]`

For each image, run:

```bash
docker run --rm hw2-X
docker run --rm hw2-X overridden-arg
docker run --rm hw2-X arg1 arg2 arg3
```

**Acceptance.** A file `notes/cmd-entrypoint-table.md` containing a 3-row × 4-column table with the actual stdout of each combination. Add one paragraph at the bottom explaining the difference between shell-form and exec-form `ENTRYPOINT` based on what you saw with `hw2-d`.

---

## Problem 3 — Reorder for cache (45 min)

Take this `Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN apt-get update && apt-get install -y --no-install-recommends curl
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["python", "app.py"]
```

There is a sample app in the [Exercise 1 starter](./exercises/exercise-01-three-builds-three-images.md); reuse it (or write your own one-file Flask app + `requirements.txt`).

1. Build twice in a row with no change. Note total time.
2. Modify a comment in `app/main.py`. Rebuild. Note total time.
3. Reorder the `Dockerfile` to follow the COPY-deps-first / COPY-source-second pattern. Move the `apt-get` step too, if it makes sense.
4. Build twice in a row. Modify the same comment. Rebuild. Note the new times.

**Acceptance.** A file `notes/reorder.md` containing:

- The original `Dockerfile`.
- The reordered `Dockerfile`.
- A 4-row table with the four measured times.
- A one-paragraph explanation of which `COPY`/`RUN` instructions moved and why.

---

## Problem 4 — Scan, ignore, justify (60 min)

Pick any image you have built this week (Exercise 1's `c15-ex01:v2` is fine). Run:

```bash
trivy image --severity HIGH,CRITICAL <your-image>
```

Pick **two** findings and, for each, do the following:

1. Look up the CVE on <https://nvd.nist.gov/vuln/detail/CVE-XXXX-XXXXX>.
2. Read the description; identify what the vulnerable code path is.
3. Determine whether your application *reaches* the vulnerable code path. (Examples: a `libssl` timing side-channel in TLS handshake might be reachable; a CVE in `apt` is not, because your runtime never invokes `apt`.)
4. Decide: rebuild (if fix available), suppress (if unreachable), or escalate (if reachable and unpatched).
5. If you suppressed, write the `.trivyignore` entry with rationale-owner-expiry as in Exercise 3.

**Acceptance.** A file `notes/cve-triage.md` containing one section per CVE: CVE ID, severity, NVD link, your reachability analysis (3–5 sentences), decision, and (if applicable) the `.trivyignore` entry you added.

---

## Problem 5 — Multi-stage from a real public Dockerfile (90 min)

Take a single-stage `Dockerfile` from a small open-source Python project of your choice. Reasonable options:

- <https://github.com/tiangolo/uvicorn-gunicorn-fastapi-docker> (FastAPI starter)
- A small Flask repo of your own from C1 or C16
- <https://github.com/pallets/flask>'s example apps

Refactor the `Dockerfile` to:

1. Be multi-stage (builder + runtime).
2. Use `python:3.12-slim` for the runtime stage.
3. Use a non-root user with a pinned UID.
4. Include a `HEALTHCHECK`.
5. Have a proper `.dockerignore`.
6. Pin the base image by digest.
7. Use a pip cache mount.

Measure before-and-after image size and build time.

**Acceptance.** A file `notes/real-multistage.md` containing:

- The original `Dockerfile` (or a link).
- Your refactored `Dockerfile.improved`.
- A before-and-after measurement table (size, build time cold, build time warm).
- A `.dockerignore` you wrote.
- Two paragraphs: one on what changed and why; one on what you would *not* change and why.

---

## Problem 6 — The "if I had ten minutes to review your Dockerfile" question (45 min)

Open the Dockerfile review checklist from Lecture 2 Section 11. Apply it to the `Dockerfile.improved` you produced in Problem 5.

For each unchecked item:

- If you can fix it in under 5 minutes, fix it and re-tick.
- If you cannot, write one sentence explaining why not.

**Acceptance.** A file `notes/checklist.md` containing the full 15-item checklist, with each item either ticked or annotated with a "skipped because ..." rationale.

---

## Time budget

| Problem | Time |
|--------:|-----:|
| 1 | 45 min |
| 2 | 45 min |
| 3 | 45 min |
| 4 | 60 min |
| 5 | 90 min |
| 6 | 45 min |
| **Total** | **~5 h 30 min** |

---

## Why this homework looks like this

The first half of Week 2's homework (Problems 1–3) drills the *reading* and *cache mechanics* skills you will use on every PR you review for the rest of your career. The second half (Problems 4–6) drills the *operational judgement* skills you will use on every production deploy: triaging CVEs, refactoring inherited Dockerfiles, and code-reviewing your own work against a written checklist.

A junior engineer can write a Dockerfile. A senior one can review one in ten minutes and tell you the three things that are wrong with it. This homework is the first rep of that second skill.

When done, push your week-02 repo and start the [mini-project](./mini-project/README.md).
