import hmac
import hashlib
import json
import os
from typing import Dict


# MUST be set in Render / Railway / env vars
# Example: LICENSE_SECRET = "super-long-random-string"
SECRET = os.getenv("LICENSE_SECRET")

if not SECRET:
    raise RuntimeError("LICENSE_SECRET environment variable is not set")

SECRET = SECRET.encode()


def _canonical_json(payload: Dict) -> str:
    """
    Produce deterministic JSON string for signing.
    Order + separators MUST NEVER change.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sign_payload(payload: Dict) -> str:
    """
    Create an HMAC-SHA256 signature for a payload.
    Used by the license server ONLY.
    """
    raw = _canonical_json(payload).encode()
    return hmac.new(SECRET, raw, hashlib.sha256).hexdigest()


def verify_signature(payload: Dict, signature: str) -> bool:
    """
    Verify payload integrity and authenticity.
    Used by the CLIENT.
    """
    expected = sign_payload(payload)
    return hmac.compare_digest(expected, signature)
