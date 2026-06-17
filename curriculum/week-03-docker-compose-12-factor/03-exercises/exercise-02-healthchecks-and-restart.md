# Exercise 2 — Healthchecks and Restart

**Goal.** Add a `healthcheck:` to every service in the Exercise 1 stack, gate `depends_on:` with `condition: service_healthy`, set restart policies that match each service's role, and observe what happens when you deliberately crash a service.

**Estimated time.** 90 minutes.

---

## Why we are doing this

The Exercise 1 stack has two latent bugs. First, on a cold boot, the `web` service can start before Postgres has finished initializing — the first few requests will see 500s. Second, if the `web` process crashes (an OOM, an unhandled exception in a worker), nothing brings it back. Both are one-line fixes, but you have to write the right line in the right place.

By the end you will have a stack that boots in a deterministic order, recovers from crashes, and reports its health in a way Compose can consume.

---

## Setup

Continue from Exercise 1:

```bash
cd ~/c15/week-03/ex-01-three-service
docker compose down
```

If you removed the directory, recreate it from Exercise 1's starter files. Pin the `compose.yaml` from Exercise 1 Step 5 (the version with `frontend` + `backend` networks) as your starting point.

---

## Step 1 — Healthchecks per service (~25 min)

Add a `healthcheck:` to each service.

**`web`** — HTTP healthcheck on `/healthz`:

```yaml
  web:
    # ... existing fields ...
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=2)"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 10s
```

We use `python -c` instead of `curl` because the `python:3.12-slim` image does not ship `curl`. If you would rather add `curl`, do it in the Dockerfile with `RUN apt-get update && apt-get install -y --no-install-recommends curl` — but the Python one-liner is fewer image-bytes.

**`db`** — `pg_isready`:

```yaml
  db:
    # ... existing fields ...
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 5s
```

**`cache`** — `redis-cli ping`:

```yaml
  cache:
    # ... existing fields ...
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 2s
      retries: 5
```

Bring the stack up and watch the health column:

```bash
docker compose up -d --build
docker compose ps
```

Wait 15 seconds. Re-run `docker compose ps`. The `STATUS` column should now show `(healthy)` on all three services.

Tail the events to see the healthchecks happen:

```bash
docker compose events --json | jq -r '"\(.time) \(.service // "-") \(.action)"' &
sleep 15
kill %1
```

You will see `health_status: healthy` events for each service. That is what `depends_on: service_healthy` listens for.

---

## Step 2 — `depends_on` with `condition` (~15 min)

Add the dependency block to `web`:

```yaml
  web:
    # ... existing fields ...
    depends_on:
      db:
        condition: service_healthy
      cache:
        condition: service_healthy
```

Now the cold-boot race is fixed. Force a cold boot to verify:

```bash
docker compose down --volumes
time docker compose up -d --wait
```

The `--wait` flag blocks until every service is healthy. Note the elapsed time — typically 15–25 seconds, dominated by Postgres's initial `initdb`.

Hit `/info`:

```bash
curl -s http://localhost:8000/info | jq '.db_ok, .cache_ok'
```

Expect `true` on the very first request. Before this exercise, that was a coin flip.

---

## Step 3 — Restart policies (~15 min)

Add `restart: unless-stopped` to every long-running service:

```yaml
  web:
    # ...
    restart: unless-stopped

  db:
    # ...
    restart: unless-stopped

  cache:
    # ...
    restart: unless-stopped
```

Re-up:

```bash
docker compose up -d
```

Now kill the `web` process from inside its container:

```bash
docker compose exec web bash -c 'kill -9 1'
```

The container exits. Watch:

```bash
docker compose ps
# STATUS for web will briefly be "Exited (137)"
sleep 5
docker compose ps
# STATUS for web should be "Up (healthy)" again
```

Restart policy: **observed**. Hit `/info`:

```bash
curl -s http://localhost:8000/info | jq .
```

Expect a working response, with `hits` reset (the in-memory state went with the container, but Postgres data survived because of the named volume).

> **Status check — restart loop**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  SERVICE STATUS — c15-ex01 / web                    │
> │                                                     │
> │  Health:   ● healthy        last crash: 14s ago     │
> │  Restarts: 1 (auto)         exit code:  137 (SIGKILL)│
> │  Policy:   unless-stopped   Owner:      Compose      │
> │  Action:   none required                            │
> └─────────────────────────────────────────────────────┘
> ```

---

## Step 4 — A flapping service (~15 min)

Add a deliberately broken service to demonstrate `on-failure`:

```yaml
  flaky:
    image: alpine:3.19
    command: ["sh", "-c", "echo 'crashing in 3s'; sleep 3; exit 1"]
    restart: on-failure:5
    networks:
      - backend
```

Bring it up:

```bash
docker compose up -d flaky
docker compose logs -f flaky
```

The container will crash, restart, crash, restart — five times — and then stop. `on-failure:5` caps it. Without the cap, it would loop forever.

In a real outage, the cap on `on-failure` is the line between a logging volume that grows by 10 MB and one that fills the disk in an hour. Always cap.

Tear down the flaky service:

```bash
docker compose rm -fsv flaky
```

(`rm -fsv`: force, stop first, remove anonymous volumes.)

---

## Step 5 — `start_period` and slow-starting services (~10 min)

Simulate a slow database. Stop the stack:

```bash
docker compose down
```

Temporarily set `db.healthcheck.start_period` to `1s` and re-up:

```bash
docker compose up -d --wait
```

You may see `web` give up waiting because Postgres took longer than `1s + interval * retries` to be healthy. (If it does not, your machine is fast — try `start_period: 0s` and `retries: 2`.)

Restore `start_period: 5s` and `retries: 10`. Re-up.

The lesson: `start_period` is the **grace window**. Set it generously for slow-starting services (Postgres, Java services, anything with warmup). It does not cost performance — it only delays the *failure* declaration.

---

## Step 6 — Write it up (~10 min)

Create `notes.md` in the exercise directory containing:

1. The final `compose.yaml`.
2. The output of `docker compose ps` showing the `STATUS (healthy)` column.
3. A timeline (UTC timestamps) of your Step 3 experiment: `kill -9 1` → container exit → restart → healthy again.
4. A one-paragraph explanation of `start_period` in your own words.
5. One sentence: when would you use `restart: always` vs `restart: unless-stopped`?

**Acceptance.** `notes.md` exists, the timeline has real timestamps, and the answer to the `always` vs `unless-stopped` question is correct (hint: it has to do with what a manual `docker stop` should mean).

---

## What you should walk away knowing

- A service is "healthy" only when its `healthcheck:` says so. Compose does not infer health.
- `depends_on: service_healthy` is the cure for every "DB not ready" bug from 2015.
- `restart: unless-stopped` is the right default for long-running services.
- `on-failure:N` is the right cap for jobs that should retry but not loop forever.
- `start_period` is grace, not timeout. Use it.

Continue to [Exercise 3 — Env and Secrets](./exercise-03-env-and-secrets.md). The stack is now resilient; next, we make it configurable without committing credentials.
