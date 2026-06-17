"""A trivial FastAPI service used as the target for cosign signing.

For Week 10 Exercise 3 and Exercise 4. The application itself is uninteresting
on purpose: the lessons are in the *build, sign, scan, and verify* flow,
not in the application code.

Endpoints:
    GET /            - returns a JSON greeting
    GET /api/health  - liveness probe
    GET /version     - returns build metadata (set via env vars at build time)

This file is import-safe even if FastAPI is not installed; `build_app`
returns None in that case so `python3 -m py_compile signed_app.py` is clean.
"""
from __future__ import annotations

import logging
import os
from typing import Any


LOG: logging.Logger = logging.getLogger("signed_app")


def get_build_metadata() -> dict[str, str]:
    """Return build metadata baked in via env vars at container build time.

    The CI workflow sets these from the GitHub Actions context:
        BUILD_GIT_SHA   - the source commit
        BUILD_GIT_REF   - the ref (branch or tag) the build ran from
        BUILD_VERSION   - the semver tag if any
        BUILD_TIMESTAMP - ISO-8601 timestamp the image was built
    """
    return {
        "git_sha": os.environ.get("BUILD_GIT_SHA", "unknown"),
        "git_ref": os.environ.get("BUILD_GIT_REF", "unknown"),
        "version": os.environ.get("BUILD_VERSION", "0.0.0-dev"),
        "timestamp": os.environ.get("BUILD_TIMESTAMP", "unknown"),
    }


def render_greeting(name: str) -> dict[str, Any]:
    """Compute a greeting and attach build metadata.

    The metadata is here so a verifier reading the running pod can sanity-check
    that the build it expected is the build that is running.
    """
    sanitized: str = name.strip()[:64] or "world"
    return {
        "greeting": f"Hello, {sanitized}",
        "build": get_build_metadata(),
    }


def build_app() -> Any:
    """Construct the FastAPI app. Returns None if FastAPI is not installed."""
    try:
        from fastapi import FastAPI
    except ImportError:
        LOG.warning("fastapi not installed; build_app skipped")
        return None

    app: Any = FastAPI(title="signed-app", version=get_build_metadata()["version"])

    @app.get("/")
    def root(name: str = "world") -> dict[str, Any]:
        return render_greeting(name=name)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/version")
    def version() -> dict[str, str]:
        return get_build_metadata()

    return app


def main() -> None:
    """Run the service under uvicorn. Used only for local development."""
    try:
        import uvicorn
    except ImportError:
        LOG.error("uvicorn not installed; cannot serve")
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app: Any = build_app()
    if app is None:
        return
    port: int = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
