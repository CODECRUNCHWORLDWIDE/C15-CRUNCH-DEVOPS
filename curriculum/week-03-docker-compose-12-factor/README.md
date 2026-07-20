# Week 3 — `docker compose` and the 12-Factor App

> *One container is a science project. Three containers wired together with a shared network, a healthcheck, and a restart policy is a system. The difference is one YAML file.*

Welcome to Week 3 of **C15 · Crunch DevOps**. Week 1 told you what a container *is*. Week 2 made you build one well. Week 3 is where one container becomes a **system of containers** — a web app talking to a database, a worker draining a queue, a cache in front of both — and where most of the confusion around Docker networking, volumes, and config finally resolves.

We focus this week on **Docker Compose** (the modern `docker compose` plugin, Compose specification 2.x) and the **Twelve-Factor App** methodology that Heroku published in 2011 and that every production system you will ever touch either obeys or pays the cost of ignoring. By Sunday you will have a `compose.yaml` for a four-service stack that spins up with a single command, seeds itself with data, declares healthchecks, restarts on failure, reads its configuration from the environment, and ships zero secrets in source control.

Week 2's mini-project gave you one good image. Week 3's mini-project gives you a **one-command local development environment** that resembles the one you will write for production in Phase 2.

---

## Learning objectives

By the end of this week, you will be able to:

- **Read** any `compose.yaml` and explain, line by line, what each top-level key (`services`, `networks`, `volumes`, `secrets`, `configs`) does and what would break if it were removed.
- **Write** a `compose.yaml` for a multi-service stack (web + db + cache + worker) that starts with `docker compose up`, runs every service as non-root where the image allows it, defines a healthcheck per service, and orders startup with `depends_on: condition: service_healthy`.
- **Distinguish** Compose's three networking modes (default bridge, custom bridge, host) and the four ways services can address each other on the default network — by service name, by container name, by alias, and by published port — without looking them up.
- **Apply** the Twelve-Factor App methodology to a real service: separate config from code, treat backing services as attached resources, run as a stateless process, dispose fast, keep dev/prod parity.
- **Manage** environment configuration the right way: a committed `.env.example`, an uncommitted `.env`, the `environment:` key in `compose.yaml`, and the precedence rules between them.
- **Use** Docker Compose secrets (the `secrets:` top-level key) for credentials that should *not* live in `.env`, and explain why Compose secrets are not Kubernetes secrets and not Vault.
- **Diagnose** a stuck Compose stack: read `docker compose ps`, `docker compose logs`, `docker compose top`, and a failing healthcheck output, and tell which service is the root cause.
- **Defend** the choice of bind mount vs named volume vs tmpfs for a given workload (source code, database data, ephemeral build artifacts).

---

## Prerequisites

This week assumes you have completed **Weeks 1 and 2 of C15** and pushed both mini-projects. Specifically:

- You can build a multi-stage Dockerfile for a Python web service and the resulting image is under 150 MB.
- You can read `docker images`, `docker history`, `docker inspect`, and `docker logs` without referring to `--help`.
- You have a Docker (or Podman with the compose plugin) install on your machine and `docker compose version` returns a v2.x release. **Compose v1** (the Python `docker-compose` binary) was retired in 2023; this week uses **Compose v2 only**.

If `docker compose version` returns "command not found," install the Compose plugin: <https://docs.docker.com/compose/install/>. Confirm with `docker compose version` (note: a *space*, not a hyphen — that distinguishes v2 from the deprecated v1).

We assume **Docker 24+** with **Compose v2.24+** throughout. Specific Compose-spec features used this week (the `develop:` block, named `configs`, the `service_completed_successfully` condition) require v2.22 or newer.

---

## Topics covered

- The Compose specification 2.x — what it is, who owns it (the Compose Specification working group, not Docker Inc.), and why `compose.yaml` is now the canonical filename.
- The eight top-level keys: `name`, `services`, `networks`, `volumes`, `configs`, `secrets`, `include`, `x-*` extensions.
- The service block in depth: `image`, `build`, `command`, `entrypoint`, `environment`, `env_file`, `ports`, `expose`, `volumes`, `networks`, `depends_on`, `restart`, `healthcheck`, `deploy`, `develop`.
- Networking: the default `<project>_default` bridge, custom named networks, service-to-service DNS resolution, the difference between `ports:` (published) and `expose:` (in-network only).
- Volumes: bind mounts (`./src:/app/src`) vs named volumes (`pgdata:`) vs tmpfs vs anonymous volumes — when to reach for each.
- Healthchecks: the four parameters (`test`, `interval`, `timeout`, `retries`, `start_period`), and the dependency primitive `service_healthy`.
- Restart policies: `no`, `on-failure`, `always`, `unless-stopped`. What each one does to a flapping service and what your monitoring will look like for each.
- Environment configuration: the four sources (`environment:`, `env_file:`, the shell, the `--env-file` flag) and their precedence order.
- Compose secrets: file-based and external. Why this is the right primitive in dev, the wrong primitive in production, and what Kubernetes secrets / Vault / AWS Secrets Manager are for.
- The **Twelve-Factor App** — all twelve principles, in C15's order of operational impact: III Config, IV Backing services, VI Processes, IX Disposability, X Dev/prod parity, II Dependencies, V Build/release/run, XI Logs, then the rest.
- Compose anti-patterns: hardcoded ports, `depends_on:` without `condition:`, `latest` tags, root containers, secrets in `environment:`, `restart: always` on a job that should die.
- The `docker compose` CLI surface you will actually use: `up`, `down`, `ps`, `logs`, `exec`, `run`, `config`, `top`, `events`, `kill`, `restart`, `pull`, `build`.

---

## Weekly schedule

The schedule below adds up to approximately **36 hours**. Some sections click in 20 minutes; others need 3 hours. The total is what matters, not the daily split.

| Day       | Focus                                              | Lectures | Exercises | Challenges | Quiz/Read | Homework | Mini-Project | Self-Study | Daily Total |
|-----------|----------------------------------------------------|---------:|----------:|-----------:|----------:|---------:|-------------:|-----------:|------------:|
| Monday    | Compose YAML anatomy (Lecture 1)                   |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Tuesday   | Twelve-factor applied (Lecture 2)                  |    2h    |    2h     |     0h     |    0.5h   |   1h     |     0h       |    0.5h    |     6h      |
| Wednesday | Healthchecks, restart, depends_on (Exercise 2)     |    1h    |    2h     |     1h     |    0.5h   |   1h     |     1h       |    0.5h    |     7h      |
| Thursday  | Env + secrets, twelve-factor III/IV (Exercise 3)   |    1h    |    1h     |     1h     |    0.5h   |   1h     |     2h       |    0.5h    |     7h      |
| Friday    | Mini-project — four-service local stack            |    0h    |    0h     |     1h     |    0.5h   |   1h     |     3h       |    0.5h    |     6h      |
| Saturday  | Challenge — one-command spin-up with seed data     |    0h    |    0h     |     1h     |    0h     |   1h     |     1h       |    0h      |     3h      |
| Sunday    | Quiz, write the README, retro                      |    0h    |    0h     |     0h     |    0.5h   |   0h     |     0h       |    0h      |     0.5h    |
| **Total** |                                                    | **6h**   | **7h**    | **4h**     | **3h**    | **6h**   | **7h**       | **2.5h**   | **35.5h**   |

---

## How to navigate this week

| File | What's inside |
|------|---------------|
| [README.md](./README.md) | This overview (you are here) |
| [resources.md](./resources.md) | Curated readings: 12factor.net, the Compose specification, free books |
| [lecture-notes/01-the-compose-yaml-anatomy.md](./lecture-notes/01-the-compose-yaml-anatomy.md) | Every top-level key, every service field worth knowing |
| [lecture-notes/02-the-twelve-factors-applied.md](./lecture-notes/02-the-twelve-factors-applied.md) | All twelve principles, with Compose-shaped recipes |
| [exercises/README.md](./exercises/README.md) | Index of hands-on drills |
| [exercises/exercise-01-three-service-compose.md](./exercises/exercise-01-three-service-compose.md) | Wire a web + db + cache stack in one `compose.yaml` |
| [exercises/exercise-02-healthchecks-and-restart.md](./exercises/exercise-02-healthchecks-and-restart.md) | Add healthchecks; watch a flapping service auto-restart |
| [exercises/exercise-03-env-and-secrets.md](./exercises/exercise-03-env-and-secrets.md) | `.env`, `env_file`, `environment:`, and Compose secrets |
| [challenges/README.md](./challenges/README.md) | Index of weekly challenges |
| [challenges/challenge-01-one-command-spinup-with-seed-data.md](./challenges/challenge-01-one-command-spinup-with-seed-data.md) | `make up` and a 30-second wait until everything is green |
| [quiz.md](./quiz.md) | 10 multiple-choice questions |
| [homework.md](./homework.md) | Six practice problems |
| [mini-project/README.md](./mini-project/README.md) | Local dev environment for a four-service app, one command to spin up |

---

## Stretch goals

If you finish early and want to push further:

- Read the Compose specification end to end at <https://github.com/compose-spec/compose-spec/blob/main/spec.md>. It is shorter than you think, and once you have read it you stop guessing.
- Convert your Week 2 mini-project to a `compose.yaml` and add a `prometheus` service that scrapes `/metrics` from your Flask app. Wire `grafana` to it. That is a Week 10 preview for free.
- Read the `docker compose` v2 source — specifically `cmd/compose/up.go` — to see how `depends_on: condition: service_healthy` is implemented as a polling loop over the Docker API.
- Run the same `compose.yaml` under **Podman Compose** and under **`nerdctl compose`**. Find the three things that do not work identically. (Hint: bind mounts, user namespaces, networking.)
- Read the post-mortem of Heroku's 2011 outage that inspired Factor IX ("Disposability") at <https://status.heroku.com/incidents/151>. Disposability is not theory; it is a scar.

---

## Up next

Continue to **Week 4 — GitHub Actions Beyond Hello-World** once you have pushed your Week 3 mini-project to GitHub. Week 4 is where the `docker compose` workflow you just wrote becomes a CI pipeline — and where the muscle memory of "build, test, ship" starts to feel automatic.

---

*If you find errors in this material, please open an issue or send a PR. Future learners will thank you.*
