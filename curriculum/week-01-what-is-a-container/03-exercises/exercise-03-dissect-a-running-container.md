# Exercise 3 — Dissect a Running Container

**Goal.** Take a single running container through its whole lifecycle — `create`, `start`, `exec`, `pause`, `stop`, `rm` — and at each stage observe it *from the host* with stock Linux tools: `lsns`, `nsenter`, `/proc/<pid>/`, the cgroup v2 filesystem, and `capsh`. By the end you will be able to point at the exact kernel objects (namespace inodes, cgroup files, the capability bounding set) that make a "container" a container, and watch them appear and disappear as the container changes state. No new abstractions — just the ones from Exercise 1 and 2, observed live.

**Estimated time.** 90 minutes.

---

## Why we are doing this

In Exercise 1 you built the kernel objects by hand. In Exercise 2 you let Docker build them and glanced at the namespace inodes. This exercise closes the loop: you keep Docker's container running and *take it apart with the same host-side tools an SRE uses during an incident* — when the container engine's own CLI is lying to you, or `dockerd` is wedged, or you are on a node where the only thing you trust is `/proc`.

The container lifecycle is the other half. `docker run` hides five distinct states behind one command. When a container is stuck in `Created` and never `Running`, or sits in `Paused` and stops responding, or refuses to `rm` because it is still `Running`, you need to know these are real, separate states the runtime moves through — not Docker UI flavor. By the end you will have driven a container through each state by hand and watched what changes underneath.

When production says `container is paused` or `cannot remove container: container is running` or a process is "gone" from `docker ps` but its cgroup is still pinning 2 GB of RAM, you will know exactly which `/proc` and `/sys` file to read to find the truth.

---

## Setup

You need a **Linux machine** with `sudo` and Docker installed (the same box from Exercise 1 and 2). Docker Desktop's VM works for the Docker commands, but the host-side `/proc` and `lsns` introspection assumes you can get a shell *on the same kernel the container runs on* — i.e. real Linux, a Linux VM, or WSL2. On Docker Desktop for macOS/Windows, run these commands inside the Docker VM (`docker run --rm -it --privileged --pid host justincormack/nsenter1` drops you onto the VM's host namespace) or, more simply, do this exercise on a Linux box.

Install the introspection tools (most are already present):

- **Debian/Ubuntu:** `sudo apt update && sudo apt install -y util-linux libcap2-bin procps`
- **Fedora/RHEL:** `sudo dnf install -y util-linux libcap procps-ng`

These give you `lsns`, `nsenter`, `unshare` (from `util-linux`), `capsh` and `getpcaps` (from `libcap2-bin` / `libcap`), and `ps` (from `procps`). All are OSS and ship in the base repos.

Confirm:

```bash
lsns --version          # lsns from util-linux 2.3x
capsh --version         # libcap
stat -fc %T /sys/fs/cgroup/
# Expect: cgroup2fs   (this exercise assumes cgroup v2 — see the v1 hint if not)
```

Start one long-lived container we will dissect for the whole exercise. We give it explicit limits so the cgroup files have interesting values:

```bash
docker run -d --name c15-dissect \
    --memory 256m \
    --cpus 0.5 \
    debian:bookworm sleep 3600
```

Grab its host-side PID once — we will reuse it constantly:

```bash
PID=$(docker inspect -f '{{.State.Pid}}' c15-dissect)
echo "container main process is host PID $PID"
# Expect: a normal host PID like 48213
```

That number is the whole trick. From the host's point of view, the container's `sleep 3600` is just **a regular process with PID `$PID`**. Everything below reads that process's `/proc` entry.

---

## Step 1 — List the container's namespaces from the host (~10 min)

`lsns` reads `/proc/*/ns/` for every process and groups them by namespace. Filter to your container's PID:

```bash
sudo lsns -p $PID
```

Expect something like:

```text
        NS TYPE   NPROCS   PID USER   COMMAND
4026531835 cgroup      1 48213 root   sleep 3600
4026531837 user        1 48213 root   sleep 3600
4026532187 mnt         1 48213 root   sleep 3600
4026532188 uts         1 48213 root   sleep 3600
4026532189 ipc         1 48213 root   sleep 3600
4026532190 pid         1 48213 root   sleep 3600
4026532192 net         1 48213 root   sleep 3600
```

Read the `NS` column — those are namespace **inode numbers**, the kernel's identity for each namespace. Now list *your own* namespaces:

```bash
lsns -p $$
```

Compare inode-by-inode. The `mnt`, `uts`, `ipc`, `pid`, and `net` inodes differ between you and the container — those are isolated. The `user` and `cgroup` inodes are usually **identical** to the host's: Docker does not enable a user namespace by default (container root is host root, exactly as you noted in Exercise 2), and the cgroup *namespace* (which just changes what the container sees as its cgroup root) is sometimes shared even though the cgroup *limits* are not.

Write both lists into `notes/lifecycle.md` under a heading "Step 1 — namespaces (Running)". You will compare against later states.

---

## Step 2 — Enter the container with `nsenter`, no Docker (~10 min)

`docker exec` is convenient but it goes through `dockerd` → `containerd` → `runc`. The underlying syscall is `setns()`, and `nsenter` calls it directly. Enter every namespace of `$PID`:

```bash
sudo nsenter --target $PID --mount --uts --ipc --net --pid --cgroup -- /bin/bash
```

You are now inside the container — without Docker having been involved at all. Verify:

```bash
ps -ef
# Expect: PID 1 is `sleep 3600`. Your bash is a low PID in the SAME pid namespace.
hostname
# Expect: the container's hostname (its short ID), not the host's.
ls /
# Expect: Debian's rootfs — because --mount put you in the container's mount namespace.
cat /etc/os-release
```

This is the SRE's "the daemon is wedged but I still need inside" move. `nsenter` needs only `/proc` and root; it does not need a working Docker. Exit back to the host:

```bash
exit
```

> **Why the flag list matters.** Drop `--mount` and you keep the host's filesystem view while sharing the container's PID namespace — a genuinely useful debug stance (you have your own tools but can see the container's processes). Drop `--pid` and `ps` shows the host. Each flag is one `setns()` into one namespace. This is the same à-la-carte joining Kubernetes ephemeral debug containers do.

---

## Step 3 — Read the cgroup the kernel put it in (~15 min)

The namespaces isolate *what the container sees*. The cgroup limits *what it can consume*. Find the container's cgroup path from the host:

```bash
cat /proc/$PID/cgroup
# Expect (cgroup v2 — single line starting with 0::):
# 0::/system.slice/docker-<64-hex-id>.scope
```

That path is relative to `/sys/fs/cgroup/`. Build the full path and look at the limit files:

```bash
CG=/sys/fs/cgroup$(cat /proc/$PID/cgroup | cut -d: -f3)
echo "cgroup dir: $CG"

cat $CG/memory.max
# Expect: 268435456     (= 256 MiB, the --memory 256m you set)

cat $CG/cpu.max
# Expect: 50000 100000  (= 0.5 CPU: 50ms of every 100ms, from --cpus 0.5)

cat $CG/cgroup.procs
# Expect: the container's PIDs (host-namespace PIDs), including $PID
```

These are the *same files* you wrote by hand in Exercise 1, Step 4 — except `runc` wrote them for you. Watch the live accounting:

```bash
cat $CG/memory.current
# Expect: a few MB — current real usage of everything in the container

cat $CG/pids.current
# Expect: 1   (just the sleep process)
```

Now prove the limit is real, the way you did by hand. In another terminal, exec a memory bomb *inside* the container and watch the cgroup OOM-kill it:

```bash
docker exec c15-dissect sh -c 'cat /dev/zero | head -c 400m | tail' ; echo "exit=$?"
# Expect: the process is Killed; exit code reflects SIGKILL (137).
```

Back on the host, the cgroup recorded the kill:

```bash
grep oom_kill $CG/memory.events
# Expect: oom_kill 1   (or higher) — the kernel OOM-killer fired inside this cgroup
```

`docker ps` still shows the container `Up` — the *main* process (`sleep`) survived; only the bomb died. That distinction (one process OOM-killed vs. the container exiting) is a classic incident-time confusion. You just read the ground truth out of `memory.events`.

Record `memory.max`, `cpu.max`, and the `oom_kill` count in `notes/lifecycle.md`.

---

## Step 4 — Inspect the capability set (~10 min)

Namespaces and cgroups are two of the three pillars from Lecture 1. The third is **capabilities** — the kernel's way of splitting "root" into ~40 independent privileges. A default Docker container does *not* run with full root; `runc` drops most capabilities.

Read the bounding set of the container's main process directly from `/proc`:

```bash
grep CapBnd /proc/$PID/status
# Expect a hex mask, e.g.: CapBnd: 00000000a80425fb
```

Decode that hex mask into human-readable capability names with `capsh`:

```bash
capsh --decode=$(grep CapBnd /proc/$PID/status | awk '{print $2}')
# Expect a list like: cap_chown,cap_dac_override,...,cap_net_bind_service,cap_setuid,...
```

Compare against a full root process on the host:

```bash
grep CapBnd /proc/1/status
capsh --decode=$(grep CapBnd /proc/1/status | awk '{print $2}')
# Host PID 1 has the FULL set (cap_sys_admin, cap_net_admin, cap_sys_module, ...).
```

Notice what is **missing** from the container's set: `cap_sys_admin` (mount, many privileged ops), `cap_net_admin` (reconfigure networking), `cap_sys_module` (load kernel modules), `cap_sys_time` (set the clock). That is why `mount` and `ip link add` fail inside a default container even though you are "root." Prove it:

```bash
docker exec c15-dissect mount -t tmpfs none /mnt 2>&1; echo "exit=$?"
# Expect: mount: permission denied  — cap_sys_admin was dropped. exit != 0.
```

Now run a container *with* that capability and watch the same command succeed:

```bash
docker run --rm --cap-add SYS_ADMIN debian:bookworm \
    sh -c 'mount -t tmpfs none /mnt && echo "mounted ok" && mount | grep /mnt'
# Expect: mounted ok   — granting CAP_SYS_ADMIN re-enabled mount().
```

This is the granularity production security review cares about. "`--privileged`" hands back *all* of these at once and is the single biggest red flag in a container security audit. Note the container's capability list in `notes/lifecycle.md`.

---

## Step 5 — Walk the lifecycle and watch the kernel objects change (~25 min)

Up to now the container has been `Running` the whole time. Now drive it through every state and observe what happens to the PID, the namespaces, and the cgroup. Keep a terminal on the host with `$PID` handy (re-fetch it whenever you start the container, since it changes).

### 5a. Pause → the namespaces survive, the process freezes

```bash
docker pause c15-dissect
docker inspect -f '{{.State.Status}}' c15-dissect      # Expect: paused
```

`pause` uses the **cgroup freezer** — it does *not* stop the process or tear down anything. Confirm:

```bash
cat $CG/cgroup.freeze
# Expect: 1   (1 = frozen, 0 = thawed)
sudo lsns -p $PID
# Expect: the SAME namespace inodes as Step 1. Nothing was destroyed.
```

The process is still there, still PID `$PID`, still in all its namespaces — it is simply not scheduled. A paused container that "stops responding" is *working as designed*. Unfreeze it:

```bash
docker unpause c15-dissect
cat $CG/cgroup.freeze     # Expect: 0
```

### 5b. Stop → the process dies, the namespaces vanish, the cgroup is reclaimed

```bash
docker stop c15-dissect
docker inspect -f '{{.State.Status}}' c15-dissect      # Expect: exited
```

`stop` sends `SIGTERM`, waits (default 10 s), then `SIGKILL`. The main process exits. When a process exits, the kernel destroys any namespace it was the last member of, and `runc` removes the cgroup directory. Prove both:

```bash
ls /proc/$PID 2>&1
# Expect: No such file or directory — the process is gone.
ls $CG 2>&1
# Expect: No such file or directory — the cgroup directory was removed.
sudo lsns | grep -c "$PID"
# Expect: 0
```

The container is `exited` but **not deleted** — its config and writable layer still exist. That is why `docker ps -a` still lists it and you can restart it.

### 5c. Start again → brand-new kernel objects, new PID

```bash
docker start c15-dissect
PID=$(docker inspect -f '{{.State.Pid}}' c15-dissect)
echo "new host PID: $PID"
sudo lsns -p $PID
```

The PID is **different** from before, and the namespace inodes are **different** too. Same container *identity* (same name, same image, same writable layer), entirely new kernel objects. "Restart" is "tear down all the kernel state and build it again from the stored config" — there is no such thing as a paused-on-disk namespace.

### 5d. Create without start → config exists, no process yet

There is a state before `Running` that `docker run` blows past. Make it visible:

```bash
docker create --name c15-created debian:bookworm sleep 60
docker inspect -f '{{.State.Status}}' c15-created      # Expect: created
docker inspect -f '{{.State.Pid}}' c15-created         # Expect: 0  (no process!)
```

`created` means `runc` has the bundle and `config.json` ready but has **not** executed the entrypoint. PID is `0` because there is no process. This is the state a container is stuck in when an init hook fails before exec. Start it to leave the state:

```bash
docker start c15-created
docker inspect -f '{{.State.Pid}}' c15-created         # Expect: a real PID now
```

### 5e. The lifecycle table

Fill in `notes/lifecycle.md` from your own observations:

| State     | Host process? | Namespaces exist? | Cgroup dir exists? | How you got here     |
|-----------|---------------|-------------------|--------------------|----------------------|
| `created` | No (PID 0)    | No                | Yes (limits set)   | `docker create`      |
| `running` | Yes           | Yes               | Yes                | `docker start`       |
| `paused`  | Yes (frozen)  | Yes               | Yes (`freeze` = 1) | `docker pause`       |
| `exited`  | No            | No                | No                 | `docker stop`        |

Confirm each row against what you actually saw. The "Cgroup dir exists?" answer for `created` is subtle — verify it on your kernel and note what you find.

---

## Step 6 — Clean up

```bash
docker rm -f c15-dissect c15-created
docker ps -a | grep c15-          # Expect: nothing
```

`docker rm` is the fifth lifecycle verb: it deletes the config and the writable layer. After this, the container *identity* is gone — not just its kernel objects but its on-disk record. `rm -f` forces it even if running (it stops first). This is why CI scripts use `docker run --rm`: auto-`rm` on exit so dead containers don't pile up.

---

## Acceptance criteria

You can mark this exercise done when:

- [ ] You captured `lsns -p $PID` for the container and `lsns -p $$` for yourself, and identified which namespaces are shared vs. isolated.
- [ ] You entered the container with `nsenter` (no `docker exec`) and confirmed you were inside via `ps -ef` and `hostname`.
- [ ] You located the container's cgroup directory from `/proc/$PID/cgroup` and read `memory.max`, `cpu.max`, and `memory.events`, and triggered an in-container OOM kill that showed up in `memory.events`.
- [ ] You decoded the container's `CapBnd` with `capsh`, named at least three capabilities Docker drops by default, and demonstrated one of them (e.g. `mount`) failing inside and succeeding with `--cap-add`.
- [ ] You drove the container through `pause`, `stop`, `start`, and `create`, and verified for each state whether the host process, namespaces, and cgroup directory exist.
- [ ] You committed `notes/lifecycle.md` with the namespace comparison, the cgroup values, the capability list, and the completed lifecycle table.

---

## Stretch

- **Find the container's PID by hand, without `docker inspect`.** Run `sudo lsns -t pid` and identify the container's PID namespace by its lone `sleep 3600`. Then read `$CG` from that PID. You have now found a container with zero Docker CLI involvement — the skill for when `dockerd` is down.
- **Watch a namespace's reference count.** Run `docker exec -d c15-dissect sleep 999` to add a process, then re-run `sudo lsns -p $PID` and note the `NPROCS` column climbed. A namespace lives as long as *any* process references it (or a bind-mount or open fd pins it). That reference counting is why a namespace can outlive its PID 1.
- **Pin a namespace after the container dies.** Before stopping the container, `sudo touch /tmp/netns && sudo mount --bind /proc/$PID/ns/net /tmp/netns`. Stop the container. The net namespace inode *survives* in `lsns` because your bind-mount holds a reference. `sudo umount /tmp/netns` to release it. This is exactly how `ip netns` persists namespaces.
- **Compare `crun` to `runc`.** If your distro has `podman`, run the same `sleep 3600` under Podman with `--runtime crun` and compare the namespace/cgroup layout. Same kernel objects, different (smaller, C instead of Go) runtime binary made them.

---

## Hints

<details>
<summary>If <code>stat -fc %T /sys/fs/cgroup/</code> returns <code>tmpfs</code> (cgroup v1)</summary>

You are on cgroup v1 (older Ubuntu, RHEL 8 with the default kernel cmdline). The paths differ: there is one tree per controller. The container's memory cgroup is at `/sys/fs/cgroup/memory/docker/<id>/`, CPU at `/sys/fs/cgroup/cpu/docker/<id>/`, and the limit files are named `memory.limit_in_bytes` and `cpu.cfs_quota_us` / `cpu.cfs_period_us`. The freezer is `/sys/fs/cgroup/freezer/docker/<id>/freezer.state` (`FROZEN`/`THAWED`). Adapt the reads and continue; the *concepts* are identical. Switching the host to v2 is one kernel cmdline flag — see [Ubuntu's cgroup v2 page](https://ubuntu.com/blog/cgroup-v2-stable).

</details>

<details>
<summary>If <code>$CG</code> comes out wrong or empty</summary>

`cat /proc/$PID/cgroup` on v2 prints a single line `0::/...`. The `cut -d: -f3` pulls the path after the second colon. If `$PID` is stale (you restarted the container), re-fetch it: `PID=$(docker inspect -f '{{.State.Pid}}' c15-dissect)`. The cgroup path changes on every start.

</details>

<details>
<summary>If <code>nsenter</code> fails with "reassociate to pid namespace: Invalid argument"</summary>

Joining a PID namespace with `setns()` only affects *children* you fork after joining — you cannot move an already-running process into a PID namespace. `nsenter` handles this by forking, which is why you must give it a command to run (the trailing `-- /bin/bash`). If you omit the command it tries to exec your current shell and can trip this. Always pass a command.

</details>

<details>
<summary>If <code>capsh --decode</code> isn't available</summary>

Some minimal `libcap` builds ship `getpcaps` but not `capsh`. Use `getpcaps $PID` instead — it prints the capability sets of a running PID in human-readable form directly, no hex decoding needed.

</details>

<details>
<summary>If you're on Docker Desktop (macOS/Windows) and <code>/proc/$PID</code> doesn't exist</summary>

Your shell is on the macOS/Windows host, but the container runs inside Docker Desktop's Linux VM — different kernel, different `/proc`. Get onto the VM's namespace first: `docker run -it --rm --privileged --pid host justincormack/nsenter1`. That drops you into the VM's host PID namespace where `/proc/$PID` and `lsns` work. Or just do this exercise on a real Linux box; it is cleaner.

</details>

---

## What just happened

You took one container through its entire life and watched the kernel objects appear, freeze, vanish, and reappear — using only `/proc`, `/sys/fs/cgroup`, and four small `util-linux`/`libcap` tools. You now know that:

- A "running container" is a host process whose `/proc/<pid>/ns/` inodes differ from yours and whose `/proc/<pid>/cgroup` points at a limits directory under `/sys/fs/cgroup/`.
- `pause` is the cgroup freezer, not a teardown. `stop` is a real teardown — process dies, namespaces and cgroup vanish. `start` rebuilds everything new. `create` sets up config with no process. `rm` deletes the on-disk identity.
- "Root in a container" is a reduced capability set; `--privileged` and `--cap-add SYS_ADMIN` hand back the dangerous bits, which is exactly what security review looks for.
- You can do every bit of this with the daemon dead, because the truth lives in `/proc` and `/sys`, not in `dockerd`.

That is the difference between operating containers and trusting them. When the next incident says "the container is paused and won't die" or "`docker ps` is clean but memory is pinned," you know which file holds the answer.

---

When this exercise feels comfortable, move on to the [Week 1 challenge](../04-challenges/challenge-01-shrink-the-image.md).
