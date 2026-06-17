"""Vault demo client for Week 10 Exercise 1.

Reads and writes secrets against a HashiCorp Vault server running in dev mode.
Intended to be run from the host (after `kubectl port-forward svc/vault 8200`)
or from inside a pod that has been configured with the Kubernetes auth method.

This file is import-safe: the `hvac` import is guarded so that
`python3 -m py_compile vault_demo.py` works in isolation without the
package installed. At runtime the package is present and the code paths run.

Reference:
    https://hvac.readthedocs.io/
    https://developer.hashicorp.com/vault/docs/auth/kubernetes
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any


LOG: logging.Logger = logging.getLogger("vault_demo")


def get_client_token_auth(addr: str, token: str) -> Any:
    """Construct an hvac client authenticated via a static token.

    Used in dev mode where Vault is unsealed and a root token is known.
    Never use a long-lived token in production; prefer Kubernetes auth.
    """
    try:
        import hvac
    except ImportError:
        LOG.error("hvac not installed; run `pip install hvac`")
        return None
    client: Any = hvac.Client(url=addr, token=token)
    if not client.is_authenticated():
        LOG.error("vault authentication failed for token-auth at %s", addr)
        return None
    LOG.info("vault token-auth ok: addr=%s", addr)
    return client


def get_client_k8s_auth(
    addr: str,
    role: str,
    jwt_path: str = "/var/run/secrets/kubernetes.io/serviceaccount/token",
    mount_point: str = "kubernetes",
) -> Any:
    """Construct an hvac client authenticated via the Kubernetes auth method.

    Reads the pod's service-account JWT from the standard projected-volume
    path, sends it to Vault's Kubernetes auth method, and obtains a Vault
    token bound to the configured role.
    """
    try:
        import hvac
    except ImportError:
        LOG.error("hvac not installed; run `pip install hvac`")
        return None

    try:
        with open(jwt_path, "r", encoding="utf-8") as fh:
            jwt: str = fh.read().strip()
    except OSError as exc:
        LOG.error("could not read service-account JWT at %s: %s", jwt_path, exc)
        return None

    client: Any = hvac.Client(url=addr)
    try:
        client.auth.kubernetes.login(role=role, jwt=jwt, mount_point=mount_point)
    except Exception as exc:  # noqa: BLE001 (hvac raises a variety of types)
        LOG.error("vault k8s-auth login failed: %s", exc)
        return None

    if not client.is_authenticated():
        LOG.error("vault k8s-auth authentication did not succeed")
        return None
    LOG.info("vault k8s-auth ok: addr=%s role=%s", addr, role)
    return client


def write_kv_secret(
    client: Any,
    path: str,
    data: dict[str, str],
    mount_point: str = "secret",
) -> bool:
    """Write a secret to the K/V v2 engine at the given path."""
    if client is None:
        return False
    try:
        client.secrets.kv.v2.create_or_update_secret(
            path=path,
            secret=data,
            mount_point=mount_point,
        )
    except Exception as exc:  # noqa: BLE001
        LOG.error("vault kv write failed at %s: %s", path, exc)
        return False
    LOG.info("vault kv write ok: path=%s keys=%s", path, list(data.keys()))
    return True


def read_kv_secret(
    client: Any,
    path: str,
    mount_point: str = "secret",
) -> dict[str, Any]:
    """Read a secret from the K/V v2 engine. Returns the data dict or {}."""
    if client is None:
        return {}
    try:
        response: dict[str, Any] = client.secrets.kv.v2.read_secret_version(
            path=path,
            mount_point=mount_point,
        )
    except Exception as exc:  # noqa: BLE001
        LOG.error("vault kv read failed at %s: %s", path, exc)
        return {}
    data_block: dict[str, Any] = response.get("data", {})
    payload: dict[str, Any] = data_block.get("data", {}) or {}
    LOG.info("vault kv read ok: path=%s keys=%s", path, list(payload.keys()))
    return payload


def demo_token_path() -> int:
    """Demo: token-auth, write a secret, read it back."""
    addr: str = os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
    token: str = os.environ.get("VAULT_TOKEN", "")
    if not token:
        LOG.error("VAULT_TOKEN not set; cannot run demo")
        return 1

    client: Any = get_client_token_auth(addr=addr, token=token)
    if client is None:
        return 1

    ok: bool = write_kv_secret(
        client=client,
        path="myapp/db",
        data={
            "username": "webapp",
            "password": "hunter2-not-a-real-password",
            "host": "postgres.default.svc.cluster.local",
        },
    )
    if not ok:
        return 1

    read_back: dict[str, Any] = read_kv_secret(client=client, path="myapp/db")
    LOG.info("read-back: %s", read_back)
    return 0


def demo_k8s_path() -> int:
    """Demo: k8s-auth, read a pre-populated secret."""
    addr: str = os.environ.get("VAULT_ADDR", "http://vault.vault.svc.cluster.local:8200")
    role: str = os.environ.get("VAULT_ROLE", "myapp")
    client: Any = get_client_k8s_auth(addr=addr, role=role)
    if client is None:
        return 1
    payload: dict[str, Any] = read_kv_secret(client=client, path="myapp/db")
    LOG.info("k8s-auth read-back: %s", payload)
    return 0


def main() -> int:
    """Entrypoint. Picks demo mode based on $VAULT_AUTH_MODE."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    mode: str = os.environ.get("VAULT_AUTH_MODE", "token").lower()
    if mode == "token":
        return demo_token_path()
    if mode == "k8s":
        return demo_k8s_path()
    LOG.error("unknown VAULT_AUTH_MODE=%s; expected 'token' or 'k8s'", mode)
    return 2


if __name__ == "__main__":
    sys.exit(main())
