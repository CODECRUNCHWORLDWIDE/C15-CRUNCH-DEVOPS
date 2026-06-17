# Challenge 1 — One-Command Spin-Up with Seed Data

**Time estimate.** ~3 hours.
**Required.** Docker 24+, Compose v2.22+, `make`, `curl`, `jq`.
**Reward.** Real proof that you can hand a repo to a teammate, they run one command, and 60 seconds later they have a working local dev environment with seed data — no readme-following, no missing-dep emails, no "works on my machine."

---

## Problem statement

Starting from your Exercise 3 stack, produce a single `Makefile` target — `make up` — that, from a fresh clone of the repo on a machine that has only Docker and `make` installed:

1. Generates a `.env` from `.env.example` if one does not exist.
2. Generates a random `db_password` secret if one does not exist.
3. Builds the application image.
4. Brings up `db`, `cache`, `web`, and a new `worker` service.
5. Runs database migrations against the freshly-started Postgres.
6. Seeds the database with at least **20 rows** of realistic data across at least **two tables**.
7. Returns control to the user only when every service is `(healthy)`.
8. Prints a single line: `dev environment ready — http://localhost:<port>/info`.

The whole sequence must complete in **under 60 seconds** on a 4-vCPU laptop, and it must be **idempotent**: running `make up` a second time, with the stack already up, must do nothing destructive.

A second target — `make down` — tears the stack down cleanly. A third — `make reset` — tears it down *with* volumes (`down --volumes`) and re-runs `up`. A fourth — `make smoke` — runs a curl-based smoke test against `/healthz` and `/info` and exits with a non-zero code on any failure.

---

## Starter files

You may reuse your Exercise 3 starter. The additions:

### `app/worker.py`

```python
import os
import time
import logging
import psycopg

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger("worker")

DATABASE_URL = os.environ["DATABASE_URL"]


def main():
    log.info("worker_starting")
    while True:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO events (kind, payload) VALUES (%s, %s)",
                            ("heartbeat", "{\"source\":\"worker\"}"))
                conn.commit()
        log.info("worker_heartbeat")
        time.sleep(10)


if __name__ == "__main__":
    main()
```

### `migrations/001_init.sql`

```sql
CREATE TABLE IF NOT EXISTS users (
  id           BIGSERIAL PRIMARY KEY,
  email        TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
  id         BIGSERIAL PRIMARY KEY,
  kind       TEXT NOT NULL,
  payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS events_kind_idx ON events (kind);
```

### `migrations/002_seed.sql`

```sql
INSERT INTO users (email, display_name) VALUES
  ('ana@codecrunch.example',   'Ana'),
  ('ben@codecrunch.example',   'Ben'),
  ('cira@codecrunch.example',  'Cira'),
  ('deren@codecrunch.example', 'Deren'),
  ('eli@codecrunch.example',   'Eli'),
  ('fia@codecrunch.example',   'Fia'),
  ('gabe@codecrunch.example',  'Gabe'),
  ('haru@codecrunch.example',  'Haru'),
  ('inez@codecrunch.example',  'Inez'),
  ('joon@codecrunch.example',  'Joon'),
  ('kai@codecrunch.example',   'Kai'),
  ('luca@codecrunch.example',  'Luca'),
  ('mira@codecrunch.example',  'Mira'),
  ('niko@codecrunch.example',  'Niko'),
  ('oren@codecrunch.example',  'Oren')
ON CONFLICT (email) DO NOTHING;

INSERT INTO events (kind, payload) VALUES
  ('signup',     '{"user":"ana"}'),
  ('signup',     '{"user":"ben"}'),
  ('login',      '{"user":"ana"}'),
  ('login',      '{"user":"ben"}'),
  ('signup',     '{"user":"cira"}'),
  ('heartbeat',  '{"source":"seed"}');
```

### `Makefile`

```make
SHELL := /bin/bash
.PHONY: up down reset smoke logs ps secret env

WEB_PORT ?= 8000

env:
	@test -f .env || (cp .env.example .env && echo "generated .env from .env.example")

secret:
	@mkdir -p secrets
	@test -s secrets/db_password.txt || \
	  ( openssl rand -hex 24 > secrets/db_password.txt && \
	    chmod 600 secrets/db_password.txt && \
	    echo "generated secrets/db_password.txt" )

up: env secret
	docker compose up -d --build --wait
	@echo "dev environment ready — http://localhost:$(WEB_PORT)/info"

down:
	docker compose down

reset:
	docker compose down --volumes
	$(MAKE) up

smoke:
	@curl -fsS http://localhost:$(WEB_PORT)/healthz >/dev/null && echo "healthz: ok"
	@curl -fsS http://localhost:$(WEB_PORT)/info    | jq -e '.db_ok and .cache_ok' >/dev/null && echo "info: ok"

ps:
	docker compose ps

logs:
	docker compose logs -f --tail=200
```

### `compose.yaml` (skeleton — fill in the rest)

```yaml
name: ${COMPOSE_PROJECT_NAME:-c15-w03-challenge}

networks:
  frontend: {}
  backend:
    internal: true

secrets:
  db_password:
    file: ./secrets/db_password.txt

services:
  migrate:
    image: postgres:16-alpine
    networks: [backend]
    secrets: [db_password]
    environment:
      PGHOST: db
      PGUSER: ${DB_USER}
      PGDATABASE: ${DB_NAME}
      PGPASSFILE: /run/secrets/db_password
    volumes:
      - ./migrations:/migrations:ro
    command:
      - sh
      - -c
      - |
        until pg_isready -h db -U "$$PGUSER" -d "$$PGDATABASE"; do sleep 1; done
        export PGPASSWORD="$$(cat /run/secrets/db_password)"
        for f in /migrations/*.sql; do
          echo "applying $$f"
          psql -h db -U "$$PGUSER" -d "$$PGDATABASE" -v ON_ERROR_STOP=1 -f "$$f"
        done
    depends_on:
      db:
        condition: service_healthy
    restart: "no"

  # ... web, worker, db, cache from Exercise 3 ...

volumes:
  pgdata: {}
```

The `migrate` service is the key trick. It runs to completion, exits 0, and `web` and `worker` wait on `service_completed_successfully`.

Wire the rest from Exercise 3, plus:

- `worker` with `command: ["python", "-m", "app.worker"]` and `depends_on: { migrate: service_completed_successfully, db: service_healthy }`.
- `web.depends_on` extended with `migrate: { condition: service_completed_successfully }`.

---

## Acceptance

You may submit when, **from a fresh `git clone`** on a machine with only Docker and `make`:

```bash
make up
# < 60 seconds later
# dev environment ready — http://localhost:8000/info
make smoke
# healthz: ok
# info: ok
docker compose exec db psql -U app -d app -c 'SELECT COUNT(*) FROM users;'
# returns >= 15
docker compose exec db psql -U app -d app -c 'SELECT COUNT(*) FROM events;'
# returns >= 6 (seed) and growing (worker)
```

And then:

```bash
make up   # second run, no-op
# dev environment ready — http://localhost:8000/info
```

The second run must take less than **5 seconds** and must not rebuild, recreate, or restart any service.

---

## Journal

Keep a `journal.md` open while you work. Log every dead end with a timestamp. Sample entries:

```text
2026-05-13 14:02 UTC — first `make up` hung at "waiting for db to be healthy"
2026-05-13 14:08 UTC — root cause: pg_isready was using the wrong hostname; .env had DB_HOST=localhost
2026-05-13 14:11 UTC — fixed by removing DB_HOST from .env (compose resolves "db" via service name)
2026-05-13 14:35 UTC — migrate service ran twice on the second `make up`; root cause: depends_on without restart: "no"
2026-05-13 14:38 UTC — fixed by adding restart: "no" to migrate
```

Submission must include this journal.

---

## Tips

- `--wait` on `docker compose up` is your friend. It returns control only when every service with a healthcheck is healthy.
- `service_completed_successfully` is the condition you want for `migrate`. Get it wrong (`service_started`, `service_healthy`) and the migration races with the app.
- The Postgres `entrypoint-initdb.d` mechanism runs SQL files **only on first boot of an empty volume**. Re-running migrations on an existing volume needs an explicit migrate step — which is exactly what the `migrate` service exists to do.
- The 60-second budget is achievable but not generous. If you blow it, profile: `time docker compose up -d --wait` and compare against `time docker compose pull && time docker compose build` to see where the time went.
- Idempotence comes from Compose's own logic: `up` on an already-running healthy stack is a no-op. If your `make up` does something destructive on the second run, you have an issue in the `Makefile`, not in Compose.

---

## Stretch goals

- Add a `make logs-since` target that tails logs since the last `make up`.
- Add a `make psql` target that drops you into an interactive `psql` shell against the dev database.
- Add a `make tunnel` target that exposes the Postgres on `127.0.0.1:5432` via a temporary port mapping, for use with a local GUI client.

---

## Submission

Push to a public repo `c15-week-03-spinup-<yourhandle>`. The repo must contain:

- `compose.yaml`
- `Makefile`
- `app/`
- `migrations/`
- `Dockerfile`
- `.env.example`
- `.gitignore` (must include `.env` and `secrets/`)
- `journal.md`
- `README.md` — one screen, telling the reader to run `make up`

We will grade by `git clone`-ing on a clean machine, running `make up`, and seeing whether the success line appears in under 60 seconds.
