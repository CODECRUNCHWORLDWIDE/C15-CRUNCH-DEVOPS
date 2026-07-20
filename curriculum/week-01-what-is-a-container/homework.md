# Week 1 Homework

Six problems, ~6 hours total. Commit each in your week-01 repo.

---

## Problem 1 — Namespace inventory (30 min)

Open a Linux shell on a host that has Docker installed. Run:

```bash
docker run --rm -d --name hw1 alpine sleep 3600
CONTAINER_PID=$(docker inspect -f '{{.State.Pid}}' hw1)
sudo ls -l /proc/$CONTAINER_PID/ns/
ls -l /proc/self/ns/
```

**Acceptance.** A file `notes/namespaces.md` containing:

- A Markdown table with one row per namespace type, three columns: namespace name, host inode, container inode.
- A one-sentence answer to: "Why does the `user` namespace inode match between host and container under Docker's defaults?"

---

## Problem 2 — cgroup walk-through (45 min)

Without Docker:

1. Create `/sys/fs/cgroup/hw2-demo`.
2. Set `memory.max` to 50 MB and `cpu.max` to "10000 100000" (10% of one CPU).
3. Move your current shell into the cgroup.
4. Run `stress-ng --vm 1 --vm-bytes 100M --timeout 10s` (or `python3 -c 'bytearray(100*1024*1024)'`) and observe the result.
5. Run a tight CPU loop (`while true; do :; done` works) for 5 seconds; check `cat /sys/fs/cgroup/hw2-demo/cpu.stat` before and after.

**Acceptance.** A file `notes/cgroups.md` containing:

- The exact commands you ran.
- The kernel's response (OOM kill, throttling pattern).
- A one-paragraph explanation in your own words of what `cpu.stat`'s `nr_throttled` and `throttled_usec` mean.

---

## Problem 3 — Inspect an OCI image by hand (45 min)

Use `skopeo` to copy an image to a local OCI layout, then explore it without using `docker`:

```bash
skopeo copy docker://docker.io/library/alpine:3.20 oci:./hw3-alpine:latest
cd hw3-alpine
cat oci-layout
cat index.json | jq
# Pick the manifest digest from index.json, then:
cat blobs/sha256/<that-digest> | jq
# Pick the config digest from inside the manifest, then:
cat blobs/sha256/<that-digest> | jq
```

**Acceptance.** A file `notes/oci-walk.md` that contains:

- The `index.json` content.
- The manifest content with annotations.
- The config content with annotations.
- A 3-sentence summary of how each blob references the next.

---

## Problem 4 — Tag vs digest (45 min)

Pick a popular image (e.g. `nginx:1.27`). Do the following over the course of a few days, or simulate it with two different image versions:

1. Note the digest the tag currently points to with `skopeo inspect docker://docker.io/library/nginx:1.27 | jq -r .Digest`.
2. Pull by tag and by digest, side by side. Confirm both produce the same content with `docker image inspect`.
3. Find a *historical* image — for example, find an older nginx version, or a different tag that has been re-pushed. Show that pulling that same *tag* a year ago would have given a different digest. (You can simulate this by examining `docker image history` of a stale image you have locally.)

**Acceptance.** A file `notes/tag-vs-digest.md` containing:

- The digest the tag currently resolves to.
- An example of *the same tag* resolving to a different digest at a different time, with citation (a screenshot, a registry log, or your own pull date stamps).
- A two-paragraph essay on when a tag is acceptable and when a digest is required.

---

## Problem 5 — A real first Dockerfile (1 h 30 min)

You will write a small Python service and build it three times, each time tighter than the last.

The app is one file, `service.py`:

```python
from flask import Flask
app = Flask(__name__)

@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```

And `requirements.txt`:

```text
flask==3.0.3
gunicorn==22.0.0
```

Write three `Dockerfile`s, each in its own file:

- **`Dockerfile.v1`** — single-stage, naïve, `FROM python:3.12`, `CMD ["python", "service.py"]`.
- **`Dockerfile.v2`** — multi-stage, `FROM python:3.12-slim`, virtualenv copied between stages, gunicorn as the server.
- **`Dockerfile.v3`** — multi-stage with `python:3.12-alpine` *or* a non-root user, `.dockerignore`, `--no-cache-dir`. Aim for under 80 MB.

For each, record:

```bash
docker build -f Dockerfile.vX -t hw5-vX .
docker images hw5-vX --format '{{.Size}}'
docker run -d --rm -p 8080:8080 --name hw5-vX hw5-vX
curl -s localhost:8080/health
docker stop hw5-vX
```

**Acceptance.** A file `notes/three-dockerfiles.md` with:

- A Markdown table: version, base image, final size, build time (use `time docker build`), security posture (root or non-root user, `apt` history present or absent).
- A short paragraph of which one you would ship.
- All three `Dockerfile` variants committed.

---

## Problem 6 — Reflection (30 min)

Write `notes/week-01-reflection.md` (300–400 words) answering:

1. Before this week, in three sentences, what would you have said a "container" is? In three sentences, what would you say now?
2. Which lecture or exercise most changed your mental model? Be specific.
3. What part of Docker still feels like magic? (Hint: networking is the usual answer. There is no shame in that — Week 3 is for it.)
4. What is one thing you want to dig deeper on after C15 — maybe in C18, C19, or on your own?

---

## Time budget

| Problem | Time |
|--------:|----:|
| 1 | 30 min |
| 2 | 45 min |
| 3 | 45 min |
| 4 | 45 min |
| 5 | 1 h 30 min |
| 6 | 30 min |
| **Total** | **~5 h 45 min** |

When done, push your week-01 repo and start the [mini-project](./mini-project/README.md).
