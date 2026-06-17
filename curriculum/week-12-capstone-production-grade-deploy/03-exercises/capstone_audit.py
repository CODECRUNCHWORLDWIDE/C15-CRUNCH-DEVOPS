"""
capstone_audit.py — produce a checklist report on the state of the
Week 12 capstone cluster.

The audit walks the cluster (via the kubectl Python client OR via
`kubectl` shell-outs, depending on what is available) and produces a
markdown-formatted report on the state of every component the
capstone exercises. The report lists which components are present,
which are absent, and which are present but unhealthy.

The audit is deliberately read-only. It does not change cluster state.
Run it before submitting the mini-project to confirm the cluster is
in the expected shape.

This module uses only Python's standard library and subprocess to
invoke kubectl. It does not depend on the kubernetes Python package
to keep the prerequisite set small.

References:
    - kubectl reference: https://kubernetes.io/docs/reference/kubectl/
    - jsonpath outputs:  https://kubernetes.io/docs/reference/kubectl/jsonpath/

Usage:
    python3 capstone_audit.py [--context kind-capstone] [--output report.md]

Exit code: 0 if every check passes, 1 if any check fails. Used in CI
as a smoke gate on a successful bootstrap.

Type-hinted throughout. Compiles cleanly with `python3 -m py_compile`.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    """The outcome of one audit check."""

    name: str
    ok: bool
    detail: str
    notes: list[str] = field(default_factory=list)

    def render_md(self) -> str:
        """Render as a markdown bullet."""
        flag: str = "PASS" if self.ok else "FAIL"
        out: list[str] = [f"- **[{flag}]** `{self.name}` — {self.detail}"]
        for n in self.notes:
            out.append(f"    - {n}")
        return "\n".join(out)


def _have_kubectl() -> bool:
    """Return True if kubectl is on PATH."""
    return shutil.which("kubectl") is not None


def _kubectl_json(
    args: list[str],
    context: str | None = None,
    timeout_s: float = 30.0,
) -> dict[str, Any] | None:
    """Invoke kubectl with -o json. Return the parsed JSON or None."""
    cmd: list[str] = ["kubectl"]
    if context:
        cmd += ["--context", context]
    cmd += args + ["-o", "json"]
    try:
        proc: subprocess.CompletedProcess[bytes] = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def check_namespace_exists(name: str, context: str | None) -> CheckResult:
    """Check that a namespace exists and is Active."""
    payload: dict[str, Any] | None = _kubectl_json(
        ["get", "namespace", name],
        context=context,
    )
    if payload is None:
        return CheckResult(
            name=f"namespace/{name}",
            ok=False,
            detail="kubectl get failed or namespace absent",
        )
    phase: str = (payload.get("status") or {}).get("phase") or "Unknown"
    if phase != "Active":
        return CheckResult(
            name=f"namespace/{name}",
            ok=False,
            detail=f"phase is {phase!r}",
        )
    return CheckResult(
        name=f"namespace/{name}",
        ok=True,
        detail="Active",
    )


def check_deployment_ready(
    namespace: str,
    name: str,
    context: str | None,
) -> CheckResult:
    """Check that a Deployment exists and has its desired replicas ready."""
    payload: dict[str, Any] | None = _kubectl_json(
        ["get", "deployment", name, "-n", namespace],
        context=context,
    )
    if payload is None:
        return CheckResult(
            name=f"deployment/{namespace}/{name}",
            ok=False,
            detail="kubectl get failed or deployment absent",
        )
    spec: dict[str, Any] = payload.get("spec") or {}
    status: dict[str, Any] = payload.get("status") or {}
    desired: int = int(spec.get("replicas") or 0)
    ready: int = int(status.get("readyReplicas") or 0)
    if ready < desired or desired == 0:
        return CheckResult(
            name=f"deployment/{namespace}/{name}",
            ok=False,
            detail=f"ready {ready}/{desired}",
        )
    return CheckResult(
        name=f"deployment/{namespace}/{name}",
        ok=True,
        detail=f"ready {ready}/{desired}",
    )


def check_statefulset_ready(
    namespace: str,
    name: str,
    context: str | None,
) -> CheckResult:
    """Check that a StatefulSet exists and has its desired replicas ready."""
    payload: dict[str, Any] | None = _kubectl_json(
        ["get", "statefulset", name, "-n", namespace],
        context=context,
    )
    if payload is None:
        return CheckResult(
            name=f"statefulset/{namespace}/{name}",
            ok=False,
            detail="kubectl get failed or statefulset absent",
        )
    spec: dict[str, Any] = payload.get("spec") or {}
    status: dict[str, Any] = payload.get("status") or {}
    desired: int = int(spec.get("replicas") or 0)
    ready: int = int(status.get("readyReplicas") or 0)
    if ready < desired or desired == 0:
        return CheckResult(
            name=f"statefulset/{namespace}/{name}",
            ok=False,
            detail=f"ready {ready}/{desired}",
        )
    return CheckResult(
        name=f"statefulset/{namespace}/{name}",
        ok=True,
        detail=f"ready {ready}/{desired}",
    )


def check_argocd_apps_healthy(context: str | None) -> CheckResult:
    """Check that every ArgoCD Application is Synced and Healthy."""
    payload: dict[str, Any] | None = _kubectl_json(
        ["get", "applications.argoproj.io", "-n", "argocd"],
        context=context,
    )
    if payload is None:
        return CheckResult(
            name="argocd/applications",
            ok=False,
            detail="kubectl get failed or no ArgoCD Applications present",
        )
    items: list[dict[str, Any]] = payload.get("items") or []
    if not items:
        return CheckResult(
            name="argocd/applications",
            ok=False,
            detail="zero Applications found",
        )
    bad: list[str] = []
    for it in items:
        nm: str = (it.get("metadata") or {}).get("name") or "<unnamed>"
        st: dict[str, Any] = it.get("status") or {}
        sync_status: str = (st.get("sync") or {}).get("status") or "Unknown"
        health_status: str = (st.get("health") or {}).get("status") or "Unknown"
        if sync_status != "Synced" or health_status != "Healthy":
            bad.append(f"{nm}({sync_status}/{health_status})")
    if bad:
        return CheckResult(
            name="argocd/applications",
            ok=False,
            detail=f"{len(bad)} of {len(items)} unhealthy",
            notes=bad,
        )
    return CheckResult(
        name="argocd/applications",
        ok=True,
        detail=f"all {len(items)} apps Synced+Healthy",
    )


def check_kyverno_policies(context: str | None) -> CheckResult:
    """Check that the two capstone Kyverno ClusterPolicies exist."""
    expected: set[str] = {"verify-images", "require-cost-labels"}
    payload: dict[str, Any] | None = _kubectl_json(
        ["get", "clusterpolicies.kyverno.io"],
        context=context,
    )
    if payload is None:
        return CheckResult(
            name="kyverno/clusterpolicies",
            ok=False,
            detail="kubectl get failed or no ClusterPolicies present",
        )
    found: set[str] = {
        (it.get("metadata") or {}).get("name") or ""
        for it in (payload.get("items") or [])
    }
    missing: set[str] = expected - found
    if missing:
        return CheckResult(
            name="kyverno/clusterpolicies",
            ok=False,
            detail=f"missing {sorted(missing)!r}",
        )
    return CheckResult(
        name="kyverno/clusterpolicies",
        ok=True,
        detail=f"all expected policies present: {sorted(expected)!r}",
    )


def check_certificate(
    namespace: str,
    name: str,
    context: str | None,
) -> CheckResult:
    """Check that a cert-manager Certificate is Ready."""
    payload: dict[str, Any] | None = _kubectl_json(
        ["get", "certificate", name, "-n", namespace],
        context=context,
    )
    if payload is None:
        return CheckResult(
            name=f"certificate/{namespace}/{name}",
            ok=False,
            detail="kubectl get failed or Certificate absent",
        )
    status: dict[str, Any] = payload.get("status") or {}
    conditions: list[dict[str, Any]] = status.get("conditions") or []
    ready_status: str = "Unknown"
    for c in conditions:
        if c.get("type") == "Ready":
            ready_status = str(c.get("status"))
            break
    if ready_status != "True":
        return CheckResult(
            name=f"certificate/{namespace}/{name}",
            ok=False,
            detail=f"Ready={ready_status!r}",
        )
    return CheckResult(
        name=f"certificate/{namespace}/{name}",
        ok=True,
        detail="Ready=True",
    )


def run_audit(context: str | None) -> list[CheckResult]:
    """Run every audit check in order. Return all results."""
    checks: list[CheckResult] = []

    # Namespaces.
    for ns in [
        "argocd",
        "ingress-nginx",
        "cert-manager",
        "monitoring",
        "vault",
        "kyverno",
        "opencost",
        "app",
    ]:
        checks.append(check_namespace_exists(ns, context))

    # Core deployments and statefulsets.
    checks.append(check_deployment_ready("argocd", "argocd-server", context))
    checks.append(check_deployment_ready("ingress-nginx", "ingress-nginx-controller", context))
    checks.append(check_deployment_ready("cert-manager", "cert-manager", context))
    checks.append(check_deployment_ready("monitoring", "kube-prometheus-stack-operator", context))
    checks.append(check_deployment_ready("app", "crunch-quotes", context))
    checks.append(check_statefulset_ready("app", "postgres", context))

    # ArgoCD Applications health.
    checks.append(check_argocd_apps_healthy(context))

    # Kyverno policies presence.
    checks.append(check_kyverno_policies(context))

    # The application's TLS certificate.
    checks.append(check_certificate("app", "crunch-quotes-tls", context))

    return checks


def render_report(results: list[CheckResult]) -> str:
    """Render the full audit as a markdown report."""
    total: int = len(results)
    passed: int = sum(1 for r in results if r.ok)
    failed: int = total - passed
    lines: list[str] = [
        "# Capstone audit report",
        "",
        f"- **Checks total:** {total}",
        f"- **Passed:** {passed}",
        f"- **Failed:** {failed}",
        "",
        "## Results",
        "",
    ]
    for r in results:
        lines.append(r.render_md())
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Audit the Week 12 capstone cluster.",
    )
    parser.add_argument(
        "--context",
        default=None,
        help="kubectl context to use (default: current context).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write the report to this file in addition to stdout.",
    )
    args: argparse.Namespace = parser.parse_args(argv)

    if not _have_kubectl():
        print("error: kubectl is not on PATH", file=sys.stderr)
        return 2

    results: list[CheckResult] = run_audit(args.context)
    report: str = render_report(results)
    print(report)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(report)
        except OSError as exc:
            print(f"error: could not write {args.output}: {exc}", file=sys.stderr)
            return 2

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
