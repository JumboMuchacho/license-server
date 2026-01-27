import hmac
import hashlib
import json
from typing import Dict

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

def sign_payload(payload: Dict, secret: str) -> str:
    """
    Create an HMAC-SHA256 signature for a payload.
    Used by the license server ONLY.
    
    :param payload: dict to sign
    :param secret: the LICENSE_SECRET string
    :return: hex signature string
    """
    raw = _canonical_json(payload).encode()
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

def verify_signature(payload: Dict, signature: str, secret: str) -> bool:
    """
    Verify payload integrity and authenticity.
    Used by the CLIENT.

    :param payload: dict to verify
    :param signature: hex string signature to compare
    :param secret: LICENSE_SECRET string
    :return: True if valid, False if invalid
    """
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature)
