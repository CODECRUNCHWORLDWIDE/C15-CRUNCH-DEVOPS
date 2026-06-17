"""
opencost_client.py — A minimal Python client for the OpenCost /allocation API.

Used by the Week 11 exercises. Talks to an OpenCost service reachable at
http://localhost:9003 by default; the exercises set up a kubectl port-forward
to expose the in-cluster service on that port.

References:
  - API reference:   https://www.opencost.io/docs/api
  - Project home:    https://www.opencost.io/
  - Helm chart:      https://github.com/opencost/opencost-helm-chart

This file is a single module with no external dependencies beyond the
Python standard library. It is type-hinted throughout.

Run a quick smoke test:
    python3 opencost_client.py --window 24h --aggregate namespace
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


DEFAULT_OPENCOST_URL: str = "http://localhost:9003"


@dataclass(frozen=True)
class AllocationEntry:
    """A single allocation row from the OpenCost /allocation response."""

    name: str
    total_cost: float
    cpu_cost: float
    ram_cost: float
    pv_cost: float
    network_cost: float
    load_balancer_cost: float
    cpu_efficiency: float
    ram_efficiency: float
    properties: dict[str, Any] = field(default_factory=dict)

    def waste_dollars(self) -> float:
        """Return the dollars paid for capacity reserved but not used.

        Uses the lower of cpu and ram efficiency as a conservative estimate.
        """
        eff: float = min(self.cpu_efficiency, self.ram_efficiency)
        if eff > 1.0:
            eff = 1.0
        if eff < 0.0:
            eff = 0.0
        return self.total_cost * (1.0 - eff)


def _fetch_json(url: str, timeout_s: float = 30.0) -> dict[str, Any]:
    """Fetch a URL and parse the response body as JSON.

    Raises urllib.error.URLError on transport failure; ValueError on a non-JSON
    body; RuntimeError on a non-200 status code.
    """
    req: urllib.request.Request = urllib.request.Request(
        url=url,
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status: int = resp.getcode()
            if status != 200:
                raise RuntimeError(
                    f"OpenCost returned HTTP {status} for {url}"
                )
            body: bytes = resp.read()
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Could not reach OpenCost at {url}: {e}"
        ) from e
    try:
        parsed: dict[str, Any] = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(
            f"OpenCost response was not JSON: {body[:200]!r}"
        ) from e
    return parsed


def allocation(
    base_url: str = DEFAULT_OPENCOST_URL,
    window: str = "24h",
    aggregate: str = "namespace",
    accumulate: bool = True,
    namespace_filter: str | None = None,
    label_filter: dict[str, str] | None = None,
) -> list[AllocationEntry]:
    """Query the /allocation endpoint and return parsed AllocationEntry rows.

    Arguments:
      base_url:        OpenCost service base URL.
      window:          OpenCost window string. Examples: "24h", "7d", "today".
      aggregate:       Aggregation key. Examples: "namespace", "label:team",
                       "namespace,label:team".
      accumulate:      If True, collapse all sub-windows into a single window.
      namespace_filter: If set, restrict to a single namespace.
      label_filter:    If set, restrict to pods matching these labels.

    Returns: a list of AllocationEntry rows.
    """
    params: dict[str, str] = {
        "window": window,
        "aggregate": aggregate,
        "accumulate": "true" if accumulate else "false",
    }
    filter_parts: list[str] = []
    if namespace_filter:
        filter_parts.append(f'namespace:"{namespace_filter}"')
    if label_filter:
        for key, value in label_filter.items():
            filter_parts.append(f'label[{key}]:"{value}"')
    if filter_parts:
        params["filter"] = "+".join(filter_parts)
    query: str = urllib.parse.urlencode(params, safe='":[]')
    url: str = f"{base_url.rstrip('/')}/allocation?{query}"
    body: dict[str, Any] = _fetch_json(url)
    if body.get("code", 0) != 200:
        raise RuntimeError(
            f"OpenCost API returned code={body.get('code')}: {body}"
        )
    data_field: list[Any] = body.get("data", [])
    rows: list[AllocationEntry] = []
    for window_block in data_field:
        if not isinstance(window_block, dict):
            continue
        for name, entry in window_block.items():
            if not isinstance(entry, dict):
                continue
            rows.append(_entry_from_dict(name, entry))
    return rows


def _entry_from_dict(name: str, entry: dict[str, Any]) -> AllocationEntry:
    """Map an /allocation JSON object onto an AllocationEntry."""

    def f(key: str) -> float:
        v: Any = entry.get(key, 0.0)
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    return AllocationEntry(
        name=name,
        total_cost=f("totalCost"),
        cpu_cost=f("cpuCost"),
        ram_cost=f("ramCost"),
        pv_cost=f("pvCost"),
        network_cost=f("networkCost"),
        load_balancer_cost=f("loadBalancerCost"),
        cpu_efficiency=f("cpuEfficiency"),
        ram_efficiency=f("ramEfficiency"),
        properties=dict(entry.get("properties") or {}),
    )


def print_rows(rows: list[AllocationEntry]) -> None:
    """Print rows as a fixed-width table."""
    if not rows:
        print("(no rows returned)")
        return
    rows_sorted: list[AllocationEntry] = sorted(
        rows, key=lambda r: r.total_cost, reverse=True
    )
    print(
        f"{'name':<30} "
        f"{'total$':>10} "
        f"{'cpu$':>8} "
        f"{'ram$':>8} "
        f"{'cpuEff':>7} "
        f"{'ramEff':>7} "
        f"{'waste$':>8}"
    )
    print("-" * 88)
    for r in rows_sorted:
        if r.name in {"__idle__", "__unallocated__"} and r.total_cost <= 0:
            continue
        print(
            f"{r.name[:30]:<30} "
            f"{r.total_cost:>10.4f} "
            f"{r.cpu_cost:>8.4f} "
            f"{r.ram_cost:>8.4f} "
            f"{r.cpu_efficiency:>7.2f} "
            f"{r.ram_efficiency:>7.2f} "
            f"{r.waste_dollars():>8.4f}"
        )


def main(argv: list[str]) -> int:
    """Command-line entry point. Returns process exit code."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Query the OpenCost /allocation endpoint."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_OPENCOST_URL,
        help="OpenCost base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--window",
        default="24h",
        help="Window (default: %(default)s)",
    )
    parser.add_argument(
        "--aggregate",
        default="namespace",
        help="Aggregation key (default: %(default)s)",
    )
    parser.add_argument(
        "--namespace",
        default=None,
        help="Filter to a single namespace.",
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="Filter by label key=value. Repeatable.",
    )
    args: argparse.Namespace = parser.parse_args(argv)

    label_filter: dict[str, str] = {}
    for kv in args.label:
        if "=" not in kv:
            print(f"--label {kv!r} must be key=value", file=sys.stderr)
            return 2
        key, value = kv.split("=", 1)
        label_filter[key] = value

    try:
        rows: list[AllocationEntry] = allocation(
            base_url=args.url,
            window=args.window,
            aggregate=args.aggregate,
            namespace_filter=args.namespace,
            label_filter=label_filter or None,
        )
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print_rows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
