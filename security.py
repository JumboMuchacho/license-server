import hmac
import hashlib
import json
import os
import re
import time

from fastapi import HTTPException

# --- Configuration ---
PBKDF2_ITERATIONS = 100_000
KEY_LENGTH = 32
REQUEST_TIMESTAMP_TOLERANCE = int(os.getenv("REQUEST_TIMESTAMP_TOLERANCE", "300"))
SALT = os.getenv("SECRET_SALT", "").encode("utf-8")

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

if not SALT:
    raise RuntimeError("SECRET_SALT environment variable is not set!")


def validate_device_id(device_id: str) -> None:
    if not device_id or not UUID_PATTERN.match(device_id):
        raise HTTPException(status_code=400, detail="Invalid device_id format.")


def validate_request_timestamp(timestamp: int) -> None:
    if abs(int(time.time()) - int(timestamp)) > REQUEST_TIMESTAMP_TOLERANCE:
        raise HTTPException(status_code=401, detail="Request expired.")


def derive_device_secret(device_id: str) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        device_id.encode("utf-8"),
        SALT,
        PBKDF2_ITERATIONS,
        dklen=KEY_LENGTH,
    )


def verify_raw_signature(
    device_id: str, timestamp: int, incoming_signature: str
) -> bool:
    try:
        derived_key = derive_device_secret(device_id)
        raw_message = f"{device_id}:{timestamp}"
        computed = hmac.new(
            derived_key, raw_message.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(computed, incoming_signature)
    except Exception:
        return False


def verify_device_request(
    device_id: str, timestamp: int, incoming_signature: str
) -> None:
    """Validate device identity, freshness, and HMAC signature."""
    validate_device_id(device_id)
    validate_request_timestamp(timestamp)
    if not verify_raw_signature(device_id, int(timestamp), incoming_signature):
        raise HTTPException(status_code=403, detail="Invalid signature.")


def sign_payload(payload: dict) -> str:
    if "device" not in payload:
        raise ValueError("Missing 'device' field")
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    secret = derive_device_secret(payload["device"])
    return hmac.new(secret, raw, hashlib.sha256).hexdigest()
