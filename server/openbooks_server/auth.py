"""Engine-key check: the shared secret the Next.js server sends in x-openbooks-key."""
from __future__ import annotations

import hmac
import logging
import os
from collections.abc import Mapping

log = logging.getLogger("openbooks_server")
KEY_HEADER = b"x-openbooks-key"
KEY_ENV = "OPENBOOKS_ENGINE_KEY"
KEY_EXEMPT = frozenset({"/healthz", "/readyz"})


def engine_key_from_env() -> bytes:
    """The configured key as bytes. Empty means auth is off, so the engine accepts any caller; a warning is logged."""
    key = os.environ.get(KEY_ENV, "").encode()
    if not key:
        log.warning("%s is not set: the engine accepts any caller that can reach it. "
                    "Set it whenever the engine listens on anything but loopback.", KEY_ENV)
    return key


def is_authorised(key: bytes, path: str, headers: Mapping[bytes, bytes]) -> bool:
    """True when auth is off, the path is a probe, or the key header matches (constant-time comparison)."""
    if not key or path in KEY_EXEMPT:
        return True
    return hmac.compare_digest(headers.get(KEY_HEADER, b""), key)
