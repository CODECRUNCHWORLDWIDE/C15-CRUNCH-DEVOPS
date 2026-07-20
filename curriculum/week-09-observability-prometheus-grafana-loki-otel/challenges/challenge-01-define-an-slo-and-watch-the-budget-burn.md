# Challenge 1 — Define an SLO, Write the Burn-Rate Alert, Watch the Budget Burn

**Time:** 90 minutes.
**Cost:** $0.00.
**Prerequisite:** Exercises 1, 2, and 3 complete. You have the `greeter` service running and emitting metrics.

---

## Goal

For the `greeter` service from Exercise 3, define an availability SLI, an SLO over a 28-day window, and a multi-window burn-rate alert pair. Force the SLI to degrade and watch the burn-rate alert fire correctly.

After this challenge you will have:

- A clear, written SLI definition for `greeter` availability.
- A clear SLO target (read the SRE book chapter 4 before you pick).
- A `PrometheusRule` containing two recording rules (the SLI over the long window and over the short window) and two alerting rules (the "fast burn" and "slow burn" pages).
- A test that degrades the service, observes the burn-rate alert firing, and reasons about whether the alert fired correctly given the rate of consumption.

---

## Step 1 — Pick an SLI

For an HTTP service, the canonical SLIs are availability and latency. Pick one (or do both as a stretch).

**Availability SLI** for `greeter`:

```
SLI_availability = count(requests with status in [200..499]) / count(all requests)
```

In PromQL:

```promql
sum(rate(http_server_requests_total{service="greeter",status_code!~"5.."}[5m]))
  /
sum(rate(http_server_requests_total{service="greeter"}[5m]))
```

A subtle question: the FastAPI auto-instrumentation emits the metric as `http_server_duration_count` (or `http_server_requests_total` depending on the version of the contrib package). Use whichever your greeter is emitting; check with `curl localhost:9090/api/v1/label/__name__/values | jq` if unsure.

Write your SLI definition down in a short paragraph: *what* it measures, *for whom* (which user behavior it proxies), *why* it is the right thing to measure.

---

## Step 2 — Pick an SLO

The SLO is a target on the SLI over a window. Choose:

- The **window** (typically 28 days; sometimes 30, sometimes 4 weeks).
- The **target** (typically 99%, 99.5%, 99.9%, or 99.95%).

For a learning service like greeter, 99.5% over 28 days is a defensible choice. The error budget is 0.5%; over 28 days × 24 hours × 60 minutes = 40,320 minutes, the budget is 201 minutes (3.35 hours). That feels generous and is a fine starting point.

Real services have to defend the choice to the product team. Read SRE-book chapter 4 ([sre.google/sre-book/service-level-objectives/](https://sre.google/sre-book/service-level-objectives/)) and write a one-paragraph justification for your number.

---

## Step 3 — Write the two-window burn-rate alert

The multi-window multi-burn-rate alert from the SRE Workbook chapter 5 is the canonical pattern. The idea:

- A **fast burn-rate** alert (short window, high burn threshold) catches a sudden spike in error rate.
- A **slow burn-rate** alert (long window, lower burn threshold) catches a gradual drift.

The burn-rate factor for a 1-hour window (catching 2% of the 28-day budget consumed) is:

```
factor = 0.02 * (28d / 1h) = 0.02 * 672 = 13.44
```

So the fast-burn alert fires when the error rate over the last 1 hour exceeds 13.44 × (1 - SLO) = 13.44 × 0.005 = 6.72%.

For a 6-hour window (catching 5% of budget):

```
factor = 0.05 * (28d / 6h) = 0.05 * 112 = 5.6
```

Fast-burn alert: 5.6 × 0.005 = 2.8%.

Two windows, two thresholds. Both must hold simultaneously to fire (to avoid one-sample flapping).

Save as `greeter-slo.yaml`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: greeter-slo
  namespace: monitoring
  labels:
    release: kps
spec:
  groups:
    - name: greeter-slo-recording
      interval: 30s
      rules:
        - record: greeter:availability_sli:ratio_rate5m
          expr: |
            sum(rate(http_server_duration_count{service="greeter",http_response_status_code!~"5.."}[5m]))
              /
            sum(rate(http_server_duration_count{service="greeter"}[5m]))
        - record: greeter:availability_sli:error_ratio_rate5m
          expr: 1 - greeter:availability_sli:ratio_rate5m
        - record: greeter:availability_sli:error_ratio_rate1h
          expr: |
            sum(rate(http_server_duration_count{service="greeter",http_response_status_code=~"5.."}[1h]))
              /
            sum(rate(http_server_duration_count{service="greeter"}[1h]))
        - record: greeter:availability_sli:error_ratio_rate6h
          expr: |
            sum(rate(http_server_duration_count{service="greeter",http_response_status_code=~"5.."}[6h]))
              /
            sum(rate(http_server_duration_count{service="greeter"}[6h]))
    - name: greeter-slo-alerting
      interval: 30s
      rules:
        - alert: GreeterSLOBurnRateFast
          expr: |
            greeter:availability_sli:error_ratio_rate5m > (13.44 * 0.005)
              and
            greeter:availability_sli:error_ratio_rate1h > (13.44 * 0.005)
          for: 2m
          labels:
            severity: critical
            service: greeter
            slo: availability
          annotations:
            summary: "greeter is burning the SLO error budget at >2%/hour rate"
            description: "5m error ratio = {{ $value | humanizePercentage }}. The 28-day budget will be exhausted in <2 days at this rate."
            runbook: "https://wiki.example.com/runbooks/greeter-slo-burn"
        - alert: GreeterSLOBurnRateSlow
          expr: |
            greeter:availability_sli:error_ratio_rate5m > (5.6 * 0.005)
              and
            greeter:availability_sli:error_ratio_rate6h > (5.6 * 0.005)
          for: 15m
          labels:
            severity: warning
            service: greeter
            slo: availability
          annotations:
            summary: "greeter is burning the SLO error budget at >0.5%/hour rate"
            description: "6h error ratio = {{ $value | humanizePercentage }}. The 28-day budget will be exhausted in ~5 days at this rate."
            runbook: "https://wiki.example.com/runbooks/greeter-slo-burn"
```

Adjust the metric name to match what your greeter actually emits. The OTel FastAPI instrumentation in 1.27 emits `http_server_duration_milliseconds_count` (or `http_server_duration_count` if you have the older naming); inspect `curl /metrics` to confirm.

Apply:

```bash
kubectl apply -f greeter-slo.yaml
```

Verify in Prometheus's `/rules` page that the four recording rules and two alerting rules are loaded.

---

## Step 4 — Degrade the service

Add a query parameter to `greeter.py` that returns a 500 when `?fail=1`. Patch the `/api/hello` route:

```python
@app.get("/api/hello")
def hello(name: str = "world", locale: str = "en", fail: int = 0) -> dict[str, Any]:
    if fail == 1:
        raise HTTPException(status_code=500, detail="injected failure")
    return compute_greeting(name=name, locale=locale)
```

Rebuild, reload into kind, restart the deployment:

```bash
docker build -t greeter:0.2 .
kind load docker-image greeter:0.2 --name w09
kubectl set image deploy/greeter greeter=greeter:0.2
kubectl rollout status deploy/greeter
```

Now run a load generator that sends 10% failures:

```bash
kubectl run loadgen --image=curlimages/curl:8.10.1 --rm -i --tty --restart=Never -- sh
```

Inside the pod:

```sh
N=0
while true; do
  if [ $((N % 10)) -eq 0 ]; then
    curl -s "http://greeter.default.svc.cluster.local:8080/api/hello?fail=1" > /dev/null
  else
    curl -s "http://greeter.default.svc.cluster.local:8080/api/hello?name=X" > /dev/null
  fi
  N=$((N + 1))
  sleep 0.1
done
```

10% failure rate means an error ratio of 0.1 (10%). The fast-burn alert threshold is 13.44 × 0.005 = 6.72%. 10% > 6.72%, so the fast-burn alert should fire after the 5m short-window catches up plus the 2m `for:` clause.

Watch Prometheus's `/alerts` page. Within ~7 minutes of starting the load, `GreeterSLOBurnRateFast` should fire. The webhook from Exercise 2 should receive it.

---

## Step 5 — Reason about the result

Answer in your notes:

1. **Did the alert fire?** If not, what was wrong? (Common: the metric name does not match what the greeter emits. Inspect `curl /metrics | grep http_server`.)
2. **How long after starting the bad load did the alert fire?** The expected: ~7 minutes (5m window + 2m `for:`).
3. **What happens to the 1-hour error ratio over the next 30 minutes?** It rises slowly because the 1h window is wide. Plot `greeter:availability_sli:error_ratio_rate1h` in Grafana and watch it climb.
4. **If you stop the bad load, when does the alert clear?** The 5m window needs to drop below the threshold first, then the `for:` clears. Total: ~5-7 minutes.
5. **Is the alert threshold right?** A 10% failure rate is well above the budget burn rate. A 1% failure rate would not have fired the *fast* alert (1% < 6.72%) but would have fired the *slow* alert (1% > 2.8% × ... no wait, 1% < 2.8%). Reason through which thresholds catch which scenarios.

---

## Step 6 — Document the SLO

In your write-up, include:

1. The SLI definition (one paragraph).
2. The SLO target and window (one sentence).
3. The error budget in absolute units (X requests per 28 days, Y minutes of full outage).
4. The two burn-rate alerts and what they mean.
5. The runbook link (write a stub page if you do not have a wiki; the URL must exist).

---

## Stretch

- **Add a latency SLO.** "99% of greeter requests are served in under 100 ms over 28 days." Compute the SLI from the histogram (`histogram_quantile(0.99, ...)`) and the error ratio from "requests > 100ms / total requests".
- **Add a third burn-rate window.** A 3-day window catches the slowest possible budget exhaustion. The SRE Workbook describes the four-window pattern.
- **Plot the burn rate in Grafana.** A panel that shows `greeter:availability_sli:error_ratio_rate1h / 0.005` is "burn rate as a multiple of the SLO's allowed error rate". When it exceeds 1, you are burning the budget faster than it accumulates.

---

## Notes

The SRE Workbook chapter 5 — Implementing SLOs — at <https://sre.google/workbook/implementing-slos/> is the gold standard for this material. Read it. The multi-window multi-burn-rate alert pattern is from this chapter.

The threshold math (13.44 for 1h, 5.6 for 6h, etc.) comes from Google's published table. The intuition: a 1h window with a burn rate of 14x means 14 hours of budget consumed in 1 hour of wall time. Over 28 days that is 14 × (1/672) = 2.1% of the budget consumed. The exact percentages depend on the window and the target.
