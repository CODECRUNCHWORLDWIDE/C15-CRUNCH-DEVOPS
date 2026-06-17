"""
unit_economics.py — Compute unit-cost metrics from OpenCost cost data and a
business-metric series (typically a Prometheus counter).

The classic unit-economics formulas:

    cost_per_request        = total_cost_usd / requests
    cost_per_active_user    = total_cost_usd / daily_active_users
    cost_per_gb_processed   = total_cost_usd / bytes_processed_gb

This script is deliberately small. It exists so that the FinOps dashboard
team can wire the numerator (cost from OpenCost) and the denominator (a
Prometheus query) into a single number to graph over time.

References:
  - https://www.finops.org/framework/
  - https://prometheus.io/docs/prometheus/latest/querying/basics/
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


@dataclass(frozen=True)
class UnitMetric:
    """A single unit-economics computation."""

    name: str
    numerator_usd: float
    denominator: float
    denominator_units: str
    unit_cost_usd: float

    def humanize(self) -> str:
        return (
            f"{self.name}: ${self.numerator_usd:.4f} / "
            f"{self.denominator:.2f} {self.denominator_units} = "
            f"${self.unit_cost_usd:.6f} per {self.denominator_units}"
        )


def _http_json(url: str, timeout_s: float = 30.0) -> dict[str, Any]:
    """Fetch a URL and parse JSON. Raises RuntimeError on transport failure."""
    req: urllib.request.Request = urllib.request.Request(
        url, headers={"Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"could not reach {url}: {e}") from e


def fetch_total_cost(
    opencost_url: str,
    window: str,
    namespace_filter: str | None = None,
) -> float:
    """Return total cost across all workloads in `window` (USD)."""
    params: dict[str, str] = {
        "window": window,
        "aggregate": "cluster",
        "accumulate": "true",
    }
    if namespace_filter:
        params["filter"] = f'namespace:"{namespace_filter}"'
    query: str = urllib.parse.urlencode(params, safe='":[]')
    url: str = f"{opencost_url.rstrip('/')}/allocation?{query}"
    body: dict[str, Any] = _http_json(url)
    total: float = 0.0
    for block in body.get("data", []) or []:
        if isinstance(block, dict):
            for _name, entry in block.items():
                if isinstance(entry, dict):
                    total += float(entry.get("totalCost") or 0.0)
    return total


def fetch_prom_scalar(prom_url: str, query: str) -> float:
    """Return the scalar value of an instant PromQL query, or 0.0."""
    encoded: str = urllib.parse.urlencode({"query": query})
    url: str = f"{prom_url.rstrip('/')}/api/v1/query?{encoded}"
    body: dict[str, Any] = _http_json(url)
    if body.get("status") != "success":
        return 0.0
    result: list[Any] = body.get("data", {}).get("result", []) or []
    if not result:
        return 0.0
    first: Any = result[0]
    if not isinstance(first, dict):
        return 0.0
    value_pair: Any = first.get("value")
    if not isinstance(value_pair, list) or len(value_pair) < 2:
        return 0.0
    try:
        return float(value_pair[1])
    except (TypeError, ValueError):
        return 0.0


def compute_cost_per_request(
    opencost_url: str,
    prom_url: str,
    window: str,
    namespace_filter: str | None = None,
    requests_query: str = (
        'sum(increase(http_requests_total[24h]))'
    ),
) -> UnitMetric:
    """Compute cost per request over the requested window."""
    cost: float = fetch_total_cost(opencost_url, window, namespace_filter)
    requests_count: float = fetch_prom_scalar(prom_url, requests_query)
    unit: float = (cost / requests_count) if requests_count > 0 else 0.0
    return UnitMetric(
        name="cost_per_request",
        numerator_usd=cost,
        denominator=requests_count,
        denominator_units="request",
        unit_cost_usd=unit,
    )


def compute_cost_per_active_user(
    opencost_url: str,
    prom_url: str,
    window: str,
    namespace_filter: str | None = None,
    dau_query: str = (
        'sum(active_users_daily)'
    ),
) -> UnitMetric:
    """Compute cost per daily active user."""
    cost: float = fetch_total_cost(opencost_url, window, namespace_filter)
    dau: float = fetch_prom_scalar(prom_url, dau_query)
    unit: float = (cost / dau) if dau > 0 else 0.0
    return UnitMetric(
        name="cost_per_dau",
        numerator_usd=cost,
        denominator=dau,
        denominator_units="DAU",
        unit_cost_usd=unit,
    )


def compute_cost_per_gb(
    opencost_url: str,
    prom_url: str,
    window: str,
    namespace_filter: str | None = None,
    bytes_query: str = (
        'sum(increase(bytes_processed_total[24h]))'
    ),
) -> UnitMetric:
    """Compute cost per GB processed."""
    cost: float = fetch_total_cost(opencost_url, window, namespace_filter)
    bytes_processed: float = fetch_prom_scalar(prom_url, bytes_query)
    gb: float = bytes_processed / (1024.0**3) if bytes_processed > 0 else 0.0
    unit: float = (cost / gb) if gb > 0 else 0.0
    return UnitMetric(
        name="cost_per_gb",
        numerator_usd=cost,
        denominator=gb,
        denominator_units="GB",
        unit_cost_usd=unit,
    )


def main(argv: list[str]) -> int:
    """Command-line entry point. Returns process exit code."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Compute unit-economics metrics."
    )
    parser.add_argument("--opencost-url", default="http://localhost:9003")
    parser.add_argument("--prom-url", default="http://localhost:9090")
    parser.add_argument("--window", default="24h")
    parser.add_argument("--namespace", default=None)
    parser.add_argument(
        "--requests-query",
        default="sum(increase(http_requests_total[24h]))",
    )
    parser.add_argument(
        "--dau-query",
        default="sum(active_users_daily)",
    )
    parser.add_argument(
        "--bytes-query",
        default="sum(increase(bytes_processed_total[24h]))",
    )
    args: argparse.Namespace = parser.parse_args(argv)

    try:
        m1: UnitMetric = compute_cost_per_request(
            args.opencost_url, args.prom_url, args.window,
            args.namespace, args.requests_query,
        )
        m2: UnitMetric = compute_cost_per_active_user(
            args.opencost_url, args.prom_url, args.window,
            args.namespace, args.dau_query,
        )
        m3: UnitMetric = compute_cost_per_gb(
            args.opencost_url, args.prom_url, args.window,
            args.namespace, args.bytes_query,
        )
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print("Unit economics")
    print("==============")
    for m in (m1, m2, m3):
        print(m.humanize())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
