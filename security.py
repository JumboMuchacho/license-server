import hmac
import hashlib
import json
import os
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# --- Configuration ---
PBKDF2_ITERATIONS = 100_000
KEY_LENGTH = 32
SALT = os.getenv("SECRET_SALT", "").encode("utf-8")

if not SALT:
    raise RuntimeError("SECRET_SALT environment variable is not set!")

# --- Auth Dependency ---
security = HTTPBearer()

async def verify_oauth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verifies the Bearer token."""
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    # Add actual JWT validation logic here if needed
    return token

# --- Crypto Helpers ---
def derive_device_secret(device_id: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", device_id.encode("utf-8"), SALT, PBKDF2_ITERATIONS, dklen=KEY_LENGTH)

def verify_raw_signature(device_id: str, timestamp: int, incoming_signature: str) -> bool:
    try:
        derived_key = derive_device_secret(device_id)
        raw_message = f"{device_id}:{timestamp}"
        computed = hmac.new(derived_key, raw_message.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, incoming_signature)
    except Exception:
        return False

def sign_payload(payload: dict) -> str:
    if "device" not in payload: raise ValueError("Missing 'device' field")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    secret = derive_device_secret(payload["device"])
    return hmac.new(secret, raw, hashlib.sha256).hexdigest()
