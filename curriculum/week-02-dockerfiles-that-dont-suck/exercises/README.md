# Week 2 — Exercises

Three drills. Each takes 60–120 minutes. Do them in order — Exercise 1 is the canvas the other two paint on.

1. **[Exercise 1 — Three Builds, Three Images](exercise-01-three-builds-three-images.md)** — Build the same Flask app naive, multi-stage, and distroless. Measure size, build time, CVE count. (~120 min)
2. **[Exercise 2 — Cache Mounts](exercise-02-cache-mounts.md)** — Add BuildKit `--mount=type=cache` to your pip and apt steps. Watch rebuilds get fast. (~90 min)
3. **[Exercise 3 — Scan with Trivy](exercise-03-scan-with-trivy.md)** — Install `trivy`, scan all three images, write a `.trivyignore` policy. (~90 min)

## Workflow

- Type the commands, do not paste them. The point is to feel the build.
- After each exercise, write one paragraph in your notes file about what surprised you. Real surprises only — "the build was fast" is not a surprise, "the multi-stage build was *slower* than the single-stage on the first run" might be.
- Do not skip Exercise 1 because "I already wrote a multi-stage Dockerfile last week." The measurements are the point this week, not the syntax.

## Platform requirements

- Docker 24+ with BuildKit (default in 23+). Confirm: `docker version | grep -i buildkit` shows BuildKit is active, or `docker buildx version` returns a version.
- About 2 GB of free disk for image storage. The naive build alone is over 1 GB.
- `curl`, `jq` on your host. macOS, Linux, and WSL2 all work this week.

## Self-grading

After each exercise, ask: "Could I explain this to a junior engineer in 3 minutes, with the screen showing the relevant numbers?" If yes, move on. If no, re-read the relevant section of the lectures.
