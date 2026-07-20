# Week 2 — Quiz

Ten questions. Lectures closed. Aim for 9/10.

---

**Q1.** Which `Dockerfile` instruction is the most reliable way to bring local files into an image without surprise behavior?

- A) `ADD`
- B) `COPY`
- C) `INCLUDE`
- D) `IMPORT`

---

**Q2.** Given this `Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "app.py"]
```

You change a single line in `app.py` and rebuild. Why does `pip install` re-run?

- A) BuildKit always re-runs `RUN` instructions on every build.
- B) `COPY . .` is before `RUN pip install`; the source-code change invalidates the `COPY` layer and every layer after it.
- C) `pip` checks the network on every build for newer wheel versions.
- D) `python:3.12-slim` is a mutable tag and pulled a new image.

---

**Q3.** What does `EXPOSE 8000` actually do?

- A) Publishes container port 8000 to host port 8000.
- B) Opens a firewall rule for port 8000.
- C) Writes "8000" into the image config as documentation; `docker run -P` maps it to a random host port.
- D) Binds the application to port 8000 at runtime.

---

**Q4.** A container's `Dockerfile` ends with:

```dockerfile
ENTRYPOINT ["/usr/local/bin/myapp"]
CMD ["--help"]
```

What does `docker run myimage serve --port 8080` execute?

- A) `/usr/local/bin/myapp --help`
- B) `serve --port 8080`
- C) `/usr/local/bin/myapp serve --port 8080`
- D) `/bin/sh -c "/usr/local/bin/myapp serve --port 8080"`

---

**Q5.** Which is the **correct** way to pass a secret to a build step without recording it in `docker history`?

- A) `ARG SECRET` plus `docker build --build-arg SECRET=...`
- B) `ENV SECRET=...` in the Dockerfile.
- C) `RUN --mount=type=secret,id=mysecret cat /run/secrets/mysecret` plus `docker build --secret id=mysecret,src=...`
- D) `COPY .env /app/.env` and reading it in the container.

---

**Q6.** What is the practical effect of `RUN --mount=type=cache,target=/root/.cache/pip`?

- A) The pip cache is committed into the image layer for the next build.
- B) The pip cache persists across builds but is never committed to any image layer.
- C) `pip install` is skipped entirely.
- D) The `pip` command is run inside a different container.

---

**Q7.** Which statement about distroless images is correct?

- A) Distroless images contain a minimal Alpine Linux distribution.
- B) Distroless images contain only the language runtime and direct dependencies; they have no shell, no `apt`, and no `ls`.
- C) Distroless images are larger than Debian-slim images because they statically link everything.
- D) Distroless images require Kaniko or Buildah; they cannot be used with Docker.

---

**Q8.** A `trivy image` scan reports a `CRITICAL` CVE in `libssl3`. The "Fixed Version" column is populated. What is the most operationally sound first response?

- A) Add the CVE to `.trivyignore` and document the suppression.
- B) Rebuild the image on a current base; the fix is upstream.
- C) Patch `libssl3` manually inside a custom `RUN apt-get install` step.
- D) Switch the base image to Alpine.

---

**Q9.** Which one of these `Dockerfile` patterns is the **standard** way to keep the dependency-install layer cached when source code changes?

- A) `COPY . .` then `RUN pip install -r requirements.txt`
- B) `COPY requirements.txt .` then `RUN pip install -r requirements.txt` then `COPY app/ ./app/`
- C) `RUN pip install -r https://example.com/requirements.txt`
- D) `ADD requirements.txt /app/` then `RUN pip install /app/requirements.txt`

---

**Q10.** A container running on Kubernetes has `HEALTHCHECK` defined in its `Dockerfile`. Which is true?

- A) Kubernetes evaluates the `HEALTHCHECK` and uses it for `readinessProbe`.
- B) Kubernetes ignores `HEALTHCHECK`; you must define `readinessProbe` / `livenessProbe` in the Pod spec.
- C) Kubernetes evaluates `HEALTHCHECK` and uses it for `livenessProbe` but not `readinessProbe`.
- D) Kubernetes refuses to schedule a Pod whose image has `HEALTHCHECK`.

---

## Answer key

<details>
<summary>Click to reveal</summary>

1. **B** — `COPY` does exactly one thing: copy local files. `ADD` *also* fetches URLs and auto-extracts tarballs, which are the two footguns Lecture 1 warns about. Hadolint flags `ADD` (DL3020). `INCLUDE` and `IMPORT` are not Dockerfile instructions.

2. **B** — Cache invalidation is positional. `COPY . .` includes `app.py`; its content changed; its cache key changed; every subsequent instruction's key changes too, including `RUN pip install`. The fix is to `COPY requirements.txt` first, run pip, *then* `COPY` the source.

3. **C** — `EXPOSE` is documentation. It writes the port into the image's config blob, where `docker inspect` shows it. It does **not** publish a port. `docker run -p 8000:8000` (lowercase, explicit) is what publishes. `docker run -P` (uppercase, magic) auto-maps EXPOSEd ports to random host ports.

4. **C** — `ENTRYPOINT` is the binary; `CMD` provides default arguments; positional arguments to `docker run` *replace* `CMD` and become arguments to `ENTRYPOINT`. So the run line replaces `--help` with `serve --port 8080`, and the actual command is `/usr/local/bin/myapp serve --port 8080`.

5. **C** — BuildKit's `--mount=type=secret` mounts the secret to a tmpfs during the `RUN` and never records it in the image or history. `ARG` (option A) **does** record in history; `ENV` (B) writes the secret into the image config blob; `COPY .env` (D) ships the secret with the image. (C) is the only secure answer.

6. **B** — Cache mounts are external to the image. The cache persists across builds and speeds up `pip install` when deps change, but the cache directory itself is unmounted before the layer is committed. That is the whole point.

7. **B** — Distroless contains the runtime plus its libs and nothing else. No shell, no package manager. This is what gives distroless its near-zero CVE surface and its "you cannot `docker exec sh`" property. (A) is wrong: distroless is Debian-based, not Alpine. (C) is the opposite of true. (D) is wrong: distroless images work with any OCI-compatible builder.

8. **B** — A populated "Fixed Version" means upstream has patched. The fastest, most operationally sound action is to rebuild on a current base image. Suppression (A) is a last resort and requires documented rationale. Manual patching (C) creates drift. Switching to Alpine (D) is a much bigger change for a single CVE.

9. **B** — The COPY-deps-first / COPY-source-second pattern is the foundation of Dockerfile caching. It is on the first page of every "Dockerfile best practices" guide for a reason. (A) is the antipattern this rule fixes. (C) introduces network non-determinism. (D) uses `ADD` (avoid) and does not solve the ordering problem.

10. **B** — Kubernetes ignores `HEALTHCHECK`. K8s uses its own `livenessProbe`, `readinessProbe`, and `startupProbe`. Compose and `docker run` use `HEALTHCHECK`; K8s does not. Best practice: define the `/healthz` endpoint in the app, reference it from `HEALTHCHECK` for Compose and from `readinessProbe` for K8s — same endpoint, two consumers.

</details>

If under 7, re-read the lectures you missed. If 9+, you are ready for the [homework](./homework.md).
