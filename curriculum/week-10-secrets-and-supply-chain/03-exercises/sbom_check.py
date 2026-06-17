"""Validate that a syft-generated SBOM satisfies the CISA Minimum Elements.

For Week 10 Exercise 4. Takes one or more SBOM file paths on the command line
(SPDX-JSON or CycloneDX-JSON, auto-detected) and reports which of the seven
CISA Minimum Elements are present for each component.

The seven elements (https://www.cisa.gov/sbom):
    1. Supplier name
    2. Component name
    3. Version
    4. Unique identifier (PURL or CPE)
    5. Dependency relationship
    6. Author of SBOM data
    7. Timestamp

Usage:
    python3 sbom_check.py sbom.spdx.json
    python3 sbom_check.py sbom.cdx.json
    python3 sbom_check.py sbom.spdx.json sbom.cdx.json --quiet

Exit code is 0 if every component has every required field; non-zero otherwise.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any


LOG: logging.Logger = logging.getLogger("sbom_check")


def detect_format(doc: dict[str, Any]) -> str:
    """Return 'spdx', 'cyclonedx', or 'unknown' based on schema markers."""
    if "spdxVersion" in doc:
        return "spdx"
    if doc.get("bomFormat") == "CycloneDX":
        return "cyclonedx"
    return "unknown"


def check_spdx(doc: dict[str, Any]) -> dict[str, Any]:
    """Run the seven-element check against an SPDX document."""
    report: dict[str, Any] = {
        "format": "spdx",
        "spdx_version": doc.get("spdxVersion", ""),
        "timestamp_present": False,
        "author_present": False,
        "component_count": 0,
        "components_missing": [],
        "ok": False,
    }
    creation_info: dict[str, Any] = doc.get("creationInfo", {}) or {}
    report["timestamp_present"] = bool(creation_info.get("created"))
    creators: list[str] = creation_info.get("creators", []) or []
    report["author_present"] = len(creators) > 0
    relationships: list[dict[str, Any]] = doc.get("relationships", []) or []
    has_relationship: dict[str, bool] = {}
    for rel in relationships:
        spdx_id: str = rel.get("spdxElementId", "")
        related: str = rel.get("relatedSpdxElement", "")
        rel_type: str = rel.get("relationshipType", "")
        # Either side of a non-DESCRIBES relationship counts as "has a relationship"
        if rel_type and rel_type != "NOOP":
            has_relationship[spdx_id] = True
            has_relationship[related] = True
    packages: list[dict[str, Any]] = doc.get("packages", []) or []
    report["component_count"] = len(packages)
    for pkg in packages:
        missing_fields: list[str] = []
        if not pkg.get("supplier"):
            missing_fields.append("supplier")
        if not pkg.get("name"):
            missing_fields.append("name")
        if not pkg.get("versionInfo"):
            missing_fields.append("versionInfo")
        ext_refs: list[dict[str, Any]] = pkg.get("externalRefs", []) or []
        has_purl_or_cpe: bool = any(
            r.get("referenceType") in ("purl", "cpe22Type", "cpe23Type")
            for r in ext_refs
        )
        if not has_purl_or_cpe:
            missing_fields.append("purl-or-cpe")
        if not has_relationship.get(pkg.get("SPDXID", ""), False):
            missing_fields.append("dependency-relationship")
        if missing_fields:
            report["components_missing"].append({
                "name": pkg.get("name", "?"),
                "version": pkg.get("versionInfo", "?"),
                "missing": missing_fields,
            })
    report["ok"] = (
        report["timestamp_present"]
        and report["author_present"]
        and len(report["components_missing"]) == 0
    )
    return report


def check_cyclonedx(doc: dict[str, Any]) -> dict[str, Any]:
    """Run the seven-element check against a CycloneDX document."""
    report: dict[str, Any] = {
        "format": "cyclonedx",
        "spec_version": doc.get("specVersion", ""),
        "timestamp_present": False,
        "author_present": False,
        "component_count": 0,
        "components_missing": [],
        "ok": False,
    }
    metadata: dict[str, Any] = doc.get("metadata", {}) or {}
    report["timestamp_present"] = bool(metadata.get("timestamp"))
    tools: Any = metadata.get("tools", []) or []
    # CycloneDX 1.5+ allows tools to be a dict; 1.4- requires a list.
    if isinstance(tools, dict):
        tool_list: list[Any] = tools.get("components", []) or []
    else:
        tool_list = tools
    report["author_present"] = len(tool_list) > 0 or bool(metadata.get("authors"))
    dependencies: list[dict[str, Any]] = doc.get("dependencies", []) or []
    deps_by_ref: dict[str, bool] = {}
    for dep in dependencies:
        ref: str = dep.get("ref", "")
        if ref:
            deps_by_ref[ref] = True
        for child in dep.get("dependsOn", []) or []:
            deps_by_ref[child] = True
    components: list[dict[str, Any]] = doc.get("components", []) or []
    report["component_count"] = len(components)
    for comp in components:
        missing_fields: list[str] = []
        if not comp.get("supplier") and not comp.get("publisher") and not comp.get("author"):
            missing_fields.append("supplier-or-publisher")
        if not comp.get("name"):
            missing_fields.append("name")
        if not comp.get("version"):
            missing_fields.append("version")
        if not comp.get("purl") and not comp.get("cpe"):
            missing_fields.append("purl-or-cpe")
        ref_key: str = comp.get("bom-ref", "") or comp.get("purl", "")
        if not deps_by_ref.get(ref_key, False):
            missing_fields.append("dependency-relationship")
        if missing_fields:
            report["components_missing"].append({
                "name": comp.get("name", "?"),
                "version": comp.get("version", "?"),
                "missing": missing_fields,
            })
    report["ok"] = (
        report["timestamp_present"]
        and report["author_present"]
        and len(report["components_missing"]) == 0
    )
    return report


def check_file(path: str) -> dict[str, Any]:
    """Load one SBOM file and run the appropriate check."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc: dict[str, Any] = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        return {"path": path, "ok": False, "error": str(exc)}
    fmt: str = detect_format(doc)
    if fmt == "spdx":
        report: dict[str, Any] = check_spdx(doc)
    elif fmt == "cyclonedx":
        report = check_cyclonedx(doc)
    else:
        return {"path": path, "ok": False, "error": "unknown SBOM format"}
    report["path"] = path
    return report


def render_report(report: dict[str, Any], quiet: bool) -> None:
    """Print a human-readable summary of one file's report."""
    print(f"---")
    print(f"file: {report.get('path', '')}")
    if report.get("error"):
        print(f"  ERROR: {report['error']}")
        return
    print(f"  format: {report['format']}")
    print(f"  timestamp_present: {report['timestamp_present']}")
    print(f"  author_present: {report['author_present']}")
    print(f"  component_count: {report['component_count']}")
    missing: list[dict[str, Any]] = report.get("components_missing", [])
    print(f"  components_with_missing_fields: {len(missing)}")
    if not quiet:
        for entry in missing[:25]:
            fields: str = ", ".join(entry["missing"])
            print(f"    - {entry['name']}@{entry['version']}: {fields}")
        if len(missing) > 25:
            print(f"    ... and {len(missing) - 25} more")
    print(f"  ok: {report['ok']}")


def main() -> int:
    """Entrypoint. Parses args, runs the checks, prints reports."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Check syft-generated SBOMs against CISA minimum elements.",
    )
    parser.add_argument("paths", nargs="+", help="SBOM file path(s)")
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress per-component detail"
    )
    args: argparse.Namespace = parser.parse_args()

    overall_ok: bool = True
    for path in args.paths:
        report: dict[str, Any] = check_file(path)
        render_report(report=report, quiet=args.quiet)
        if not report.get("ok", False):
            overall_ok = False
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
