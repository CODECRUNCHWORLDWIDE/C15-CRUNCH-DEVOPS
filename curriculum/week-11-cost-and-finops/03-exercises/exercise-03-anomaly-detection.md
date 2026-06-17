# Exercise 3 — Cost anomaly detection in Python

**Estimated time:** 60 minutes.
**Prerequisite reading:** Lecture 2, section 4.
**Files used:** `anomaly_detect.py`, `manifests-workloads.yaml`.

The goal of this exercise is to detect a cost anomaly the way a real on-call SRE would: write a small script, run it against OpenCost's daily allocations, and flag workloads whose cost has drifted in ways that warrant a human look.

We will run the script in two modes. First, against the live cluster, where we will observe no anomalies because the workloads have been steady-state for a day. Second, by deliberately introducing a "log-pipe explosion" — scaling the `report-generator` Deployment from 4 replicas to 40 — and watching the anomaly detector flag it.

---

## Part A — Run the self-test

The anomaly detection module ships with a small self-test suite. Run it:

```bash
python3 anomaly_detect.py --self-test
```

Expected output: `self-test: OK (6 cases)`.

The self-test verifies the two anomaly-detection algorithms in isolation, without depending on a live cluster. If this fails, do not proceed — the math is wrong before the integration is wrong.

---

## Part B — Run against the live cluster

Port-forward OpenCost if it is not already exposed:

```bash
kubectl port-forward -n opencost svc/opencost 9003:9003 &
sleep 2
```

Run the detector against the last 7 days:

```bash
python3 anomaly_detect.py --opencost-url http://localhost:9003 \
  --aggregate namespace \
  --days 7 \
  --pct-threshold 50.0 \
  --z-threshold 2.0
```

On a freshly-installed cluster, the history is too short for the z-score rule to fire (it needs at least 7 days of history to compute a standard deviation). The percent-change rule may fire on day 2 against day 1, which is uninformative.

Expected output: `no anomalies detected`, or a small number of false positives on the first day when the cost ramps from zero.

The first conclusion: **anomaly detection requires history**. A new cluster's baseline is zero, against which any cost is anomalous. The baseline becomes meaningful only after the cluster has been running for at least a week.

---

## Part C — Induce a deliberate anomaly

Now we manufacture a cost anomaly. The `report-generator` Deployment runs an idle workload at 4 replicas. We will scale it to 40 — the autoscaler-runaway scenario from Lecture 2.

```bash
kubectl scale deployment/report-generator \
  --namespace team-analytics \
  --replicas=40
```

Verify the scale-up:

```bash
kubectl get deployment report-generator -n team-analytics
kubectl get pods -n team-analytics
```

You should see pods Pending (the kind cluster does not have capacity for 40 replicas) and some Running. The cluster autoscaler is not installed on kind, so the Pending pods stay Pending; in a real cloud cluster, the cluster autoscaler would provision more nodes and the cost would rise immediately. For our purposes, the resource-request bookkeeping is what OpenCost charges against — the 40 replicas reserve compute even if only some are scheduled, and OpenCost's `__pending__` and per-pod allocation accounting reflects that.

Wait 10 minutes for OpenCost to ingest the change. While waiting:

```bash
python3 opencost_client.py --window 1h --aggregate namespace
```

The `team-analytics` namespace's cost should rise visibly.

---

## Part D — Observe the anomaly in the script

Run the detector again, this time using a shorter window (the change is recent):

```bash
python3 anomaly_detect.py --opencost-url http://localhost:9003 \
  --aggregate namespace \
  --days 7
```

The detector should flag `team-analytics` as anomalous via the percent-change rule. Sample output:

```
team-analytics: today $0.4250 vs baseline $0.0680 (+525.0%) > 50.0%
```

The z-score rule may not fire if there is insufficient history; that is correct behavior.

---

## Part E — Scale back and verify the detector reports clean

Scale `report-generator` back to its original 4 replicas:

```bash
kubectl scale deployment/report-generator \
  --namespace team-analytics \
  --replicas=4
```

Wait 10 minutes for OpenCost to recompute. Re-run the detector:

```bash
python3 anomaly_detect.py --opencost-url http://localhost:9003 \
  --aggregate namespace \
  --days 7
```

Note: the anomaly may **still** fire because the previous day's cost (with 40 replicas for some hours) is still in the rolling window. This is correct behavior for a real anomaly detector — the spike happened, it is part of the recent history, the detector reports it for a few more days until it ages out.

A more sophisticated implementation would compare cost against the same hour-of-day baseline rather than rolling-window mean; that is left as a stretch challenge in `challenges/challenge-02-anomaly-detector-v2.md`.

---

## Part F — Wire the detector into a CronJob (extension)

In a real cluster, the detector runs on a schedule. The CronJob below runs the script every hour and writes its output to stdout (where the cluster's log aggregator picks it up). This is optional; complete it if time permits.

Create `cronjob-anomaly-detect.yaml`:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: cost-anomaly-detect
  namespace: opencost
spec:
  schedule: "0 * * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: detect
              image: python:3.12-slim
              command: ["/bin/sh", "-c"]
              args:
                - |
                  cat > /tmp/anomaly_detect.py <<'PY'
                  # copy the contents of anomaly_detect.py here
                  PY
                  python3 /tmp/anomaly_detect.py \
                    --opencost-url http://opencost.opencost.svc:9003 \
                    --aggregate namespace \
                    --days 14
              resources:
                requests:
                  cpu: 50m
                  memory: 64Mi
                limits:
                  cpu: 200m
                  memory: 128Mi
```

In a real pipeline, the script would be packaged as a small container image rather than inlined via heredoc; the inlined form is shown here only to keep the exercise self-contained. The output of the detector lands in pod logs, which a log aggregator (Loki, Elasticsearch) indexes for human review.

A more realistic pipeline pipes the script output to a Slack webhook, an email service, or PagerDuty — depending on the team's incident-response tooling.

---

## Part G — Checkpoint

Capture the following and paste into `SOLUTIONS.md`:

1. The output of `python3 anomaly_detect.py --self-test`.
2. The output of `python3 anomaly_detect.py --days 7` immediately after Part B (cluster steady-state).
3. The output of `python3 anomaly_detect.py --days 7` after Part D (spike induced).
4. A one-paragraph note: when would the z-score rule fire instead of the percent-change rule? Under what real-world cost pattern is the z-score rule more useful?

---

## A note on practice

The detector here is a teaching version. A production-grade cost anomaly detector typically has the following additional properties:

- **Per-time-of-day baselines.** Cost varies by hour of the day in workloads with diurnal traffic. A "5x baseline" rule that compares against the same hour-of-day from one week earlier is more accurate than a flat 24-hour average.
- **Suppression for known events.** A team scheduled to deploy a new service today will produce a cost anomaly. The detector should silence anomalies whose source matches a known deploy event in the change-management system.
- **Cooldown windows.** Once an anomaly is reported, the detector should silence subsequent reports for the same workload for some period (typically 4 to 24 hours) so that the on-call engineer is not paged every hour for the same spike.
- **Multiple metrics.** Beyond total cost, surface anomalies in CPU cost, memory cost, network cost, and storage cost separately. A network-cost anomaly is the log-pipe-explosion signal that a total-cost detector might miss.

Both Kubecost (paid) and Datadog's cloud cost-management product implement variations of these. The OpenCost-native anomaly detector is not part of the open-source project at the time of this writing; one is on the roadmap (track at <https://github.com/opencost/opencost/issues>).

---

## Reading

- Anomaly detection — primer: <https://en.wikipedia.org/wiki/Anomaly_detection>
- Z-score primer: <https://en.wikipedia.org/wiki/Standard_score>
- OpenCost roadmap and feature requests: <https://github.com/opencost/opencost/issues>
- Twitter's open-source anomaly detector (R, S-H-ESD algorithm): <https://github.com/twitter/AnomalyDetection>

Continue to Exercise 4.
