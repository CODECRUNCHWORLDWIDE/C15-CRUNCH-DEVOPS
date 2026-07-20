# Week 3 — Quiz

Ten questions. Lectures closed. Aim for 9/10.

---

**Q1.** In Compose v2, which top-level key has been **removed** from the specification and should be deleted from any modern `compose.yaml`?

- A) `services`
- B) `volumes`
- C) `version`
- D) `networks`

---

**Q2.** A service named `db` is declared in `compose.yaml`. From the `web` service in the same project, which hostname will resolve to the `db` container on the default network?

- A) `localhost`
- B) `db`
- C) `127.0.0.1`
- D) `<project>_db_1.local`

---

**Q3.** What is the practical difference between `ports:` and `expose:` on a service?

- A) `expose:` is a Compose-v1 alias for `ports:` and should not be used.
- B) `ports:` publishes the port to the host; `expose:` makes it reachable only inside the Compose network.
- C) `ports:` is for TCP and `expose:` is for UDP.
- D) `expose:` opens the port in the host firewall; `ports:` does not.

---

**Q4.** A service `web` has `depends_on: [db]` with no `condition:` specified. On `docker compose up`, when does Compose start `web`?

- A) After `db` has been `docker create`d, regardless of whether the process inside is ready.
- B) After `db`'s healthcheck reports healthy.
- C) After `db` has exited successfully.
- D) `depends_on` without `condition:` is a syntax error in Compose v2.

---

**Q5.** Which restart policy will continue restarting a one-shot migration job after it has successfully exited with code 0?

- A) `on-failure`
- B) `unless-stopped`
- C) `no`
- D) `always`

---

**Q6.** A `compose.yaml` declares `env_file: [.env.web]` and `environment: { LOG_LEVEL: DEBUG }` on the `web` service. The file `.env.web` contains `LOG_LEVEL=INFO`. The shell that runs `docker compose up` exports `LOG_LEVEL=WARN`. What value does the running container see for `LOG_LEVEL`?

- A) `INFO`
- B) `DEBUG`
- C) `WARN`
- D) Empty — Compose refuses to resolve conflicting values.

---

**Q7.** Compose `secrets:` declared with `file: ./secrets/db_password.txt` mount the value at what path inside the container?

- A) `/etc/secrets/db_password`
- B) `/run/secrets/db_password`
- C) `/var/lib/docker/secrets/db_password`
- D) The path given by the `SECRET_PATH` environment variable.

---

**Q8.** Which of the following is the **correct** way to express, in a healthcheck, "do not count failures during the first 20 seconds of container startup"?

- A) `retries: 0` for the first 20 seconds, then `retries: 5`.
- B) `start_period: 20s`
- C) `interval: 20s`
- D) `timeout: 20s`

---

**Q9.** A service has `depends_on: { migrate: { condition: service_completed_successfully } }`. On `docker compose up`, what does Compose wait for before starting this service?

- A) The `migrate` container is created.
- B) The `migrate` container's healthcheck reports healthy.
- C) The `migrate` container has exited with code 0.
- D) The `migrate` container has been running for at least 5 seconds.

---

**Q10.** A web app reads its database password from `os.environ["DB_PASSWORD"]`. Which of the following placements of the password is most consistent with the Twelve-Factor App methodology?

- A) Hardcoded in `app/config.py`, committed to git.
- B) In `compose.yaml`'s `environment:` block, committed to git.
- C) In a `.env` file that is gitignored, with a `.env.example` committed.
- D) In a comment in the `README.md`, base64-encoded.

---

## Answer key

<details>
<summary>Click to reveal</summary>

1. **C** — `version:` was deprecated when the Compose specification was extracted from Docker in 2020 and is now simply ignored. Compose still parses it for backward compatibility, but no modern file should include it. `services`, `volumes`, and `networks` are all current.

2. **B** — Compose's embedded DNS resolver (at `127.0.0.11` inside each container) resolves service names directly. `localhost` is the container itself; `127.0.0.1` likewise. The `<project>_db_1.local` form is fabricated.

3. **B** — `ports:` is the "publish to the host" verb; the port appears in `docker ps`. `expose:` is documentation plus an in-network hint; the port is reachable from sibling services on the same network but not from the host. (A) is wrong: both keys exist in v2. (C) is wrong: both are protocol-agnostic. (D) is wrong: neither manages host firewalls.

4. **A** — Bare `depends_on` (Compose v1 behavior, kept for compatibility) only orders **container creation**, not readiness. This is the cargo-culted footgun Lecture 1 calls out. The fix is to add `condition: service_healthy` (with a healthcheck on the dependency).

5. **D** — `always` restarts the container on **any** exit, including a clean exit code 0. That is exactly the wrong behavior for a one-shot job: the migration completes, Compose restarts it, it runs again (possibly a no-op, possibly destructive), exits, restarts again, and so on. Use `restart: "no"` for jobs that should die. `unless-stopped` is `always`-but-respects-manual-stop, which is still wrong for a one-shot.

6. **C** — The shell env wins. The precedence from highest to lowest is: shell → `--env-file` flag → `environment:` in the file → `env_file:` in the file. The literal `DEBUG` in `environment:` would have won over `env_file:` if no shell value were present, but the shell trumps both because shell substitution happens before the value is written into the container.

7. **B** — Compose mounts secrets at `/run/secrets/<name>` by default, with mode `0400`. (A path can be overridden with the long-form `target:` field but `/run/secrets/` is the default and the convention.) The value is *not* in the container's env, which is why secrets are a strict upgrade over `environment:` for credentials.

8. **B** — `start_period:` is the grace window during which failed healthchecks **do not** count toward the `retries` budget. (A) is not a syntactic possibility. (C) sets how often the check runs, not when it starts. (D) is per-check timeout.

9. **C** — `service_completed_successfully` means the dependency has run to completion and exited with code 0. This is the right condition for migration / seeder jobs. (A) is `service_started`. (B) is `service_healthy`.

10. **C** — Factor III: config in the environment. `.env` gitignored, `.env.example` committed, the app reads from `os.environ`. (A) violates Factor III directly. (B) commits a secret to git. (D) commits a secret to git *and* uses base64 as if it were encryption.

</details>

If under 7, re-read the lectures you missed. If 9+, you are ready for the [homework](./homework.md).
