# Week 3 — Exercises

Three drills. Each takes 60–120 minutes. Do them in order — Exercise 1 is the canvas the other two paint on.

1. **[Exercise 1 — Three-Service Compose](exercise-01-three-service-compose.md)** — Wire a web + db + cache stack in one `compose.yaml`. (~120 min)
2. **[Exercise 2 — Healthchecks and Restart](exercise-02-healthchecks-and-restart.md)** — Add `healthcheck:`, `depends_on: service_healthy`, and a restart policy. Watch a flapping service auto-restart. (~90 min)
3. **[Exercise 3 — Env and Secrets](exercise-03-env-and-secrets.md)** — `.env`, `env_file`, `environment:`, Compose secrets, and the four sources of config. (~90 min)

## Workflow

- Type the commands, do not paste them. The point is to feel the orchestration.
- After each exercise, write one paragraph in your notes about what surprised you. "It worked" is not a surprise; "the worker started before the migration finished and crashed" is.
- Run `docker compose config` before every `up`. Build the muscle memory now.

## Platform requirements

- Docker 24+ with Compose v2.22 or newer. Confirm: `docker compose version` (note the space). Expect `v2.22.x` or higher.
- About 2 GB of free disk for image storage and named volumes.
- `curl`, `jq`, and `yq` on your host. macOS, Linux, and WSL2 all work this week.

## Self-grading

After each exercise, ask: "Could I rebuild this stack from a blank directory in 15 minutes, without looking?" If yes, move on. If no, do it again from scratch.
