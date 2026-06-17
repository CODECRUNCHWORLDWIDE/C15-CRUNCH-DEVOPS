"""Tiny HTTP service that reads its database credentials at startup.

For Week 10 Exercise 2. Demonstrates the consumer side of External Secrets:
the pod treats `/etc/secrets/db-password` and similar paths as the canonical
source. The Kubernetes Secret behind that mount is populated by either the
External Secrets Operator (pulling from Vault) or by Sealed Secrets
(reconciled from a SealedSecret CRD). The pod does not care which.

Exposes:
    GET /         - returns a summary of which secret keys were loaded
    GET /health   - liveness probe
    GET /verify   - reads the secret again from disk and reports whether
                    the value differs from the boot-time value (used to
                    demonstrate ExternalSecret refresh behavior)

This file is import-safe even when http.server is the only dependency.
"""
from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


LOG: logging.Logger = logging.getLogger("secret_consumer")

SECRETS_DIR: str = os.environ.get("SECRETS_DIR", "/etc/secrets")
PORT: int = int(os.environ.get("PORT", "8080"))


def read_secret_file(path: str) -> str:
    """Read a single secret file. Returns the contents stripped of trailing newline.

    Returns "" if the file does not exist. Logs but does not raise on read errors.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError as exc:
        LOG.warning("could not read secret at %s: %s", path, exc)
        return ""


def load_all_secrets(secrets_dir: str) -> dict[str, str]:
    """Load every regular file under secrets_dir into a dict.

    Symlinks are followed (Kubernetes secret mounts use atomic symlink swaps
    so reading the symlink target always sees a consistent value).
    """
    out: dict[str, str] = {}
    if not os.path.isdir(secrets_dir):
        LOG.warning("secrets dir %s does not exist", secrets_dir)
        return out
    for name in os.listdir(secrets_dir):
        if name.startswith("."):
            continue
        full: str = os.path.join(secrets_dir, name)
        if os.path.isfile(full):
            out[name] = read_secret_file(full)
    return out


# Boot-time snapshot. The application captures this once and uses it as the
# baseline for comparison in the /verify endpoint.
BOOT_SECRETS: dict[str, str] = load_all_secrets(SECRETS_DIR)


def redact(value: str) -> str:
    """Return a redacted form of a secret value for safe logging or display.

    Shows the length and the first 2 characters; never the full secret.
    """
    if not value:
        return "(empty)"
    if len(value) <= 4:
        return "(<=4 chars)"
    return f"{value[:2]}***({len(value)} chars)"


class ConsumerHandler(BaseHTTPRequestHandler):
    """HTTP handler for the secret-consumer demo service."""

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler convention)
        if self.path == "/":
            self._serve_summary()
        elif self.path == "/health":
            self._serve_health()
        elif self.path == "/verify":
            self._serve_verify()
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:
        """Suppress default access log; emit through stdlib logging."""
        LOG.info("%s - %s", self.client_address[0], fmt % args)

    def _write_json(self, status: int, body: dict[str, Any]) -> None:
        """Helper: write a JSON response with the given status."""
        encoded: bytes = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _serve_summary(self) -> None:
        """List the secret keys observed at boot, redacted."""
        body: dict[str, Any] = {
            "secrets_dir": SECRETS_DIR,
            "boot_keys": sorted(BOOT_SECRETS.keys()),
            "redacted_values": {k: redact(v) for k, v in BOOT_SECRETS.items()},
        }
        self._write_json(200, body)

    def _serve_health(self) -> None:
        """Liveness: always returns 200 with status=ok."""
        self._write_json(200, {"status": "ok"})

    def _serve_verify(self) -> None:
        """Re-read the secrets from disk and compare to the boot snapshot.

        Reports whether any key has rotated. This is how you demonstrate
        ExternalSecret refresh: write a new value to Vault, wait for ESO's
        refreshInterval, then hit /verify and observe `rotated=true`.
        """
        current: dict[str, str] = load_all_secrets(SECRETS_DIR)
        rotated_keys: list[str] = []
        for key in sorted(set(current.keys()) | set(BOOT_SECRETS.keys())):
            if current.get(key, "") != BOOT_SECRETS.get(key, ""):
                rotated_keys.append(key)
        body: dict[str, Any] = {
            "secrets_dir": SECRETS_DIR,
            "rotated": bool(rotated_keys),
            "rotated_keys": rotated_keys,
            "boot_redacted": {k: redact(v) for k, v in BOOT_SECRETS.items()},
            "current_redacted": {k: redact(v) for k, v in current.items()},
        }
        self._write_json(200, body)


def main() -> None:
    """Run the HTTP server on the configured port."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    LOG.info("starting secret-consumer on :%d", PORT)
    LOG.info("boot snapshot: %s", {k: redact(v) for k, v in BOOT_SECRETS.items()})
    server: HTTPServer = HTTPServer(("0.0.0.0", PORT), ConsumerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
