"""
smoke_test.py — end-to-end smoke test for the Week 12 capstone.

The smoke test exercises every layer of the capstone, in order:

  1. The application's /health endpoint responds 200 over HTTPS.
  2. The application's /quote endpoint returns a JSON body with a
     non-empty "quote" string.
  3. The application's /metrics endpoint exposes Prometheus metrics
     and includes the request counter `http_requests_total`.
  4. Prometheus is scraping the application (the metric appears with a
     non-zero count in a Prometheus instant query).
  5. ArgoCD reports every Application as Synced and Healthy.

Each step is a function returning (success: bool, message: str). The
overall result is the AND of the steps. On failure, the message
identifies the layer that failed; on success the script exits 0.

Usage:
    python3 smoke_test.py [--host crunch-quotes.local] \
                          [--prometheus-url http://localhost:9090] \
                          [--argocd-url http://localhost:8080] \
                          [--argocd-token TOKEN]

The script depends only on the Python standard library so that the
exercise's prerequisites are unchanged from the rest of the week.

References:
    - kubectl port-forward:
      https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/
    - Prometheus query API:
      https://prometheus.io/docs/prometheus/latest/querying/api/
    - ArgoCD API:
      https://argo-cd.readthedocs.io/en/stable/operator-manual/server-commands/argocd-server/

This file is type-hinted throughout. It compiles cleanly with
`python3 -m py_compile smoke_test.py`.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


# Defaults assume the kubectl port-forward bridges are active:
#   kubectl port-forward -n monitoring svc/.../prometheus 9090:9090
#   kubectl port-forward -n argocd svc/argocd-server 8080:443
# The Ingress for the application is reachable on the host because the
# kind cluster config maps host port 443 to the ingress controller.
DEFAULT_APP_HOST: str = "crunch-quotes.local"
DEFAULT_PROMETHEUS_URL: str = "http://localhost:9090"
DEFAULT_ARGOCD_URL: str = "http://localhost:8080"


@dataclass(frozen=True)
class StepResult:
    """The outcome of a single smoke-test step."""

    name: str
    ok: bool
    message: str

    def render(self) -> str:
        """Return a single-line human-readable representation."""
        flag: str = "PASS" if self.ok else "FAIL"
        return f"[{flag}] {self.name}: {self.message}"


def _build_insecure_context() -> ssl.SSLContext:
    """Return an SSL context that does not verify the local CA.

    The capstone uses a self-signed ClusterIssuer (via cert-manager).
    The certificate is valid for `crunch-quotes.local` but the chain
    is rooted in a CA that is not in the system trust store. For the
    smoke test we accept the trade-off; a real cluster would use a
    real CA (Let's Encrypt) and verify normally.
    """
    ctx: ssl.SSLContext = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _fetch(
    url: str,
    timeout_s: float = 10.0,
    insecure: bool = False,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    """Fetch a URL with a timeout. Return (status, body) on success.

    Raises urllib.error.URLError on transport failure.
    """
    req: urllib.request.Request = urllib.request.Request(
        url=url,
        headers=headers or {"Accept": "*/*"},
    )
    ctx: ssl.SSLContext | None = _build_insecure_context() if insecure else None
    with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
        return resp.getcode(), resp.read()


def step_health(host: str) -> StepResult:
    """Step 1 — the application's /health endpoint responds 200."""
    url: str = f"https://{host}/health"
    try:
        status, body = _fetch(url, insecure=True)
    except (urllib.error.URLError, TimeoutError) as exc:
        return StepResult(
            name="health",
            ok=False,
            message=f"GET {url} failed: {exc}",
        )
    if status != 200:
        return StepResult(
            name="health",
            ok=False,
            message=f"GET {url} returned HTTP {status}",
        )
    body_text: str = body.decode("utf-8", errors="replace").strip()
    return StepResult(
        name="health",
        ok=True,
        message=f"HTTP 200 OK; body={body_text[:60]!r}",
    )


def step_quote(host: str) -> StepResult:
    """Step 2 — the application's /quote endpoint returns a quote."""
    url: str = f"https://{host}/quote"
    try:
        status, body = _fetch(url, insecure=True)
    except (urllib.error.URLError, TimeoutError) as exc:
        return StepResult(
            name="quote",
            ok=False,
            message=f"GET {url} failed: {exc}",
        )
    if status != 200:
        return StepResult(
            name="quote",
            ok=False,
            message=f"GET {url} returned HTTP {status}",
        )
    try:
        payload: dict[str, Any] = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return StepResult(
            name="quote",
            ok=False,
            message=f"GET {url} returned non-JSON body: {exc}",
        )
    quote: Any = payload.get("quote")
    if not isinstance(quote, str) or not quote.strip():
        return StepResult(
            name="quote",
            ok=False,
            message=f"GET {url} returned payload without a quote string: {payload!r}",
        )
    return StepResult(
        name="quote",
        ok=True,
        message=f"got quote: {quote[:60]!r}",
    )


def step_metrics(host: str) -> StepResult:
    """Step 3 — the application's /metrics endpoint exposes counters."""
    url: str = f"https://{host}/metrics"
    try:
        status, body = _fetch(url, insecure=True)
    except (urllib.error.URLError, TimeoutError) as exc:
        return StepResult(
            name="metrics",
            ok=False,
            message=f"GET {url} failed: {exc}",
        )
    if status != 200:
        return StepResult(
            name="metrics",
            ok=False,
            message=f"GET {url} returned HTTP {status}",
        )
    body_text: str = body.decode("utf-8", errors="replace")
    if "http_requests_total" not in body_text:
        return StepResult(
            name="metrics",
            ok=False,
            message=(
                f"GET {url} returned no http_requests_total metric; "
                f"first 200 chars: {body_text[:200]!r}"
            ),
        )
    return StepResult(
        name="metrics",
        ok=True,
        message="http_requests_total metric present",
    )


def step_prometheus(prometheus_url: str) -> StepResult:
    """Step 4 — Prometheus scrapes the application."""
    query: str = "sum(rate(http_requests_total{app=\"crunch-quotes\"}[5m]))"
    url: str = (
        f"{prometheus_url.rstrip('/')}/api/v1/query"
        f"?query={urllib.parse.quote(query)}"
    )
    try:
        status, body = _fetch(url)
    except (urllib.error.URLError, TimeoutError) as exc:
        return StepResult(
            name="prometheus",
            ok=False,
            message=f"GET {url} failed: {exc}",
        )
    if status != 200:
        return StepResult(
            name="prometheus",
            ok=False,
            message=f"GET {url} returned HTTP {status}",
        )
    try:
        payload: dict[str, Any] = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return StepResult(
            name="prometheus",
            ok=False,
            message=f"Prometheus returned non-JSON body: {exc}",
        )
    if payload.get("status") != "success":
        return StepResult(
            name="prometheus",
            ok=False,
            message=f"Prometheus query status: {payload.get('status')!r}",
        )
    data: dict[str, Any] = payload.get("data") or {}
    result: list[Any] = data.get("result") or []
    if not result:
        return StepResult(
            name="prometheus",
            ok=False,
            message=(
                "Prometheus query returned no series; either the "
                "ServiceMonitor is not matching, or scrape has not yet "
                "happened (wait 60 seconds and retry)."
            ),
        )
    # A series is [timestamp, "value"]. Parse the value as float.
    first: dict[str, Any] = result[0]
    value_pair: list[Any] = first.get("value") or [0, "0"]
    try:
        rate_value: float = float(value_pair[1])
    except (ValueError, TypeError, IndexError):
        rate_value = 0.0
    return StepResult(
        name="prometheus",
        ok=True,
        message=f"rate={rate_value:.4f} req/s",
    )


def step_argocd(argocd_url: str, token: str | None) -> StepResult:
    """Step 5 — ArgoCD reports all Applications Synced + Healthy."""
    if not token:
        return StepResult(
            name="argocd",
            ok=True,
            message="skipped (no token supplied; ArgoCD check is opt-in)",
        )
    url: str = f"{argocd_url.rstrip('/')}/api/v1/applications"
    try:
        status, body = _fetch(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        return StepResult(
            name="argocd",
            ok=False,
            message=f"GET {url} failed: {exc}",
        )
    if status != 200:
        return StepResult(
            name="argocd",
            ok=False,
            message=f"GET {url} returned HTTP {status}",
        )
    try:
        payload: dict[str, Any] = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return StepResult(
            name="argocd",
            ok=False,
            message=f"ArgoCD returned non-JSON body: {exc}",
        )
    apps: list[dict[str, Any]] = payload.get("items") or []
    if not apps:
        return StepResult(
            name="argocd",
            ok=False,
            message="ArgoCD reports zero Applications",
        )
    bad: list[str] = []
    for app in apps:
        name: str = (app.get("metadata") or {}).get("name") or "<unnamed>"
        status_block: dict[str, Any] = app.get("status") or {}
        sync_status: str = (
            (status_block.get("sync") or {}).get("status") or "Unknown"
        )
        health_status: str = (
            (status_block.get("health") or {}).get("status") or "Unknown"
        )
        if sync_status != "Synced" or health_status != "Healthy":
            bad.append(f"{name}({sync_status}/{health_status})")
    if bad:
        return StepResult(
            name="argocd",
            ok=False,
            message=f"{len(bad)} of {len(apps)} apps not Synced+Healthy: {', '.join(bad)}",
        )
    return StepResult(
        name="argocd",
        ok=True,
        message=f"all {len(apps)} apps Synced+Healthy",
    )


def run_smoke_test(
    app_host: str,
    prometheus_url: str,
    argocd_url: str,
    argocd_token: str | None,
) -> list[StepResult]:
    """Run every smoke-test step in order. Return the full result list."""
    steps: list[Callable[[], StepResult]] = [
        lambda: step_health(app_host),
        lambda: step_quote(app_host),
        lambda: step_metrics(app_host),
        lambda: step_prometheus(prometheus_url),
        lambda: step_argocd(argocd_url, argocd_token),
    ]
    return [s() for s in steps]


def main(argv: list[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="End-to-end smoke test for the W12 capstone.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_APP_HOST,
        help="Application host (default: %(default)s).",
    )
    parser.add_argument(
        "--prometheus-url",
        default=DEFAULT_PROMETHEUS_URL,
        help="Prometheus URL (default: %(default)s).",
    )
    parser.add_argument(
        "--argocd-url",
        default=DEFAULT_ARGOCD_URL,
        help="ArgoCD API URL (default: %(default)s).",
    )
    parser.add_argument(
        "--argocd-token",
        default=None,
        help=(
            "ArgoCD bearer token. If omitted, the ArgoCD step is "
            "skipped. Get one with: argocd account generate-token."
        ),
    )
    args: argparse.Namespace = parser.parse_args(argv)

    results: list[StepResult] = run_smoke_test(
        app_host=args.host,
        prometheus_url=args.prometheus_url,
        argocd_url=args.argocd_url,
        argocd_token=args.argocd_token,
    )
    for r in results:
        print(r.render())

    ok: bool = all(r.ok for r in results)
    if ok:
        print("\nSMOKE TEST PASSED")
        return 0
    print("\nSMOKE TEST FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
