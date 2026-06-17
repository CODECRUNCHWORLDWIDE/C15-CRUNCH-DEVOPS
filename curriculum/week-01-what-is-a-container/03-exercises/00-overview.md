# Week 1 — Exercises

Three drills. Each takes 60–90 minutes. Do them in order — each one only lands if the one before it did.

1. **[Exercise 1 — Build a Container by Hand](./exercise-01-build-a-container-by-hand.md)** — `unshare` + `chroot` + a Debian rootfs tarball. No Docker. (~90 min)
2. **[Exercise 2 — First Real Docker](./exercise-02-first-real-docker.md)** — the same container, with Docker, then a side-by-side comparison. (~60 min)
3. **[Exercise 3 — Dissect a Running Container](./exercise-03-dissect-a-running-container.md)** — drive one container through its full lifecycle and take it apart live from the host with `lsns`, `nsenter`, the cgroup files, and `capsh`. (~90 min)

## Workflow

- Type the commands, do not paste them. The point is to feel each one.
- After each exercise, write down — in your notes file — what changed in your mental model. Two sentences is enough.
- Do not skip Exercise 1 because Docker is "obviously easier." Skipping it is the point at which DevOps becomes wizardry instead of engineering.

## Platform requirements

- Exercise 1 requires a **Linux** machine where you can run `sudo`. macOS native and Windows native will not work. WSL2, a Linux VM, or a cloud VM all work.
- Exercise 2 requires Docker installed. Docker Desktop is fine.

## Self-grading

After each exercise, ask yourself: "Could I explain this to a junior engineer in 3 minutes?" If yes, move on. If no, re-read the relevant section of the lectures before attempting the next.
