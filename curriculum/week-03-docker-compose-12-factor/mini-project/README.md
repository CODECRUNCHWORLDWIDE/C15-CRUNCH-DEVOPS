# Mini-Project — A Local Dev Environment for a Multi-Service App

> Build a `compose.yaml`-based local development environment for a four-service application — web, worker, database, cache — that comes up with a single command, runs migrations, seeds the database, supports live source sync, ships zero secrets in source control, and survives a deliberate crash of any one service. Write the README a new teammate would read on their first day.

This is the synthesis project for Week 3. By doing it, you will touch every concept from both lectures: every Compose top-level key worth using, every service field, all twelve factors, and the operational discipline that turns "it works on my machine" into "it works on **anyone's** machine in 60 seconds."

**Estimated time.** 7 hours, spread across Thursday–Saturday.

---

## What you will build

A public GitHub repo `c15-week-03-localdev-<yourhandle>` containing:

1. **`app/`** — a real Python web service with at least:
   - Three HTTP endpoints (`/healthz`, `/readyz`, `/info`).
   - A `worker.py` that consumes from a Redis queue (or a Postgres `LISTEN/NOTIFY` channel) and writes to the database.
   - Reads every config value from `os.environ`.
   - Reads `DB_PASSWORD` from `/run/secrets/db_password` (or from a `*_FILE` env var pointing at it).
2. **`Dockerfile`** — multi-stage, slim base, non-root, `HEALTHCHECK`, `.dockerignore`. (Carry your Week 2 craft forward.)
3. **`compose.yaml`** — four services (`web`, `worker`, `db`, `cache`), plus a one-shot `migrate` service, plus a `db-backup` service behind a `profiles:` gate.
4. **`compose.override.yaml`** — dev-only overlay (`develop.watch:` for live sync, debug log levels, mailhog if you wire mail).
5. **`compose.prod.yaml`** — production-shaped overlay (digest-pinned images, resource limits, `restart: always`).
6. **`.env.example`** — committed, every key documented.
7. **`secrets/.gitkeep`** — directory present, `db_password.txt` is not.
8. **`Makefile`** — at least `up`, `down`, `reset`, `smoke`, `logs`, `psql`, `backup`.
9. **`migrations/`** — at least two `.sql` files (schema + seed) with ≥ 20 seeded rows across ≥ 2 tables.
10. **`README.md`** — explains the project for someone who has not taken C15. One screen. The reader runs `make up` and reads the success line.

---

## Acceptance criteria

- [ ] Public GitHub repo at the URL above.
- [ ] `make up` on a fresh clone brings the stack to `(healthy)` in **under 60 seconds**, on a 4-vCPU laptop.
- [ ] `make smoke` passes: `/healthz` returns 200, `/info` returns 200 with `db_ok: true` and `cache_ok: true`.
- [ ] `make backup` runs the `db-backup` service via `--profile admin run --rm`, produces a `.sql` file on the host, and exits 0.
- [ ] `make reset` tears the stack down with `--volumes`, brings it back up, and re-seeds. End state matches a fresh `make up`.
- [ ] Killing the `web` container (`docker compose kill web`) is followed by an automatic restart within 15 seconds. `make smoke` passes again without manual intervention.
- [ ] No secret values in any committed file. `git log -p` shows zero credentials.
- [ ] `compose.yaml` contains no `latest` tags. Every `image:` is pinned by tag at minimum.
- [ ] Every long-running service has a `healthcheck:` and a `restart:` policy.
- [ ] `depends_on:` is used with `condition:` on every dependency edge. No bare `depends_on:`.
- [ ] The `web` service uses `develop.watch:` for live source sync. Editing a `.py` file in `app/` reflects within 5 seconds.
- [ ] `docker compose -f compose.yaml -f compose.prod.yaml config` produces a valid file with stricter resource limits and pinned digests.
- [ ] `README.md` reads like documentation, not a sales pitch. No emoji. No marketing voice.

---

## The reference app (if you do not have your own)

If you have a `crunchwriter`-shaped project from C16, use it. Otherwise, build the following.

### `app/main.py`

```python
import os
from flask import Flask, jsonify, request
import psycopg
import redis
import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)
log = structlog.get_logger("c15-w03-mini")


def _password_from_file():
    path = os.environ.get("DB_PASSWORD_FILE")
    if path:
        with open(path) as f:
            return f.read().strip()
    return os.environ["DB_PASSWORD"]


DB_USER = os.environ["DB_USER"]
DB_NAME = os.environ["DB_NAME"]
DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_PASSWORD = _password_from_file()
DATABASE_URL = f"postgres://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
REDIS_URL = os.environ["REDIS_URL"]

app = Flask(__name__)
cache = redis.Redis.from_url(REDIS_URL, decode_responses=True)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/readyz")
def readyz():
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=2) as conn:
            conn.cursor().execute("SELECT 1;")
        cache.ping()
        return {"ready": True}
    except Exception as e:
        log.warning("readyz_failed", error=str(e))
        return jsonify({"ready": False, "error": str(e)}), 503


@app.get("/info")
def info():
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users;")
            user_count = cur.fetchone()[0]
    hits = cache.incr("info:hits")
    return jsonify({"users": user_count, "hits": hits, "service": os.environ.get("SERVICE_NAME", "c15-w03-mini")})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
```

### `app/worker.py`

```python
import os
import time
import psycopg
import redis
import structlog

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)
log = structlog.get_logger("worker")

# (same DB connection construction as main.py)
```

Wire the worker to consume from a Redis list (`BRPOP work:queue`), insert into Postgres, and ack. The web service has a `/enqueue` endpoint that pushes a job; the worker drains it.

### Required env vars (document in `.env.example`)

```text
COMPOSE_PROJECT_NAME=c15-w03-mini

DB_USER=app
DB_NAME=app
DB_PORT=5432
DB_HOST=db
DB_PASSWORD_FILE=/run/secrets/db_password

REDIS_URL=redis://cache:6379/0

WEB_HOST_PORT=8000
WEB_LOG_LEVEL=INFO
SERVICE_NAME=c15-w03-mini

WORKER_LOG_LEVEL=INFO
```

---

## Deliverable: `compare.md` is not required this week

Unlike Week 2, the deliverable is **the running stack**, not a comparison write-up. Your grade is whether a teammate can `git clone` your repo and run `make up`. Write the README with that single user in mind.

---

## Sketch of `compose.yaml`

```yaml
name: ${COMPOSE_PROJECT_NAME:-c15-w03-mini}

networks:
  frontend: {}
  backend:
    internal: true

secrets:
  db_password:
    file: ./secrets/db_password.txt

services:
  web:
    build:
      context: .
      target: runtime
    image: ${COMPOSE_PROJECT_NAME}-web:dev
    ports: ["127.0.0.1:${WEB_HOST_PORT:-8000}:8000"]
    networks: [frontend, backend]
    environment:
      DB_USER: ${DB_USER}
      DB_NAME: ${DB_NAME}
      DB_HOST: db
      DB_PORT: 5432
      DB_PASSWORD_FILE: /run/secrets/db_password
      REDIS_URL: ${REDIS_URL}
      LOG_LEVEL: ${WEB_LOG_LEVEL}
      SERVICE_NAME: ${SERVICE_NAME}
    secrets: [db_password]
    depends_on:
      db: { condition: service_healthy }
      cache: { condition: service_healthy }
      migrate: { condition: service_completed_successfully }
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=2)"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 10s
    restart: unless-stopped
    init: true
    stop_grace_period: 30s

  worker:
    image: ${COMPOSE_PROJECT_NAME}-web:dev
    command: ["python", "-m", "app.worker"]
    networks: [backend]
    environment: # same as web minus the HTTP-port stuff
      DB_USER: ${DB_USER}
      DB_NAME: ${DB_NAME}
      DB_HOST: db
      DB_PORT: 5432
      DB_PASSWORD_FILE: /run/secrets/db_password
      REDIS_URL: ${REDIS_URL}
      LOG_LEVEL: ${WORKER_LOG_LEVEL}
    secrets: [db_password]
    depends_on:
      db: { condition: service_healthy }
      cache: { condition: service_healthy }
      migrate: { condition: service_completed_successfully }
    restart: unless-stopped
    init: true

  migrate:
    image: postgres:16-alpine
    networks: [backend]
    secrets: [db_password]
    environment:
      PGUSER: ${DB_USER}
      PGDATABASE: ${DB_NAME}
      PGHOST: db
      PGPORT: 5432
    volumes:
      - ./migrations:/migrations:ro
    command:
      - sh
      - -c
      - |
        export PGPASSWORD="$$(cat /run/secrets/db_password)"
        for f in /migrations/*.sql; do
          psql -v ON_ERROR_STOP=1 -f "$$f"
        done
    depends_on:
      db: { condition: service_healthy }
    restart: "no"

  db:
    image: postgres:16-alpine
    networks: [backend]
    secrets: [db_password]
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 5s
    restart: unless-stopped

  cache:
    image: redis:7-alpine
    networks: [backend]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 2s
      retries: 5
    restart: unless-stopped

  db-backup:
    image: postgres:16-alpine
    profiles: ["admin"]
    networks: [backend]
    secrets: [db_password]
    environment:
      PGHOST: db
      PGUSER: ${DB_USER}
      PGDATABASE: ${DB_NAME}
    volumes:
      - ./backups:/backups
    command:
      - sh
      - -c
      - |
        export PGPASSWORD="$$(cat /run/secrets/db_password)"
        ts=$$(date -u +%Y%m%dT%H%M%SZ)
        pg_dump > /backups/dump-$$ts.sql

volumes:
  pgdata: {}
```

---

## Grading rubric

- **40% — `make up` works on a clean clone in under 60s.** This is the headline number.
- **20% — Twelve-factor compliance.** All twelve audit items pass. Lecture 2 Section 14.
- **20% — Resilience.** `kill web` results in automatic restart; `reset` re-seeds correctly.
- **10% — Live sync via `develop.watch:`** Code edits visible within 5 seconds.
- **10% — README quality.** Reads like documentation. A teammate could use it.

---

## Common pitfalls

- **The migrate service runs twice on the second `up`.** Cause: missing `restart: "no"`. Add it.
- **Worker starts before migrations finish.** Cause: `depends_on` without `condition: service_completed_successfully`. Fix.
- **Bind-mount shadows the `.venv` inside the image.** Cause: `./:/app` instead of `./src:/app/src`. Mount only what you edit.
- **`pg_isready` claims healthy before Postgres can take user-data connections.** Cause: `start_period:` is too short, or the user/DB check is missing from the `pg_isready` command. Pass `-U ${DB_USER} -d ${DB_NAME}`.
- **Secret file is empty.** Cause: `make secret` ran with `set -e` and `openssl` missing. Test the path independently.

---

## Submission

Push the repo, then open an issue with three things:

1. The repo URL.
2. The output of `time make up` on your machine.
3. The output of `time make reset` on your machine.

We grade by `git clone`-ing on a clean machine and running `make up`. If that succeeds in under 60 seconds and `make smoke` passes, you have shipped Week 3.

Continue to **Week 4 — GitHub Actions Beyond Hello-World** once the project is submitted. Week 4 is where this same Makefile becomes a CI pipeline.
