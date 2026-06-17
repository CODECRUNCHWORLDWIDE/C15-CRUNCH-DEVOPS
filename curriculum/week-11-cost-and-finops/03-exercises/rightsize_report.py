"""
rightsize_report.py — Produce a right-sizing recommendation report from
OpenCost allocation data plus Prometheus usage data.

For each workload aggregated by Deployment, the report shows:
  - current requests (CPU, RAM)
  - observed P95 usage (CPU, RAM)
  - recommended requests (P95 * margin)
  - estimated monthly savings

The script is read-only. It does not modify any Kubernetes object.

References:
  - OpenCost /allocation:  https://www.opencost.io/docs/api
  - Prometheus query API:  https://prometheus.io/docs/prometheus/latest/querying/api/

Usage:
    python3 rightsize_report.py --opencost-url http://localhost:9003 \\
                                --prom-url http://localhost:9090 \\
                                --margin 1.3 \\
                                --window 7d
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


@dataclass
class WorkloadStats:
    """Per-workload statistics for right-sizing analysis."""

    namespace: str
    deployment: str
    cpu_request_cores: float
    cpu_p95_cores: float
    ram_request_bytes: float
    ram_p95_bytes: float
    monthly_cost_usd: float
    cpu_efficiency: float
    ram_efficiency: float


def _http_json(url: str, timeout_s: float = 30.0) -> dict[str, Any]:
    """Fetch a URL and parse it as JSON. Raises RuntimeError on failure."""
    req: urllib.request.Request = urllib.request.Request(
        url, headers={"Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status: int = resp.getcode()
            if status != 200:
                raise RuntimeError(f"HTTP {status} for {url}")
            body: bytes = resp.read()
    except urllib.error.URLError as e:
        raise RuntimeError(f"could not reach {url}: {e}") from e
    return json.loads(body.decode("utf-8"))


def prom_query(prom_url: str, query: str) -> list[dict[str, Any]]:
    """Run an instant PromQL query and return the result vector."""
    url: str = (
        f"{prom_url.rstrip('/')}/api/v1/query?"
        f"{urllib.parse.urlencode({'query': query})}"
    )
    body: dict[str, Any] = _http_json(url)
    if body.get("status") != "success":
        raise RuntimeError(f"prom query failed: {body}")
    result: list[dict[str, Any]] = body.get("data", {}).get("result", [])
    return result


def gather_cpu_p95(
    prom_url: str,
    namespace: str,
    deployment: str,
    window: str = "7d",
) -> float:
    """Return P95 CPU usage in cores for a Deployment's pods over `window`."""
    query: str = (
        'quantile_over_time(0.95, '
        'sum(rate(container_cpu_usage_seconds_total{'
        f'namespace="{namespace}",'
        f'pod=~"{deployment}-.*",'
        'container!="",container!="POD"}[5m]))'
        f'[{window}:5m])'
    )
    result: list[dict[str, Any]] = prom_query(prom_url, query)
    if not result:
        return 0.0
    try:
        return float(result[0]["value"][1])
    except (KeyError, IndexError, TypeError, ValueError):
        return 0.0


def gather_ram_p95(
    prom_url: str,
    namespace: str,
    deployment: str,
    window: str = "7d",
) -> float:
    """Return P95 memory working-set in bytes for a Deployment over `window`."""
    query: str = (
        'quantile_over_time(0.95, '
        'sum(container_memory_working_set_bytes{'
        f'namespace="{namespace}",'
        f'pod=~"{deployment}-.*",'
        'container!="",container!="POD"})'
        f'[{window}:5m])'
    )
    result: list[dict[str, Any]] = prom_query(prom_url, query)
    if not result:
        return 0.0
    try:
        return float(result[0]["value"][1])
    except (KeyError, IndexError, TypeError, ValueError):
        return 0.0


def gather_requests(
    prom_url: str,
    namespace: str,
    deployment: str,
) -> tuple[float, float]:
    """Return (cpu_request_cores, ram_request_bytes) for a Deployment."""
    cpu_query: str = (
        'sum(kube_pod_container_resource_requests{'
        f'namespace="{namespace}",'
        f'pod=~"{deployment}-.*",'
        'resource="cpu"})'
    )
    ram_query: str = (
        'sum(kube_pod_container_resource_requests{'
        f'namespace="{namespace}",'
        f'pod=~"{deployment}-.*",'
        'resource="memory"})'
    )
    cpu_result: list[dict[str, Any]] = prom_query(prom_url, cpu_query)
    ram_result: list[dict[str, Any]] = prom_query(prom_url, ram_query)
    cpu: float = 0.0
    ram: float = 0.0
    try:
        if cpu_result:
            cpu = float(cpu_result[0]["value"][1])
        if ram_result:
            ram = float(ram_result[0]["value"][1])
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return cpu, ram


def gather_allocation_by_deployment(
    opencost_url: str,
    window: str = "7d",
) -> dict[tuple[str, str], dict[str, float]]:
    """Return a mapping of (namespace, deployment) -> totals from OpenCost.

    Each value contains keys: totalCost, cpuEfficiency, ramEfficiency.
    Costs are in USD over the requested window.
    """
    params: dict[str, str] = {
        "window": window,
        "aggregate": "namespace,deployment",
        "accumulate": "true",
    }
    query: str = urllib.parse.urlencode(params, safe='":[]')
    url: str = f"{opencost_url.rstrip('/')}/allocation?{query}"
    body: dict[str, Any] = _http_json(url)
    out: dict[tuple[str, str], dict[str, float]] = {}
    for block in body.get("data", []) or []:
        if not isinstance(block, dict):
            continue
        for name, entry in block.items():
            if not isinstance(entry, dict):
                continue
            if name in {"__idle__", "__unallocated__"}:
                continue
            props: dict[str, Any] = entry.get("properties") or {}
            ns: str = str(props.get("namespace") or "")
            dep: str = str(
                props.get("deployment") or props.get("controller") or ""
            )
            if not ns or not dep:
                # Fall back to splitting the name "ns/dep" when properties absent.
                if "/" in name:
                    ns, dep = name.split("/", 1)
                else:
                    continue
            out[(ns, dep)] = {
                "totalCost": float(entry.get("totalCost") or 0.0),
                "cpuEfficiency": float(entry.get("cpuEfficiency") or 0.0),
                "ramEfficiency": float(entry.get("ramEfficiency") or 0.0),
            }
    return out


def build_workload_stats(
    opencost_url: str,
    prom_url: str,
    window: str,
) -> list[WorkloadStats]:
    """Gather all stats needed to build a right-sizing report."""
    alloc: dict[tuple[str, str], dict[str, float]] = (
        gather_allocation_by_deployment(opencost_url, window=window)
    )
    rows: list[WorkloadStats] = []
    for (ns, dep), totals in alloc.items():
        cpu_req, ram_req = gather_requests(prom_url, ns, dep)
        cpu_p95: float = gather_cpu_p95(prom_url, ns, dep, window)
        ram_p95: float = gather_ram_p95(prom_url, ns, dep, window)
        # Convert window cost to monthly cost: 30 days / window days.
        monthly: float = _window_to_monthly(totals["totalCost"], window)
        rows.append(
            WorkloadStats(
                namespace=ns,
                deployment=dep,
                cpu_request_cores=cpu_req,
                cpu_p95_cores=cpu_p95,
                ram_request_bytes=ram_req,
                ram_p95_bytes=ram_p95,
                monthly_cost_usd=monthly,
                cpu_efficiency=totals["cpuEfficiency"],
                ram_efficiency=totals["ramEfficiency"],
            )
        )
    return rows


def _window_to_monthly(cost: float, window: str) -> float:
    """Approximate a monthly cost from a per-window cost."""
    factors: dict[str, float] = {
        "1h": 24 * 30,
        "24h": 30.0,
        "1d": 30.0,
        "7d": 30.0 / 7.0,
        "30d": 1.0,
    }
    factor: float = factors.get(window, 1.0)
    return cost * factor


def format_recommendation(
    stats: WorkloadStats,
    margin: float = 1.3,
) -> str:
    """Format a one-line right-sizing recommendation for a workload."""
    cpu_rec_cores: float = max(0.05, stats.cpu_p95_cores * margin)
    ram_rec_bytes: float = max(
        64 * 1024 * 1024, stats.ram_p95_bytes * margin
    )
    waste_eff: float = min(stats.cpu_efficiency, stats.ram_efficiency)
    if waste_eff > 1.0:
        waste_eff = 1.0
    if waste_eff < 0.0:
        waste_eff = 0.0
    monthly_waste: float = stats.monthly_cost_usd * (1.0 - waste_eff)
    return (
        f"{stats.namespace}/{stats.deployment}: "
        f"req {stats.cpu_request_cores:.2f}c/"
        f"{stats.ram_request_bytes / 1024 / 1024:.0f}MiB "
        f"-> p95 {stats.cpu_p95_cores:.2f}c/"
        f"{stats.ram_p95_bytes / 1024 / 1024:.0f}MiB; "
        f"recommend {cpu_rec_cores:.2f}c/"
        f"{ram_rec_bytes / 1024 / 1024:.0f}MiB; "
        f"~${monthly_waste:.2f}/mo recoverable"
    )


def main(argv: list[str]) -> int:
    """Command-line entry point. Returns process exit code."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Generate a right-sizing report from OpenCost + Prometheus."
    )
    parser.add_argument(
        "--opencost-url",
        default="http://localhost:9003",
    )
    parser.add_argument(
        "--prom-url",
        default="http://localhost:9090",
    )
    parser.add_argument(
        "--window",
        default="7d",
        help="Window: 24h, 7d, 30d. Default %(default)s.",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=1.3,
        help="Safety margin over P95 (default %(default)s).",
    )
    args: argparse.Namespace = parser.parse_args(argv)

    try:
        rows: list[WorkloadStats] = build_workload_stats(
            opencost_url=args.opencost_url,
            prom_url=args.prom_url,
            window=args.window,
        )
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    rows.sort(key=lambda r: r.monthly_cost_usd, reverse=True)
    print("Right-sizing report")
    print("===================")
    for r in rows:
        print(format_recommendation(r, margin=args.margin))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
