# Exercise 3 — Env and Secrets

**Goal.** Replace every hardcoded credential in your Exercise 2 stack with environment variables read from a `.env` file. Add a `.env.example`. Verify the precedence rules between shell env, `environment:`, and `env_file:`. Move the database password from `environment:` to a Compose **secret**, mounted at `/run/secrets/db_password`. Confirm the secret never appears in `docker inspect`.

**Estimated time.** 90 minutes.

---

## Why we are doing this

A real production system has tens of config values and several secrets. Hardcoding any of them is a maintenance bug at best and a credential-leak at worst. By the end of this exercise you will have a stack whose `compose.yaml` is **safe to commit verbatim** — no secrets, no environment-specific URLs, no `localhost` shortcuts.

You will also have, in your fingers, the precedence order between the four sources of env values. That ordering is in Lecture 2 Section 1; by the end of this exercise it will be in muscle memory.

---

## Setup

Continue from Exercise 2:

```bash
cd ~/c15/week-03/ex-01-three-service
docker compose down
```

---

## Step 1 — Extract config to `.env` (~20 min)

Create `.env`:

```text
COMPOSE_PROJECT_NAME=c15-ex01

DB_USER=app
DB_PASSWORD=devpass
DB_NAME=app
DB_PORT=5432

REDIS_PORT=6379

WEB_HOST_PORT=8000
WEB_LOG_LEVEL=INFO
SERVICE_NAME=c15-ex01-web
```

Create `.env.example` (commit this one; it is the public contract):

```text
COMPOSE_PROJECT_NAME=c15-ex01

# Database
DB_USER=app
DB_PASSWORD=change-me
DB_NAME=app
DB_PORT=5432

# Cache
REDIS_PORT=6379

# Web
WEB_HOST_PORT=8000
WEB_LOG_LEVEL=INFO
SERVICE_NAME=c15-ex01-web
```

Add `.env` to `.gitignore`:

```text
.env
.compose.rendered.yaml
__pycache__
.venv
```

Now rewrite `compose.yaml` to read every value from the env:

```yaml
name: ${COMPOSE_PROJECT_NAME:-c15-ex01}

networks:
  frontend: {}
  backend:
    internal: true

services:
  web:
    build: .
    image: c15-ex01-web:dev
    ports:
      - "127.0.0.1:${WEB_HOST_PORT:-8000}:8000"
    networks:
      - frontend
      - backend
    environment:
      DATABASE_URL: postgres://${DB_USER}:${DB_PASSWORD}@db:${DB_PORT}/${DB_NAME}
      REDIS_URL: redis://cache:${REDIS_PORT}/0
      LOG_LEVEL: ${WEB_LOG_LEVEL:-INFO}
      SERVICE_NAME: ${SERVICE_NAME}
    depends_on:
      db:
        condition: service_healthy
      cache:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=2)"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 10s
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    networks:
      - backend
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
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
    networks:
      - backend
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 2s
      retries: 5
    restart: unless-stopped

volumes:
  pgdata: {}
```

Render and verify:

```bash
docker compose config
```

Every `${VAR}` reference should resolve to the value from `.env`. If you see a literal `${...}` in the output, you have a typo.

Bring it up:

```bash
docker compose up -d --wait
curl -s http://localhost:${WEB_HOST_PORT:-8000}/info | jq .
```

---

## Step 2 — Precedence experiment (~20 min)

The four sources of env values, in order of precedence (highest wins): shell env, `--env-file` flag, `environment:` in the file, `env_file:` in the file.

Prove it. Make a copy of `.env` named `.env.alt`:

```bash
cp .env .env.alt
sed -i.bak 's/^SERVICE_NAME=.*/SERVICE_NAME=from-env-alt/' .env.alt
```

Add `env_file:` to the `web` service. Edit `compose.yaml` in the `web` service block:

```yaml
    env_file:
      - .env.web
```

Create `.env.web`:

```text
SERVICE_NAME=from-env-file
```

And in the same `web.environment:` block, hardcode:

```yaml
    environment:
      # ... existing ...
      SERVICE_NAME: from-environment-block
```

Render to see the merge:

```bash
docker compose config | grep -A1 SERVICE_NAME
```

You should see `from-environment-block` (the file's `environment:` wins over `env_file:`).

Now set it from the shell:

```bash
SERVICE_NAME=from-shell docker compose config | grep -A1 SERVICE_NAME
```

If your `environment:` block uses `${SERVICE_NAME}` (variable substitution), the shell will win. If it uses a literal value (`SERVICE_NAME: from-environment-block`), the literal still wins. **Variable substitution and the `environment:` key are not the same thing** — substitution happens at file-parse time; the `environment:` key is what is actually passed to the container.

Document what you found. The full precedence table:

| Source | Wins over | Loses to |
|--------|-----------|----------|
| Shell env (substitutes into the file) | `.env` defaults | nothing |
| `--env-file` (substitutes into the file) | `.env` defaults | shell |
| `environment:` (literal) in the file | `env_file:` | shell substituted into the literal |
| `env_file:` | nothing | everything else |
| `.env` (substitution defaults) | nothing | everything else |

Restore your stack to its Step 1 state before continuing:

```bash
rm .env.web .env.alt .env.alt.bak
# remove the experimental env_file: entry from compose.yaml
docker compose up -d --wait
```

---

## Step 3 — Move the DB password to a Compose secret (~25 min)

The `DB_PASSWORD` variable is currently in `.env`, which is gitignored — fine for dev, not great in shared CI. Compose **secrets** are the next step up: a file mounted at `/run/secrets/<name>` inside the container, never visible in `docker inspect`.

Create the secret file:

```bash
mkdir -p secrets
echo -n "devpass" > secrets/db_password.txt
chmod 600 secrets/db_password.txt
```

Add `secrets/` to `.gitignore`:

```text
.env
secrets/
.compose.rendered.yaml
__pycache__
.venv
```

Add a top-level `secrets:` block to `compose.yaml`:

```yaml
secrets:
  db_password:
    file: ./secrets/db_password.txt
```

Reference it from the `db` service:

```yaml
  db:
    image: postgres:16-alpine
    networks:
      - backend
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
      POSTGRES_DB: ${DB_NAME}
    secrets:
      - db_password
    volumes:
      - pgdata:/var/lib/postgresql/data
    # healthcheck as before
    # restart as before
```

The Postgres official image reads `POSTGRES_PASSWORD_FILE` if set, in preference to `POSTGRES_PASSWORD`. Many official images support a `*_FILE` variant for exactly this reason. Read the image's documentation; assume nothing.

For `web`, you have two choices:

**Option A — pass the secret file path to the app:**

```yaml
    secrets:
      - db_password
    environment:
      DATABASE_URL_TEMPLATE: postgres://${DB_USER}:%s@db:${DB_PORT}/${DB_NAME}
      DB_PASSWORD_FILE: /run/secrets/db_password
```

Then read the file in code:

```python
import os

template = os.environ["DATABASE_URL_TEMPLATE"]
with open(os.environ["DB_PASSWORD_FILE"]) as f:
    password = f.read().strip()
DATABASE_URL = template % password
```

**Option B — keep `DATABASE_URL` in `.env` for dev simplicity, and document that production will use the secret-file pattern.**

For this exercise, do **Option A** for the practice. Update `app/main.py` to read the password from the file.

Re-up:

```bash
docker compose down
docker compose up -d --build --wait
curl -s http://localhost:${WEB_HOST_PORT:-8000}/info | jq .
```

Confirm the secret is invisible in `docker inspect`:

```bash
docker compose ps -q web | xargs docker inspect | jq '.[0].Config.Env'
```

You should see no `DB_PASSWORD` value. The password is on disk inside the container at `/run/secrets/db_password`, with mode `0400`, but not in the container's env.

Confirm it is reachable from inside:

```bash
docker compose exec web cat /run/secrets/db_password
# devpass
docker compose exec web ls -la /run/secrets/
# -r-------- 1 root root 7 ... db_password
```

---

## Step 4 — A short post-mortem on a fake secret leak (~10 min)

Pretend, for two minutes, that you accidentally committed `.env` to a public repo with `DB_PASSWORD=hunter2`. Write the **mitigation runbook** in `notes.md`:

1. Rotate the password (in the database, in the secret store, in `.env`).
2. Restart every service that reads the password.
3. Audit logs for any access using the old credential.
4. Run a git history rewrite (`git filter-repo --invert-paths --path .env`) and force-push. Note: the secret may already be cached by GitHub search, scrapers, etc.
5. **Always assume the secret is compromised the moment it leaves your laptop.** Rotation is mandatory; cleanup is a courtesy.

You will not actually rotate anything for this exercise. Writing the runbook is the deliverable.

---

## Step 5 — Write it up (~10 min)

Create `notes.md` in the exercise directory containing:

1. The final `compose.yaml`.
2. The final `.env.example`.
3. The precedence table you confirmed in Step 2, with at least one cell annotated "I verified this with `docker compose config`."
4. The output of `docker inspect` showing the absence of `DB_PASSWORD` in the container's env.
5. The fake-leak runbook from Step 4.

**Acceptance.** `notes.md` exists; `.env.example` is committed and `.env` is in `.gitignore`; the `inspect` output shows the password is not in the container's `Env` array.

---

## What you should walk away knowing

- `.env` is for substitution; `env_file:` is for runtime; `environment:` is for explicit values. Three different things, often confused.
- Shell env wins over everything, including the file. Use this for one-off overrides.
- Compose secrets are file mounts at `/run/secrets/<name>`. They are not in `docker inspect` and not in `env`.
- Most official images support a `*_FILE` env var that points at a secret file. Use it.
- A leaked secret is compromised forever. Rotate first, clean up second.

You have completed Week 3's exercises. Move on to the [challenge](../challenges/challenge-01-one-command-spinup-with-seed-data.md) and then the [mini-project](../mini-project/README.md).
