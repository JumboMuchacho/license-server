import hmac
import hashlib
import json
import os

# --- Configuration ---
# Hardcoded parameters that must match the client exactly
PBKDF2_ITERATIONS = 100_000
KEY_LENGTH = 32

# Salt fetched from environment variable for production security
SALT_ENV = os.getenv("SECRET_SALT")
if not SALT_ENV:
    raise RuntimeError("SECRET_SALT environment variable is not set!")
SALT = SALT_ENV.encode("utf-8")

def derive_device_secret(device_id: str) -> bytes:
    """Derives a cryptographic key using PBKDF2."""
    return hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=device_id.encode("utf-8"),
        salt=SALT,
        iterations=PBKDF2_ITERATIONS,
        dklen=KEY_LENGTH,
    )

def verify_raw_signature(device_id: str, timestamp: int, incoming_signature: str) -> bool:
    """Verifies signature using raw concatenated format (device_id:timestamp)."""
    try:
        derived_key = derive_device_secret(device_id)
        raw_message_string = f"{device_id}:{timestamp}"

        computed_signature = hmac.new(
            derived_key,
            raw_message_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(computed_signature, incoming_signature)
    except Exception:
        return False

def sign_payload(payload: dict) -> str:
    """Creates a cryptographic signature for a dictionary payload."""
    if "device" not in payload:
        raise ValueError("Payload missing required 'device' field")

    # Canonical JSON encoding ensures identical hashes on client and server
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
