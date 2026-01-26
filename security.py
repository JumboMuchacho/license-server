import hmac
import hashlib
import json
import os

SECRET = os.getenv("LICENSE_SECRET", "CHANGE_ME_NOW").encode()


def sign_payload(payload: dict) -> str:
    """
    Create an HMAC-SHA256 signature for a JSON payload
    """
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hmac.new(SECRET, raw.encode(), hashlib.sha256).hexdigest()


def verify_signature(payload: dict, signature: str) -> bool:
    """
    Verify payload integrity
    """
    expected = sign_payload(payload)
    return hmac.compare_digest(expected, signature)
