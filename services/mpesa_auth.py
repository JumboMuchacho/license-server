import base64
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests

# Type-safe cache initialization
_token_cache: Dict[str, Any] = {
    "token": None,
    "expires_at": datetime.min,
}


def _mpesa_base_url() -> str:
    return os.getenv("MPESA_BASE_URL", "https://sandbox.safaricom.co.ke").rstrip("/")


def get_mpesa_access_token() -> str:
    # 1. Safely retrieve and check cache
    token = _token_cache.get("token")
    expires_at: Optional[datetime] = _token_cache.get("expires_at")

    if token and expires_at and datetime.now() < expires_at:
        return str(token)

    # 2. Prepare credentials
    consumer_key = os.getenv("MPESA_CONSUMER_KEY")
    consumer_secret = os.getenv("MPESA_CONSUMER_SECRET")

    if not consumer_key or not consumer_secret:
        raise Exception("M-Pesa credentials not configured.")

    credentials = f"{consumer_key}:{consumer_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    # 3. Fetch new token
    api_url = f"{_mpesa_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    headers = {"Authorization": f"Basic {encoded_credentials}"}

    response = requests.get(api_url, headers=headers, timeout=10)
    if response.status_code != 200:
        raise Exception("Failed to authenticate with M-Pesa.")

    data = response.json()
    new_token = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))

    # 4. Update cache
    _token_cache["token"] = new_token
    _token_cache["expires_at"] = datetime.now() + timedelta(seconds=expires_in - 60)

    return str(new_token)
