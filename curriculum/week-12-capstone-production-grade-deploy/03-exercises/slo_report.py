"""
slo_report.py — compute the capstone's SLO compliance for a window.

The capstone defines two SLOs on the crunch-quotes application:

  - Availability: at least 99.0% of requests return a non-5xx status.
  - Latency:      at least 95% of requests complete in under 100ms.

Both are computed from Prometheus over a configurable rolling window
(default 1 hour). The script queries Prometheus, computes the
compliance ratio, and renders a one-page report.

The script is intended to be the first half of the W9 + W12
observability loop. The second half — alerting on SLO burn rate —
lives in the PrometheusRule manifests; this script is for periodic
reporting and for sanity-checking the alerts.

References:
    - SRE workbook on SLOs and error budgets:
      https://sre.google/workbook/implementing-slos/
    - Prometheus rate() function:
      https://prometheus.io/docs/prometheus/latest/querying/functions/#rate
    - histogram_quantile():
      https://prometheus.io/docs/prometheus/latest/querying/functions/#histogram_quantile

Usage:
    python3 slo_report.py [--prometheus-url http://localhost:9090] \
                          [--window 1h] \
                          [--service crunch-quotes]

Type-hinted throughout. Standard-library only.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_PROMETHEUS_URL: str = "http://localhost:9090"
DEFAULT_WINDOW: str = "1h"
DEFAULT_SERVICE: str = "crunch-quotes"

# The two SLO targets. Adjust per service; these are reasonable
# defaults for a low-traffic capstone service. Production targets
# are typically tighter (99.9% availability is the canonical SRE
# starting point).
AVAILABILITY_TARGET: float = 0.99
LATENCY_TARGET_RATIO: float = 0.95     # 95% under threshold
LATENCY_THRESHOLD_SECONDS: float = 0.10  # 100ms


@dataclass(frozen=True)
class SLOEvaluation:
    """Result of one SLO evaluation over the window."""

    name: str
    target: float
    actual: float
    met: bool
    detail: str


def _query(prometheus_url: str, promql: str) -> float | None:
    """Run an instant query against Prometheus. Return the first
    scalar value as a float, or None if the query has no result.
    """
    url: str = (
        f"{prometheus_url.rstrip('/')}/api/v1/query"
        f"?query={urllib.parse.quote(promql)}"
    )
    try:
        with urllib.request.urlopen(url, timeout=15.0) as resp:
            body: bytes = resp.read()
    except (urllib.error.URLError, TimeoutError):
        return None
    try:
        payload: dict[str, Any] = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if payload.get("status") != "success":
        return None
    data: dict[str, Any] = payload.get("data") or {}
    result_type: str = str(data.get("resultType") or "")
    result: list[Any] = data.get("result") or []
    if result_type == "scalar":
        try:
            return float(result[1])
        except (ValueError, IndexError, TypeError):
            return None
    if result_type == "vector":
        if not result:
            return None
        try:
            return float(result[0]["value"][1])
        except (ValueError, KeyError, IndexError, TypeError):
            return None
    return None


def evaluate_availability(
    prometheus_url: str,
    service: str,
    window: str,
) -> SLOEvaluation:
    """Evaluate the availability SLO over the window.

    The query: 1 - (5xx rate / total rate). When the denominator is
    zero (no traffic), we treat the SLO as met (no requests = no
    failed requests).
    """
    promql: str = (
        f"sum(rate(http_requests_total{{app=\"{service}\",status=~\"5..\"}}[{window}]))"
        " / "
        f"sum(rate(http_requests_total{{app=\"{service}\"}}[{window}]))"
    )
    error_ratio: float | None = _query(prometheus_url, promql)
    if error_ratio is None:
        return SLOEvaluation(
            name="availability",
            target=AVAILABILITY_TARGET,
            actual=0.0,
            met=False,
            detail="Prometheus returned no data; cannot evaluate",
        )
    availability: float = 1.0 - error_ratio
    if availability < 0.0:
        availability = 0.0
    met: bool = availability >= AVAILABILITY_TARGET
    return SLOEvaluation(
        name="availability",
        target=AVAILABILITY_TARGET,
        actual=availability,
        met=met,
        detail=(
            f"window={window}; non-5xx fraction "
            f"{availability:.4f} vs target {AVAILABILITY_TARGET:.4f}"
        ),
    )


def evaluate_latency(
    prometheus_url: str,
    service: str,
    window: str,
) -> SLOEvaluation:
    """Evaluate the latency SLO over the window.

    The query: fraction of requests under the threshold. Computed
    from the histogram buckets directly (sum of bucket counts under
    threshold divided by total count).
    """
    promql: str = (
        f"sum(rate(http_request_duration_seconds_bucket{{"
        f"app=\"{service}\",le=\"{LATENCY_THRESHOLD_SECONDS}\""
        f"}}[{window}]))"
        " / "
        f"sum(rate(http_request_duration_seconds_count{{"
        f"app=\"{service}\""
        f"}}[{window}]))"
    )
    fraction_under: float | None = _query(prometheus_url, promql)
    if fraction_under is None:
        return SLOEvaluation(
            name="latency",
            target=LATENCY_TARGET_RATIO,
            actual=0.0,
            met=False,
            detail="Prometheus returned no data; cannot evaluate",
        )
    if fraction_under < 0.0:
        fraction_under = 0.0
    if fraction_under > 1.0:
        fraction_under = 1.0
    met: bool = fraction_under >= LATENCY_TARGET_RATIO
    return SLOEvaluation(
        name="latency",
        target=LATENCY_TARGET_RATIO,
        actual=fraction_under,
        met=met,
        detail=(
            f"window={window}; "
            f"{fraction_under * 100:.2f}% under "
            f"{LATENCY_THRESHOLD_SECONDS * 1000:.0f}ms "
            f"vs target {LATENCY_TARGET_RATIO * 100:.0f}%"
        ),
    )


def evaluate_error_budget(
    prometheus_url: str,
    service: str,
    window: str,
) -> tuple[float, float]:
    """Compute the error budget remaining for the rolling window.

    Returns (used_fraction, remaining_fraction). The budget is
    (1 - availability_target); used_fraction is the share of the
    budget already consumed.
    """
    promql: str = (
        f"sum(rate(http_requests_total{{app=\"{service}\",status=~\"5..\"}}[{window}]))"
        " / "
        f"sum(rate(http_requests_total{{app=\"{service}\"}}[{window}]))"
    )
    error_ratio: float | None = _query(prometheus_url, promql)
    budget: float = 1.0 - AVAILABILITY_TARGET
    if error_ratio is None or budget <= 0.0:
        return 0.0, 1.0
    used: float = error_ratio / budget
    if used < 0.0:
        used = 0.0
    if used > 1.0:
        used = 1.0
    return used, 1.0 - used


def render_report(
    availability: SLOEvaluation,
    latency: SLOEvaluation,
    budget_used: float,
    window: str,
) -> str:
    """Render the SLO evaluation as a markdown report."""
    lines: list[str] = [
        "# SLO report",
        "",
        f"- **Window:** {window}",
        "",
        "## Availability SLO",
        "",
        f"- **Target:** {availability.target * 100:.2f}%",
        f"- **Actual:** {availability.actual * 100:.4f}%",
        f"- **Met:**    {'YES' if availability.met else 'NO'}",
        f"- **Detail:** {availability.detail}",
        "",
        "## Latency SLO",
        "",
        f"- **Target:** {latency.target * 100:.0f}% of requests under "
        f"{LATENCY_THRESHOLD_SECONDS * 1000:.0f}ms",
        f"- **Actual:** {latency.actual * 100:.2f}%",
        f"- **Met:**    {'YES' if latency.met else 'NO'}",
        f"- **Detail:** {latency.detail}",
        "",
        "## Error budget",
        "",
        f"- **Used:**      {budget_used * 100:.2f}%",
        f"- **Remaining:** {(1 - budget_used) * 100:.2f}%",
        "",
    ]
    if not availability.met or not latency.met:
        lines.append("## Action")
        lines.append("")
        lines.append(
            "One or more SLOs are not met. Open the application "
            "Golden-Signals dashboard, look at the trace for the "
            "slowest recent request, and investigate."
        )
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Compute SLO compliance for the capstone over a window.",
    )
    parser.add_argument("--prometheus-url", default=DEFAULT_PROMETHEUS_URL)
    parser.add_argument("--window", default=DEFAULT_WINDOW)
    parser.add_argument("--service", default=DEFAULT_SERVICE)
    args: argparse.Namespace = parser.parse_args(argv)

    availability: SLOEvaluation = evaluate_availability(
        args.prometheus_url, args.service, args.window
    )
    latency: SLOEvaluation = evaluate_latency(
        args.prometheus_url, args.service, args.window
    )
    budget_used, _budget_remaining = evaluate_error_budget(
        args.prometheus_url, args.service, args.window
    )

    report: str = render_report(availability, latency, budget_used, args.window)
    print(report)

    return 0 if (availability.met and latency.met) else 1


if __name__ == "__main__":
    sys.exit(main())
