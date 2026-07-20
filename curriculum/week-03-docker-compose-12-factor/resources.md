# Week 3 — Resources

Every resource on this page is **free** and **publicly accessible**. No paywalled books. If a link 404s, please open an issue.

## Required reading (work it into your week)

- **The Twelve-Factor App** — the original 2011 manifesto, by Adam Wiggins. Read all twelve sections, in order, before Tuesday's lecture. It is the single most-referenced document in this course: <https://12factor.net/>
- **Compose specification** — the canonical spec for the file you will write all week. Read sections "Services top-level element," "Networks top-level element," "Volumes top-level element," "Configs top-level element," "Secrets top-level element": <https://github.com/compose-spec/compose-spec/blob/main/spec.md>
- **`docker compose` CLI reference** — every subcommand, every flag, kept current with Compose v2: <https://docs.docker.com/reference/cli/docker/compose/>
- **Compose file reference (Docker docs flavor)** — the same spec, with examples and Docker-Inc-specific extensions called out: <https://docs.docker.com/reference/compose-file/>
- **Compose networking** — how the `<project>_default` network is built and how service-name DNS resolution actually works: <https://docs.docker.com/compose/how-tos/networking/>

## The specs (skim, don't memorize)

- **Compose specification — services** — every key on a service, in alphabetical order, with version history: <https://github.com/compose-spec/compose-spec/blob/main/05-services.md>
- **Compose specification — networks**: <https://github.com/compose-spec/compose-spec/blob/main/06-networks.md>
- **Compose specification — volumes**: <https://github.com/compose-spec/compose-spec/blob/main/07-volumes.md>
- **Compose specification — secrets**: <https://github.com/compose-spec/compose-spec/blob/main/09-secrets.md>
- **Compose v2 release notes** — the changelog is short and easy to skim; useful when a feature you read about does not work on your install: <https://github.com/docker/compose/releases>

## Official tool docs

- **`docker compose up`** — flags, the `--wait` flag, the `--abort-on-container-exit` flag: <https://docs.docker.com/reference/cli/docker/compose/up/>
- **`docker compose config`** — render the final, fully-resolved Compose file with variables substituted; the single most useful debugging command: <https://docs.docker.com/reference/cli/docker/compose/config/>
- **`docker compose watch` and the `develop:` block** — live file sync without rebuilding, added in Compose v2.22: <https://docs.docker.com/compose/how-tos/file-watch/>
- **Compose profiles** — selectively enable subsets of services (e.g., `--profile debug` to bring up `pgadmin` alongside `postgres`): <https://docs.docker.com/compose/how-tos/profiles/>
- **Healthchecks** — the four parameters and how Compose schedules them: <https://docs.docker.com/reference/dockerfile/#healthcheck>

## Free books and write-ups

- **"Beyond the Twelve-Factor App"** by Kevin Hoffman — a 2016 update that adds three factors and reorders the original twelve. Free PDF from Pivotal (now VMware Tanzu): <https://tanzu.vmware.com/content/blog/beyond-the-twelve-factor-app>
- **"Compose your service in YAML"** — Docker's own walkthrough; reasonable starting point, ignore the marketing voice: <https://docs.docker.com/compose/gettingstarted/>
- **"Docker Compose for local development"** by Michael Herman — practical Python + Postgres patterns: <https://testdriven.io/blog/docker-compose-flask/>
- **Bret Fisher's Compose patterns repo** — eleven real-world Compose files, each with a one-paragraph rationale: <https://github.com/BretFisher/docker-mastery-for-nodejs>
- **"The cult of done"** by Bre Pettis and Kio Stark — not about DevOps, but Factor IX (disposability) makes a lot more sense once you have read it: <https://medium.com/@bre/the-cult-of-done-manifesto-724ca1c2ff13>

## Talks and videos (free, no signup)

- **"The Twelve-Factor App, ten years later" — Adam Wiggins** (~30 min). The author looks back on what he got right and wrong: <https://www.youtube.com/results?search_query=adam+wiggins+twelve+factor+ten+years>
- **"Compose in production-ish" — Bret Fisher** (~40 min). The single best practical Compose talk on YouTube: <https://www.youtube.com/results?search_query=bret+fisher+docker+compose>
- **"Docker Compose under the hood" — Nicolas De Loof** (~25 min). The Compose v2 maintainer walks through how `up` is implemented: <https://www.youtube.com/results?search_query=nicolas+de+loof+docker+compose>

## Open-source Compose files to read this week

You can learn more from one hour reading other people's `compose.yaml` than from three hours of tutorials. Pick one and just read it:

- **`awesome-compose`** — Docker's own curated catalog, ~80 stacks: <https://github.com/docker/awesome-compose>
- **Sentry's `self-hosted`** — a real, complex production-grade Compose stack (web + workers + Postgres + Redis + Kafka + Zookeeper): <https://github.com/getsentry/self-hosted>
- **Mastodon's `docker-compose.yml`** — a battle-tested social-network stack: <https://github.com/mastodon/mastodon/blob/main/docker-compose.yml>
- **Gitea's `docker-compose.yml`** — small, readable, well-commented: <https://docs.gitea.com/installation/install-with-docker>

## Tools you'll install this week

| Tool | Install | Purpose |
|------|---------|---------|
| `docker compose` | bundled in Docker Desktop 4.x and Docker Engine 24+ | Build, run, manage multi-container stacks |
| `dive` | `brew install dive` | Inspect image layers (carried over from Week 2) |
| `yq` | `brew install yq` / [release page](https://github.com/mikefarah/yq/releases) | `jq` for YAML; invaluable for sanity-checking Compose files |
| `docker compose watch` | bundled with Compose v2.22+ | Live source sync without rebuilds |
| `httpie` or `curl` | `brew install httpie` / preinstalled | Smoke-test web services from the shell |

## Glossary cheat sheet

Keep this open in a tab.

| Term | Plain English |
|------|---------------|
| **Compose project** | The set of services, networks, and volumes defined in one `compose.yaml`. Named by `--project-name` or by the parent directory. |
| **Service** | A named container definition. One service = one (or more, with `deploy: replicas:`) running container. |
| **`compose.yaml`** | The current canonical filename for a Compose file. `docker-compose.yml` still works for compatibility. |
| **Backing service** | Any data store or external resource your app talks to over the network — Postgres, Redis, S3, an email API. (Twelve-Factor IV.) |
| **Bind mount** | A path on the host mounted into the container. Source changes appear live. |
| **Named volume** | A volume Docker manages on the host's storage driver. Survives `docker compose down`, dies with `down -v`. |
| **Healthcheck** | A periodic command Docker runs inside a container; its exit code drives the container's `health` status. |
| **`depends_on: service_healthy`** | Wait to start service B until service A's healthcheck reports healthy. Compose v2 only. |
| **Restart policy** | What Docker should do when a container exits: `no`, `on-failure`, `always`, `unless-stopped`. |
| **Compose secret** | A file mounted at `/run/secrets/<name>` inside the container, declared in the `secrets:` top-level key. |
| **Profile** | A label on a service; `docker compose --profile X up` only starts services with that profile. |

---

*If a link 404s, please [open an issue](https://github.com/CODE-CRUNCH-CLUB) so we can replace it.*
