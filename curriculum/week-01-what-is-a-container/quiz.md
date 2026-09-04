# Week 1 — Quiz

Ten questions. Lectures closed. Aim for 9/10.

---

**Q1.** Which of the following is **not** a Linux namespace type?

- A) `pid`
- B) `net`
- C) `disk`
- D) `mount`

<details>
<summary>Answer</summary>

**C** — There is no `disk` namespace. The eight namespace types are `mount`, `pid`, `net`, `uts`, `ipc`, `user`, `cgroup`, `time`.

</details>

---

**Q2.** A container exits with status code `137`. What is the most likely cause?

- A) The application called `sys.exit(137)`.
- B) The kernel OOM-killer terminated the process because it hit its cgroup `memory.max`.
- C) The container could not pull its image and timed out.
- D) The container's TLS handshake to the registry failed.

<details>
<summary>Answer</summary>

**B** — Exit code `137` is `128 + SIGKILL (9)`. The kernel OOM-killer sends `SIGKILL` when a process in a cgroup exceeds `memory.max`. `docker inspect` will show `OOMKilled: true`.

</details>

---

**Q3.** Which statement about containers and virtual machines is correct?

- A) Containers each run their own kernel; VMs share a kernel.
- B) Containers share the host kernel; VMs each run their own kernel.
- C) Both run their own kernel.
- D) Both share the host kernel.

<details>
<summary>Answer</summary>

**B** — Containers share the host kernel; VMs run their own kernel on virtual hardware presented by a hypervisor. This is the single most important distinction.

</details>

---

**Q4.** In an OCI image, where are an image's environment variables (e.g. `ENV PATH=...`) recorded?

- A) Inside one of the layer tarballs as `/etc/environment`.
- B) Inside the image's config blob (a JSON document).
- C) In the manifest's `annotations` field.
- D) In the registry's database, not the image itself.

<details>
<summary>Answer</summary>

**B** — The image config blob holds `Env`, `Cmd`, `Entrypoint`, `WorkingDir`, `ExposedPorts`, `User`, `Labels`. Layers hold only filesystem contents.

</details>

---

**Q5.** Which program does Kubernetes' `kubelet` talk to on most clusters as of 2026?

- A) `docker` (via `dockershim`).
- B) `containerd` (directly, via CRI).
- C) `runc` (directly).
- D) `podman` (via D-Bus).

<details>
<summary>Answer</summary>

**B** — `containerd` directly, via the Container Runtime Interface (CRI). `dockershim` was removed from Kubernetes in 1.24 (2022).

</details>

---

**Q6.** You run `docker run --rm -it debian:bookworm bash`, then on the host run `docker exec -it <id> bash`. What is the relationship between the two `bash` processes?

- A) Both run in the same set of namespaces; the second is `setns()`ed into the first's.
- B) Each runs in its own fresh set of namespaces; only the rootfs is shared.
- C) The second bash runs on the host, not in a container.
- D) The second bash runs in a sibling container that shares only the network namespace.

<details>
<summary>Answer</summary>

**A** — `docker exec` calls `setns()` to join the existing container's namespaces. Both bash processes share PID, mount, net, etc. namespaces; that is why `ps -ef` inside `exec` shows the first bash as PID 1.

</details>

---

**Q7.** Which is the most correct way to refer to an image in a production deployment manifest?

- A) `myapp:latest`
- B) `myapp:v1.4.2`
- C) `myapp@sha256:9c2ad9c0d3b8...`
- D) `docker.io/library/myapp`

<details>
<summary>Answer</summary>

**C** — Pin by digest in production. Tags can be re-pushed; digests cannot.

</details>

---

**Q8.** A naïve `Dockerfile` produces a 1.07 GB image for a small Flask app. Which **one** change typically yields the largest single reduction in image size?

- A) Adding `.dockerignore`.
- B) Switching `FROM python:3.12` to `FROM python:3.12-slim`.
- C) Running `pip install` with `--no-cache-dir`.
- D) Running the container as a non-root user.

<details>
<summary>Answer</summary>

**B** — Switching from `python:3.12` (~1 GB, includes build-essential) to `python:3.12-slim` (~120 MB) is by far the largest single win. The other options matter, but in the tens of MB range, not the hundreds.

</details>

---

**Q9.** What is the relationship between `runc` and `crun`?

- A) `runc` is a higher-level engine; `crun` is a lower-level runtime it delegates to.
- B) `crun` is a Rust reimplementation of `runc`.
- C) Both are OCI-compliant container runtimes; `runc` is the Go reference implementation, `crun` is a C reimplementation.
- D) `crun` is an older project that `runc` replaced in 2017.

<details>
<summary>Answer</summary>

**C** — Both are OCI-compliant runtimes. `runc` is the Linux Foundation reference in Go; `crun` is a smaller, faster C implementation maintained by Red Hat / the `containers` org. They accept the same `config.json`.

</details>

---

**Q10.** A process is in a new `pid` namespace but its `mnt` namespace is the host's. It runs `ps -ef`. What does it see?

- A) Only the processes in its own PID namespace.
- B) All processes on the host.
- C) Nothing; `ps` errors out.
- D) Only the processes started after `unshare` was called.

<details>
<summary>Answer</summary>

**A** — `ps` reads `/proc/`. Even though the `mnt` namespace is the host's, `/proc` is a kernel-provided filesystem and shows the *process's* PID namespace view. The catch is that `ps` may show only the right processes but with weird mount paths.

</details>

If under 7, re-read the lectures you missed. If 9+, you are ready for the [homework](./homework.md).

---
