# Challenge 2 — A second-generation cost anomaly detector

**Difficulty:** Hard.
**Estimated time:** 4 to 5 hours.

The setup: the anomaly detector from Exercise 3 is a teaching version. It uses two simple rules — percentage-change against day-of-week-prior and z-score against a 14-day rolling window. The rules fire on real anomalies; they also produce false positives. Engineers on call eventually start ignoring the alerts.

The challenge: build a second-generation detector that produces a lower false-positive rate by being smarter about (a) the baseline, (b) the suppression, (c) the multi-metric view. Then evaluate it on a synthetic dataset and report on the precision/recall trade-off.

This challenge does not require additional cluster setup. It is a Python exercise plus a small evaluation harness. You can run it entirely on your laptop without needing the kind cluster running.

---

## Requirements

Your detector must:

1. **Baseline by hour-of-day.** A workload's cost is rarely uniform across the day. Compute the baseline for each hour separately — Monday 14:00 compared against the median Monday 14:00 of the prior 4 weeks. This is the *seasonal* baseline.
2. **Two-dimensional anomaly.** Flag *both* total cost and network cost separately. A network-cost spike with no total-cost spike is the log-pipe-explosion signal.
3. **Suppression for known events.** Accept a file `known_events.json` that lists scheduled deploys, traffic spikes, and other intentional events. Anomalies within 4 hours of a known event are suppressed.
4. **Cooldown.** Once an anomaly fires for a workload, the same workload's anomalies are suppressed for 12 hours.
5. **Severity ranking.** Each anomaly carries a `severity` field — `low`, `medium`, `high`, `critical` — computed from the magnitude of the deviation and the workload's absolute cost. A 500% spike on a $5/month workload is `low`; a 100% spike on a $5,000/month workload is `high`.
6. **Evaluation harness.** Generate a synthetic 60-day cost series for at least 10 workloads. Inject ~20 known anomalies (sharp spikes, slow drifts, network-only spikes) at known timestamps. Run your detector. Report precision and recall against the ground truth.
7. **Type hints throughout.** Every function signature must have type hints. The grader runs `mypy --strict` on the submission.

---

## Suggested data model

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Severity = Literal["low", "medium", "high", "critical"]
Metric   = Literal["total_cost", "network_cost", "cpu_cost", "ram_cost"]

@dataclass(frozen=True)
class CostSample:
    timestamp:   datetime
    workload:    str
    total_cost:  float
    cpu_cost:    float
    ram_cost:    float
    network_cost: float

@dataclass(frozen=True)
class KnownEvent:
    timestamp:   datetime
    workload:    str
    description: str

@dataclass(frozen=True)
class Anomaly:
    timestamp:   datetime
    workload:    str
    metric:      Metric
    observed:    float
    baseline:    float
    deviation:   float
    severity:    Severity
    message:     str

class Detector:
    def __init__(self, known_events: list[KnownEvent], cooldown_h: int = 12): ...
    def ingest(self, sample: CostSample) -> list[Anomaly]: ...
    def history(self, workload: str, metric: Metric) -> list[float]: ...
```

The detector is online — it ingests samples one at a time and emits any anomalies the new sample triggers. The internal state is a per-workload, per-metric history plus a per-workload cooldown timer.

---

## Suggested baseline algorithm

For each (workload, metric, hour-of-day, day-of-week) tuple, maintain a list of the last 4 weeks' samples for that slot. The baseline is the median of those samples. The observed sample is anomalous if it is more than:

- `1.5x median` AND
- `3 * MAD` (median absolute deviation) above the median.

The combination of "ratio above baseline" and "absolute deviation above noise" reduces false positives in two ways. The ratio test catches spikes. The MAD test ensures the spike is large relative to the natural noise of that slot (a slot with high variance gets a higher threshold).

This is the *Hampel filter*, a well-known robust statistic for time-series anomaly detection. Wikipedia: <https://en.wikipedia.org/wiki/Median_absolute_deviation>.

---

## Suggested severity model

```python
def compute_severity(
    deviation_ratio: float,
    workload_monthly_cost: float,
) -> Severity:
    score: float = deviation_ratio * (workload_monthly_cost / 100.0)
    if score < 1.0:
        return "low"
    if score < 5.0:
        return "medium"
    if score < 25.0:
        return "high"
    return "critical"
```

The product of "how anomalous" and "how expensive" produces a single score. The thresholds are judgement and should be tunable; document the ones you pick.

---

## Synthetic dataset

The evaluation harness generates 60 days of hourly samples for 10 to 20 workloads. The baseline pattern: each workload has a "shape" — diurnal (peak 9am-5pm), nocturnal (peak overnight), or flat. Add Gaussian noise (~5 percent of the baseline).

Inject anomalies:

- **5 sharp spikes** — one hour, 3x to 10x baseline. Should be detected.
- **5 slow drifts** — over 2 to 3 days, ramping up to 1.5x to 2x baseline. Should be detected.
- **5 network-only spikes** — total cost normal, network cost 5x to 20x baseline. Should be detected (but only by the multi-metric rule).
- **5 false-positive-bait events** — known deploys logged in `known_events.json` that coincide with cost spikes. Should *not* be detected (the suppression rule fires).

Compute precision (true positives / detected positives) and recall (true positives / actual positives). Report both.

A passing submission scores precision >= 0.7 and recall >= 0.7. A strong submission scores both >= 0.85.

---

## Stretch goals

- **EWMA baseline.** Instead of median over the 4-week slot, use an exponentially-weighted moving average. Compare precision/recall against the median-baseline version.
- **Multi-metric correlation.** A spike in network cost that *also* shows a spike in total cost is more likely to be a real event than a network-only spike. Build a rule that requires correlation.
- **Per-workload tuning.** Some workloads are inherently bursty and should have a higher threshold. Persist per-workload threshold overrides.
- **Slack output.** Format anomalies as Slack Block Kit JSON. Print the output that would be sent to a `#cost-alerts` channel.

---

## Write-up requirements

1. Describe the algorithm. Pseudocode is acceptable.
2. Show the precision/recall table from the evaluation. Compare against a "naive" baseline detector (the Exercise 3 rules) run on the same dataset.
3. Discuss two scenarios in which your detector would still produce a false positive, and what additional signal would suppress them.
4. Discuss two scenarios in which your detector would still produce a false negative, and what additional signal would surface them.

---

## Reading

- Hampel filter / MAD: <https://en.wikipedia.org/wiki/Median_absolute_deviation>
- EWMA: <https://en.wikipedia.org/wiki/Moving_average#Exponentially_weighted_moving_average>
- Anomaly detection algorithm survey: <https://en.wikipedia.org/wiki/Anomaly_detection>
- Twitter's open-source detector (Seasonal Hybrid ESD): <https://github.com/twitter/AnomalyDetection>
- OpenCost cost-anomaly RFCs (track for context): <https://github.com/opencost/opencost/issues?q=anomaly>
