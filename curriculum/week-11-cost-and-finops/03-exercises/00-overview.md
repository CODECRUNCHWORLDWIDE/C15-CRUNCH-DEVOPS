# Week 11 — Exercises

Four exercises, in order. Each builds on the previous; do them sequentially.

| # | Title                                             | Estimated time | File                                              |
| - | ------------------------------------------------- | -------------- | ------------------------------------------------- |
| 1 | Install OpenCost on `kind` and read /allocation   | 60 minutes     | `exercise-01-opencost-install-and-read.md`        |
| 2 | Cost-by-label, Kyverno enforcement, right-sizing  | 75 minutes     | `exercise-02-allocation-by-label-and-rightsizing.md` |
| 3 | Anomaly detection in Python                       | 60 minutes     | `exercise-03-anomaly-detection.md`                |
| 4 | The pricing-calculator workflow                   | 30 minutes     | `exercise-04-pricing-calculators.md`              |

Solutions and expected outputs are in `SOLUTIONS.md`.

All exercises assume Kubernetes 1.31+, kind 0.24+, helm 3.14+, python3 3.11+. No cloud account required this week.

The Python scripts (`opencost_client.py`, `rightsize_report.py`, `anomaly_detect.py`, `unit_economics.py`) are shared utilities used across exercises. They depend only on the Python standard library; no `pip install` required.
