# Week 3 Homework

Six problems, ~6 hours total. Commit each in your week-03 repo.

---

## Problem 1 — Annotate a real `compose.yaml` (45 min)

Pick a real `compose.yaml` from one of these open-source projects:

- **Sentry self-hosted** — <https://github.com/getsentry/self-hosted/blob/master/docker-compose.yml>
- **Mastodon** — <https://github.com/mastodon/mastodon/blob/main/docker-compose.yml>
- **Gitea** — <https://docs.gitea.com/installation/install-with-docker>
- **`docker/awesome-compose`** any non-trivial stack (e.g., `react-express-mongodb`)

Copy the file into `notes/annotated.compose.yaml`. For **every service** and **every top-level block** (`volumes`, `networks`, `secrets`, `configs`), add a YAML comment that explains:

1. *What* this block declares in one phrase.
2. *Why* it is structured this way (config separation, healthcheck choice, restart policy rationale).
3. *What would break* if you removed it.

**Acceptance.** `notes/annotated.compose.yaml` contains the file with at least 30 comment lines, distributed across services and top-level blocks.

---

## Problem 2 — Twelve-factor audit on a real project (60 min)

Pick a small open-source project that ships a `compose.yaml`. Reasonable choices:

- An old project of your own.
- One of the `awesome-compose` stacks.
- Any C16 project from a peer.

Run the **twelve-factor audit checklist** from Lecture 2 Section 14 against the project. For each factor:

1. State `pass` / `fail` / `partial`.
2. If `fail` or `partial`, cite the file and line that fails it.
3. Propose one concrete change that would move it to `pass`.

**Acceptance.** `notes/audit.md` contains a 12-row table with `factor | status | evidence | proposed fix`, plus a one-paragraph summary at the bottom identifying the **two highest-impact** fixes you would do first.

---

## Problem 3 — The `depends_on` failure mode (60 min)

Take your Exercise 1 stack (web + db + cache, no healthchecks, no `condition:`). Insert a deliberate slow-start in the `db` service:

```yaml
  db:
    image: postgres:16-alpine
    command: ["sh", "-c", "sleep 15 && exec docker-entrypoint.sh postgres"]
    # ... rest as before
```

Bring it up with `docker compose up -d` (no `--wait`). Immediately hit `/info`:

```bash
docker compose up -d
sleep 1
for i in $(seq 1 30); do
  curl -s -o /dev/null -w "$(date -u +%T) status=%{http_code}\n" http://localhost:8000/info
  sleep 1
done
```

Record the output. You should see 500s (or connection-refused) for the first ~15 seconds, then a transition to 200s.

Now add a healthcheck on `db` and `depends_on: { db: { condition: service_healthy } }` on `web`. Re-run the same experiment.

**Acceptance.** `notes/depends-on.md` contains:

- The original `compose.yaml`.
- The fixed `compose.yaml`.
- Two timelines (before / after) with timestamps and HTTP codes.
- A one-paragraph explanation of why `depends_on` without `condition` was insufficient.

---

## Problem 4 — `.env`, `env_file`, `environment:`: a precedence proof (45 min)

Create a tiny `compose.yaml` with a single service that prints its `FOO` env var:

```yaml
services:
  printer:
    image: alpine:3.19
    command: ["sh", "-c", "echo FOO=$FOO; sleep 1"]
    environment:
      FOO: ${FOO:-from-default-substitution}
```

Run **eight** experiments. For each, record what the container prints:

1. No `.env`, no shell var, no `env_file`. (Expect the substitution default.)
2. `.env` contains `FOO=from-dotenv`.
3. `.env` contains `FOO=from-dotenv`; shell exports `FOO=from-shell`.
4. As (3), with `--env-file=.env.alt` where `.env.alt` has `FOO=from-alt-flag`.
5. Add `env_file: [.env.web]` with `FOO=from-envfile`. No `.env`, no shell.
6. As (5), but `environment: { FOO: from-literal }` is also set.
7. As (6), with `FOO=from-shell` exported.
8. `environment: { FOO: from-literal }` and `environment: { FOO: ${FOO:-default} }` — yes, override the same key twice in the file. Compose will accept the last one. Which does it use?

**Acceptance.** `notes/precedence.md` contains the eight experiments with input, command, and observed output, plus a final precedence table you derived from the experiments (not copied from Lecture 2).

---

## Problem 5 — From a hostile `compose.yaml` (90 min)

A teammate sent you the following `compose.yaml`. It works on their machine. List **every** anti-pattern it contains, then write a fixed version.

```yaml
version: "3.8"

services:
  app:
    image: python:latest
    command: bash -c "pip install -r requirements.txt && python app.py"
    ports:
      - "8000:8000"
    environment:
      DB_HOST: localhost
      DB_PORT: 5432
      DB_USER: postgres
      DB_PASS: hunter2
      SECRET_KEY: super-secret-key
    depends_on:
      - postgres
    restart: always
    volumes:
      - .:/app
    network_mode: host

  postgres:
    image: postgres
    environment:
      POSTGRES_PASSWORD: hunter2
    restart: always

  migrate:
    image: python:latest
    command: bash -c "pip install -r requirements.txt && python migrate.py"
    depends_on:
      - postgres
    restart: always
```

**Acceptance.** `notes/hostile.md` contains:

- A numbered list of at least **12 anti-patterns** present in this file, each with one sentence of explanation.
- A fixed `compose.yaml` that addresses every one.
- A one-paragraph note about which two anti-patterns are most likely to cause an **actual outage** versus which are merely smells.

---

## Problem 6 — One-shot admin task as a Compose service (60 min)

Take your Exercise 3 stack. Add a `db-backup` service that:

1. Runs on demand (use `profiles: [admin]` so it does not start by default).
2. Connects to the `db` service.
3. Runs `pg_dump` and writes the dump to a host-mounted volume.
4. Exits with code 0 on success, non-zero on failure.

Invoke it with `docker compose --profile admin run --rm db-backup`. Verify a dump file appears on the host. Verify it does **not** start under a plain `docker compose up`.

**Acceptance.** `notes/backup.md` contains:

- The `db-backup` service block.
- The shell session showing the invocation and the resulting dump file (size and a `head -20` of the SQL).
- A one-paragraph note on why Compose `profiles:` is the right primitive for "admin-only services" (and how this maps to Factor XII).

---

## Time budget

| Problem | Time |
|--------:|-----:|
| 1 | 45 min |
| 2 | 60 min |
| 3 | 60 min |
| 4 | 45 min |
| 5 | 90 min |
| 6 | 60 min |
| **Total** | **~6 h 00 min** |

---

## Why this homework looks like this

Problems 1–3 drill the **reading** skill — recognizing what a real `compose.yaml` says, who wrote it, and which parts of it will hurt you when the stack is under load. You will review more Compose files than you write in your career; reading them is the skill that scales.

Problems 4–6 drill the **operational discipline** skills: getting precedence right, refactoring a hostile file, and using Compose primitives (`profiles`, `run --rm`) for one-off admin work instead of `docker exec`-ing into production by hand.

A junior engineer can write a `compose.yaml`. A senior one can read someone else's `compose.yaml`, name the four things wrong with it in two minutes, and fix the most important one in five. This homework is the first rep of that second skill.

When done, push your week-03 repo and start the [mini-project](./mini-project/README.md).
