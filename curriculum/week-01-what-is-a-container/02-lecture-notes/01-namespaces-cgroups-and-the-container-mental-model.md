# Lecture 1 — Namespaces, cgroups, and the Container Mental Model

> **Outcome:** You can explain, in plain language, the three Linux kernel features that make containers possible. You can list the seven Linux namespaces. You can say in two sentences how a container differs from a virtual machine. You can do all of this without using the word "Docker."

## 1. The shortest correct definition of a container

A **Linux container** is an ordinary Linux process that has been started with:

1. A restricted view of system resources, via **namespaces**.
2. Resource limits and accounting, via **cgroups**.
3. A reduced set of privileges, via **capabilities** (and often `seccomp`, `AppArmor`, `SELinux`).
4. Often, but not always, a private filesystem root, via **`chroot`** or **`pivot_root`**.

That is it. There is no "container kernel object" in Linux. There is no `struct container` anywhere in the source tree. The word "container" is shorthand for "a process configured to look like it owns the machine."

Everything else — Docker, Kubernetes, OCI images, registries, sidecars, service meshes — is *tooling on top of those four primitives*. If you understand the primitives, every layer above them is just a UX choice.

This lecture covers the primitives. Lecture 2 covers the tooling.

---

## 2. A container is not a virtual machine

A **virtual machine** is a complete simulated computer. A hypervisor (KVM, Xen, Hyper-V, VMware ESXi) carves the host's hardware into virtual hardware, and each VM boots its own kernel on its own virtual CPU and virtual disk. The boundary is hardware-level: the guest kernel cannot directly see the host kernel.

A **container** shares the host's kernel. There is one kernel running on the host. Every process — yours, mine, the database, the web server — is on the same kernel. A container is just a process tree that has been *partitioned* by that one kernel into a smaller world.

The distinction matters operationally:

| Axis | Virtual Machine | Container |
|------|-----------------|-----------|
| **Kernel** | Each VM runs its own kernel | All containers share the host kernel |
| **Boot time** | Seconds to minutes (full OS boot) | Milliseconds (it is `fork+exec`) |
| **Memory overhead** | Hundreds of MB (kernel + init + sshd) | Single-digit MB (just the process) |
| **Density** | Tens per host | Thousands per host |
| **Isolation** | Hardware-virtualization strong | Namespace-strong, but kernel-shared |
| **Security model** | Hypervisor escape is the boundary | Kernel escape *is* the host (a serious bug in the kernel breaks everyone) |
| **OS variety** | Run any OS the hypervisor supports | All containers must use the host kernel's ABI (you cannot run a FreeBSD container on Linux) |

A practical consequence: a Linux container cannot meaningfully run Windows binaries, because there is no Windows kernel underneath. When Docker Desktop on a Mac "runs Linux containers," it is silently running them inside a Linux VM. The VM is doing the kernel-sharing; Docker is doing the namespacing.

A second practical consequence: a kernel-level vulnerability (think *Dirty Pipe*, *Dirty COW*) breaks every container on the host at once. VMs have a stronger boundary against that class of attack.

---

## 3. The seven (eight) Linux namespaces

A **namespace** is a kernel mechanism that gives a process its own view of one kind of resource. Linux currently supports eight namespace types, all of which are listed in [`namespaces(7)`](https://man7.org/linux/man-pages/man7/namespaces.7.html):

| Namespace | Constant | What it isolates |
|-----------|----------|------------------|
| **`mount`** | `CLONE_NEWNS` | The mount table: which filesystems are mounted where |
| **`pid`** | `CLONE_NEWPID` | The process ID number space; PID 1 inside is not PID 1 outside |
| **`net`** | `CLONE_NEWNET` | Network interfaces, routing tables, firewall rules, sockets |
| **`uts`** | `CLONE_NEWUTS` | The hostname and NIS domain name returned by `uname()` |
| **`ipc`** | `CLONE_NEWIPC` | System V IPC objects (message queues, semaphores, shared memory) |
| **`user`** | `CLONE_NEWUSER` | UID and GID mappings; lets unprivileged users have "root" inside |
| **`cgroup`** | `CLONE_NEWCGROUP` | The view of `/proc/self/cgroup`; isolates the cgroup hierarchy |
| **`time`** | `CLONE_NEWTIME` | The system clock offset (rare; added in Linux 5.6) |

Each namespace type is independent. A process can be in a new `pid` namespace but share the host's `net` namespace. That combination is exactly what `kubectl exec` produces when you `exec` into a running pod: the new shell joins the existing pod's namespaces.

You can see your own namespaces by listing `/proc/self/ns/`:

```bash
$ ls -l /proc/self/ns/
total 0
lrwxrwxrwx 1 you you 0 May 12 14:32 cgroup -> 'cgroup:[4026531835]'
lrwxrwxrwx 1 you you 0 May 12 14:32 ipc    -> 'ipc:[4026531839]'
lrwxrwxrwx 1 you you 0 May 12 14:32 mnt    -> 'mnt:[4026531840]'
lrwxrwxrwx 1 you you 0 May 12 14:32 net    -> 'net:[4026531992]'
lrwxrwxrwx 1 you you 0 May 12 14:32 pid    -> 'pid:[4026531836]'
lrwxrwxrwx 1 you you 0 May 12 14:32 user   -> 'user:[4026531837]'
lrwxrwxrwx 1 you you 0 May 12 14:32 uts    -> 'uts:[4026531838]'
```

The numbers in brackets are **inode numbers** for each namespace. Two processes are in the same `pid` namespace if and only if their `/proc/<pid>/ns/pid` symlinks point to the same inode. Run that `ls` once on the host, then again inside a `docker run --rm -it alpine sh`, and compare. The container's inode numbers will differ for every namespace Docker spun up — and *match* the host's for any namespace it shared.

### How a process enters a namespace

There are three syscalls. You almost never use them directly; tools like `unshare`, `nsenter`, and runtimes like `runc` do it for you.

- **`clone()` / `clone3()`** — create a new process, optionally with new namespaces. This is how containers are *born*.
- **`unshare()`** — disassociate the current process from one or more of its current namespaces and put it in fresh ones. This is what the `unshare(1)` command does.
- **`setns()`** — join an existing namespace by opening one of those `/proc/<pid>/ns/*` files. This is how `docker exec` and `kubectl exec` work.

### The PID namespace, made tangible

The most visceral namespace is `pid`. Inside a new PID namespace, your process gets to be PID 1. That is the same PID that `init` (or `systemd`) has on the host. To the process, it looks like it just booted on a fresh machine.

```bash
$ sudo unshare --pid --fork --mount-proc bash
# ps -ef
UID          PID    PPID  C STIME TTY          TIME CMD
root           1       0  0 14:35 pts/0    00:00:00 bash
root           4       1  0 14:35 pts/0    00:00:00 ps -ef
# echo "I am PID 1"
I am PID 1
# exit
```

That `bash` is PID 1 inside the namespace. From the host, it has a perfectly ordinary high-numbered PID. Run `ps -ef | grep bash` on the host while the namespace is open and you will find it.

This is also where the famous **PID-1 zombie problem** comes from. On a real Linux box, PID 1 is `init`. When any process orphans, `init` adopts it. Inside a container, `bash` (or `python`, or `node`) is PID 1, and it does *not* know how to reap orphans. If your application spawns subprocesses and never `wait()`s for them, you accumulate zombies. The fix is either:

- Use a tiny init like `tini` or `dumb-init` as PID 1.
- Pass `docker run --init` (Docker does the same thing for you).
- Reap children yourself in your application code (don't).

### The mount namespace, made tangible

A new mount namespace gives the process its own *copy* of the mount table. Inside, you can mount and unmount things without affecting the host. Inside a container, `/proc`, `/sys`, `/dev`, and your application's filesystem are usually fresh mounts.

This is *also* where `chroot` got upgraded. Old-school `chroot` changes the apparent root of the filesystem, but a sufficiently determined process can `chdir("..")` back out. **`pivot_root`**, used inside a fresh mount namespace, properly swaps the rootfs out from under the process so there is no path back. Real container runtimes use `pivot_root`, not `chroot`. We will still use `chroot` in tomorrow's exercise because it is the simpler primitive — the security tradeoff is acceptable in a learning context.

### The user namespace, made tangible

User namespaces are the youngest of the major namespaces (Linux 3.8, 2013) and the most powerful for security. They let an unprivileged user have "root" *inside* the namespace, with that "root" mapped to their unprivileged UID on the host.

```bash
$ id
uid=1000(you) gid=1000(you) groups=1000(you)
$ unshare --user --map-root-user bash
# id
uid=0(root) gid=0(root) groups=0(root),65534(nogroup)
# touch /etc/passwd
touch: cannot touch '/etc/passwd': Permission denied
```

You "are root" inside, but the kernel still enforces real-UID permissions on resources outside the namespace. Rootless Podman, rootless Docker, and the Kubernetes "user-namespace pods" feature all hinge on this. It is one of the few mechanisms that meaningfully reduces the kernel-shared-with-host risk.

---

## 4. cgroups: limits and accounting

Namespaces give a process its own *view*. cgroups give it a *bound*.

A **cgroup** (control group) is a kernel mechanism for grouping processes and applying resource controls. There are two generations in the wild:

- **cgroup v1** — multiple separate hierarchies, one per resource type (`cpu`, `memory`, `blkio`, etc.). Default on older distros.
- **cgroup v2** — single unified hierarchy. Default on every recent distro (Fedora 31+, Ubuntu 22.04+, Debian 11+). What you should learn first.

You interact with cgroups by writing to a virtual filesystem mounted at `/sys/fs/cgroup`. To limit a process to 50% of one CPU and 100 MB of memory:

```bash
# Create a cgroup
sudo mkdir /sys/fs/cgroup/demo

# Set limits
echo "50000 100000" | sudo tee /sys/fs/cgroup/demo/cpu.max     # 50ms per 100ms = 50% of 1 CPU
echo "100M"          | sudo tee /sys/fs/cgroup/demo/memory.max # 100 MB hard cap

# Move a process in
echo $$ | sudo tee /sys/fs/cgroup/demo/cgroup.procs            # $$ = current shell

# Anything this shell now spawns is bound by those limits.
stress --vm 1 --vm-bytes 200M  # will be OOM-killed
```

That is the entire mechanism. Every "CPU limit" and "memory limit" in Docker, in Kubernetes, in `systemd` (slices), in `nspawn` — all of them are writing to these files. The Kubernetes `resources.limits.memory: "100Mi"` in your pod manifest ends up as four numeric digits in a file under `/sys/fs/cgroup`.

cgroups also provide *accounting* — `cpu.stat`, `memory.current`, `memory.peak`, `pressure` files — which is where every container metric you have ever seen on a dashboard ultimately comes from.

### The OOM killer and cgroups

When a process in a cgroup hits `memory.max`, the kernel's **OOM killer** chooses a victim inside that cgroup and terminates it. The rest of the host is unaffected. This is why "out-of-memory inside a container" usually looks like a clean `exit code 137` (= 128 + SIGKILL 9) and not a host-wide meltdown.

Operationally, when a container dies mysteriously with code 137, the answer is almost always "it hit its memory limit." `kubectl describe pod` or `docker inspect` will show `OOMKilled: true`.

---

## 5. Capabilities and the rest of the security toolbox

Traditional Unix splits processes into "root" (UID 0) and "everyone else." That is too coarse. **Capabilities** (Linux 2.2, 1999) split root's powers into ~40 named permissions: `CAP_NET_BIND_SERVICE` lets you bind ports < 1024, `CAP_SYS_ADMIN` lets you `mount`, `CAP_NET_ADMIN` lets you change routing tables, and so on.

A container that runs "as root" typically does *not* have all the capabilities the host's root would have. Docker drops most of them by default. The starting capability set for a Docker container is:

```text
CAP_AUDIT_WRITE        CAP_CHOWN              CAP_DAC_OVERRIDE
CAP_FOWNER             CAP_FSETID             CAP_KILL
CAP_MKNOD              CAP_NET_BIND_SERVICE   CAP_NET_RAW
CAP_SETFCAP            CAP_SETGID             CAP_SETPCAP
CAP_SETUID             CAP_SYS_CHROOT
```

That is 14 of ~40. The dropped ones include `CAP_SYS_ADMIN` (a real `root` superpower) and `CAP_NET_ADMIN`. You can verify in any running container:

```bash
docker run --rm alpine sh -c 'apk add -q libcap; capsh --print'
```

There are three more layers of restriction commonly applied:

- **`seccomp`** — a kernel filter on which *system calls* a process may issue. Docker ships a default profile that blocks ~50 dangerous syscalls (raw `ptrace`, `reboot`, `kexec_load`, etc.). Source: [moby/profiles/seccomp](https://github.com/moby/moby/blob/master/profiles/seccomp/default.json).
- **`AppArmor`** (Debian/Ubuntu) or **`SELinux`** (Fedora/RHEL) — mandatory access control. Adds path- or label-based restrictions on top.
- **Read-only root filesystem** (`docker run --read-only`) — flips the rootfs to read-only at mount time. Cheap and effective.

You do not need to memorize the list. You need to know it exists, so that when a hardened image refuses to write to `/tmp`, you can guess the cause in one go.

---

## 6. Where `chroot` fits

`chroot` predates everything else here. It is the Unix call that changes a process's apparent root directory, dating to 1979 in V7 Unix. By itself, `chroot` is **not** a security boundary — a process with `CAP_SYS_CHROOT` can `chroot` again and escape. But combined with a mount namespace and dropped capabilities, it gives you the "your `/` is a directory I picked" piece of the container illusion.

We will use `chroot` in tomorrow's exercise because the command is one line and the concept is small. Real runtimes use `pivot_root` for the reasons above. Both produce the same user-visible effect: `ls /` shows the contents of a directory you chose, not the host's `/`.

---

## 7. A worked example: a one-line container

Here is a container in a single shell pipeline. You will execute a richer version of this in Exercise 1, but read it now to anchor the concepts.

```bash
# 1. Get a Debian rootfs (one-time, ~100 MB).
sudo debootstrap --variant=minbase stable /var/lib/c15/debian-rootfs

# 2. Launch a process inside fresh namespaces, with that rootfs as /,
#    and bind /proc so 'ps' works.
sudo unshare --pid --net --mount --uts --ipc --fork --mount-proc=/var/lib/c15/debian-rootfs/proc \
    chroot /var/lib/c15/debian-rootfs /bin/bash
```

Inside that shell:

```bash
# hostname-isolated:
root@host:/# hostname tinybox && hostname
tinybox

# ps-isolated:
root@tinybox:/# ps -ef
UID          PID    PPID  C STIME TTY          TIME CMD
root           1       0  0 14:50 ?        00:00:00 /bin/bash
root           5       1  0 14:50 ?        00:00:00 ps -ef

# net-isolated:
root@tinybox:/# ip addr
1: lo: <LOOPBACK> mtu 65536 qdisc noop state DOWN
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
```

That is a container. No Docker. No image format. No registry. About 200 MB of disk and ~5 ms of CPU to start. The reason your `docker run` looks fancy is not because the kernel is doing anything different — it is doing exactly this — but because Docker is shipping the rootfs, networking, image cache, layer storage, CLI, and registry plumbing on top.

---

## 8. Operational consequences

Why does any of this matter for the rest of your DevOps career? Five reasons.

1. **Cost.** A VM has hundreds of MB of overhead. A container has single-digit MB. On a fleet of 1000 services, that is the difference between $50k/month and $5k/month on cloud spend. Container density is why Netflix and Spotify use them.

2. **Startup time.** A VM takes seconds to minutes to boot. A container takes milliseconds. This is why autoscalers exist — and why "scale to zero" is feasible only for containers.

3. **Reproducibility.** A container image is a tarball + a JSON manifest. Two engineers on two laptops who pull the same image digest get *bit-identical* filesystems. That is a property the rest of the industry (npm, pip, apt) is still catching up to.

4. **Security boundary calibration.** Containers are *not* a strong boundary against a malicious tenant. If you run untrusted code (a multi-tenant CI runner, a serverless platform), use VMs (Firecracker, Kata, gVisor) under your containers. If you control the workload, containers are fine.

5. **Debuggability.** Knowing what a namespace is changes how you read incidents. "The container can't reach the database" → which network namespace is it in? "DNS is broken in the pod" → is the `mnt` namespace bind-mounting a stale `/etc/resolv.conf`? "Out of file descriptors" → which cgroup's `pids.max`? Operations is the discipline of asking these questions, fast, at 3 AM.

---

## 9. Self-check

Without re-reading:

1. Name the four kernel features that together make a container.
2. List five of the eight Linux namespaces and what each isolates.
3. Why is a container started with `--pid` always *also* given `--mount-proc`?
4. What is the difference between `chroot` and `pivot_root` for the purposes of containerization?
5. In which generation of cgroups (v1 or v2) is there a single unified hierarchy?
6. A container exits with status code 137. What is the most likely cause?

---

## Further reading

- **Michael Kerrisk — `namespaces(7)`** — the man page, but written like a textbook chapter:
  <https://man7.org/linux/man-pages/man7/namespaces.7.html>
- **Michael Kerrisk — `cgroups(7)`**: <https://man7.org/linux/man-pages/man7/cgroups.7.html>
- **LWN — "Namespaces in operation, part 1" (free) — the deepest free write-up**:
  <https://lwn.net/Articles/531114/>
- **Liz Rice — "Containers from Scratch" talk (free, 40 min)**:
  <https://www.youtube.com/watch?v=8fi7uSYlOdc>
- **Jess Frazelle — "Setting the record straight: containers vs zones vs jails vs VMs"**:
  <https://blog.jessfraz.com/post/containers-zones-jails-vms/>

Next: [Lecture 2 — From Tarball to Image: The OCI Stack](./02-from-tarball-to-image-the-oci-stack.md).
