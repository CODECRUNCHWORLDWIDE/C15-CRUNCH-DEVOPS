# Lecture 2 — The Twelve Factors, Applied

> **Outcome:** You can recite the Twelve-Factor App principles in your own words, identify which of them are obeyed and violated by a given `compose.yaml`, and refactor a service that fails three factors into one that fails none. You understand which factors are still load-bearing in 2026 and which were patched by Kubernetes, service meshes, and the modern observability stack.

The Twelve-Factor App is a methodology published by Adam Wiggins in 2011, while he was working at Heroku. The full text lives at <https://12factor.net/>. It is short — twelve pages, one per factor — and it is the single most-referenced document in cloud-native operations. Every runbook you will ever read, every CI pipeline you will write, every Kubernetes manifest you will inherit, was built by someone who either followed these twelve rules or paid the cost of not following them.

We will not present the twelve in their original Wiggins order. Wiggins's order is rhetorical; ours is **operational** — which factors hurt the most when you violate them in a Compose-shaped stack. You will know Factor III (Config) cold by the end of this week because Factor III is the one most teams get wrong, and it is the one that turns a small outage into a long one.

Compose v2 (the file format you learned in Lecture 1) is, intentionally, the shortest path between a Python web service and a twelve-factor configuration. Every factor in this lecture has a concrete Compose-shaped recipe.

---

## 1. Factor III — Config

> *Store config in the environment.*

**The factor.** Anything that varies between deployments — credentials, hostnames, feature flags, log levels — should be read from environment variables, not committed to source code. The codebase should be **identical** between dev, staging, and production; only the env differs.

**Why it matters.** When config is in code, a "dev to prod" deploy means re-merging two long-lived branches, and at some point the wrong branch goes out. Outages caused by config-in-code are common, slow to detect, and trivial to prevent.

**The Compose recipe.**

A typical Python service reads its config like this:

```python
import os

DATABASE_URL = os.environ["DATABASE_URL"]   # required, crash on missing
LOG_LEVEL    = os.environ.get("LOG_LEVEL", "INFO")
DEBUG        = os.environ.get("DEBUG", "false").lower() == "true"
```

In `compose.yaml`:

```yaml
services:
  web:
    image: crunchwriter-api:1.4.2
    environment:
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      DATABASE_URL: postgres://app:${DB_PASSWORD}@db:5432/app
    env_file:
      - .env
```

The **four sources** of environment values for a Compose service, in order of precedence (highest wins):

1. The shell that ran `docker compose up`. (Yes, your interactive shell.)
2. `--env-file <path>` on the `docker compose` command line.
3. The `environment:` key in `compose.yaml`.
4. Files listed in `env_file:`.

This is the inverse of what most people expect. **The shell wins.** That is by design — operators can override anything at runtime — but it is the source of about 30% of "it works on my machine, not on theirs" Compose problems.

The `.env` file in the **project directory** has a separate role: Compose reads it automatically and uses it for **variable substitution** in the YAML itself (`${DB_PASSWORD}` above). It is not the same as `env_file:`. Both can coexist; both *should* coexist.

**The discipline.**

- Commit `.env.example` with every key the app needs, with safe placeholder values.
- Do not commit `.env`. Add it to `.gitignore`. Always.
- Every new env var ships in *three* places in the same PR: the code that reads it, `.env.example`, and the `environment:` block in `compose.yaml`.
- Do not put secrets in `environment:` in production. Use Compose secrets (Section 8). In dev, `.env` is acceptable; in CI, use the CI provider's secret store; in prod, use a real secret manager (Week 11).

> **Status check — Factor III discipline**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  CONFIG HYGIENE — crunchwriter-dev                  │
> │                                                     │
> │  .env in .gitignore:  ●  yes                        │
> │  .env.example tracked: ●  yes (12 keys)             │
> │  Secrets in `environment:`: ●  none                 │
> │  Hardcoded URLs in code:    ●  none (last audit 5d) │
> └─────────────────────────────────────────────────────┘
> ```

---

## 2. Factor IV — Backing services

> *Treat backing services as attached resources.*

**The factor.** Databases, caches, message queues, email APIs, file stores: every one of them is a *resource attached to your app over the network*. The app should not know nor care whether the Postgres at `DATABASE_URL` is a container in `compose.yaml`, an Amazon RDS instance, or a third-party SaaS — the only difference between those is the connection string in the env.

**Why it matters.** When backing services are "attached," you can swap one without touching the app: change the URL, restart, done. When they are not — when the app has hardcoded hostnames, or runs `apt-get install postgresql` at startup, or assumes `localhost:5432` — every dev/staging/prod difference becomes a code change.

**The Compose recipe.**

In `compose.yaml`, each backing service is its own service block. In the app, the URL is read from the env:

```yaml
services:
  web:
    environment:
      DATABASE_URL: postgres://app:${DB_PASSWORD}@db:5432/app
      REDIS_URL:    redis://cache:6379/0
      SMTP_URL:     smtp://mail:1025
  db:
    image: postgres:16-alpine
  cache:
    image: redis:7-alpine
  mail:
    image: mailhog/mailhog:v1.0.1
    ports: ["127.0.0.1:8025:8025"]   # web UI
```

In production, the same app reads a `DATABASE_URL` pointing at RDS. Same code, same image, different env. That is the whole point.

**The discipline.**

- One env var per backing service. Use `_URL` suffix conventions: `DATABASE_URL`, `REDIS_URL`, `SMTP_URL`, `S3_URL`.
- Never hardcode `localhost` anywhere in the app. (You will not be on localhost in production.)
- Never construct connection strings in code from individual host/port/user/pass vars unless you have a strong reason; a single `DATABASE_URL` is what every modern library accepts.
- Run `mailhog` or `smtp4dev` in dev so the app can send mail without configuring a real SMTP relay — Factor IV gives you that for free.

---

## 3. Factor VI — Processes

> *Execute the app as one or more stateless processes.*

**The factor.** The app process should be **stateless**: it keeps nothing important in local memory or on local disk that another instance of the same process could not also serve. Any state that needs to persist belongs in a backing service (Factor IV). Anything the app caches in memory is best-effort and must survive the cache being cold.

**Why it matters.** Stateless processes are *replaceable*. Three of them can serve the same request equally well; one can crash and be replaced without losing data. Stateful processes — the kind that hold user sessions in a Python dictionary, or write user uploads to `./uploads/` — break the moment you run more than one of them.

**The Compose recipe.**

```yaml
services:
  web:
    image: crunchwriter-api:1.4.2
    deploy:
      replicas: 3   # only honored by Swarm; in Compose, see below
```

`replicas:` is Swarm-only. In dev with Compose, you can fake horizontal scale with the CLI:

```bash
docker compose up -d --scale web=3
```

If you do that and any of the three instances misbehave, you have a state leak — find it and fix it.

**The discipline.**

- Sessions go in Redis (or another shared store), not in process memory.
- Uploads go in object storage (S3, MinIO in dev), not the local filesystem.
- A `/tmp` file is fine **within a single request**. A `/tmp` file shared across requests is a bug.
- Background tasks scheduled with `threading.Timer` or APScheduler `BackgroundScheduler` cross the state boundary. Use a real worker (Celery, RQ, Arq, Dramatiq) — its own service in Compose.

**Real footgun.** A Flask login that stores the session in `session['user_id'] = 42` with the default `SECRET_KEY` and the **filesystem session backend** (an old Flask-Session default) writes a file to `/tmp/`. Scale to 2 instances and 50% of logins randomly forget the user. The fix is one config line, but it is a 90-minute debug if you have not seen it before.

---

## 4. Factor IX — Disposability

> *Maximize robustness with fast startup and graceful shutdown.*

**The factor.** Processes should start fast (sub-10-second cold start is the target) and shut down cleanly when sent SIGTERM. A graceful shutdown means: stop accepting new work, finish work in flight, close database connections, exit with code 0.

**Why it matters.** Modern orchestrators (Compose, Kubernetes, Nomad) kill and restart processes constantly: deploys, autoscaling, healthcheck failures, node moves. A process that takes 60 seconds to boot stalls every deploy. A process that ignores SIGTERM gets SIGKILL'd after the grace period — and SIGKILL means in-flight requests get dropped.

**The Compose recipe.**

```yaml
services:
  web:
    image: crunchwriter-api:1.4.2
    init: true                # use tini as PID 1; reaps zombies, forwards signals
    stop_grace_period: 30s    # how long Compose waits after SIGTERM before SIGKILL
    stop_signal: SIGTERM
```

`init: true` is **almost always the right answer** when your image's `ENTRYPOINT` is a process that does not act as a proper PID 1 (most Python processes, most Node processes). It runs `tini` as PID 1, which forwards signals correctly and reaps zombies — two responsibilities most application runtimes do not handle.

**The discipline.**

- Use `gunicorn --graceful-timeout 30 --timeout 60` (or your framework's equivalent).
- Wire a `SIGTERM` handler in your worker code; stop polling, finish the current task, close connections, exit.
- Measure cold start. If a service takes more than 10 seconds to be ready, find out why. (Common cause: importing the world at startup. Lazy-import expensive modules.)
- `start_period:` in your healthcheck buys grace; it does not fix slow startup.

---

## 5. Factor X — Dev/prod parity

> *Keep development, staging, and production as similar as possible.*

**The factor.** Reduce the gap between dev and prod across three dimensions: **time** (deploys are frequent), **personnel** (the same engineers write and run the code), and **tools** (dev runs the same backing services as prod, not a SQLite stand-in for the Postgres in production).

**Why it matters.** Parity gaps are where production-only bugs live. If dev uses SQLite and prod uses Postgres, your dev never tests the Postgres-specific behavior; you find it in prod, at 02:14 UTC, on a Saturday.

**The Compose recipe.**

Compose's existence is *the* dev/prod parity tool. Use it.

- **Run the same Postgres in dev as prod.** Same major version, ideally same minor.
- **Run the same Redis.**
- **Run the same Python interpreter and the same image tags.**
- **Do not use SQLite in dev "because it is easier."** It is not easier; it is a different database.
- **Use Compose overlays for the legitimate dev/prod differences:** `compose.yaml` for the shared core, `compose.override.yaml` for dev-only services (mailhog, a debug proxy), `compose.prod.yaml` for prod-only resource limits and replicas.

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

**The discipline.**

- Image tags pinned by digest in `compose.prod.yaml`.
- The same migration tool (Alembic, Flyway, sqitch) runs in every environment.
- The same observability stack (Prometheus + Grafana + Loki) is wired in dev. Yes, in dev. You will thank yourself in Week 10.

---

## 6. Factor II — Dependencies

> *Explicitly declare and isolate dependencies.*

**The factor.** Every dependency the app needs to run must be **declared** in a manifest (`requirements.txt`, `pyproject.toml`, `package.json`, `go.mod`) and **isolated** so it does not collide with what is already on the host (virtualenvs, containers, language-specific package managers).

**Why it matters.** Implicit dependencies — "this script needs `curl` and `jq` to be installed on the host" — make builds non-reproducible. The Dockerfile from Week 2 already enforced this for the runtime image; here, we extend it to the development workflow.

**The Compose recipe.**

The app image is the source of truth for runtime dependencies. The dev workflow runs the **same image** with a bind-mounted source tree, so an engineer never installs Python packages on their host:

```yaml
services:
  web:
    build: .
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src
        - action: rebuild
          path: ./requirements.txt
```

Editing `src/` triggers a sync; editing `requirements.txt` triggers a rebuild. No host `pip install`, no virtualenv on the laptop.

**The discipline.**

- Lockfiles in version control. `requirements.txt` should be the output of `pip-compile` or `poetry lock --no-update`, not hand-written.
- No `pip install --user` recommendations in your README. The image is the env.
- No "first, install Python 3.12 and PostgreSQL on your laptop" step. The point of Compose is that no one does that anymore.

---

## 7. Factor V — Build, release, run

> *Strictly separate build and run stages.*

**The factor.** A deploy has three stages: **build** (compile code, install deps, produce an image), **release** (combine the image with the environment's config), and **run** (start the process). They are distinct and must not be interleaved.

**Why it matters.** When build and run share a stage — when `pip install` runs at container startup, when assets are compiled on `docker compose up` — every deploy is slow, every rollback is slow, and a network blip at startup time becomes an outage.

**The Compose recipe.**

```yaml
services:
  web:
    build: .                 # the BUILD stage; happens once, produces an image
    image: crunchwriter-api:dev
    environment:             # the RELEASE stage; image + env = release
      LOG_LEVEL: INFO
      DATABASE_URL: ...
    command: ["gunicorn", ...]  # the RUN stage; starts the process
```

A clean Compose stack runs `pip install` exactly once — at `docker build` time. Never in `CMD`. Never in an `ENTRYPOINT` wrapper script. If you see `RUN pip install` followed by `CMD ["/start.sh"]` where `start.sh` *also* runs `pip install`, your `build` and `run` stages have leaked into each other.

**The discipline.**

- `docker compose build` produces an image. `docker compose up` runs it. Never the other way around.
- Releases are tagged: `crunchwriter-api:1.4.2`, never `crunchwriter-api:latest` in any file that goes to prod.
- Rollback = run the previous tag. If your rollback story includes `git revert + rebuild + redeploy`, it is not a rollback; it is a forward fix.

---

## 8. Factor XI — Logs

> *Treat logs as event streams.*

**The factor.** The app should write logs as a **stream** of events to `stdout`. The app should not manage log files, log rotation, or log shipping. The execution environment captures the stream and routes it.

**Why it matters.** When the app writes to a file inside the container, that file is invisible to every log aggregator on the planet. When it writes to `stdout`, Compose captures it (`docker compose logs`), Kubernetes captures it (`kubectl logs`), and every log driver — `json-file`, `journald`, `fluentd`, `awslogs`, `loki` — can route it onward.

**The Compose recipe.**

```yaml
services:
  web:
    image: crunchwriter-api:1.4.2
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

The default driver is `json-file`, which writes one JSON object per line to a file on the host (per container). The `max-size` and `max-file` options are the closest thing Compose has to log rotation — and you should set them, because without limits a chatty container can fill the host disk in a day.

**The discipline.**

- Use **structured logging** (`structlog`, `pino`, `zap`) and write **JSON to stdout**.
- Include a request ID and a service name in every log line. Make them grep-able.
- Never `tail -f` a log file. The file is a side effect of the log driver, not your interface.
- Send logs to Loki / Cloud Logging / Datadog via the orchestrator. We wire this up in Week 10.

---

## 9. Factor VIII — Concurrency

> *Scale out via the process model.*

**The factor.** Concurrency is achieved by running **more processes**, not by adding threads inside one process. The process model — long-lived workers managed by a process supervisor (gunicorn, uvicorn, supervisord, systemd, Compose) — scales horizontally; the thread model has hard upper bounds and language-specific footguns (Python's GIL, Node's single-threadedness).

**Why it matters.** A web service that runs a single Python process with a thousand threads will fall over under modest load. A web service that runs four gunicorn workers, each with eight threads, will hold up.

**The Compose recipe.**

```yaml
services:
  web:
    image: crunchwriter-api:1.4.2
    command: ["gunicorn", "-w", "4", "-k", "gthread", "--threads", "8", "app:create_app()"]
```

Four worker processes, each with eight threads, on a 4-vCPU host: a good starting point for a CPU-bound Python web app. Gunicorn forks each worker; you scale processes per container, then you scale containers per Compose project.

**The discipline.**

- The container is the smallest unit you scale **horizontally**.
- The process inside is the smallest unit you scale **vertically** (workers, threads, async coroutines).
- Background work goes to a worker service, never to a thread inside the web service.

---

## 10. Factor I — Codebase

> *One codebase tracked in revision control, many deploys.*

**The factor.** One app = one repo. One repo can produce many deploys (dev, staging, prod). Multiple apps that share code share via a library, not via a shared repo.

**Why it matters.** This is the principle that lets your CI pipeline make sense. Without it, "which version of the code is in production" has no answer.

**The Compose recipe.** Not much, directly — but `compose.yaml` lives **in the application repo**, and any per-environment override lives in the **same repo** (overlay file) or in a separate **infrastructure** repo with a clean handoff. Never two app repos with two slightly different `compose.yaml` files describing the same service.

---

## 11. Factor VII — Port binding

> *Export services via port binding.*

**The factor.** The app exposes its service by **binding to a port** — it does not rely on being mounted into a parent web server (the old Apache / `mod_wsgi` model). The port is the contract.

**The Compose recipe.** This is how every Compose service already works. The Dockerfile `EXPOSE`s a port, the app binds to it, Compose can publish it. There is no Apache module to configure.

**The discipline.**

- The port the app binds to is read from the env (`PORT`), with a sensible default.
- Publish ports only when needed (Lecture 1 Section 4.4).
- Do not run an in-container nginx-as-reverse-proxy unless you have a strong reason; Compose's networking already gives you that for free.

---

## 12. Factor XII — Admin processes

> *Run admin/management tasks as one-off processes.*

**The factor.** Migrations, REPL sessions, ad-hoc data fixes: run them as **one-off processes**, using the same image and the same environment as the long-running services, not as a separate "admin server."

**The Compose recipe.**

```bash
docker compose run --rm web alembic upgrade head
docker compose run --rm web python -m app.scripts.repair_inconsistent_rows
docker compose exec web python   # interactive REPL inside the running container
```

`run --rm` creates a fresh container with the same image and the same `environment:`, executes the command, and tears down. `exec` runs in an *already running* container. Both are admin processes per Factor XII.

The migration service we wrote in Lecture 1's example file is the **declarative** version of this: a service whose lifecycle is "start, run migration, exit successfully, never restart." Use either pattern; both are twelve-factor-compliant.

---

## 13. Which factors did Kubernetes patch?

Wiggins wrote the twelve factors in 2011, two years before Docker and four years before Kubernetes. Some of them have been operationally absorbed:

- **Factor VIII (Concurrency)** — Kubernetes scales pods. You declare `replicas: N`; the scheduler does the rest. Compose v2 leans on the OS process supervisor (gunicorn workers) plus `--scale`; Kubernetes has the more complete answer.
- **Factor IX (Disposability)** — Kubernetes will SIGKILL you after `terminationGracePeriodSeconds` whether you like it or not, which forces compliance.
- **Factor XI (Logs)** — every container runtime captures stdout. The factor is now table stakes.
- **Factor VII (Port binding)** — Kubernetes Services and Ingress make this the only option.

Factors that **still** trip people up in 2026 (because no orchestrator can fix them for you):

- **Factor III (Config)** — env vars vs config files vs secrets is still a discipline question, not a tooling one.
- **Factor IV (Backing services)** — coupling between app code and a specific backing service is a code-smell no orchestrator can refactor.
- **Factor VI (Processes / stateless)** — a stateful in-memory cache will bite you the day you scale.
- **Factor X (Dev/prod parity)** — Compose helps a lot, but only if you use it.

---

## 14. The twelve-factor audit checklist

Apply this to any `compose.yaml` you inherit. Each item is one factor.

- [ ] **I.** One repo per service. No `compose.yaml` lives in two repos at once.
- [ ] **II.** A lockfile is in version control; the Dockerfile installs from it.
- [ ] **III.** Every config value comes from the env. `.env.example` exists; `.env` is gitignored. No secrets in `environment:` of any committed file.
- [ ] **IV.** Every backing service is reached via a `*_URL` env var. No hardcoded `localhost`. No "first install Postgres on your laptop" instructions.
- [ ] **V.** `build` produces an image. `run` does not install dependencies. Tags are not `latest`.
- [ ] **VI.** No state in process memory that another process could not serve. Sessions in Redis or another shared store. Uploads in object storage.
- [ ] **VII.** The app binds to a port read from the env. No in-container reverse proxy.
- [ ] **VIII.** Concurrency is via processes / containers, not threads. A worker is its own service.
- [ ] **IX.** `init: true` is set or PID 1 is a proper init. `stop_grace_period:` is set. Startup is under 10 seconds.
- [ ] **X.** Same Postgres major in dev as prod. Same Redis. Same Python.
- [ ] **XI.** Logs go to stdout as JSON. The `logging:` block sets `max-size` and `max-file`.
- [ ] **XII.** Migrations and admin tasks run as `docker compose run --rm` or a one-shot service, not by `exec`-ing into a running container.

A passing score is **12 / 12**. An 11 is a yellow flag. A 9 is a service you should fix this sprint.

---

## 15. The factor that is missing

Wiggins's twelve factors do not cover **observability** — metrics and traces, distinct from logs. The 2016 follow-up "Beyond the Twelve-Factor App" by Kevin Hoffman adds three factors, the most important of which is **Telemetry**: emit metrics, traces, and health signals as a first-class concern. We will treat this as a 13th factor in this course. The recipe lives in Week 10.

Until then, the rule is: every service has a `/healthz` endpoint that returns 200 when the process is up, and a `/readyz` endpoint that returns 200 only when it can actually serve traffic (DB connection works, cache reachable, schema is current). The Compose `healthcheck:` block consumes `/healthz`. Future Kubernetes consumes both.

> **Status check — Lecture 2 mastery**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  WEEK 3 LECTURE 2 — CHECKPOINT                      │
> │                                                     │
> │  Factors recited in own words: ●  12 / 12           │
> │  Audit checklist applied:      ●  to your own stack │
> │  Distinction Wiggins/Hoffman:  ●  understood        │
> │  Anti-pattern radar:           ●  calibrated        │
> └─────────────────────────────────────────────────────┘
> ```

Continue to the exercises. Lecture 1 gave you the file shape; Lecture 2 gave you the discipline. Exercises 1–3 ask your hands to do both.
