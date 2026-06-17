# Lecture 1 — The `compose.yaml` Anatomy

> **Outcome:** You can read any production `compose.yaml`, name every top-level key, explain every service-level field worth knowing, and identify the three or four things that are wrong with it. You can write a `compose.yaml` for a multi-service stack that comes up with `docker compose up`, has correct healthchecks and startup ordering, and exposes only the ports it intends to expose.

A `compose.yaml` is a *declaration*. It says: *given these services, these networks, these volumes, these secrets, and these environment values, produce a running system whose topology matches this file and whose lifecycle the user controls with one CLI verb.* Compose is not magic. Every key in the file maps to a deterministic call against the Docker Engine API; every value is either a literal, an environment-variable reference, or a structured sub-block. This lecture walks through the file shape you will read and write in the next 10 weeks of the course, in roughly the order you will write the keys in a real file.

We use **Docker 24+** with the **Compose v2** plugin (invoked as `docker compose`, with a space). The Compose specification version we cite throughout is the **Compose Spec 2.x line** maintained by the Compose Specification working group at <https://github.com/compose-spec/compose-spec>. The legacy `docker-compose` Python binary (Compose v1) was end-of-life'd in 2023 and is not used in this course.

---

## 1. The shortest correct `compose.yaml`

Before any of the keys, here is the smallest `compose.yaml` that actually does something useful:

```yaml
services:
  web:
    image: nginx:1.27-alpine
    ports:
      - "8080:80"
```

Three keys. It will come up with `docker compose up`. It will serve the default nginx welcome page at `http://localhost:8080`. It is also wrong in about five different ways — no healthcheck, no restart policy, no pinned digest, no resource limits, a published port that did not need to be published — every one of which we will fix over the next 400 lines. But it is the right starting point: every key you add from here is an *explicit choice* to make the stack more reproducible, more observable, more secure, or easier to operate.

Note what is *not* in that file: no `version:` key. The top-level `version:` was deprecated in 2020 and removed from the spec entirely in Compose v2. If you copy-paste a 2018 tutorial and see `version: "3.8"` at the top, delete that line. It is harmless but it is also a tell that the rest of the example may be out of date.

---

## 2. The eight top-level keys

A Compose file has, at most, **eight top-level keys**. You will use the first four every week. The next two when the application is non-trivial. The last two rarely, and you should know why each one exists:

| Key | What it declares |
|-----|------------------|
| `name` | The project name. Overrides the directory-name default. |
| `services` | The containers. The thing the whole file exists to describe. |
| `networks` | Named networks the services attach to. |
| `volumes` | Named volumes Docker will manage on your behalf. |
| `configs` | Read-only configuration files mounted into containers. |
| `secrets` | Read-only secret files mounted into containers at `/run/secrets/<name>`. |
| `include` | Compose files to merge into this one. (v2.20+.) |
| `x-*` | User-defined extensions. Compose ignores them; you can anchor-and-reference them. |

The file is YAML. YAML is one of three reasonable choices for configuration (the others being TOML and HCL), each with its own footguns. Compose's footgun is whitespace: a mis-indented `volumes:` under `services.web:` will silently become a *top-level* `volumes:` and you will spend twenty minutes wondering why the bind mount has no effect. Use an editor with YAML linting on, or run `docker compose config` before every commit (we will see this command in Section 11).

---

## 3. `name` — the project name

```yaml
name: crunchwriter-dev
```

`name` sets the **project name** — the prefix Compose uses for every resource it creates. If your file declares a service `web` and a volume `pgdata`, the actual Docker resources will be named `crunchwriter-dev-web-1` (container) and `crunchwriter-dev_pgdata` (volume), and the default network will be `crunchwriter-dev_default`.

If you omit `name`, Compose uses the **basename of the current directory** in lowercase, with non-alphanumerics replaced by underscores. That is fine for hobby projects; it is a footgun in a monorepo where two directories named `infra/` would collide. Always set `name` explicitly in a project anyone else will touch.

`name` may also be overridden by `--project-name` on the CLI, or by the `COMPOSE_PROJECT_NAME` env var. Precedence: CLI flag wins, then env var, then file, then directory basename.

> **Status check — project naming**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  COMPOSE PROJECT — crunchwriter-dev                 │
> │                                                     │
> │  Source:    compose.yaml `name:` key                │
> │  Resources: 4 containers, 2 volumes, 1 network      │
> │  Conflicts: none                                    │
> │  Last `up`: 2026-05-13 08:42:11 UTC                 │
> └─────────────────────────────────────────────────────┘
> ```

---

## 4. `services` — the heart of the file

`services` is a mapping whose keys are **service names** and whose values are service definitions. The service name is what your other services use as a DNS hostname on the project's default network: a service named `db` is reachable from every other container at the hostname `db`. We will return to that in Section 8.

A service definition has, in practice, about **fifteen fields worth knowing**. The Compose spec defines more — about fifty — but most are either rare, or `deploy:` keys that only Swarm interprets, or convenience aliases for things you can do with two other keys. We will cover the fifteen.

### 4.1 `image` and `build`

```yaml
services:
  web:
    image: ghcr.io/codecrunch/crunchwriter-api:1.4.2
```

`image` is the image reference Compose will `docker pull` (or use a local copy of). Pin by **tag plus digest** in any file that runs in CI or production:

```yaml
    image: ghcr.io/codecrunch/crunchwriter-api:1.4.2@sha256:9b2d8a7c...
```

If the image needs to be built locally instead, swap `image:` for `build:`:

```yaml
services:
  web:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    image: crunchwriter-api:dev
```

Setting both `build:` and `image:` is the recommended pattern: Compose builds and **tags** the result as `image:`, so subsequent `docker compose up` runs without `--build` reuse the cached image instead of rebuilding.

The `target:` key lets you build a specific stage from a multi-stage Dockerfile — useful when you have a `builder`, a `runtime`, and a `test` stage.

### 4.2 `command` and `entrypoint`

```yaml
    command: ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:create_app()"]
```

`command` overrides the image's `CMD`. `entrypoint` overrides its `ENTRYPOINT`. The same CMD-vs-ENTRYPOINT rules from Week 2 still apply: positional args after `entrypoint` become args to it, and `command` replaces the default args. Use the **list form** (exec form), never the string form, unless you specifically want shell expansion — for the same reasons we covered in Week 2 (signal forwarding, no `sh -c` wrapper).

### 4.3 `environment` and `env_file`

```yaml
    environment:
      LOG_LEVEL: INFO
      DATABASE_URL: postgres://app:${DB_PASSWORD}@db:5432/app
    env_file:
      - .env
```

`environment:` accepts a mapping or a list. Use the **mapping** form — it is less ambiguous about quoting. `env_file:` points at one or more files of `KEY=VALUE` lines. We cover precedence in Lecture 2 (Factor III: Config), but the short version is: `environment:` in the Compose file wins over `env_file:`, and both lose to a value already set in the shell that ran `docker compose up`.

### 4.4 `ports` and `expose`

```yaml
    ports:
      - "8000:8000"        # publish container 8000 to host 8000
      - "127.0.0.1:5432:5432"  # publish only to loopback
    expose:
      - "9090"             # in-network only; never reachable from host
```

`ports:` **publishes** a container port to the host. The long form `HOST_IP:HOST_PORT:CONTAINER_PORT` gives you precise control. Without an explicit host IP, Compose binds to `0.0.0.0`, which means **any interface, including external ones** — a footgun on a laptop on a coffee-shop Wi-Fi. Bind to `127.0.0.1` for dev databases. Always.

`expose:` is documentation plus an in-network firewall hint. The port is reachable from other services on the same Compose network, never from the host. Use `expose` for the worker's metrics port; use `ports` only when you actually need to hit the service from the host.

### 4.5 `volumes`

```yaml
    volumes:
      - ./src:/app/src                                    # bind mount (dev)
      - pgdata:/var/lib/postgresql/data                   # named volume
      - type: tmpfs
        target: /tmp                                       # tmpfs (RAM)
      - ./seed.sql:/docker-entrypoint-initdb.d/seed.sql:ro  # bind mount, read-only
```

Four flavors:

- **Bind mount** (`./src:/app/src`) — a path on the host appears in the container. Changes are live. Use for source code in dev, never for database data in any environment.
- **Named volume** (`pgdata:/var/lib/postgresql/data`) — Docker manages the storage. Survives `docker compose down`; deleted only on `docker compose down --volumes`. Use for stateful service data.
- **Anonymous volume** — a `volumes:` entry with only a container path (e.g., `- /var/cache`). Compose generates a name. Avoid; almost always you want a named volume so you can `inspect` it.
- **tmpfs** — RAM-backed mount. Survives nothing, fastest possible IO. Use for `/tmp` in containers that write lots of small files.

Volumes also accept the explicit long form, which is what `docker compose config` always emits and what you should learn to read:

```yaml
    volumes:
      - type: bind
        source: ./src
        target: /app/src
        read_only: false
        consistency: cached    # macOS-only optimization
```

### 4.6 `networks`

```yaml
    networks:
      - frontend
      - backend
```

By default, every service is attached to the project's default network (`<project>_default`). If you list `networks:` on a service, that list **replaces** the default — the service is *only* on the listed networks. Use named networks to enforce a topology: `web` is on `frontend` and `backend`; `db` is on `backend` only; therefore the public-facing nginx in `frontend` cannot reach `db` directly. We cover networking in Section 8.

### 4.7 `depends_on`

```yaml
    depends_on:
      db:
        condition: service_healthy
      cache:
        condition: service_started
      seeder:
        condition: service_completed_successfully
```

`depends_on:` declares startup ordering. The three conditions, in operational order:

- **`service_started`** — Compose's default. The dependency's container has been *started*. This says **nothing** about whether the process inside is ready to serve requests. The 2017 footgun: a Postgres container takes 8 seconds to be ready; your web app starts at second 0.3 and crashes against a Postgres that has not opened port 5432 yet.
- **`service_healthy`** — Wait until the dependency's healthcheck has reported healthy at least once. This is the right condition for backing services. Requires the dependency to have a `healthcheck:` defined.
- **`service_completed_successfully`** — Wait until the dependency has *exited with code 0*. The right condition for one-shot jobs: migrations, seeders, build steps that produce assets.

The pre-2020 advice ("write a `wait-for-it.sh` script in your entrypoint") is obsolete. Use `service_healthy`. Always.

### 4.8 `restart`

```yaml
    restart: unless-stopped
```

Four values, in increasing aggressiveness:

| Value | Behavior |
|-------|----------|
| `no` | Container exits, stays exited. Default. |
| `on-failure` | Restart only on non-zero exit. Optional retry count: `on-failure:5`. |
| `always` | Restart on any exit, including `docker compose down` followed by `up`. |
| `unless-stopped` | Like `always`, but a manual `docker stop` is respected. |

The right default for a long-running web service is `unless-stopped`. For a one-shot migration job, use `no`. For a worker you want to flap-test, use `on-failure`. Never use `always` on a job that should die; you will spend an hour wondering why it keeps coming back.

### 4.9 `healthcheck`

```yaml
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/healthz"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 20s
```

Five parameters:

- **`test`** — the command to run. List form (exec) or `CMD-SHELL` form for shell expressions. Exit 0 means healthy.
- **`interval`** — how often Compose runs the check. Default 30s. Tune this against the cost of the probe.
- **`timeout`** — how long to wait before declaring a check failed. Default 30s. Always shorter than `interval`.
- **`retries`** — consecutive failures before the container is `unhealthy`. Default 3.
- **`start_period`** — a grace window at startup during which failures do **not** count toward `retries`. Use this for services with a long warm-up (Postgres needs ~5s, Java services may need 60s).

A healthcheck takes precedence over any `HEALTHCHECK` declared in the image's Dockerfile. We covered Dockerfile `HEALTHCHECK` in Week 2 Section 9; this is where it gets *consumed*.

### 4.10 `deploy`

```yaml
    deploy:
      resources:
        limits:
          cpus: "1.5"
          memory: 512M
        reservations:
          memory: 128M
```

`deploy:` is a complicated block. Most of its sub-keys (`replicas`, `update_config`, `placement`, `restart_policy`) are interpreted **only by Docker Swarm**, not by `docker compose up`. The exception is `deploy.resources` — Compose v2 honors `cpus` and `memory` limits with `--compatibility` (and, since v2.21, without it).

For Compose-only stacks, the practical answer is: set `deploy.resources.limits` for memory and CPU on every long-running service, and ignore the rest. We will come back to `deploy:` in Week 7 when we move to Kubernetes — most of these fields have a 1:1 mapping in a Pod spec.

### 4.11 `develop`

```yaml
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src
        - action: rebuild
          path: ./requirements.txt
```

`develop:` is the **modern replacement** for bind-mounting source code. Added in Compose v2.22 (late 2023). `docker compose watch` reads this block and:

- `sync` — rsync the host path into the container, no rebuild.
- `rebuild` — trigger a `docker compose up --build` when the path changes.
- `sync+restart` — rsync, then restart the service process inside.

This solves the "edited Python file but the gunicorn process is still running the old code" problem without a bind mount. For Python with `gunicorn --reload`, `sync` alone is enough. For a compiled language, `sync+restart` is the right verb.

### 4.12 `user`

```yaml
    user: "1000:1000"
```

Override the user the container's main process runs as. Use this when the image's default is root and you cannot rebuild the image. Bind-mount footgun: if the container writes to a bind-mounted host directory as UID 1000, the files on the host are owned by UID 1000. Match this to your host UID with `id -u` or pass it dynamically: `user: "${UID}:${GID}"`.

### 4.13 `tmpfs` (the standalone field)

```yaml
    tmpfs:
      - /tmp:size=64m
      - /run:size=8m
```

Shortcut for `type: tmpfs` volume mounts. Useful in read-only containers that still need a writeable `/tmp`.

### 4.14 `read_only`

```yaml
    read_only: true
```

Mount the container's root filesystem read-only. Combined with explicit `tmpfs:` for `/tmp` and a named volume for the data directory, this is the strongest container hardening primitive Compose exposes. Many off-the-shelf images do not work with `read_only: true` because they write to unexpected paths; the fix is to identify those paths (`docker logs` after a crash, or `strace`) and add `tmpfs:` entries.

### 4.15 `labels`

```yaml
    labels:
      app: crunchwriter
      tier: api
      com.codecrunch.scrape: "true"
```

Labels show up in `docker inspect` and `docker ps --filter "label=..."`. Use them. Future-you grepping logs across 20 containers will be grateful.

---

## 5. `volumes` — the top-level block

```yaml
volumes:
  pgdata:
    driver: local
  cache:
    external: true     # do not create; expect this volume to already exist
```

The top-level `volumes:` block **declares** named volumes that services reference. Every named volume used in a service's `volumes:` list must appear here, even if its body is empty:

```yaml
volumes:
  pgdata: {}
  redisdata: {}
```

`external: true` means "Compose will not create this volume; it must already exist." Use for volumes that are pre-provisioned by a different tool (Terraform, a shared dev VM).

The lifecycle:

- `docker compose up` — creates any missing volumes.
- `docker compose down` — leaves volumes alone.
- `docker compose down --volumes` — *deletes named volumes*. Run this and your dev Postgres is gone.

There is no automatic deletion of *external* volumes. The `--volumes` flag respects `external: true`.

---

## 6. `networks` — the top-level block

```yaml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true       # no egress to the host bridge / Internet
  default:
    name: crunchwriter-bus   # rename the default
```

A bridge network is a Linux bridge plus an iptables NAT for outbound traffic. `internal: true` removes the NAT, isolating the network from the host's external connectivity — useful for a database tier that should not be able to phone home.

Three common patterns:

- **One network for everything** (the default). Fine for a four-service dev stack.
- **Frontend + backend split.** Web is on both, DB is on backend only. Models a real production network topology.
- **A network per concern.** Web is on `web-net`, queue is on `queue-net`, DB is on `db-net`. Excessive for dev, instructive in Kubernetes terms (each Compose network corresponds roughly to a `NetworkPolicy` in K8s).

---

## 7. `secrets` and `configs` — the top-level blocks

```yaml
secrets:
  db_password:
    file: ./secrets/db_password.txt
  api_token:
    environment: API_TOKEN

configs:
  nginx_main:
    file: ./infra/nginx.conf
```

Compose secrets and configs are both **files** mounted into the container at `/run/secrets/<name>` and `/<name>` (configurable) respectively. The two differences:

- Secrets are mounted with mode `0400` and are intended for credentials.
- Configs are mounted with mode `0444` and are intended for non-sensitive config files (e.g., an `nginx.conf`).

The `file:` form reads from the host. The `environment:` form passes a value from the shell env at `up` time. There is also `external: true` for secrets managed by an external store, but in Compose-only mode that just means "I'll create it with `docker secret create` first" and you can't, because that command is Swarm-only — so in practice the `file:` form is the one you will use in dev.

**Why Compose secrets are not Kubernetes secrets:** Compose secrets are a file mount. Kubernetes secrets are a base64-encoded blob in etcd that is *also* mounted as a file. The mount semantics look identical to your app code, which is the point — your app reads `/run/secrets/db_password` in both environments. The encryption-at-rest, the RBAC, and the rotation story are different. We will revisit in Week 11.

---

## 8. Networking in detail

Compose creates a default bridge network named `<project>_default`. Every service is attached to it unless you override with `networks:`. On that network:

- Each service is **resolvable by its service name** via the embedded DNS server Docker runs at `127.0.0.11`. A service named `db` is reachable from any other service in the project at the hostname `db`. No `/etc/hosts` editing required.
- Each service is **also** resolvable by its container name (e.g., `crunchwriter-dev-db-1`).
- Each service is **also** resolvable by any `aliases:` you set under `networks:`.
- Each service is **not** resolvable from the host. The host sees only published ports.

The four ways one service can address another:

| Address form | Example | When to use |
|--------------|---------|-------------|
| Service name | `postgres://db:5432/app` | Always. The canonical form. |
| Container name | `db.crunchwriter-dev-db-1:5432` | Almost never. Tied to Compose's naming. |
| Network alias | declared as `aliases: [postgres-primary]` | When two services must address the same target by different names. |
| Host loopback | `host.docker.internal:5432` | When the service needs to reach a process on the host (rare in Compose; common when Compose runs alongside non-containerized infrastructure). |

Two more network properties worth knowing:

- **`network_mode: host`** — the container shares the host's network namespace. No published ports, no NAT, no isolation. Linux-only. Useful for a tcpdump container. Catastrophic by default; never use in production.
- **`network_mode: "service:other"`** — share the network namespace of another service. The same trick `kubectl debug --image` uses. Useful for sidecar patterns.

---

## 9. The Compose CLI surface you'll actually use

`docker compose` has 28 subcommands. You will use eleven daily and three weekly. Memorize these:

| Command | What it does |
|---------|--------------|
| `up` | Build (if `build:` is set and `--build` is passed), create, start, attach. The verb. |
| `up -d` | Same, but detached. The other verb. |
| `down` | Stop and remove containers, networks. Volumes survive unless `--volumes`. |
| `ps` | List containers in the project, with state and ports. |
| `logs -f <svc>` | Tail logs for one service. |
| `logs --tail=200` | The last 200 lines, across all services. |
| `exec <svc> <cmd>` | Run a command in a running container. The "shell in" verb. |
| `run --rm <svc> <cmd>` | Run a one-off container (e.g., for a migration). |
| `config` | Render the merged, variable-substituted Compose file. Debugging gold. |
| `top` | `ps` (Unix) inside each service's container. |
| `build` | Build only, no start. |
| `pull` | Pull images for `image:`-based services. |
| `kill` | Send SIGKILL. Use over `down` when something is wedged. |
| `restart` | Restart without recreating. |
| `events` | Stream every Engine event for the project. |
| `wait <svc>` | Block until a service exits, print its exit code. |
| `watch` | Read the `develop:` block and live-sync source. |

`docker compose config` deserves its own paragraph. Every footgun in this lecture (a typo in `services:`, a `volumes:` block that landed at the wrong indent level, an env var that did not interpolate) becomes visible the moment you run `docker compose config`. Make it the first thing you run when something is off. It is faster than reading the file by eye.

---

## 10. Reading a real `compose.yaml`

Here is a four-service stack we will spend the rest of the week refining. Read it once end-to-end before we annotate it.

```yaml
name: crunchwriter-dev

services:
  web:
    build:
      context: .
      target: runtime
    image: crunchwriter-api:dev
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      DATABASE_URL: postgres://app:${DB_PASSWORD}@db:5432/app
      REDIS_URL: redis://cache:6379/0
    depends_on:
      db:
        condition: service_healthy
      cache:
        condition: service_started
      migrate:
        condition: service_completed_successfully
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/healthz"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 10s
    restart: unless-stopped
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src
        - action: rebuild
          path: ./requirements.txt

  worker:
    image: crunchwriter-api:dev
    command: ["python", "-m", "app.worker"]
    environment:
      DATABASE_URL: postgres://app:${DB_PASSWORD}@db:5432/app
      REDIS_URL: redis://cache:6379/0
    depends_on:
      db:
        condition: service_healthy
      cache:
        condition: service_started
    restart: unless-stopped

  migrate:
    image: crunchwriter-api:dev
    command: ["alembic", "upgrade", "head"]
    environment:
      DATABASE_URL: postgres://app:${DB_PASSWORD}@db:5432/app
    depends_on:
      db:
        condition: service_healthy
    restart: "no"

  db:
    image: postgres:16-alpine@sha256:c7af1eaeb...
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: app
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./infra/seed.sql:/docker-entrypoint-initdb.d/seed.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 5s
    restart: unless-stopped

  cache:
    image: redis:7-alpine@sha256:9b2d8a7c...
    command: ["redis-server", "--save", "", "--appendonly", "no"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 2s
      retries: 5
    restart: unless-stopped

volumes:
  pgdata: {}
```

What this file does, in plain English:

- The **`db`** service starts first and seeds itself from `seed.sql` (Postgres's official image runs every `.sql` in `/docker-entrypoint-initdb.d/` on first boot, and only on first boot — the named volume `pgdata` persists state).
- The **`cache`** service starts in parallel; its healthcheck is `redis-cli ping`.
- The **`migrate`** service waits until `db` is healthy, runs `alembic upgrade head`, and exits with code 0.
- The **`worker`** waits for `db` healthy and `cache` started.
- The **`web`** service waits for `db` healthy, `cache` started, **and** `migrate` completed successfully — so the web process never sees a database whose schema is behind the code.

One command, `docker compose up`, brings every step of that ordering up reliably.

---

## 11. Compose anti-patterns

Things you will see in tutorials and that you should not copy.

- **`version: "3.8"`** at the top of the file. Removed from the spec. Delete.
- **`latest` tag on every image.** A 6-month-old `compose.yaml` with `image: postgres:latest` produces a different system than it did at write-time. Pin tags and, in CI, pin digests.
- **`depends_on:` without `condition:`.** This is the cargo-culted advice from 2016. It only waits for the container to *start*, not to be ready. Either add `condition: service_healthy` or remove `depends_on:` entirely.
- **`restart: always` on a one-shot job.** A migration that completes successfully will be restarted forever. The Compose logs will eventually fill your disk. Use `restart: "no"` for jobs that should die.
- **Hardcoded ports in `environment:`.** Set `DATABASE_URL: postgres://...:${DB_PORT}/...` and `DB_PORT` in `.env`. We will spend a section of Lecture 2 on this.
- **`command: bash -c "while true; do ...; done"`** as a healthcheck substitute. Use `healthcheck:`. That is what it is for.
- **Secrets in `environment:`.** They end up in `docker inspect`. Use the `secrets:` top-level key, or read them at runtime from a file path the app knows about.
- **`network_mode: host`** without a strong reason. You are silently giving the container every port on the host.
- **Bind-mounting your entire repo (`.:/app`) into the container.** This shadows the `node_modules/` or `.venv/` you carefully built inside the image. Bind-mount `./src` and leave the dependency directories owned by the image.

---

## 12. The mental model

A `compose.yaml` is a graph: nodes are services, edges are `depends_on`. Compose's `up` algorithm is roughly:

1. Read the file. Validate against the spec. Substitute env vars.
2. Resolve the dependency graph. Find the start order.
3. For each service in order: pull or build image, create container, attach networks, mount volumes, start.
4. If `condition: service_healthy` is in play, poll the healthcheck endpoint of the dependency until it reports healthy or `start_period + interval * retries` elapses.
5. Stream logs (in foreground) or detach (in `-d`).

That graph is the whole mental model. Once you see it that way, every weird behavior — "why did `web` start before `db` was ready?" "why did `down --volumes` delete my data?" — becomes obvious.

> **Status check — Lecture 1 mastery**
> ```
> ┌─────────────────────────────────────────────────────┐
> │  WEEK 3 LECTURE 1 — CHECKPOINT                      │
> │                                                     │
> │  Top-level keys named:  ●  8 / 8                    │
> │  Service fields named:  ●  15 / 15                  │
> │  Anti-patterns spotted: ●  9 / 9                    │
> │  `compose config` muscle memory: ● established      │
> └─────────────────────────────────────────────────────┘
> ```

Continue to Lecture 2 — *The Twelve Factors, Applied*. We have built the file shape; next we install the discipline that makes it production-grade.
