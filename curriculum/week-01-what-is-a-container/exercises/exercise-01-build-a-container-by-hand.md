# Exercise 1 — Build a Container by Hand

**Goal:** Build a working Linux container from first principles using only `unshare`, `chroot`, a Debian rootfs tarball, and a couple of writes to `/sys/fs/cgroup`. No Docker. No Podman. No image format.

**Estimated time:** 90 minutes.

---

## Why we are doing this

Every container engine on the market — Docker, Podman, containerd, CRI-O — is doing some version of what you are about to do, dressed in JSON and Go. By Friday you will use Docker for everything. Right now, before that happens, you are going to do it by hand so that Docker stops being a magic word.

When something breaks in production three months from now and the error message says "OCI runtime exec failed: container_linux.go:380: starting container process caused 'permission denied'," you will know there is a `clone()` call and a `chroot` and a capability set underneath, and you will know where to look.

---

## Setup

You need a **Linux machine** with `sudo`. Required packages:

- **Debian/Ubuntu:** `sudo apt update && sudo apt install -y debootstrap util-linux coreutils`
- **Fedora/RHEL:** `sudo dnf install -y debootstrap util-linux coreutils` (debootstrap is in the EPEL repos)
- **WSL2:** install Ubuntu, then run the Debian/Ubuntu command above.

Confirm kernel features:

```bash
uname -r           # 5.x or 6.x is fine
zcat /proc/config.gz | grep -E 'CONFIG_(USER|PID|NET|MOUNT)_NS' || \
  grep -E 'CONFIG_(USER|PID|NET|MOUNT)_NS' /boot/config-$(uname -r)
# Expect: all four set to 'y'. On most distros they will be.
```

Create a working directory for this exercise:

```bash
sudo mkdir -p /var/lib/c15
sudo chown $USER /var/lib/c15
cd /var/lib/c15
```

---

## Step 1 — Build a root filesystem (~10 min, mostly download)

A container needs a filesystem to look at. Use `debootstrap` to build a minimal Debian rootfs from the upstream archive. This is the same tool the Debian and Ubuntu cloud-image builders use.

```bash
sudo debootstrap --variant=minbase --arch=$(dpkg --print-architecture) \
    stable ./debian-rootfs http://deb.debian.org/debian
```

That downloads about 100 MB and unpacks it to `./debian-rootfs`. It will sit there until you delete it.

Verify:

```bash
ls debian-rootfs/
# Expect: bin boot dev etc home lib ... usr var
sudo chroot debian-rootfs /bin/ls /etc/os-release
sudo cat debian-rootfs/etc/os-release
# Expect: PRETTY_NAME="Debian GNU/Linux 12 (bookworm)" (or whichever current stable is)
```

That directory tree is, for all practical purposes, the contents of a `debian:bookworm` Docker image — except you built it from upstream instead of pulling from Docker Hub. Tomorrow you will see they are bit-for-bit very similar.

---

## Step 2 — Enter a chroot and explore (5 min)

Before we add namespaces, see what `chroot` alone does:

```bash
sudo chroot ./debian-rootfs /bin/bash
```

Inside:

```bash
ls /                      # Looks like Debian. Because it is.
ps -ef                    # ERROR: /proc not mounted; ps cannot read it.
hostname                  # Still the host's hostname — UTS namespace is shared.
ip addr 2>/dev/null || true
                          # `ip` may be missing in minbase; that is fine.
exit
```

You changed `/` but nothing else. The PID namespace is still the host's. The hostname is still the host's. The network is still the host's. `chroot` alone is not a container.

---

## Step 3 — Add the namespaces (15 min)

Now wrap that `chroot` in `unshare`:

```bash
sudo unshare \
    --pid \
    --uts \
    --mount \
    --ipc \
    --fork \
    --mount-proc=$(pwd)/debian-rootfs/proc \
    chroot ./debian-rootfs /bin/bash
```

Read each flag:

- `--pid` — new PID namespace; your shell will be PID 1 inside.
- `--uts` — new UTS namespace; you can `hostname` without affecting the host.
- `--mount` — new mount namespace; mounts you make inside do not affect the host.
- `--ipc` — new IPC namespace; System V IPC objects are isolated.
- `--fork` — fork before exec; required because PID 1 cannot itself be the `unshare` process.
- `--mount-proc=<path>` — mount a fresh `/proc` inside the rootfs so that `ps`, `top`, etc. see only the new PID namespace.

We deliberately do **not** pass `--net` yet. We will in Step 5.

Inside the new shell:

```bash
ps -ef
# Expect: bash is PID 1, ps is PID 4 or so. No other host processes.

hostname tinybox
hostname
# Expect: tinybox

# On the host, run `hostname` in another terminal:
#   it still says the host's name.

ls /
# Expect: Debian's /
```

You are now in a container. The kernel is the host's. The userspace is Debian. The processes are isolated. The hostname is isolated. The filesystem is isolated. That is roughly what `docker run -it debian bash` gives you on Wednesday.

Exit and come back to the host shell:

```bash
exit
```

---

## Step 4 — Add cgroup limits (20 min)

Right now your container can use as much RAM and CPU as it wants. Real containers do not get that privilege. Add a cgroup.

This assumes **cgroup v2**, which is the default on Ubuntu 22.04+, Debian 11+, Fedora 31+. Check:

```bash
stat -fc %T /sys/fs/cgroup/
# Expect: cgroup2fs    (= v2)
# If you get: tmpfs    (= v1) — re-read the cgroup v1 section in Lecture 1 and adapt.
```

Create the cgroup and set limits:

```bash
sudo mkdir /sys/fs/cgroup/c15-tinybox

# Memory cap: 100 MB
echo "104857600" | sudo tee /sys/fs/cgroup/c15-tinybox/memory.max

# CPU cap: 20% of one CPU (20 ms out of every 100 ms)
echo "20000 100000" | sudo tee /sys/fs/cgroup/c15-tinybox/cpu.max
```

Now run the same `unshare` invocation as before — but first, put the shell into the cgroup:

```bash
echo $$ | sudo tee /sys/fs/cgroup/c15-tinybox/cgroup.procs

sudo unshare --pid --uts --mount --ipc --fork \
    --mount-proc=$(pwd)/debian-rootfs/proc \
    chroot ./debian-rootfs /bin/bash
```

Inside the container, try to allocate more than 100 MB:

```bash
# Simple memory-bomb (no extra deps; just python's bytearray):
python3 -c 'b = bytearray(200 * 1024 * 1024); print("ok")'
# Expect: Killed   (the kernel OOM-killed the process inside the cgroup)
```

If `python3` is not in your minbase rootfs, install it briefly with `apt update && apt install -y python3` (you have a real Debian; `apt` works). Or stress it differently:

```bash
# pure shell memory eater:
dd if=/dev/zero of=/tmp/balloon bs=1M count=200
# Expect: dd: writing '/tmp/balloon': No space left on device (if /tmp is small)
# or:    Killed (if memory.max trips first)
```

Exit when you are done:

```bash
exit
```

On the host, clean up:

```bash
sudo rmdir /sys/fs/cgroup/c15-tinybox
```

---

## Step 5 — Stretch: networking (20 min, optional)

Networking is the most fiddly piece. We will skip it in the main build because every distro's `iproute2` package is a little different, and because Docker's defaults work for the rest of the week. If you want to do it, the pattern is:

```bash
# On the host, create a veth pair:
sudo ip link add veth0 type veth peer name veth1

# Start the container with a new net namespace.
# (Same unshare line, plus --net):
sudo unshare --pid --uts --mount --ipc --net --fork \
    --mount-proc=$(pwd)/debian-rootfs/proc \
    chroot ./debian-rootfs /bin/bash &
CONTAINER_PID=$!

# Move one end of the veth into the container's net namespace:
sudo ip link set veth1 netns $CONTAINER_PID

# Inside the container, configure it (you'd do this in a setup script;
# we are doing it from the host with `nsenter` for brevity):
sudo nsenter -t $CONTAINER_PID -n ip addr add 10.10.10.2/24 dev veth1
sudo nsenter -t $CONTAINER_PID -n ip link set veth1 up
sudo nsenter -t $CONTAINER_PID -n ip link set lo up

# On the host, give veth0 an address and bring it up:
sudo ip addr add 10.10.10.1/24 dev veth0
sudo ip link set veth0 up

# Now you can ping from the container to the host:
sudo nsenter -t $CONTAINER_PID -n ping -c 3 10.10.10.1
```

This is what Docker's default `bridge` network is doing under the hood, with `iptables` rules layered on for NAT. We will not dwell on it.

---

## Step 6 — Tear down

```bash
# Container exits as soon as you 'exit' the bash inside it.
# Then on the host:
sudo umount /var/lib/c15/debian-rootfs/proc 2>/dev/null || true

# Optional: leave the rootfs in place — Exercise 2 may reuse it.
# Or delete it:
# sudo rm -rf /var/lib/c15/debian-rootfs
```

---

## Acceptance criteria

You can mark this exercise done when:

- [ ] You have a working Debian rootfs in `/var/lib/c15/debian-rootfs`.
- [ ] You have launched a shell inside it with `unshare --pid --uts --mount --ipc --fork --mount-proc=... chroot ...`.
- [ ] Inside that shell, `ps -ef` shows your shell as PID 1 and no host processes.
- [ ] You changed the hostname inside the namespace without affecting the host's hostname.
- [ ] You created a cgroup, put the shell in it, set `memory.max` to 100 MB, and triggered an OOM kill.
- [ ] You can explain — in your own words, in writing — what each `unshare` flag does. Commit that explanation to a file `notes/by-hand-container.md` in your week-01 repo.

---

## Stretch

- Replace `chroot` with `pivot_root` (you will need to bind-mount the rootfs onto itself first; read `man pivot_root`).
- Add a `user` namespace with `--user --map-root-user`. Drop the `sudo`. Now you have a rootless container.
- Drop `CAP_NET_BIND_SERVICE` and `CAP_SYS_ADMIN` from the container's capability set using `capsh --drop=...` after entering the namespace. Verify that `mount` inside fails.
- Add `seccomp` filtering with the [`bpfcc-tools`](https://github.com/iovisor/bcc) package's `seccomp-helper` — or skip and come back in Week 11.

---

## Hints

<details>
<summary>If <code>debootstrap</code> hangs or fails on a slow connection</summary>

You can use a closer mirror. Replace `http://deb.debian.org/debian` with your country's mirror — see <https://www.debian.org/mirror/list>. Or try `--variant=minbase --include=python3` to bake in `python3` so you do not need network access from inside later.

</details>

<details>
<summary>If <code>ps</code> still shows host processes</summary>

You forgot `--mount-proc`. `ps` reads `/proc/`. Without a fresh proc mount, it is reading the host's. Add `--mount-proc=$(pwd)/debian-rootfs/proc` to the `unshare` line.

</details>

<details>
<summary>If <code>cgroup.procs</code> write fails with <code>EBUSY</code></summary>

Some cgroup v2 controllers cannot have processes in a non-leaf cgroup. Make sure you are writing into a freshly created directory under `/sys/fs/cgroup/` (a leaf), not into the root.

</details>

<details>
<summary>If <code>stat -fc %T /sys/fs/cgroup/</code> returns <code>tmpfs</code></summary>

You are on cgroup v1. On older Ubuntu (20.04 and earlier), v1 was the default; on RHEL 8, v1 is forced. The mount layout is different: there is one directory per controller (`/sys/fs/cgroup/memory/`, `/sys/fs/cgroup/cpu/`). The commands change — e.g., `echo 104857600 > /sys/fs/cgroup/memory/c15-tinybox/memory.limit_in_bytes`. Switching to v2 on Ubuntu 20.04 is one kernel command line flag; see [Ubuntu's cgroup v2 page](https://ubuntu.com/blog/cgroup-v2-stable). For the purposes of this exercise, v1 is acceptable — adapt the commands and continue.

</details>

---

## What just happened

You built a container. You did not call it that, but: it had its own PID namespace, mount namespace, UTS namespace, IPC namespace, its own filesystem root, and was bound by a cgroup. That is what Docker does on Wednesday. Docker also handles image pull, layer storage, networking, registry auth, the daemon, the API, the CLI, and a few thousand other things. But the container itself — the moving part the kernel sees — is what you just made.

When the runtime crashes in production with `failed to clone: invalid argument`, you know that `clone()` is a kernel syscall, the flag bitmap to it includes `CLONE_NEW*` constants, and the argument was probably an unsupported combination (e.g. user namespace on a kernel that has it disabled). You can read the strace. You can read the source.

That is the whole point.

---

When this exercise feels comfortable, move to [Exercise 2 — First Real Docker](exercise-02-first-real-docker.md).
