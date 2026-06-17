# Challenge 02 — Write a Readiness and Liveness Probe for a Misbehaving Python API

**Goal.** You are given a Python API that takes 15-30 seconds to warm up at startup, and that occasionally hangs (becomes unresponsive but does not exit). Write a Kubernetes probe configuration that distinguishes the two states the cluster needs to know about — "this pod is starting; do not send it traffic" vs "this pod is wedged; restart it" — and verify your configuration works.

**Estimated time.** 1-2 hours (45 min implementing, 45 min testing and writing up).

**Cost.** $0.00 (entirely local on the `kind` cluster).

---

## Why we are doing this

Lecture 3 Section 4 told you that readiness and liveness probes solve different problems. This challenge is the proof. A naive probe configuration — same endpoint, same interval, same threshold for both probes — produces one of two pathologies: (a) the cluster restarts pods during their normal slow startup (because the liveness probe fails while the app is warming up), or (b) the cluster routes traffic to a pod that is wedged (because the readiness probe is too lax to detect the hang). Either is a production outage. The fix is the probe configuration; the configuration is small; getting it right requires thought.

The Python API for this challenge has two annoying properties on purpose: a slow startup and an occasional hang. Real-world apps have both; JVM apps have brutal startups; Python apps with large model loads or long DB-pool initializations have the same shape. The probe pattern you build here transfers to all of them.

---

## The application

Save the following as `app.py` in `~/c15/week-07/challenge-02/`. Read it before you run it.

```python
"""A small Python API with deliberate startup slowness and an occasional hang.

Endpoints:
    GET  /healthz   - returns 200 OK as soon as the process is alive
    GET  /readyz    - returns 200 OK after the warmup completes; 503 otherwise
    GET  /hang      - intentionally blocks the worker for 60 seconds (simulates a hang)
    GET  /          - returns the greeting
"""

from __future__ import annotations

import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


WARMUP_SECONDS: int = int(os.environ.get("WARMUP_SECONDS", "20"))
PORT: int = int(os.environ.get("PORT", "8080"))

_ready: bool = False


def _warmup() -> None:
    """Pretend to load a model or warm a DB pool."""
    global _ready
    time.sleep(WARMUP_SECONDS)
    _ready = True


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        """Keep the log line short."""
        print(f"{self.address_string()} {format % args}", flush=True)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._respond(200, b"alive")
        elif self.path == "/readyz":
            if _ready:
                self._respond(200, b"ready")
            else:
                self._respond(503, b"warming up")
        elif self.path == "/hang":
            time.sleep(60)
            self._respond(200, b"finally")
        elif self.path == "/":
            self._respond(200, b"Hello from C15 Week 7 Challenge 02\n")
        else:
            self._respond(404, b"not found")

    def _respond(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    threading.Thread(target=_warmup, daemon=True).start()
    server = HTTPServer(("0.0.0.0", PORT), _Handler)
    print(f"listening on :{PORT}; warmup {WARMUP_SECONDS}s", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
```

Verify it compiles cleanly:

```bash
python3 -m py_compile app.py
# (no output means success)
```

Run it locally to see the shape:

```bash
WARMUP_SECONDS=20 python3 app.py &
sleep 1
curl -i http://localhost:8080/healthz
# HTTP/1.0 200 OK
# alive

curl -i http://localhost:8080/readyz
# HTTP/1.0 503 Service Unavailable
# warming up

# Wait 20 seconds, then:
sleep 20
curl -i http://localhost:8080/readyz
# HTTP/1.0 200 OK
# ready

kill %1
```

The app behaves as documented: `/healthz` returns 200 immediately, `/readyz` returns 503 until the warmup completes (20 seconds), and `/hang` blocks the handler for 60 seconds (simulating a wedge).

---

## Containerize it

A minimal `Dockerfile`:

```dockerfile
FROM python:3.12-alpine
WORKDIR /app
COPY app.py /app/app.py
USER 1000
EXPOSE 8080
ENTRYPOINT ["python3", "/app/app.py"]
```

Build and load into your `kind` cluster:

```bash
docker build -t c15-w07-challenge-02:dev .
kind load docker-image c15-w07-challenge-02:dev --name c15-w07-lab
```

(The `kind load` step copies the image into the cluster's node so pods can use it without a registry. Without it, the cluster would try to pull from a registry and fail.)

---

## Your task

Write a Deployment manifest (`deploy.yaml`) for this app. The pod must:

1. Run the `c15-w07-challenge-02:dev` image.
2. Set `WARMUP_SECONDS` to 20 via an env var.
3. Configure a **startup probe**, a **readiness probe**, and a **liveness probe**, each calling the right endpoint with appropriate intervals and thresholds.

The constraints:

- The pod must not be marked `Ready` until `/readyz` returns 200. (The Service should not route traffic to a warming pod.)
- The pod must not be **restarted** during the 20-second warmup. (The liveness probe should not fail while the app is warming up.)
- The pod must be **restarted** within 60 seconds of becoming hung. (If `/hang` is called and the worker blocks, the cluster should restart the container.)
- Use a startup probe to gate the readiness and liveness probes during startup; this is the post-1.18 idiomatic shape.

Save your manifest. Apply it. Verify each acceptance criterion below.

---

## Acceptance criteria

For each criterion, write the command(s) you used and the output you observed.

- [ ] **A1.** Pod becomes `Running` (containers started) within 5 seconds of `kubectl apply`.
- [ ] **A2.** Pod becomes `Ready` (READY=1/1) within 22 seconds of `kubectl apply` (initial delay + first successful probe).
- [ ] **A3.** Pod is **not** restarted during the warmup. (`RESTARTS=0` at the moment it becomes `Ready`.)
- [ ] **A4.** With the pod `Ready`, the Service has one endpoint and a `curl http://service-name/` returns the greeting.
- [ ] **A5.** Trigger a hang: `kubectl exec pod-name -- wget -q -O- http://localhost:8080/hang &`. Within 60 seconds, the pod is restarted (`RESTARTS=1`).
- [ ] **A6.** After the restart, the pod goes through warmup again and becomes `Ready` (within ~25 seconds of the restart event).

Acceptance also requires:

- [ ] A `notes.md` in your working directory explaining the **rationale for each probe's settings**: why the `initialDelaySeconds`, `periodSeconds`, `failureThreshold`, and `timeoutSeconds` values you chose. Bad answer: "I copied them from a tutorial." Good answer: "The startup probe must allow 20s of warmup plus a margin; with periodSeconds=2 and failureThreshold=15, we allow up to 30s before the startup probe is considered failed, which gives 10s of headroom for slow CI nodes."
- [ ] A description of what would have happened if you had **omitted the startup probe** and used only readiness + liveness. (Two specific failure scenarios.)

---

## Hints

The Kubernetes probe schema is documented at `kubectl explain pod.spec.containers.livenessProbe` (same shape for `readinessProbe` and `startupProbe`). The fields you set are the same on all three:

```yaml
startupProbe:
  httpGet:
    path: /healthz
    port: http
  initialDelaySeconds: 2
  periodSeconds: 2
  timeoutSeconds: 1
  failureThreshold: 15
```

The semantics differ:

- **`startupProbe`** runs first; while it is failing, the other two probes are *suppressed*. Once it succeeds once, the startup probe is done and the readiness + liveness probes take over.
- **`readinessProbe`** controls the pod's `Ready` condition, which controls Service endpoint inclusion.
- **`livenessProbe`** controls container restart.

The math for the startup probe: if your warmup takes up to N seconds, set `periodSeconds × failureThreshold ≥ N + margin`. With `periodSeconds=2, failureThreshold=15`, you allow 30 seconds. With `periodSeconds=5, failureThreshold=20`, you allow 100 seconds. Pick numbers that match your worst-case startup.

For the hang test, you want the liveness probe to declare the pod dead within 60 seconds. With `periodSeconds=10, failureThreshold=3`, the probe declares failure after 30 seconds (initial delay) + 30 seconds (3 × 10) = 60 seconds. Adjust to taste.

Read `kubectl explain pod.spec.containers.startupProbe` before you start. Read it again after your first failed attempt.

---

## Bonus — write the same probe set without a startup probe

Once your first answer is working, try this variant: **remove the startup probe and configure only readiness + liveness** that satisfy the same acceptance criteria. This is the pre-1.18 shape and the shape you will see in many old YAMLs.

The challenge: the liveness probe must not fail during the 20-second warmup, AND must fail within 60 seconds of a hang. The two constraints push the probe parameters in opposite directions.

The trick is the `initialDelaySeconds`: set it to ~25 seconds on the liveness probe so the probe does not even start until warmup is likely done. The cost is that you sacrifice the cluster's ability to detect a container that *fails to start at all* during the first 25 seconds — the liveness probe is silent. The startup probe was introduced (KEP-950) specifically to solve this trade-off.

Add a section to `notes.md` comparing the two approaches: when is the no-startup-probe shape acceptable, when is it not?

---

## What "good" looks like

A correct, well-tuned configuration is small — about 20 lines of probe YAML. It does not over-tune; it does not pad arbitrary safety margins. The values map to the application's actual behavior: a 20-second warmup, a 60-second hang detection, a 1-second probe timeout because the HTTP handler is non-blocking under normal load.

Engineers who write probes badly add `initialDelaySeconds: 300` "to be safe" and `failureThreshold: 100` "in case the network is slow." The result is a cluster that takes 5 minutes to notice a dead pod. The right shape is *as conservative as the app's worst case, no more*. Worst case for this app is 20 seconds for warmup; allocate 30. Worst case for the hang is 60 seconds; allocate 60. Anything more is fat.

---

## Cleanup

```bash
kubectl delete -f deploy.yaml
```

---

## The five sentences

The five sentences that summarize this challenge, in case you are reviewing for the quiz:

1. The startup probe gates the readiness and liveness probes during slow startup; once it succeeds, it is done.
2. The readiness probe controls Service endpoint inclusion; failing it removes the pod from the load-balancing pool without restarting it.
3. The liveness probe controls container restart; failing it kills the container and starts a new one.
4. The three probe parameters (`initialDelaySeconds`, `periodSeconds`, `failureThreshold`) together determine the time-to-detection of a failure; pick them based on the app's actual worst case, not arbitrary safety margins.
5. The pre-1.18 way to handle slow startup was a large `initialDelaySeconds` on the liveness probe; the post-1.18 way is a startup probe. The latter is strictly better when both are available.

---

*If you find errors in this material, please open an issue or send a PR.*
