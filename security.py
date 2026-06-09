import hmac
import hashlib

# Constant for key derivation (must match client exactly)
SALT = b"popup_detector_v2_secure_salt_2024"
PBKDF2_ITERATIONS = 100_000
KEY_LENGTH = 32  # 256-bit key

def derive_device_secret(device_id: str) -> bytes:
    """
    Derive a strong cryptographic key from the unique device ID using PBKDF2.
    Protects your signature keys from brute-force lookup if the database leaks.
    """
    return hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=device_id.encode("utf-8"),
        salt=SALT,
        iterations=PBKDF2_ITERATIONS,
        dklen=KEY_LENGTH,
    )

def verify_raw_signature(device_id: str, timestamp: int, incoming_signature: str) -> bool:
    """
    Verifies the signature using a raw concatenated format (device_id:timestamp).
    No JSON formatting dependencies, meaning zero serialization mismatches.
    """
    try:
        # Derive the cryptographic key unique to this device ID
        derived_key = derive_device_secret(device_id)

        # Rebuild the deterministic message payload string
        raw_message_string = f"{device_id}:{timestamp}"

        # Calculate expected HMAC-SHA256 signature
        computed_signature = hmac.new(
            derived_key,
            raw_message_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison to protect against timing analysis attacks
        return hmac.compare_digest(computed_signature, incoming_signature)
    except Exception:
        return False
import json

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
