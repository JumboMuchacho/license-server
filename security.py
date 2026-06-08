import json
import hmac
import hashlib

# -------------------------------------------------
# Cryptographic parameters
# -------------------------------------------------

# IMPORTANT:
# This salt MUST match the client exactly.
# It is NOT a secret — it is a derivation constant.
SALT = b"popup_detector_v2_secure_salt_2024"

PBKDF2_ITERATIONS = 100_000
KEY_LENGTH = 32  # 256-bit HMAC key


# -------------------------------------------------
# Secret derivation (device-bound)
# -------------------------------------------------

def derive_device_secret(device_id: str) -> bytes:
    """
    Derive a per-device HMAC secret using PBKDF2.
    This replaces the old LICENSE_SECRET model.
    """
    return hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=device_id.encode("utf-8"),
        salt=SALT,
        iterations=PBKDF2_ITERATIONS,
        dklen=KEY_LENGTH,
    )


# -------------------------------------------------
# Payload signing
# -------------------------------------------------

def sign_payload(payload: dict) -> str:
    """
    Create a cryptographic signature for a payload.

    The payload MUST contain a 'device' field.
    """
    if "device" not in payload:
        raise ValueError("Payload missing required 'device' field")

    # Canonical JSON encoding (must match client exactly)
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    secret = derive_device_secret(payload["device"])

    return hmac.new(
        secret,
        raw,
        hashlib.sha256
    ).hexdigest()


# -------------------------------------------------
# Signature verification (server-side rules endpoint)
# -------------------------------------------------

def verify_signature(envelope: dict, client_signature: str, derived_secret: bytes) -> bool:
    """
    Verify that the incoming payload signature matches the derived device secret.
    Minimizes and sorts dictionary keys exactly like JavaScript's JSON.stringify().
    """
    try:
        # 1. Canonical JSON representation matching extension's JSON.stringify()
        serialized_envelope = json.dumps(envelope, separators=(',', ':'), sort_keys=True)

        # 2. Compute the HMAC-SHA256 signature using the derived secret
        computed_hash = hmac.new(
            derived_secret,
            serialized_envelope.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # 3. Securely compare strings to prevent timing attacks
        return hmac.compare_digest(computed_hash, client_signature)
    except Exception:
        return False
