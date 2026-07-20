# Exercise 2 — First Real Docker

**Goal:** Run the same container you built by hand in Exercise 1, this time with Docker. Then take it apart with `docker inspect`, `docker exec`, and `skopeo` to confirm that Docker is doing the same kernel-level work you did manually — just with more polish.

**Estimated time:** 60 minutes.

---

## Setup

Install Docker:

- **Linux (Ubuntu/Debian):** follow <https://docs.docker.com/engine/install/ubuntu/> or the equivalent for your distro. **Do not** `apt install docker.io` — that package is outdated. Use Docker's own apt repo.
- **macOS / Windows:** [Docker Desktop](https://docs.docker.com/desktop/) is the path of least resistance. OrbStack and Rancher Desktop are free alternatives.
- **Verify:** `docker version` prints both client and server versions. `docker run --rm hello-world` runs end-to-end.

Add yourself to the `docker` group on Linux so you do not need `sudo`:

```bash
sudo usermod -aG docker $USER
newgrp docker        # or log out and back in
```

> **Security note.** The `docker` group is effectively root-equivalent on the host: anyone in it can spin up a container with the host's `/` bind-mounted as a volume and own the box. On shared machines, use rootless Docker or Podman instead.

---

## Step 1 — Run a Debian container the Docker way

In Exercise 1 you typed:

```bash
sudo unshare --pid --uts --mount --ipc --fork \
    --mount-proc=$(pwd)/debian-rootfs/proc \
    chroot ./debian-rootfs /bin/bash
```

The Docker equivalent:

```bash
docker run --rm -it debian:bookworm bash
```

That single line, behind the scenes:

1. Talks to the local Docker daemon (`dockerd`).
2. Checks the local image store for `debian:bookworm`. If absent, pulls it from Docker Hub.
3. Unpacks (or reuses) the image layers in an overlayfs.
4. Tells `containerd` to launch a container with that rootfs.
5. `containerd` shells out to `runc`, which does the `clone()` + namespaces + cgroups + capabilities + `pivot_root`.
6. `runc` execs `bash`. Your terminal is wired up via a pty.

Inside the container, do the same checks you did in Exercise 1:

```bash
ps -ef           # bash is PID 1, ps is PID 7-ish, no host processes.
hostname         # a random hex string (the container ID short prefix)
ls /             # Debian's rootfs.
cat /etc/os-release
```

Same outcome. Different ergonomics.

Exit the container:

```bash
exit
```

Because of `--rm`, the stopped container is cleaned up automatically.

---

## Step 2 — Make Docker show you the namespaces

In another terminal — keep this one — restart the container so it runs long enough to inspect:

```bash
docker run --rm -d --name c15-tinybox debian:bookworm sleep 3600
```

That starts a detached container that just sleeps. Now compare its namespaces to the host's.

```bash
# Get the PID of the container's main process on the host:
CONTAINER_PID=$(docker inspect -f '{{.State.Pid}}' c15-tinybox)
echo "container PID on host: $CONTAINER_PID"

# Compare namespace inodes:
sudo ls -l /proc/$CONTAINER_PID/ns/
ls -l /proc/self/ns/
```

For every namespace type, the container's inode should be **different** from yours, except possibly:

- `user` — Docker does *not* use user namespaces by default. Container "root" is host root.
- `cgroup` — historically not isolated; on cgroup v2 it usually is.

Make a small Markdown table in your notes file with both sets of inode numbers, side by side. Mark which match and which differ. This is the namespace boundary made tangible.

---

## Step 3 — `docker exec` into it

`docker exec` is *not* a new container. It is a new process inside the existing container's namespaces — the `setns()` syscall from Lecture 1.

```bash
docker exec -it c15-tinybox bash
```

Inside:

```bash
ps -ef
# Expect: PID 1 is `sleep 3600`. PID 7 (or thereabouts) is this new bash.
# Both are in the same PID namespace.
```

Exit:

```bash
exit
```

That join semantics is exactly what `kubectl exec -it pod-name -- bash` does later.

---

## Step 4 — Look at the layers

Find the image on disk and inspect its layers:

```bash
docker pull debian:bookworm
docker history debian:bookworm
```

Output (truncated):

```text
IMAGE          CREATED      CREATED BY                                      SIZE
8c47...        2 weeks ago  /bin/sh -c #(nop)  CMD ["bash"]                 0B
<missing>      2 weeks ago  /bin/sh -c #(nop) ADD file:abc... in /          117MB
```

For `debian:bookworm` there is usually one real layer plus a sequence of zero-byte metadata layers. Compare with `python:3.12-slim`:

```bash
docker pull python:3.12-slim
docker history python:3.12-slim
```

You will see four or five real layers, each adding a piece (the base Debian rootfs, then `python3`, then `pip`, then config). When you change one of those during a build, only that layer and the ones above it have to be rebuilt.

Inspect an image's config blob directly:

```bash
docker image inspect debian:bookworm | jq '.[0].Config'
```

That JSON is the `config.json` from Lecture 2. The `Cmd`, `Entrypoint`, `Env`, `WorkingDir`, `User`, `ExposedPorts`, `Labels` fields are exactly the fields the OCI image-config spec defines.

---

## Step 5 — Get the manifest with `skopeo`

`skopeo` talks to the registry over HTTP and gives you the raw OCI manifest without pulling the image into Docker's store. Install it:

- Ubuntu 22.04+: `sudo apt install -y skopeo`
- macOS: `brew install skopeo`

Inspect:

```bash
skopeo inspect docker://docker.io/library/debian:bookworm
skopeo inspect --raw docker://docker.io/library/debian:bookworm | jq
```

The first command gives a friendly summary. The second prints the raw manifest. Pin the digest from the output:

```bash
DIGEST=$(skopeo inspect docker://docker.io/library/debian:bookworm | jq -r '.Digest')
echo "digest: $DIGEST"
```

Then pull *by digest* and confirm it is the same:

```bash
docker pull debian@$DIGEST
docker images --digests | grep debian
```

That digest is the production-pinnable identifier. Save it in your notes.

---

## Step 6 — Side-by-side comparison with Exercise 1

Open a fresh notes file (`notes/by-hand-vs-docker.md`) and fill in a table like this from your own measurements:

| Aspect | By-hand (Exercise 1) | Docker (Exercise 2) |
|--------|----------------------|---------------------|
| Time to "rootfs ready" | ~2 minutes (`debootstrap`) | ~10 seconds (`docker pull`) |
| Time to "shell open" | ~50 ms (`unshare ... bash`) | ~200 ms (`docker run`) |
| Size on disk | ~100 MB | ~120 MB (layers + overlay metadata) |
| PID namespace | Yes | Yes |
| Mount namespace | Yes | Yes |
| Net namespace | No (we skipped) | Yes (default `bridge`) |
| User namespace | No | No (Docker default) |
| Cgroup limits | Manual `echo` to `/sys/fs/cgroup/` | `docker run --memory 100m --cpus 0.2` |
| Filesystem root | `chroot` | `pivot_root` |
| Layer caching | No | Yes (overlayfs) |
| Image format | None — a tarball directory | OCI manifest + layers |
| Registry | None | Docker Hub |
| Networking | DIY veth pairs | Default `bridge` with `iptables` |

The kernel is doing the same work. Docker is doing every *other* job — and that is exactly why Docker won.

---

## Step 7 — Clean up

```bash
docker stop c15-tinybox    # if still running
docker rm c15-tinybox      # if not auto-removed
docker image prune         # remove dangling images (optional)
```

---

## Acceptance criteria

You can mark this exercise done when:

- [ ] `docker run --rm -it debian:bookworm bash` opens a shell that behaves like your hand-built container.
- [ ] You inspected the container's namespace inodes and confirmed they differ from the host's.
- [ ] You used `docker exec` to enter a running container and verified it joined the existing namespaces.
- [ ] You ran `docker history python:3.12-slim` and can name the layers it shows.
- [ ] You pinned `debian:bookworm` to a digest using `skopeo` and pulled by digest.
- [ ] You committed a `notes/by-hand-vs-docker.md` to your week-01 repo with the comparison table.

---

## Stretch

- Read [`/proc/<container-pid>/cgroup`](https://man7.org/linux/man-pages/man7/cgroups.7.html) on the host to see which cgroup Docker put the container in. Compare with `docker run --memory 100m`'s effect on `memory.max`.
- Run `docker run --rm --network none alpine ip addr` and observe that only `lo` exists. That is `--net` namespace with nothing attached.
- Run `docker run --rm --pid host alpine ps -ef`. The container shares the host's PID namespace; `ps` shows everything. That escape hatch is sometimes useful for debug containers; it is also why `--pid host` is a red flag in security review.

---

## Hints

<details>
<summary>If <code>docker run hello-world</code> fails with "permission denied"</summary>

You are not in the `docker` group, or you have not started a new shell since being added. Run `groups` to check; `newgrp docker` to refresh without logging out.

</details>

<details>
<summary>If <code>docker pull</code> rate-limits you</summary>

Docker Hub's anonymous tier allows 100 pulls per 6 hours. Authenticate with a free Docker Hub account (`docker login`) to lift that to 200. Or switch to GHCR / Quay for the bulk of your images.

</details>

<details>
<summary>If <code>skopeo inspect</code> says "manifest unknown"</summary>

You probably typed `docker://debian:bookworm` instead of `docker://docker.io/library/debian:bookworm`. `skopeo` does not infer Docker Hub as the default registry.

</details>

---

When this exercise feels comfortable, move on to the [Week 1 challenge](../challenges/challenge-01-shrink-the-image.md).
