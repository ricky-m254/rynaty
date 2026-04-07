from __future__ import annotations

import secrets
import time


_CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_ulid() -> str:
    """Return a canonical 26-character ULID string."""
    timestamp_ms = int(time.time() * 1000)
    if not 0 <= timestamp_ms < (1 << 48):
        raise ValueError("ULID timestamp is out of range.")

    randomness = int.from_bytes(secrets.token_bytes(10), "big")
    value = (timestamp_ms << 80) | randomness

    chars: list[str] = []
    for _ in range(26):
        chars.append(_CROCKFORD_BASE32[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))
