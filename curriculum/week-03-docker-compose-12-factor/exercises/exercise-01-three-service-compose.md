# Exercise 1 — Three-Service Compose

**Goal.** Wire a Flask app, a Postgres database, and a Redis cache into a single `compose.yaml`. Bring the stack up with one command. Confirm service-to-service DNS works. Tear it down without losing the database.

**Estimated time.** 120 minutes (60 min building, 30 min experimenting, 30 min writing it up).

---

## Why we are doing this

Lecture 1 gave you the file shape. This exercise gives you the muscle memory: every key you wrote about, you will now type. By the end you will have an opinion about every field — which ones you need on every service, which ones you reach for only sometimes, and which ones you wrote into a tutorial three years ago and never used again.

---

## Setup

### Working directory

```bash
mkdir -p ~/c15/week-03/ex-01-three-service
cd ~/c15/week-03/ex-01-three-service
```

### Verify Compose version

```bash
docker compose version
# Expect: Docker Compose version v2.22.x or newer
```

If you see "Docker Compose version 1.x" or "command not found," install the v2 plugin from <https://docs.docker.com/compose/install/>.

### Starter files

Create `app/main.py`:

```python
import os
import sys
import platform
import psycopg
import redis
from flask import Flask, jsonify

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL    = os.environ["REDIS_URL"]
SERVICE_NAME = os.environ.get("SERVICE_NAME", "c15-ex01")

app = Flask(__name__)
cache = redis.Redis.from_url(REDIS_URL, decode_responses=True)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/info")
def info():
    db_ok = True
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                db_version = cur.fetchone()[0]
    except Exception as e:
        db_ok = False
        db_version = str(e)

    cache_ok = True
    try:
        cache.ping()
        hits = cache.incr("info:hits")
    except Exception as e:
        cache_ok = False
        hits = -1

    return jsonify({
        "service":   SERVICE_NAME,
        "python":    sys.version.split()[0],
        "platform":  platform.platform(),
        "db_ok":     db_ok,
        "db_version": db_version,
        "cache_ok":  cache_ok,
        "hits":      hits,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
```

Create `requirements.txt`:

```text
flask==3.0.3
psycopg[binary]==3.2.1
redis==5.0.7
gunicorn==22.0.0
```

Create `Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
EXPOSE 8000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "app.main:app"]
```

Create `.dockerignore`:

```text
.git
.venv
__pycache__
*.pyc
.env
```

---

## Step 1 — The minimal `compose.yaml` (~20 min)

Create `compose.yaml`:

```yaml
name: c15-ex01

services:
  web:
    build: .
    image: c15-ex01-web:dev
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      DATABASE_URL: postgres://app:devpass@db:5432/app
      REDIS_URL: redis://cache:6379/0
      SERVICE_NAME: c15-ex01-web

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: devpass
      POSTGRES_DB: app
    volumes:
      - pgdata:/var/lib/postgresql/data

  cache:
    image: redis:7-alpine

volumes:
  pgdata: {}
```

Bring it up:

```bash
docker compose up -d --build
docker compose ps
```

Hit the endpoints:

```bash
curl -s http://localhost:8000/healthz | jq .
curl -s http://localhost:8000/info | jq .
```

**Acceptance.** `/info` returns `db_ok: true`, `cache_ok: true`, and `hits` increments on every call.

---

## Step 2 — Service-to-service DNS (~15 min)

Open a shell inside the `web` container and resolve the other services by name:

```bash
docker compose exec web bash -c 'getent hosts db cache'
```

Expect two lines, each with an internal IP and the service name. That is the embedded Docker DNS server (`127.0.0.11`) at work.

Now from the host, try the same:

```bash
getent hosts db || nslookup db || echo "host cannot resolve service names; expected"
```

The host cannot resolve `db` — that name only exists *inside* the Compose network. Confirm by hitting Postgres from inside the container:

```bash
docker compose exec web bash -c 'apt-get update -qq && apt-get install -y -qq postgresql-client >/dev/null && psql "$DATABASE_URL" -c "SELECT 1;"'
```

(Yes, that is an `apt-get install` at runtime. In real life you would put `postgresql-client` in the Dockerfile.)

Write down: **which hostnames resolve inside the network, and which do not?** This is the foundation of every "why can't my app reach the DB" support thread you will ever read.

---

## Step 3 — Render the merged file with `compose config` (~10 min)

```bash
docker compose config > .compose.rendered.yaml
diff -u compose.yaml .compose.rendered.yaml | head -80
```

Notice:

- `version:` is added at the top (Compose adds it for backward compat; ignore it).
- Volume definitions are expanded to their long form.
- Environment variables are fully resolved.
- The default network appears explicitly.

This is the file Compose actually evaluates. When something is mysterious, this is where you look.

---

## Step 4 — `docker compose down` vs `down --volumes` (~15 min)

Stop the stack but keep the data:

```bash
docker compose down
docker volume ls | grep c15-ex01
```

Expect the `c15-ex01_pgdata` volume to still be there.

Bring the stack back up:

```bash
docker compose up -d
curl -s http://localhost:8000/info | jq .hits
```

The hit counter is stored in **Redis** and Redis has no persistent volume in this exercise. The counter resets to `1`. (Add a volume to `cache` and run this experiment again as a stretch.)

Now nuke everything, including volumes:

```bash
docker compose down --volumes
docker volume ls | grep c15-ex01 || echo "no volumes left; expected"
```

If you had real data in Postgres, this command just deleted it. Get used to typing it carefully.

---

## Step 5 — Add explicit networks (~20 min)

Replace the top of `compose.yaml`:

```yaml
name: c15-ex01

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true   # no Internet egress for services on this network

services:
  web:
    build: .
    image: c15-ex01-web:dev
    ports:
      - "127.0.0.1:8000:8000"
    networks:
      - frontend
      - backend
    environment:
      DATABASE_URL: postgres://app:devpass@db:5432/app
      REDIS_URL: redis://cache:6379/0
      SERVICE_NAME: c15-ex01-web

  db:
    image: postgres:16-alpine
    networks:
      - backend
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: devpass
      POSTGRES_DB: app
    volumes:
      - pgdata:/var/lib/postgresql/data

  cache:
    image: redis:7-alpine
    networks:
      - backend

volumes:
  pgdata: {}
```

Re-up:

```bash
docker compose down
docker compose up -d --build
curl -s http://localhost:8000/info | jq .
```

Verify the isolation: from `db`, try to reach the Internet:

```bash
docker compose exec db sh -c 'apk add --no-cache curl >/dev/null 2>&1 || true; curl -sS --max-time 3 https://example.com || echo "no egress; expected"'
```

The `apk add` fails (no Internet on `backend`), or the `curl` times out. That is `internal: true` doing its job.

Verify `web` can still reach the Internet via `frontend`:

```bash
docker compose exec web bash -c 'curl -sS --max-time 3 -o /dev/null -w "%{http_code}\n" https://example.com'
```

Expect `200`.

---

## Step 6 — Write it up (~30 min)

Create `notes.md` in the exercise directory containing:

1. The final `compose.yaml`.
2. The output of `docker compose ps` for the running stack.
3. A 3-row table: service name, hostname (inside the network), reachable from host (yes/no).
4. One paragraph on what `docker compose config` showed you that you would not have spotted by reading `compose.yaml`.
5. One paragraph on the difference between `down` and `down --volumes`, in your own words.

**Acceptance.** `notes.md` exists, the table has accurate data from your actual stack, and the two paragraphs are written in your own words, not Lecture 1's.

---

## What you should walk away knowing

- The `services:` / `volumes:` / `networks:` triad is the whole shape of a Compose file.
- Service names are hostnames on the project network. The host cannot resolve them.
- `docker compose config` is the truth; `compose.yaml` is your source of intent.
- `down --volumes` is destructive. Type it on purpose.
- `internal: true` removes Internet egress. Useful for the database tier.

Continue to [Exercise 2 — Healthchecks and Restart](./exercise-02-healthchecks-and-restart.md). This stack still has two bugs: nothing waits for `db` to be ready before starting `web`, and a crashed `web` does not recover. We fix both next.
