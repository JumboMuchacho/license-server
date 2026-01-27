import hmac
import hashlib
import json
import os
from dotenv import load_dotenv

# Ensure .env variables are loaded into the environment
load_dotenv()

# Look for the secret in environment variables
SECRET = os.getenv("LICENSE_SECRET")

# Safeguard: Crash immediately if the secret isn't found
if not SECRET:
    raise ValueError("CRITICAL ERROR: LICENSE_SECRET not found in environment variables!")

def sign_payload(payload: dict) -> str:
    """Creates a cryptographic signature of the payload."""
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hmac.new(
        SECRET.encode(),
        raw.encode(),
        hashlib.sha256
    ).hexdigest()

def verify_signature(payload: dict, signature: str) -> bool:
    """Verifies that the signature matches the payload and the secret key."""
    return hmac.compare_digest(sign_payload(payload), signature)