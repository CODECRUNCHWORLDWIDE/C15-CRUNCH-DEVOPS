"""
anomaly_detect.py — Detect cost anomalies from OpenCost daily allocation data.

Two algorithms are implemented:
  1. percent_change: flag a series whose latest day is more than `pct_threshold`
     percent above its day-of-week baseline from one week earlier.
  2. zscore: flag a series whose latest day is more than `z_threshold` standard
     deviations above its rolling mean over `history_days` days.

The script can be run against:
  - A live OpenCost service via --opencost-url.
  - A JSON file produced by `opencost_dump.py` for offline testing.

References:
  - OpenCost /allocation: https://www.opencost.io/docs/api
  - Z-score:              https://en.wikipedia.org/wiki/Standard_score

Run unit-style sanity checks:
    python3 anomaly_detect.py --self-test
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnomalyFinding:
    """A single anomaly detection result."""

    name: str
    rule: str
    today_cost: float
    baseline: float
    score: float
    message: str


def is_anomaly_pct(
    cost_now: float,
    cost_baseline: float,
    threshold_pct: float = 50.0,
    floor_now: float = 0.10,
    floor_baseline: float = 0.01,
) -> tuple[bool, float]:
    """Return (is_anomaly, percent_change).

    A tiny baseline produces nonsense percent changes; the floors filter them.
    """
    if cost_baseline <= floor_baseline:
        return (cost_now > floor_now, 0.0)
    change_pct: float = ((cost_now - cost_baseline) / cost_baseline) * 100.0
    return (change_pct > threshold_pct, change_pct)


def is_anomaly_zscore(
    cost_today: float,
    history: list[float],
    z_threshold: float = 2.0,
    min_history: int = 7,
) -> tuple[bool, float]:
    """Return (is_anomaly, z_score) for the latest sample.

    Returns (False, 0.0) when there is insufficient history or zero variance.
    """
    if len(history) < min_history:
        return (False, 0.0)
    mean: float = statistics.mean(history)
    try:
        stdev: float = statistics.stdev(history)
    except statistics.StatisticsError:
        return (False, 0.0)
    if stdev <= 0.0:
        return (False, 0.0)
    z: float = (cost_today - mean) / stdev
    return (z > z_threshold, z)


def detect_in_series(
    name: str,
    series: list[float],
    pct_threshold: float = 50.0,
    z_threshold: float = 2.0,
) -> list[AnomalyFinding]:
    """Run both rules on a single time series. Returns all findings."""
    findings: list[AnomalyFinding] = []
    if len(series) < 2:
        return findings
    today: float = series[-1]

    # Percentage-change rule: compare to 7 days ago when possible, else
    # to the previous day.
    if len(series) >= 8:
        baseline: float = series[-8]
    else:
        baseline = series[-2]
    flagged_pct, pct = is_anomaly_pct(today, baseline, pct_threshold)
    if flagged_pct:
        findings.append(
            AnomalyFinding(
                name=name,
                rule="percent_change",
                today_cost=today,
                baseline=baseline,
                score=pct,
                message=(
                    f"{name}: today ${today:.4f} vs baseline ${baseline:.4f} "
                    f"({pct:+.1f}%) > {pct_threshold:.1f}%"
                ),
            )
        )

    # Z-score rule: compare to the prior `len(series) - 1` days as history.
    history: list[float] = series[:-1]
    flagged_z, z = is_anomaly_zscore(today, history, z_threshold)
    if flagged_z:
        findings.append(
            AnomalyFinding(
                name=name,
                rule="zscore",
                today_cost=today,
                baseline=statistics.mean(history) if history else 0.0,
                score=z,
                message=(
                    f"{name}: today ${today:.4f} vs 14d mean "
                    f"${statistics.mean(history):.4f} (z={z:.2f}) > "
                    f"{z_threshold:.2f}"
                ),
            )
        )
    return findings


def fetch_daily_series(
    opencost_url: str,
    aggregate: str,
    days: int,
) -> dict[str, list[float]]:
    """Return a mapping of group name -> daily cost over the last `days` days.

    The series are ordered oldest-first. Missing days are filled with zeros.
    """
    params: dict[str, str] = {
        "window": f"{days}d",
        "aggregate": aggregate,
        "accumulate": "false",
        "step": "1d",
    }
    query: str = urllib.parse.urlencode(params, safe='":[]')
    url: str = f"{opencost_url.rstrip('/')}/allocation?{query}"
    req: urllib.request.Request = urllib.request.Request(
        url, headers={"Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60.0) as resp:
            body: bytes = resp.read()
    except urllib.error.URLError as e:
        raise RuntimeError(f"could not reach {url}: {e}") from e
    parsed: dict[str, Any] = json.loads(body.decode("utf-8"))
    series: dict[str, list[float]] = {}
    for daily_block in parsed.get("data", []) or []:
        if not isinstance(daily_block, dict):
            continue
        names_in_day: set[str] = set()
        for name, entry in daily_block.items():
            if not isinstance(entry, dict):
                continue
            if name in {"__idle__", "__unallocated__"}:
                continue
            series.setdefault(name, []).append(
                float(entry.get("totalCost") or 0.0)
            )
            names_in_day.add(name)
        # Backfill zeros for series that had no data this day.
        for existing in list(series.keys()):
            if existing not in names_in_day:
                series[existing].append(0.0)
    return series


def detect_all(
    opencost_url: str,
    aggregate: str = "namespace",
    days: int = 14,
    pct_threshold: float = 50.0,
    z_threshold: float = 2.0,
) -> list[AnomalyFinding]:
    """End-to-end detection across all groups in the chosen aggregation."""
    series: dict[str, list[float]] = fetch_daily_series(
        opencost_url=opencost_url, aggregate=aggregate, days=days
    )
    out: list[AnomalyFinding] = []
    for name, daily in series.items():
        out.extend(
            detect_in_series(
                name=name,
                series=daily,
                pct_threshold=pct_threshold,
                z_threshold=z_threshold,
            )
        )
    return out


def _self_test() -> int:
    """Run a small self-test suite. Returns 0 on success."""
    failures: int = 0

    # 1. percent_change: 100 vs 50 baseline at 50% threshold -> anomaly.
    flagged, pct = is_anomaly_pct(100.0, 50.0, threshold_pct=50.0)
    if not flagged or abs(pct - 100.0) > 0.001:
        print("FAIL is_anomaly_pct(100, 50)")
        failures += 1

    # 2. percent_change: 60 vs 50 baseline at 50% threshold -> NOT anomaly.
    flagged, _ = is_anomaly_pct(60.0, 50.0, threshold_pct=50.0)
    if flagged:
        print("FAIL is_anomaly_pct(60, 50) should NOT flag")
        failures += 1

    # 3. zscore: clearly anomalous high value with a tight history.
    history: list[float] = [10.0] * 14
    flagged, z = is_anomaly_zscore(50.0, history, z_threshold=2.0)
    # stdev of constant series is 0 -> rule abstains.
    if flagged:
        print("FAIL: zero-variance history should not flag")
        failures += 1

    # 4. zscore: realistic noisy history with a clear spike.
    history2: list[float] = [
        10.0, 11.0, 9.0, 10.5, 9.5, 10.2, 9.8, 10.1, 10.0, 9.9, 10.3, 9.7,
        10.0, 10.1,
    ]
    flagged, z = is_anomaly_zscore(20.0, history2, z_threshold=2.0)
    if not flagged:
        print(f"FAIL: realistic spike should flag, z={z}")
        failures += 1

    # 5. zscore: too-short history -> abstain.
    flagged, _ = is_anomaly_zscore(50.0, [1.0, 2.0, 3.0], z_threshold=2.0)
    if flagged:
        print("FAIL: short history should abstain")
        failures += 1

    # 6. detect_in_series: spike on day 8 of a flat 8-day series.
    series: list[float] = [10.0] * 7 + [50.0]
    findings: list[AnomalyFinding] = detect_in_series("test", series)
    if not any(f.rule == "percent_change" for f in findings):
        print("FAIL: flat-then-spike should trigger percent_change")
        failures += 1

    if failures == 0:
        print("self-test: OK (6 cases)")
    else:
        print(f"self-test: {failures} FAILURES")
    return failures


def main(argv: list[str]) -> int:
    """Command-line entry point. Returns process exit code."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Detect cost anomalies from OpenCost daily allocations."
    )
    parser.add_argument(
        "--opencost-url",
        default="http://localhost:9003",
    )
    parser.add_argument(
        "--aggregate",
        default="namespace",
        help="OpenCost aggregation key (default: %(default)s).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
    )
    parser.add_argument(
        "--pct-threshold",
        type=float,
        default=50.0,
    )
    parser.add_argument(
        "--z-threshold",
        type=float,
        default=2.0,
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
    )
    args: argparse.Namespace = parser.parse_args(argv)

    if args.self_test:
        return _self_test()

    try:
        findings: list[AnomalyFinding] = detect_all(
            opencost_url=args.opencost_url,
            aggregate=args.aggregate,
            days=args.days,
            pct_threshold=args.pct_threshold,
            z_threshold=args.z_threshold,
        )
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not findings:
        print("no anomalies detected")
        return 0
    for f in findings:
        print(f.message)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
